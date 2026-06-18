"""
HealthShield AI V4 — ETL Pipeline
==================================
Orquesta la cadena completa:
  Extract → [10 Transformadores] → Load

CORRECCIONES V4.1:
  - NUEVO: ColumnStandardizer insertado tras NullImputer (reglas SENA)
"""

from typing import Optional, Dict, Any
import time
import logging
from datetime import datetime
import pandas as pd

from .extractors import CSVExtractor, ExcelExtractor
from .transformers import (
    DuplicateRemover,
    TypeCoercer,
    NullImputer,
    ColumnStandardizer,          # ← NUEVO (reglas estandarización SENA)
    OutlierHandler,
    DiagnosisNormalizer,
    SexNormalizer,
    ActividadFisicaNormalizer,
    IMCCalculator,
    RiskClassifier,
)
from .loaders import DatabaseLoader
from .quality import DataQualityReport
from .models import EjecucionETL

logger = logging.getLogger('etl')

# ─── Orden del pipeline ───────────────────────────────────────────────────────
# La secuencia importa:
#   1. DuplicateRemover   → eliminar filas repetidas primero
#   2. TypeCoercer        → convertir tipos (texto → número, etc.)
#   3. NullImputer        → imputar nulos antes de estandarizar
#   4. ColumnStandardizer → aplicar reglas SENA (id consecutivo, decimales, etc.)
#   5. OutlierHandler     → corregir valores clínicamente imposibles
#   6. DiagnosisNormalizer→ ortografía + Title Case en diagnósticos
#   7. SexNormalizer      → M / F
#   8. ActividadFísica    → valores canónicos en minúsculas
#   9. IMCCalculator      → recalcular IMC + clasificación OMS
#  10. RiskClassifier     → Bajo / Medio / Alto / Crítico
TRANSFORMERS = [
    DuplicateRemover,
    TypeCoercer,
    NullImputer,
    ColumnStandardizer,          # ← NUEVO
    OutlierHandler,
    DiagnosisNormalizer,
    SexNormalizer,
    ActividadFisicaNormalizer,
    IMCCalculator,
    RiskClassifier,
]


class ETLPipeline:
    def __init__(self, usuario=None, tipo: str = 'manual', dataset_cache=None):
        self.usuario       = usuario
        self.tipo          = tipo
        self.dataset_cache = dataset_cache   # NUEVO V4.2: link al DatasetCache real
        self.ejecucion     = None
        self.qr            = DataQualityReport()

    # ── Entrada: archivo CSV / Excel ─────────────────────────────────────────
    def run(self, source_path: str) -> dict:
        self.ejecucion = EjecucionETL.objects.create(
            usuario=self.usuario,
            archivo_fuente=source_path,
            tipo=self.tipo,
            dataset_cache=self.dataset_cache,
        )
        t0 = time.time()
        try:
            if source_path.endswith(('.xlsx', '.xls')):
                df = ExcelExtractor().extract(source_path)
            else:
                df = CSVExtractor().extract(source_path)
            return self._process(df, t0)
        except Exception as e:
            self.ejecucion.estado = 'fallido'
            self.ejecucion.save()
            logger.error(f"ETL fallido: {e}", exc_info=True)
            raise

    # ── Entrada: DataFrame pre-generado (simulación / reutilización) ─────────
    def run_dataframe(self, df: pd.DataFrame) -> dict:
        self.ejecucion = EjecucionETL.objects.create(
            usuario=self.usuario,
            archivo_fuente='simulacion',
            tipo=self.tipo,
        )
        return self._process(df, time.time())

    # ── Núcleo: Transform + Load ─────────────────────────────────────────────
    def _process(self, df: pd.DataFrame, t0: float) -> dict:
        """
        Ejecuta Transform + Load dentro de una transacción atómica.
        Si cualquier paso falla → rollback completo, BD en estado consistente.
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

        self.ejecucion.fecha_fin             = datetime.now()
        self.ejecucion.duracion_segundos     = round(duration, 3)
        self.ejecucion.registros_procesados  = loaded
        self.ejecucion.registros_rechazados  = len(df_raw) - len(df)
        self.ejecucion.duplicados_eliminados = self.qr._metrics.get('duplicados_eliminados', 0)
        self.ejecucion.nulos_imputados       = self.qr._metrics.get('nulos_imputados', 0)
        self.ejecucion.reporte_calidad       = report
        self.ejecucion.estado                = 'completado'
        self.ejecucion.save()

        logger.info(
            f"[ETL] ✅ Completado en {duration:.2f}s — "
            f"{loaded} registros — score={report['quality_score']}"
        )
        return {
            'status':       'success',
            'ejecucion_id': self.ejecucion.id,
            'report':       report,
        }
