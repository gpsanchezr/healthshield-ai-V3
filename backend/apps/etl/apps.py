from django.apps import AppConfig


class EtlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.etl'
    verbose_name = 'ETL Pipeline'

    def ready(self):
        import apps.etl.signals  # noqa: F401 — registra señales al iniciar Django
