#!/bin/bash
set -e

echo "=== HealthShield AI — Iniciando ==="
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

# Crear superusuario si no existe
python manage.py shell -c "
from apps.authentication.models import UsuarioClinico
if not UsuarioClinico.objects.filter(username='admin').exists():
    UsuarioClinico.objects.create_superuser('admin','admin@healthshield.ai','Admin123!', rol='administrador')
    print('Superusuario admin creado.')
"

# Cargar dataset si BD está vacía
python manage.py shell -c "
from apps.etl.models import RegistroClinico
if RegistroClinico.objects.count() == 0:
    from apps.etl.pipeline import ETLPipeline
    import os
    dataset = 'datasets/clinical_data_v1.0_raw.xlsx'
    if os.path.exists(dataset):
        ETLPipeline(tipo='automatico').run(dataset)
        print('Dataset cargado.')
    else:
        print('Dataset no encontrado, usa: python manage.py run_etl --simulate --count 100')
"

echo "=== Iniciando servidor Gunicorn ==="
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120
