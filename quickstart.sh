#!/bin/bash
# HealthShield AI V4.1 — Quickstart Local
# Uso: bash quickstart.sh
# FIX #5: detección automática del dataset (cualquier .xlsx en datasets/)
set -e

echo "╔════════════════════════════════════════════════════╗"
echo "║          HealthShield AI V4.1 — Quickstart        ║"
echo "║  Plataforma Inteligente de Analítica Clínica      ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# ── Requisito: Python 3.12+ ───────────────────────────────────────────────────
python3 --version 2>&1 | grep -q "3.1[2-9]" || {
  echo "⚠  Se recomienda Python 3.12+. Continuando de todas formas..."
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/backend"

# ── Verificar .env ────────────────────────────────────────────────────────────
if [ ! -f "../.env" ]; then
  echo "⚠  No se encontró .env — creando desde .env.example..."
  cp ../.env.example ../.env
  echo "   → Revisa ../.env y ajusta DATABASE_URL si necesitas MySQL/PostgreSQL."
  echo "   → Para desarrollo sin XAMPP, DATABASE_URL=sqlite:///db.sqlite3 ya funciona."
fi

# Cargar variables de entorno
set -a; [ -f "../.env" ] && source "../.env"; set +a

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
                password=pwd, rol=rol, first_name=first, last_name=last)
        else:
            UsuarioClinico.objects.create_user(
                username=username, email=f'{username}@healthshield.ai',
                password=pwd, rol=rol, first_name=first, last_name=last)
        print(f'  → {username} creado ({rol})')
    else:
        print(f'  → {username} ya existe')
"

# ── FIX #5: Detección automática del dataset ──────────────────────────────────
echo "[5/7] Ejecutando ETL con dataset clínico..."

DATASETS_DIR="$SCRIPT_DIR/datasets"
DATASET_FOUND=""

# Prioridad 1: dataset estandarizado SENA
if [ -f "$DATASETS_DIR/dataset_clinico_etl_1800_registros_ESTANDARIZADO.xlsx" ]; then
  DATASET_FOUND="$DATASETS_DIR/dataset_clinico_etl_1800_registros_ESTANDARIZADO.xlsx"
  echo "  → Usando dataset estandarizado SENA V4"
fi

# Prioridad 2: cualquier archivo con 'dataset' en el nombre
if [ -z "$DATASET_FOUND" ]; then
  for f in "$DATASETS_DIR"/dataset*.xlsx "$DATASETS_DIR"/dataset*.csv; do
    if [ -f "$f" ]; then
      DATASET_FOUND="$f"
      echo "  → Usando: $(basename "$f")"
      break
    fi
  done
fi

# Prioridad 3: cualquier .xlsx en datasets/
if [ -z "$DATASET_FOUND" ]; then
  for f in "$DATASETS_DIR"/*.xlsx "$DATASETS_DIR"/*.csv; do
    if [ -f "$f" ]; then
      DATASET_FOUND="$f"
      echo "  → Usando: $(basename "$f")"
      break
    fi
  done
fi

# Fallback: simulación
if [ -n "$DATASET_FOUND" ]; then
  python manage.py run_etl --file "$DATASET_FOUND"
else
  echo "  ⚠  No se encontró ningún dataset en $DATASETS_DIR"
  echo "     Generando 500 registros simulados..."
  python manage.py run_etl --simulate --count 500
fi

echo "[6/7] Entrenando modelo de Machine Learning (Random Forest)..."
python manage.py train_model --algorithm random_forest

echo "[7/7] Detectando pacientes críticos y generando alertas..."
python manage.py shell -c "
from apps.analytics.calculators import PacienteCriticoDetector
n = PacienteCriticoDetector().detectar()
print(f'  → {n} alertas críticas generadas')
"

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║           ✅  SETUP COMPLETADO V4.1               ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  🌐 App:       http://localhost:8000               ║"
echo "║  📚 Swagger:   http://localhost:8000/api/schema/   ║"
echo "║  🔧 Admin:     http://localhost:8000/admin/        ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  👤 Admin:    admin    / Admin123!                 ║"
echo "║  🏥 Médico:   medico   / Medico123!                ║"
echo "║  📊 Analista: analista / Analista123!              ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║  🔌 WebSockets: ws://localhost:8000/ws/alertas/   ║"
echo "║  🤖 IA Gemini:  agrega GEMINI_API_KEY en .env     ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Iniciando servidor Daphne (ASGI — HTTP + WebSockets)..."
python manage.py runserver 0.0.0.0:8000
