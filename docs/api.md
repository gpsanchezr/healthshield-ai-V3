# HealthShield AI — Documentación de API REST

> Swagger UI interactivo: `http://localhost:8000/api/schema/swagger-ui/`

## Autenticación

Todos los endpoints (excepto login) requieren header:
```
Authorization: Bearer <access_token>
```

---

## Auth

### POST `/api/auth/login/`
```json
Body:  { "username": "admin", "password": "Admin123!" }
200:   { "access": "...", "refresh": "...", "usuario": {"rol": "administrador", ...} }
401:   { "detail": "No active account found..." }
```

### POST `/api/auth/refresh/`
```json
Body: { "refresh": "<refresh_token>" }
200:  { "access": "<nuevo_access_token>" }
```

### POST `/api/auth/logout/`
```json
Body: { "refresh": "<refresh_token>" }
200:  { "detail": "Sesión cerrada correctamente." }
```

### GET `/api/auth/me/`
```json
200: { "id": 1, "username": "admin", "rol": "administrador", ... }
```

### GET/POST `/api/auth/usuarios/` — Solo Admin
### GET/PUT/DELETE `/api/auth/usuarios/{id}/` — Solo Admin

---

## Pacientes

### GET `/api/pacientes/`
```
Roles: Médico+   Query: ?search=nombre  ?ordering=apellidos,-edad
200: { "count": 1800, "results": [...] }
```

### GET `/api/pacientes/{id}/`
```json
200: {
  "id": 1, "nombres": "Ana", "apellidos": "García", "edad": 45, "sexo": "F",
  "registros": [{ "imc": 25.7, "riesgo_enfermedad": "Medio", ... }]
}
```

### GET `/api/pacientes/registros/`
```
Query: ?riesgo_enfermedad=Crítico  ?fumador=true
```

---

## ETL

### POST `/api/etl/run/`
```
Roles: Analista+   Content-Type: multipart/form-data
Body: archivo=<file.csv>
200: { "status": "success", "ejecucion_id": 1, "report": { "quality_score": 94.2, ... } }
400: { "error": "Se requiere un archivo CSV o Excel." }
```

### POST `/api/etl/simular/`
```
Roles: Administrador   Content-Type: application/json
Body: { "count": 50 }
200: { "status": "success", "report": { ... } }
403: Solo para administradores
```

### GET `/api/etl/historial/`
```json
200: { "count": 10, "results": [{ "id": 1, "estado": "completado", "quality_score": 94.2, ... }] }
```

### GET `/api/etl/calidad/{id}/`
```json
200: {
  "quality_score": 94.2, "clasificacion": "Excelente",
  "antes": { "total_registros": 1850, "total_nulos": 202 },
  "despues": { "total_registros": 1800, "total_nulos": 0 },
  "acciones_correctivas": { "duplicados_eliminados": 50, "nulos_imputados": 202, ... }
}
```

### GET `/api/etl/alertas/`
```json
200: { "count": 3, "results": [{ "nivel_urgencia": "critica", "descripcion": "...", ... }] }
```

### PATCH `/api/etl/alertas/{id}/vista/`
```json
200: { "status": "marcada como vista" }
```

---

## Analytics

### GET `/api/analytics/kpis/`
```json
200: {
  "total_registros": 1800,
  "pacientes_criticos": 45,
  "pacientes_alto_riesgo": 213,
  "pacientes_hipertensos": 387,
  "pacientes_diabeticos": 156,
  "pacientes_fumadores": 498,
  "promedio_imc": 27.3,
  "promedio_glucosa": 142.8,
  "distribucion_riesgo": { "Bajo": 542, "Medio": 1000, "Alto": 213, "Crítico": 45 },
  "distribucion_imc": { "Normal": 650, "Sobrepeso": 720, "Obesidad": 380, "Bajo peso": 50 },
  "top_diagnosticos": [{ "diagnostico": "Hipertensión", "total": 520 }, ...]
}
```

### GET `/api/analytics/estadistica/?campo=glucosa`
```
Campos válidos: imc, glucosa, colesterol, presion_sistolica, temperatura, frecuencia_cardiaca
200: { "campo": "glucosa", "n": 1800, "media": 142.8, "mediana": 138.0, "maximo": 598.0, "minimo": 52.0 }
```

### POST `/api/etl/detectar/` — Roles: Analista+
```json
200: { "alertas_creadas": 12, "mensaje": "12 nuevas alertas críticas generadas" }
```

### GET `/api/analytics/segmentacion/?por=riesgo`
```
Parámetros: por=riesgo | por=sexo | por=diagnostico
```

---

## Machine Learning

### GET `/api/predicciones/modelo/metricas/`
```json
200: {
  "nombre": "HealthShield Random Forest", "algoritmo": "random_forest", "version": "v1",
  "accuracy": 0.8734, "precision_score": 0.8621, "recall": 0.8734, "f1_score": 0.8670,
  "feature_importance": { "glucosa": 0.2341, "presion_sistolica": 0.1987, ... }
}
404: { "error": "No hay modelo activo. Ejecuta: python manage.py train_model" }
```

### POST `/api/predicciones/modelo/entrenar/` — Solo Admin
```json
Body: { "algorithm": "random_forest" }
200: { "accuracy": 0.87, "f1_score": 0.86, "modelo_id": 2, "feature_importance": {...} }
```

### POST `/api/predicciones/paciente/{id}/`
```json
200: {
  "riesgo_predicho": "Alto",
  "probabilidad_max": 0.7823,
  "probabilidades": { "Bajo": 0.05, "Medio": 0.17, "Alto": 0.78, "Crítico": 0.00 },
  "factores_clave": [
    { "variable": "glucosa",           "importancia": 0.234, "valor_paciente": 285.0 },
    { "variable": "presion_sistolica", "importancia": 0.198, "valor_paciente": 162 },
    { "variable": "imc",               "importancia": 0.156, "valor_paciente": 33.4 }
  ]
}
404: { "error": "Paciente o registro no encontrado" }
```

### GET `/api/predicciones/` — Lista todas las predicciones

---

## Dashboard

### GET `/api/dashboard/kpis/`
```json
200: { "kpis": { ...todos los KPIs... }, "ultima_etl": { "id": 5, "quality_score": 94.2 } }
```

### GET `/api/dashboard/tendencia/`
```json
200: { "tendencia": [{ "fecha": "21/05", "registros": 1800, "quality_score": 94.2 }, ...] }
```

---

## Reportes

### GET `/api/reportes/pdf/`
```
Roles: Analista+
Retorna: application/pdf — Reporte clínico con KPIs, tabla de pacientes, logo HealthShield AI
```

### GET `/api/reportes/excel/`
```
Retorna: .xlsx con colores por nivel de riesgo
```

### GET `/api/reportes/csv/`
```
Retorna: .csv del dataset limpio completo
```

### Nuevos endpoints (esta versión)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/etl/run-async/` | ETL en background (Celery) |
| GET | `/api/etl/task/<id>/` | Polling de progreso de tarea |
| GET | `/api/etl/calidad-historica/` | Evolución histórica del quality score |
| GET | `/api/analytics/correlacion/` | Matriz de correlación Pearson |
| GET | `/api/analytics/tendencia-clinica/` | Tendencia por campo y mes |
| GET | `/api/analytics/segmentacion/?por=imc` | Segmentación por IMC |
| GET | `/api/analytics/segmentacion/?por=actividad` | Segmentación por actividad física |
| GET | `/api/predicciones/modelo/confusion-matrix/` | Matriz de confusión + report |
| POST | `/api/predicciones/analisis-ia/<id>/` | IA generativa (body: proveedor) |
| GET | `/api/predicciones/proveedores-ia/` | Estado Claude y Gemini |
| GET | `/api/auth/auditoria/` | Log de acciones de usuario (Admin) |
