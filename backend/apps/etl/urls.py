from django.urls import path
from .views import (RunETLView, SimulateDataView, HistorialETLView, CalidadReporteView,
                    AlertaListView, AlertaMarcarVistaView,
                    PacienteListView, PacienteDetailView, RegistroClinicoListView,
                    RunETLAsyncView, TaskStatusView, EstadisticasCalidadView)

urlpatterns = [
    path('run/',                RunETLView.as_view(),            name='etl-run'),
    path('simular/',            SimulateDataView.as_view(),      name='etl-simular'),
    path('historial/',          HistorialETLView.as_view(),      name='etl-historial'),
    path('calidad/<int:pk>/',   CalidadReporteView.as_view(),    name='etl-calidad'),
    path('alertas/',            AlertaListView.as_view(),        name='alertas-list'),
    path('alertas/<int:pk>/vista/', AlertaMarcarVistaView.as_view(), name='alerta-vista'),
    path('run-async/',              RunETLAsyncView.as_view(),       name='etl-run-async'),
    path('task/<str:task_id>/',     TaskStatusView.as_view(),        name='task-status'),
    path('calidad-historica/',       EstadisticasCalidadView.as_view(), name='calidad-historica'),
]

pacientes_urlpatterns = [
    path('',          PacienteListView.as_view(),     name='pacientes-list'),
    path('<int:pk>/', PacienteDetailView.as_view(),   name='pacientes-detail'),
    path('registros/',RegistroClinicoListView.as_view(), name='registros-list'),
]
