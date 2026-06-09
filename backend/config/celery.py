"""
Configuración de Celery para HealthShield AI.
Permite ejecutar el ETL y el entrenamiento ML en background,
retornando respuesta inmediata al usuario con un task_id.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('healthshield')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
