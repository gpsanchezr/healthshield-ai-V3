"""
SanitizacionMiddleware: limpia inputs de texto antes de que lleguen a las views.
Protege contra XSS, inyección de scripts y caracteres de control peligrosos.
"""
import html
import json
import logging
from typing import Any

from django.http import HttpRequest

logger = logging.getLogger('security')


def _sanitize_value(value: Any) -> Any:
    """Escapa HTML y elimina caracteres de control en strings."""
    if isinstance(value, str):
        cleaned = html.escape(value.strip())
        # Eliminar caracteres de control (excepto \n y \t)
        cleaned = ''.join(c for c in cleaned if ord(c) >= 32 or c in '\n\t')
        return cleaned
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


class SanitizacionMiddleware:
    """
    Middleware que sanitiza el body JSON de requests POST/PUT/PATCH.
    No modifica archivos (multipart) ni GET params.
    """

    METODOS_SANITIZAR = {'POST', 'PUT', 'PATCH'}
    RUTAS_EXCLUIDAS  = {'/admin/', '/api/schema/'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if (request.method in self.METODOS_SANITIZAR
                and not any(request.path.startswith(r) for r in self.RUTAS_EXCLUIDAS)
                and request.content_type == 'application/json'):
            try:
                body = json.loads(request.body)
                sanitized = _sanitize_value(body)
                request._sanitized_body = sanitized
                request._body = json.dumps(sanitized).encode('utf-8')
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # body no es JSON válido — las views devolverán 400
        return self.get_response(request)


class AuditoriaMiddleware:
    """
    Registra en log cada acción importante (POST/PUT/PATCH/DELETE)
    con el usuario, endpoint, IP y timestamp.
    """

    METODOS_AUDITAR = {'POST', 'PUT', 'PATCH', 'DELETE'}
    RUTAS_IGNORAR   = {'/api/auth/refresh/', '/api/schema/', '/static/', '/admin/jsi18n/'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)

        if (request.method in self.METODOS_AUDITAR
                and not any(request.path.startswith(r) for r in self.RUTAS_IGNORAR)
                and response.status_code < 500):
            usuario = getattr(request, 'user', None)
            nombre  = str(usuario) if usuario and usuario.is_authenticated else 'anónimo'
            ip      = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '?'))
            logger.info(
                f"[AUDIT] {request.method} {request.path} | "
                f"usuario={nombre} | ip={ip} | status={response.status_code}"
            )
            try:
                from apps.authentication.audit_views import registrar_auditoria
                registrar_auditoria(nombre, request.method, request.path, ip, response.status_code)
            except Exception:
                pass
        return response


# ── Protección contra fuerza bruta en login ───────────────────────────────────
from collections import defaultdict
import time as _time

_failed_attempts: dict = defaultdict(list)  # ip → [timestamps]
MAX_INTENTOS     = 5
VENTANA_SEGUNDOS = 300   # 5 minutos
BLOQUEO_SEGUNDOS = 900   # 15 minutos tras superar límite


class LoginBruteForceMiddleware:
    """
    Bloquea IPs que superan MAX_INTENTOS fallidos en VENTANA_SEGUNDOS.
    Retorna HTTP 429 con mensaje de bloqueo temporal.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.path == '/api/auth/login/' and request.method == 'POST':
            ip = request.META.get('HTTP_X_FORWARDED_FOR',
                                  request.META.get('REMOTE_ADDR', '0.0.0.0')).split(',')[0].strip()
            now = _time.time()
            # Limpiar intentos viejos
            _failed_attempts[ip] = [t for t in _failed_attempts[ip] if now - t < BLOQUEO_SEGUNDOS]

            if len(_failed_attempts[ip]) >= MAX_INTENTOS:
                tiempo_restante = int(BLOQUEO_SEGUNDOS - (now - _failed_attempts[ip][0]))
                from django.http import JsonResponse
                logger.warning(f"[SECURITY] IP bloqueada por fuerza bruta: {ip}")
                return JsonResponse(
                    {'detail': f'Demasiados intentos fallidos. Espera {tiempo_restante // 60} minutos.'},
                    status=429
                )

        response = self.get_response(request)

        # Registrar intento fallido
        if request.path == '/api/auth/login/' and request.method == 'POST' and response.status_code == 401:
            ip = request.META.get('HTTP_X_FORWARDED_FOR',
                                  request.META.get('REMOTE_ADDR', '0.0.0.0')).split(',')[0].strip()
            _failed_attempts[ip].append(_time.time())
            intentos = len(_failed_attempts[ip])
            logger.warning(f"[SECURITY] Login fallido #{intentos} desde {ip}")

        return response
