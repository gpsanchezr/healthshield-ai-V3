-- ============================================================
-- HealthShield AI — Script SQL Completo
-- Base de datos: PostgreSQL 16
-- ============================================================

-- Extensión para UUIDs (opcional)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Tabla de usuarios ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS authentication_usuarioclinico (
    id            BIGSERIAL PRIMARY KEY,
    password      VARCHAR(128)  NOT NULL,
    last_login    TIMESTAMP     NULL,
    is_superuser  BOOLEAN       NOT NULL DEFAULT FALSE,
    username      VARCHAR(150)  NOT NULL UNIQUE,
    first_name    VARCHAR(150)  NOT NULL DEFAULT '',
    last_name     VARCHAR(150)  NOT NULL DEFAULT '',
    email         VARCHAR(254)  NOT NULL DEFAULT '',
    is_staff      BOOLEAN       NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    date_joined   TIMESTAMP     NOT NULL DEFAULT NOW(),
    rol           VARCHAR(20)   NOT NULL DEFAULT 'medico'
                  CHECK (rol IN ('administrador','medico','analista')),
    created_at    TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- ── Tabla de ejecuciones ETL ──────────────────────────────────
CREATE TABLE IF NOT EXISTS etl_ejecucionetl (
    id                    BIGSERIAL PRIMARY KEY,
    archivo_fuente        VARCHAR(255) NOT NULL DEFAULT '',
    fecha_inicio          TIMESTAMP    NOT NULL DEFAULT NOW(),
    fecha_fin             TIMESTAMP    NULL,
    duracion_segundos     NUMERIC(10,3) NULL,
    registros_extraidos   INTEGER      NOT NULL DEFAULT 0,
    registros_procesados  INTEGER      NOT NULL DEFAULT 0,
    registros_rechazados  INTEGER      NOT NULL DEFAULT 0,
    duplicados_eliminados INTEGER      NOT NULL DEFAULT 0,
    nulos_imputados       INTEGER      NOT NULL DEFAULT 0,
    estado                VARCHAR(20)  NOT NULL DEFAULT 'en_proceso'
                          CHECK (estado IN ('en_proceso','completado','fallido')),
    tipo                  VARCHAR(20)  NOT NULL DEFAULT 'manual'
                          CHECK (tipo IN ('manual','simulacion','automatico')),
    reporte_calidad       JSONB        NULL,
    usuario_id            BIGINT       NULL REFERENCES authentication_usuarioclinico(id) ON DELETE SET NULL
);

-- ── Tabla de pacientes ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS etl_paciente (
    id                    BIGSERIAL PRIMARY KEY,
    id_paciente_original  INTEGER      NOT NULL UNIQUE,
    nombres               VARCHAR(100) NOT NULL,
    apellidos             VARCHAR(100) NOT NULL,
    edad                  SMALLINT     NOT NULL CHECK (edad BETWEEN 0 AND 120),
    sexo                  VARCHAR(1)   NOT NULL CHECK (sexo IN ('M','F')),
    fecha_registro        TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- ── Tabla de registros clínicos ───────────────────────────────
CREATE TABLE IF NOT EXISTS etl_registroclinico (
    id                       BIGSERIAL PRIMARY KEY,
    peso                     NUMERIC(5,2)  NULL,
    altura                   NUMERIC(4,2)  NULL,
    imc                      NUMERIC(5,2)  NULL,
    clasificacion_imc        VARCHAR(20)   NOT NULL DEFAULT '',
    presion_sistolica        SMALLINT      NULL,
    presion_diastolica       SMALLINT      NULL,
    frecuencia_cardiaca      SMALLINT      NULL,
    glucosa                  NUMERIC(6,2)  NULL,
    colesterol               NUMERIC(6,2)  NULL,
    saturacion_oxigeno       NUMERIC(5,2)  NULL,
    temperatura              NUMERIC(4,1)  NULL,
    antecedentes_familiares  BOOLEAN       NOT NULL DEFAULT FALSE,
    fumador                  BOOLEAN       NOT NULL DEFAULT FALSE,
    consumo_alcohol          BOOLEAN       NOT NULL DEFAULT FALSE,
    actividad_fisica         VARCHAR(20)   NOT NULL DEFAULT '',
    diagnostico_preliminar   VARCHAR(100)  NOT NULL DEFAULT '',
    riesgo_enfermedad        VARCHAR(10)   NOT NULL DEFAULT 'Bajo'
                             CHECK (riesgo_enfermedad IN ('Bajo','Medio','Alto','Crítico')),
    fecha_consulta           DATE          NULL,
    created_at               TIMESTAMP     NOT NULL DEFAULT NOW(),
    paciente_id              BIGINT        NOT NULL REFERENCES etl_paciente(id) ON DELETE CASCADE,
    fuente_etl_id            BIGINT        NULL REFERENCES etl_ejecucionetl(id) ON DELETE SET NULL
);

-- ── Tabla de logs ETL ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS etl_logetl (
    id              BIGSERIAL PRIMARY KEY,
    nivel           VARCHAR(10)  NOT NULL DEFAULT 'INFO'
                    CHECK (nivel IN ('INFO','WARNING','ERROR')),
    mensaje         TEXT         NOT NULL,
    campo_afectado  VARCHAR(50)  NOT NULL DEFAULT '',
    valor_original  TEXT         NOT NULL DEFAULT '',
    valor_corregido TEXT         NOT NULL DEFAULT '',
    timestamp       TIMESTAMP    NOT NULL DEFAULT NOW(),
    ejecucion_id    BIGINT       NOT NULL REFERENCES etl_ejecucionetl(id) ON DELETE CASCADE
);

-- ── Tabla de alertas ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS etl_alerta (
    id              BIGSERIAL PRIMARY KEY,
    tipo_alerta     VARCHAR(50)  NOT NULL,
    descripcion     TEXT         NOT NULL,
    nivel_urgencia  VARCHAR(10)  NOT NULL DEFAULT 'alta'
                    CHECK (nivel_urgencia IN ('baja','media','alta','critica')),
    fecha_alerta    TIMESTAMP    NOT NULL DEFAULT NOW(),
    fecha_vista     TIMESTAMP    NULL,
    paciente_id     BIGINT       NOT NULL REFERENCES etl_paciente(id) ON DELETE CASCADE,
    visto_por_id    BIGINT       NULL REFERENCES authentication_usuarioclinico(id) ON DELETE SET NULL
);

-- ── Tabla de modelos ML ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_modeloml (
    id                      BIGSERIAL PRIMARY KEY,
    nombre                  VARCHAR(100) NOT NULL,
    algoritmo               VARCHAR(30)  NOT NULL
                            CHECK (algoritmo IN ('random_forest','logistic_regression','decision_tree')),
    version                 VARCHAR(20)  NOT NULL,
    accuracy                NUMERIC(6,4) NULL,
    precision_score         NUMERIC(6,4) NULL,
    recall                  NUMERIC(6,4) NULL,
    f1_score                NUMERIC(6,4) NULL,
    archivo_modelo          VARCHAR(255) NOT NULL,
    feature_names           JSONB        NOT NULL DEFAULT '[]',
    feature_importance      JSONB        NOT NULL DEFAULT '{}',
    entrenado_en            TIMESTAMP    NOT NULL DEFAULT NOW(),
    registros_entrenamiento INTEGER      NOT NULL DEFAULT 0,
    activo                  BOOLEAN      NOT NULL DEFAULT FALSE
);

-- ── Tabla de predicciones ────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_prediccion (
    id              BIGSERIAL PRIMARY KEY,
    riesgo_predicho VARCHAR(10)   NOT NULL,
    probabilidad    NUMERIC(5,4)  NOT NULL,
    factores_clave  JSONB         NOT NULL DEFAULT '[]',
    fecha           TIMESTAMP     NOT NULL DEFAULT NOW(),
    modelo_id       BIGINT        NULL REFERENCES ml_modeloml(id) ON DELETE SET NULL,
    paciente_id     BIGINT        NOT NULL REFERENCES etl_paciente(id) ON DELETE CASCADE
);

-- ── Tabla de snapshots analíticos ───────────────────────────
CREATE TABLE IF NOT EXISTS analytics_snapshotanalitico (
    id                    BIGSERIAL PRIMARY KEY,
    fecha                 DATE         NOT NULL DEFAULT CURRENT_DATE,
    total_registros       INTEGER      NOT NULL DEFAULT 0,
    pacientes_criticos    INTEGER      NOT NULL DEFAULT 0,
    pacientes_alto        INTEGER      NOT NULL DEFAULT 0,
    pacientes_hipertensos INTEGER      NOT NULL DEFAULT 0,
    pacientes_diabeticos  INTEGER      NOT NULL DEFAULT 0,
    promedio_imc          NUMERIC(5,2) NULL,
    promedio_glucosa      NUMERIC(6,2) NULL
);

-- ── Índices de rendimiento ───────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_registro_riesgo    ON etl_registroclinico(riesgo_enfermedad);
CREATE INDEX IF NOT EXISTS idx_registro_paciente  ON etl_registroclinico(paciente_id);
CREATE INDEX IF NOT EXISTS idx_registro_fecha     ON etl_registroclinico(fecha_consulta DESC);
CREATE INDEX IF NOT EXISTS idx_alerta_urgencia    ON etl_alerta(nivel_urgencia, fecha_alerta DESC);
CREATE INDEX IF NOT EXISTS idx_alerta_vista       ON etl_alerta(fecha_vista) WHERE fecha_vista IS NULL;
CREATE INDEX IF NOT EXISTS idx_etl_estado         ON etl_ejecucionetl(estado, fecha_inicio DESC);
CREATE INDEX IF NOT EXISTS idx_prediccion_paciente ON ml_prediccion(paciente_id);
CREATE INDEX IF NOT EXISTS idx_modelo_activo      ON ml_modeloml(activo) WHERE activo = TRUE;

-- ── Datos iniciales (superusuario) ───────────────────────────
-- NOTA: La contraseña debe ser hasheada por Django. Usar manage.py createsuperuser
-- INSERT INTO authentication_usuarioclinico (username,email,password,rol,is_staff,is_superuser,is_active,date_joined)
-- VALUES ('admin','admin@healthshield.ai','<django-hashed-password>','administrador',TRUE,TRUE,TRUE,NOW());
