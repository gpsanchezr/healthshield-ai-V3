"""
MultiAIProvider: Abstracción para múltiples proveedores de IA generativa.
Soporta Claude (Anthropic) y Gemini (Google). El proveedor se selecciona
dinámicamente desde la request o desde la configuración del sistema.

Principio SOLID: Open/Closed — agregar un nuevo proveedor = nueva clase,
sin modificar el código existente.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import logging
import urllib.request
import urllib.error
import os

logger = logging.getLogger('ml')

# ── Prompt clínico compartido ──────────────────────────────────────────────────
SYSTEM_PROMPT_ES = """Eres un asistente clínico especializado en medicina preventiva.
Recibes datos clínicos de un paciente y debes generar un análisis conciso en español.

Tu respuesta SIEMPRE debe tener exactamente estas 3 secciones:
1. RESUMEN CLÍNICO (2-3 oraciones sobre el estado del paciente)
2. FACTORES DE RIESGO IDENTIFICADOS (lista de máximo 4 puntos)
3. RECOMENDACIONES (lista de máximo 3 recomendaciones concretas y accionables)

Usa lenguaje clínico profesional. NO hagas diagnósticos definitivos.
Incluye siempre al final: "Nota: este análisis es orientativo y no reemplaza la evaluación médica presencial."
"""


def construir_prompt_clinico(datos: Dict[str, Any], pred: Dict[str, Any]) -> str:
    """Construye el prompt clínico estructurado para cualquier proveedor."""
    factores = pred.get('factores_clave', [])
    factores_str = '\n'.join(
        f"  - {f['variable'].replace('_',' ')}: valor={f.get('valor_paciente','?')} "
        f"(importancia={float(f.get('importancia', 0)):.1%})"
        for f in factores
    ) or '  (no disponible)'

    return f"""Analiza el siguiente paciente clínico:

DATOS DEL PACIENTE:
- Edad: {datos.get('edad','?')} años | Sexo: {datos.get('sexo','?')}
- IMC: {datos.get('imc','?')} ({datos.get('clasificacion_imc','Normal')})
- Presión arterial: {datos.get('presion_sistolica','?')}/{datos.get('presion_diastolica','?')} mmHg
- Glucosa: {datos.get('glucosa','?')} mg/dL | Colesterol: {datos.get('colesterol','?')} mg/dL
- Saturación O₂: {datos.get('saturacion_oxigeno','?')}% | FC: {datos.get('frecuencia_cardiaca','?')} bpm
- Fumador: {'Sí' if datos.get('fumador') else 'No'} | Alcohol: {'Sí' if datos.get('consumo_alcohol') else 'No'}
- Antecedentes familiares: {'Sí' if datos.get('antecedentes_familiares') else 'No'}
- Diagnóstico preliminar: {datos.get('diagnostico_preliminar','?')}
- Actividad física: {datos.get('actividad_fisica','?')}

PREDICCIÓN DEL MODELO ML:
- Nivel de riesgo: {pred.get('riesgo_predicho','?')} ({pred.get('probabilidad_max',0):.1%} de probabilidad)
- Variables determinantes:
{factores_str}

Genera el análisis clínico siguiendo exactamente el formato indicado."""


# ── Base abstracta ─────────────────────────────────────────────────────────────
class BaseAIProvider(ABC):
    """Interfaz base para proveedores de IA generativa."""

    nombre: str = 'Base'

    @abstractmethod
    def esta_disponible(self) -> bool:
        """Retorna True si la API key está configurada."""
        ...

    @abstractmethod
    def analizar(self, prompt: str) -> Dict[str, Any]:
        """Envía el prompt y retorna el análisis."""
        ...

    def analizar_paciente(
        self,
        datos_paciente: Dict[str, Any],
        prediccion: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Template method: construye prompt y llama a analizar()."""
        if not self.esta_disponible():
            return {
                'disponible': False,
                'proveedor': self.nombre,
                'error': f'API key de {self.nombre} no configurada en .env',
            }
        prompt = construir_prompt_clinico(datos_paciente, prediccion)
        resultado = self.analizar(prompt)
        resultado['proveedor'] = self.nombre
        return resultado


# ── Proveedor Claude (Anthropic) ───────────────────────────────────────────────
class ClaudeProvider(BaseAIProvider):
    """
    Proveedor Claude de Anthropic.
    Requiere: ANTHROPIC_API_KEY en variables de entorno.
    Modelo: claude-sonnet-4-20250514
    """

    nombre  = 'Claude (Anthropic)'
    API_URL = 'https://api.anthropic.com/v1/messages'
    MODEL   = 'claude-sonnet-4-20250514'

    def __init__(self) -> None:
        self.api_key: Optional[str] = os.environ.get('ANTHROPIC_API_KEY')

    def esta_disponible(self) -> bool:
        return bool(self.api_key)

    def analizar(self, prompt: str) -> Dict[str, Any]:
        try:
            payload = json.dumps({
                'model':      self.MODEL,
                'max_tokens': 700,
                'system':     SYSTEM_PROMPT_ES,
                'messages':   [{'role': 'user', 'content': prompt}],
            }).encode('utf-8')

            req = urllib.request.Request(
                self.API_URL, data=payload,
                headers={
                    'Content-Type':      'application/json',
                    'x-api-key':         self.api_key,
                    'anthropic-version': '2023-06-01',
                },
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            return {
                'disponible':     True,
                'analisis':       data['content'][0]['text'],
                'modelo':         self.MODEL,
                'tokens_entrada': data.get('usage', {}).get('input_tokens', 0),
                'tokens_salida':  data.get('usage', {}).get('output_tokens', 0),
            }
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore')[:200]
            logger.error(f"Claude API {e.code}: {e.reason} — {body}")
            if e.code == 401:
                msg = 'ANTHROPIC_API_KEY inválida. Verifica tu clave en console.anthropic.com'
            elif e.code == 429:
                msg = 'Límite de uso de Claude API alcanzado. Intenta en unos minutos.'
            elif e.code == 500:
                msg = 'Error interno de Claude API. Intenta con Gemini.'
            else:
                msg = f'Claude API error {e.code}: {e.reason}'
            return {'disponible': False, 'error': msg}
        except TimeoutError:
            return {'disponible': False, 'error': f'Claude no respondió en {self.TIMEOUT}s. Intenta con Gemini.'}
        except Exception as exc:
            logger.error(f"Claude error: {exc}")
            return {'disponible': False, 'error': f'Claude no disponible: {str(exc)[:100]}'}


# ── Proveedor Gemini (Google) ──────────────────────────────────────────────────
class GeminiProvider(BaseAIProvider):
    """
    Proveedor Gemini de Google.
    Requiere: GEMINI_API_KEY en variables de entorno.
    Modelo: gemini-1.5-flash (rápido y gratuito en tier básico)
    """

    nombre  = 'Gemini (Google)'
    MODEL   = 'gemini-1.5-flash'

    def __init__(self) -> None:
        self.api_key: Optional[str] = os.environ.get('GEMINI_API_KEY')

    @property
    def API_URL(self) -> str:
        return (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{self.MODEL}:generateContent?key={self.api_key}'
        )

    def esta_disponible(self) -> bool:
        return bool(self.api_key)

    def analizar(self, prompt: str) -> Dict[str, Any]:
        try:
            full_prompt = SYSTEM_PROMPT_ES + '\n\n' + prompt
            payload = json.dumps({
                'contents': [{'parts': [{'text': full_prompt}]}],
                'generationConfig': {
                    'maxOutputTokens': 700,
                    'temperature':     0.4,
                    'topP':            0.9,
                },
            }).encode('utf-8')

            req = urllib.request.Request(
                self.API_URL, data=payload,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            texto = (
                data.get('candidates', [{}])[0]
                    .get('content', {})
                    .get('parts', [{}])[0]
                    .get('text', 'Sin respuesta')
            )
            uso = data.get('usageMetadata', {})
            return {
                'disponible':     True,
                'analisis':       texto,
                'modelo':         self.MODEL,
                'tokens_entrada': uso.get('promptTokenCount', 0),
                'tokens_salida':  uso.get('candidatesTokenCount', 0),
            }
        except urllib.error.HTTPError as e:
            logger.error(f"Gemini API error {e.code}: {e.reason}")
            return {'disponible': False, 'error': f'Gemini API {e.code}: {e.reason}'}
        except Exception as exc:
            logger.error(f"Gemini error: {exc}")
            return {'disponible': False, 'error': 'Gemini no disponible temporalmente'}


# ── Factory: selecciona el proveedor ─────────────────────────────────────────
PROVEEDORES: Dict[str, type] = {
    'claude': ClaudeProvider,
    'gemini': GeminiProvider,
}

def get_provider(nombre: str = 'claude') -> BaseAIProvider:
    """
    Factory que retorna una instancia del proveedor solicitado.

    Args:
        nombre: 'claude' o 'gemini'

    Returns:
        Instancia del proveedor de IA correspondiente
    """
    cls = PROVEEDORES.get(nombre.lower(), ClaudeProvider)
    return cls()

def get_providers_status() -> Dict[str, bool]:
    """Retorna el estado de disponibilidad de todos los proveedores."""
    return {
        nombre: cls().esta_disponible()
        for nombre, cls in PROVEEDORES.items()
    }
