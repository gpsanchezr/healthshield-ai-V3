from typing import Dict, List, Any
import joblib, numpy as np
try:
    from apps.ml.trainer import FEATURES
except ImportError:
    FEATURES = ['edad','imc','presion_sistolica','presion_diastolica','frecuencia_cardiaca',
                'glucosa','colesterol','saturacion_oxigeno','temperatura',
                'fumador','consumo_alcohol','antecedentes_familiares']

class ClinicalPredictor:
    def __init__(self, model_path: str):
        artifact = joblib.load(model_path)
        self.model = artifact['model']
        self.le    = artifact['label_encoder']
        self.fi = dict(zip(FEATURES, getattr(self.model, 'feature_importances_', [1/len(FEATURES)]*len(FEATURES))))

    def predict(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        X = np.array([[float(patient_data.get(f, 0) or 0) for f in FEATURES]])
        proba   = self.model.predict_proba(X)[0]
        idx     = np.argmax(proba)
        riesgo  = self.le.inverse_transform([idx])[0]
        probas  = {cls: round(float(p), 4) for cls, p in zip(self.le.classes_, proba)}
        factores= [{'variable': f, 'importancia': round(self.fi[f],4), 'valor_paciente': patient_data.get(f,'N/A')}
                   for f, _ in sorted(self.fi.items(), key=lambda x: x[1], reverse=True)[:3]]
        return {'riesgo_predicho': riesgo, 'probabilidad_max': round(float(proba[idx]),4),
                'probabilidades': probas, 'factores_clave': factores}

    def predict_batch(self, df):
        import pandas as pd
        for c in ['fumador','consumo_alcohol','antecedentes_familiares']:
            if c in df.columns: df[c] = df[c].astype(int)
        X = df[FEATURES].fillna(df[FEATURES].median()).values
        df['riesgo_predicho'] = self.le.inverse_transform(self.model.predict(X))
        return df
