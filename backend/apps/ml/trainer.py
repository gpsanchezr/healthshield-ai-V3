from typing import Dict, List, Tuple, Any
import joblib, numpy as np, pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report
from django.conf import settings

FEATURES = ['edad','imc','presion_sistolica','presion_diastolica','frecuencia_cardiaca',
            'glucosa','colesterol','saturacion_oxigeno','temperatura','fumador','consumo_alcohol','antecedentes_familiares']
TARGET = 'riesgo_enfermedad'

ALGOS = {
    'random_forest': lambda: RandomForestClassifier(
        n_estimators=200, max_depth=10, min_samples_leaf=5,
        class_weight='balanced', random_state=42, n_jobs=-1,
    ),
    'logistic_regression': lambda: Pipeline([
        ('scaler', StandardScaler()),       # escala features → LR converge mejor
        ('clf', LogisticRegression(
            max_iter=1000, class_weight='balanced',
            solver='lbfgs', random_state=42,  # multi_class deprecado en sklearn 1.5+
        )),
    ]),
    'decision_tree': lambda: DecisionTreeClassifier(
        max_depth=8, min_samples_leaf=5,
        class_weight='balanced', random_state=42,
    ),
}

class ModelTrainer:
    def __init__(self, algorithm='random_forest'):
        self.algorithm = algorithm
        self.le = LabelEncoder()
        self.models_dir = Path(getattr(settings, 'ML_MODELS_PATH', './ml_models'))
        self.models_dir.mkdir(exist_ok=True)

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        for col in ['fumador','consumo_alcohol','antecedentes_familiares']:
            if col in df.columns: df[col] = df[col].astype(int)
        X = df[FEATURES].fillna(df[FEATURES].median()).values
        y = self.le.fit_transform(df[TARGET])
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        model = ALGOS[self.algorithm]()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        # Feature importance (Pipeline de LR no tiene feature_importances_)
        if hasattr(model, 'feature_importances_'):
            fi = dict(zip(FEATURES, model.feature_importances_.tolist()))
        elif hasattr(model, 'named_steps') and hasattr(model.named_steps.get('clf'), 'coef_'):
            # Regresión logística: usar valor absoluto de coeficientes promediados por clase
            coefs = np.abs(model.named_steps['clf'].coef_).mean(axis=0)
            coefs = coefs / coefs.sum()  # normalizar a suma 1
            fi = dict(zip(FEATURES, coefs.tolist()))
        else:
            fi = {f: round(1/len(FEATURES), 4) for f in FEATURES}
        fi_sorted = dict(sorted(fi.items(), key=lambda x: x[1], reverse=True))

        cv = float(cross_val_score(model, X, y, cv=5, scoring='accuracy').mean())
        path = self.models_dir / f'{self.algorithm}_{datetime.now():%Y%m%d_%H%M%S}.pkl'
        joblib.dump({'model': model, 'label_encoder': self.le}, path)

        acc  = round(accuracy_score(y_test, y_pred), 4)
        prec = round(precision_score(y_test, y_pred, average='weighted', zero_division=0), 4)
        rec  = round(recall_score(y_test, y_pred, average='weighted', zero_division=0), 4)
        f1   = round(f1_score(y_test, y_pred, average='weighted', zero_division=0), 4)
        cm   = confusion_matrix(y_test, y_pred).tolist()
        cr   = classification_report(y_test, y_pred,
                   target_names=self.le.classes_.tolist(), output_dict=True, zero_division=0)

        # Guardar confusion_matrix en feature_importance para persistencia en BD
        fi_sorted['confusion_matrix']        = cm
        fi_sorted['classification_report']   = cr
        fi_sorted['classes']                 = self.le.classes_.tolist()

        return {
            'model_path':            str(path),
            'algorithm':             self.algorithm,
            'features':              FEATURES,
            'training_samples':      len(X_train),
            'accuracy':              acc,
            'precision':             prec,
            'recall':                rec,
            'f1_score':              f1,
            'cv_accuracy':           round(cv, 4),
            'confusion_matrix':      cm,
            'classes':               self.le.classes_.tolist(),
            'classification_report': cr,
            'feature_importance':    fi_sorted,
        }
