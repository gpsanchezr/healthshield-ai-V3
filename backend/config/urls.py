from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.etl.urls import pacientes_urlpatterns
from apps.dashboard.template_views import (
    login_page, dashboard_page, etl_page, pacientes_page, ml_page, reportes_page,
    alertas_page, ml_monitor_page, paciente_detail_page, analytics_page
)
from django.views.generic import TemplateView
from apps.dashboard.views import kpi_drilldown_view

urlpatterns = [
    # Pages
    path('',          RedirectView.as_view(url='/dashboard/')),
    path('login/',    login_page,     name='login'),
    path('dashboard/',dashboard_page, name='dashboard'),
    path('etl/',      etl_page,       name='etl'),
    path('pacientes/',pacientes_page, name='pacientes'),
    path('pacientes/drilldown/', kpi_drilldown_view, name='kpi_drilldown'),
    path('ml/',       ml_page,        name='ml'),
    path('reportes/', reportes_page,  name='reportes'),
    path('etl/alertas/', alertas_page,     name='alertas'),
    path('ml/monitor/',  ml_monitor_page,  name='ml-monitor'),
    path('pacientes/<int:pk>/', paciente_detail_page, name='paciente-detail'),
    path('auditoria/', TemplateView.as_view(template_name='auth/auditoria.html'), name='auditoria'),
    path('analytics/',  analytics_page, name='analytics'),

    # Admin
    path('admin/', admin.site.urls),

    # REST API
    path('api/auth/',           include('apps.authentication.urls')),
    path('api/pacientes/',      include((pacientes_urlpatterns, 'pacientes'))),
    path('api/etl/',            include('apps.etl.urls')),
    path('api/analytics/',      include('apps.analytics.urls')),
    path('api/predicciones/',   include('apps.ml.urls')),
    path('api/dashboard/',      include('apps.dashboard.urls')),
    path('api/reportes/',       include('apps.reports.urls')),

    # Swagger
    path('api/schema/',         SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
