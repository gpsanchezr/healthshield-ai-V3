from django.db import models
from django.conf import settings

class Paciente(models.Model):
    id_paciente_original = models.IntegerField(unique=True)
    cedula               = models.BigIntegerField(unique=True, null=True, blank=True, verbose_name='Cédula')
    nombres  = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    edad     = models.PositiveSmallIntegerField()
    sexo     = models.CharField(max_length=1, choices=[('M','Masculino'),('F','Femenino')])
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['apellidos', 'nombres']
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'

    def __str__(self):
        return f"{self.nombres} {self.apellidos} (ID {self.id_paciente_original})"

class EjecucionETL(models.Model):
    ESTADO = [('en_proceso','En proceso'),('completado','Completado'),('fallido','Fallido')]
    TIPO   = [('manual','Manual'),('simulacion','Simulación'),('automatico','Automático')]

    usuario              = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    archivo_fuente       = models.CharField(max_length=255, blank=True)
    fecha_inicio         = models.DateTimeField(auto_now_add=True)
    fecha_fin            = models.DateTimeField(null=True, blank=True)
    duracion_segundos    = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    registros_extraidos  = models.IntegerField(default=0)
    registros_procesados = models.IntegerField(default=0)
    registros_rechazados = models.IntegerField(default=0)
    duplicados_eliminados= models.IntegerField(default=0)
    nulos_imputados      = models.IntegerField(default=0)
    estado               = models.CharField(max_length=20, choices=ESTADO, default='en_proceso')
    tipo                 = models.CharField(max_length=20, choices=TIPO, default='manual')
    reporte_calidad      = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = 'Ejecución ETL'

    def __str__(self):
        return f"ETL #{self.id} — {self.estado} ({self.fecha_inicio:%Y-%m-%d %H:%M})"

class RegistroClinico(models.Model):
    RIESGO = [('Bajo','Bajo'),('Medio','Medio'),('Alto','Alto'),('Crítico','Crítico')]

    paciente             = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='registros')
    peso                 = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    altura               = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    imc                  = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    clasificacion_imc    = models.CharField(max_length=20, blank=True)
    presion_sistolica    = models.SmallIntegerField(null=True)
    presion_diastolica   = models.SmallIntegerField(null=True)
    frecuencia_cardiaca  = models.SmallIntegerField(null=True)
    glucosa              = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    colesterol           = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    saturacion_oxigeno   = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    temperatura          = models.DecimalField(max_digits=4, decimal_places=1, null=True)
    antecedentes_familiares = models.BooleanField(default=False)
    fumador              = models.BooleanField(default=False)
    consumo_alcohol      = models.BooleanField(default=False)
    actividad_fisica     = models.CharField(max_length=20, blank=True)
    diagnostico_preliminar = models.CharField(max_length=100, blank=True)
    riesgo_enfermedad    = models.CharField(max_length=10, choices=RIESGO, default='Bajo')
    fecha_consulta       = models.DateField(null=True)
    fuente_etl           = models.ForeignKey(EjecucionETL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_consulta']
        verbose_name = 'Registro Clínico'

    def __str__(self):
        return f"{self.paciente} — Riesgo: {self.riesgo_enfermedad}"

class LogETL(models.Model):
    NIVEL = [('INFO','INFO'),('WARNING','WARNING'),('ERROR','ERROR')]
    ejecucion      = models.ForeignKey(EjecucionETL, on_delete=models.CASCADE, related_name='logs')
    nivel          = models.CharField(max_length=10, choices=NIVEL, default='INFO')
    mensaje        = models.TextField()
    campo_afectado = models.CharField(max_length=50, blank=True)
    valor_original = models.TextField(blank=True)
    valor_corregido= models.TextField(blank=True)
    timestamp      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

class Alerta(models.Model):
    URGENCIA = [('baja','Baja'),('media','Media'),('alta','Alta'),('critica','Crítica')]
    paciente      = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='alertas')
    tipo_alerta   = models.CharField(max_length=50)
    descripcion   = models.TextField()
    nivel_urgencia= models.CharField(max_length=10, choices=URGENCIA, default='alta')
    visto_por     = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    fecha_alerta  = models.DateTimeField(auto_now_add=True)
    fecha_vista   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_alerta']

    @property
    def vista(self): return self.fecha_vista is not None
