from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UsuarioClinico
from .permissions import EsAdministrador
from .serializers import (
    CustomTokenObtainPairSerializer, UsuarioSerializer, CrearUsuarioSerializer
)

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request) -> Response:
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            return Response({'detail': 'Sesión cerrada correctamente.'})
        except Exception:
            return Response({'error': 'Token inválido.'}, status=status.HTTP_400_BAD_REQUEST)

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request) -> Response:
        return Response(UsuarioSerializer(request.user).data)

class UsuarioListView(generics.ListCreateAPIView):
    queryset = UsuarioClinico.objects.all()
    permission_classes = [EsAdministrador]
    def get_serializer_class(self):
        return CrearUsuarioSerializer if self.request.method == 'POST' else UsuarioSerializer

class UsuarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UsuarioClinico.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [EsAdministrador]
