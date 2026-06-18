from django.urls import path
from .views import (
    RunETLView, SimulateDataView, HistorialETLView, CalidadReporteView,
    AlertaListView, AlertaMarcarVistaView,
    PacienteListView, PacienteDetailView, RegistroClinicoListView,
    RunETLAsyncView, TaskStatusView, EstadisticasCalidadView,
    ConsultaMedicaListCreateView, ConsultaMedicaDetailView,
    ReutilizarETLView, DatasetCacheHistorialView,
    DescargarDatasetLimpioView,
)

urlpatterns = [
    path('run/',                    RunETLView.as_view(),            name='etl-run'),
    path('simular/',                SimulateDataView.as_view(),      name='etl-simular'),
    path('historial/',              HistorialETLView.as_view(),      name='etl-historial'),
    path('calidad/<int:pk>/',       CalidadReporteView.as_view(),    name='etl-calidad'),
    path('alertas/',                AlertaListView.as_view(),        name='alertas-list'),
    path('alertas/<int:pk>/vista/', AlertaMarcarVistaView.as_view(), name='alerta-vista'),
    path('run-async/',              RunETLAsyncView.as_view(),       name='etl-run-async'),
    path('task/<str:task_id>/',     TaskStatusView.as_view(),        name='task-status'),
    path('calidad-historica/',      EstadisticasCalidadView.as_view(), name='calidad-historica'),

    # ── FIX CRÍTICO V4.2 ──────────────────────────────────────────────────────
    # El frontend (etl/index.html) llama a `${API}/etl/reutilizar/`, es decir
    # /api/etl/reutilizar/, pero la vista sólo estaba registrada en
    # pacientes_urlpatterns → /api/pacientes/reutilizar/. Eso hacía que el
    # botón "Reutilizar" devolviera 404 siempre. Se registra aquí también
    # (ruta correcta) y se deja la de pacientes por compatibilidad.
    path('reutilizar/',             ReutilizarETLView.as_view(),     name='etl-reutilizar-fix'),
    # NUEVO V4.2: historial/auditoría de archivos cacheados
    path('datasets-cache/',         DatasetCacheHistorialView.as_view(), name='etl-datasets-cache'),
    # MEJORA: GET /api/etl/descargar/<pk>/?formato=xlsx|csv
    path('descargar/<int:pk>/',     DescargarDatasetLimpioView.as_view(), name='etl-descargar'),
]

pacientes_urlpatterns = [
    path('',                          PacienteListView.as_view(),              name='pacientes-list'),
    path('<int:pk>/',                 PacienteDetailView.as_view(),            name='pacientes-detail'),
    path('registros/',                RegistroClinicoListView.as_view(),       name='registros-list'),
    path('consultas/',                ConsultaMedicaListCreateView.as_view(),  name='consultas-list'),
    path('consultas/<int:pk>/',       ConsultaMedicaDetailView.as_view(),      name='consultas-detail'),
    # Se conserva por compatibilidad con cualquier código que aún apunte aquí;
    # la ruta "oficial" usada por el frontend es /api/etl/reutilizar/ (arriba).
    path('reutilizar/',               ReutilizarETLView.as_view(),             name='etl-reutilizar'),
]
