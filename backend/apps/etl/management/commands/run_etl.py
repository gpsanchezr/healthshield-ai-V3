from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Ejecuta el pipeline ETL completo'
    def add_arguments(self, parser):
        parser.add_argument('--file', type=str)
        parser.add_argument('--simulate', action='store_true')
        parser.add_argument('--count', type=int, default=50)

    def handle(self, *args, **options):
        from apps.etl.pipeline import ETLPipeline
        from apps.etl.simulation import DataSimulator
        self.stdout.write(self.style.MIGRATE_HEADING('HealthShield AI — ETL Pipeline'))
        if options['simulate']:
            df = DataSimulator().generate(options['count'])
            result = ETLPipeline(tipo='simulacion').run_dataframe(df)
        elif options['file']:
            result = ETLPipeline(tipo='manual').run(options['file'])
        else:
            raise CommandError('Especifica --file o --simulate')
        r = result['report']
        self.stdout.write(self.style.SUCCESS(f"ETL OK en {r['duracion_segundos']}s — {r['despues']['total_registros']} registros — Score: {r['quality_score']} ({r['clasificacion']})"))
