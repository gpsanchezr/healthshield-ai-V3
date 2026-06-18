"""
ASGI entry-point para HealthShield AI.
Soporta HTTP clásico + WebSockets (Django Channels).
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Inicializar Django ANTES de importar routing (necesita apps cargadas)
django_asgi_app = get_asgi_application()

from apps.etl.routing import websocket_urlpatterns   # noqa: E402

application = ProtocolTypeRouter({
    "http":      django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
