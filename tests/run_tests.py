"""
Suite completa de tests unitarios — HealthShield AI
NO requiere Django ni base de datos (tests ETL + ML).
Para tests de API usa: python3 tests/test_api.py

Ejecutar: python3 tests/run_tests.py
"""
import sys, os, types, importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
import pandas as pd, numpy as np

# ── Stub Django ────────────────────────────────────────────────────────────────
for mod in ['django','django.db','django.db.models','django.conf',
            'apps','apps.etl','apps.etl.models','apps.ml','apps.ml.models']:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

import apps.etl.models as _etl_m
class _Mgr:
    def create(self, **kw): pass
_etl_m.LogETL = type('LogETL', (), {'objects': _Mgr()})()

class _Settings:
    ML_MODELS_PATH = '/tmp/hs_ml_test'
sys.modules['django.conf'].settings = _Settings()
os.makedirs('/tmp/hs_ml_test', exist_ok=True)

def _load(fpath):
    spec = importlib.util.spec_from_file_location("_m", fpath)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

BASE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'apps')
T  = _load(os.path.join(BASE, 'etl', 'transformers.py'))
Q  = _load(os.path.join(BASE, 'etl', 'quality.py'))
S  = _load(os.path.join(BASE, 'etl', 'simulation.py'))
Tr = _load(os.path.join(BASE, 'ml',  'trainer.py'))
# Inject FEATURES so predictor can find it without package resolution
import builtins
_real_import = builtins.__import__
def _mock_import(name, *args, **kwargs):
    if name in ('apps.ml.trainer',):
        return Tr
    return _real_import(name, *args, **kwargs)
builtins.__import__ = _mock_import
Pr = _load(os.path.join(BASE, 'ml',  'predictor.py'))
builtins.__import__ = _real_import

passed = 0; total = 0; _model_path = [None]

def t(name, fn):
    global passed, total
    total += 1
    try:
        fn()
        print(f"  ✅  {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌  {name}: {e}")

def make_df():
    return pd.DataFrame({
        'id_paciente':     [1, 1, 2, 3, 4],
        'nombres':         ['Ana','Ana','Luis','Pedro','María'],
        'apellidos':       ['G','G','M','L','S'],
        'edad':            pd.array([45, 45, 'Treinta', 60, 35], dtype=object),
        'sexo':            ['f','f','Masculino','M','Femenino'],
        'peso':            [70.0, 70.0, None, 420.0, 65.0],
        'altura':          [1.65, 1.65, 1.75, 1.70, 1.60],
        'IMC':             [25.7, 25.7, 22.0, 145.0, 25.4],
        'presión_sistólica':   pd.array([120, 120, 'alta', 185, 110], dtype=object),
        'presión_diastólica':  [80, 80, 75, 100, 70],
        'frecuencia_cardiaca': [72, 72, 68, 90, 75],
        'glucosa':         [95.0, 95.0, None, 350.0, 110.0],
        'colesterol':      [200.0, 200.0, 180.0, 230.0, 195.0],
        'saturación_oxígeno':  [98.0, 98.0, 97.0, 82.0, 99.0],
        'temperatura':     [36.5, 36.5, None, 37.0, 36.8],
        'antecedentes_familiares': [False, False, True, True, False],
        'fumador':         [False, False, False, True, False],
        'consumo_alcohol': [False, False, True, False, True],
        'actividad_física': ['Media','Media','Alta','Baja','Media'],
        'diagnóstico_preliminar': ['hipertencion','hipertencion','Paciente sano','Hipertensión','Obesidad'],
        'riesgo_enfermedad': ['Medio','Medio','Bajo','Alto','Bajo'],
        'fecha_consulta':  ['2025-01-01']*5,
    })

def make_ml_df(n=250):
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        'edad': rng.integers(18,85,n), 'imc': rng.uniform(16,45,n),
        'presion_sistolica': rng.integers(80,200,n),
        'presion_diastolica': rng.integers(50,130,n),
        'frecuencia_cardiaca': rng.integers(50,120,n),
        'glucosa': rng.uniform(70,350,n), 'colesterol': rng.uniform(120,350,n),
        'saturacion_oxigeno': rng.uniform(85,100,n),
        'temperatura': rng.uniform(36,39,n),
        'fumador': rng.integers(0,2,n),
        'consumo_alcohol': rng.integers(0,2,n),
        'antecedentes_familiares': rng.integers(0,2,n),
    })
    def clf(r):
        s = (3 if r['presion_sistolica']>180 else 2 if r['presion_sistolica']>140 else 1 if r['presion_sistolica']>120 else 0) + \
            (3 if r['glucosa']>300 else 2 if r['glucosa']>200 else 0) + \
            (3 if r['saturacion_oxigeno']<88 else 0) + int(r['fumador'])
        return 'Crítico' if s>=6 else 'Alto' if s>=4 else 'Medio' if s>=2 else 'Bajo'
    df['riesgo_enfermedad'] = df.apply(clf, axis=1)
    return df

print("="*55)
print("  HealthShield AI — Suite de Tests")
print("="*55)
print()
print("── ETL Pipeline ──────────────────────────────────────")

def _t1():
    r = T.DuplicateRemover().transform(make_df())
    assert len(r) == 4 and r['id_paciente'].is_unique
t("DuplicateRemover: elimina duplicados y garantiza IDs únicos", _t1)

def _t2():
    r = T.TypeCoercer().transform(make_df())
    v = r.loc[r['id_paciente']==2, 'edad'].values[0]
    assert pd.isna(v) or str(v)=='<NA>'
t("TypeCoercer: edad 'Treinta' → NaN", _t2)

def _t3():
    r = T.TypeCoercer().transform(make_df())
    v = r.loc[r['id_paciente']==2, 'presión_sistólica'].values[0]
    assert pd.isna(v) or str(v)=='<NA>'
t("TypeCoercer: presión 'alta' → NaN", _t3)

def _t4():
    df = T.NullImputer().transform(T.TypeCoercer().transform(make_df()))
    assert df['peso'].isna().sum()==0 and df['glucosa'].isna().sum()==0 and df['temperatura'].isna().sum()==0
t("NullImputer: elimina todos los nulos (peso/glucosa/temperatura)", _t4)

def _t5():
    r = T.OutlierHandler().transform(T.TypeCoercer().transform(make_df()))
    assert float(r['peso'].max()) <= 300 and float(r['saturación_oxígeno'].min()) >= 70
t("OutlierHandler: peso 420 y saturación 82 → dentro de rangos clínicos", _t5)

def _t6():
    r = T.DiagnosisNormalizer().transform(make_df())
    assert 'hipertencion' not in r['diagnóstico_preliminar'].values
    assert 'Hipertensión' in r['diagnóstico_preliminar'].values
t("DiagnosisNormalizer: 'hipertencion' → 'Hipertensión'", _t6)

def _t7():
    r = T.SexNormalizer().transform(make_df())
    assert set(r['sexo'].unique()).issubset({'M','F'})
t("SexNormalizer: todos los valores normalizados a M/F", _t7)

def _t8():
    df = pd.DataFrame({'peso':[70.0],'altura':[1.65],'IMC':[0.0]})
    r = T.IMCCalculator().transform(df)
    assert abs(float(r.loc[0,'IMC'])-25.71)<0.1
    df2 = pd.DataFrame({'peso':[40.0,70.0,82.0,100.0],'altura':[1.70]*4,'IMC':[0.0]*4})
    r2 = T.IMCCalculator().transform(df2)
    assert {'Bajo peso','Normal','Sobrepeso','Obesidad'}.issubset(set(r2['clasificacion_imc']))
t("IMCCalculator: fórmula correcta + 4 categorías OMS", _t8)

def _t9():
    critico = pd.DataFrame({'presión_sistólica':[190],'glucosa':[320],'saturación_oxígeno':[82],
                            'antecedentes_familiares':[True],'fumador':[True],'edad':[75],'IMC':[37.0]})
    bajo    = pd.DataFrame({'presión_sistólica':[110],'glucosa':[90],'saturación_oxígeno':[98],
                            'antecedentes_familiares':[False],'fumador':[False],'edad':[28],'IMC':[22.0]})
    assert T.RiskClassifier().transform(critico).loc[0,'riesgo_enfermedad'] == 'Crítico'
    assert T.RiskClassifier().transform(bajo).loc[0,'riesgo_enfermedad'] == 'Bajo'
t("RiskClassifier: clasifica Crítico y Bajo correctamente", _t9)

def _t10():
    qr = Q.DataQualityReport()
    df = pd.DataFrame({'a':[1,None,3]})
    qr.snapshot_before(df); qr.add_metric('dupl',2)
    r = qr.generate(df, df.dropna(), 1.2)
    assert 'quality_score' in r and 0<=r['quality_score']<=100
    assert r['acciones_correctivas']['dupl']==2
t("DataQualityReport: score en [0,100] + métricas acumuladas", _t10)

def _t11():
    df = S.DataSimulator().generate(20)
    assert len(df)>=20
    for col in ['id_paciente','nombres','edad','sexo','glucosa','riesgo_enfermedad']:
        assert col in df.columns
t("DataSimulator: genera ≥20 registros con todas las columnas", _t11)

def _t12():
    df = S.DataSimulator(error_rate=0.5).generate(50)
    assert df[['peso','glucosa','colesterol','temperatura']].isnull().sum().sum()>0
t("DataSimulator: inyecta nulos con error_rate=0.5", _t12)

print()
print("── Machine Learning ──────────────────────────────────")

def _t13():
    result = Tr.ModelTrainer('random_forest').train(make_ml_df())
    _model_path[0] = result['model_path']
    assert os.path.exists(result['model_path'])
    assert result['accuracy'] > 0.5
    for k in ['accuracy','precision','recall','f1_score','cv_accuracy','feature_importance']:
        assert k in result, f"Falta: {k}"
t("ModelTrainer RF: entrena, guarda .pkl y retorna todas las métricas", _t13)

def _t14():
    result = Tr.ModelTrainer('random_forest').train(make_ml_df())
    for k in ['accuracy','precision','recall','f1_score']:
        assert 0<=result[k]<=1
t("ModelTrainer: accuracy/precision/recall/f1 en rango [0,1]", _t14)

def _t15():
    result = Tr.ModelTrainer('random_forest').train(make_ml_df())
    fi_raw = result['feature_importance']
    # Filtrar claves especiales (confusion_matrix, classification_report, classes)
    NON_FEATURE_KEYS = {'confusion_matrix', 'classification_report', 'classes'}
    fi = {k: float(v) for k, v in fi_raw.items() if k not in NON_FEATURE_KEYS}
    assert len(fi) == len(Tr.FEATURES), f"Esperadas {len(Tr.FEATURES)} features, got {len(fi)}: {list(fi.keys())}"
    total = sum(fi.values())
    assert abs(total - 1.0) < 0.05, f"Suma features={total:.4f} (tolerancia 0.05)"
t("ModelTrainer: feature_importance cubre todas las variables y suma ≈1", _t15)

def _t16():
    for algo in ['logistic_regression','decision_tree']:
        r = Tr.ModelTrainer(algo).train(make_ml_df())
        assert r['accuracy']>0, f"{algo} falló"
t("ModelTrainer: LogisticRegression y DecisionTree entrenan sin errores", _t16)

def _t17():
    if not _model_path[0]: return
    pred = Pr.ClinicalPredictor(_model_path[0])
    result = pred.predict({'edad':60,'imc':32,'presion_sistolica':170,'presion_diastolica':100,
        'frecuencia_cardiaca':90,'glucosa':250,'colesterol':280,'saturacion_oxigeno':91,
        'temperatura':37.2,'fumador':1,'consumo_alcohol':0,'antecedentes_familiares':1})
    assert result['riesgo_predicho'] in ['Bajo','Medio','Alto','Crítico']
    assert abs(sum(result['probabilidades'].values())-1.0)<0.01
    assert len(result['factores_clave'])==3
t("ClinicalPredictor: predict retorna riesgo válido + probabilidades + 3 factores XAI", _t17)

def _t18():
    if not _model_path[0]: return
    pred = Pr.ClinicalPredictor(_model_path[0])
    df = make_ml_df(15)
    r = pred.predict_batch(df)
    assert 'riesgo_predicho' in r.columns
    assert all(v in ['Bajo','Medio','Alto','Crítico'] for v in r['riesgo_predicho'])
t("ClinicalPredictor predict_batch: 15 pacientes con riesgos válidos", _t18)

print()
print("── Data Quality & Simulación ─────────────────────────")

def _t19():
    df_raw = make_df()
    df_c   = T.TypeCoercer().transform(df_raw.copy())
    df_c   = T.NullImputer().transform(df_c)
    qr = Q.DataQualityReport()
    qr.snapshot_before(df_raw)
    r = qr.generate(df_raw, df_c, 0.5)
    assert r['antes']['total_registros'] == 5
    assert r['despues']['total_registros'] == 5
    assert r['clasificacion'] in ['Excelente','Buena','Aceptable','Deficiente']
t("DataQualityReport: snapshot antes/después + clasificación verbal", _t19)

def _t20():
    sim = S.DataSimulator(error_rate=0.3)
    df  = sim.generate(100)
    age_vals = df['edad'].astype(str).tolist()
    has_string = any(not v.replace('.','').replace('-','').isdigit() and v!='None' for v in age_vals)
    assert has_string, "No se inyectaron errores de tipo en edad"
t("DataSimulator: inyecta errores de tipo en edad (string numérico)", _t20)

print()
print("="*55)
print(f"  TOTAL: {passed}/{total} tests PASADOS  {'✅ ALL PASS' if passed==total else f'⚠️  {total-passed} fallando'}")
print("="*55)


# ── Tests adicionales: Validador CSV + Correlación + IA Providers ─────────────
print()
print("── Nuevas funcionalidades ────────────────────────────")

def _t21():
    """Validador CSV: detecta columnas faltantes."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
    # Stub Django para el import
    import types
    for mod in ['django','django.db','django.db.models','apps.etl.models']:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    import importlib.util
    spec = importlib.util.spec_from_file_location("validators",
        os.path.join(os.path.dirname(__file__),'..','backend','apps','etl','validators.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    df_ok = pd.DataFrame({col: [1] for col in m.COLUMNAS_REQUERIDAS})
    valido, errores, _ = m.CSVFormatValidator().validate(df_ok)
    assert valido, f"Debería ser válido: {errores}"
t("CSVFormatValidator: DataFrame completo → válido", _t21)

def _t22():
    """Validador CSV: rechaza DataFrame vacío."""
    import sys, types, importlib.util, os
    for mod in ['django','django.db','apps.etl.models']:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    spec = importlib.util.spec_from_file_location("validators",
        os.path.join(os.path.dirname(__file__),'..','backend','apps','etl','validators.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    valido, errores, _ = m.CSVFormatValidator().validate(pd.DataFrame())
    assert not valido and len(errores) > 0
t("CSVFormatValidator: DataFrame vacío → inválido con errores", _t22)

def _t23():
    """IA Providers: factory retorna instancias correctas."""
    import sys, types, os, importlib.util
    for mod in ['django','django.conf']:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    sys.modules['django.conf'].settings = type('S',(),{'ML_MODELS_PATH':'/tmp'})()
    spec = importlib.util.spec_from_file_location("ai_providers",
        os.path.join(os.path.dirname(__file__),'..','backend','apps','ml','ai_providers.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    claude = m.get_provider('claude')
    gemini = m.get_provider('gemini')
    assert claude.nombre == 'Claude (Anthropic)'
    assert gemini.nombre == 'Gemini (Google)'
    assert isinstance(claude, m.ClaudeProvider)
    assert isinstance(gemini, m.GeminiProvider)
t("AIProviders: factory retorna Claude y Gemini correctamente", _t23)

def _t24():
    """IA Providers: sin API key → esta_disponible() = False."""
    import sys, types, os, importlib.util
    for mod in ['django','django.conf']:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    spec = importlib.util.spec_from_file_location("ai_providers",
        os.path.join(os.path.dirname(__file__),'..','backend','apps','ml','ai_providers.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    # Sin API key configurada
    os.environ.pop('ANTHROPIC_API_KEY', None)
    os.environ.pop('GEMINI_API_KEY', None)
    assert not m.ClaudeProvider().esta_disponible()
    assert not m.GeminiProvider().esta_disponible()
t("AIProviders: sin API keys → esta_disponible() = False", _t24)

def _t25():
    """Correlación: CorrelacionCalculator tiene variables clínicas definidas."""
    import sys, types, os, importlib.util
    for mod in ['django','django.db','django.db.models','apps.etl.models',
                'apps.etl','apps']:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    spec = importlib.util.spec_from_file_location("correlacion",
        os.path.join(os.path.dirname(__file__),'..','backend','apps','analytics','correlacion.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert len(m.VARIABLES_CLINICAS) == 8
    assert 'glucosa' in m.VARIABLES_CLINICAS
    assert 'imc' in m.VARIABLES_CLINICAS
    assert len(m.LABELS) == 8
t("CorrelacionCalculator: 8 variables clínicas definidas con labels", _t25)

print()
print("="*55)
print(f"  TOTAL FINAL: {passed}/{total} tests PASADOS  {'✅ ALL PASS' if passed==total else f'⚠️  {total-passed} fallando'}")
print("="*55)
