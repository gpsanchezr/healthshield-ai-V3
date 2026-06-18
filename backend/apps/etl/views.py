import os
import tempfile
from django.utils import timezone
from rest_framework import status, generics, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Paciente, RegistroClinico, EjecucionETL, Alerta
from .serializers import PacienteSerializer, RegistroClinicoSerializer, EjecucionETLSerializer, AlertaSerializer
from apps.authentication.permissions import EsAdministrador, EsAnalista, EsMedico

MAX_ETL_UPLOAD_SIZE = 20 * 1024 * 1024
ALLOWED_ETL_EXTENSIONS = ('.csv', '.xlsx', '.xls')

def validar_archivo_etl(archivo):
    if not archivo:
        return 'Se requiere un archivo CSV o Excel.'
    if archivo.size > MAX_ETL_UPLOAD_SIZE:
        return f'Archivo demasiado grande: {archivo.size/1024/1024:.1f} MB. Maximo permitido: 20 MB.'
    if not archivo.name.lower().endswith(ALLOWED_ETL_EXTENSIONS):
        return f'Formato no soportado: {archivo.name}. Usa CSV, XLSX o XLS.'
    return None

def guardar_archivo_temporal(archivo, prefix):
    suffix = os.path.splitext(archivo.name)[1].lower() or '.csv'
    with tempfile.NamedTemporaryFile(delete=False, prefix=prefix, suffix=suffix) as tmp:
        for chunk in archivo.chunks():
            tmp.write(chunk)
        return tmp.name

class PacienteListView(generics.ListAPIView):
    queryset = Paciente.objects.prefetch_related('registros').all()
    serializer_class = PacienteSerializer
    permission_classes = [EsMedico]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sexo']
    search_fields = ['nombres', 'apellidos', 'id_paciente_original', 'cedula']
    ordering_fields = ['apellidos', 'edad', 'id_paciente_original']

class PacienteDetailView(generics.RetrieveAPIView):
    queryset = Paciente.objects.prefetch_related('registros')
    serializer_class = PacienteSerializer
    permission_classes = [EsMedico]
    def retrieve(self, request, *args, **kwargs):
        p = self.get_object()
        data = PacienteSerializer(p).data
        registros = RegistroClinico.objects.filter(paciente=p).order_by('-fecha_consulta')
        data['registros'] = RegistroClinicoSerializer(registros, many=True).data
        return Response(data)

class RegistroClinicoListView(generics.ListAPIView):
    queryset = RegistroClinico.objects.select_related('paciente').all()
    serializer_class = RegistroClinicoSerializer
    permission_classes = [EsMedico]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['riesgo_enfermedad', 'diagnostico_preliminar', 'fumador', 'paciente__sexo']
    ordering_fields = ['fecha_consulta', 'riesgo_enfermedad']

class RunETLView(APIView):
    permission_classes = [EsAnalista]
    def post(self, request) -> Response:
        archivo = request.FILES.get('archivo')
        if not archivo:
            return Response({'error': 'Se requiere un archivo CSV o Excel.'}, status=400)

        # Validar tamaño máximo (20 MB)
        MAX_SIZE = 20 * 1024 * 1024
        if archivo.size > MAX_SIZE:
            return Response({
                'error': f'Archivo demasiado grande: {archivo.size/1024/1024:.1f} MB. Máximo permitido: 20 MB.'
            }, status=400)

        # Validar extensión
        nombre = archivo.name.lower()
        if not any(nombre.endswith(ext) for ext in ['.csv', '.xlsx', '.xls']):
            return Response({
                'error': f'Formato no soportado: {archivo.name}. Usa CSV, XLSX o XLS.'
            }, status=400)
        tmp = guardar_archivo_temporal(archivo, 'etl_')
        try:
            from .pipeline import ETLPipeline
            from .extractors import CSVExtractor, ExcelExtractor
            from .validators import CSVFormatValidator
            # Validar formato antes de ejecutar ETL
            extractor = ExcelExtractor() if tmp.endswith(('.xlsx','.xls')) else CSVExtractor()
            df_preview = extractor.extract(tmp)
            valido, errores, advertencias = CSVFormatValidator().validate(df_preview)
            if not valido:
                return Response({'error': 'Formato inválido', 'errores': errores,
                                 'advertencias': advertencias}, status=400)
            result = ETLPipeline(usuario=request.user, tipo='manual').run(tmp)
            result['advertencias'] = advertencias
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
        finally:
            if os.path.exists(tmp): os.remove(tmp)

class SimulateDataView(APIView):
    permission_classes = [EsAdministrador]
    def post(self, request) -> Response:
        count = int(request.data.get('count', 10))
        if not 1 <= count <= 500:
            return Response({'error': 'count debe estar entre 1 y 500'}, status=400)
        from .simulation import DataSimulator
        from .pipeline import ETLPipeline
        df = DataSimulator().generate(count)
        result = ETLPipeline(usuario=request.user, tipo='simulacion').run_dataframe(df)
        return Response(result)

class HistorialETLView(generics.ListAPIView):
    queryset = EjecucionETL.objects.all()
    serializer_class = EjecucionETLSerializer
    permission_classes = [EsAnalista]

class CalidadReporteView(APIView):
    permission_classes = [EsAnalista]
    def get(self, request, pk: int) -> Response:
        try:
            e = EjecucionETL.objects.get(pk=pk)
            return Response(e.reporte_calidad or {'error': 'Sin reporte'})
        except EjecucionETL.DoesNotExist:
            return Response({'error': 'No encontrada'}, status=404)

class AlertaListView(generics.ListAPIView):
    queryset = Alerta.objects.select_related('paciente').filter(fecha_vista__isnull=True)
    serializer_class = AlertaSerializer
    permission_classes = [EsMedico]

class AlertaMarcarVistaView(APIView):
    permission_classes = [EsMedico]
    def patch(self, request, pk: int) -> Response:
        try:
            a = Alerta.objects.get(pk=pk)
            a.visto_por = request.user
            a.fecha_vista = timezone.now()
            a.save()
            return Response({'status': 'marcada como vista'})
        except Alerta.DoesNotExist:
            return Response({'error': 'No encontrada'}, status=404)


class RunETLAsyncView(APIView):
    """
    POST /api/etl/run-async/
    Lanza el ETL en background con Celery y retorna task_id inmediatamente.
    Usa GET /api/etl/task/<task_id>/ para consultar el progreso.
    """
    permission_classes = [EsAnalista]

    def post(self, request) -> Response:
        archivo = request.FILES.get('archivo')
        error = validar_archivo_etl(archivo)
        if error:
            return Response({'error': error}, status=400)
        tmp = guardar_archivo_temporal(archivo, 'etl_async_')
        try:
            from .tasks import run_etl_task
            task = run_etl_task.delay(
                source_path=tmp,
                usuario_id=request.user.id if request.user.is_authenticated else None,
                tipo='manual',
            )
            return Response({
                'task_id': task.id,
                'estado':  'iniciado',
                'mensaje': 'ETL iniciado en background. Consulta el progreso en /api/etl/task/<task_id>/',
            })
        except Exception as e:
            if os.path.exists(tmp): os.remove(tmp)
            return Response({'error': str(e)}, status=500)


class TaskStatusView(APIView):
    """
    GET /api/etl/task/<task_id>/
    Consulta el estado y progreso de una tarea Celery.
    """
    permission_classes = [EsAnalista]

    def get(self, request, task_id: str):
        try:
            from celery.result import AsyncResult
            task = AsyncResult(task_id)
            info = task.info or {}
            return Response({
                'task_id': task_id,
                'estado':  task.state,
                'progreso': info.get('progreso', 0) if isinstance(info, dict) else 0,
                'paso':     info.get('paso', '') if isinstance(info, dict) else '',
                'resultado': task.result if task.state == 'SUCCESS' else None,
                'error':     str(task.result) if task.state == 'FAILURE' else None,
            })
        except Exception as e:
            return Response({'task_id': task_id, 'estado': 'UNKNOWN', 'error': str(e)})


class EstadisticasCalidadView(APIView):
    """
    GET /api/etl/calidad-historica/
    Retorna las estadísticas de calidad de las últimas N ejecuciones ETL.
    Permite al dashboard mostrar la evolución del quality_score con el tiempo.
    """
    permission_classes = [EsAnalista]

    def get(self, request) -> Response:
        limite = int(request.query_params.get('limite', 10))
        ejecuciones = EjecucionETL.objects.filter(
            estado='completado',
            reporte_calidad__isnull=False,
        ).order_by('-fecha_inicio')[:limite]

        datos = []
        for e in reversed(list(ejecuciones)):
            rpt = e.reporte_calidad or {}
            datos.append({
                'id':                    e.id,
                'fecha':                 e.fecha_inicio.strftime('%d/%m %H:%M'),
                'quality_score':         rpt.get('quality_score', 0),
                'clasificacion':         rpt.get('clasificacion', ''),
                'registros_procesados':  e.registros_procesados,
                'registros_rechazados':  e.registros_rechazados,
                'duracion_segundos':     float(e.duracion_segundos or 0),
                'tipo':                  e.tipo,
                'acciones': {
                    'duplicados':    rpt.get('acciones_correctivas', {}).get('duplicados_eliminados', 0),
                    'nulos':         rpt.get('acciones_correctivas', {}).get('nulos_imputados', 0),
                    'outliers':      rpt.get('acciones_correctivas', {}).get('outliers_corregidos', 0),
                    'diagnosticos':  rpt.get('acciones_correctivas', {}).get('diagnosticos_normalizados', 0),
                },
            })

        # Calcular tendencia del quality_score
        scores = [d['quality_score'] for d in datos if d['quality_score'] > 0]
        tendencia = 'estable'
        if len(scores) >= 2:
            if scores[-1] > scores[0] + 2:   tendencia = 'mejorando'
            elif scores[-1] < scores[0] - 2: tendencia = 'empeorando'

        return Response({
            'datos':             datos,
            'promedio_score':    round(sum(scores) / len(scores), 2) if scores else 0,
            'mejor_score':       max(scores, default=0),
            'peor_score':        min(scores, default=0),
            'tendencia':         tendencia,
            'total_ejecuciones': len(datos),
        })


# ─── Consulta Médica — CRUD ───────────────────────────────────────────────────
from .models import ConsultaMedica
from .serializers import ConsultaMedicaSerializer

class ConsultaMedicaListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/etl/consultas/?paciente=<pk>  → historial de consultas del paciente
    POST /api/etl/consultas/               → registrar nueva consulta
    """
    serializer_class   = ConsultaMedicaSerializer
    permission_classes = [EsMedico]

    def get_queryset(self):
        qs = ConsultaMedica.objects.select_related('paciente', 'medico').all()
        pk = self.request.query_params.get('paciente')
        if pk:
            qs = qs.filter(paciente_id=pk)
        return qs

    def perform_create(self, serializer):
        serializer.save(medico=self.request.user)


class ConsultaMedicaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE /api/etl/consultas/<pk>/
    """
    queryset           = ConsultaMedica.objects.select_related('paciente', 'medico').all()
    serializer_class   = ConsultaMedicaSerializer
    permission_classes = [EsMedico]


# ─── ETL "Usar anterior" ──────────────────────────────────────────────────────
class ReutilizarETLView(APIView):
    """
    GET  /api/etl/reutilizar/  → info del último ETL ejecutado
    POST /api/etl/reutilizar/  → volver a simular con el mismo conteo
    """
    permission_classes = [EsAnalista]

    def get(self, request):
        ultimo = EjecucionETL.objects.filter(estado='completado').order_by('-fecha_inicio').first()
        if not ultimo:
            return Response({'disponible': False, 'mensaje': 'Sin ETL previo ejecutado.'})
        return Response({
            'disponible':            True,
            'id':                    ultimo.id,
            'fecha':                 ultimo.fecha_inicio.strftime('%d/%m/%Y %H:%M'),
            'registros_procesados':  ultimo.registros_procesados,
            'tipo':                  ultimo.tipo,
            'archivo_fuente':        ultimo.archivo_fuente or 'simulación',
        })

    def post(self, request):
        ultimo = EjecucionETL.objects.filter(estado='completado').order_by('-fecha_inicio').first()
        if not ultimo:
            return Response({'error': 'No hay ETL previo para reutilizar.'}, status=400)
        count = max(10, min(ultimo.registros_procesados, 500))
        try:
            from .simulation import DataSimulator
            from .pipeline import ETLPipeline
            df = DataSimulator().generate(count)
            result = ETLPipeline(usuario=request.user, tipo='reutilizado').run_dataframe(df)
            return Response({**result, 'mensaje': f'ETL reutilizado: {count} registros simulados.'})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
