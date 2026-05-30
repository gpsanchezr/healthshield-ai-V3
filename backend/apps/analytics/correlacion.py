"""
Módulo de correlación clínica para el heatmap del dashboard.
Calcula la matriz de correlación de Pearson entre variables numéricas clave.
"""
from typing import Dict, List
import pandas as pd

VARIABLES_CLINICAS: List[str] = [
    'imc', 'glucosa', 'colesterol', 'presion_sistolica',
    'presion_diastolica', 'frecuencia_cardiaca', 'saturacion_oxigeno', 'temperatura',
]

LABELS: Dict[str, str] = {
    'imc':                'IMC',
    'glucosa':            'Glucosa',
    'colesterol':         'Colesterol',
    'presion_sistolica':  'Presión Sist.',
    'presion_diastolica': 'Presión Diast.',
    'frecuencia_cardiaca':'Frec. Cardíaca',
    'saturacion_oxigeno': 'Saturación O₂',
    'temperatura':        'Temperatura',
}


class CorrelacionCalculator:
    def calcular(self) -> dict:
        from apps.etl.models import RegistroClinico

        qs = RegistroClinico.objects.values(*VARIABLES_CLINICAS)
        if not qs.exists():
            return {'error': 'Sin datos suficientes para calcular correlación'}

        df = pd.DataFrame(list(qs)).dropna()
        if len(df) < 10:
            return {'error': 'Se necesitan al menos 10 registros'}

        corr = df[VARIABLES_CLINICAS].corr(method='pearson')

        # Formato plano para Chart.js matrix plugin
        data_points = []
        for i, var_x in enumerate(VARIABLES_CLINICAS):
            for j, var_y in enumerate(VARIABLES_CLINICAS):
                val = round(float(corr.loc[var_x, var_y]), 3)
                data_points.append({'x': i, 'y': j, 'v': val})

        # FIX: Also return 2D matrix format for HTML table heatmap
        matriz = [
            [round(float(corr.loc[r, c]), 3) for c in VARIABLES_CLINICAS]
            for r in VARIABLES_CLINICAS
        ]

        return {
            'labels':      [LABELS[v] for v in VARIABLES_CLINICAS],
            'variables':   VARIABLES_CLINICAS,
            'data_points': data_points,
            'matriz':      matriz,   # ← NEW: 2D array for HTML table heatmap
            'n_registros': len(df),
        }
