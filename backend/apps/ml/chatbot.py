"""
Asistente Clínico LOCAL — consulta exclusivamente la base de datos MySQL via Django ORM.
No requiere API Keys externas ni acceso a internet.
Responde preguntas médicas basándose en los registros clínicos almacenados.
"""
import logging
from apps.etl.models import RegistroClinico, Paciente

logger = logging.getLogger('ml')


def _formatear_lista(registros, max_items=15):
    """Formatea una lista de registros clínicos para presentación médica."""
    if not registros.exists():
        return "No se encontraron pacientes con esas características en la base de datos."
    
    total = registros.count()
    lines = [f"📋 **{total} pacientes encontrados:**\n"]
    
    for r in registros.select_related('paciente')[:max_items]:
        p = r.paciente
        habitos = []
        if r.fumador: habitos.append("fumador")
        if r.consumo_alcohol: habitos.append("consume alcohol")
        hab_str = ", ".join(habitos) if habitos else "sin hábitos de riesgo"
        
        lines.append(
            f"• **{p.nombres} {p.apellidos}** (ID: {p.id_paciente_original}) | "
            f"{p.edad} años | {p.get_sexo_display()} | "
            f"Riesgo: **{r.riesgo_enfermedad}** | "
            f"Dx: {r.diagnostico_preliminar or 'N/A'} | "
            f"Glucosa: {r.glucosa or 'N/A'} mg/dL | "
            f"Presión: {r.presion_sistolica or 'N/A'}/{r.presion_diastolica or 'N/A'} | "
            f"{hab_str} | Actividad: {r.actividad_fisica or 'N/A'}"
        )
    
    if total > max_items:
        lines.append(f"\n_...y {total - max_items} pacientes más. Usa los filtros del Dashboard para ver todos._")
    
    return "\n".join(lines)


def get_clinical_answer(query: str) -> str:
    """
    Motor de consulta clínica local.
    Analiza la pregunta del médico y consulta MySQL vía Django ORM.
    """
    try:
        qs = RegistroClinico.objects.select_related('paciente').all()
        q = query.lower()

        # ─── DIABETES ────────────────────────────────────────────────────────────
        if any(k in q for k in ['diabet', 'glucosa alta', 'azúcar', 'azucar', 'insulina']):
            umbral = 200 if 'muy alta' in q or 'critico' in q or 'crítico' in q else 125
            pacientes = qs.filter(glucosa__gt=umbral)
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"🩸 **Análisis de riesgo diabético** (Glucosa > {umbral} mg/dL)\n\n"
                f"Se identificaron **{total} pacientes** propensos a diabetes:\n\n{lista}\n\n"
                f"ℹ️ _El umbral diagnóstico estándar para diabetes es glucosa en ayuno > 125 mg/dL (ADA 2024)._"
            )

        # ─── HIPERTENSIÓN ─────────────────────────────────────────────────────────
        elif any(k in q for k in ['hiperten', 'presion alta', 'presión alta', 'tension arterial', 'tensión arterial']):
            umbral = 160 if 'grado 2' in q or 'severo' in q else 140
            pacientes = qs.filter(presion_sistolica__gt=umbral)
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"❤️ **Análisis de Hipertensión** (Presión sistólica > {umbral} mmHg)\n\n"
                f"Se identificaron **{total} pacientes** hipertensos:\n\n{lista}\n\n"
                f"ℹ️ _Criterio: Presión sistólica > 140 mmHg (JNC 8 / ESC 2023)._"
            )

        # ─── FUMADORES ───────────────────────────────────────────────────────────
        elif any(k in q for k in ['fumador', 'fuman', 'tabaco', 'cigarro', 'cigarrillo']):
            pacientes = qs.filter(fumador=True)
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"🫁 **Pacientes Fumadores**\n\n"
                f"Se identificaron **{total} pacientes** fumadores en la base de datos:\n\n{lista}"
            )

        # ─── OBESIDAD / IMC ───────────────────────────────────────────────────────
        elif any(k in q for k in ['obeso', 'obesi', 'sobrepeso', 'imc', 'peso']):
            if 'sobrepeso' in q:
                pacientes = qs.filter(imc__gte=25, imc__lt=30)
                label = "Sobrepeso (IMC 25–29.9)"
            else:
                pacientes = qs.filter(imc__gte=30)
                label = "Obesidad (IMC ≥ 30)"
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"⚖️ **Pacientes con {label}**\n\n"
                f"Se identificaron **{total} pacientes**:\n\n{lista}"
            )

        # ─── SEDENTARIOS / FITNESS ────────────────────────────────────────────────
        elif any(k in q for k in ['sedentario', 'actividad física', 'actividad fisica', 'ejercicio', 'deport', 'fitness']):
            if 'sedent' in q:
                pacientes = qs.filter(actividad_fisica__iexact='Sedentaria')
                label = "Sedentarios"
            elif 'alta' in q or 'deport' in q or 'intensiv' in q:
                pacientes = qs.filter(actividad_fisica__iexact='Alta')
                label = "Actividad Alta (Deportistas)"
            elif 'media' in q or 'moderada' in q:
                pacientes = qs.filter(actividad_fisica__iexact='Media')
                label = "Actividad Media"
            elif 'baja' in q:
                pacientes = qs.filter(actividad_fisica__iexact='Baja')
                label = "Actividad Baja"
            else:
                from django.db.models import Count
                dist = qs.values('actividad_fisica').annotate(total=Count('id')).order_by('-total')
                lines = ["🏃 **Distribución de Actividad Física:**\n"]
                for d in dist:
                    nivel = d['actividad_fisica'] or 'No registrado'
                    lines.append(f"• **{nivel}**: {d['total']} pacientes")
                return "\n".join(lines)
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return f"🏃 **Pacientes con {label}**\n\nSe encontraron **{total} pacientes**:\n\n{lista}"

        # ─── CRÍTICOS ─────────────────────────────────────────────────────────────
        elif any(k in q for k in ['crítico', 'critico', 'urgente', 'emergencia', 'grave']):
            pacientes = qs.filter(riesgo_enfermedad='Crítico')
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"🚨 **Pacientes en Estado Crítico**\n\n"
                f"Se identificaron **{total} pacientes** con riesgo CRÍTICO:\n\n{lista}\n\n"
                f"⚠️ _Estos pacientes requieren atención médica inmediata._"
            )

        # ─── ALCOHOL ─────────────────────────────────────────────────────────────
        elif any(k in q for k in ['alcohol', 'bebida', 'licor', 'trago']):
            pacientes = qs.filter(consumo_alcohol=True)
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"🍺 **Pacientes con Consumo de Alcohol**\n\n"
                f"Se identificaron **{total} pacientes** con consumo de alcohol:\n\n{lista}"
            )

        # ─── COLESTEROL ───────────────────────────────────────────────────────────
        elif any(k in q for k in ['colesterol', 'dislipidemia', 'triglicerido']):
            pacientes = qs.filter(colesterol__gt=200)
            total = pacientes.count()
            lista = _formatear_lista(pacientes)
            return (
                f"🧪 **Pacientes con Colesterol Elevado** (> 200 mg/dL)\n\n"
                f"Se identificaron **{total} pacientes**:\n\n{lista}"
            )

        # ─── RESUMEN ESTADÍSTICO GENERAL ─────────────────────────────────────────
        elif any(k in q for k in ['resumen', 'estadística', 'estadistica', 'estadisticas', 'total', 'cuántos', 'cuantos', 'resumen general']):
            total = qs.count()
            from django.db.models import Avg
            aggs = qs.aggregate(avg_glucosa=Avg('glucosa'), avg_imc=Avg('imc'), avg_presion=Avg('presion_sistolica'))
            return (
                f"📊 **Resumen Estadístico General**\n\n"
                f"• Total registros: **{total}**\n"
                f"• Pacientes críticos: **{qs.filter(riesgo_enfermedad='Crítico').count()}**\n"
                f"• Pacientes hipertensos: **{qs.filter(presion_sistolica__gt=140).count()}**\n"
                f"• Pacientes diabéticos (glucosa>125): **{qs.filter(glucosa__gt=125).count()}**\n"
                f"• Fumadores: **{qs.filter(fumador=True).count()}**\n"
                f"• Consumen alcohol: **{qs.filter(consumo_alcohol=True).count()}**\n"
                f"• Sedentarios: **{qs.filter(actividad_fisica__iexact='Sedentaria').count()}**\n"
                f"• Glucosa promedio: **{round(float(aggs['avg_glucosa'] or 0), 1)} mg/dL**\n"
                f"• IMC promedio: **{round(float(aggs['avg_imc'] or 0), 1)}**\n"
                f"• Presión sistólica prom.: **{round(float(aggs['avg_presion'] or 0), 0)} mmHg**\n"
            )

        # ─── BÚSQUEDA POR NOMBRE ─────────────────────────────────────────────────
        elif any(k in q for k in ['paciente', 'buscar', 'encontrar', 'quién es', 'quien es', 'informacion de', 'información de']):
            # Extraer posible nombre del query
            palabras = [w for w in query.split() if len(w) > 3 and w.lower() not in
                        ['paciente', 'buscar', 'dame', 'muestra', 'quien', 'quién', 'información', 'informacion', 'datos']]
            if palabras:
                nombre_buscar = palabras[0]
                pacientes = qs.filter(
                    paciente__nombres__icontains=nombre_buscar
                ) | qs.filter(
                    paciente__apellidos__icontains=nombre_buscar
                )
                if pacientes.exists():
                    return f"🔍 **Resultados para '{nombre_buscar}':**\n\n{_formatear_lista(pacientes)}"
            return (
                "🔍 No pude identificar un nombre específico en tu consulta.\n\n"
                "**Ejemplos de preguntas que puedo responder:**\n"
                "• '¿Qué pacientes están propensos a sufrir diabetes?'\n"
                "• '¿Cuántos pacientes son hipertensos?'\n"
                "• '¿Quiénes son los pacientes críticos?'\n"
                "• '¿Qué pacientes son fumadores?'\n"
                "• 'Dame un resumen estadístico'\n"
                "• '¿Qué pacientes tienen obesidad?'\n"
                "• '¿Cuántos son sedentarios?'"
            )

        # ─── AYUDA / FALLBACK ─────────────────────────────────────────────────────
        else:
            return (
                "🤖 **Asistente Clínico HealthShield AI**\n\n"
                "No reconocí esa consulta, pero puedo ayudarte con:\n\n"
                "• **Diabetes:** _¿Qué pacientes están propensos a diabetes?_\n"
                "• **Hipertensión:** _¿Cuántos pacientes hipertensos hay?_\n"
                "• **Fumadores:** _Lista los pacientes fumadores_\n"
                "• **Obesidad:** _¿Quiénes tienen obesidad?_\n"
                "• **Críticos:** _¿Quiénes son los pacientes críticos?_\n"
                "• **Alcohol:** _¿Quiénes consumen alcohol?_\n"
                "• **Fitness:** _¿Cuántos pacientes son sedentarios?_\n"
                "• **Resumen:** _Dame un resumen estadístico_\n\n"
                f"_Base de datos activa: {RegistroClinico.objects.count()} registros clínicos._"
            )

    except Exception as e:
        logger.error(f"Error en ChatBot Clínico Local: {str(e)}")
        return f"⚠️ Error al consultar la base de datos: {str(e)}"
