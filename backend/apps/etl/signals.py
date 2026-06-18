"""
Señales Django para HealthShield AI — ETL.
Cuando se crea una nueva Alerta, se hace broadcast a todos los clientes
WebSocket conectados en el grupo alertas_broadcast.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='etl.Alerta')
def broadcast_nueva_alerta(sender, instance, created, **kwargs):
    """Dispara un evento WebSocket cada vez que se crea una Alerta nueva."""
    if not created:
        return
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from .models import Alerta

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return    # sin channel layer configurado (tests, etc.)

        count = Alerta.objects.filter(fecha_vista__isnull=True).count()

        alerta_data = {
            "id":              instance.id,
            "nivel_urgencia":  instance.nivel_urgencia,
            "paciente":        instance.paciente_id,
            "paciente_nombre": (
                f"{instance.paciente.nombres} {instance.paciente.apellidos}"
            ),
            "tipo_alerta":     instance.tipo_alerta,
            "fecha_alerta":    (
                instance.fecha_alerta.isoformat()
                if instance.fecha_alerta else None
            ),
        }

        async_to_sync(channel_layer.group_send)(
            "alertas_broadcast",
            {
                "type":   "nueva_alerta",
                "alerta": alerta_data,
                "count":  count,
            },
        )
    except Exception:
        pass   # broadcast es opcional — nunca debe romper el flujo ETL
