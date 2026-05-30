"""
Vistas para el log de auditoría de acciones de usuario.
Solo accesible para Administradores.
"""
import re
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from .permissions import EsAdministrador

# Parsear logs de auditoría desde el archivo de log o desde memoria
_audit_log = []  # almacenamiento en memoria para desarrollo


def registrar_auditoria(usuario: str, metodo: str, endpoint: str, ip: str, status: int):
    """Registra una acción en el log de auditoría en memoria."""
    from datetime import datetime
    _audit_log.append({
        'timestamp': datetime.now().isoformat(),
        'usuario':   usuario,
        'metodo':    metodo,
        'endpoint':  endpoint,
        'ip':        ip,
        'status':    status,
    })
    if len(_audit_log) > 500:  # mantener solo últimas 500 entradas
        _audit_log.pop(0)


class AuditoriaView(APIView):
    """
    GET /api/auth/auditoria/
    Retorna el log de acciones de los últimos usuarios.
    Solo Admin.
    """
    permission_classes = [EsAdministrador]

    def get(self, request):
        metodo = request.query_params.get('metodo', '')
        logs = list(reversed(_audit_log))  # más recientes primero
        if metodo:
            logs = [l for l in logs if l['metodo'] == metodo.upper()]
        return Response({'count': len(logs), 'logs': logs[:100]})
