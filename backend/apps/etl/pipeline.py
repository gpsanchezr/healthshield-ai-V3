from typing import Optional, Dict, Any
import time, logging
from datetime import datetime
import pandas as pd
from .extractors import CSVExtractor, ExcelExtractor
from .transformers import (DuplicateRemover, TypeCoercer, NullImputer,
    OutlierHandler, DiagnosisNormalizer, SexNormalizer, ActividadFisicaNormalizer,
    IMCCalculator, RiskClassifier)
from .loaders import DatabaseLoader
from .quality import DataQualityReport
from .models import EjecucionETL

logger = logging.getLogger('etl')

TRANSFORMERS = [DuplicateRemover, TypeCoercer, NullImputer, OutlierHandler,
                DiagnosisNormalizer, SexNormalizer, ActividadFisicaNormalizer,
                IMCCalculator, RiskClassifier]

class ETLPipeline:
    def __init__(self, usuario=None, tipo='manual'):
        self.usuario = usuario
        self.tipo = tipo
        self.ejecucion = None
        self.qr = DataQualityReport()

    def run(self, source_path: str) -> dict:
        self.ejecucion = EjecucionETL.objects.create(usuario=self.usuario, archivo_fuente=source_path, tipo=self.tipo)
        t0 = time.time()
        try:
            df = ExcelExtractor().extract(source_path) if source_path.endswith(('.xlsx','.xls')) else CSVExtractor().extract(source_path)
            return self._process(df, t0)
        except Exception as e:
            self.ejecucion.estado = 'fallido'; self.ejecucion.save()
            logger.error(f"ETL fallido: {e}", exc_info=True); raise

    def run_dataframe(self, df: pd.DataFrame) -> dict:
        self.ejecucion = EjecucionETL.objects.create(usuario=self.usuario, archivo_fuente='simulacion', tipo=self.tipo)
        return self._process(df, time.time())

    def _process(self, df: pd.DataFrame, t0: float) -> dict:
        """
        Ejecuta Transform + Load dentro de una transacción atómica.
        Si cualquier paso falla, se hace rollback completo y la BD
        queda en estado consistente (sin datos a medias).
        """
        from django.db import transaction

        self.ejecucion.registros_extraidos = len(df)
        self.ejecucion.save(update_fields=['registros_extraidos'])
        self.qr.snapshot_before(df)

        # ── TRANSFORM (fuera de transacción — no toca BD) ─────────────────
        df_raw = df.copy()
        for TransformerClass in TRANSFORMERS:
            df = TransformerClass(
                ejecucion=self.ejecucion,
                quality_report=self.qr,
            ).transform(df)

        # ── LOAD (dentro de transacción atómica) ──────────────────────────
        try:
            with transaction.atomic():
                loaded = DatabaseLoader(self.ejecucion).load(df)
        except Exception as exc:
            self.ejecucion.estado = 'fallido'
            self.ejecucion.save(update_fields=['estado'])
            logger.error(f"[ETL] LOAD falló — rollback completo: {exc}", exc_info=True)
            raise

        duration = time.time() - t0
        report   = self.qr.generate(df_raw, df, duration)

        self.ejecucion.fecha_fin              = datetime.now()
        self.ejecucion.duracion_segundos      = round(duration, 3)
        self.ejecucion.registros_procesados   = loaded
        self.ejecucion.registros_rechazados   = len(df_raw) - len(df)
        self.ejecucion.duplicados_eliminados  = self.qr._metrics.get('duplicados_eliminados', 0)
        self.ejecucion.nulos_imputados        = self.qr._metrics.get('nulos_imputados', 0)
        self.ejecucion.reporte_calidad        = report
        self.ejecucion.estado                 = 'completado'
        self.ejecucion.save()

        logger.info(f"[ETL] ✅ Completado en {duration:.2f}s — {loaded} registros — score={report['quality_score']}")
        return {'status': 'success', 'ejecucion_id': self.ejecucion.id, 'report': report}
