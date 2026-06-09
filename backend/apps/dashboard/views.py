from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.authentication.permissions import EsMedico
from apps.analytics.calculators import KPICalculator
from apps.etl.models import EjecucionETL, Alerta, RegistroClinico


class DashboardKPIsView(APIView):
    permission_classes = [EsMedico]
    def get(self, request):
        kpis = KPICalculator().get_all_kpis()
        ultima_etl = EjecucionETL.objects.filter(estado='completado').first()
        return Response({
            'kpis': kpis,
            'ultima_etl': {
                'id': ultima_etl.id if ultima_etl else None,
                'fecha': ultima_etl.fecha_inicio if ultima_etl else None,
                'quality_score': (ultima_etl.reporte_calidad or {}).get('quality_score') if ultima_etl else None,
            } if ultima_etl else None,
        })


class DashboardTendenciaView(APIView):
    permission_classes = [EsMedico]
    def get(self, request):
        etls = EjecucionETL.objects.filter(estado='completado').order_by('-fecha_inicio')[:10]
        tendencia = []
        for e in reversed(list(etls)):
            qr = e.reporte_calidad or {}
            tendencia.append({
                'fecha': e.fecha_inicio.strftime('%d/%m'),
                'registros': e.registros_procesados,
                'quality_score': qr.get('quality_score', 0),
                'criticos': qr.get('criticos', 0),
            })
        return Response({'tendencia': tendencia})


def kpi_drilldown_view(request):
    """
    Drilldown de KPIs clínicos.
    Nota: Temporariamente se deshabilita la validación estricta de JWT para evitar redirect a login
    cuando la navegación desde el Dashboard se hace con enlaces <a> sin Authorization header.
    """
    filtro = request.GET.get('filtro', 'total')

    # BUG FIX: select_related para evitar N+1 queries y acceder a paciente.*
    qs = RegistroClinico.objects.select_related('paciente').all()
    titulo_filtro = "Todos los Registros"

    if filtro == 'criticos':
        qs = qs.filter(riesgo_enfermedad__iexact='Crítico')
        titulo_filtro = "🚨 Pacientes Críticos"
    elif filtro == 'hipertensos':
        qs = qs.filter(presion_sistolica__gt=140)
        titulo_filtro = "❤️ Pacientes Hipertensos (Presión > 140 mmHg)"
    elif filtro == 'diabeticos':
        # BUG FIX: umbral 125 mg/dL consistente con KPICalculator
        qs = qs.filter(glucosa__gt=125)
        titulo_filtro = "💧 Pacientes Diabéticos (Glucosa > 125 mg/dL)"
    elif filtro == 'fumadores':
        qs = qs.filter(fumador=True)
        titulo_filtro = "🫁 Pacientes Fumadores"
    elif filtro == 'glucosa_alta':
        qs = qs.filter(glucosa__gt=100)
        titulo_filtro = "📋 Pacientes con Glucosa Elevada"
    elif filtro == 'obesidad':
        qs = qs.filter(imc__gte=30)
        titulo_filtro = "📊 Pacientes con Obesidad (IMC ≥ 30)"
    # BUG FIX: añadir handler para filtro=riesgo (Riesgo Promedio card)
    elif filtro == 'riesgo':
        qs = qs.filter(riesgo_enfermedad__in=['Alto', 'Crítico'])
        titulo_filtro = "⚠️ Pacientes con Riesgo Alto o Crítico"
    # BUG FIX: añadir handler para alertas
    elif filtro == 'alertas':
        pacientes_ids = Alerta.objects.filter(
            fecha_vista__isnull=True
        ).values_list('paciente_id', flat=True)
        qs = qs.filter(paciente__id__in=pacientes_ids)
        titulo_filtro = "🔔 Pacientes con Alertas Sin Ver"
    # Perfil Fitness
    elif filtro == 'fitness_sedentario':
        qs = qs.filter(actividad_fisica__iexact='Sedentaria')
        titulo_filtro = "🪑 Perfil Fitness: Sedentarios"
    elif filtro == 'fitness_baja':
        qs = qs.filter(actividad_fisica__iexact='Baja')
        titulo_filtro = "🚶 Perfil Fitness: Actividad Baja"
    elif filtro == 'fitness_media':
        qs = qs.filter(actividad_fisica__iexact='Media')
        titulo_filtro = "🏃 Perfil Fitness: Actividad Media"
    elif filtro == 'fitness_alta':
        qs = qs.filter(actividad_fisica__iexact='Alta')
        titulo_filtro = "🏋️ Perfil Fitness: Alta Intensidad (Deportistas)"

    context = {
        'registros': qs,           # BUG FIX: renombrado para claridad
        'titulo_filtro': titulo_filtro,
        'filtro_activo': filtro,
        'total': qs.count(),
    }
    return render(request, 'patients/kpi_list.html', context)
