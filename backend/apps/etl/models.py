from django.db import models
from django.conf import settings
from django.utils import timezone


class Paciente(models.Model):
    id_paciente_original = models.IntegerField(unique=True)
    cedula    = models.BigIntegerField(unique=True, null=True, blank=True, verbose_name='Cédula')
    nombres   = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    edad      = models.IntegerField()
    sexo      = models.CharField(max_length=1, choices=[('M','Masculino'),('F','Femenino')])
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return f"{self.nombres} {self.apellidos} (ID {self.id_paciente_original})"


# ─────────────────────────────────────────────────────────────────────────────
# NUEVO (V4.2): Caché del archivo real subido para ETL
# ─────────────────────────────────────────────────────────────────────────────
class DatasetCache(models.Model):
    """
    Persiste el archivo CSV/Excel real subido por el analista/administrador
    para que pueda "Reutilizarse" sin tener que volver a seleccionarlo desde
    el explorador de archivos cada vez.

    CORRECCIÓN CRÍTICA V4.2:
    Antes, el archivo subido se guardaba en un tempfile y se BORRABA
    inmediatamente después de procesarlo (ver versiones anteriores de
    RunETLView). El botón "Reutilizar" que ya existía en el frontend, al no
    tener ningún archivo real al que apuntar, terminaba generando datos
    SIMULADOS (DataSimulator) en vez de reprocesar el dataset real. Esta
    tabla resuelve ese problema persistiendo el archivo en
    MEDIA_ROOT/etl_cache/.

    También sirve como evidencia auditable del proceso ETL (uno de los
    entregables del reto: "Evidencias Proceso ETL").
    """
    archivo               = models.FileField(upload_to='etl_cache/%Y/%m/')
    nombre_original       = models.CharField(max_length=255)
    tamaño_bytes          = models.PositiveIntegerField(default=0)
    registros_detectados  = models.PositiveIntegerField(default=0)
    usuario               = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='datasets_subidos',
    )
    fecha_subida          = models.DateTimeField(auto_now_add=True)
    # Sólo un registro puede estar "activo" (el que se reutiliza) a la vez.
    activo                = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-fecha_subida']
        verbose_name = 'Dataset en caché (ETL)'
        verbose_name_plural = 'Datasets en caché (ETL)'

    def __str__(self):
        return f"{self.nombre_original} — {self.fecha_subida:%d/%m/%Y %H:%M}"

    def marcar_como_activo(self):
        """Desactiva cualquier otro caché y marca este como el vigente."""
        DatasetCache.objects.exclude(pk=self.pk).update(activo=False)
        self.activo = True
        self.save(update_fields=['activo'])

    @property
    def tamaño_legible(self) -> str:
        kb = self.tamaño_bytes / 1024
        return f"{kb:.0f} KB" if kb < 1024 else f"{kb / 1024:.1f} MB"


class EjecucionETL(models.Model):
    usuario              = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    tipo                 = models.CharField(max_length=20, default='manual')
    estado               = models.CharField(max_length=20, default='pendiente')
    registros_procesados = models.IntegerField(default=0)
    registros_rechazados = models.IntegerField(default=0)
    duracion_segundos    = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    reporte_calidad      = models.JSONField(null=True, blank=True)
    fecha_inicio         = models.DateTimeField(auto_now_add=True)
    fecha_fin            = models.DateTimeField(null=True, blank=True)
    # ← Cache: path del archivo fuente para "usar anterior"
    archivo_fuente       = models.CharField(max_length=500, blank=True, default='')
    # NUEVO V4.2: referencia al archivo real cacheado que originó esta ejecución
    # (None para ejecuciones de tipo 'simulacion' que no parten de un archivo)
    dataset_cache        = models.ForeignKey(
        DatasetCache, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ejecuciones',
    )

    class Meta:
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f"ETL #{self.id} — {self.estado} ({self.fecha_inicio:%Y-%m-%d %H:%M})"


class RegistroClinico(models.Model):
    RIESGO = [('Bajo','Bajo'),('Medio','Medio'),('Alto','Alto'),('Crítico','Crítico')]

    paciente             = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='registros')
    peso                 = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    altura               = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    imc                  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    clasificacion_imc    = models.CharField(max_length=20, blank=True)
    presion_sistolica    = models.IntegerField(null=True, blank=True)
    presion_diastolica   = models.IntegerField(null=True, blank=True)
    frecuencia_cardiaca  = models.IntegerField(null=True, blank=True)
    glucosa              = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    colesterol           = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    saturacion_oxigeno   = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    temperatura          = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    fumador              = models.BooleanField(default=False)
    consumo_alcohol      = models.BooleanField(default=False)
    antecedentes_familiares = models.BooleanField(default=False)
    actividad_fisica     = models.CharField(max_length=20, blank=True)
    diagnostico_preliminar = models.TextField(blank=True)
    riesgo_enfermedad    = models.CharField(max_length=10, choices=RIESGO, default='Bajo')
    fecha_consulta       = models.DateField(null=True)

    class Meta:
        ordering = ['-fecha_consulta']

    def __str__(self):
        return f"{self.paciente} — Riesgo: {self.riesgo_enfermedad}"


class LogETL(models.Model):
    ejecucion  = models.ForeignKey(EjecucionETL, on_delete=models.CASCADE, related_name='logs')
    nivel      = models.CharField(max_length=10, default='INFO')
    mensaje    = models.TextField()
    timestamp  = models.DateTimeField(auto_now_add=True)
    step       = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['timestamp']


class Alerta(models.Model):
    NIVELES = [('critica','Crítica'),('alta','Alta'),('media','Media'),('baja','Baja')]
    paciente      = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='alertas')
    nivel_urgencia = models.CharField(max_length=10, choices=NIVELES, default='alta')
    tipo_alerta   = models.CharField(max_length=100, blank=True)
    fecha_alerta  = models.DateTimeField(auto_now_add=True)
    fecha_vista   = models.DateTimeField(null=True, blank=True)
    visto_por     = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='alertas_vistas')

    class Meta:
        ordering = ['-fecha_alerta']

    @property
    def vista(self): return self.fecha_vista is not None


# ─────────────────────────────────────────────────────────────────────────────
# Consulta Médica — registro clínico de cada visita del doctor al paciente
# ─────────────────────────────────────────────────────────────────────────────
class ConsultaMedica(models.Model):
    ESTADO_CHOICES = [
        ('mejorando',   'Mejorando 📈'),
        ('estable',     'Estable ➡️'),
        ('empeorando',  'Empeorando 📉'),
        ('critico',     'Crítico 🚨'),
        ('alta_medica', 'Alta Médica ✅'),
    ]

    paciente             = models.ForeignKey(Paciente, on_delete=models.CASCADE,
                                              related_name='consultas')
    medico               = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                              on_delete=models.SET_NULL, related_name='consultas_realizadas')
    fecha_consulta       = models.DateTimeField(default=timezone.now)

    # ── Motivo y síntomas ─────────────────────────────────────────────────────
    motivo_consulta      = models.TextField(blank=True, verbose_name='Motivo de consulta')
    sintomas_actuales    = models.TextField(blank=True, verbose_name='Síntomas actuales')
    diagnostico          = models.TextField(blank=True, verbose_name='Diagnóstico')
    tratamiento          = models.TextField(blank=True, verbose_name='Tratamiento indicado')
    observaciones        = models.TextField(blank=True, verbose_name='Observaciones')

    # ── Signos vitales registrados en la consulta (opcionales) ────────────────
    peso                 = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    temperatura          = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    presion_sistolica    = models.IntegerField(null=True, blank=True)
    presion_diastolica   = models.IntegerField(null=True, blank=True)
    frecuencia_cardiaca  = models.IntegerField(null=True, blank=True)
    saturacion_oxigeno   = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    glucosa              = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

    # ── Estado general del paciente ────────────────────────────────────────────
    estado_general       = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='estable')

    # ── Condiciones especiales ────────────────────────────────────────────────
    en_embarazo          = models.BooleanField(default=False, verbose_name='Paciente embarazada')
    semana_embarazo      = models.IntegerField(null=True, blank=True, verbose_name='Semana de gestación')
    condicion_especial   = models.CharField(max_length=300, blank=True,
                                             verbose_name='Condición / tratamiento activo',
                                             help_text='Ej: Tratamiento poliquístico 3 meses, Quimioterapia ciclo 2...')

    proxima_cita         = models.DateField(null=True, blank=True, verbose_name='Próxima cita')

    class Meta:
        ordering = ['-fecha_consulta']
        verbose_name = 'Consulta Médica'
        verbose_name_plural = 'Consultas Médicas'

    def __str__(self):
        fecha = self.fecha_consulta.strftime('%d/%m/%Y') if self.fecha_consulta else '—'
        return f"Consulta {fecha} — {self.paciente} [{self.estado_general}]"
