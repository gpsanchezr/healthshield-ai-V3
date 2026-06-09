from django.db import models

class SnapshotAnalitico(models.Model):
    """Guarda un snapshot de KPIs para tendencias históricas."""
    fecha              = models.DateField(auto_now_add=True)
    total_registros    = models.IntegerField(default=0)
    pacientes_criticos = models.IntegerField(default=0)
    pacientes_alto     = models.IntegerField(default=0)
    pacientes_hipertensos = models.IntegerField(default=0)
    pacientes_diabeticos  = models.IntegerField(default=0)
    promedio_imc       = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    promedio_glucosa   = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    class Meta:
        ordering = ['-fecha']
