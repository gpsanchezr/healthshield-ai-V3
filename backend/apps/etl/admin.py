from django.contrib import admin
from .models import Paciente, RegistroClinico, EjecucionETL, LogETL, Alerta

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['id_paciente_original','nombres','apellidos','edad','sexo']
    search_fields = ['nombres','apellidos']

@admin.register(RegistroClinico)
class RegistroAdmin(admin.ModelAdmin):
    list_display = ['paciente','riesgo_enfermedad','glucosa','presion_sistolica','fecha_consulta']
    list_filter = ['riesgo_enfermedad','fumador']

@admin.register(EjecucionETL)
class EjecucionAdmin(admin.ModelAdmin):
    list_display = ['id','tipo','estado','registros_procesados','duracion_segundos','fecha_inicio']
    list_filter = ['estado','tipo']

@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ['paciente','tipo_alerta','nivel_urgencia','fecha_alerta','vista']
    list_filter = ['nivel_urgencia']
