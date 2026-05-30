"""
Tests unitarios del motor ML — HealthShield AI
Ejecutar: python3 tests/run_tests.py (incluido en run_tests.py)
O directamente: python3 tests/test_ml.py
"""
import sys, os, types, importlib.util
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Stub Django
for mod in ['django','django.db','django.db.models','django.conf',
            'apps','apps.etl','apps.etl.models','apps.ml','apps.ml.models']:
    if mod not in sys.modules:
        sys.modules[mod] = types.ModuleType(mod)

# Stub settings para ML_MODELS_PATH
class _Settings:
    ML_MODELS_PATH = '/tmp/hs_ml_test_models'
django_conf = sys.modules['django.conf']
django_conf.settings = _Settings()

import numpy as np
import pandas as pd

def load_module(fpath):
    spec = importlib.util.spec_from_file_location("_m", fpath)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

base = os.path.join(os.path.dirname(__file__), '..', 'backend', 'apps')
Tr = load_module(os.path.join(base, 'ml', 'trainer.py'))
Pr = load_module(os.path.join(base, 'ml', 'predictor.py'))

os.makedirs('/tmp/hs_ml_test_models', exist_ok=True)

FEATURES = Tr.FEATURES

def make_clinical_df(n=200):
    """Dataset clínico mínimo para entrenar."""
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        'edad':              rng.integers(18, 85, n),
        'imc':               rng.uniform(16, 45, n),
        'presion_sistolica': rng.integers(80, 200, n),
        'presion_diastolica':rng.integers(50, 130, n),
        'frecuencia_cardiaca':rng.integers(50, 120, n),
        'glucosa':           rng.uniform(70, 350, n),
        'colesterol':        rng.uniform(120, 350, n),
        'saturacion_oxigeno':rng.uniform(85, 100, n),
        'temperatura':       rng.uniform(36, 39, n),
        'fumador':           rng.integers(0, 2, n),
        'consumo_alcohol':   rng.integers(0, 2, n),
        'antecedentes_familiares': rng.integers(0, 2, n),
    })
    # Asignar riesgo basado en reglas simples para tener etiquetas reales
    def classify(r):
        s = 0
        if r['presion_sistolica'] > 180: s += 3
        elif r['presion_sistolica'] > 140: s += 2
        if r['glucosa'] > 300: s += 3
        elif r['glucosa'] > 200: s += 2
        if r['saturacion_oxigeno'] < 88: s += 3
        if r['fumador']: s += 1
        if r['imc'] > 35: s += 1
        if s >= 6: return 'Crítico'
        if s >= 4: return 'Alto'
        if s >= 2: return 'Medio'
        return 'Bajo'
    df['riesgo_enfermedad'] = df.apply(classify, axis=1)
    return df

passed = 0; total = 0
_model_path = None  # se llena tras primer test

def t(name, fn):
    global passed, total
    total += 1
    try:
        fn()
        print(f"  ✅  {name}")
        passed += 1
    except Exception as e:
        print(f"  ❌  {name}: {e}")


# ── ModelTrainer ───────────────────────────────────────────────────────────────
def _train_rf():
    global _model_path
    df = make_clinical_df(300)
    trainer = Tr.ModelTrainer('random_forest')
    result = trainer.train(df)
    _model_path = result['model_path']
    assert os.path.exists(_model_path), "Archivo .pkl no generado"
    assert result['accuracy'] > 0.5, f"Accuracy muy baja: {result['accuracy']}"
t("ModelTrainer RandomForest: entrena y genera .pkl", _train_rf)

def _metrics_present():
    df = make_clinical_df(200)
    result = Tr.ModelTrainer('random_forest').train(df)
    for key in ['accuracy','precision','recall','f1_score','cv_accuracy','feature_importance']:
        assert key in result, f"Falta clave: {key}"
t("ModelTrainer: retorna todas las métricas requeridas", _metrics_present)

def _metrics_range():
    df = make_clinical_df(200)
    result = Tr.ModelTrainer('random_forest').train(df)
    for key in ['accuracy','precision','recall','f1_score']:
        v = result[key]
        assert 0 <= v <= 1, f"{key}={v} fuera de rango [0,1]"
t("ModelTrainer: métricas en rango [0, 1]", _metrics_range)

def _feature_importance():
    df = make_clinical_df(200)
    result = Tr.ModelTrainer('random_forest').train(df)
    fi = result['feature_importance']
    assert len(fi) == len(FEATURES), f"Esperadas {len(FEATURES)} features, got {len(fi)}"
    total_imp = sum(fi.values())
    assert abs(total_imp - 1.0) < 0.01, f"Importancias no suman 1: {total_imp}"
t("ModelTrainer: feature_importance incluye todos los features y suma ≈1", _feature_importance)

def _logistic():
    df = make_clinical_df(200)
    result = Tr.ModelTrainer('logistic_regression').train(df)
    assert result['accuracy'] > 0, "Logistic regression falló"
t("ModelTrainer LogisticRegression: entrena correctamente", _logistic)

def _decision_tree():
    df = make_clinical_df(200)
    result = Tr.ModelTrainer('decision_tree').train(df)
    assert result['accuracy'] > 0, "DecisionTree falló"
t("ModelTrainer DecisionTree: entrena correctamente", _decision_tree)

# ── ClinicalPredictor ──────────────────────────────────────────────────────────
def _predictor_loads():
    if not _model_path: return
    pred = Pr.ClinicalPredictor(_model_path)
    assert pred.model is not None
t("ClinicalPredictor: carga modelo .pkl correctamente", _predictor_loads)

def _predictor_output():
    if not _model_path: return
    pred = Pr.ClinicalPredictor(_model_path)
    result = pred.predict({
        'edad':60,'imc':32,'presion_sistolica':170,'presion_diastolica':100,
        'frecuencia_cardiaca':90,'glucosa':250,'colesterol':280,
        'saturacion_oxigeno':91,'temperatura':37.2,'fumador':1,
        'consumo_alcohol':0,'antecedentes_familiares':1,
    })
    assert 'riesgo_predicho'   in result
    assert 'probabilidad_max'  in result
    assert 'probabilidades'    in result
    assert 'factores_clave'    in result
    assert result['riesgo_predicho'] in ['Bajo','Medio','Alto','Crítico']
t("ClinicalPredictor: predict retorna estructura completa", _predictor_output)

def _predictor_probabilidades():
    if not _model_path: return
    pred = Pr.ClinicalPredictor(_model_path)
    result = pred.predict({k: 50 for k in FEATURES})
    probs = result['probabilidades']
    assert abs(sum(probs.values()) - 1.0) < 0.01, f"Probabilidades no suman 1: {sum(probs.values())}"
t("ClinicalPredictor: probabilidades suman 1.0", _predictor_probabilidades)

def _predictor_factores_clave():
    if not _model_path: return
    pred = Pr.ClinicalPredictor(_model_path)
    result = pred.predict({k: 50 for k in FEATURES})
    assert len(result['factores_clave']) == 3
    for f in result['factores_clave']:
        assert 'variable' in f and 'importancia' in f
t("ClinicalPredictor: retorna exactamente 3 factores clave (XAI)", _predictor_factores_clave)

def _predictor_batch():
    if not _model_path: return
    pred = Pr.ClinicalPredictor(_model_path)
    df = make_clinical_df(20)
    result = pred.predict_batch(df)
    assert 'riesgo_predicho' in result.columns
    assert len(result) == 20
    assert all(v in ['Bajo','Medio','Alto','Crítico'] for v in result['riesgo_predicho'])
t("ClinicalPredictor predict_batch: 20 pacientes con riesgos válidos", _predictor_batch)

print(f"\n{'='*55}")
print(f"  ML Tests: {passed}/{total} PASADOS {'✅ ALL PASS' if passed==total else f'⚠️ ({total-passed} fallando)'}")
