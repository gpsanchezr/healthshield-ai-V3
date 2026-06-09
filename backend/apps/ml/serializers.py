from rest_framework import serializers
from .models import ModeloML, Prediccion

class ModeloMLSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeloML
        fields = '__all__'

class PrediccionSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source='paciente.__str__', read_only=True)
    class Meta:
        model = Prediccion
        fields = '__all__'
