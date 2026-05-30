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
