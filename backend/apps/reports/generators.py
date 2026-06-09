"""Generadores de reportes PDF y Excel."""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import xlsxwriter
from apps.etl.models import RegistroClinico, Paciente

RIESGO_COLORS = {'Bajo':'#27ae60','Medio':'#f39c12','Alto':'#e67e22','Crítico':'#e74c3c'}

class PDFReportGenerator:
    def generate_pacientes_report(self, filtros: dict = None) -> bytes:
        from datetime import datetime as _dt
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=2.5*cm, bottomMargin=2*cm,
            leftMargin=2*cm, rightMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        story  = []

        # ── Encabezado profesional ────────────────────────────────────────────
        title_style = ParagraphStyle(
            'title', parent=styles['Title'],
            fontSize=22, textColor=colors.HexColor('#1a3a5c'),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            'subtitle', parent=styles['Normal'],
            fontSize=11, textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=2,
        )
        story.append(Paragraph("🛡️ HealthShield AI", title_style))
        story.append(Paragraph("Plataforma Inteligente de Analítica Clínica — HealthAnalytics IPS", subtitle_style))
        story.append(Paragraph(
            f"Reporte generado: {_dt.now().strftime('%d/%m/%Y %H:%M')} | "
            f"Confidencial — Solo uso médico",
            subtitle_style,
        ))
        story.append(Spacer(1, 0.3*cm))

        # Línea divisoria
        from reportlab.platypus import HRFlowable
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a3a5c')))
        story.append(Spacer(1, 0.4*cm))

        # KPIs summary
        from apps.analytics.calculators import KPICalculator
        kpis = KPICalculator().get_all_kpis()
        kpi_data = [
            ['KPI', 'Valor'],
            ['Total Registros', str(kpis.get('total_registros', 0))],
            ['Pacientes Críticos', str(kpis.get('pacientes_criticos', 0))],
            ['Pacientes Hipertensos', str(kpis.get('pacientes_hipertensos', 0))],
            ['Glucosa Promedio', f"{kpis.get('promedio_glucosa', 0)} mg/dL"],
            ['IMC Promedio', str(kpis.get('promedio_imc', 0))],
        ]
        t = Table(kpi_data, colWidths=[10*cm, 6*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a3a5c')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Patients table
        qs = RegistroClinico.objects.select_related('paciente').all()[:100]
        headers = ['Paciente', 'Edad', 'Sexo', 'Riesgo', 'Glucosa', 'Presión Sist.', 'IMC']
        rows = [headers]
        for r in qs:
            rows.append([
                f"{r.paciente.nombres} {r.paciente.apellidos}",
                str(r.paciente.edad), r.paciente.sexo,
                r.riesgo_enfermedad, str(r.glucosa), str(r.presion_sistolica), str(r.imc),
            ])
        pt = Table(rows, colWidths=[4.5*cm, 1.5*cm, 1.5*cm, 2*cm, 2.5*cm, 2.5*cm, 2*cm])
        pt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2980b9')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#ecf0f1')]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
        ]))
        story.append(pt)
        doc.build(story)
        return buffer.getvalue()


class ExcelReportGenerator:
    def generate(self) -> bytes:
        buffer = io.BytesIO()
        wb = xlsxwriter.Workbook(buffer)
        ws = wb.add_worksheet('Pacientes')

        # Formats
        header_fmt = wb.add_format({'bold':True,'bg_color':'#1a3a5c','font_color':'white','border':1})
        critico_fmt = wb.add_format({'bg_color':'#fadbd8','border':1})
        alto_fmt    = wb.add_format({'bg_color':'#fdebd0','border':1})
        normal_fmt  = wb.add_format({'bg_color':'#eafaf1','border':1})
        cell_fmt    = wb.add_format({'border':1})

        headers = ['ID','Nombres','Apellidos','Edad','Sexo','IMC','Clasificación IMC',
                   'Presión Sist.','Glucosa','Colesterol','Riesgo','Diagnóstico','Fecha Consulta']
        for col, h in enumerate(headers):
            ws.write(0, col, h, header_fmt)
            ws.set_column(col, col, 15)

        qs = RegistroClinico.objects.select_related('paciente').all()
        for row, r in enumerate(qs, start=1):
            fmt = critico_fmt if r.riesgo_enfermedad=='Crítico' else alto_fmt if r.riesgo_enfermedad=='Alto' else normal_fmt if r.riesgo_enfermedad=='Bajo' else cell_fmt
            data = [r.paciente.id_paciente_original, r.paciente.nombres, r.paciente.apellidos,
                    r.paciente.edad, r.paciente.sexo, float(r.imc or 0), r.clasificacion_imc,
                    r.presion_sistolica, float(r.glucosa or 0), float(r.colesterol or 0),
                    r.riesgo_enfermedad, r.diagnostico_preliminar, str(r.fecha_consulta or '')]
            for col, val in enumerate(data):
                ws.write(row, col, val, fmt)

        wb.close()
        return buffer.getvalue()


class PDFPatientReportGenerator:
    """Genera un reporte PDF individual de un paciente clínico."""

    def generate_for_patient(self, patient_id: int) -> bytes:
        from datetime import datetime as _dt
        from apps.etl.models import Paciente, RegistroClinico
        from apps.ml.models import Prediccion

        paciente = Paciente.objects.get(pk=patient_id)
        registros = RegistroClinico.objects.filter(paciente=paciente).order_by('-fecha_consulta')
        ultimo = registros.first()
        prediccion = Prediccion.objects.filter(paciente=paciente).order_by('-fecha').first()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            topMargin=2*cm, bottomMargin=2*cm,
            leftMargin=2*cm, rightMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        story = []

        # Header
        h1 = ParagraphStyle('h1', parent=styles['Title'], fontSize=18,
                             textColor=colors.HexColor('#1a3a5c'), spaceAfter=4)
        sub = ParagraphStyle('sub', parent=styles['Normal'], fontSize=10,
                             textColor=colors.HexColor('#7f8c8d'), spaceAfter=2)
        story.append(Paragraph("🛡️ HealthShield AI — Resumen Clínico Individual", h1))
        story.append(Paragraph(
            f"Generado: {_dt.now().strftime('%d/%m/%Y %H:%M')} | Confidencial — Solo uso médico", sub))
        from reportlab.platypus import HRFlowable
        story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1a3a5c')))
        story.append(Spacer(1, 0.5*cm))

        # Patient info
        info = ParagraphStyle('info', parent=styles['Normal'], fontSize=11, spaceAfter=4)
        story.append(Paragraph(f"<b>Paciente:</b> {paciente.nombres} {paciente.apellidos}", info))
        story.append(Paragraph(f"<b>ID:</b> {paciente.id_paciente_original} &nbsp;|&nbsp; "
                                f"<b>Edad:</b> {paciente.edad} años &nbsp;|&nbsp; "
                                f"<b>Sexo:</b> {'Masculino' if paciente.sexo == 'M' else 'Femenino'}", info))
        if paciente.cedula:
            story.append(Paragraph(f"<b>Cédula:</b> {paciente.cedula}", info))
        story.append(Spacer(1, 0.3*cm))

        # Risk badge
        riesgo = ultimo.riesgo_enfermedad if ultimo else 'N/D'
        riesgo_color = {'Bajo': '#27ae60', 'Medio': '#f39c12', 'Alto': '#e67e22', 'Crítico': '#e74c3c'}.get(riesgo, '#95a5a6')
        risk_style = ParagraphStyle('risk', parent=styles['Normal'], fontSize=14,
                                    textColor=colors.HexColor(riesgo_color), spaceAfter=6)
        story.append(Paragraph(f"<b>Nivel de Riesgo Clínico: {riesgo}</b>", risk_style))

        if prediccion:
            story.append(Paragraph(
                f"<i>Predicción IA ({prediccion.fecha.strftime('%d/%m/%Y')}) — "
                f"Confianza: {round(float(prediccion.probabilidad) * 100, 1)}%</i>", sub))
        story.append(Spacer(1, 0.4*cm))

        # Vitals table
        if ultimo:
            story.append(Paragraph("<b>Últimos Signos Vitales</b>", info))
            vitals_data = [
                ['Variable', 'Valor', 'Variable', 'Valor'],
                ['Peso', f"{ultimo.peso or '—'} kg",       'Altura',       f"{ultimo.altura or '—'} m"],
                ['IMC',  f"{ultimo.imc or '—'} ({ultimo.clasificacion_imc or '—'})", 'Glucosa', f"{ultimo.glucosa or '—'} mg/dL"],
                ['P. Sistólica', f"{ultimo.presion_sistolica or '—'} mmHg", 'P. Diastólica', f"{ultimo.presion_diastolica or '—'} mmHg"],
                ['Frec. Cardíaca', f"{ultimo.frecuencia_cardiaca or '—'} bpm", 'Temperatura', f"{ultimo.temperatura or '—'} °C"],
                ['Colesterol', f"{ultimo.colesterol or '—'} mg/dL", 'Sat. O₂', f"{ultimo.saturacion_oxigeno or '—'}%"],
            ]
            t = Table(vitals_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2980b9')),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
                ('FONTSIZE', (0,0), (-1,-1), 9),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.3*cm))

            # Habits
            story.append(Paragraph(
                f"<b>Hábitos:</b> Fumador: {'Sí' if ultimo.fumador else 'No'} | "
                f"Alcohol: {'Sí' if ultimo.consumo_alcohol else 'No'} | "
                f"Antecedentes fam.: {'Sí' if ultimo.antecedentes_familiares else 'No'} | "
                f"Actividad física: {ultimo.actividad_fisica or 'N/D'}", info))

            if ultimo.diagnostico_preliminar:
                story.append(Paragraph(f"<b>Diagnóstico:</b> {ultimo.diagnostico_preliminar}", info))
            story.append(Spacer(1, 0.3*cm))

        # Historical records
        if registros.count() > 1:
            story.append(Paragraph("<b>Historial de Consultas</b>", info))
            hist_data = [['Fecha', 'Riesgo', 'Glucosa', 'P. Sist.', 'IMC']]
            for r in registros[:10]:
                hist_data.append([
                    str(r.fecha_consulta or '—'), r.riesgo_enfermedad,
                    str(r.glucosa or '—'), str(r.presion_sistolica or '—'), str(r.imc or '—'),
                ])
            ht = Table(hist_data, colWidths=[3*cm, 3*cm, 3.5*cm, 3.5*cm, 3*cm])
            ht.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a3a5c')),
                ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0,0), (-1,-1), 9),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#ecf0f1')]),
                ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
            ]))
            story.append(ht)

        doc.build(story)
        return buffer.getvalue()
