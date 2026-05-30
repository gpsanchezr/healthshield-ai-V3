from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Entrena el modelo de Machine Learning'
    def add_arguments(self, parser):
        parser.add_argument('--algorithm', type=str, default='random_forest',
            choices=['random_forest','logistic_regression','decision_tree'])
    def handle(self, *args, **options):
        import pandas as pd
        from apps.etl.models import RegistroClinico
        from apps.ml.trainer import ModelTrainer
        from apps.ml.models import ModeloML
        qs = RegistroClinico.objects.all().values(
            'imc','presion_sistolica','presion_diastolica','frecuencia_cardiaca',
            'glucosa','colesterol','saturacion_oxigeno','temperatura',
            'fumador','consumo_alcohol','antecedentes_familiares','riesgo_enfermedad','paciente__edad')
        if not qs.exists():
            self.stdout.write(self.style.ERROR('Sin datos. Ejecuta primero: python manage.py run_etl --file ...')); return
        df = pd.DataFrame(list(qs)).rename(columns={'paciente__edad':'edad'})
        self.stdout.write(f"Entrenando con {len(df)} registros...")
        result = ModelTrainer(options['algorithm']).train(df)
        ModeloML.objects.filter(activo=True).update(activo=False)
        ModeloML.objects.create(
            nombre=f"HealthShield {options['algorithm'].replace('_',' ').title()}",
            algoritmo=options['algorithm'], version=f"v{ModeloML.objects.count()+1}",
            accuracy=result['accuracy'], precision_score=result['precision'],
            recall=result['recall'], f1_score=result['f1_score'],
            archivo_modelo=result['model_path'], feature_names=result['features'],
            feature_importance=result['feature_importance'],
            registros_entrenamiento=result['training_samples'], activo=True)
        self.stdout.write(self.style.SUCCESS(f"Modelo entrenado — Accuracy: {result['accuracy']} | F1: {result['f1_score']} | CV: {result['cv_accuracy']}"))
        for f, i in list(result['feature_importance'].items())[:3]:
            self.stdout.write(f"  Top feature: {f} = {i:.4f}")
