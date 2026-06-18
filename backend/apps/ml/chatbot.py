"""
Explorador Inteligente de Datos Global para HealthShield AI.

Esta versión construye un mega-contexto usando Django ORM sobre todas las tablas
relevantes de apps.etl.models. Cuando GEMINI_API_KEY está disponible, utiliza el
SDK google.generativeai y el modelo gemini-1.5-flash. Si no hay clave, devuelve
un reporte de respaldo local con la información extraída directamente de MySQL.
"""

import logging
import os
from typing import Optional

from django.db.models import Avg, Count, Q, Sum
from apps.etl.models import Alerta, EjecucionETL, LogETL, Paciente, RegistroClinico

logger = logging.getLogger('ml')

try:
    import google.generativeai as genai
except ImportError:
    genai = None

GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = 'gemini-1.5-flash'


def _configure_gemini() -> bool:
    if genai is None or not GEMINI_KEY:
        return False
    try:
        if hasattr(genai, 'configure'):
            genai.configure(api_key=GEMINI_KEY)
        return True
    except Exception as exc:
        logger.warning('No se pudo configurar Gemini: %s', exc)
        return False


def _safe_round(value: Optional[float], digits: int = 1) -> float:
    if value is None:
        return 0.0
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def _extract_global_context() -> str:
    pacientes_totales = Paciente.objects.count()
    consultas_totales = RegistroClinico.objects.count()

    medias = RegistroClinico.objects.aggregate(
        avg_glucosa=Avg('glucosa'),
        avg_imc=Avg('imc'),
        avg_presion_sistolica=Avg('presion_sistolica'),
        avg_presion_diastolica=Avg('presion_diastolica'),
        avg_frecuencia=Avg('frecuencia_cardiaca'),
        avg_temperatura=Avg('temperatura'),
        avg_saturacion=Avg('saturacion_oxigeno'),
    )

    riesgo_dist = RegistroClinico.objects.values('riesgo_enfermedad').annotate(total=Count('id')).order_by('-total')
    riesgo_map = {row['riesgo_enfermedad'] or 'Sin riesgo definido': row['total'] for row in riesgo_dist}

    etl_totales = EjecucionETL.objects.aggregate(
        total_ejecuciones=Count('id'),
        total_procesados=Sum('registros_procesados'),
        total_rechazados=Sum('registros_rechazados'),
        total_duplicados=Sum('duplicados_eliminados'),
        total_nulos=Sum('nulos_imputados'),
    )
    etl_completadas = EjecucionETL.objects.filter(estado='completado').count()
    etl_fallidas = EjecucionETL.objects.filter(estado='fallido').count()
    etl_tipos = EjecucionETL.objects.values('tipo').annotate(total=Count('id')).order_by('tipo')

    log_totales = LogETL.objects.values('nivel').annotate(total=Count('id')).order_by('nivel')
    ultimos_logs = LogETL.objects.filter(nivel__in=['WARNING', 'ERROR']).order_by('-timestamp')[:5]

    alertas_totales = Alerta.objects.count()
    alertas_criticas = Alerta.objects.filter(nivel_urgencia='critica').count()
    alertas_pendientes = Alerta.objects.filter(fecha_vista__isnull=True).count()

    lines = [
        '### Contexto Global HealthShield AI',
        f'- Pacientes únicos: {pacientes_totales}',
        f'- Consultas registradas: {consultas_totales}',
        f'- Glucosa promedio: {_safe_round(medias.get("avg_glucosa"))} mg/dL',
        f'- IMC promedio: {_safe_round(medias.get("avg_imc"))}',
        f'- Presión sistólica promedio: {_safe_round(medias.get("avg_presion_sistolica"), 0)} mmHg',
        f'- Presión diastólica promedio: {_safe_round(medias.get("avg_presion_diastolica"), 0)} mmHg',
        f'- Frecuencia cardiaca promedio: {_safe_round(medias.get("avg_frecuencia"), 0)} lpm',
        f'- Temperatura promedio: {_safe_round(medias.get("avg_temperatura"), 1)} °C',
        f'- Saturación de oxígeno promedio: {_safe_round(medias.get("avg_saturacion"), 1)} %',
        '',
        '#### Distribución de riesgo clínico',
    ]

    for nivel in ['Bajo', 'Medio', 'Alto', 'Crítico']:
        lines.append(f'- {nivel}: {riesgo_map.get(nivel, 0)}')
    if 'Sin riesgo definido' in riesgo_map:
        lines.append(f'- Sin riesgo definido: {riesgo_map.get("Sin riesgo definido", 0)}')

    lines.extend([
        '',
        '### Estado histórico del ETL',
        f'- Ejecuciones totales: {etl_totales.get("total_ejecuciones", 0)}',
        f'- Completadas: {etl_completadas}',
        f'- Fallidas: {etl_fallidas}',
    ])
    for item in etl_tipos:
        tipo = item['tipo'] or 'sin tipo'
        lines.append(f'- Tipo {tipo}: {item["total"]}')

    lines.extend([
        f'- Registros procesados acumulados: {etl_totales.get("total_procesados") or 0}',
        f'- Registros rechazados acumulados: {etl_totales.get("total_rechazados") or 0}',
        f'- Duplicados eliminados acumulados: {etl_totales.get("total_duplicados") or 0}',
        f'- Nulos imputados acumulados: {etl_totales.get("total_nulos") or 0}',
        '',
        '### Auditoría de calidad de datos',
    ])
    for log in log_totales:
        lines.append(f'- Logs {log["nivel"]}: {log["total"]}')

    if ultimos_logs:
        lines.append('Últimos 5 mensajes de WARNING/ERROR:')
        for log in ultimos_logs:
            lines.append(f'- [{log.nivel}] {log.timestamp}: {log.mensaje}')
    else:
        lines.append('- No hay logs recientes de WARNING/ERROR.')

    lines.extend([
        '',
        '### Alerta y triage',
        f'- Alertas totales: {alertas_totales}',
        f'- Alertas críticas: {alertas_criticas}',
        f'- Alertas pendientes de revisión: {alertas_pendientes}',
    ])

    return '\n'.join(lines)


def _extract_patient_history(query: str) -> Optional[str]:
    query_lower = query.lower()
    search_keywords = ['paciente', 'nombre', 'buscar', 'historial', 'mostrar', 'encontrar', 'datos']
    if not any(keyword in query_lower for keyword in search_keywords):
        return None

    tokens = [token.strip() for token in query.split() if len(token.strip()) > 3]
    if not tokens:
        return None

    q_objects = Q()
    for token in tokens[:4]:
        q_objects |= Q(paciente__nombres__icontains=token) | Q(paciente__apellidos__icontains=token)

    registros = RegistroClinico.objects.select_related('paciente').filter(q_objects).order_by('-fecha_consulta')[:6]
    if not registros.exists():
        return None

    lines = ['### Historial clínico relevante encontrado en la base de datos:']
    seen_patients = set()
    for registro in registros:
        paciente = registro.paciente
        if paciente.id in seen_patients:
            continue
        seen_patients.add(paciente.id)
        lines.append(
            f'- **{paciente.nombres} {paciente.apellidos}** (ID {paciente.id_paciente_original}) | '
            f'Edad: {paciente.edad} | Sexo: {paciente.get_sexo_display()} | Fecha consulta: {registro.fecha_consulta} | '
            f'Riesgo: {registro.riesgo_enfermedad} | Dx: {registro.diagnostico_preliminar or "N/A"} | '
            f'Glucosa: {registro.glucosa or "N/A"} | Presión: {registro.presion_sistolica or "N/A"}/{registro.presion_diastolica or "N/A"} | '
            f'FC: {registro.frecuencia_cardiaca or "N/A"} | SatO₂: {registro.saturacion_oxigeno or "N/A"} | Temp: {registro.temperatura or "N/A"}'
        )
        if len(seen_patients) >= 3:
            break

    if seen_patients:
        return '\n'.join(lines)
    return None


def _compose_system_prompt(global_context: str, patient_context: Optional[str]) -> str:
    prompt = [
        'Eres un asistente clínico y de operaciones de HealthShield AI. Tu tarea es analizar datos reales extraídos de la base de datos y responder en español con precisión, profesionalismo y estilo médico. Usa Markdown en tu respuesta: títulos, secciones, viñetas, énfasis y tablas cuando sea útil. No inventes cifras; usa solo los datos que te proporciona el contexto.',
        '',
        'Contexto global extraído de la base de datos:',
        global_context,
    ]
    if patient_context:
        prompt.extend(['', 'Contexto de historial de paciente específico:', patient_context])
    prompt.extend([
        '',
        'Instrucciones adicionales:',
        '- Responde cualquier pregunta libre del médico o analista sobre datos clínicos, ETL, alertas, calidad de datos y triage.',
        '- Si el usuario pregunta por la calidad del último Excel, usa los últimos logs de warning/error disponibles.',
        '- Si no hay suficiente información específica, explica claramente qué datos faltan y qué se puede revisar en la plataforma.',
        '',
        'Respuesta esperada en español:',
    ])
    return '\n'.join(prompt)


def _ask_gemini(prompt: str) -> Optional[str]:
    if genai is None or not GEMINI_KEY:
        return None

    if not _configure_gemini():
        return None

    try:
        if hasattr(genai, 'generate_text'):
            response = genai.generate_text(
                model=GEMINI_MODEL,
                prompt=prompt,
                temperature=0.2,
                max_output_tokens=700,
            )
            if isinstance(response, dict):
                return response.get('output_text') or response.get('content') or str(response)
            return getattr(response, 'output_text', None) or getattr(response, 'content', None) or str(response)

        if hasattr(genai, 'ResponsesClient'):
            client = genai.ResponsesClient()
            result = client.create(
                model=GEMINI_MODEL,
                input=prompt,
                temperature=0.2,
                max_output_tokens=700,
            )
            if hasattr(result, 'output') and hasattr(result.output, 'text'):
                return result.output.text
            if hasattr(result, 'candidates'):
                candidate = result.candidates[0] if result.candidates else None
                return getattr(candidate, 'content', None) or str(result)

        return None
    except Exception as exc:
        logger.warning('Gemini request falló: %s', exc)
        return None


def _build_medical_safe_global_context() -> str:
    """
    Resumen clínico para médicos: SOLO métricas clínicas básicas.
    Prohibido incluir secciones técnicas de ETL/auditoría.
    """
    pacientes_totales = Paciente.objects.count()
    medias = RegistroClinico.objects.aggregate(
        avg_glucosa=Avg('glucosa'),
        avg_imc=Avg('imc'),
    )

    return '\n'.join([
        '### Resumen clínico (datos reales)',
        f'- Pacientes únicos: {pacientes_totales}',
        f'- Glucosa promedio: {_safe_round(medias.get("avg_glucosa"))} mg/dL',
        f'- IMC promedio: {_safe_round(medias.get("avg_imc"))}',
    ])


def _format_patient_identity(paciente: Paciente) -> str:
    cedula = getattr(paciente, 'cedula', None)
    if not cedula:
        cedula = getattr(paciente, 'documento', None)
    cedula_str = str(cedula) if cedula is not None else 'N/A'
    return f'{paciente.nombres} {paciente.apellidos} | Cédula: {cedula_str}'


def _local_clinical_fallback(query: str) -> str:
    """
    Modo respaldo local: asistente clínico real usando ORM y respuestas comprensibles.
    """
    query_lower = (query or '').lower()

    # 1) Diabetes / Diabéticos (glucosa > 125)
    if 'diabetes' in query_lower or 'diabéticos' in query_lower or 'diabeticos' in query_lower:
        registros = (
            RegistroClinico.objects
            .filter(glucosa__gt=125)
            .select_related('paciente')[:5]
        )
        total = RegistroClinico.objects.filter(glucosa__gt=125).count()

        if total == 0:
            return '\n'.join([
                '### Diabetes / Riesgo de diabetes',
                'No se encontraron pacientes con glucosa > 125 mg/dL en la base de datos.',
            ])

        lines = [
            '### Diabetes / Riesgo de diabetes',
            f'Pacientes en riesgo (glucosa > 125 mg/dL): {total}',
            '',
            '#### Top 5 pacientes (por glucosa registrada)',
        ]
        for r in registros:
            p = r.paciente
            lines.append(f'- {_format_patient_identity(p)} | Glucosa: {r.glucosa}')
        return '\n'.join(lines)

    # 2) Hipertensión / Hipertensos (presión sistólica > 140)
    if 'hipertension' in query_lower or 'hipertensión' in query_lower or 'hipertensos' in query_lower:
        registros = (
            RegistroClinico.objects
            .filter(presion_sistolica__gt=140)
            .select_related('paciente')[:5]
        )
        total = RegistroClinico.objects.filter(presion_sistolica__gt=140).count()

        if total == 0:
            return '\n'.join([
                '### Hipertensión / Riesgo de hipertensión',
                'No se encontraron pacientes con presión sistólica > 140 mmHg en la base de datos.',
            ])

        lines = [
            '### Hipertensión / Riesgo de hipertensión',
            f'Pacientes en riesgo (presión sistólica > 140 mmHg): {total}',
            '',
            '#### Top 5 pacientes (por presión sistólica registrada)',
        ]
        for r in registros:
            p = r.paciente
            lines.append(f'- {_format_patient_identity(p)} | Presión sistólica: {r.presion_sistolica}')
        return '\n'.join(lines)

    # 3) Críticos / Riesgo alto (riesgo_enfermedad = Crítico)
    if 'criticos' in query_lower or 'críticos' in query_lower or 'riesgo alto' in query_lower:
        registros = (
            RegistroClinico.objects
            .filter(riesgo_enfermedad__iexact='Crítico')
            .select_related('paciente')[:5]
        )
        total = RegistroClinico.objects.filter(riesgo_enfermedad__iexact='Crítico').count()

        if total == 0:
            return '\n'.join([
                '### Pacientes críticos',
                'No se encontraron pacientes con riesgo clínico marcado como “Crítico”.',
            ])

        lines = [
            '### Pacientes críticos',
            f'Pacientes con riesgo “Crítico”: {total}',
            '',
            '#### Top 5 pacientes (según registros)',
        ]
        for r in registros:
            p = r.paciente
            lines.append(f'- {_format_patient_identity(p)} | Riesgo: {r.riesgo_enfermedad} | Glucosa: {r.glucosa}')
        return '\n'.join(lines)

    # 4) Genérico / no coincide: contexto global resumido (sin ETL ni auditoría)
    return _build_medical_safe_global_context()


def get_clinical_answer(query: str) -> str:
    if not query or not query.strip():
        return 'La consulta no puede estar vacía. Describe tu pregunta clínica u operativa.'

    global_context = _extract_global_context()
    patient_context = _extract_patient_history(query)
    system_prompt = _compose_system_prompt(global_context, patient_context)

    gemini_response = _ask_gemini(system_prompt + '\n\nPregunta del usuario:\n' + query)
    if gemini_response:
        return gemini_response.strip()

    # Si Gemini no está disponible o no respondió, hacemos fallback local clínico real
    # (sin secciones técnicas y con consultas ORM específicas por keywords).
    logger.warning('Usando modo respaldo local clínico (sin Gemini o sin respuesta válida).')
    return _local_clinical_fallback(query)
