from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('authentication', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='EjecucionETL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('archivo_fuente', models.CharField(blank=True, max_length=255)),
                ('fecha_inicio', models.DateTimeField(auto_now_add=True)),
                ('fecha_fin', models.DateTimeField(blank=True, null=True)),
                ('duracion_segundos', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ('registros_extraidos', models.IntegerField(default=0)),
                ('registros_procesados', models.IntegerField(default=0)),
                ('registros_rechazados', models.IntegerField(default=0)),
                ('duplicados_eliminados', models.IntegerField(default=0)),
                ('nulos_imputados', models.IntegerField(default=0)),
                ('estado', models.CharField(choices=[('en_proceso','En proceso'),('completado','Completado'),('fallido','Fallido')], default='en_proceso', max_length=20)),
                ('tipo', models.CharField(choices=[('manual','Manual'),('simulacion','Simulación'),('automatico','Automático')], default='manual', max_length=20)),
                ('reporte_calidad', models.JSONField(blank=True, null=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='authentication.usuarioclinico')),
            ],
            options={'ordering': ['-fecha_inicio'], 'verbose_name': 'Ejecución ETL'},
        ),
        migrations.CreateModel(
            name='Paciente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('id_paciente_original', models.IntegerField(unique=True)),
                ('nombres', models.CharField(max_length=100)),
                ('apellidos', models.CharField(max_length=100)),
                ('edad', models.PositiveSmallIntegerField()),
                ('sexo', models.CharField(choices=[('M','Masculino'),('F','Femenino')], max_length=1)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['apellidos', 'nombres'], 'verbose_name': 'Paciente'},
        ),
        migrations.CreateModel(
            name='RegistroClinico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('peso', models.DecimalField(decimal_places=2, max_digits=5, null=True)),
                ('altura', models.DecimalField(decimal_places=2, max_digits=4, null=True)),
                ('imc', models.DecimalField(decimal_places=2, max_digits=5, null=True)),
                ('clasificacion_imc', models.CharField(blank=True, max_length=20)),
                ('presion_sistolica', models.SmallIntegerField(null=True)),
                ('presion_diastolica', models.SmallIntegerField(null=True)),
                ('frecuencia_cardiaca', models.SmallIntegerField(null=True)),
                ('glucosa', models.DecimalField(decimal_places=2, max_digits=6, null=True)),
                ('colesterol', models.DecimalField(decimal_places=2, max_digits=6, null=True)),
                ('saturacion_oxigeno', models.DecimalField(decimal_places=2, max_digits=5, null=True)),
                ('temperatura', models.DecimalField(decimal_places=1, max_digits=4, null=True)),
                ('antecedentes_familiares', models.BooleanField(default=False)),
                ('fumador', models.BooleanField(default=False)),
                ('consumo_alcohol', models.BooleanField(default=False)),
                ('actividad_fisica', models.CharField(blank=True, max_length=20)),
                ('diagnostico_preliminar', models.CharField(blank=True, max_length=100)),
                ('riesgo_enfermedad', models.CharField(choices=[('Bajo','Bajo'),('Medio','Medio'),('Alto','Alto'),('Crítico','Crítico')], default='Bajo', max_length=10)),
                ('fecha_consulta', models.DateField(null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('fuente_etl', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='etl.ejecucionetl')),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registros', to='etl.paciente')),
            ],
            options={'ordering': ['-fecha_consulta'], 'verbose_name': 'Registro Clínico'},
        ),
        migrations.CreateModel(
            name='LogETL',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('nivel', models.CharField(choices=[('INFO','INFO'),('WARNING','WARNING'),('ERROR','ERROR')], default='INFO', max_length=10)),
                ('mensaje', models.TextField()),
                ('campo_afectado', models.CharField(blank=True, max_length=50)),
                ('valor_original', models.TextField(blank=True)),
                ('valor_corregido', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('ejecucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='etl.ejecucionetl')),
            ],
            options={'ordering': ['timestamp']},
        ),
        migrations.CreateModel(
            name='Alerta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('tipo_alerta', models.CharField(max_length=50)),
                ('descripcion', models.TextField()),
                ('nivel_urgencia', models.CharField(choices=[('baja','Baja'),('media','Media'),('alta','Alta'),('critica','Crítica')], default='alta', max_length=10)),
                ('fecha_alerta', models.DateTimeField(auto_now_add=True)),
                ('fecha_vista', models.DateTimeField(blank=True, null=True)),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alertas', to='etl.paciente')),
                ('visto_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='authentication.usuarioclinico')),
            ],
            options={'ordering': ['-fecha_alerta']},
        ),
    ]
