"""
Configuración de producción — HealthShield AI
Activa HTTPS, HSTS, cookies seguras y cabeceras de seguridad.
"""
from .base import *
import dj_database_url

# ── Base ───────────────────────────────────────────────────────────────────────
DEBUG        = False
SECRET_KEY   = env('SECRET_KEY')                           # obligatorio en prod
ALLOWED_HOSTS = env('ALLOWED_HOSTS', '.onrender.com,.railway.app,localhost').split(',')

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
SECURE_SSL_REDIRECT             = True
SECURE_PROXY_SSL_HEADER         = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS             = 31536000    # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
SECURE_HSTS_PRELOAD             = True

# ── Cookies seguras ────────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE    = True
SESSION_COOKIE_HTTPONLY  = True
SESSION_COOKIE_SAMESITE  = 'Lax'
CSRF_COOKIE_SECURE       = True
CSRF_COOKIE_HTTPONLY     = True
CSRF_COOKIE_SAMESITE     = 'Lax'

# ── Cabeceras de seguridad adicionales ─────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
X_FRAME_OPTIONS                  = 'DENY'        # Previene clickjacking
SECURE_REFERRER_POLICY           = 'strict-origin-when-cross-origin'

# ── Logging en producción (stdout → Render/Railway lo captura) ──────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'production': {
            'format': '%(levelname)s %(asctime)s %(name)s %(process)d %(thread)d %(message)s'
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

# ── Redis / Celery en producción ────────────────────────────────────────────────
CELERY_BROKER_URL     = env('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
