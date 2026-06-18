"""
HealthShield AI V4 — Configuración de Producción
==================================================
Configuración inteligente: Desactiva restricciones SSL si DEBUG es True.
"""

from .base import *
import dj_database_url
import os

# ── Base ───────────────────────────────────────────────────────────────────────
# Leemos DEBUG del entorno, por defecto False
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = env('SECRET_KEY')

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,0.0.0.0'
).strip().split(',')

# ── Base de Datos ──────────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.parse(
        env('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ── Archivos estáticos (WhiteNoise) ────────────────────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── HTTPS y cabeceras de seguridad ─────────────────────────────────────────────
# IMPORTANTE: Desactivamos el redireccionamiento HTTPS solo si DEBUG está activo
SECURE_SSL_REDIRECT = False if DEBUG else True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS: Solo habilitar en producción real
SECURE_HSTS_SECONDS = 0 if DEBUG else 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── Cookies seguras (Condicionales) ────────────────────────────────────────────
SESSION_COOKIE_SECURE   = False if DEBUG else True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE      = False if DEBUG else True
CSRF_COOKIE_HTTPONLY    = True
CSRF_COOKIE_SAMESITE    = 'Lax'

# ── Cabeceras de seguridad adicionales ─────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER   = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'
SECURE_REFERRER_POLICY      = 'strict-origin-when-cross-origin'

# ── CORS para producción ───────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8080',
).strip().split(',')

CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://.*\.onrender\.com$',
    r'^https://.*\.up\.railway\.app$',
]

# ── Redis / Celery en producción ───────────────────────────────────────────────
CELERY_BROKER_URL     = env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'

# ── Django Channels — Redis Channel Layer en producción ───────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG':  {'hosts': [env('REDIS_URL', 'redis://localhost:6379/0')]},
    }
}

# ── Logging en producción ──────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'production': {
            'format': '%(levelname)s %(asctime)s %(name)s %(process)d %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'production',
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