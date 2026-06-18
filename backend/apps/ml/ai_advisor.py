"""
ClinicalAdvisor: Integración con Claude API para análisis médico generativo.
Dado un paciente con sus datos clínicos y predicción de riesgo, genera
un análisis narrativo con recomendaciones clínicas en lenguaje natural.

Requiere: ANTHROPIC_API_KEY en variables de entorno.
"""
from typing import Dict, Any, Optional
import json
import logging
import urllib.request
import urllib.error
import os

logger = logging.getLogger('ml')

SYSTEM_PROMPT = """Eres un asistente clínico especializado en medicina preventiva.
Recibes datos clínicos de un paciente y debes generar un análisis conciso en español.

Tu respuesta SIEMPRE debe tener exactamente estas 3 secciones (sin más texto):
1. RESUMEN CLÍNICO (2-3 oraciones sobre el estado del paciente)
2. FACTORES DE RIESGO IDENTIFICADOS (lista de máximo 4 puntos)
3. RECOMENDACIONES (lista de máximo 3 recomendaciones concretas y accionables)

Usa lenguaje clínico profesional pero comprensible. NO hagas diagnósticos definitivos.
Incluye siempre una nota de que estas son sugerencias basadas en datos y no reemplazan la evaluación médica presencial."""


class ClinicalAdvisor:
    """
    Genera análisis clínico narrativo usando Claude API.
    Proporciona explicabilidad adicional al modelo ML (XAI narrativo).
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    MODEL   = "claude-sonnet-4-20250514"

    def __init__(self) -> None:
        self.api_key: Optional[str] = os.environ.get('ANTHROPIC_API_KEY')

    def analizar_paciente(
        self,
        datos_paciente: Dict[str, Any],
        prediccion: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Genera análisis narrativo de un paciente.

        Args:
            datos_paciente: Dict con campos clínicos del paciente
            prediccion:     Dict con riesgo_predicho, probabilidades y factores_clave

        Returns:
            Dict con análisis narrativo o mensaje de error
        """
        if not self.api_key:
            return {
                'disponible': False,
                'error': 'ANTHROPIC_API_KEY no configurada. Agrega la clave en el archivo .env',
            }

        prompt = self._construir_prompt(datos_paciente, prediccion)

        try:
            payload = json.dumps({
                'model':      self.MODEL,
                'max_tokens': 600,
                'system':     SYSTEM_PROMPT,
                'messages':   [{'role': 'user', 'content': prompt}],
            }).encode('utf-8')

            req = urllib.request.Request(
                self.API_URL,
                data=payload,
                headers={
                    'Content-Type':      'application/json',
                    'x-api-key':         self.api_key,
                    'anthropic-version': '2023-06-01',
                },
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                texto = data['content'][0]['text']

            return {
                'disponible':  True,
                'analisis':    texto,
                'modelo_ia':   self.MODEL,
                'tokens_usados': data.get('usage', {}).get('output_tokens', 0),
            }

        except urllib.error.HTTPError as e:
            logger.error(f"Claude API HTTP error: {e.code} {e.reason}")
            return {'disponible': False, 'error': f'Error API: {e.code} — {e.reason}'}
        except Exception as exc:
            logger.error(f"Claude API error: {exc}")
            return {'disponible': False, 'error': 'Servicio de IA no disponible temporalmente'}

    @staticmethod
    def _construir_prompt(datos: Dict[str, Any], pred: Dict[str, Any]) -> str:
        factores = pred.get('factores_clave', [])
        factores_str = '\n'.join(
            f"  - {f['variable'].replace('_',' ')}: valor={f.get('valor_paciente','?')} "
            f"(importancia={f.get('importancia',0):.1%})"
            for f in factores
        )
        return f"""Analiza el siguiente paciente clínico:

DATOS DEL PACIENTE:
- Edad: {datos.get('edad', '?')} años | Sexo: {datos.get('sexo', '?')}
- IMC: {datos.get('imc', '?')} ({datos.get('clasificacion_imc', '?')})
- Presión arterial: {datos.get('presion_sistolica', '?')}/{datos.get('presion_diastolica', '?')} mmHg
- Glucosa: {datos.get('glucosa', '?')} mg/dL
- Colesterol: {datos.get('colesterol', '?')} mg/dL
- Saturación O₂: {datos.get('saturacion_oxigeno', '?')}%
- Frecuencia cardíaca: {datos.get('frecuencia_cardiaca', '?')} bpm
- Fumador: {'Sí' if datos.get('fumador') else 'No'}
- Consumo alcohol: {'Sí' if datos.get('consumo_alcohol') else 'No'}
- Antecedentes familiares: {'Sí' if datos.get('antecedentes_familiares') else 'No'}
- Diagnóstico preliminar: {datos.get('diagnostico_preliminar', '?')}
- Actividad física: {datos.get('actividad_fisica', '?')}

PREDICCIÓN DEL MODELO ML:
- Nivel de riesgo: {pred.get('riesgo_predicho', '?')}
- Probabilidad: {pred.get('probabilidad_max', 0):.1%}
- Variables determinantes:
{factores_str if factores_str else '  (no disponible)'}

Genera el análisis clínico siguiendo exactamente el formato indicado en el sistema."""
