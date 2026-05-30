from django.http import HttpResponse
from rest_framework.views import APIView
from apps.authentication.permissions import EsAnalista

class ExportarPDFView(APIView):
    permission_classes = [EsAnalista]
    def get(self, request):
        from .generators import PDFReportGenerator
        pdf = PDFReportGenerator().generate_pacientes_report()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="healthshield_reporte.pdf"'
        return response

class ExportarExcelView(APIView):
    permission_classes = [EsAnalista]
    def get(self, request):
        from .generators import ExcelReportGenerator
        data = ExcelReportGenerator().generate()
        response = HttpResponse(data, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="healthshield_pacientes.xlsx"'
        return response

class ExportarCSVView(APIView):
    permission_classes = [EsAnalista]
    def get(self, request):
        import csv, io
        from apps.etl.models import RegistroClinico
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['id_paciente','nombres','apellidos','edad','sexo','imc','glucosa','presion_sistolica','riesgo_enfermedad','diagnostico'])
        for r in RegistroClinico.objects.select_related('paciente').all():
            w.writerow([r.paciente.id_paciente_original, r.paciente.nombres, r.paciente.apellidos,
                        r.paciente.edad, r.paciente.sexo, r.imc, r.glucosa, r.presion_sistolica,
                        r.riesgo_enfermedad, r.diagnostico_preliminar])
        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="healthshield_pacientes.csv"'
        return response
