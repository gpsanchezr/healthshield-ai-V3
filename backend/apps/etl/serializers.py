from rest_framework import serializers
from .models import Paciente, RegistroClinico, EjecucionETL, LogETL, Alerta

class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = '__all__'

class RegistroClinicoSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.__str__', read_only=True)
    class Meta:
        model = RegistroClinico
        fields = '__all__'

class EjecucionETLSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.__str__', read_only=True)
    quality_score  = serializers.SerializerMethodField()
    class Meta:
        model = EjecucionETL
        fields = '__all__'
    def get_quality_score(self, obj):
        return (obj.reporte_calidad or {}).get('quality_score')

class LogETLSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogETL
        fields = '__all__'

class AlertaSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.__str__', read_only=True)
    class Meta:
        model = Alerta
        fields = '__all__'
