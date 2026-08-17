from django.db.models import Sum

from .models import Historial, LoginLog, Pago


def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    perfil = request.user.perfil
    ctx = {"rol": perfil.rol}

    if perfil.rol in ("caja", "tesoreria"):
        deudores = (
            Pago.objects.filter(valor__gt=0)
            .select_related("local")
            .order_by("-valor")
        )
        ctx["deudores"] = deudores
        ctx["total_deudas"] = deudores.aggregate(total=Sum("valor"))["total"] or 0
        ctx["total_deudores"] = deudores.count()
    elif perfil.rol == "administrador":
        ctx["logs_login"] = LoginLog.objects.select_related("usuario").order_by(
            "-fecha_hora"
        )[:30]
        ctx["ultimas_operaciones"] = Historial.objects.select_related(
            "usuario"
        ).order_by("-fecha_hora")[:10]
    return ctx
