from django.urls import path
from .views import (ModeloMetricasView, ModeloHistorialView, PredecirPacienteView,
                    EntrenarModeloView, PrediccionListView, AnalisisIAView,
                    ProveedoresIAView, ConfusionMatrixView)
# BUG FIX: chatbot estaba definido pero NO registrado en ninguna URL
from .views_chat import ClinicalChatbotView

urlpatterns = [
    path('',                          PrediccionListView.as_view(),    name='predicciones-list'),
    path('modelo/metricas/',          ModeloMetricasView.as_view(),    name='modelo-metricas'),
    path('modelo/historial/',         ModeloHistorialView.as_view(),   name='modelo-historial'),
    path('modelo/entrenar/',          EntrenarModeloView.as_view(),    name='modelo-entrenar'),
    path('paciente/<int:pk>/',        PredecirPacienteView.as_view(),  name='predecir-paciente'),
    path('analisis-ia/<int:pk>/',     AnalisisIAView.as_view(),        name='analisis-ia'),
    path('proveedores-ia/',           ProveedoresIAView.as_view(),     name='proveedores-ia'),
    path('modelo/confusion-matrix/',  ConfusionMatrixView.as_view(),   name='confusion-matrix'),
    path('chatbot/',                  ClinicalChatbotView.as_view(),   name='chatbot-clinico'),  # FIX
]
