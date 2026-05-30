"""
CSVFormatValidator: valida que un archivo CSV/Excel tenga las columnas
requeridas, tipos básicos correctos y rangos clínicos antes de ejecutar ETL.
"""
from typing import Tuple, List
import pandas as pd

COLUMNAS_REQUERIDAS: List[str] = [
    'id_paciente', 'nombres', 'apellidos', 'edad', 'sexo',
    'peso', 'altura', 'IMC', 'presión_sistólica', 'presión_diastólica',
    'frecuencia_cardiaca', 'glucosa', 'colesterol', 'saturación_oxígeno',
    'temperatura', 'antecedentes_familiares', 'fumador', 'consumo_alcohol',
    'actividad_física', 'diagnóstico_preliminar', 'riesgo_enfermedad', 'fecha_consulta',
]

RANGOS_CRITICOS = {
    'edad':               (0,   130),
    'peso':               (1,   500),
    'altura':             (0.3, 3.0),
    'glucosa':            (10,  800),
    'temperatura':        (25,  45),
    'saturación_oxígeno': (50,  100),
}


class CSVFormatValidator:
    """
    Valida estructura y calidad mínima de un DataFrame antes del ETL.

    Args:
        df: DataFrame leído del archivo CSV/Excel

    Returns:
        Tuple (es_valido: bool, errores: list[str], advertencias: list[str])
    """

    def validate(self, df: pd.DataFrame) -> Tuple[bool, List[str], List[str]]:
        errores: List[str] = []
        advertencias: List[str] = []

        # 1. Verificar columnas requeridas
        columnas_actuales = set(df.columns.tolist())
        columnas_faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in columnas_actuales]
        if columnas_faltantes:
            errores.append(f"Columnas faltantes ({len(columnas_faltantes)}): {', '.join(columnas_faltantes)}")

        # 2. Verificar que el archivo no esté vacío
        if len(df) == 0:
            errores.append("El archivo está vacío (0 registros)")
            return False, errores, advertencias

        # 3. Verificar id_paciente existe y no está todo vacío
        if 'id_paciente' in df.columns:
            nulos_id = df['id_paciente'].isna().sum()
            if nulos_id == len(df):
                errores.append("La columna 'id_paciente' está completamente vacía")
            elif nulos_id > len(df) * 0.5:
                advertencias.append(f"'id_paciente' tiene {nulos_id} valores nulos ({nulos_id/len(df)*100:.0f}%)")

        # 4. Advertir sobre nulos excesivos (>30%) en columnas críticas
        cols_criticas = ['glucosa', 'peso', 'presión_sistólica', 'edad']
        for col in cols_criticas:
            if col not in df.columns:
                continue
            pct_nulos = df[col].isna().mean() * 100
            if pct_nulos > 30:
                advertencias.append(f"'{col}' tiene {pct_nulos:.0f}% de valores nulos (se imputarán)")

        # 5. Verificar rangos críticos donde sea posible
        for col, (lo, hi) in RANGOS_CRITICOS.items():
            if col not in df.columns:
                continue
            numericos = pd.to_numeric(df[col], errors='coerce').dropna()
            if len(numericos) == 0:
                continue
            pct_outlier = ((numericos < lo) | (numericos > hi)).mean() * 100
            if pct_outlier > 20:
                advertencias.append(f"'{col}' tiene {pct_outlier:.0f}% de valores fuera del rango clínico [{lo}, {hi}]")

        # 6. Verificar tamaño mínimo
        if len(df) < 10:
            advertencias.append(f"El archivo tiene solo {len(df)} registros. Se recomienda al menos 100 para análisis estadístico.")

        es_valido = len(errores) == 0
        return es_valido, errores, advertencias
