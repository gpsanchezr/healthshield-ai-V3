"""Módulo de KPIs médicos, estadística descriptiva y detección de pacientes críticos."""
from django.db.models import Count, Avg, Max, Min
from apps.etl.models import RegistroClinico, Alerta, Paciente

class KPICalculator:
    def get_all_kpis(self) -> dict:
        qs = RegistroClinico.objects.all()
        total = qs.count()
        if total == 0:
            return {'total_registros': 0, 'mensaje': 'Sin datos. Ejecuta el ETL primero.'}

        aggs = qs.aggregate(
            avg_imc=Avg('imc'), avg_glucosa=Avg('glucosa'),
            avg_presion=Avg('presion_sistolica'), avg_colesterol=Avg('colesterol'),
            avg_edad=Avg('paciente__edad'),
        )

        # Conteos por riesgo
        n_critico = qs.filter(riesgo_enfermedad='Crítico').count()
        n_alto    = qs.filter(riesgo_enfermedad='Alto').count()
        n_medio   = qs.filter(riesgo_enfermedad='Medio').count()
        n_bajo    = qs.filter(riesgo_enfermedad='Bajo').count()

        # Riesgo promedio ponderado
        score_ponderado = (n_bajo*1 + n_medio*2 + n_alto*3 + n_critico*4) / max(total, 1)
        if score_ponderado >= 3.5:   riesgo_label = 'Crítico'
        elif score_ponderado >= 2.5: riesgo_label = 'Alto'
        elif score_ponderado >= 1.5: riesgo_label = 'Medio'
        else:                        riesgo_label = 'Bajo'

        # BUG FIX: diabéticos umbral 125 mg/dL (estándar clínico) — consistente con drilldown
        # BUG FIX: añadir conteos fitness que el JS del dashboard espera
        return {
            'total_registros':        total,
            'pacientes_criticos':     n_critico,
            'pacientes_alto_riesgo':  n_alto,
            'pacientes_medio_riesgo': n_medio,
            'pacientes_bajo_riesgo':  n_bajo,
            'pacientes_hipertensos':  qs.filter(presion_sistolica__gt=140).count(),
            'pacientes_diabeticos':   qs.filter(glucosa__gt=125).count(),   # FIX: 125 en lugar de 200
            'pacientes_fumadores':    qs.filter(fumador=True).count(),
            'promedio_imc':           round(float(aggs['avg_imc'] or 0), 2),
            'promedio_glucosa':       round(float(aggs['avg_glucosa'] or 0), 2),
            'promedio_presion':       round(float(aggs['avg_presion'] or 0), 1),
            'edad_promedio':          round(float(aggs['avg_edad'] or 0), 1),
            'alertas_sin_ver':        Alerta.objects.filter(fecha_vista__isnull=True).count(),
            'riesgo_promedio':        round(score_ponderado, 2),
            'riesgo_promedio_label':  riesgo_label,
            'indice_criticos_pct':    round(n_critico / max(total, 1) * 100, 2),
            'distribucion_riesgo':    self._dist_riesgo(qs),
            'distribucion_imc':       self._dist_imc(qs),
            'distribucion_sexo':      self._dist_sexo(qs),
            'top_diagnosticos':       self._top_diagnosticos(qs),
            # FIX: campos fitness para las tarjetas del dashboard
            'fitness_sedentario':     qs.filter(actividad_fisica__iexact='Sedentaria').count(),
            'fitness_baja':           qs.filter(actividad_fisica__iexact='Baja').count(),
            'fitness_media':          qs.filter(actividad_fisica__iexact='Media').count(),
            'fitness_alta':           qs.filter(actividad_fisica__iexact='Alta').count(),
        }

    def _dist_riesgo(self, qs):
        result = qs.values('riesgo_enfermedad').annotate(total=Count('id'))
        return {r['riesgo_enfermedad']: r['total'] for r in result}

    def _dist_imc(self, qs):
        return {
            'Bajo peso': qs.filter(imc__lt=18.5).count(),
            'Normal':    qs.filter(imc__gte=18.5, imc__lt=25).count(),
            'Sobrepeso': qs.filter(imc__gte=25, imc__lt=30).count(),
            'Obesidad':  qs.filter(imc__gte=30).count(),
        }

    def _dist_sexo(self, qs):
        result = qs.values('paciente__sexo').annotate(total=Count('id'))
        return {r['paciente__sexo']: r['total'] for r in result}

    def _top_diagnosticos(self, qs):
        result = qs.values('diagnostico_preliminar').annotate(total=Count('id')).order_by('-total')[:8]
        return [{'diagnostico': r['diagnostico_preliminar'], 'total': r['total']} for r in result]


class EstadisticaDescriptiva:
    def calcular(self, campo: str) -> dict:
        import statistics
        qs = RegistroClinico.objects.all()
        agg = qs.aggregate(media=Avg(campo), maximo=Max(campo), minimo=Min(campo))
        vals = sorted([float(v) for v in qs.values_list(campo, flat=True) if v is not None])
        n = len(vals)
        if n == 0:
            return {'campo': campo, 'n': 0, 'error': 'Sin datos'}
        mediana = statistics.median(vals)
        try:
            moda = statistics.mode(vals)
        except statistics.StatisticsError:
            moda = vals[len(vals)//2]
        desv_std = round(statistics.stdev(vals), 3) if n > 1 else 0.0
        p25 = vals[int(n * 0.25)]
        p75 = vals[int(n * 0.75)]
        return {
            'campo': campo, 'n': n,
            'media': round(float(agg['media'] or 0), 3),
            'mediana': round(float(mediana), 3),
            'moda': round(float(moda), 3),
            'desv_std': desv_std,
            'maximo': round(float(agg['maximo'] or 0), 3),
            'minimo': round(float(agg['minimo'] or 0), 3),
            'percentil_25': round(float(p25), 3),
            'percentil_75': round(float(p75), 3),
            'rango_iqr': round(float(p75 - p25), 3),
        }


class PacienteCriticoDetector:
    REGLAS = [
        ('presion_sistolica__gt', 180, 'Presión sistólica > 180 mmHg', 'critica'),
        ('glucosa__gt',           300, 'Glucosa > 300 mg/dL',          'critica'),
        ('saturacion_oxigeno__lt', 85, 'Saturación O₂ < 85%',          'critica'),
        ('presion_sistolica__gt', 160, 'Presión sistólica > 160 mmHg', 'alta'),
    ]
    def detectar(self) -> int:
        creadas = 0
        for campo, umbral, desc, urgencia in self.REGLAS:
            registros = RegistroClinico.objects.filter(**{campo: umbral}).select_related('paciente')
            for r in registros:
                _, created = Alerta.objects.get_or_create(
                    paciente=r.paciente, tipo_alerta=campo.split('__')[0],
                    defaults={'descripcion': desc, 'nivel_urgencia': urgencia}
                )
                if created: creadas += 1
        return creadas
