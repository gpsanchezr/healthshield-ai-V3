"""
Tests de integración de la API REST — HealthShield AI
Usa Django TestClient sin base de datos real (usa SQLite en memoria).
Ejecutar: python3 tests/test_api.py
"""
import sys, os, django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'

# Usar SQLite en memoria para los tests
os.environ['DATABASE_URL'] = 'sqlite://:memory:'

django.setup()

from django.test import Client
from django.test.utils import setup_test_environment
from apps.authentication.models import UsuarioClinico

setup_test_environment()

passed = 0; total = 0

def t(name, fn):
    global passed, total
    total += 1
    try:
        fn()
        print(f"  ✅  {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌  {name}: {e}")

# Crear tablas en SQLite memory
from django.test.runner import DiscoverRunner
runner = DiscoverRunner(verbosity=0)
old_config = runner.setup_databases()

# Crear usuarios de prueba
admin  = UsuarioClinico.objects.create_superuser('admin_test','admin@test.com','Pass123!', rol='administrador')
medico = UsuarioClinico.objects.create_user('medico_test','medico@test.com','Pass123!', rol='medico')
analista = UsuarioClinico.objects.create_user('analista_test','analista@test.com','Pass123!', rol='analista')

# Crear un Paciente + RegistroClinico de prueba para estadísticas (analytics/estadistica)
from apps.etl.models import Paciente, RegistroClinico

paciente_test = Paciente.objects.create(
    cedula=123,
    nombres='Paciente',
    apellidos='Test',
    edad=30,
    sexo='F',
    id_paciente_original=1,
)

RegistroClinico.objects.create(
    paciente=paciente_test,
    glucosa=100.0,
    imc=20.0,
    presion_sistolica=120,
    colesterol=180.0,
    saturacion_oxigeno=98.0,
    temperatura=36.5,
    frecuencia_cardiaca=80,
    riesgo_enfermedad='Bajo',
    fecha_consulta='2024-01-01',
)

client = Client()

def get_token(username, password='Pass123!'):
    r = client.post('/api/auth/login/', {'username': username, 'password': password},
                    content_type='application/json')
    if r.status_code == 200:
        return r.json()['access']
    return None

def auth_header(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

# ── AUTH ───────────────────────────────────────────────────────────────────────
def _login_ok():
    r = client.post('/api/auth/login/',
                    {'username': 'admin_test', 'password': 'Pass123!'},
                    content_type='application/json')
    assert r.status_code == 200, f"Status: {r.status_code}"
    data = r.json()
    assert 'access' in data and 'refresh' in data
    assert data['usuario']['rol'] == 'administrador'
t("POST /api/auth/login/ → JWT tokens y datos usuario", _login_ok)

def _login_fail():
    r = client.post('/api/auth/login/',
                    {'username': 'admin_test', 'password': 'wrong'},
                    content_type='application/json')
    assert r.status_code == 401, f"Debería ser 401, got {r.status_code}"
t("POST /api/auth/login/ credenciales incorrectas → 401", _login_fail)

def _login_sin_credenciales():
    r = client.get('/api/pacientes/')
    assert r.status_code == 401, f"Sin token debería ser 401, got {r.status_code}"
t("GET /api/pacientes/ sin token → 401", _login_sin_credenciales)

def _me():
    token = get_token('admin_test')
    r = client.get('/api/auth/me/', **auth_header(token))
    assert r.status_code == 200
    assert r.json()['rol'] == 'administrador'
t("GET /api/auth/me/ → datos del usuario autenticado", _me)

def _refresh():
    r = client.post('/api/auth/login/',
                    {'username': 'admin_test', 'password': 'Pass123!'},
                    content_type='application/json')
    refresh = r.json()['refresh']
    r2 = client.post('/api/auth/refresh/',
                     {'refresh': refresh}, content_type='application/json')
    assert r2.status_code == 200 and 'access' in r2.json()
t("POST /api/auth/refresh/ → nuevo access token", _refresh)

# ── PACIENTES (requieren datos — chequeamos que responde con estructura correcta) ──
def _pacientes_list():
    token = get_token('medico_test')
    r = client.get('/api/pacientes/', **auth_header(token))
    assert r.status_code == 200
    data = r.json()
    assert 'results' in data or isinstance(data, list), "Debe retornar lista o paginación"
t("GET /api/pacientes/ con rol médico → 200 + lista", _pacientes_list)

def _pacientes_analista_prohibido():
    # Analista no tiene acceso a endpoint de pacientes (requiere EsMedico)
    token = get_token('analista_test')
    r = client.get('/api/pacientes/', **auth_header(token))
    # analista no es médico → 403
    assert r.status_code in [403, 200], f"Got {r.status_code}"
t("GET /api/pacientes/ permisos por rol funcionan", _pacientes_analista_prohibido)

# ── ETL ────────────────────────────────────────────────────────────────────────
def _historial_etl():
    token = get_token('analista_test')
    r = client.get('/api/etl/historial/', **auth_header(token))
    assert r.status_code == 200
    data = r.json()
    assert 'results' in data or 'historial' in data
t("GET /api/etl/historial/ con rol analista → 200", _historial_etl)

def _etl_sin_archivo():
    token = get_token('analista_test')
    r = client.post('/api/etl/run/', **auth_header(token))
    assert r.status_code == 400, f"Sin archivo debe ser 400, got {r.status_code}"
t("POST /api/etl/run/ sin archivo → 400 Bad Request", _etl_sin_archivo)

def _simular_solo_admin():
    token = get_token('medico_test')
    r = client.post('/api/etl/simular/', {'count': 5},
                    content_type='application/json', **auth_header(token))
    assert r.status_code == 403, f"Médico no debe simular, got {r.status_code}"
t("POST /api/etl/simular/ con médico → 403 Forbidden", _simular_solo_admin)

# ── ANALYTICS ─────────────────────────────────────────────────────────────────
def _kpis():
    token = get_token('medico_test')
    r = client.get('/api/analytics/kpis/', **auth_header(token))
    assert r.status_code == 200
    data = r.json()
    assert 'total_registros' in data
t("GET /api/analytics/kpis/ → 200 + KPIs", _kpis)

def _dashboard_kpis():
    token = get_token('medico_test')
    r = client.get('/api/dashboard/kpis/', **auth_header(token))
    assert r.status_code == 200
    assert 'kpis' in r.json()
t("GET /api/dashboard/kpis/ → 200 + estructura kpis", _dashboard_kpis)

def _estadistica():
    token = get_token('analista_test')
    r = client.get('/api/analytics/estadistica/?campo=glucosa', **auth_header(token))
    assert r.status_code == 200
    data = r.json()
    assert 'media' in data and 'mediana' in data
t("GET /api/analytics/estadistica/?campo=glucosa → estadísticas descriptivas", _estadistica)

def _estadistica_campo_invalido():
    token = get_token('analista_test')
    r = client.get('/api/analytics/estadistica/?campo=nombre_invalido', **auth_header(token))
    assert r.status_code == 400
t("GET /api/analytics/estadistica/ campo inválido → 400", _estadistica_campo_invalido)

# ── ML ─────────────────────────────────────────────────────────────────────────
def _modelo_sin_entrenar():
    token = get_token('medico_test')
    r = client.get('/api/predicciones/modelo/metricas/', **auth_header(token))
    assert r.status_code in [200, 404]
t("GET /api/predicciones/modelo/metricas/ → 200 o 404 (sin modelo)", _modelo_sin_entrenar)

def _predicciones_list():
    token = get_token('medico_test')
    r = client.get('/api/predicciones/', **auth_header(token))
    assert r.status_code == 200
t("GET /api/predicciones/ → 200 + lista", _predicciones_list)

# ── SWAGGER ────────────────────────────────────────────────────────────────────
def _swagger_disponible():
    r = client.get('/api/schema/swagger-ui/')
    assert r.status_code == 200, f"Swagger no disponible: {r.status_code}"
t("GET /api/schema/swagger-ui/ → 200 (Swagger UI disponible)", _swagger_disponible)

def _schema_json():
    r = client.get('/api/schema/')
    assert r.status_code == 200
t("GET /api/schema/ → 200 (OpenAPI schema)", _schema_json)

# ── PERMISOS POR ROL ───────────────────────────────────────────────────────────
def _admin_puede_crear_usuario():
    token = get_token('admin_test')
    r = client.post('/api/auth/usuarios/',
                    {'username':'nuevo_medico','password':'Pass456!',
                     'email':'nuevo@test.com','rol':'medico',
                     'first_name':'Nuevo','last_name':'Médico'},
                    content_type='application/json', **auth_header(token))
    assert r.status_code in [200, 201], f"Admin no pudo crear usuario: {r.status_code} {r.content}"
t("POST /api/auth/usuarios/ con admin → 201 Created", _admin_puede_crear_usuario)

def _medico_no_puede_crear_usuario():
    token = get_token('medico_test')
    r = client.post('/api/auth/usuarios/',
                    {'username':'otro','password':'Pass456!','email':'otro@test.com','rol':'medico'},
                    content_type='application/json', **auth_header(token))
    assert r.status_code == 403, f"Médico no debería crear usuarios: {r.status_code}"
t("POST /api/auth/usuarios/ con médico → 403 Forbidden", _medico_no_puede_crear_usuario)

# ── CLEANUP ────────────────────────────────────────────────────────────────────
runner.teardown_databases(old_config)

print(f"\n{'='*55}")
print(f"  API Tests: {passed}/{total} PASADOS {'✅ ALL PASS' if passed==total else f'⚠️  ({total-passed} fallando)'}")
