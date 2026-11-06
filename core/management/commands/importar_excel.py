import argparse

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Importa pagos desde un archivo Excel (.xlsx o .xls)."

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=argparse.FileType("rb"), help="Ruta al archivo .xlsx o .xls")
        parser.add_argument("--hoja", default=None, help="Nombre de la hoja a leer (default: primera)")
        parser.add_argument("--tipo", default=None, help="Tipo de local por defecto si no viene en el Excel")

    @transaction.atomic
    def handle(self, *args, **opts):
        from core.importador import _cerrar_excel, _leer_excel_bytes, importar_workbook

        contenido = opts["archivo"].read()
        hojas, formato, res = _leer_excel_bytes(contenido)
        if hojas is None:
            self.stderr.write(res)
            return

        try:
            if opts["hoja"]:
                ws = next((h for h in hojas if h.title == opts["hoja"]), None)
                if ws is None:
                    self.stderr.write(f"No se encontró la hoja: {opts['hoja']}")
                    return
            else:
                ws = hojas[0]

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
        finally:
            _cerrar_excel(formato, res)