from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UsuarioClinico

@admin.register(UsuarioClinico)
class UsuarioClinicoAdmin(UserAdmin):
    list_display  = ['username', 'get_full_name', 'email', 'rol', 'is_active', 'created_at']
    list_filter   = ['rol', 'is_active']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    fieldsets = UserAdmin.fieldsets + (
        ('Rol Clínico', {'fields': ('rol',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol Clínico', {'fields': ('rol',)}),
    )
