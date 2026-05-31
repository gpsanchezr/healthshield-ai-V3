"""
Tests unitarios del pipeline ETL — HealthShield AI
Ejecutar: pytest tests/test_etl.py -v
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

# Path setup — importar transformers directamente sin Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# ── Stubs para evitar importar Django ORM ──────────────────────────────────────
# Ahora importar los módulos reales
from apps.etl.transformers import (
    DuplicateRemover, TypeCoercer, NullImputer, OutlierHandler,
    DiagnosisNormalizer, SexNormalizer, IMCCalculator, RiskClassifier
)
from apps.etl.quality import DataQualityReport
from apps.etl.simulation import DataSimulator


@pytest.fixture
def df_sucio():
    """Dataset de prueba con los mismos errores que el archivo real."""
    return pd.DataFrame({
        'id_paciente':           [1, 1, 2, 3, 4],
        'nombres':               ['Ana','Ana','Luis','Pedro','María'],
        'apellidos':             ['García','García','Martín','López','Soto'],
        'edad':                  [45, 45, 'Treinta', 60, 35],
        'sexo':                  ['f','f','Masculino','M','Femenino'],
        'peso':                  [70.0, 70.0, None, 420.0, 65.0],
        'altura':                [1.65,1.65,1.75,1.70,1.60],
        'IMC':                   [25.7,25.7,22.0,145.0,25.4],
        'presión_sistólica':     [120,120,'alta',185,110],
        'presión_diastólica':    [80,80,75,100,70],
        'frecuencia_cardiaca':   [72,72,68,90,75],
        'glucosa':               [95.0,95.0,None,350.0,110.0],
        'colesterol':            [200.0,200.0,180.0,230.0,195.0],
        'saturación_oxígeno':    [98.0,98.0,97.0,82.0,99.0],
        'temperatura':           [36.5,36.5,None,37.0,36.8],
        'antecedentes_familiares':[False,False,True,True,False],
        'fumador':               [False,False,False,True,False],
        'consumo_alcohol':       [False,False,True,False,True],
        'actividad_física':      ['Media','Media','Alta','Baja','Media'],
        'diagnóstico_preliminar':['hipertencion','hipertencion','Paciente sano','Hipertensión','Obesidad'],
        'riesgo_enfermedad':     ['Medio','Medio','Bajo','Alto','Bajo'],
        'fecha_consulta':        ['2025-01-01']*5,
    })


# ── DuplicateRemover ───────────────────────────────────────────────────────────
def test_duplicate_remover_elimina_duplicados(df_sucio):
    result = DuplicateRemover().transform(df_sucio.copy())
    assert len(result) == 4

def test_duplicate_remover_ids_unicos(df_sucio):
    result = DuplicateRemover().transform(df_sucio.copy())
    assert result['id_paciente'].is_unique

# ── TypeCoercer ────────────────────────────────────────────────────────────────
def test_typecoercer_edad_string_a_nan(df_sucio):
    df = df_sucio.copy()
    # Convertir edad a object antes para permitir strings
    df['edad'] = df['edad'].astype(object)
    result = TypeCoercer().transform(df)
    val = result.loc[result['id_paciente']==2, 'edad'].values[0]
    assert pd.isna(val) or str(val) == '<NA>'

def test_typecoercer_presion_string_a_nan(df_sucio):
    df = df_sucio.copy()
    df['presión_sistólica'] = df['presión_sistólica'].astype(object)
    result = TypeCoercer().transform(df)
    val = result.loc[result['id_paciente']==2, 'presión_sistólica'].values[0]
    assert pd.isna(val) or str(val) == '<NA>'

# ── NullImputer ────────────────────────────────────────────────────────────────
def test_nullimputer_elimina_nulos_peso(df_sucio):
    df = TypeCoercer().transform(df_sucio.copy())
    result = NullImputer().transform(df)
    assert result['peso'].isna().sum() == 0

def test_nullimputer_elimina_nulos_glucosa(df_sucio):
    df = TypeCoercer().transform(df_sucio.copy())
    result = NullImputer().transform(df)
    assert result['glucosa'].isna().sum() == 0

def test_nullimputer_elimina_nulos_temperatura(df_sucio):
    df = TypeCoercer().transform(df_sucio.copy())
    result = NullImputer().transform(df)
    assert result['temperatura'].isna().sum() == 0

# ── OutlierHandler ────────────────────────────────────────────────────────────
def test_outlierhandler_peso_420_corregido(df_sucio):
    result = OutlierHandler().transform(df_sucio.copy())
    assert float(result['peso'].max()) <= 300

def test_outlierhandler_saturacion_82_corregido(df_sucio):
    result = OutlierHandler().transform(df_sucio.copy())
    assert float(result['saturación_oxígeno'].min()) >= 70

def test_outlierhandler_imc_145_corregido(df_sucio):
    result = OutlierHandler().transform(df_sucio.copy())
    # IMC > 60 es imposible, la mediana es ~25
    valid = result['IMC'].dropna()
    assert float(valid.max()) < 100

# ── DiagnosisNormalizer ───────────────────────────────────────────────────────
def test_diagnorma_hipertencion_corregido(df_sucio):
    result = DiagnosisNormalizer().transform(df_sucio.copy())
    assert 'hipertencion' not in result['diagnóstico_preliminar'].values

def test_diagnorma_hipertension_normalizado(df_sucio):
    result = DiagnosisNormalizer().transform(df_sucio.copy())
    assert 'Hipertensión' in result['diagnóstico_preliminar'].values

# ── SexNormalizer ─────────────────────────────────────────────────────────────
def test_sexnorm_solo_m_f(df_sucio):
    result = SexNormalizer().transform(df_sucio.copy())
    assert set(result['sexo'].unique()).issubset({'M','F'})

# ── IMCCalculator ─────────────────────────────────────────────────────────────
def test_imccalc_formula_correcta():
    df = pd.DataFrame({'peso':[70.0],'altura':[1.65],'IMC':[0.0]})
    result = IMCCalculator().transform(df)
    assert abs(float(result.loc[0,'IMC']) - 25.71) < 0.1

def test_imccalc_clasificaciones():
    df = pd.DataFrame({'peso':[40.0,70.0,82.0,100.0],'altura':[1.70]*4,'IMC':[0.0]*4})
    result = IMCCalculator().transform(df)
    clases = result['clasificacion_imc'].tolist()
    assert 'Bajo peso' in clases
    assert 'Normal' in clases
    assert 'Sobrepeso' in clases
    assert 'Obesidad' in clases

def test_imccalc_columna_existe():
    df = pd.DataFrame({'peso':[70.0],'altura':[1.70],'IMC':[0.0]})
    result = IMCCalculator().transform(df)
    assert 'clasificacion_imc' in result.columns

# ── RiskClassifier ────────────────────────────────────────────────────────────
def test_riskclassifier_critico():
    df = pd.DataFrame({'presión_sistólica':[190],'glucosa':[320],'saturación_oxígeno':[82],
                       'antecedentes_familiares':[True],'fumador':[True],'edad':[75],'IMC':[37.0]})
    result = RiskClassifier().transform(df)
    assert result.loc[0,'riesgo_enfermedad'] == 'Crítico'

def test_riskclassifier_bajo():
    df = pd.DataFrame({'presión_sistólica':[110],'glucosa':[90],'saturación_oxígeno':[98],
                       'antecedentes_familiares':[False],'fumador':[False],'edad':[28],'IMC':[22.0]})
    result = RiskClassifier().transform(df)
    assert result.loc[0,'riesgo_enfermedad'] == 'Bajo'

def test_riskclassifier_valores_validos(df_sucio):
    result = RiskClassifier().transform(df_sucio.copy())
    assert all(v in ['Bajo','Medio','Alto','Crítico'] for v in result['riesgo_enfermedad'])

# ── DataQualityReport ─────────────────────────────────────────────────────────
def test_qr_genera_reporte():
    qr = DataQualityReport()
    df = pd.DataFrame({'a':[1,None,3],'b':[None,2,3]})
    qr.snapshot_before(df)
    qr.add_metric('duplicados_eliminados', 2)
    report = qr.generate(df, df.dropna(), 1.2)
    assert 'quality_score' in report
    assert 'clasificacion' in report
    assert report['antes']['total_registros'] == 3

def test_qr_quality_score_rango():
    qr = DataQualityReport()
    df = pd.DataFrame({'a':[1,2,3,4,5]})
    qr.snapshot_before(df)
    report = qr.generate(df, df, 0.5)
    assert 0 <= report['quality_score'] <= 100

def test_qr_metricas_acumuladas():
    qr = DataQualityReport()
    qr.add_metric('nulos_imputados', 10)
    qr.add_metric('nulos_imputados', 5)
    assert qr._metrics['nulos_imputados'] == 15

# ── DataSimulator ─────────────────────────────────────────────────────────────
def test_simulator_genera_n_registros():
    df = DataSimulator().generate(10)
    assert len(df) >= 10

def test_simulator_columnas_presentes():
    df = DataSimulator().generate(5)
    for col in ['id_paciente','nombres','edad','sexo','glucosa','riesgo_enfermedad']:
        assert col in df.columns

def test_simulator_inyecta_nulos():
    df = DataSimulator(error_rate=0.5).generate(40)
    nulos = df[['peso','glucosa','colesterol','temperatura']].isnull().sum().sum()
    assert nulos > 0

def test_simulator_inyecta_errores_tipo():
    df = DataSimulator(error_rate=0.5).generate(40)
    edad_vals = df['edad'].astype(str).tolist()
    assert any(not v.replace('.','').replace('-','').isdigit() for v in edad_vals)
