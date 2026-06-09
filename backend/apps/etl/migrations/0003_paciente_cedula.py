from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('etl', '0002_alter_paciente_options_alter_alerta_id_and_more'),
    ]
    operations = [
        migrations.AddField(
            model_name='paciente',
            name='cedula',
            field=models.BigIntegerField(blank=True, null=True, unique=True, verbose_name='Cédula'),
        ),
    ]
