from django.urls import path
from .views import ExportarPDFView, ExportarExcelView, ExportarCSVView, ExportarPacientePDFView

urlpatterns = [
    path('pdf/',   ExportarPDFView.as_view(),   name='exportar-pdf'),
    path('excel/', ExportarExcelView.as_view(), name='exportar-excel'),
    path('csv/',   ExportarCSVView.as_view(),   name='exportar-csv'),
    path('paciente/<int:pk>/', ExportarPacientePDFView.as_view(), name='paciente-pdf'),
]