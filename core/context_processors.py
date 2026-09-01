from .models import Historial, LoginLog


def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    perfil = request.user.perfil
    ctx = {"rol": perfil.rol}

    if perfil.rol == "administrador":
        ctx["logs_login"] = LoginLog.objects.select_related("usuario").order_by(
            "-fecha_hora"
        )[:30]
        ctx["ultimas_operaciones"] = Historial.objects.select_related(
            "usuario"
        ).order_by("-fecha_hora")[:10]
    return ctx
