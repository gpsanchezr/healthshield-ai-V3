from django.contrib import admin
from .models import SnapshotAnalitico

@admin.register(SnapshotAnalitico)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ['fecha','total_registros','pacientes_criticos','pacientes_hipertensos','promedio_glucosa']
    ordering     = ['-fecha']
