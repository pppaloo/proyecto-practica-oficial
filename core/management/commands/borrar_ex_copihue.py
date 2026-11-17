# -*- coding: utf-8 -*-
"""Elimina por completo el sector "Ex Copihue".

Borra de la base de datos:
  * las filas de la hoja Matriz (LocalMatriz),
  * los locales (Local, tipo kiosco, N° 1-5 y 7-13),
  * sus pagos y desgloses diarios,
  * las entradas del historial de esos locales.

Antes de borrar guarda un respaldo JSON en la carpeta ``respaldos/``.

Uso:
    python manage.py borrar_ex_copihue              # solo muestra el resumen
    python manage.py borrar_ex_copihue --confirmar  # borra de verdad
"""
import json
import os
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Historial, Local, LocalMatriz, Pago, PagoDiario

SECTOR = "Ex Copihue"
TIPO = "kiosco"


def _llave_numero(numero):
    return (0, int(numero)) if numero.isdigit() else (1, numero)


class Command(BaseCommand):
    help = "Elimina los datos de Ex Copihue (Matriz, locales, pagos, desgloses e historial)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Ejecuta el borrado. Sin esta opción solo se muestra el resumen.",
        )

    def handle(self, *args, **options):
        matriz = list(
            LocalMatriz.objects.filter(descripcion__iexact=SECTOR).order_by("numero")
        )
        if not matriz:
            self.stdout.write(
                self.style.WARNING("No se encontraron locales de Ex Copihue en la Matriz.")
            )
            return

        numeros = {m.numero for m in matriz}
        locales = list(Local.objects.filter(tipo=TIPO, numero__in=numeros))
        ids_locales = [l.id for l in locales]
        pagos = Pago.objects.filter(local_id__in=ids_locales)
        diarios = PagoDiario.objects.filter(pago__local_id__in=ids_locales)
        historial = Historial.objects.filter(tipo=TIPO, local_numero__in=numeros)

        self.stdout.write("Resumen de lo que se eliminará:")
        self.stdout.write(f"  LocalMatriz : {len(matriz)} filas")
        self.stdout.write(f"  Local       : {len(locales)} registros")
        self.stdout.write(f"  Pago        : {pagos.count()}")
        self.stdout.write(f"  PagoDiario  : {diarios.count()}")
        self.stdout.write(f"  Historial   : {historial.count()}")
        self.stdout.write(f"  Números     : {', '.join(sorted(numeros, key=_llave_numero))}")

        if not options["confirmar"]:
            self.stdout.write(
                self.style.WARNING(
                    "Modo simulación. Vuelve a ejecutar con --confirmar para borrar."
                )
            )
            return

        respaldo = {
            "generado": datetime.now().isoformat(timespec="seconds"),
            "sector": SECTOR,
            "numeros": sorted(numeros, key=_llave_numero),
            "localmatriz": list(LocalMatriz.objects.filter(pk__in=[m.pk for m in matriz]).values()),
            "locales": list(Local.objects.filter(pk__in=ids_locales).values()),
            "pagos": list(Pago.objects.filter(local_id__in=ids_locales).values()),
            "pago_diario": list(
                PagoDiario.objects.filter(pago__local_id__in=ids_locales).values()
            ),
            "historial": list(
                Historial.objects.filter(tipo=TIPO, local_numero__in=numeros).values()
            ),
        }

        carpeta = os.path.join(settings.BASE_DIR, "respaldos")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(
            carpeta, f"ex_copihue_{datetime.now():%Y%m%d_%H%M%S}.json"
        )
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(respaldo, archivo, ensure_ascii=False, indent=2, default=str)
        self.stdout.write(f"Respaldo guardado en {ruta}")

        with transaction.atomic():
            diarios.delete()
            pagos.delete()
            eliminados_local = Local.objects.filter(pk__in=ids_locales).delete()[0]
            eliminados_matriz = LocalMatriz.objects.filter(
                pk__in=[m.pk for m in matriz]
            ).delete()[0]
            eliminados_historial = Historial.objects.filter(
                tipo=TIPO, local_numero__in=numeros
            ).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                "Ex Copihue eliminado: "
                f"{eliminados_matriz} filas de Matriz, "
                f"{eliminados_local} locales, "
                f"{eliminados_historial} registros de historial."
            )
        )
