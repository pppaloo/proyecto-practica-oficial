from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .feriados import FERIADOS_2026, TIPOS_RESTRINGIDOS, dia_habil_para, mensaje_no_habil
from .models import (
    ROLES,
    TIPOS_LOCAL,
    TIPOS_MENSUALES,
    Historial,
    Local,
    Pago,
    Perfil,
)

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def registrar_historial(request, accion, tipo, folio, local_numero, monto):
    Historial.objects.create(
        usuario=request.user,
        accion=accion,
        tipo=tipo,
        folio=folio,
        local_numero=local_numero,
        monto=monto,
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("inicio")
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("inicio")
        messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def inicio(request):
    return redirect("pagos")


@login_required
def pagos(request, tipo="local"):
    tipos_validos = {v for v, _ in TIPOS_LOCAL}
    if tipo not in tipos_validos:
        tipo = "local"

    numero_filtro = request.GET.get("numero", "")
    pagos_lista = Pago.objects.filter(local__tipo=tipo)
    if numero_filtro:
        pagos_lista = pagos_lista.filter(local__numero__icontains=numero_filtro)
    pagos_lista = pagos_lista.select_related("local").order_by("-fecha")

    es_caja = request.user.perfil.rol == "caja"
    es_admin = request.user.perfil.rol == "administrador"

    context = {
        "tipos": TIPOS_LOCAL,
        "tipo_actual": tipo,
        "tipo_mensual": tipo in TIPOS_MENSUALES,
        "pagos": pagos_lista,
        "numero_filtro": numero_filtro,
        "es_caja": es_caja,
        "es_admin": es_admin,
    }
    return render(request, "core/pagos.html", context)


@login_required
def agregar_pago(request, tipo):
    if request.user.perfil.rol != "caja":
        messages.error(request, "No tienes permisos para registrar pagos.")
        return redirect("pagos_tipo", tipo=tipo)

    if request.method == "POST":
        try:
            numero = request.POST.get("numero", "").strip()
            fecha = request.POST.get("fecha", "")
            mes = request.POST.get("mes", "").strip()
            empresario = request.POST.get("empresario", "").strip()
            rut = request.POST.get("rut", "").strip()
            descripcion = request.POST.get("descripcion", "").strip()
            valor = request.POST.get("valor", "")
            fecha_pago = request.POST.get("fecha_pago", "") or None
            folio = request.POST.get("folio", "").strip()

            if not numero or not fecha:
                raise ValueError("N° de local y fecha son obligatorios.")
            if not valor:
                raise ValueError("El valor es obligatorio.")
            if not folio:
                raise ValueError("El folio es obligatorio.")

            from datetime import datetime
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()

            if not dia_habil_para(tipo, fecha_obj):
                raise ValueError(mensaje_no_habil(tipo, fecha_obj))

            if not mes:
                mes = MESES_ES[fecha_obj.month - 1]

            valor_dec = Decimal(valor)
            if valor_dec < 0:
                raise ValueError("El valor no puede ser negativo.")

            local, _ = Local.objects.get_or_create(
                numero=numero, defaults={"tipo": tipo, "ocupado": True}
            )
            if local.tipo != tipo:
                local.tipo = tipo
                local.save()

            if Pago.objects.filter(folio=folio).exists():
                raise ValueError(f"Ya existe un registro con el folio {folio}.")

            fecha_pago_obj = None
            if fecha_pago:
                fecha_pago_obj = datetime.strptime(fecha_pago, "%Y-%m-%d").date()

            Pago.objects.create(
                local=local,
                fecha=fecha_obj,
                mes=mes,
                empresario=empresario,
                rut=rut,
                descripcion=descripcion,
                valor=valor_dec,
                fecha_pago=fecha_pago_obj,
                folio=folio,
            )
            registrar_historial(
                request, "crear", tipo, folio, numero, valor_dec
            )
            messages.success(request, "Registro guardado correctamente.")
            return redirect("pagos_tipo", tipo=tipo)
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"No se pudo guardar: {e}")

    from datetime import date
    context = {
        "tipo": tipo,
        "tipo_mensual": tipo in TIPOS_MENSUALES,
        "hoy": date.today().isoformat(),
        "restringido": tipo in TIPOS_RESTRINGIDOS,
        "feriados": [f.isoformat() for f in FERIADOS_2026],
    }
    return render(request, "core/agregar_pago.html", context)


@login_required
def abonar_pago(request, tipo, folio):
    if request.user.perfil.rol != "caja":
        messages.error(request, "No tienes permisos para abonar pagos.")
        return redirect("pagos_tipo", tipo=tipo)

    try:
        pago = Pago.objects.get(folio=folio)
    except Pago.DoesNotExist:
        messages.error(request, "No se encontró el registro con ese folio.")
        return redirect("pagos_tipo", tipo=tipo)

    if request.method == "POST":
        try:
            monto = Decimal(request.POST.get("monto", ""))
            if monto <= 0:
                raise ValueError("El monto debe ser mayor que cero.")
            nuevo_valor = pago.valor - monto
            if nuevo_valor < 0:
                nuevo_valor = Decimal("0")
            pago.valor = nuevo_valor
            if nuevo_valor == 0:
                pago.fecha_pago = date.today()
            pago.save()
            registrar_historial(
                request, "abonar", pago.local.tipo, pago.folio, pago.local.numero, monto
            )
            messages.success(request, f"Abono registrado. Saldo pendiente: ${nuevo_valor:,.2f}")
        except (ValueError, InvalidOperation) as e:
            messages.error(request, f"No se pudo abonar: {e}")
        return redirect("pagos_tipo", tipo=tipo)

    context = {"pago": pago, "tipo": tipo}
    return render(request, "core/abonar.html", context)


@login_required
def historial(request):
    registros = Historial.objects.select_related("usuario").order_by("-fecha_hora")
    context = {"registros": registros}
    return render(request, "core/historial.html", context)


@login_required
def locales_desocupados(request):
    desocupados = Local.objects.filter(ocupado=False).order_by("numero")
    context = {"desocupados": desocupados}
    return render(request, "core/desocupados.html", context)


@login_required
def usuarios_admin(request):
    if request.user.perfil.rol != "administrador":
        messages.error(request, "No tienes permisos para administrar usuarios.")
        return redirect("inicio")

    if request.method == "POST":
        accion = request.POST.get("accion", "")
        if accion == "crear":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password", "")
            rol = request.POST.get("rol", "caja")
            try:
                if not username or not password:
                    raise ValueError("Usuario y contraseña son obligatorios.")
                if User.objects.filter(username=username).exists():
                    raise ValueError(f"El usuario '{username}' ya existe.")
                user = User.objects.create_user(username=username, password=password)
                user.perfil.rol = rol
                user.perfil.save()
                messages.success(request, "Usuario creado correctamente.")
            except ValueError as e:
                messages.error(request, str(e))
        elif accion == "cambiar_rol":
            username = request.POST.get("username", "").strip()
            nuevo_rol = request.POST.get("rol", "caja")
            try:
                user = User.objects.get(username=username)
                user.perfil.rol = nuevo_rol
                user.perfil.save()
                messages.success(request, f"Rol de '{username}' actualizado.")
            except User.DoesNotExist:
                messages.error(request, "Usuario no encontrado.")

    usuarios = Perfil.objects.select_related("user").order_by("user__username")
    context = {"usuarios": usuarios, "roles": ROLES}
    return render(request, "core/usuarios.html", context)
