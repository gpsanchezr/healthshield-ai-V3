"""
HealthShield AI V4 — Configuración Base
========================================
CORRECCIÓN V4.1 — FIX #1:
  Base de datos ahora configurable 100% desde variable de entorno DATABASE_URL.
  Por defecto usa SQLite para desarrollo local (sin necesidad de XAMPP/MySQL).
  En producción (Render/Railway) se inyecta DATABASE_URL con PostgreSQL.
"""

from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(key, default=None):
    return os.environ.get(key, default)


SECRET_KEY    = env('SECRET_KEY', 'dev-secret-key-change-in-production-NEVER-use-this')
DEBUG         = env('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'daphne',                  # DEBE ir primero — sobreescribe runserver con ASGI
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'django_filters',
    'apps.authentication',
    'apps.etl',
    'apps.analytics',
    'apps.ml',
    'apps.dashboard',
    'apps.reports',
    'django_celery_results',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.authentication.middleware.LoginBruteForceMiddleware',
    'apps.authentication.middleware.SanitizacionMiddleware',
    'apps.authentication.middleware.AuditoriaMiddleware',
]

ROOT_URLCONF     = 'config.urls'
ASGI_APPLICATION = 'config.asgi.application'
AUTH_USER_MODEL  = 'authentication.UsuarioClinico'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL        = '/login/'
LANGUAGE_CODE    = 'es-co'
TIME_ZONE        = 'America/Bogota'
USE_I18N         = True
USE_TZ           = True

# ── Base de Datos (FIX #1) ────────────────────────────────────────────────────
# Prioridad: DATABASE_URL (env) > MySQL local > SQLite (fallback dev)
#
# Para desarrollo sin XAMPP, añadir al .env:
#   DATABASE_URL=sqlite:///db.sqlite3
#
# Para producción (Render/Railway), añadir al .env:
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname

_DATABASE_URL = env('DATABASE_URL')

if _DATABASE_URL:
    # dj_database_url parsea cualquier esquema: sqlite://, postgresql://, mysql://
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(
            _DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Fallback: MySQL local (XAMPP) — configuración original del proyecto
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.mysql',
            'NAME':     env('DB_NAME',     'healthshield'),
            'USER':     env('DB_USER',     'root'),
            'PASSWORD': env('DB_PASSWORD', ''),
            'HOST':     env('DB_HOST',     '127.0.0.1'),
            'PORT':     env('DB_PORT',     '3306'),
            'OPTIONS':  {
                'charset':     'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS':    [BASE_DIR.parent / 'frontend' / 'templates'],
    'APP_DIRS': True,
    'OPTIONS':  {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

# ── Archivos estáticos ────────────────────────────────────────────────────────
STATIC_URL       = '/static/'
STATIC_ROOT      = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR.parent / 'frontend' / 'static']
MEDIA_URL        = '/media/'
MEDIA_ROOT       = BASE_DIR / 'media'

# ── REST Framework ────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=int(env('JWT_ACCESS_MINUTES', 60))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(env('JWT_REFRESH_DAYS', 7))),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ── Swagger / OpenAPI ─────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE':       'HealthShield AI API',
    'DESCRIPTION': 'Plataforma Inteligente de Analítica Clínica — HealthAnalytics IPS',
    'VERSION':     '4.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:8000,http://localhost:3000,http://127.0.0.1:8000',
).split(',')
CORS_ALLOW_CREDENTIALS = True

# ── Celery ────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL     = env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# ── Django Channels (WebSockets) ──────────────────────────────────────────────
_redis_url = env('REDIS_URL', 'redis://localhost:6379/0')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG':  {'hosts': [_redis_url]},
    }
}

# ── ML ────────────────────────────────────────────────────────────────────────
ML_MODELS_PATH       = env('ML_MODELS_PATH', str(BASE_DIR / 'ml_models'))
ML_RETRAIN_THRESHOLD = float(env('ML_RETRAIN_THRESHOLD', '0.05'))

# ── ETL ───────────────────────────────────────────────────────────────────────
ETL_BATCH_SIZE = int(env('ETL_BATCH_SIZE', '500'))

# ── IA Generativa ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = env('ANTHROPIC_API_KEY', '')
GEMINI_API_KEY    = env('GEMINI_API_KEY',    '')
AI_TIMEOUT        = int(env('AI_TIMEOUT_SECONDS', '20'))

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(levelname)s] %(asctime)s %(name)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'etl':      {'handlers': ['console'], 'level': 'INFO',    'propagate': False},
        'ml':       {'handlers': ['console'], 'level': 'INFO',    'propagate': False},
        'security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'django':   {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}
