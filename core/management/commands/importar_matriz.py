# -*- coding: utf-8 -*-
"""Carga la hoja 'Matriz' del Excel en la tabla LocalMatriz.

Uso:
    python manage.py importar_matriz
    python manage.py importar_matriz --archivo "C:\\ruta\\al\\excel.xlsx"
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import LocalMatriz

ARCHIVO_DEFAULT = r"C:\Users\palom\Downloads\DEUDA CENTRO COMERCIAL (2).xlsx"
HOJA = "Matriz"


def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _fecha(valor):
    if valor is None or str(valor).strip() == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _numero_local(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _decimal(valor):
    if valor is None or str(valor).strip() == "":
        return Decimal("0")
    if isinstance(valor, (int, float)):
        d = Decimal(repr(valor)) if isinstance(valor, float) else Decimal(valor)
    else:
        s = str(valor).strip().replace("$", "").replace(" ", "")
        try:
            d = Decimal(s)
        except InvalidOperation:
            s = s.replace(".", "").replace(",", ".")
            try:
                d = Decimal(s)
            except InvalidOperation:
                return Decimal("0")
    return d.quantize(Decimal("0.01"))


def _entero(valor):
    try:
        return int(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


class Command(BaseCommand):
    help = "Importa la hoja Matriz (ficha de los 135 locales) desde el Excel."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=ARCHIVO_DEFAULT)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        archivo = options["archivo"]
        self.stdout.write(f"Leyendo {archivo} ...")
        wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
        if HOJA not in wb.sheetnames:
            self.stderr.write(f"No existe la hoja {HOJA!r}. Hojas: {wb.sheetnames}")
            wb.close()
            return

        ws = wb[HOJA]
        filas = []
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or row[0] is None or str(row[0]).strip() == "":
                continue
            filas.append(
                LocalMatriz(
                    numero=_numero_local(row[0]),
                    empresario=_texto(row[1]),
                    rut=_texto(row[2]),
                    descripcion=_texto(row[3]),
                    fecha_inicio=_fecha(row[4]),
                    fecha_termino=_fecha(row[5]),
                    ultimo_pago_2020=_fecha(row[6]),
                    mes_curso=_fecha(row[7]),
                    valor_pendiente=_decimal(row[8]),
                    meses_pendientes=_entero(row[9]),
                    observacion=_texto(row[10]),
                )
            )
        wb.close()

        self.stdout.write(f"Filas leidas: {len(filas)}")
        if options["dry_run"]:
            for f in filas[:10]:
                self.stdout.write(f"  {f.numero} | {f.empresario} | {f.descripcion} | {f.valor_pendiente}")
            return

        with transaction.atomic():
            LocalMatriz.objects.all().delete()
            LocalMatriz.objects.bulk_create(filas)
        self.stdout.write(self.style.SUCCESS(f"Importados {LocalMatriz.objects.count()} locales."))
