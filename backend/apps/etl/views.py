import os
from django.utils import timezone
from rest_framework import status, generics, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Paciente, RegistroClinico, EjecucionETL, Alerta, DatasetCache
from .serializers import (
    PacienteSerializer, RegistroClinicoSerializer, EjecucionETLSerializer,
    AlertaSerializer, DatasetCacheSerializer,
)
from apps.authentication.permissions import EsAdministrador, EsAnalista, EsMedico, puede_analizar

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


# ─────────────────────────────────────────────────────────────────────────────
# NUEVO V4.2 — Caché real del archivo subido
# ─────────────────────────────────────────────────────────────────────────────
def cachear_archivo_subido(archivo, usuario) -> DatasetCache:
    """
    Persiste el archivo subido en MEDIA_ROOT/etl_cache/ y lo registra como
    el dataset "activo" para que pueda reutilizarse después sin que el
    usuario tenga que volver a seleccionarlo desde su computador.

    IMPORTANTE: se llama ANTES de leer/consumir el stream del archivo
    (extract, validate, etc.), porque una vez que `archivo.chunks()` se
    recorre una vez, el puntero queda al final y guardarlo después
    produciría un archivo vacío.
    """
    cache = DatasetCache.objects.create(
        archivo=archivo,
        nombre_original=archivo.name,
        tamaño_bytes=archivo.size,
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
    )
    cache.marcar_como_activo()
    return cache


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
    """
    POST /api/etl/run/
    FIX V4.2: el archivo subido ya NO se descarta tras procesarlo.
    Se persiste en DatasetCache para poder "Reutilizarlo" más adelante
    (ver ReutilizarETLView) sin volver a pedírselo al usuario.
    """
    permission_classes = [EsAnalista]

    def post(self, request) -> Response:
        archivo = request.FILES.get('archivo')
        error = validar_archivo_etl(archivo)
        if error:
            return Response({'error': error}, status=400)

        # FIX V4.2: cachear ANTES de leer el archivo (ver docstring de la función)
        cache = cachear_archivo_subido(archivo, request.user)
        ruta  = cache.archivo.path

        try:
            from .pipeline import ETLPipeline
            from .extractors import CSVExtractor, ExcelExtractor
            from .validators import CSVFormatValidator

            extractor  = ExcelExtractor() if ruta.endswith(('.xlsx', '.xls')) else CSVExtractor()
            df_preview = extractor.extract(ruta)

            cache.registros_detectados = len(df_preview)
            cache.save(update_fields=['registros_detectados'])

            valido, errores, advertencias = CSVFormatValidator().validate(df_preview)
            if not valido:
                return Response({'error': 'Formato inválido', 'errores': errores,
                                  'advertencias': advertencias}, status=400)

            result = ETLPipeline(
                usuario=request.user, tipo='manual', dataset_cache=cache,
            ).run(ruta)
            result['advertencias']     = advertencias
            result['dataset_cache_id'] = cache.id
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


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
    FIX V4.2: también cachea el archivo real (igual que RunETLView).
    """
    permission_classes = [EsAnalista]

    def post(self, request) -> Response:
        archivo = request.FILES.get('archivo')
        error = validar_archivo_etl(archivo)
        if error:
            return Response({'error': error}, status=400)

        cache = cachear_archivo_subido(archivo, request.user)
        ruta  = cache.archivo.path
        try:
            from .tasks import run_etl_task
            task = run_etl_task.delay(
                source_path=ruta,
                usuario_id=request.user.id if request.user.is_authenticated else None,
                tipo='manual',
                dataset_cache_id=cache.id,
            )
            return Response({
                'task_id':          task.id,
                'estado':           'iniciado',
                'dataset_cache_id': cache.id,
                'mensaje': 'ETL iniciado en background. Consulta el progreso en /api/etl/task/<task_id>/',
            })
        except Exception as e:
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


# ─────────────────────────────────────────────────────────────────────────────
# ETL "Usar anterior" / "Reutilizar"  — CORREGIDO V4.2
# ─────────────────────────────────────────────────────────────────────────────
class ReutilizarETLView(APIView):
    """
    GET  /api/etl/reutilizar/
        Info del dataset cacheado actual. Visible a TODOS los roles
        autenticados (médico, analista, administrador) — el médico no
        puede subir archivos, pero sí necesita ver qué dataset está
        cargado y cuándo se actualizó por última vez.

    POST /api/etl/reutilizar/
        Reprocesa el pipeline ETL usando el ARCHIVO REAL cacheado.
        ANTES (bug): generaba registros simulados nuevos con
        DataSimulator, sin relación alguna con el archivo original.
        AHORA: reutiliza exactamente el mismo archivo subido la última
        vez. Sólo Analista/Administrador pueden ejecutar el POST.
    """
    permission_classes = [EsMedico]   # EsMedico permite médico+analista+administrador (ver permissions.py)

    def get(self, request):
        cache = DatasetCache.objects.filter(activo=True).first()
        if not cache:
            return Response({
                'disponible': False,
                'mensaje': 'Aún no se ha subido ningún dataset clínico.',
            })
        return Response({
            'disponible':           True,
            'id':                   cache.id,
            'nombre_archivo':       cache.nombre_original,
            'fecha_subida':         cache.fecha_subida.strftime('%d/%m/%Y %H:%M'),
            'subido_por':           str(cache.usuario) if cache.usuario else 'Desconocido',
            'registros_detectados': cache.registros_detectados,
            'tamaño':               cache.tamaño_legible,
            # El frontend usa esto para mostrar/ocultar el botón "Reutilizar"
            'puede_reutilizar':     puede_analizar(request.user),
        })

    def post(self, request):
        # FIX: sólo analista/administrador puede disparar el reproceso real
        if not puede_analizar(request.user):
            return Response(
                {'error': 'No tienes permiso para ejecutar el ETL. Solo Analista o Administrador.'},
                status=403,
            )

        cache = DatasetCache.objects.filter(activo=True).first()
        if not cache:
            return Response({'error': 'No hay ningún dataset en caché para reutilizar.'}, status=400)

        ruta = cache.archivo.path
        if not os.path.exists(ruta):
            return Response(
                {'error': 'El archivo cacheado ya no existe en el servidor. Sube el archivo de nuevo.'},
                status=404,
            )

        try:
            from .pipeline import ETLPipeline
            result = ETLPipeline(
                usuario=request.user, tipo='reutilizado', dataset_cache=cache,
            ).run(ruta)
            result['mensaje'] = f'ETL reutilizado con el archivo real: {cache.nombre_original}'
            result['dataset_cache_id'] = cache.id
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class DatasetCacheHistorialView(generics.ListAPIView):
    """
    GET /api/etl/datasets-cache/
    Historial de los últimos archivos subidos (auditoría / evidencia ETL).
    Visible para analista/administrador.
    """
    permission_classes = [EsAnalista]
    serializer_class   = DatasetCacheSerializer

    def get_queryset(self):
        return DatasetCache.objects.all()[:10]


# ─── Descarga del dataset limpio tras el ETL ──────────────────────────────────
import io
import pandas as pd
from django.http import HttpResponse
from django.shortcuts import get_object_or_404


class DescargarDatasetLimpioView(APIView):
    """
    GET /api/etl/descargar/<pk>/
    Descarga el dataset limpio procesado en una ejecución ETL específica.
    Formato: ?formato=xlsx (default) | csv
    Permite al analista obtener evidencia del proceso ETL como archivo.
    """
    permission_classes = [EsAnalista]

    def get(self, request, pk: int):
        ejecucion = get_object_or_404(EjecucionETL, pk=pk, estado='completado')
        fmt = request.query_params.get('formato', 'xlsx').lower()

        registros = RegistroClinico.objects.filter(
            ejecucion_etl=ejecucion
        ).select_related('paciente').values(
            'paciente__id_paciente_original',
            'paciente__nombres',
            'paciente__apellidos',
            'paciente__edad',
            'paciente__sexo',
            'peso', 'altura', 'imc',
            'presion_sistolica', 'presion_diastolica', 'frecuencia_cardiaca',
            'glucosa', 'colesterol', 'saturacion_oxigeno', 'temperatura',
            'paciente__antecedentes_familiares',
            'fumador', 'consumo_alcohol', 'actividad_fisica',
            'diagnostico_preliminar', 'riesgo_enfermedad', 'fecha_consulta',
        )

        df = pd.DataFrame(list(registros))

        if df.empty:
            return Response(
                {'error': f'Sin registros para la ejecución ETL #{pk}'},
                status=404,
            )

        df = df.rename(columns={
            'paciente__id_paciente_original': 'id_paciente',
            'paciente__nombres':              'nombres',
            'paciente__apellidos':            'apellidos',
            'paciente__edad':                 'edad',
            'paciente__sexo':                 'sexo',
            'imc':                            'IMC',
            'presion_sistolica':              'presión_sistólica',
            'presion_diastolica':             'presión_diastólica',
            'frecuencia_cardiaca':            'frecuencia_cardiaca',
            'saturacion_oxigeno':             'saturación_oxígeno',
            'paciente__antecedentes_familiares': 'antecedentes_familiares',
            'actividad_fisica':               'actividad_física',
            'diagnostico_preliminar':         'diagnóstico_preliminar',
        })

        filename_base = f"dataset_limpio_etl_{pk}"

        if fmt == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
            df.to_csv(response, index=False, encoding='utf-8-sig')
            return response

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Dataset_ETL_Limpio')
        buffer.seek(0)

        response = HttpResponse(
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
        return response
