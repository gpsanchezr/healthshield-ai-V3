from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, LogoutView, MeView, UsuarioListView, UsuarioDetailView
from .audit_views import AuditoriaView

urlpatterns = [
    path('login/',             LoginView.as_view(),        name='login'),
    path('logout/',            LogoutView.as_view(),        name='logout'),
    path('refresh/',           TokenRefreshView.as_view(),  name='token_refresh'),
    path('me/',                MeView.as_view(),            name='me'),
    path('usuarios/',          UsuarioListView.as_view(),   name='usuarios-list'),
    path('usuarios/<int:pk>/', UsuarioDetailView.as_view(), name='usuarios-detail'),
    path('auditoria/',         AuditoriaView.as_view(),     name='auditoria'),
]
