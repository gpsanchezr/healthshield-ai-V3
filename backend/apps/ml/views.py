from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from apps.authentication.permissions import EsAdministrador, EsAnalista, EsMedico
from .models import ModeloML, Prediccion
from .serializers import ModeloMLSerializer, PrediccionSerializer

class ModeloMetricasView(APIView):
    permission_classes = [EsMedico]
    def get(self, request) -> Response:
        modelo = ModeloML.objects.filter(activo=True).first()
        if not modelo:
            return Response({'error': 'No hay modelo activo. Ejecuta: python manage.py train_model'}, status=404)
        return Response(ModeloMLSerializer(modelo).data)

class ModeloHistorialView(generics.ListAPIView):
    queryset = ModeloML.objects.all()
    serializer_class = ModeloMLSerializer
    permission_classes = [EsAdministrador]

class PredecirPacienteView(APIView):
    permission_classes = [EsMedico]
    def post(self, request, pk: int) -> Response:
        from apps.etl.models import RegistroClinico, Paciente
        try:
            paciente = Paciente.objects.get(pk=pk)
            registro = RegistroClinico.objects.filter(paciente=paciente).latest('fecha_consulta')
        except (Paciente.DoesNotExist, RegistroClinico.DoesNotExist):
            return Response({'error': 'Paciente o registro no encontrado'}, status=404)

        modelo = ModeloML.objects.filter(activo=True).first()
        if not modelo:
            return Response({'error': 'No hay modelo entrenado activo'}, status=404)

        from .predictor import ClinicalPredictor
        predictor = ClinicalPredictor(modelo.archivo_modelo)
        data = {
            'edad': paciente.edad, 'imc': float(registro.imc or 0),
            'presion_sistolica': registro.presion_sistolica,
            'presion_diastolica': registro.presion_diastolica,
            'frecuencia_cardiaca': registro.frecuencia_cardiaca,
            'glucosa': float(registro.glucosa or 0),
            'colesterol': float(registro.colesterol or 0),
            'saturacion_oxigeno': float(registro.saturacion_oxigeno or 0),
            'temperatura': float(registro.temperatura or 0),
            'fumador': registro.fumador,
            'consumo_alcohol': registro.consumo_alcohol,
            'antecedentes_familiares': registro.antecedentes_familiares,
        }
        resultado = predictor.predict(data)

        # Guardar predicción
        Prediccion.objects.create(
            paciente=paciente, modelo=modelo,
            riesgo_predicho=resultado['riesgo_predicho'],
            probabilidad=resultado['probabilidad_max'],
            factores_clave=resultado['factores_clave'],
        )
        return Response({**resultado, 'paciente_id': pk, 'paciente': str(paciente)})

class EntrenarModeloView(APIView):
    permission_classes = [EsAdministrador]
    def post(self, request) -> Response:
        import pandas as pd
        from apps.etl.models import RegistroClinico
        from .trainer import ModelTrainer
        algorithm = request.data.get('algorithm', 'random_forest')
        qs = RegistroClinico.objects.all().values(
            'imc','presion_sistolica','presion_diastolica','frecuencia_cardiaca',
            'glucosa','colesterol','saturacion_oxigeno','temperatura',
            'fumador','consumo_alcohol','antecedentes_familiares','riesgo_enfermedad',
            'paciente__edad')
        if not qs.exists():
            return Response({'error': 'Sin datos. Ejecuta el ETL primero.'}, status=400)
        df = pd.DataFrame(list(qs)).rename(columns={'paciente__edad':'edad'})
        result = ModelTrainer(algorithm).train(df)
        ModeloML.objects.filter(activo=True).update(activo=False)
        modelo = ModeloML.objects.create(
            nombre=f"HealthShield {algorithm.replace('_',' ').title()}",
            algoritmo=algorithm, version=f"v{ModeloML.objects.count()+1}",
            accuracy=result['accuracy'], precision_score=result['precision'],
            recall=result['recall'], f1_score=result['f1_score'],
            archivo_modelo=result['model_path'], feature_names=result['features'],
            feature_importance=result['feature_importance'],
            registros_entrenamiento=result['training_samples'], activo=True)
        return Response({**result, 'modelo_id': modelo.id})

class PrediccionListView(generics.ListAPIView):
    queryset = Prediccion.objects.select_related('paciente','modelo').all()
    serializer_class = PrediccionSerializer
    permission_classes = [EsMedico]


class AnalisisIAView(APIView):
    """
    POST /api/predicciones/analisis-ia/<pk>/
    Genera análisis clínico narrativo con IA generativa.

    Soporta múltiples proveedores:
    - Body: {"proveedor": "claude"}   → Claude (Anthropic)
    - Body: {"proveedor": "gemini"}   → Gemini (Google)
    Si no se especifica, usa Claude por defecto.

    Requiere ANTHROPIC_API_KEY o GEMINI_API_KEY en .env según el proveedor.
    """
    permission_classes = [EsMedico]

    def post(self, request, pk: int):
        from apps.etl.models import RegistroClinico, Paciente
        from .ai_providers import get_provider, get_providers_status

        try:
            paciente = Paciente.objects.get(pk=pk)
            registro = RegistroClinico.objects.filter(
                paciente=paciente
            ).latest('fecha_consulta')
        except (Paciente.DoesNotExist, RegistroClinico.DoesNotExist):
            return Response({'error': 'Paciente o registro no encontrado'}, status=404)

        modelo_ml = ModeloML.objects.filter(activo=True).first()
        if not modelo_ml:
            return Response(
                {'error': 'No hay modelo ML activo. Ejecuta: python manage.py train_model'},
                status=404,
            )

        from .predictor import ClinicalPredictor
        predictor = ClinicalPredictor(modelo_ml.archivo_modelo)

        datos_paciente = {
            'edad':                    paciente.edad,
            'sexo':                    paciente.sexo,
            'imc':                     float(registro.imc or 0),
            'clasificacion_imc':       registro.clasificacion_imc,
            'presion_sistolica':       registro.presion_sistolica,
            'presion_diastolica':      registro.presion_diastolica,
            'frecuencia_cardiaca':     registro.frecuencia_cardiaca,
            'glucosa':                 float(registro.glucosa or 0),
            'colesterol':              float(registro.colesterol or 0),
            'saturacion_oxigeno':      float(registro.saturacion_oxigeno or 0),
            'temperatura':             float(registro.temperatura or 0),
            'fumador':                 registro.fumador,
            'consumo_alcohol':         registro.consumo_alcohol,
            'antecedentes_familiares': registro.antecedentes_familiares,
            'diagnostico_preliminar':  registro.diagnostico_preliminar,
            'actividad_fisica':        registro.actividad_fisica,
        }

        prediccion = predictor.predict(datos_paciente)
        nombre_proveedor = request.data.get('proveedor', 'claude').lower()
        provider = get_provider(nombre_proveedor)
        analisis = provider.analizar_paciente(datos_paciente, prediccion)

        return Response({
            'paciente':            str(paciente),
            'prediccion':          prediccion,
            'analisis_ia':         analisis,
            'proveedores_activos': get_providers_status(),
        })


class ProveedoresIAView(APIView):
    """
    GET /api/predicciones/proveedores-ia/
    Retorna qué proveedores de IA están disponibles (API key configurada).
    """
    permission_classes = [EsMedico]

    def get(self, request) -> Response:
        from .ai_providers import get_providers_status, PROVEEDORES
        status = get_providers_status()
        return Response({
            'proveedores': [
                {
                    'id':          nombre,
                    'nombre':      cls().nombre,
                    'disponible':  status[nombre],
                    'instruccion': (
                        f'Agrega {nombre.upper()}_API_KEY en el archivo .env'
                        if not status[nombre] else 'Listo para usar'
                    ),
                }
                for nombre, cls in PROVEEDORES.items()
            ]
        })


class ConfusionMatrixView(APIView):
    """
    GET /api/predicciones/modelo/confusion-matrix/
    Retorna la matriz de confusión del modelo activo y las etiquetas de clases.
    Usada por el dashboard ML para renderizar la visualización.
    """
    permission_classes = [EsMedico]

    def get(self, request) -> Response:
        modelo = ModeloML.objects.filter(activo=True).first()
        if not modelo:
            return Response({'error': 'Sin modelo activo'}, status=404)

        # La confusion matrix se guardó en feature_importance como parte del
        # dict de entrenamiento — la guardamos en un campo separado si existe
        # o la recalculamos del último historial
        fi = modelo.feature_importance or {}
        cm = fi.get('confusion_matrix')
        cr = fi.get('classification_report', {})

        if cm is None:
            return Response({'error': 'Confusion matrix no disponible para este modelo. Reentrena.'}, status=404)

        clases = list(cr.keys()) if cr else ['Bajo', 'Medio', 'Alto', 'Crítico']
        clases = [c for c in clases if c not in ('accuracy','macro avg','weighted avg')]

        return Response({
            'confusion_matrix':       cm,
            'clases':                 clases,
            'accuracy':               float(modelo.accuracy or 0),
            'f1_score':               float(modelo.f1_score or 0),
            'classification_report':  cr,
        })
