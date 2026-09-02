from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Max, Sum
from django.shortcuts import redirect, render
from django.http import HttpResponse

from .feriados import (
    FERIADOS_2026,
    TIPOS_RESTRINGIDOS,
    dia_habil_para,
    siguiente_dia_habil,
    mensaje_no_habil,
)
from .models import (
    ROLES,
    TIPOS_LOCAL,
    Historial,
    Local,
    Pago,
    Perfil,
)

MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

DIAS_GENERACION = 5
PREFIJO_FOLIO_GEN = "GEN"


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
    mes_filtro = request.GET.get("mes", "")
    anio_filtro = request.GET.get("anio", "")
    folio_filtro = request.GET.get("folio", "")
    empresario_filtro = request.GET.get("empresario", "")

    pagos_lista = Pago.objects.filter(local__tipo=tipo)
    if numero_filtro:
        pagos_lista = pagos_lista.filter(local__numero__icontains=numero_filtro)
    if mes_filtro:
        pagos_lista = pagos_lista.filter(mes__icontains=mes_filtro)
    if anio_filtro:
        pagos_lista = pagos_lista.filter(fecha__year=anio_filtro)
    if folio_filtro:
        pagos_lista = pagos_lista.filter(folio__icontains=folio_filtro)
    if empresario_filtro:
        pagos_lista = pagos_lista.filter(empresario__icontains=empresario_filtro)
    pagos_lista = pagos_lista.select_related("local").order_by("-fecha")

    from django.db.models import Count
    años_disponibles = (
        Pago.objects.filter(local__tipo=tipo)
        .dates("fecha", "year")
    )
    años_lista = [a.year for a in años_disponibles]

    orden_meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    meses_lista = orden_meses

    es_caja = request.user.perfil.rol == "caja"
    es_admin = request.user.perfil.rol == "administrador"

    context = {
        "tipos": TIPOS_LOCAL,
        "tipo_actual": tipo,
        "pagos": pagos_lista,
        "numero_filtro": numero_filtro,
        "mes_filtro": mes_filtro,
        "anio_filtro": anio_filtro,
        "folio_filtro": folio_filtro,
        "empresario_filtro": empresario_filtro,
        "años_lista": años_lista,
        "meses_lista": meses_lista,
        "es_caja": es_caja,
        "es_admin": es_admin,
        "generacion_disponible": es_caja and date.today().day <= DIAS_GENERACION,
    }
    return render(request, "core/pagos.html", context)


def _datos_generacion(hoy):
    periodo = f"{hoy.year}{hoy.month:02d}"
    filas = []
    for local in Local.objects.filter(ocupado=True).order_by("numero"):
        ultimo = local.pagos.order_by("-fecha", "-id").first()
        referencia = local.pagos.aggregate(v=Max("valor"))["v"] or Decimal("0")
        filas.append({
            "local": local,
            "ultimo": ultimo,
            "referencia": referencia,
            "folio": f"{PREFIJO_FOLIO_GEN}-{periodo}-{local.numero}",
            "existe": Pago.objects.filter(
                folio=f"{PREFIJO_FOLIO_GEN}-{periodo}-{local.numero}"
            ).exists(),
            "fecha_aplicada": siguiente_dia_habil(local.tipo, hoy),
        })
    return filas


@login_required
def generar_deuda(request):
    if request.user.perfil.rol != "caja":
        messages.error(request, "No tienes permisos para generar la deuda.")
        return redirect("pagos")

    hoy = date.today()
    if hoy.day > DIAS_GENERACION:
        messages.error(
            request,
            "La generación automática solo está disponible los primeros 5 días del mes.",
        )
        return redirect("pagos")

    filas = _datos_generacion(hoy)

    if request.method == "POST":
        creados = 0
        omitidos = 0
        total = Decimal("0")
        for fila in filas:
            if fila["existe"]:
                continue
            valor_post = request.POST.get(f"valor_{fila['local'].id}", "").strip()
            try:
                valor_dec = Decimal(valor_post) if valor_post else None
            except InvalidOperation:
                valor_dec = None
            if valor_dec is None or valor_dec <= 0:
                omitidos += 1
                continue
            if Pago.objects.filter(folio=fila["folio"]).exists():
                omitidos += 1
                continue
            local = fila["local"]
            ultimo = fila["ultimo"]
            fecha_obj = fila["fecha_aplicada"]
            Pago.objects.create(
                local=local,
                fecha=fecha_obj,
                mes=MESES_ES[fecha_obj.month - 1],
                empresario=ultimo.empresario if ultimo else "",
                rut=ultimo.rut if ultimo else "",
                descripcion=f"Deuda mensual {hoy.year}-{hoy.month:02d} generada automáticamente",
                valor=valor_dec,
                folio=fila["folio"],
            )
            registrar_historial(
                request, "generar", local.tipo, fila["folio"], local.numero, valor_dec
            )
            creados += 1
            total += valor_dec
        if creados:
            messages.success(
                request,
                f"Deuda del mes generada: {creados} registro(s) por ${total:,.0f}."
                f" Omitidos: {omitidos}.",
            )
        else:
            messages.error(request, "No se generó ningún registro nuevo.")
        return redirect("pagos_tipo", tipo="local")

    pendientes = [f for f in filas if not f["existe"]]
    ya_generados = [f for f in filas if f["existe"]]
    total_a_generar = sum((f["referencia"] for f in pendientes), Decimal("0"))
    context = {
        "filas": filas,
        "pendientes": pendientes,
        "ya_generados": ya_generados,
        "total_a_generar": total_a_generar,
        "periodo": f"{hoy.year}-{hoy.month:02d}",
    }
    return render(request, "core/generar_deuda.html", context)


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


@login_required
def editar_pago(request, tipo, folio):
    if request.user.perfil.rol != "caja":
        messages.error(request, "No tienes permisos para editar pagos.")
        return redirect("pagos_tipo", tipo=tipo)

    try:
        pago = Pago.objects.select_related("local").get(folio=folio)
    except Pago.DoesNotExist:
        messages.error(request, "No se encontró el registro con ese folio.")
        return redirect("pagos_tipo", tipo=tipo)

    if request.method == "POST":
        try:
            fecha = request.POST.get("fecha", "").strip()
            mes = request.POST.get("mes", "").strip()
            empresario = request.POST.get("empresario", "").strip()
            rut = request.POST.get("rut", "").strip()
            descripcion = request.POST.get("descripcion", "").strip()
            valor = request.POST.get("valor", "").strip()
            fecha_pago = request.POST.get("fecha_pago", "").strip() or None

            from datetime import datetime

            if not fecha:
                raise ValueError("La fecha es obligatoria.")
            fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()

            if not dia_habil_para(tipo, fecha_obj):
                raise ValueError(mensaje_no_habil(tipo, fecha_obj))

            if not mes:
                mes = MESES_ES[fecha_obj.month - 1]

            valor_dec = Decimal(valor)
            if valor_dec < 0:
                raise ValueError("El valor no puede ser negativo.")

            fecha_pago_obj = None
            if fecha_pago:
                fecha_pago_obj = datetime.strptime(fecha_pago, "%Y-%m-%d").date()

            pago.fecha = fecha_obj
            pago.mes = mes
            pago.empresario = empresario
            pago.rut = rut
            pago.descripcion = descripcion
            pago.valor = valor_dec
            pago.fecha_pago = fecha_pago_obj
            pago.save()

            registrar_historial(
                request, "editar", pago.local.tipo, pago.folio, pago.local.numero, valor_dec
            )
            messages.success(request, "Registro actualizado correctamente.")
            return redirect("pagos_tipo", tipo=tipo)
        except (ValueError, InvalidOperation) as e:
            messages.error(request, f"No se pudo actualizar: {e}")

    context = {
        "pago": pago,
        "tipo": tipo,
        "restringido": tipo in TIPOS_RESTRINGIDOS,
        "feriados": [f.isoformat() for f in FERIADOS_2026],
    }
    return render(request, "core/editar_pago.html", context)


@login_required
def eliminar_pago(request, tipo, folio):
    if request.user.perfil.rol != "caja":
        messages.error(request, "No tienes permisos para eliminar pagos.")
        return redirect("pagos_tipo", tipo=tipo)

    try:
        pago = Pago.objects.select_related("local").get(folio=folio)
    except Pago.DoesNotExist:
        messages.error(request, "No se encontró el registro.")
        return redirect("pagos_tipo", tipo=tipo)

    if request.method == "POST":
        registrar_historial(
            request, "eliminar", pago.local.tipo, pago.folio, pago.local.numero, pago.valor
        )
        pago.delete()
        messages.success(request, "Registro eliminado correctamente.")
        return redirect("pagos_tipo", tipo=tipo)

    context = {"pago": pago, "tipo": tipo}
    return render(request, "core/eliminar_pago.html", context)


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


@login_required
def reportes(request):
    tipo = request.GET.get("tipo", "")
    anio = request.GET.get("anio", "")
    exportar = request.GET.get("exportar", "")

    base = Pago.objects.all()
    if tipo:
        base = base.filter(local__tipo=tipo)
    if anio:
        base = base.filter(fecha__year=anio)

    total_general = base.aggregate(total=Sum("valor"))["total"] or Decimal("0")
    total_pendiente = base.filter(valor__gt=0).aggregate(total=Sum("valor"))["total"] or Decimal("0")
    cantidad = base.count()

    resumen_tipos = []
    for valor, nombre in TIPOS_LOCAL:
        qs = base.filter(local__tipo=valor)
        tot = qs.aggregate(t=Sum("valor"))["t"] or Decimal("0")
        cant = qs.count()
        if cant:
            resumen_tipos.append({
                "codigo": valor,
                "nombre": nombre,
                "total": tot,
                "cantidad": cant,
            })

    años_disponibles = [a.year for a in Pago.objects.dates("fecha", "year")]

    context = {
        "tipos": TIPOS_LOCAL,
        "tipo_filtro": tipo,
        "anio_filtro": anio,
        "años_lista": años_disponibles,
        "resumen_tipos": resumen_tipos,
        "total_general": total_general,
        "total_pendiente": total_pendiente,
        "cantidad": cantidad,
    }

    if exportar:
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reporte_vega.csv"'
        writer = csv.writer(response)
        writer.writerow(["Tipo de local", "Cantidad", "Total recaudado"])
        for fila in resumen_tipos:
            writer.writerow([fila["nombre"], fila["cantidad"], f'{fila["total"]:.0f}'])
        writer.writerow([])
        writer.writerow(["TOTAL GENERAL", cantidad, f"{total_general:.0f}"])
        writer.writerow(["TOTAL PENDIENTE", "", f"{total_pendiente:.0f}"])
        return response

    return render(request, "core/reportes.html", context)
