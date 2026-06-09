from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

def login_page(request):
    return render(request, 'auth/login.html')

def dashboard_page(request):
    return render(request, 'dashboard/index.html')

def etl_page(request):
    return render(request, 'etl/index.html')

def pacientes_page(request):
    return render(request, 'patients/list.html')

def admision_page(request):
    from datetime import date
    from decimal import Decimal, InvalidOperation
    from django.db import IntegrityError, transaction
    from django.db.models import Max
    from apps.etl.models import Paciente, RegistroClinico
    from apps.ml.models import ModeloML
    from apps.ml.predictor import ClinicalPredictor as PatientPredictor

    context = {'success': None, 'errors': []}

    if request.method == 'POST':
        def parse_int(value):
            try:
                return int(value) if value not in (None, '') else None
            except (ValueError, TypeError):
                return None

        def parse_decimal(value):
            try:
                return Decimal(value) if value not in (None, '') else None
            except (InvalidOperation, TypeError):
                return None

        def parse_bool(value):
            return str(value).lower() in ('on', 'true', '1', 'yes', 'si')

        nombres = request.POST.get('nombres', '').strip()
        apellidos = request.POST.get('apellidos', '').strip()
        cedula = request.POST.get('cedula', '').strip() or None
        sexo = request.POST.get('sexo', '').strip().upper()
        edad = parse_int(request.POST.get('edad'))
        peso = parse_decimal(request.POST.get('peso'))
        altura = parse_decimal(request.POST.get('altura'))
        imc = parse_decimal(request.POST.get('imc'))
        presion_sistolica = parse_int(request.POST.get('presion_sistolica'))
        presion_diastolica = parse_int(request.POST.get('presion_diastolica'))
        frecuencia_cardiaca = parse_int(request.POST.get('frecuencia_cardiaca'))
        glucosa = parse_decimal(request.POST.get('glucosa'))
        colesterol = parse_decimal(request.POST.get('colesterol'))
        saturacion_oxigeno = parse_decimal(request.POST.get('saturacion_oxigeno'))
        temperatura = parse_decimal(request.POST.get('temperatura'))
        actividad_fisica = request.POST.get('actividad_fisica', '').strip()
        fecha_consulta = request.POST.get('fecha_consulta') or date.today()
        diagnostico_preliminar = request.POST.get('diagnostico_preliminar', '').strip()
        antecedentes_familiares = parse_bool(request.POST.get('antecedentes_familiares'))
        fumador = parse_bool(request.POST.get('fumador'))
        consumo_alcohol = parse_bool(request.POST.get('consumo_alcohol'))

        if not nombres:
            context['errors'].append('El campo nombres es obligatorio.')
        if not apellidos:
            context['errors'].append('El campo apellidos es obligatorio.')
        if sexo not in ('M', 'F'):
            context['errors'].append('Selecciona un sexo válido.')
        if edad is None:
            context['errors'].append('La edad debe ser un número entero válido.')

        if cedula and Paciente.objects.filter(cedula=cedula).exists():
            context['errors'].append('Ya existe un paciente con esa cédula.')

        if not context['errors']:
            try:
                with transaction.atomic():
                    max_original = Paciente.objects.aggregate(Max('id_paciente_original'))
                    next_id = (max_original['id_paciente_original__max'] or 0) + 1

                    paciente = Paciente.objects.create(
                        id_paciente_original=next_id,
                        cedula=cedula,
                        nombres=nombres,
                        apellidos=apellidos,
                        edad=edad,
                        sexo=sexo,
                    )

                    if imc is None and peso is not None and altura:
                        try:
                            imc = peso / (altura * altura)
                        except (InvalidOperation, ZeroDivisionError):
                            imc = None

                    # Calcular clasificación IMC según estándares OMS
                    def calc_clasificacion_imc(val):
                        if val is None:
                            return ''
                        v = float(val)
                        if v < 18.5:   return 'Bajo peso'
                        elif v < 25.0: return 'Normal'
                        elif v < 30.0: return 'Sobrepeso'
                        else:          return 'Obesidad'

                    registro = RegistroClinico.objects.create(
                        paciente=paciente,
                        peso=peso,
                        altura=altura,
                        imc=imc,
                        clasificacion_imc=calc_clasificacion_imc(imc),
                        riesgo_enfermedad='Bajo',
                        presion_sistolica=presion_sistolica,
                        presion_diastolica=presion_diastolica,
                        frecuencia_cardiaca=frecuencia_cardiaca,
                        glucosa=glucosa,
                        colesterol=colesterol,
                        saturacion_oxigeno=saturacion_oxigeno,
                        temperatura=temperatura,
                        actividad_fisica=actividad_fisica,
                        fecha_consulta=fecha_consulta,
                        diagnostico_preliminar=diagnostico_preliminar,
                        antecedentes_familiares=antecedentes_familiares,
                        fumador=fumador,
                        consumo_alcohol=consumo_alcohol,
                    )

                    modelo_activo = ModeloML.objects.filter(activo=True).first()
                    if modelo_activo:
                        predictor = PatientPredictor(modelo_activo.archivo_modelo)
                        input_data = {
                            'edad': edad,
                            'imc': float(imc) if imc is not None else 0,
                            'presion_sistolica': presion_sistolica,
                            'presion_diastolica': presion_diastolica,
                            'frecuencia_cardiaca': frecuencia_cardiaca,
                            'glucosa': float(glucosa) if glucosa is not None else 0,
                            'colesterol': float(colesterol) if colesterol is not None else 0,
                            'saturacion_oxigeno': float(saturacion_oxigeno) if saturacion_oxigeno is not None else 0,
                            'temperatura': float(temperatura) if temperatura is not None else 0,
                            'fumador': fumador,
                            'consumo_alcohol': consumo_alcohol,
                            'antecedentes_familiares': antecedentes_familiares,
                        }
                        prediction = predictor.predict(input_data)
                        registro.riesgo_enfermedad = prediction.get('riesgo_predicho', registro.riesgo_enfermedad)
                        registro.save(update_fields=['riesgo_enfermedad'])

                riesgo_final = registro.riesgo_enfermedad
                context['success'] = (
                    f'Paciente {nombres} {apellidos} registrado con éxito (ID #{next_id}). '
                    f'Riesgo clínico asignado por IA: {riesgo_final}.'
                )
                context['riesgo_resultado'] = riesgo_final
            except IntegrityError as exc:
                context['errors'].append('Error en la base de datos: ' + str(exc))
            except Exception as exc:
                context['errors'].append(str(exc))

    return render(request, 'patients/admision.html', context)

def ml_page(request):
    return render(request, 'ml/index.html')

def reportes_page(request):
    return render(request, 'reports/index.html')

def alertas_page(request):
    return render(request, 'etl/alertas.html')

def ml_monitor_page(request):
    return render(request, 'ml/monitor.html')

def paciente_detail_page(request, pk):
    return render(request, 'patients/detail.html')
def analytics_page(request):
    return render(request, 'analytics/index.html')

def auditoria_page(request):
    return render(request, 'auth/auditoria.html')
