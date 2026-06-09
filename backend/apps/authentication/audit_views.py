"""
Vistas para el log de auditoría de acciones de usuario.
Solo accesible para Administradores.

Mejora: los registros se persisten en la base de datos a través del modelo AuditoriaLog.
Si el modelo no existe, recae en almacenamiento en memoria (entorno dev).
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from .permissions import EsAdministrador

logger = logging.getLogger('security')

# Fallback en memoria para dev (se usa si AuditoriaLog no está disponible)
_audit_log_memory: list = []
_USE_DB = False  # se activa si el modelo AuditoriaLog está disponible

try:
    from .models import AuditoriaLog  # type: ignore
    _USE_DB = True
except ImportError:
    pass


def registrar_auditoria(usuario: str, metodo: str, endpoint: str, ip: str, status: int) -> None:
    """Registra una acción en el log de auditoría (BD si está disponible, memoria si no)."""
    from datetime import datetime

    entry = {
        'timestamp': datetime.now().isoformat(),
        'usuario':   usuario,
        'metodo':    metodo,
        'endpoint':  endpoint,
        'ip':        ip,
        'status':    status,
    }

    if _USE_DB:
        try:
            AuditoriaLog.objects.create(**entry)
            return
        except Exception:
            pass  # si falla, caer a memoria

    # Almacenamiento en memoria (dev / fallback)
    _audit_log_memory.append(entry)
    if len(_audit_log_memory) > 1000:
        del _audit_log_memory[:200]  # limpiar los más viejos


class AuditoriaView(APIView):
    """
    GET /api/auth/auditoria/
    Retorna el log de acciones de los últimos usuarios.
    Solo Administradores.
    """
    permission_classes = [EsAdministrador]

    def get(self, request):
        metodo = request.query_params.get('metodo', '')

        if _USE_DB:
            qs = AuditoriaLog.objects.order_by('-timestamp')[:200]
            logs = list(qs.values())
            if metodo:
                logs = [l for l in logs if l['metodo'] == metodo.upper()]
        else:
            logs = list(reversed(_audit_log_memory))
            if metodo:
                logs = [l for l in logs if l['metodo'] == metodo.upper()]
            logs = logs[:100]

        return Response({'count': len(logs), 'logs': logs})
