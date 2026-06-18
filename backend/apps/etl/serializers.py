from rest_framework import serializers
from .models import Paciente, RegistroClinico, EjecucionETL, LogETL, Alerta, DatasetCache

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


# ─── ConsultaMedica ───────────────────────────────────────────────────────────
class ConsultaMedicaSerializer(serializers.ModelSerializer):
    medico_nombre = serializers.SerializerMethodField()
    paciente_nombre = serializers.SerializerMethodField()

    class Meta:
        from .models import ConsultaMedica
        model  = ConsultaMedica
        fields = '__all__'
        read_only_fields = ['medico', 'id']

    def get_medico_nombre(self, obj):
        if obj.medico:
            return f"Dr./Dra. {obj.medico.first_name} {obj.medico.last_name}".strip() or obj.medico.username
        return 'Médico del sistema'

    def get_paciente_nombre(self, obj):
        return str(obj.paciente)


# ─── NUEVO V4.2: DatasetCache — caché del archivo real subido ────────────────
class DatasetCacheSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.__str__', read_only=True)
    tamaño_legible = serializers.ReadOnlyField()

    class Meta:
        model  = DatasetCache
        fields = ['id', 'nombre_original', 'tamaño_bytes', 'tamaño_legible',
                  'registros_detectados', 'usuario_nombre', 'fecha_subida', 'activo']

