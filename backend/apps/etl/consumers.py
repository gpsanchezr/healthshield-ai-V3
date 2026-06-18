"""
WebSocket Consumer para alertas clínicas en tiempo real.
URL: ws://host/ws/alertas/?token=<jwt_access_token>

Flujo:
  1. Cliente abre conexión con JWT en query string
  2. Consumer valida el token
  3. Se une al grupo "alertas_broadcast"
  4. Recibe eventos type=nueva_alerta cuando PacienteCriticoDetector crea alertas
  5. Re-emite la alerta al cliente en JSON
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class AlertasConsumer(AsyncWebsocketConsumer):
    GROUP = "alertas_broadcast"

    # ── Conexión ──────────────────────────────────────────────────────────────
    async def connect(self):
        # Validar JWT en query string: ?token=<access_token>
        if not await self._token_valido():
            await self.close(code=4001)   # 4001 = unauthorized
            return

        await self.channel_layer.group_add(self.GROUP, self.channel_name)
        await self.accept()

        # Enviar conteo inicial de alertas pendientes
        await self._enviar_conteo()

    # ── Desconexión ───────────────────────────────────────────────────────────
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP, self.channel_name)

    # ── Recibir (clientes no envían datos) ────────────────────────────────────
    async def receive(self, text_data=None, bytes_data=None):
        pass

    # ── Eventos desde el grupo ────────────────────────────────────────────────
    async def nueva_alerta(self, event):
        """Llamado cuando PacienteCriticoDetector.detectar() crea una alerta nueva."""
        await self.send(text_data=json.dumps({
            "type":   "nueva_alerta",
            "alerta": event["alerta"],
            "count":  event["count"],
        }))

    async def actualizar_conteo(self, event):
        """Llamado cuando cambia el conteo (ej. marcar como vista)."""
        await self.send(text_data=json.dumps({
            "type":  "conteo",
            "count": event["count"],
        }))

    # ── Helpers ───────────────────────────────────────────────────────────────
    async def _token_valido(self) -> bool:
        """Valida el JWT token pasado como query param ?token=<jwt>."""
        qs = self.scope.get("query_string", b"").decode()
        params = {k: v for k, v in
                  (p.split("=", 1) for p in qs.split("&") if "=" in p)}
        token = params.get("token", "")
        if not token:
            return False
        try:
            from rest_framework_simplejwt.tokens import UntypedToken
            UntypedToken(token)
            return True
        except Exception:
            return False

    @database_sync_to_async
    def _get_conteo(self) -> int:
        from .models import Alerta
        return Alerta.objects.filter(fecha_vista__isnull=True).count()

    async def _enviar_conteo(self):
        count = await self._get_conteo()
        await self.send(text_data=json.dumps({"type": "conteo", "count": count}))
