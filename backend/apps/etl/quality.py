from typing import Dict, Any
from datetime import datetime
import pandas as pd

class DataQualityReport:
    def __init__(self):
        self._metrics = {}
        self._before = {}

    def snapshot_before(self, df: pd.DataFrame):
        self._before = {
            'total_registros': len(df),
            'total_nulos': int(df.isnull().sum().sum()),
            'nulos_por_columna': {k: int(v) for k, v in df.isnull().sum().items() if v > 0},
        }

    def add_metric(self, key: str, value):
        self._metrics[key] = self._metrics.get(key, 0) + value

    def generate(self, df_raw, df_clean, duration) -> dict:
        total_raw = len(df_raw)
        total_clean = len(df_clean)
        rechazados = total_raw - total_clean
        score = max(0, round(100 - (rechazados / max(total_raw,1) * 100) - min(self._metrics.get('errores_tipo_corregidos',0)*0.1, 20), 2))
        return {
            'generado_en': datetime.now().isoformat(),
            'duracion_segundos': round(duration, 3),
            'antes': self._before,
            'despues': {'total_registros': total_clean, 'total_nulos': int(df_clean.isnull().sum().sum())},
            'acciones_correctivas': self._metrics,
            'registros_rechazados': rechazados,
            'porcentaje_recuperados': round(total_clean / max(total_raw,1) * 100, 2),
            'porcentaje_rechazados':  round(rechazados / max(total_raw,1) * 100, 2),
            'quality_score': score,
            'clasificacion': 'Excelente' if score>=90 else 'Buena' if score>=75 else 'Aceptable' if score>=60 else 'Deficiente',
        }
