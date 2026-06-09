from rest_framework.permissions import BasePermission

def puede_administrar(user):
    return (
        user.is_authenticated
        and (
            getattr(user, 'rol', None) == 'administrador'
            or user.is_staff
            or user.is_superuser
        )
    )

def puede_analizar(user):
    return (
        user.is_authenticated
        and (
            getattr(user, 'rol', None) in ['analista', 'administrador']
            or user.is_staff
            or user.is_superuser
        )
    )

def puede_ver_clinico(user):
    return (
        user.is_authenticated
        and (
            getattr(user, 'rol', None) in ['medico', 'analista', 'administrador']
            or user.is_staff
            or user.is_superuser
        )
    )

class EsAdministrador(BasePermission):
    message = 'Se requiere rol administrador o usuario staff/superuser.'

    def has_permission(self, request, view):
        return puede_administrar(request.user)

class EsMedico(BasePermission):
    message = 'Se requiere un usuario autenticado con acceso clinico.'

    def has_permission(self, request, view):
        return puede_ver_clinico(request.user)

class EsAnalista(BasePermission):
    message = 'Se requiere rol analista/administrador o usuario staff/superuser.'

    def has_permission(self, request, view):
        return puede_analizar(request.user)
