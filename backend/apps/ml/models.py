from django.db import models

class ModeloML(models.Model):
    ALGOS = [('random_forest','Random Forest'),('logistic_regression','Regresión Logística'),('decision_tree','Árbol de Decisión')]
    nombre              = models.CharField(max_length=100)
    algoritmo           = models.CharField(max_length=30, choices=ALGOS)
    version             = models.CharField(max_length=20)
    accuracy            = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    precision_score     = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    recall              = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    f1_score            = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    archivo_modelo      = models.CharField(max_length=255)
    feature_names       = models.JSONField(default=list)
    feature_importance  = models.JSONField(default=dict)
    entrenado_en        = models.DateTimeField(auto_now_add=True)
    registros_entrenamiento = models.IntegerField(default=0)
    activo              = models.BooleanField(default=False)
    class Meta:
        ordering = ['-entrenado_en']
    def __str__(self): return f"{self.nombre} v{self.version} (acc={self.accuracy})"

class Prediccion(models.Model):
    paciente        = models.ForeignKey('etl.Paciente', on_delete=models.CASCADE, related_name='predicciones')
    modelo          = models.ForeignKey(ModeloML, on_delete=models.SET_NULL, null=True)
    riesgo_predicho = models.CharField(max_length=10)
    probabilidad    = models.DecimalField(max_digits=5, decimal_places=4)
    factores_clave  = models.JSONField(default=list)
    fecha           = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-fecha']
