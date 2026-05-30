from typing import Optional
import re, numpy as np, pandas as pd
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger('etl')

class BaseTransformer(ABC):
    def __init__(self, ejecucion=None, quality_report=None):
        self.ejecucion = ejecucion
        self.qr = quality_report

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame: pass

    def _log(self, msg, campo='', nivel='INFO'):
        logger.info(f"  [{self.__class__.__name__}] {msg}")
        if self.ejecucion:
            from .models import LogETL
            LogETL.objects.create(ejecucion=self.ejecucion, nivel=nivel, mensaje=msg, campo_afectado=campo)


class DuplicateRemover(BaseTransformer):
    """Elimina registros duplicados por id_paciente, conservando el primero."""
    def transform(self, df):
        before = len(df)
        df = df.drop_duplicates(subset=['id_paciente'], keep='first')
        removed = before - len(df)
        if removed:
            self._log(f"Eliminados {removed} registros duplicados", 'id_paciente', 'WARNING')
            if self.qr: self.qr.add_metric('duplicados_eliminados', removed)
        return df.reset_index(drop=True)


class TypeCoercer(BaseTransformer):
    """Convierte columnas a sus tipos correctos. Valores no numéricos (ej. edad='Treinta') → NaN."""
    NUMERIC = {
        'id_paciente':'Int64','edad':'Int64','peso':float,'altura':float,'IMC':float,
        'presión_sistólica':'Int64','presión_diastólica':'Int64','frecuencia_cardiaca':'Int64',
        'glucosa':float,'colesterol':float,'saturación_oxígeno':float,'temperatura':float,
    }
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        errors = 0
        for col, dtype in self.NUMERIC.items():
            if col not in df.columns: continue
            before_nulls = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors='coerce')
            if dtype == 'Int64': df[col] = df[col].astype('Int64')
            new_nulls = int(df[col].isna().sum() - before_nulls)
            if new_nulls > 0:
                errors += new_nulls
                self._log(f"{new_nulls} valores no numéricos → NaN en '{col}'", col, 'WARNING')
        if self.qr: self.qr.add_metric('errores_tipo_corregidos', errors)
        return df


class NullImputer(BaseTransformer):
    """Imputa nulos: mediana para numéricas continuas, mediana entera para enteras, moda para categóricas."""
    MEDIAN_F = ['peso','glucosa','colesterol','temperatura','IMC']
    MEDIAN_I = ['presión_sistólica','presión_diastólica','frecuencia_cardiaca','edad']
    MODE_C   = ['sexo','actividad_física','diagnóstico_preliminar']

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        total = 0
        for col in self.MEDIAN_F:
            if col in df.columns and df[col].isna().any():
                n = int(df[col].isna().sum()); m = df[col].median()
                df[col] = df[col].fillna(m); total += n
                self._log(f"Imputados {n} nulos en '{col}' con mediana={m:.2f}", col)
        for col in self.MEDIAN_I:
            if col in df.columns and df[col].isna().any():
                n = int(df[col].isna().sum()); m = int(df[col].median())
                df[col] = df[col].fillna(m); total += n
                self._log(f"Imputados {n} nulos en '{col}' con mediana={m}", col)
        for col in self.MODE_C:
            if col in df.columns and df[col].isna().any():
                n = int(df[col].isna().sum()); m = df[col].mode()[0]
                df[col] = df[col].fillna(m); total += n
                self._log(f"Imputados {n} nulos en '{col}' con moda='{m}'", col)
        if self.qr: self.qr.add_metric('nulos_imputados', total)
        return df


class OutlierHandler(BaseTransformer):
    """Detecta y reemplaza valores fuera de rangos clínicos válidos con la mediana de la columna."""
    RANGES = {
        'peso':(20,300),'altura':(0.5,2.5),'presión_sistólica':(60,250),
        'presión_diastólica':(40,150),'frecuencia_cardiaca':(30,220),
        'glucosa':(50,600),'colesterol':(50,400),'saturación_oxígeno':(70,100),
        'temperatura':(34,42),'edad':(0,120),
    }
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        total = 0
        for col,(lo,hi) in self.RANGES.items():
            if col not in df.columns: continue
            mask = (df[col] < lo) | (df[col] > hi)
            n = int(mask.sum())
            if n:
                med = df.loc[~mask, col].median()
                df.loc[mask, col] = med; total += n
                self._log(f"{n} outliers en '{col}' [{lo},{hi}] → mediana={med:.2f}", col, 'WARNING')
        if self.qr: self.qr.add_metric('outliers_corregidos', total)
        return df


class DiagnosisNormalizer(BaseTransformer):
    """Estandariza errores ortográficos en diagnóstico_preliminar usando expresiones regulares."""
    MAP = {
        r'(?i)hipertensi[oó]n': 'Hipertensión',
        r'(?i)hipertencion':    'Hipertensión',
        r'(?i)prehipertensi[oó]n': 'Prehipertensión',
        r'(?i)diabetes\s*tipo\s*2': 'Diabetes Tipo 2',
        r'(?i)riesgo\s*cardiovascular': 'Riesgo cardiovascular',
        r'(?i)cardiopat[ií]a':  'Cardiopatía',
        r'(?i)obesidad':        'Obesidad',
        r'(?i)paciente\s*sano': 'Paciente sano',
    }
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = 'diagnóstico_preliminar'
        if col not in df.columns: return df
        orig = df[col].copy()
        for pat, rep in self.MAP.items():
            df[col] = df[col].str.replace(pat, rep, regex=True)
        n = int((df[col] != orig).sum())
        if n: self._log(f"Normalizados {n} diagnósticos con errores ortográficos", col)
        if self.qr: self.qr.add_metric('diagnosticos_normalizados', n)
        return df


class SexNormalizer(BaseTransformer):
    """Normaliza la columna sexo: 'f', 'femenino', 'female' → 'F'; 'm', 'masculino' → 'M'."""
    MAP = {'m':'M','masculino':'M','male':'M','hombre':'M','f':'F','femenino':'F','female':'F','mujer':'F'}
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = 'sexo'
        if col not in df.columns: return df
        orig = df[col].copy()
        df[col] = df[col].str.strip().str.lower().map(self.MAP).fillna('M')
        n = int((df[col] != orig.str.upper().str.strip()).sum())
        if self.qr: self.qr.add_metric('sexo_normalizados', n)
        return df



class ActividadFisicaNormalizer(BaseTransformer):
    """
    Normaliza actividad_física a valores canónicos: Sedentaria / Baja / Media / Alta.
    Acepta variantes: sedentario, sedentaria, ninguna, none → Sedentaria
                      baja, leve, ligera → Baja
                      media, moderada, regular → Media
                      alta, intensiva, intensa, deportista → Alta
    """
    MAP = {
        'sedentario': 'Sedentaria', 'sedentaria': 'Sedentaria',
        'ninguna': 'Sedentaria',    'none': 'Sedentaria', 'nula': 'Sedentaria',
        'sin actividad': 'Sedentaria',
        'baja': 'Baja',  'leve': 'Baja', 'ligera': 'Baja', 'poca': 'Baja',
        'media': 'Media', 'moderada': 'Media', 'regular': 'Media', 'moderado': 'Media',
        'alta': 'Alta', 'intensiva': 'Alta', 'intensa': 'Alta',
        'deportista': 'Alta', 'muy alta': 'Alta', 'elevada': 'Alta',
    }
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        col = 'actividad_física'
        if col not in df.columns: return df
        orig = df[col].copy()
        df[col] = df[col].str.strip().str.lower().map(self.MAP).fillna(df[col])
        n = int((df[col].str.lower() != orig.str.lower()).sum())
        if n: self._log(f"Normalizadas {n} variantes de actividad_física", col)
        if self.qr: self.qr.add_metric('actividad_fisica_normalizados', n)
        return df

class IMCCalculator(BaseTransformer):
    """Recalcula IMC=peso/altura² y clasifica según categorías OMS (Bajo peso/Normal/Sobrepeso/Obesidad)."""
    IMC_LABELS = [
        (18.5, 'Bajo peso'), (25, 'Normal'), (30, 'Sobrepeso'), (float('inf'), 'Obesidad')
    ]
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = df['peso'].notna() & df['altura'].notna() & (df['altura'] > 0)
        df.loc[mask, 'IMC'] = (df.loc[mask,'peso'] / df.loc[mask,'altura']**2).round(2)
        df['clasificacion_imc'] = df['IMC'].apply(self._classify)
        return df

    def _classify(self, imc):
        if pd.isna(imc): return 'Normal'
        for threshold, label in self.IMC_LABELS:
            if imc < threshold: return label
        return 'Obesidad'


class RiskClassifier(BaseTransformer):
    """Clasifica riesgo clínico en Bajo/Medio/Alto/Crítico aplicando reglas médicas sobre múltiples variables."""
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df['riesgo_enfermedad'] = df.apply(self._score, axis=1)
        return df

    @staticmethod
    def _score(r):
        s = 0
        ps = r.get('presión_sistólica', 0) or 0
        g  = r.get('glucosa', 0) or 0
        so = r.get('saturación_oxígeno', 100) or 100
        if ps > 180: s += 3
        elif ps > 140: s += 2
        elif ps > 120: s += 1
        if g > 300: s += 3
        elif g > 200: s += 2
        elif g > 140: s += 1
        if so < 85: s += 3
        elif so < 90: s += 2
        edad = r.get('edad', 0) or 0
        af   = r.get('antecedentes_familiares', False)
        if edad > 70 and af: s += 2
        if r.get('fumador', False): s += 1
        imc = r.get('IMC', 0) or 0
        if imc > 35: s += 1
        if s >= 6: return 'Crítico'
        if s >= 4: return 'Alto'
        if s >= 2: return 'Medio'
        return 'Bajo'
