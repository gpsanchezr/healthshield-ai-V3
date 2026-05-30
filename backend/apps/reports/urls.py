from django.urls import path
from .views import ExportarPDFView, ExportarExcelView, ExportarCSVView

urlpatterns = [
    path('pdf/',   ExportarPDFView.as_view(),   name='exportar-pdf'),
    path('excel/', ExportarExcelView.as_view(), name='exportar-excel'),
    path('csv/',   ExportarCSVView.as_view(),   name='exportar-csv'),
]
