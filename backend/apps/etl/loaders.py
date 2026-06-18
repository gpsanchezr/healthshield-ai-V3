"""DatabaseLoader: inserta registros limpios del ETL en PostgreSQL/SQLite de forma transaccional."""
import pandas as pd
import logging
from django.db import transaction
from .models import Paciente, RegistroClinico

logger = logging.getLogger('etl')

COL_MAP = {
    'id_paciente':           'id_paciente_original',
    'presión_sistólica':     'presion_sistolica',
    'presión_diastólica':    'presion_diastolica',
    'frecuencia_cardiaca':   'frecuencia_cardiaca',
    'saturación_oxígeno':    'saturacion_oxigeno',
    'actividad_física':      'actividad_fisica',
    'diagnóstico_preliminar':'diagnostico_preliminar',
    'antecedentes_familiares':'antecedentes_familiares',
}

class DatabaseLoader:
    def __init__(self, ejecucion=None):
        self.ejecucion = ejecucion

    @transaction.atomic
    def load(self, df: pd.DataFrame) -> int:
        df = df.rename(columns=COL_MAP)
        loaded = 0
        for _, row in df.iterrows():
            try:
                paciente, _ = Paciente.objects.update_or_create(
                    id_paciente_original=int(row['id_paciente_original']),
                    defaults={
                        'nombres':   str(row.get('nombres', '')),
                        'apellidos': str(row.get('apellidos', '')),
                        'edad':      int(row.get('edad', 0)),
                        'sexo':      str(row.get('sexo', 'M')),
                    }
                )
                RegistroClinico.objects.update_or_create(
                    paciente=paciente,
                    fecha_consulta=pd.to_datetime(
                        row.get('fecha_consulta'), errors='coerce'
                    ).date() if row.get('fecha_consulta') else None,
                    defaults=dict(
                        peso=self._safe(row, 'peso'),
                        altura=self._safe(row, 'altura'),
                        imc=self._safe(row, 'IMC'),
                        clasificacion_imc=str(row.get('clasificacion_imc', '')),
                        presion_sistolica=self._safe_int(row, 'presion_sistolica'),
                        presion_diastolica=self._safe_int(row, 'presion_diastolica'),
                        frecuencia_cardiaca=self._safe_int(row, 'frecuencia_cardiaca'),
                        glucosa=self._safe(row, 'glucosa'),
                        colesterol=self._safe(row, 'colesterol'),
                        saturacion_oxigeno=self._safe(row, 'saturacion_oxigeno'),
                        temperatura=self._safe(row, 'temperatura'),
                        antecedentes_familiares=bool(row.get('antecedentes_familiares', False)),
                        fumador=bool(row.get('fumador', False)),
                        consumo_alcohol=bool(row.get('consumo_alcohol', False)),
                        actividad_fisica=str(row.get('actividad_fisica', '')),
                        diagnostico_preliminar=str(row.get('diagnostico_preliminar', '')),
                        riesgo_enfermedad=str(row.get('riesgo_enfermedad', 'Bajo')),
                        fuente_etl=self.ejecucion,
                    )
                )
                loaded += 1
            except Exception as e:
                logger.warning(f"Error cargando fila {row.get('id_paciente_original')}: {e}")
        logger.info(f"DatabaseLoader: {loaded} registros insertados")
        return loaded

    @staticmethod
    def _safe(row, col):
        v = row.get(col)
        if v is None or (hasattr(v, '__class__') and str(v) == '<NA>'): return None
        try: return float(v)
        except: return None

    @staticmethod
    def _safe_int(row, col):
        v = row.get(col)
        if v is None or (hasattr(v, '__class__') and str(v) == '<NA>'): return None
        try: return int(v)
        except: return None
