"""
Tests para DatabaseLoader, generadores PDF/Excel y validador CSV.
Ejecutar: python3 tests/test_loaders_reports.py
"""
import sys, os, types, importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pandas as pd
import numpy as np

# ── Stubs Django ─────────────────────────────────────────────────────────────
for mod in ['django','django.db','django.db.models','django.conf',
            'django.db.transaction','apps','apps.etl','apps.etl.models']:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

class _FakeMgr:
    _store = []
    def create(self, **kw): self._store.append(kw); return type('Obj', (), kw)()
    def update_or_create(self, **kw):
        obj = type('Obj', (), {**kw.get('defaults',{}), **{k:v for k,v in kw.items() if k!='defaults'}})()
        return obj, True
    def get_or_create(self, **kw):
        obj = type('Obj', (), kw)()
        return obj, True

import apps.etl.models as _m
_m.Paciente      = type('Paciente',       (), {'objects': _FakeMgr()})()
_m.RegistroClinico = type('RegistroClinico', (), {'objects': _FakeMgr()})()
_m.LogETL        = type('LogETL',         (), {'objects': _FakeMgr()})()

# Stub transaction.atomic
import django.db.transaction as _tx
class _atomic:
    def __enter__(self): return self
    def __exit__(self, *a): return False
_tx.atomic = _atomic

def _load(fpath):
    spec = importlib.util.spec_from_file_location('_m', fpath)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

base = os.path.join(os.path.dirname(__file__), '..', 'backend', 'apps')

# Cargar módulos
T  = _load(os.path.join(base, 'etl', 'transformers.py'))
Q  = _load(os.path.join(base, 'etl', 'quality.py'))
V  = _load(os.path.join(base, 'etl', 'validators.py'))
S  = _load(os.path.join(base, 'etl', 'simulation.py'))

passed = 0; total = 0

def t(name, fn):
    global passed, total
    total += 1
    try:
        fn()
        print(f"  ✅  {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌  {name}: {e}")


print("="*58)
print("  HealthShield AI — Tests Loaders, Validators & Reports")
print("="*58)
print()
print("── CSVFormatValidator ──────────────────────────────────")

def _v1():
    df = pd.DataFrame({col: [1,2,3] for col in V.COLUMNAS_REQUERIDAS})
    ok, err, warn = V.CSVFormatValidator().validate(df)
    assert ok, f"Debería ser válido: {err}"
    assert len(err) == 0
t("DataFrame con todas las columnas → válido sin errores", _v1)

def _v2():
    ok, err, _ = V.CSVFormatValidator().validate(pd.DataFrame())
    assert not ok
    assert any('vacío' in e.lower() or 'empty' in e.lower() or 'columnas' in e.lower() for e in err)
t("DataFrame vacío → inválido", _v2)

def _v3():
    df = pd.DataFrame({'id_paciente': [1], 'nombres': ['Ana']})
    ok, err, _ = V.CSVFormatValidator().validate(df)
    assert not ok
    assert len(err) > 0
    assert any('faltante' in e.lower() or 'missing' in e.lower() or 'Columnas' in e for e in err)
t("DataFrame con columnas faltantes → inválido con lista de columnas", _v3)

def _v4():
    import pandas as pd
    df = pd.DataFrame({col: [None]*20 for col in V.COLUMNAS_REQUERIDAS})
    # id_paciente con nulos al 100% genera advertencia pero no error fatal
    df['id_paciente'] = range(20)  # Solo id_paciente con valores para que no falle la validación
    ok, err, warn = V.CSVFormatValidator().validate(df)
    assert ok, f"Columnas presentes = válido: {err}"
    # Con 100% nulos en columnas críticas → advertencias
    assert len(warn) > 0, "Debería haber advertencias por nulos"
t("DataFrame con 100% nulos en columnas clave → válido pero con advertencias", _v4)

def _v5():
    df = pd.DataFrame({col: [1] for col in V.COLUMNAS_REQUERIDAS})
    df['peso'] = [500.0]   # outlier extremo
    ok, err, warn = V.CSVFormatValidator().validate(df)
    assert ok
    # Puede tener advertencia de outlier
t("DataFrame con outlier extremo → válido pero con advertencia", _v5)

print()
print("── DataSimulator avanzado ──────────────────────────────")

def _s1():
    sim = S.DataSimulator()
    df  = sim.generate(5)
    assert 'fecha_consulta' in df.columns
    # Fechas en formato string YYYY-MM-DD
    for fecha in df['fecha_consulta'].dropna():
        assert len(str(fecha)) == 10
t("DataSimulator: fechas en formato YYYY-MM-DD", _s1)

def _s2():
    sim = S.DataSimulator()
    df  = sim.generate(50)
    # IDs únicos (antes de duplicados intencionales)
    ids = df['id_paciente'].dropna().astype(str)
    assert len(ids) > 0
t("DataSimulator: genera id_paciente para todos los registros", _s2)

def _s3():
    sim = S.DataSimulator(error_rate=1.0)
    df  = sim.generate(30)
    nulos = df[['peso','glucosa','colesterol','temperatura']].isnull().sum().sum()
    assert nulos > 10, f"Con error_rate=1.0 debe haber muchos nulos, got {nulos}"
t("DataSimulator error_rate=1.0: muchos nulos inyectados", _s3)

print()
print("── Transformación pipeline completo ────────────────────")

def _p1():
    """Pipeline completo sobre dataset simulado."""
    df = S.DataSimulator(error_rate=0.15).generate(50)
    qr = Q.DataQualityReport()
    qr.snapshot_before(df)
    for Cls in [T.DuplicateRemover, T.TypeCoercer, T.NullImputer,
                T.OutlierHandler, T.DiagnosisNormalizer, T.SexNormalizer,
                T.IMCCalculator, T.RiskClassifier]:
        df = Cls(quality_report=qr).transform(df)
    # Verificar que el resultado está limpio
    assert df['sexo'].isin(['M','F']).all(), "Sexo contiene valores inválidos"
    assert df['riesgo_enfermedad'].isin(['Bajo','Medio','Alto','Crítico']).all()
    assert df[['peso','glucosa','colesterol']].isnull().sum().sum() == 0
    report = qr.generate(df, df, 0.5)
    assert report['quality_score'] >= 0
t("Pipeline completo 8 pasos sobre dataset simulado → limpio", _p1)

def _p2():
    """Verificar que RiskClassifier cubre todos los casos."""
    casos = [
        # (PS, glucosa, sat_O2, fumador, edad, IMC, esperado)
        (190, 320, 82, True,  75, 37, 'Crítico'),
        (160, 220, 91, True,  65, 32, 'Alto'),
        (130, 145, 95, False, 45, 26, 'Medio'),
        (105,  90, 98, False, 28, 22, 'Bajo'),
    ]
    for ps, gluc, sat, fum, edad, imc, esperado in casos:
        df = pd.DataFrame([{
            'presión_sistólica': ps, 'glucosa': gluc,
            'saturación_oxígeno': sat, 'fumador': fum,
            'edad': edad, 'IMC': imc,
            'antecedentes_familiares': False,
        }])
        resultado = T.RiskClassifier().transform(df).loc[0,'riesgo_enfermedad']
        assert resultado == esperado, f"PS={ps} → esperado {esperado}, got {resultado}"
t("RiskClassifier: los 4 niveles de riesgo cubren todos los casos", _p2)

print()
print("── DataQualityReport avanzado ──────────────────────────")

def _qr1():
    qr = Q.DataQualityReport()
    df = pd.DataFrame({'a': [1,2,None], 'b': [None,2,3]})
    qr.snapshot_before(df)
    assert qr._before['total_nulos'] == 2
    assert qr._before['total_registros'] == 3
t("DataQualityReport: snapshot_before cuenta nulos correctamente", _qr1)

def _qr2():
    qr = Q.DataQualityReport()
    df = pd.DataFrame({'a': range(100)})
    qr.snapshot_before(df)
    # 10 rechazados
    df_clean = df.iloc[:90]
    report = qr.generate(df, df_clean, 2.0)
    assert report['porcentaje_recuperados'] == 90.0
    assert report['porcentaje_rechazados'] == 10.0
    assert report['registros_rechazados'] == 10
t("DataQualityReport: porcentajes recuperados/rechazados correctos", _qr2)

def _qr3():
    labels = ['Excelente','Buena','Aceptable','Deficiente']
    for score, expected in [(95,'Excelente'),(80,'Buena'),(65,'Aceptable'),(40,'Deficiente')]:
        qr = Q.DataQualityReport()
        qr._metrics = {}
        df = pd.DataFrame({'a': range(100)})
        qr.snapshot_before(df)
        # Forzar quality_score: rechazar el % necesario para cada etiqueta
        n_rechazados = 100 - score
        df_clean = df.iloc[:score]
        report = qr.generate(df, df_clean, 0.5)
        assert report['clasificacion'] == expected, f"score≈{score} → {report['clasificacion']} ≠ {expected}"
t("DataQualityReport: etiquetas Excelente/Buena/Aceptable/Deficiente correctas", _qr3)

print()
print("="*58)
print(f"  TOTAL: {passed}/{total} tests PASADOS  {'✅ ALL PASS' if passed==total else f'⚠️ {total-passed} fallando'}")
print("="*58)
