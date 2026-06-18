"""
HealthShield AI V4 — Pipeline de Transformadores ETL
=====================================================
Cadena de responsabilidad (Chain of Responsibility):
  DuplicateRemover → TypeCoercer → NullImputer → ColumnStandardizer
  → OutlierHandler → DiagnosisNormalizer → SexNormalizer
  → ActividadFisicaNormalizer → IMCCalculator → RiskClassifier

CORRECCIONES V4.1:
  - FIX #2 SexNormalizer: conteo de normalizados corregido
  - FIX #3 NullImputer: añadidas saturación_oxígeno y altura a imputación
  - FIX #4 RiskClassifier: manejo explícito de pd.NA (Int64 nullable)
  - FIX #6 DiagnosisNormalizer: Title Case aplicado al final
  - NUEVO ColumnStandardizer: aplica todas las reglas del reto SENA
"""

from typing import Optional
import unicodedata
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger('etl')


# ─────────────────────────────────────────────────────────────────────────────
# BASE
# ─────────────────────────────────────────────────────────────────────────────

class BaseTransformer(ABC):
    def __init__(self, ejecucion=None, quality_report=None):
        self.ejecucion = ejecucion
        self.qr = quality_report

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    def _log(self, msg, campo='', nivel='INFO'):
        logger.info(f"  [{self.__class__.__name__}] {msg}")
        if self.ejecucion:
            from .models import LogETL
            LogETL.objects.create(
                ejecucion=self.ejecucion,
                nivel=nivel,
                mensaje=msg,
                campo_afectado=campo,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 1. DUPLICATE REMOVER
# ─────────────────────────────────────────────────────────────────────────────

class DuplicateRemover(BaseTransformer):
    """Elimina registros duplicados por id_paciente, conservando el primero."""

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        before = len(df)
        df = df.drop_duplicates(subset=['id_paciente'], keep='first')
        removed = before - len(df)
        if removed:
            self._log(f"Eliminados {removed} registros duplicados", 'id_paciente', 'WARNING')
            if self.qr:
                self.qr.add_metric('duplicados_eliminados', removed)
        return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. TYPE COERCER
# ─────────────────────────────────────────────────────────────────────────────

class TypeCoercer(BaseTransformer):
    """
    Convierte columnas a sus tipos correctos.
    Valores no numéricos (ej. edad='Treinta', presión='Alta') → NaN.
    """

    NUMERIC = {
        'id_paciente':          'Int64',
        'edad':                 'Int64',
        'peso':                 float,
        'altura':               float,
        'IMC':                  float,
        'presión_sistólica':    'Int64',
        'presión_diastólica':   'Int64',
        'frecuencia_cardiaca':  'Int64',
        'glucosa':              float,
        'colesterol':           float,
        'saturación_oxígeno':   float,
        'temperatura':          float,
    }

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        errors = 0
        for col, dtype in self.NUMERIC.items():
            if col not in df.columns:
                continue
            before_nulls = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if dtype == 'Int64':
                df[col] = df[col].astype('Int64')
            new_nulls = int(df[col].isna().sum() - before_nulls)
            if new_nulls > 0:
                errors += new_nulls
                self._log(
                    f"{new_nulls} valores no numéricos → NaN en '{col}'",
                    col, 'WARNING',
                )
        if self.qr:
            self.qr.add_metric('errores_tipo_corregidos', errors)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. NULL IMPUTER  (FIX #3: añadidas saturación_oxígeno y altura)
# ─────────────────────────────────────────────────────────────────────────────

class NullImputer(BaseTransformer):
    """
    Imputa nulos:
      - Mediana para numéricas continuas (float)
      - Mediana entera para columnas enteras
      - Moda para categóricas
    FIX #3: saturación_oxígeno y altura ahora incluidas en MEDIAN_F.
    """

    # Float: mediana con 2 decimales
    MEDIAN_F = [
        'peso', 'glucosa', 'colesterol', 'temperatura',
        'IMC', 'altura', 'saturación_oxígeno',      # ← FIX: añadidas
    ]
    # Entero: mediana redondeada
    MEDIAN_I = [
        'presión_sistólica', 'presión_diastólica',
        'frecuencia_cardiaca', 'edad',
    ]
    # Categórico: moda
    MODE_C = ['sexo', 'actividad_física', 'diagnóstico_preliminar']

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        total = 0

        for col in self.MEDIAN_F:
            if col in df.columns and df[col].isna().any():
                n = int(df[col].isna().sum())
                m = df[col].median()
                df[col] = df[col].fillna(round(m, 2))
                total += n
                self._log(f"Imputados {n} nulos en '{col}' con mediana={m:.2f}", col)

        for col in self.MEDIAN_I:
            if col in df.columns and df[col].isna().any():
                n = int(df[col].isna().sum())
                m = int(pd.to_numeric(df[col], errors='coerce').median())
                df[col] = df[col].fillna(m)
                total += n
                self._log(f"Imputados {n} nulos en '{col}' con mediana={m}", col)

        for col in self.MODE_C:
            if col in df.columns and df[col].isna().any():
                n = int(df[col].isna().sum())
                m = df[col].mode()[0]
                df[col] = df[col].fillna(m)
                total += n
                self._log(f"Imputados {n} nulos en '{col}' con moda='{m}'", col)

        if self.qr:
            self.qr.add_metric('nulos_imputados', total)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. COLUMN STANDARDIZER  (NUEVO — Reglas del reto SENA)
# ─────────────────────────────────────────────────────────────────────────────

class ColumnStandardizer(BaseTransformer):
    """
    Aplica las reglas de estandarización obligatorias del reto SENA ADSO 2026:

    Paciente:
      - id_paciente → entero, secuencia consecutiva 1..N
      - nombres / apellidos / diagnóstico_preliminar / riesgo_enfermedad → Title Case

    Variables clínicas numéricas:
      - edad / presión_sistólica / presión_diastólica / frecuencia_cardiaca → int
      - peso / altura / IMC / glucosa / colesterol / saturación_oxígeno → float 2 dec.
      - temperatura → float 1 decimal

    Texto y booleanos:
      - antecedentes_familiares / actividad_física → minúsculas
      - fumador / consumo_alcohol → 'true' / 'false' (sin mayúsculas)

    Fechas:
      - fecha_consulta → AAAA-MM-DD (string)
    """

    INT_COLS    = ['edad', 'presión_sistólica', 'presión_diastólica', 'frecuencia_cardiaca']
    FLOAT2_COLS = ['peso', 'altura', 'IMC', 'glucosa', 'colesterol', 'saturación_oxígeno']
    TITLE_COLS  = ['nombres', 'apellidos', 'diagnóstico_preliminar', 'riesgo_enfermedad']
    LOWER_COLS  = ['antecedentes_familiares', 'actividad_física']
    BOOL_COLS   = ['fumador', 'consumo_alcohol']

    _BOOL_TRUE  = {'true', '1', 'yes', 'si', 'sí', 'verdadero'}

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        changes = []

        # ── id_paciente: entero, orden consecutivo ────────────────────────
        if 'id_paciente' in df.columns:
            df['id_paciente'] = pd.to_numeric(df['id_paciente'], errors='coerce')
            df = df.sort_values('id_paciente').reset_index(drop=True)
            df['id_paciente'] = range(1, len(df) + 1)
            changes.append("id_paciente → consecutivo")

        # ── Title Case ────────────────────────────────────────────────────
        for col in self.TITLE_COLS:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.title()
        if any(c in df.columns for c in self.TITLE_COLS):
            changes.append(f"Title Case: {', '.join(c for c in self.TITLE_COLS if c in df.columns)}")

        # ── Enteros ───────────────────────────────────────────────────────
        for col in self.INT_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(0)
                # Convertir a int nativo (no nullable) para compatibilidad Django ORM
                df[col] = df[col].fillna(0).astype(int)
        changes.append("Enteros: edad, presión_sistólica, presión_diastólica, frecuencia_cardiaca")

        # ── Float 2 decimales ─────────────────────────────────────────────
        for col in self.FLOAT2_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').round(2)
        changes.append("Float 2 dec.: peso, altura, IMC, glucosa, colesterol, saturación_oxígeno")

        # ── Temperatura: 1 decimal ────────────────────────────────────────
        if 'temperatura' in df.columns:
            df['temperatura'] = pd.to_numeric(df['temperatura'], errors='coerce').round(1)
            changes.append("temperatura → 1 decimal")

        # ── Minúsculas ────────────────────────────────────────────────────
        for col in self.LOWER_COLS:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
        changes.append("Minúsculas: antecedentes_familiares, actividad_física")

        # ── Booleanos: true / false ───────────────────────────────────────
        for col in self.BOOL_COLS:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .apply(lambda v: 'true' if v in self._BOOL_TRUE else 'false')
                )
        changes.append("Booleanos → true/false minúsculas")

        # ── Fecha: AAAA-MM-DD ─────────────────────────────────────────────
        if 'fecha_consulta' in df.columns:
            df['fecha_consulta'] = (
                pd.to_datetime(df['fecha_consulta'], errors='coerce')
                .dt.strftime('%Y-%m-%d')
            )
            changes.append("fecha_consulta → YYYY-MM-DD")

        msg = "Estandarización SENA aplicada: " + " | ".join(changes)
        self._log(msg, nivel='INFO')
        if self.qr:
            self.qr.add_metric('columnas_estandarizadas', len(changes))

        return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. OUTLIER HANDLER
# ─────────────────────────────────────────────────────────────────────────────

class OutlierHandler(BaseTransformer):
    """
    Detecta y reemplaza valores fuera de rangos clínicos válidos
    con la mediana de la columna.
    """

    RANGES = {
        'peso':               (20,  300),
        'altura':             (0.5, 2.5),
        'presión_sistólica':  (60,  250),
        'presión_diastólica': (40,  150),
        'frecuencia_cardiaca':(30,  220),
        'glucosa':            (50,  600),
        'colesterol':         (50,  400),
        'saturación_oxígeno': (70,  100),
        'temperatura':        (34,   42),
        'edad':               (0,   120),
        'IMC':                (10,   60),
    }

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        total = 0
        for col, (lo, hi) in self.RANGES.items():
            if col not in df.columns:
                continue
            numeric = pd.to_numeric(df[col], errors='coerce')
            mask = (numeric < lo) | (numeric > hi)
            n = int(mask.sum())
            if n:
                med = numeric.loc[~mask].median()
                df.loc[mask, col] = round(med, 2)
                total += n
                self._log(
                    f"{n} outliers en '{col}' [{lo}, {hi}] → mediana={med:.2f}",
                    col, 'WARNING',
                )
        if self.qr:
            self.qr.add_metric('outliers_corregidos', total)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. DIAGNOSIS NORMALIZER  (FIX #6: Title Case al final)
# ─────────────────────────────────────────────────────────────────────────────

class DiagnosisNormalizer(BaseTransformer):
    """
    Estandariza errores ortográficos en diagnóstico_preliminar.
    FIX #6: aplica str.title() al final para garantizar consistencia.

    FIX ADICIONAL (detectado en pruebas con el dataset real):
    el primer enfoque basado en regex con tildes fijas (hipertensi[oó]n)
    NO atrapaba variantes donde la tilde está en otra posición, p.ej.
    'hipertensíon' (tilde en la í en vez de la ó) — typo real presente
    en el dataset. Se cambia a comparación SIN tildes (unicodedata),
    que es robusta ante cualquier variante de acentuación.
    """

    # Claves SIN tildes (minúsculas) → valor final correcto
    MAP = {
        'hipertension':          'Hipertensión',
        'hipertencion':          'Hipertensión',   # variante con 'c'
        'prehipertension':       'Prehipertensión',
        'diabetes tipo 2':       'Diabetes Tipo 2',
        'riesgo cardiovascular': 'Riesgo Cardiovascular',
        'cardiopatia':           'Cardiopatía',
        'obesidad':              'Obesidad',
        'paciente sano':         'Paciente Sano',
    }

    @staticmethod
    def _sin_tildes(texto: str) -> str:
        """Quita tildes/diacríticos para comparar sin importar dónde caiga el acento."""
        nfkd = unicodedata.normalize('NFD', texto)
        return ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = 'diagnóstico_preliminar'
        if col not in df.columns:
            return df

        orig = df[col].copy()

        def _normalizar(valor):
            if pd.isna(valor):
                return valor
            clave = self._sin_tildes(str(valor).strip().lower())
            return self.MAP.get(clave, str(valor).strip())

        df[col] = df[col].apply(_normalizar)

        # FIX #6: garantizar Title Case en todos los diagnósticos (incl. los no mapeados)
        df[col] = df[col].astype(str).str.strip().str.title()

        n = int((df[col] != orig).sum())
        if n:
            self._log(f"Normalizados {n} diagnósticos (ortografía + tildes + Title Case)", col)
        if self.qr:
            self.qr.add_metric('diagnosticos_normalizados', n)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 7. SEX NORMALIZER  (FIX #2: conteo de normalizados corregido)
# ─────────────────────────────────────────────────────────────────────────────

class SexNormalizer(BaseTransformer):
    """
    Normaliza la columna sexo:
      'f', 'femenino', 'female', 'mujer' → 'F'
      'm', 'masculino', 'male', 'hombre' → 'M'
    FIX #2: conteo de normalizados ahora compara valores originales vs resultado.
    """

    MAP = {
        'm':         'M',
        'masculino': 'M',
        'male':      'M',
        'hombre':    'M',
        'f':         'F',
        'femenino':  'F',
        'female':    'F',
        'mujer':     'F',
    }

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = 'sexo'
        if col not in df.columns:
            return df

        # FIX #2: guardar original en formato comparable ANTES de transformar
        orig_normalized = df[col].astype(str).str.strip().str.upper()

        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(self.MAP)
            .fillna('M')
        )

        # FIX #2: comparar resultado contra valores originales en mayúsculas (M/F)
        # Sólo se cuenta como "normalizado" si el valor original NO era ya 'M' o 'F'
        n = int((~orig_normalized.isin(['M', 'F'])).sum())
        self._log(f"Normalizados {n} valores de sexo a M/F", col)
        if self.qr:
            self.qr.add_metric('sexo_normalizados', n)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 8. ACTIVIDAD FÍSICA NORMALIZER
# ─────────────────────────────────────────────────────────────────────────────

class ActividadFisicaNormalizer(BaseTransformer):
    """
    Normaliza actividad_física a valores canónicos en minúsculas:
    sedentario / baja / media / alta
    """

    MAP = {
        'sedentario':   'sedentario', 'sedentaria':  'sedentario',
        'ninguna':      'sedentario', 'none':        'sedentario',
        'nula':         'sedentario', 'sin actividad':'sedentario',
        'baja':         'baja',       'leve':        'baja',
        'ligera':       'baja',       'poca':        'baja',
        'media':        'media',      'moderada':    'media',
        'regular':      'media',      'moderado':    'media',
        'alta':         'alta',       'intensiva':   'alta',
        'intensa':      'alta',       'deportista':  'alta',
        'muy alta':     'alta',       'elevada':     'alta',
    }

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = 'actividad_física'
        if col not in df.columns:
            return df

        orig = df[col].copy()
        df[col] = (
            df[col]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(self.MAP)
            .fillna(df[col].str.strip().str.lower())
        )

        n = int((df[col].str.lower() != orig.str.lower()).sum())
        if n:
            self._log(f"Normalizadas {n} variantes de actividad_física", col)
        if self.qr:
            self.qr.add_metric('actividad_fisica_normalizados', n)
        return df


# ─────────────────────────────────────────────────────────────────────────────
# 9. IMC CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

class IMCCalculator(BaseTransformer):
    """
    Recalcula IMC = peso / altura² y asigna clasificación OMS.
    Añade columna 'clasificacion_imc' al DataFrame.
    """

    IMC_LABELS = [
        (18.5, 'Bajo Peso'),
        (25.0, 'Normal'),
        (30.0, 'Sobrepeso'),
        (float('inf'), 'Obesidad'),
    ]

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = (
            df['peso'].notna()
            & df['altura'].notna()
            & (pd.to_numeric(df['altura'], errors='coerce') > 0)
        )
        peso   = pd.to_numeric(df.loc[mask, 'peso'],   errors='coerce')
        altura = pd.to_numeric(df.loc[mask, 'altura'], errors='coerce')
        df.loc[mask, 'IMC'] = (peso / altura ** 2).round(2)
        df['clasificacion_imc'] = df['IMC'].apply(self._classify)
        return df

    def _classify(self, imc) -> str:
        try:
            val = float(imc)
        except (TypeError, ValueError):
            return 'Normal'
        if pd.isna(val):
            return 'Normal'
        for threshold, label in self.IMC_LABELS:
            if val < threshold:
                return label
        return 'Obesidad'


# ─────────────────────────────────────────────────────────────────────────────
# 10. RISK CLASSIFIER  (FIX #4: manejo de pd.NA)
# ─────────────────────────────────────────────────────────────────────────────

class RiskClassifier(BaseTransformer):
    """
    Clasifica riesgo clínico: Bajo / Medio / Alto / Crítico.
    FIX #4: todos los campos pasan por _num() para manejar pd.NA (dtype Int64).
    """

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df['riesgo_enfermedad'] = df.apply(self._score, axis=1)
        return df

    @staticmethod
    def _score(r) -> str:
        s = 0
        ps  = RiskClassifier._num(r.get('presión_sistólica'), 0)   # FIX #4
        g   = RiskClassifier._num(r.get('glucosa'),            0)   # FIX #4
        so  = RiskClassifier._num(r.get('saturación_oxígeno'), 100) # FIX #4
        edad = RiskClassifier._num(r.get('edad'),              0)   # FIX #4
        imc  = RiskClassifier._num(r.get('IMC'),               0)   # FIX #4

        # Reglas de presión sistólica
        if ps > 180:   s += 3
        elif ps > 140: s += 2
        elif ps > 120: s += 1

        # Reglas de glucosa
        if g > 300:   s += 3
        elif g > 200: s += 2
        elif g > 140: s += 1

        # Reglas de saturación de oxígeno
        if so < 85:   s += 3
        elif so < 90: s += 2

        # Factores de riesgo adicionales
        af = r.get('antecedentes_familiares', False)
        af_bool = str(af).strip().lower() in ('true', '1', 'yes', 'si', 'sí')
        if edad > 70 and af_bool:
            s += 2

        fumador = r.get('fumador', False)
        if str(fumador).strip().lower() in ('true', '1', 'yes', 'si', 'sí'):
            s += 1

        if imc > 35:
            s += 1

        if s >= 6:   return 'Crítico'
        if s >= 4:   return 'Alto'
        if s >= 2:   return 'Medio'
        return 'Bajo'

    @staticmethod
    def _num(value, default=0) -> float:
        """FIX #4: convierte pd.NA, np.nan o strings no numéricos a default."""
        if value is None:
            return float(default)
        try:
            # pd.NA no es comparable directamente; isna() lo detecta
            if pd.isna(value):
                return float(default)
        except (TypeError, ValueError):
            pass
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
