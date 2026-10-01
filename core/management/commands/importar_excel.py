import argparse

from django.core.management.base import BaseCommand
from django.db import transaction

from openpyxl import load_workbook

from core.importador import importar_workbook


class Command(BaseCommand):
    help = "Importa pagos desde un archivo Excel (.xlsx)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=argparse.FileType("rb"), help="Ruta al archivo .xlsx")
        parser.add_argument("--hoja", default=None, help="Nombre de la hoja a leer (default: primera)")
        parser.add_argument("--tipo", default=None, help="Tipo de local por defecto si no viene en el Excel")

    @transaction.atomic
    def handle(self, *args, **opts):
        wb = load_workbook(opts["archivo"], data_only=True)
        ws = wb[opts["hoja"]] if opts["hoja"] else wb.worksheets[0]

        r = importar_workbook(ws, opts["tipo"])
        if r.get("error"):
            self.stderr.write(r["error"])
            return
        for msg in r.get("fila", []):
            self.stderr.write(msg)
        self.stdout.write(
            self.style.SUCCESS(
                f"Importación terminada: {r['creados']} creados, "
                f"{r['actualizados']} actualizados, "
                f"{r['sin_cambios']} sin cambios, {r['errores']} errores."
            )
        )