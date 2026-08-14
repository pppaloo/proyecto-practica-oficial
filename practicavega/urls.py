"""practicavega URL Configuration"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login2'),
    path('logout/', views.logout_view, name='logout'),
    path('inicio/', views.inicio, name='inicio'),
    path('pagos/', views.pagos, name='pagos'),
    path('pagos/<str:tipo>/', views.pagos, name='pagos_tipo'),
    path('pagos/<str:tipo>/agregar/', views.agregar_pago, name='agregar_pago'),
    path('pagos/<str:tipo>/abonar/<str:folio>/', views.abonar_pago, name='abonar_pago'),
    path('locales-desocupados/', views.locales_desocupados, name='locales_desocupados'),
    path('historial/', views.historial, name='historial'),
    path('usuarios/', views.usuarios_admin, name='usuarios_admin'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR)
