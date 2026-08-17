from django.contrib import admin
from .models import Local, Pago, Perfil, LoginLog


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ("numero", "tipo", "ocupado")
    list_filter = ("tipo", "ocupado")
    inlines = [PagoInline]


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("folio", "local", "fecha", "empresario", "valor", "fecha_pago")
    search_fields = ("folio", "empresario", "rut", "local__numero")


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "rol")
    list_filter = ("rol",)


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ("usuario", "accion", "fecha_hora")
    list_filter = ("accion",)
    ordering = ("-fecha_hora",)
