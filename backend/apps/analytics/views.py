from rest_framework.views import APIView
from rest_framework.response import Response
from apps.authentication.permissions import EsMedico, EsAnalista
from .calculators import KPICalculator, EstadisticaDescriptiva, PacienteCriticoDetector

CAMPOS_VALIDOS = [
    'imc',
    'glucosa',
    'colesterol',
    'presion_sistolica',
    'presion_diastolica',
    'saturacion_oxigeno',
    'temperatura',
    'frecuencia_cardiaca',
]

class KPIsView(APIView):
    permission_classes = [EsMedico]
    def get(self, request) -> Response:
        return Response(KPICalculator().get_all_kpis())

class EstadisticaView(APIView):
    permission_classes = [EsAnalista | EsMedico]
    def get(self, request) -> Response:
        campo = request.query_params.get('campo', 'glucosa')
        if campo not in CAMPOS_VALIDOS:
            return Response({'error': f'Campo no válido. Use: {CAMPOS_VALIDOS}'}, status=400)
        return Response(EstadisticaDescriptiva().calcular(campo))

class DetectarCriticosView(APIView):
    permission_classes = [EsAnalista | EsMedico]
    def post(self, request) -> Response:
        creadas = PacienteCriticoDetector().detectar()
        return Response({'alertas_creadas': creadas, 'mensaje': f'{creadas} nuevas alertas críticas generadas'})

class SegmentacionView(APIView):
    permission_classes = [EsAnalista | EsMedico]
    def get(self, request) -> Response:
        from django.db.models import (
            Avg, Case, CharField, Count, IntegerField, Max, Min, Value, When
        )
        from apps.etl.models import Paciente, RegistroClinico
        por = request.query_params.get('por', 'riesgo')
        qs = RegistroClinico.objects.all()
        if por == 'riesgo':
            data = list(qs.values('riesgo_enfermedad').annotate(total=Count('id'), avg_imc=Avg('imc'), avg_glucosa=Avg('glucosa')))
        elif por == 'sexo':
            data = list(qs.values('paciente__sexo').annotate(total=Count('id'), avg_edad=Avg('paciente__edad')))
        elif por == 'diagnostico':
            data = list(qs.values('diagnostico_preliminar').annotate(total=Count('id')).order_by('-total')[:10])
        elif por == 'edad':
            pacientes = Paciente.objects.exclude(edad__isnull=True)
            limites = pacientes.aggregate(min_edad=Min('edad'), max_edad=Max('edad'))
            min_edad = limites['min_edad']
            max_edad = limites['max_edad']

            if min_edad is None or max_edad is None:
                return Response({
                    'segmentacion': 'edad',
                    'labels': [],
                    'data': [],
                    'datos': [],
                    'min_edad': None,
                    'max_edad': None,
                })

            span = max_edad - min_edad + 1
            base_size, extra = divmod(span, 3)
            tamanos = [
                base_size + (1 if index < extra else 0)
                for index in range(3)
            ]

            rangos = []
            inicio = min_edad
            for orden, tamano in enumerate(tamanos, start=1):
                # Mantiene tres barras incluso cuando hay menos de tres edades posibles.
                fin = inicio + tamano - 1 if tamano > 0 else inicio
                rangos.append((orden, inicio, fin, f'{inicio}-{fin}'))
                inicio = fin + 1

            rango_edad = Case(
                *[
                    When(edad__gte=inicio, edad__lte=fin, then=Value(label))
                    for _, inicio, fin, label in rangos
                ],
                default=Value(rangos[-1][3]),
                output_field=CharField(),
            )
            rango_orden = Case(
                *[
                    When(edad__gte=inicio, edad__lte=fin, then=Value(orden))
                    for orden, inicio, fin, _ in rangos
                ],
                default=Value(3),
                output_field=IntegerField(),
            )

            agrupados = (
                pacientes
                .annotate(rango_edad=rango_edad, rango_orden=rango_orden)
                .values('rango_edad', 'rango_orden')
                .annotate(total=Count('id'))
                .order_by('rango_orden')
            )

            labels = [label for _, _, _, label in rangos]
            conteos = {item['rango_edad']: item['total'] for item in agrupados}
            chart_data = [conteos.get(label, 0) for label in labels]
            data = [
                {'rango_edad': label, 'total': total}
                for label, total in zip(labels, chart_data)
            ]

            return Response({
                'segmentacion': 'edad',
                'labels': labels,
                'data': chart_data,
                'datos': data,
                'min_edad': min_edad,
                'max_edad': max_edad,
            })
        elif por == 'imc':
            # Segmentación por clasificación IMC (requerida por PDF)
            data = []
            for clasificacion in ['Bajo peso', 'Normal', 'Sobrepeso', 'Obesidad']:
                subset = qs.filter(clasificacion_imc=clasificacion)
                total_imc = subset.count()
                if total_imc == 0:
                    continue
                data.append({
                    'clasificacion_imc': clasificacion,
                    'total':             total_imc,
                    'criticos':          subset.filter(riesgo_enfermedad='Crítico').count(),
                    'alto':              subset.filter(riesgo_enfermedad='Alto').count(),
                    'avg_glucosa':       round(float(subset.aggregate(Avg('glucosa'))['glucosa__avg'] or 0), 2),
                    'avg_presion':       round(float(subset.aggregate(Avg('presion_sistolica'))['presion_sistolica__avg'] or 0), 1),
                })
        elif por == 'actividad':
            data = list(
                qs.values('actividad_fisica')
                  .annotate(total=Count('id'), avg_imc=Avg('imc'))
                  .order_by('-total')
            )
        else:
            return Response({'error': 'por debe ser: riesgo, sexo, diagnostico, edad, imc, actividad'}, status=400)
        return Response({'segmentacion': por, 'datos': data})


class RiesgoDistribucionView(APIView):
    permission_classes = [EsAnalista | EsMedico]

    def get(self, request) -> Response:
        from django.db.models import Count
        from apps.etl.models import RegistroClinico

        orden = ['Bajo', 'Medio', 'Alto', 'Crítico']
        datos = RegistroClinico.objects.values('riesgo_enfermedad').annotate(total=Count('id'))
        conteos = {item['riesgo_enfermedad']: item['total'] for item in datos}
        labels = orden
        data = [conteos.get(label, 0) for label in labels]
        return Response({'labels': labels, 'data': data})


class EdadImcPromedioView(APIView):
    permission_classes = [EsAnalista | EsMedico]

    def get(self, request) -> Response:
        from django.db.models import Avg, Case, When, Value, CharField
        from apps.etl.models import RegistroClinico

        qs = RegistroClinico.objects.filter(
            paciente__edad__isnull=False,
            imc__isnull=False,
            paciente__edad__gte=0,
        )
        rango_edad = Case(
            When(paciente__edad__lt=30, then=Value('Menores de 30')),
            When(paciente__edad__lte=50, then=Value('30-50')),
            default=Value('Mayores de 50'),
            output_field=CharField(),
        )
        agrupados = (
            qs
            .annotate(rango_edad=rango_edad)
            .values('rango_edad')
            .annotate(promedio_imc=Avg('imc'))
            .order_by('rango_edad')
        )
        labels = ['Menores de 30', '30-50', 'Mayores de 50']
        conteos = {item['rango_edad']: round(float(item['promedio_imc'] or 0), 2) for item in agrupados}
        data = [conteos.get(label, 0) for label in labels]
        return Response({'labels': labels, 'data': data})


class GlucosaPresionScatterView(APIView):
    permission_classes = [EsAnalista | EsMedico]

    def get(self, request) -> Response:
        from apps.etl.models import RegistroClinico

        qs = RegistroClinico.objects.filter(
            glucosa__isnull=False,
            presion_sistolica__isnull=False,
        ).order_by('glucosa')[:1200]
        puntos = [
            {'x': float(reg.glucosa), 'y': float(reg.presion_sistolica)}
            for reg in qs
        ]
        return Response({'puntos': puntos, 'total': len(puntos)})


class CorrelacionView(APIView):
    """GET /api/analytics/correlacion/ — Matriz de correlación de Pearson."""
    permission_classes = [EsAnalista | EsMedico]

    def get(self, request) -> Response:
        from .correlacion import CorrelacionCalculator
        return Response(CorrelacionCalculator().calcular())


class TendenciaClinicaView(APIView):
    """
    GET /api/analytics/tendencia-clinica/
    Devuelve la evolución mensual de indicadores clínicos clave.
    Permite al frontend renderizar gráficas de tendencias por tiempo.
    """
    permission_classes = [EsMedico]

    def get(self, request) -> Response:
        from django.db.models import Avg, Count, Max, Min
        from django.db.models.functions import TruncMonth
        from apps.etl.models import RegistroClinico

        campo = request.query_params.get('campo', 'glucosa')
        campos_validos = ['glucosa', 'imc', 'presion_sistolica', 'colesterol',
                          'saturacion_oxigeno', 'temperatura', 'frecuencia_cardiaca']
        if campo not in campos_validos:
            return Response({'error': f'Campo no válido. Usa: {campos_validos}'}, status=400)

        datos = (
            RegistroClinico.objects
            .exclude(**{f'{campo}__isnull': True})
            .exclude(fecha_consulta__isnull=True)
            .annotate(mes=TruncMonth('fecha_consulta'))
            .values('mes')
            .annotate(
                promedio=Avg(campo),
                maximo=Max(campo),
                minimo=Min(campo),
                total=Count('id'),
            )
            .order_by('mes')
        )

        resultado = [
            {
                'mes':      d['mes'].strftime('%Y-%m') if d['mes'] else None,
                'mes_label':d['mes'].strftime('%b %Y') if d['mes'] else None,
                'promedio': round(float(d['promedio'] or 0), 2),
                'maximo':   round(float(d['maximo']  or 0), 2),
                'minimo':   round(float(d['minimo']  or 0), 2),
                'total':    d['total'],
            }
            for d in datos
        ]

        return Response({'campo': campo, 'datos': resultado, 'total_meses': len(resultado)})
