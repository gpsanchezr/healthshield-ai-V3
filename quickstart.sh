#!/bin/bash
# HealthShield AI — Quickstart Local
# Uso: bash quickstart.sh
# Base de datos: SQLite (desarrollo) — el archivo db.sqlite3 se crea automáticamente
set -e

echo "╔════════════════════════════════════════════════════╗"
echo "║          HealthShield AI — Quickstart             ║"
echo "║  Plataforma Inteligente de Analítica Clínica      ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

python3 --version 2>&1 | grep -q "3.1[2-9]" || {
  echo "⚠  Se recomienda Python 3.12+. Continuando de todas formas..."
}

cd "$(dirname "$0")/backend"

echo "[1/7] Instalando dependencias..."
pip install -r requirements.txt --quiet

echo "[2/7] Aplicando migraciones (SQLite desarrollo)..."
python manage.py migrate --noinput

echo "[3/7] Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true

echo "[4/7] Creando usuarios del sistema..."
python manage.py shell -c "
from apps.authentication.models import UsuarioClinico
usuarios = [
    ('admin',    'Admin123!',    'administrador', 'Administrador',  'HealthShield'),
    ('medico',   'Medico123!',   'medico',         'Dr. Juan',       'Pérez'),
    ('analista', 'Analista123!', 'analista',       'Ana',            'Rodríguez'),
]
for username, pwd, rol, first, last in usuarios:
    if not UsuarioClinico.objects.filter(username=username).exists():
        if rol == 'administrador':
            UsuarioClinico.objects.create_superuser(
                username=username, email=f'{username}@healthshield.ai',
                password=pwd, rol=rol, first_name=first, last_name=last)
        else:
            UsuarioClinico.objects.create_user(
                username=username, email=f'{username}@healthshield.ai',
                password=pwd, rol=rol, first_name=first, last_name=last)
        print(f'  → {username} creado ({rol})')
    else:
        print(f'  → {username} ya existe')
"

echo "[5/7] Ejecutando ETL con dataset clínico..."
if [ -f "../datasets/dataset_clinico_etl_1800_registros__1_.xlsx" ]; then
    python manage.py run_etl --file ../datasets/dataset_clinico_etl_1800_registros__1_.xlsx
elif [ -f "../datasets/clinical_data_v3_clean.xlsx" ]; then
    python manage.py run_etl --file ../datasets/clinical_data_v3_clean.xlsx
else
    echo "  Dataset no encontrado, generando 200 registros simulados..."
    python manage.py run_etl --simulate --count 200
fi

echo "[6/7] Entrenando modelo de Machine Learning..."
python manage.py train_model --algorithm random_forest

echo "[7/7] Detectando pacientes críticos y generando alertas..."
python manage.py shell -c "
from apps.analytics.calculators import PacienteCriticoDetector
n = PacienteCriticoDetector().detectar()
print(f'  → {n} alertas críticas generadas')
"

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║           ✅ SETUP COMPLETADO                     ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  🌐 App:       http://localhost:8000               ║"
echo "║  📚 Swagger:   http://localhost:8000/api/schema/   ║"
echo "║  🔧 Admin:     http://localhost:8000/admin/        ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  👤 Admin:    admin    / Admin123!                 ║"
echo "║  🏥 Médico:   medico   / Medico123!                ║"
echo "║  📊 Analista: analista / Analista123!              ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  🔌 WebSockets: ws://localhost:8000/ws/alertas/    ║"
echo "║  🤖 IA Gemini:  agrega GEMINI_API_KEY en .env      ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Iniciando servidor Daphne (ASGI — HTTP + WebSockets)..."
python manage.py runserver 0.0.0.0:8000
