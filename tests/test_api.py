"""
Smoke tests de integracion para la API REST de HealthShield AI.

Ejecutar:
    python tests/test_api.py

Este archivo no reemplaza una suite pytest/unittest completa; valida de forma
rapida que los endpoints principales respondan y que los permisos basicos
esten alineados con la configuracion actual del proyecto.
"""
import logging
import os
import sys
from dataclasses import dataclass
from importlib import import_module
from typing import Any

import pytest


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")


@dataclass
class SmokeStats:
    """Acumula el resultado de los smoke tests ejecutados."""

    passed: int = 0
    total: int = 0


@dataclass
class RuntimeState:
    """Guarda objetos inicializados despues de configurar Django."""

    client: Any = None


STATS = SmokeStats()
STATE = RuntimeState()


def check(name, fn):
    """Ejecuta una validacion y registra si pasa o falla."""
    STATS.total += 1
    try:
        fn()
    except Exception as exc:
        print(f"  [FAIL] {name}: {exc}")
        return

    STATS.passed += 1
    print(f"  [OK]   {name}")


def assert_status(response, expected, message=None):
    """Valida que el status HTTP sea uno de los esperados."""
    expected_values = (
        expected if isinstance(expected, (list, tuple, set)) else [expected]
    )
    if response.status_code not in expected_values:
        body = response.content.decode("utf-8", errors="replace")[:500]
        raise AssertionError(
            message
            or (
                f"status {response.status_code}, "
                f"esperado {list(expected_values)}. Body: {body}"
            )
        )


def get_client():
    """Devuelve el cliente de Django inicializado para la ejecucion actual."""
    assert STATE.client is not None
    return STATE.client


def json_response(response):
    """Devuelve el cuerpo JSON o lanza un error legible."""
    try:
        return response.json()
    except ValueError as exc:
        body = response.content.decode("utf-8", errors="replace")[:500]
        raise AssertionError(
            f"Respuesta no es JSON valido. Body: {body}"
        ) from exc


def get_token(username, password="Pass123!"):
    """Obtiene un access token para el usuario indicado."""
    response = get_client().post(
        "/api/auth/login/",
        {"username": username, "password": password},
        content_type="application/json",
    )
    assert_status(response, 200, f"No se pudo autenticar usuario {username!r}")
    data = json_response(response)
    assert "access" in data, f"Login sin access token: {data}"
    return data["access"]


def auth_header(token):
    """Construye el header HTTP de autenticacion JWT."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def seed_data():
    """Crea usuarios y datos clinicos minimos para los endpoints."""
    auth_models = import_module("apps.authentication.models")
    etl_models = import_module("apps.etl.models")
    usuario_clinico = auth_models.UsuarioClinico
    paciente_model = etl_models.Paciente
    registro_clinico = etl_models.RegistroClinico

    usuario_clinico.objects.create_superuser(
        "admin_test", "admin@test.com", "Pass123!", rol="administrador"
    )
    usuario_clinico.objects.create_user(
        "medico_test", "medico@test.com", "Pass123!", rol="medico"
    )
    usuario_clinico.objects.create_user(
        "analista_test", "analista@test.com", "Pass123!", rol="analista"
    )

    paciente = paciente_model.objects.create(
        cedula=123,
        nombres="Paciente",
        apellidos="Test",
        edad=30,
        sexo="F",
        id_paciente_original=1,
    )

    registro_clinico.objects.create(
        paciente=paciente,
        glucosa=100.0,
        imc=20.0,
        presion_sistolica=120,
        colesterol=180.0,
        saturacion_oxigeno=98.0,
        temperatura=36.5,
        frecuencia_cardiaca=80,
        riesgo_enfermedad="Bajo",
        fecha_consulta="2024-01-01",
    )


def case_login_ok():
    """Valida login exitoso y estructura del token."""
    response = get_client().post(
        "/api/auth/login/",
        {"username": "admin_test", "password": "Pass123!"},
        content_type="application/json",
    )
    assert_status(response, 200)
    data = json_response(response)
    assert "access" in data and "refresh" in data
    assert data["usuario"]["rol"] == "administrador"


def case_login_fail():
    """Valida rechazo de credenciales incorrectas."""
    response = get_client().post(
        "/api/auth/login/",
        {"username": "admin_test", "password": "wrong"},
        content_type="application/json",
    )
    assert_status(response, 401)


def case_login_sin_credenciales():
    """Valida que pacientes requiera autenticacion."""
    response = get_client().get("/api/pacientes/")
    assert_status(response, 401)


def case_me():
    """Valida el endpoint de usuario autenticado."""
    token = get_token("admin_test")
    response = get_client().get("/api/auth/me/", **auth_header(token))
    assert_status(response, 200)
    assert json_response(response)["rol"] == "administrador"


def case_refresh():
    """Valida renovacion de access token."""
    response = get_client().post(
        "/api/auth/login/",
        {"username": "admin_test", "password": "Pass123!"},
        content_type="application/json",
    )
    refresh = json_response(response)["refresh"]
    response = get_client().post(
        "/api/auth/refresh/",
        {"refresh": refresh},
        content_type="application/json",
    )
    assert_status(response, 200)
    assert "access" in json_response(response)


def case_pacientes_list_medico():
    """Valida listado de pacientes para rol medico."""
    token = get_token("medico_test")
    response = get_client().get("/api/pacientes/", **auth_header(token))
    assert_status(response, 200)
    data = json_response(response)
    assert isinstance(data, list) or "results" in data


def case_pacientes_list_analista():
    """Valida listado de pacientes para rol analista."""
    # EsMedico significa "acceso clinico" en permissions.py; incluye analista.
    token = get_token("analista_test")
    response = get_client().get("/api/pacientes/", **auth_header(token))
    assert_status(response, 200)


def case_historial_etl():
    """Valida historial ETL para rol analista."""
    token = get_token("analista_test")
    response = get_client().get("/api/etl/historial/", **auth_header(token))
    assert_status(response, 200)
    data = json_response(response)
    assert isinstance(data, list) or "results" in data


def case_etl_sin_archivo():
    """Valida error al ejecutar ETL sin archivo."""
    token = get_token("analista_test")
    response = get_client().post("/api/etl/run/", **auth_header(token))
    assert_status(response, 400)


def case_simular_solo_admin():
    """Valida que un medico no pueda simular datos ETL."""
    token = get_token("medico_test")
    response = get_client().post(
        "/api/etl/simular/",
        {"count": 5},
        content_type="application/json",
        **auth_header(token),
    )
    assert_status(response, 403)


def case_kpis():
    """Valida KPIs de analytics."""
    token = get_token("medico_test")
    response = get_client().get("/api/analytics/kpis/", **auth_header(token))
    assert_status(response, 200)
    assert "total_registros" in json_response(response)


def case_dashboard_kpis():
    """Valida KPIs del dashboard."""
    token = get_token("medico_test")
    response = get_client().get("/api/dashboard/kpis/", **auth_header(token))
    assert_status(response, 200)
    assert "kpis" in json_response(response)


def case_estadistica():
    """Valida estadisticas para un campo numerico."""
    token = get_token("analista_test")
    response = get_client().get(
        "/api/analytics/estadistica/?campo=glucosa", **auth_header(token)
    )
    assert_status(response, 200)
    data = json_response(response)
    assert "media" in data and "mediana" in data


def case_estadistica_campo_invalido():
    """Valida error para un campo estadistico invalido."""
    token = get_token("analista_test")
    response = get_client().get(
        "/api/analytics/estadistica/?campo=nombre_invalido",
        **auth_header(token),
    )
    assert_status(response, 400)


def case_modelo_metricas_sin_modelo():
    """Valida respuesta cuando no hay modelo de prediccion."""
    token = get_token("medico_test")
    response = get_client().get(
        "/api/predicciones/modelo/metricas/",
        **auth_header(token),
    )
    assert_status(response, 404)


def case_predicciones_list():
    """Valida listado de predicciones."""
    token = get_token("medico_test")
    response = get_client().get("/api/predicciones/", **auth_header(token))
    assert_status(response, 200)


def case_swagger_disponible():
    """Valida disponibilidad de Swagger UI."""
    response = get_client().get("/api/schema/swagger-ui/")
    assert_status(response, 200)


def case_schema_json():
    """Valida disponibilidad del schema OpenAPI."""
    response = get_client().get("/api/schema/")
    assert_status(response, 200)


def case_admin_puede_crear_usuario():
    """Valida que un admin pueda crear usuarios."""
    token = get_token("admin_test")
    response = get_client().post(
        "/api/auth/usuarios/",
        {
            "username": "nuevo_medico",
            "password": "Pass456!",
            "email": "nuevo@test.com",
            "rol": "medico",
            "first_name": "Nuevo",
            "last_name": "Medico",
        },
        content_type="application/json",
        **auth_header(token),
    )
    assert_status(response, 201)


def case_medico_no_puede_crear_usuario():
    """Valida que un medico no pueda crear usuarios."""
    token = get_token("medico_test")
    response = get_client().post(
        "/api/auth/usuarios/",
        {
            "username": "otro",
            "password": "Pass456!",
            "email": "otro@test.com",
            "rol": "medico",
        },
        content_type="application/json",
        **auth_header(token),
    )
    assert_status(response, 403)



def case_alertas_list():
    """Valida listado de alertas para médico."""
    token = get_token("medico_test")
    response = get_client().get("/api/etl/alertas/", **auth_header(token))
    assert_status(response, 200)
    data = json_response(response)
    assert "results" in data or isinstance(data, list)


def case_individual_pdf_sin_modelo():
    """Valida generación de PDF individual para el paciente creado en seed_data."""
    token = get_token("medico_test")
    # El paciente con pk=1 fue creado en seed_data
    from apps.etl.models import Paciente
    pk = Paciente.objects.first().pk
    response = get_client().get(
        f"/api/reportes/paciente/{pk}/", **auth_header(token)
    )
    # Acepta 200 (PDF generado) o 403 (permisos — según rol)
    assert_status(response, [200, 403])


def case_kpi_drilldown_sin_auth():
    """Valida que kpi_drilldown redirige al login sin JWT."""
    response = get_client().get("/pacientes/drilldown/?filtro=criticos")
    # Debe redirigir a /login/ (302) o devolver 200 con la página de login
    assert_status(response, [302, 200])
    if response.status_code == 302:
        assert "/login" in response.get("Location", "")


def case_correlacion():
    """Valida que el endpoint de correlación de Pearson responde correctamente."""
    token = get_token("analista_test")
    response = get_client().get("/api/analytics/correlacion/", **auth_header(token))
    assert_status(response, 200)
    data = json_response(response)
    assert "variables" in data or "matriz" in data or "labels" in data


TESTS = [
    ("POST /api/auth/login/ -> JWT tokens y datos usuario", case_login_ok),
    ("POST /api/auth/login/ credenciales incorrectas -> 401", case_login_fail),
    ("GET /api/pacientes/ sin token -> 401", case_login_sin_credenciales),
    ("GET /api/auth/me/ -> datos usuario autenticado", case_me),
    ("POST /api/auth/refresh/ -> nuevo access token", case_refresh),
    (
        "GET /api/pacientes/ con rol medico -> 200 + lista",
        case_pacientes_list_medico,
    ),
    (
        "GET /api/pacientes/ con rol analista -> 200",
        case_pacientes_list_analista,
    ),
    ("GET /api/etl/historial/ con rol analista -> 200", case_historial_etl),
    ("POST /api/etl/run/ sin archivo -> 400", case_etl_sin_archivo),
    ("POST /api/etl/simular/ con medico -> 403", case_simular_solo_admin),
    ("GET /api/analytics/kpis/ -> 200 + KPIs", case_kpis),
    ("GET /api/dashboard/kpis/ -> 200 + estructura kpis", case_dashboard_kpis),
    (
        "GET /api/analytics/estadistica/?campo=glucosa -> estadisticas",
        case_estadistica,
    ),
    (
        "GET /api/analytics/estadistica/ campo invalido -> 400",
        case_estadistica_campo_invalido,
    ),
    (
        "GET /api/predicciones/modelo/metricas/ sin modelo -> 404",
        case_modelo_metricas_sin_modelo,
    ),
    ("GET /api/predicciones/ -> 200 + lista", case_predicciones_list),
    ("GET /api/schema/swagger-ui/ -> 200", case_swagger_disponible),
    ("GET /api/schema/ -> 200", case_schema_json),
    (
        "POST /api/auth/usuarios/ con admin -> 201",
        case_admin_puede_crear_usuario,
    ),
    (
        "POST /api/auth/usuarios/ con medico -> 403",
        case_medico_no_puede_crear_usuario,
    ),
    ("GET /api/etl/alertas/ con medico -> 200 + lista",            case_alertas_list),
    ("GET /api/reportes/paciente/<pk>/ -> PDF o 403",              case_individual_pdf_sin_modelo),
    ("GET /pacientes/drilldown/ sin auth -> redirect login",       case_kpi_drilldown_sin_auth),
    ("GET /api/analytics/correlacion/ -> Pearson matrix",          case_correlacion),
]


def main():
    """Ejecuta todos los smoke tests dentro de una base temporal."""
    logging.disable(logging.CRITICAL)
    STATS.passed = 0
    STATS.total = 0

    django, test_module, runner_module, utils_module = configure_django()

    client_class = test_module.Client
    discover_runner = runner_module.DiscoverRunner
    setup_test_environment = utils_module.setup_test_environment
    teardown_test_environment = utils_module.teardown_test_environment

    django.setup()
    STATE.client = client_class()

    environment_started = False
    try:
        setup_test_environment()
        environment_started = True
    except RuntimeError as exc:
        if "setup_test_environment() was already called" not in str(exc):
            raise

    runner = discover_runner(verbosity=0)
    old_config = None

    try:
        old_config = runner.setup_databases()
        seed_data()

        for name, fn in TESTS:
            check(name, fn)
    finally:
        if old_config is not None:
            runner.teardown_databases(old_config)
        if environment_started:
            teardown_test_environment()

    print(f"\n{'=' * 55}")
    print(
        f"  API Tests: {STATS.passed}/{STATS.total} PASADOS "
        f"{'[ALL PASS]' if STATS.passed == STATS.total else failure_summary()}"
    )
    return 0 if STATS.passed == STATS.total else 1


def failure_summary():
    """Devuelve un resumen corto de pruebas fallidas."""
    return f"[{STATS.total - STATS.passed} FALLANDO]"


@pytest.mark.django_db(transaction=True)
def test_api_smoke():
    """Permite ejecutar este smoke test tambien desde pytest."""
    assert main() == 0


def configure_django():
    """Configura Django y devuelve los modulos requeridos por los tests."""
    os.makedirs(os.path.join(BACKEND_DIR, "staticfiles"), exist_ok=True)

    django = import_module("django")
    settings = import_module("django.conf").settings
    test_module = import_module("django.test")
    runner_module = import_module("django.test.runner")
    utils_module = import_module("django.test.utils")

    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]
    settings.SPECTACULAR_SETTINGS = {
        **getattr(settings, "SPECTACULAR_SETTINGS", {}),
        "DISABLE_ERRORS_AND_WARNINGS": True,
    }
    return django, test_module, runner_module, utils_module


if __name__ == "__main__":
    sys.exit(main())
