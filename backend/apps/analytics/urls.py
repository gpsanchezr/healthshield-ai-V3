from django.urls import path
from .views import KPIsView, EstadisticaView, DetectarCriticosView, SegmentacionView, CorrelacionView, TendenciaClinicaView

urlpatterns = [
    path('kpis/',          KPIsView.as_view(),           name='kpis'),
    path('estadistica/',   EstadisticaView.as_view(),    name='estadistica'),
    path('detectar/',      DetectarCriticosView.as_view(), name='detectar-criticos'),
    path('segmentacion/',  SegmentacionView.as_view(),   name='segmentacion'),
    path('correlacion/',   CorrelacionView.as_view(),    name='correlacion'),
    path('tendencia-clinica/', TendenciaClinicaView.as_view(), name='tendencia-clinica'),
]
