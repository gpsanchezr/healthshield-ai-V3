# HealthShield AI — Diagrama ERD

```mermaid
erDiagram
    USUARIOS {
        bigint id PK
        varchar username UK
        varchar email
        varchar password
        varchar rol
        bool    is_active
        timestamp created_at
    }

    EJECUCIONES_ETL {
        bigint  id PK
        bigint  usuario_id FK
        varchar archivo_fuente
        timestamp fecha_inicio
        timestamp fecha_fin
        decimal duracion_segundos
        int     registros_extraidos
        int     registros_procesados
        int     registros_rechazados
        int     duplicados_eliminados
        int     nulos_imputados
        varchar estado
        varchar tipo
        jsonb   reporte_calidad
    }

    PACIENTES {
        bigint  id PK
        int     id_paciente_original UK
        varchar nombres
        varchar apellidos
        smallint edad
        varchar sexo
        timestamp fecha_registro
    }

    REGISTROS_CLINICOS {
        bigint  id PK
        bigint  paciente_id FK
        bigint  fuente_etl_id FK
        decimal peso
        decimal altura
        decimal imc
        varchar clasificacion_imc
        smallint presion_sistolica
        smallint presion_diastolica
        smallint frecuencia_cardiaca
        decimal glucosa
        decimal colesterol
        decimal saturacion_oxigeno
        decimal temperatura
        bool    antecedentes_familiares
        bool    fumador
        bool    consumo_alcohol
        varchar actividad_fisica
        varchar diagnostico_preliminar
        varchar riesgo_enfermedad
        date    fecha_consulta
        timestamp created_at
    }

    LOGS_ETL {
        bigint id PK
        bigint ejecucion_id FK
        varchar nivel
        text   mensaje
        varchar campo_afectado
        text    valor_original
        text    valor_corregido
        timestamp timestamp
    }

    ALERTAS {
        bigint id PK
        bigint paciente_id FK
        bigint visto_por_id FK
        varchar tipo_alerta
        text    descripcion
        varchar nivel_urgencia
        timestamp fecha_alerta
        timestamp fecha_vista
    }

    MODELOS_ML {
        bigint  id PK
        varchar nombre
        varchar algoritmo
        varchar version
        decimal accuracy
        decimal precision_score
        decimal recall
        decimal f1_score
        varchar archivo_modelo
        jsonb   feature_names
        jsonb   feature_importance
        timestamp entrenado_en
        int     registros_entrenamiento
        bool    activo
    }

    PREDICCIONES {
        bigint  id PK
        bigint  paciente_id FK
        bigint  modelo_id FK
        varchar riesgo_predicho
        decimal probabilidad
        jsonb   factores_clave
        timestamp fecha
    }

    SNAPSHOTS_ANALITICOS {
        bigint id PK
        date   fecha
        int    total_registros
        int    pacientes_criticos
        int    pacientes_alto
        int    pacientes_hipertensos
        int    pacientes_diabeticos
        decimal promedio_imc
        decimal promedio_glucosa
    }

    USUARIOS           ||--o{ EJECUCIONES_ETL      : "ejecuta"
    USUARIOS           ||--o{ ALERTAS               : "confirma"
    EJECUCIONES_ETL    ||--o{ LOGS_ETL              : "genera"
    EJECUCIONES_ETL    ||--o{ REGISTROS_CLINICOS    : "carga"
    PACIENTES          ||--o{ REGISTROS_CLINICOS    : "tiene"
    PACIENTES          ||--o{ ALERTAS               : "genera"
    PACIENTES          ||--o{ PREDICCIONES          : "recibe"
    MODELOS_ML         ||--o{ PREDICCIONES          : "produce"
```

## Índices de rendimiento

| Índice | Tabla | Campo(s) | Propósito |
|---|---|---|---|
| idx_registro_riesgo | registros_clinicos | riesgo_enfermedad | Filtros por riesgo |
| idx_registro_paciente | registros_clinicos | paciente_id | Joins paciente-registro |
| idx_registro_fecha | registros_clinicos | fecha_consulta DESC | Tendencias temporales |
| idx_alerta_urgencia | alertas | nivel_urgencia, fecha DESC | Dashboard alertas |
| idx_alerta_vista | alertas | fecha_vista WHERE NULL | Alertas pendientes |
| idx_etl_estado | ejecuciones_etl | estado, fecha DESC | Historial ETL |
| idx_prediccion_paciente | predicciones | paciente_id | Historial predicciones |
| idx_modelo_activo | modelos_ml | activo WHERE TRUE | Modelo activo |

## Reglas de negocio implementadas

- `riesgo_enfermedad` ∈ {Bajo, Medio, Alto, Crítico}
- `sexo` ∈ {M, F}
- `rol` ∈ {administrador, medico, analista}
- `nivel_urgencia` ∈ {baja, media, alta, critica}
- `estado` ETL ∈ {en_proceso, completado, fallido}
- `algoritmo` ML ∈ {random_forest, logistic_regression, decision_tree}
