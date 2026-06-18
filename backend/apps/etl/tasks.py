"""
Celery tasks para el módulo ETL.
Permite ejecutar el pipeline ETL y la simulación en background,
con seguimiento de progreso en tiempo real.
"""
from typing import Optional
from celery import shared_task
import logging

logger = logging.getLogger('etl')


@shared_task(bind=True, name='etl.run_pipeline')
def run_etl_task(
    self,
    source_path: str,
    usuario_id: Optional[int] = None,
    tipo: str = 'manual',
) -> dict:
    """
    Ejecuta el pipeline ETL completo de forma asíncrona.

    Args:
        source_path: Ruta al archivo CSV/Excel
        usuario_id:  ID del usuario que lanzó la tarea
        tipo:        'manual' | 'simulacion' | 'automatico'

    Returns:
        Resultado del ETL con report de calidad
    """
    self.update_state(state='PROGRESS', meta={'paso': 'Extrayendo datos...', 'progreso': 10})

    from apps.etl.pipeline import ETLPipeline
    from apps.authentication.models import UsuarioClinico

    usuario = None
    if usuario_id:
        try:
            usuario = UsuarioClinico.objects.get(pk=usuario_id)
        except UsuarioClinico.DoesNotExist:
            pass

    self.update_state(state='PROGRESS', meta={'paso': 'Transformando datos...', 'progreso': 40})

    try:
        pipeline = ETLPipeline(usuario=usuario, tipo=tipo)
        result   = pipeline.run(source_path)
        self.update_state(state='PROGRESS', meta={'paso': 'Cargando a base de datos...', 'progreso': 90})
        return result
    except Exception as exc:
        logger.error(f"ETL Task failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=5, max_retries=0)


@shared_task(bind=True, name='etl.simulate')
def simulate_etl_task(
    self,
    count: int = 50,
    usuario_id: Optional[int] = None,
) -> dict:
    """
    Genera datos sintéticos y ejecuta ETL asíncronamente.

    Args:
        count:      Número de registros a simular
        usuario_id: ID del usuario administrador
    """
    self.update_state(state='PROGRESS', meta={'paso': f'Generando {count} registros sintéticos...', 'progreso': 20})

    from apps.etl.simulation import DataSimulator
    from apps.etl.pipeline import ETLPipeline
    from apps.authentication.models import UsuarioClinico

    usuario = None
    if usuario_id:
        try:
            usuario = UsuarioClinico.objects.get(pk=usuario_id)
        except UsuarioClinico.DoesNotExist:
            pass

    df = DataSimulator().generate(count)
    self.update_state(state='PROGRESS', meta={'paso': 'Ejecutando ETL...', 'progreso': 60})

    pipeline = ETLPipeline(usuario=usuario, tipo='simulacion')
    result   = pipeline.run_dataframe(df)
    return result


@shared_task(name='ml.train_model')
def train_model_task(algorithm: str = 'random_forest') -> dict:
    """Entrena el modelo ML de forma asíncrona."""
    import pandas as pd
    from apps.etl.models import RegistroClinico
    from apps.ml.trainer import ModelTrainer
    from apps.ml.models import ModeloML

    qs = RegistroClinico.objects.all().values(
        'imc', 'presion_sistolica', 'presion_diastolica', 'frecuencia_cardiaca',
        'glucosa', 'colesterol', 'saturacion_oxigeno', 'temperatura',
        'fumador', 'consumo_alcohol', 'antecedentes_familiares',
        'riesgo_enfermedad', 'paciente__edad',
    )
    df = pd.DataFrame(list(qs)).rename(columns={'paciente__edad': 'edad'})
    result = ModelTrainer(algorithm).train(df)

    ModeloML.objects.filter(activo=True).update(activo=False)
    ModeloML.objects.create(
        nombre=f"HealthShield {algorithm.replace('_',' ').title()} (async)",
        algoritmo=algorithm, version=f"v{ModeloML.objects.count()+1}",
        accuracy=result['accuracy'], precision_score=result['precision'],
        recall=result['recall'], f1_score=result['f1_score'],
        archivo_modelo=result['model_path'], feature_names=result['features'],
        feature_importance=result['feature_importance'],
        registros_entrenamiento=result['training_samples'], activo=True,
    )
    return result


@shared_task(name='etl.detectar_criticos')
def detectar_criticos_task() -> dict:
    """Tarea periódica: detecta pacientes críticos y genera alertas automáticamente."""
    from apps.analytics.calculators import PacienteCriticoDetector
    n = PacienteCriticoDetector().detectar()
    return {'alertas_creadas': n}


@shared_task(name='analytics.snapshot_diario')
def snapshot_analitico_task() -> dict:
    """Tarea periódica: guarda un snapshot de KPIs para tendencias históricas."""
    from apps.analytics.calculators import KPICalculator
    from apps.analytics.models import SnapshotAnalitico
    kpis = KPICalculator().get_all_kpis()
    snap = SnapshotAnalitico.objects.create(
        total_registros       = kpis.get('total_registros', 0),
        pacientes_criticos    = kpis.get('pacientes_criticos', 0),
        pacientes_alto        = kpis.get('pacientes_alto_riesgo', 0),
        pacientes_hipertensos = kpis.get('pacientes_hipertensos', 0),
        pacientes_diabeticos  = kpis.get('pacientes_diabeticos', 0),
        promedio_imc          = kpis.get('promedio_imc'),
        promedio_glucosa      = kpis.get('promedio_glucosa'),
    )
    return {'snapshot_id': snap.id, 'fecha': str(snap.fecha)}
