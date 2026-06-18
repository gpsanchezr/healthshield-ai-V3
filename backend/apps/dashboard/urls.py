from django.urls import path
from .views import DashboardKPIsView, DashboardTendenciaView

urlpatterns = [
    path('kpis/',       DashboardKPIsView.as_view(),    name='dashboard-kpis'),
    path('tendencia/',  DashboardTendenciaView.as_view(), name='dashboard-tendencia'),
]
