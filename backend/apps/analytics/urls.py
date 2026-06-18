from django.urls import path
from .views import (
    KPIsView, EstadisticaView, DetectarCriticosView, SegmentacionView,
    RiesgoDistribucionView, EdadImcPromedioView, GlucosaPresionScatterView,
    CorrelacionView, TendenciaClinicaView
)

urlpatterns = [
    path('kpis/',          KPIsView.as_view(),           name='kpis'),
    path('estadistica/',   EstadisticaView.as_view(),    name='estadistica'),
    path('detectar/',      DetectarCriticosView.as_view(), name='detectar-criticos'),
    path('segmentacion/',  SegmentacionView.as_view(),   name='segmentacion'),
    path('riesgo-distribucion/', RiesgoDistribucionView.as_view(), name='riesgo-distribucion'),
    path('edad-imc/',      EdadImcPromedioView.as_view(), name='edad-imc'),
    path('glucosa-presion/', GlucosaPresionScatterView.as_view(), name='glucosa-presion'),
    path('correlacion/',   CorrelacionView.as_view(),    name='correlacion'),
    path('tendencia-clinica/', TendenciaClinicaView.as_view(), name='tendencia-clinica'),
]
