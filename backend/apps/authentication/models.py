from django.contrib.auth.models import AbstractUser
from django.db import models

ROL_CHOICES = [
    ('administrador', 'Administrador'),
    ('medico', 'Médico'),
    ('analista', 'Analista'),
]

class UsuarioClinico(AbstractUser):
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='medico')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Usuario Clínico'
        verbose_name_plural = 'Usuarios Clínicos'

    def __str__(self):
        return f"{self.get_full_name()} ({self.rol})"

    @property
    def es_administrador(self): return self.rol == 'administrador'
    @property
    def es_medico(self): return self.rol in ('medico', 'administrador')
    @property
    def es_analista(self): return self.rol in ('analista', 'administrador')
