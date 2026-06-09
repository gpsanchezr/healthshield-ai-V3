from django.contrib import admin
from .models import ModeloML, Prediccion

@admin.register(ModeloML)
class ModeloAdmin(admin.ModelAdmin):
    list_display = ['nombre','algoritmo','version','accuracy','f1_score','activo','entrenado_en']
    list_filter = ['algoritmo','activo']

@admin.register(Prediccion)
class PrediccionAdmin(admin.ModelAdmin):
    list_display = ['paciente','riesgo_predicho','probabilidad','fecha']
