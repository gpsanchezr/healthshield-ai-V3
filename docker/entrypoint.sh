#!/bin/bash
set -e

echo "╔══════════════════════════════════════════╗"
echo "║       HealthShield AI — Iniciando        ║"
echo "╚══════════════════════════════════════════╝"

echo "[1/4] Aplicando migraciones..."
python manage.py migrate --noinput

echo "[2/4] Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "[3/4] Creando usuarios del sistema..."
python manage.py shell -c "
from apps.authentication.models import UsuarioClinico

usuarios = [
    ('admin',    'Admin123!',    'administrador', 'Administrador', 'HealthShield'),
    ('medico',   'Medico123!',   'medico',        'Dr. Juan',      'Pérez'),
    ('analista', 'Analista123!', 'analista',      'Ana',           'Rodríguez'),
]
for username, pwd, rol, first, last in usuarios:
    if not UsuarioClinico.objects.filter(username=username).exists():
        fn = UsuarioClinico.objects.create_superuser if rol == 'administrador' else UsuarioClinico.objects.create_user
        fn(username=username, email=f'{username}@healthshield.ai',
           password=pwd, rol=rol, first_name=first, last_name=last)
        print(f'  → {username} creado ({rol})')
    else:
        print(f'  → {username} ya existe')
"

echo "[4/4] Iniciando servidor Daphne (ASGI — HTTP + WebSockets)..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
