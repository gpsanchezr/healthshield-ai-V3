from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def env(key, default=None):
    return os.environ.get(key, default)

SECRET_KEY = env('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG      = env('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'rest_framework_simplejwt', 'rest_framework_simplejwt.token_blacklist',
    'corsheaders', 'drf_spectacular', 'django_filters',
    'apps.authentication', 'apps.etl', 'apps.analytics', 'apps.ml', 'apps.dashboard', 'apps.reports',
    'django_celery_results',  # Persiste resultados Celery en BD
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

ROOT_URLCONF = 'config.urls'
AUTH_USER_MODEL = 'authentication.UsuarioClinico'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True; USE_TZ = True

# ── Base de Datos ─────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'healthshield',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR.parent / 'frontend' / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR.parent / 'frontend' / 'static']
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend','rest_framework.filters.SearchFilter','rest_framework.filters.OrderingFilter'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=int(env('JWT_ACCESS_MINUTES','60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(env('JWT_REFRESH_DAYS','7'))),
    'ALGORITHM': 'HS256', 'AUTH_HEADER_TYPES': ('Bearer',),
    'ROTATE_REFRESH_TOKENS': True, 'BLACKLIST_AFTER_ROTATION': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'HealthShield AI API', 'VERSION': '1.0.0',
    'DESCRIPTION': 'API REST — Plataforma Inteligente de Analítica Clínica HealthAnalytics IPS',
    'SERVE_INCLUDE_SCHEMA': False,
}

CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS','http://localhost:3000,http://localhost:8080').split(',')
ML_MODELS_PATH = env('ML_MODELS_PATH', str(BASE_DIR / 'ml_models'))
ETL_BATCH_SIZE = int(env('ETL_BATCH_SIZE', '500'))

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '{levelname} {asctime} {module}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}},
    'loggers': {
        'etl': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'ml':  {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}

# ── Celery + Redis (ETL asíncrono) ─────────────────────────────────────────────
CELERY_BROKER_URL        = env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND    = 'django-db'  # Persiste en PostgreSQL/SQLite
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE          = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT   = 300   # 5 minutos máximo por tarea

# ── Rate Limiting (protección contra abuso de API) ─────────────────────────────
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = [
    'rest_framework.throttling.AnonRateThrottle',
    'rest_framework.throttling.UserRateThrottle',
]
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '20/minute',    # usuarios anónimos: 20 req/min
    'user': '200/minute',   # usuarios autenticados: 200 req/min
}

# ── Celery Beat: tareas programadas ───────────────────────────────────────────
CELERY_BEAT_SCHEDULE = {
    'detectar-criticos-cada-hora': {
        'task':     'etl.detectar_criticos',
        'schedule': 3600,  # cada hora
    },
    'snapshot-analitico-diario': {
        'task':     'analytics.snapshot_diario',
        'schedule': 86400,  # cada 24h
    },
}

# ── Límites de subida de archivos ──────────────────────────────────────────────
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB máximo en memoria
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024   # 20 MB máximo por archivo
