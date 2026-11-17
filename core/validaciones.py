# -*- coding: utf-8 -*-
"""Validaciones y límites de los campos del sistema.

Se aplican en el servidor (son las que mandan) y se reflejan en los
formularios con maxlength/pattern para que el navegador también limite.
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class CampoInvalido(ValueError):
    """Error de validación mostrable al usuario."""


RE_NUMERO = re.compile(r"\d{1,10}")
RE_EMPRESARIO = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,()\-&/'°º]{1,150}")
RE_RUT = re.compile(r"\d{1,2}\.?\d{3}\.?\d{3}-?[\dKk]")
RE_DESCRIPCION = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,()\-/]{0,255}")
RE_DOMICILIO = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,#\-/°º]{0,200}")
RE_FONO = re.compile(r"[0-9+\-() ]{0,30}")
RE_PERIODO = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 ]{0,50}")
RE_FOLIO = re.compile(r"[A-Za-z0-9\-_.]{1,30}")
RE_MES = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{0,20}")
RE_USUARIO = re.compile(r"[A-Za-z0-9._\-]{3,150}")


def limpiar(valor, maximo):
    return (valor or "").strip()[:maximo]


def _patron(valor, regex, campo, ejemplo=""):
    if valor and not regex.fullmatch(valor):
        extra = f" Ejemplo: {ejemplo}." if ejemplo else ""
        raise CampoInvalido(
            f"El campo «{campo}» tiene un formato o caracteres no permitidos.{extra}"
        )
    return valor


def numero_local(valor, obligatorio=True):
    v = limpiar(valor, 10)
    if obligatorio and not v:
        raise CampoInvalido("El N° de local es obligatorio.")
    return _patron(v, RE_NUMERO, "N° local", "42")


def empresa(valor):
    return _patron(limpiar(valor, 150), RE_EMPRESARIO, "empresario")


def rut(valor, obligatorio=False):
    v = limpiar(valor, 15).replace(" ", "").upper()
    if not v:
        if obligatorio:
            raise CampoInvalido("El RUT es obligatorio.")
        return ""
    _patron(v, RE_RUT, "RUT", "12.345.678-9")

    limpio = v.replace(".", "")
    if "-" in limpio:
        cuerpo, dv = limpio.split("-", 1)
    else:
        cuerpo, dv = limpio[:-1], limpio[-1]

    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = 11 - (suma % 11)
    esperado = "0" if resto == 11 else "K" if resto == 10 else str(resto)
    if dv != esperado:
        raise CampoInvalido("El RUT no es válido (dígito verificador incorrecto).")
    return v


def descripcion(valor):
    return _patron(limpiar(valor, 255), RE_DESCRIPCION, "descripción")


def domicilio(valor):
    return _patron(limpiar(valor, 200), RE_DOMICILIO, "domicilio")


def fono(valor):
    return _patron(limpiar(valor, 30), RE_FONO, "fono")


def correo(valor):
    v = limpiar(valor, 150)
    if v:
        try:
            validate_email(v)
        except ValidationError:
            raise CampoInvalido("El correo no tiene un formato válido.")
    return v


def periodo(valor):
    return _patron(limpiar(valor, 50), RE_PERIODO, "periodo")


def mes(valor):
    return _patron(limpiar(valor, 20), RE_MES, "mes")


def folio(valor, obligatorio=True):
    v = limpiar(valor, 30)
    if obligatorio and not v:
        raise CampoInvalido("El folio es obligatorio.")
    return _patron(v, RE_FOLIO, "folio", "CC-42-2020-06")


def monto(valor, campo="valor", obligatorio=True):
    v = (valor or "").strip().replace("$", "").replace(" ", "")
    if not v:
        if obligatorio:
            raise CampoInvalido(f"El campo «{campo}» es obligatorio.")
        return Decimal("0")
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise CampoInvalido(f"El campo «{campo}» debe ser un número.")
    if d < 0:
        raise CampoInvalido(f"El campo «{campo}» no puede ser negativo.")
    if d > Decimal("99999999.99"):
        raise CampoInvalido(
            f"El campo «{campo}» supera el máximo permitido ($99.999.999,99)."
        )
    return d.quantize(Decimal("0.01"))


def fecha(valor, campo="fecha", obligatorio=True):
    v = (valor or "").strip()
    if not v:
        if obligatorio:
            raise CampoInvalido(f"La {campo} es obligatoria.")
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        raise CampoInvalido(f"La {campo} no tiene un formato válido (AAAA-MM-DD).")


def usuario(valor):
    v = limpiar(valor, 150)
    if not v:
        raise CampoInvalido("El nombre de usuario es obligatorio.")
    return _patron(v, RE_USUARIO, "usuario", "caja2")
