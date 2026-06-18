from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .chatbot import get_clinical_answer


class ClinicalChatbotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # BUG FIX: roles are lowercase in the system (medico, not Médico)
        user_rol = getattr(request.user, 'rol', '').lower().strip()
        # Allow medico, analista and admin (staff/superuser) to use chatbot
        allowed_roles = ['medico', 'médico', 'analista', 'administrador']
        if user_rol not in allowed_roles and not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Acceso denegado: El asistente clínico es exclusivo para el rol Médico.")

        query = request.data.get('query', '').strip()
        if not query:
            return Response({'error': 'La consulta no puede estar vacía.'}, status=400)

        respuesta = get_clinical_answer(query)
        return Response({'respuesta': respuesta})
