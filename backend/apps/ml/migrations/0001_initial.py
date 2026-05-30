from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('etl', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='ModeloML',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('nombre', models.CharField(max_length=100)),
                ('algoritmo', models.CharField(choices=[('random_forest','Random Forest'),('logistic_regression','Regresión Logística'),('decision_tree','Árbol de Decisión')], max_length=30)),
                ('version', models.CharField(max_length=20)),
                ('accuracy', models.DecimalField(decimal_places=4, max_digits=6, null=True)),
                ('precision_score', models.DecimalField(decimal_places=4, max_digits=6, null=True)),
                ('recall', models.DecimalField(decimal_places=4, max_digits=6, null=True)),
                ('f1_score', models.DecimalField(decimal_places=4, max_digits=6, null=True)),
                ('archivo_modelo', models.CharField(max_length=255)),
                ('feature_names', models.JSONField(default=list)),
                ('feature_importance', models.JSONField(default=dict)),
                ('entrenado_en', models.DateTimeField(auto_now_add=True)),
                ('registros_entrenamiento', models.IntegerField(default=0)),
                ('activo', models.BooleanField(default=False)),
            ],
            options={'ordering': ['-entrenado_en']},
        ),
        migrations.CreateModel(
            name='Prediccion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('riesgo_predicho', models.CharField(max_length=10)),
                ('probabilidad', models.DecimalField(decimal_places=4, max_digits=5)),
                ('factores_clave', models.JSONField(default=list)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('modelo', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='ml.modeloml')),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='predicciones', to='etl.paciente')),
            ],
            options={'ordering': ['-fecha']},
        ),
    ]
