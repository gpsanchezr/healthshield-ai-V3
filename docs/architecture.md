# HealthShield AI — Arquitectura del Sistema

## Diagrama de Arquitectura

```
┌──────────────────────────────────────────────────────────────┐
│                    FRONTEND (Puerto 8000)                     │
│  Bootstrap 5 · Chart.js · JavaScript ES6+                    │
│                                                              │
│  /login/    /dashboard/    /etl/    /pacientes/    /ml/      │
└─────────────────────────┬────────────────────────────────────┘
                          │ HTTP + REST API (JSON + JWT)
┌─────────────────────────▼────────────────────────────────────┐
│                    DJANGO BACKEND                             │
├──────────────┬──────────┬───────────┬───────────┬───────────┤
│ auth/        │ etl/     │ analytics/│ ml/       │ reports/  │
│ JWT · Roles  │ Pipeline │ KPIs      │ RandomFor.│ PDF/Excel │
│ 3 roles      │ 8 transf.│ Alertas   │ XAI       │ CSV       │
│              │ Simulador│ Segmentos │ Predicción│           │
└──────────────┴────┬─────┴───────────┴───────────┴───────────┘
                    │ Django ORM
┌───────────────────▼──────────────────────────────────────────┐
│              PostgreSQL 16 / SQLite (dev)                     │
│  8 tablas · Índices · JSONB para reportes y features         │
└──────────────────────────────────────────────────────────────┘
```

## Flujo ETL Completo

```
EXTRACT          TRANSFORM (8 pasos)              LOAD
─────────        ──────────────────────────────    ──────────────
CSV/Excel   →   DuplicateRemover                →  Paciente
                TypeCoercer                        RegistroClinico
                NullImputer (media/mediana/moda)   EjecucionETL
                OutlierHandler (rangos clínicos)   LogETL
                DiagnosisNormalizer                QualityReport
                SexNormalizer                      (JSONB)
                IMCCalculator (OMS)
                RiskClassifier (reglas clínicas)
```

## Flujo Machine Learning

```
Dataset limpio (BD)
       ↓
Preprocesamiento (encode booleans, fillna median)
       ↓
Train/Test Split 80/20 (stratified by riesgo)
       ↓
RandomForest(200 trees, balanced, max_depth=10)
       ↓
Evaluación: Accuracy · Precision · Recall · F1
       ↓
Cross-Validation 5-fold
       ↓
Feature Importance → XAI (top 3 factores)
       ↓
Persistencia .pkl con joblib
       ↓
Predicción individual + batch → API + Dashboard
```

## Roles y Permisos

| Endpoint          | Admin | Médico | Analista |
|-------------------|-------|--------|----------|
| Dashboard KPIs    | ✅    | ✅     | ✅       |
| Ver pacientes     | ✅    | ✅     | ❌       |
| Predecir riesgo   | ✅    | ✅     | ❌       |
| Ejecutar ETL      | ✅    | ❌     | ✅       |
| Simular datos     | ✅    | ❌     | ❌       |
| Entrenar modelo   | ✅    | ❌     | ❌       |
| Exportar reportes | ✅    | ❌     | ✅       |
| Gestionar usuarios| ✅    | ❌     | ❌       |

## Stack Tecnológico

| Capa       | Tecnología              | Versión  |
|------------|-------------------------|----------|
| Backend    | Python + Django         | 3.12/5.x |
| API        | Django REST Framework   | 3.15     |
| Auth       | SimpleJWT               | 5.3      |
| Docs API   | drf-spectacular         | 0.27     |
| ETL        | Pandas + NumPy          | 2.x/1.x  |
| ML         | Scikit-Learn + joblib   | 1.5/1.4  |
| BD Prod    | PostgreSQL              | 16       |
| BD Dev     | SQLite                  | 3.x      |
| Frontend   | Bootstrap 5 + Chart.js  | 5.3/4.4  |
| Reportes   | ReportLab + XlsxWriter  | 4.2/3.2  |
| DevOps     | Docker + GitHub Actions | 24/latest|
