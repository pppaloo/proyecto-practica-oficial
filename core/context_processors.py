from datetime import date
from decimal import Decimal

from .models import Historial, LoginLog, ValorUTM
from .views import MESES_ES


def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    perfil = request.user.perfil
    ctx = {"rol": perfil.rol}

    hoy = date.today()
    utm_reg = ValorUTM.objects.filter(anio=hoy.year, mes=hoy.month).first()
    ctx["utm_valor"] = utm_reg.valor if utm_reg else Decimal("0")
    ctx["utm_mes_num"] = hoy.month
    ctx["utm_mes"] = MESES_ES[hoy.month - 1]
    ctx["utm_anio"] = hoy.year

    if perfil.rol == "administrador":
        ctx["logs_login"] = LoginLog.objects.select_related("usuario").order_by(
            "-fecha_hora"
        )[:30]
        ctx["ultimas_operaciones"] = Historial.objects.select_related(
            "usuario"
        ).order_by("-fecha_hora")[:10]
    return ctx
