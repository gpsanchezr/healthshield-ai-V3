#!/bin/bash
# HealthShield AI — Quickstart Completo
# Uso: bash quickstart.sh
set -e

echo "╔════════════════════════════════════════════════════╗"
echo "║          HealthShield AI — Quickstart             ║"
echo "║  Plataforma Inteligente de Analítica Clínica      ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Verificar Python 3.12+
python3 --version 2>&1 | grep -q "3.1[2-9]" || {
  echo "⚠  Se recomienda Python 3.12+. Continuando de todas formas..."
}

cd "$(dirname "$0")/backend"

echo "[1/7] Instalando dependencias..."
pip install -r requirements.txt --quiet

echo "[2/7] Aplicando migraciones..."
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
                password=pwd, rol=rol, first_name=first, last_name=last
            )
        else:
            UsuarioClinico.objects.create_user(
                username=username, email=f'{username}@healthshield.ai',
                password=pwd, rol=rol, first_name=first, last_name=last
            )
        print(f'  → {username} creado ({rol})')
    else:
        print(f'  → {username} ya existe')
"

echo "[5/7] Ejecutando ETL con dataset clínico..."
if [ -f "../datasets/clinical_data_v3_clean.xlsx" ]; then
    python manage.py run_etl --file ../datasets/clinical_data_v3_clean.xlsx
else
    echo "  Dataset no encontrado, generando datos simulados..."
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
echo "║  🌐 App:     http://localhost:8000               ║"
echo "║  📚 Swagger: http://localhost:8000/api/schema/   ║"
echo "║  🔧 Admin:   http://localhost:8000/admin/        ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  👤 Admin:    admin    / Admin123!               ║"
echo "║  🏥 Médico:   medico   / Medico123!              ║"
echo "║  📊 Analista: analista / Analista123!            ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  🤖 IA Claude: agrega ANTHROPIC_API_KEY en .env  ║"
echo "║  ✨ IA Gemini: agrega GEMINI_API_KEY en .env     ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Iniciando servidor Django..."
python manage.py runserver 0.0.0.0:8000
