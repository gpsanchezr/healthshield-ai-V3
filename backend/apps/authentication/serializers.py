from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import UsuarioClinico

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['nombre'] = user.get_full_name()
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = {
            'id': self.user.id,
            'username': self.user.username,
            'nombre': self.user.get_full_name(),
            'email': self.user.email,
            'rol': self.user.rol,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
        }
        return data

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuarioClinico
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 'rol',
            'is_staff', 'is_superuser', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class CrearUsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = UsuarioClinico
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'rol']

    def create(self, validated_data):
        return UsuarioClinico.objects.create_user(**validated_data)
