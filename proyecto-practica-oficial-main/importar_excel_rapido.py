# -*- coding: utf-8 -*-
"""Importador rapido para el Excel DEUDA ARRIENDO.xlsx usando bulk_create"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'practicavega.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import datetime, date
from decimal import Decimal
from openpyxl import load_workbook
from core.models import Local, Pago
from django.db import transaction


TIPOS_HOJA = {
    'centro comercial': 'centro_comercial',
    'boleterias': 'boleteria',
    'pescaderias': 'pescaderia',
    'lote 6': 'lote6',
    'kiosco': 'kiosco',
    'ex copihue': 'kiosco',
}


def parsear_fecha(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def parsear_decimal(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    try:
        return Decimal(str(valor))
    except:
        return None


def importar_hoja_rapido(ws, nombre_hoja):
    tipo_local = TIPOS_HOJA.get(nombre_hoja.lower())
    if not tipo_local:
        print(f"  [OMITIDA] Hoja '{nombre_hoja}' no reconocida.")
        return 0, 0

    print(f"\n[IMPORTANDO] {nombre_hoja} -> {tipo_local}")

    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return 0, 0

    headers = [str(h).strip().lower() if h else "" for h in filas[0]]

    col_local = next((i for i, h in enumerate(headers) if 'local' in h), None)
    col_fecha = next((i for i, h in enumerate(headers) if 'fecha' in h and 'pago' not in h and 'termino' not in h and 'contrato' not in h), None)
    col_mes = next((i for i, h in enumerate(headers) if h == 'mes'), None)
    col_empresario = next((i for i, h in enumerate(headers) if 'empresario' in h), None)
    col_rut = next((i for i, h in enumerate(headers) if 'rut' in h), None)
    col_descripcion = next((i for i, h in enumerate(headers) if 'descripc' in h), None)
    col_valor = next((i for i, h in enumerate(headers) if 'valor' in h and 'diario' not in h and 'pendiente' not in h and 'arriendo' not in h), None)
    col_valor_diario = next((i for i, h in enumerate(headers) if 'valor diario' in h), None)
    col_fecha_pago = next((i for i, h in enumerate(headers) if 'fecha pago' in h), None)

    if col_valor is None and col_valor_diario is not None:
        col_valor = col_valor_diario

    if col_local is None:
        print(f"  [ERROR] No se encontro columna 'Local'.")
        return 0, 0

    # Obtener todos los locales existentes de este tipo
    locales_existentes = {l.numero: l for l in Local.objects.filter(tipo=tipo_local)}
    pagos_existentes = set(Pago.objects.filter(local__tipo=tipo_local).values_list('folio', flat=True))

    nuevos_pagos = []
    locales_nuevos = []
    actualizados = 0
    creados = 0

    for num_fila, fila in enumerate(filas[1:], start=2):
        try:
            numero_local = str(fila[col_local]).strip() if fila[col_local] is not None else ""
            if not numero_local:
                continue

            valor = parsear_decimal(fila[col_valor] if col_valor is not None else None)
            if valor is None:
                valor = Decimal("0")

            fecha = parsear_fecha(fila[col_fecha] if col_fecha is not None else None)
            if fecha is None:
                fecha = date.today()

            mes = str(fila[col_mes]).strip() if col_mes is not None and fila[col_mes] else ""
            empresario = str(fila[col_empresario]).strip() if col_empresario is not None and fila[col_empresario] else ""
            rut = str(fila[col_rut]).strip() if col_rut is not None and fila[col_rut] else ""
            descripcion = str(fila[col_descripcion]).strip() if col_descripcion is not None and fila[col_descripcion] else nombre_hoja
            fecha_pago = parsear_fecha(fila[col_fecha_pago] if col_fecha_pago is not None else None)

            # Local
            if numero_local in locales_existentes:
                local = locales_existentes[numero_local]
            else:
                local = Local(numero=numero_local, tipo=tipo_local, ocupado=True)
                locales_nuevos.append(local)
                locales_existentes[numero_local] = local

            folio = f"{numero_local}-{fecha.year}-{fecha.month:02d}"

            if folio in pagos_existentes:
                actualizados += 1
            else:
                nuevos_pagos.append(Pago(
                    local=local,
                    folio=folio,
                    fecha=fecha,
                    mes=mes,
                    empresario=empresario,
                    rut=rut,
                    descripcion=descripcion,
                    valor=valor,
                    fecha_pago=fecha_pago,
                ))
                creados += 1

        except Exception as exc:
            pass

    # Bulk create
    if locales_nuevos:
        Local.objects.bulk_create(locales_nuevos, batch_size=1000)
    if nuevos_pagos:
        Pago.objects.bulk_create(nuevos_pagos, batch_size=1000)

    print(f"  [OK] Creados: {creados}, Actualizados: {actualizados}")
    return creados, actualizados


def main():
    archivo = r'C:\Users\cfernandez\Downloads\DEUDA ARRIENDO.xlsx'

    if not os.path.exists(archivo):
        print(f"[ERROR] No se encontro: {archivo}")
        return

    print(f"[ABRIENDO] {archivo}")
    wb = load_workbook(archivo, data_only=True)

    total_creados = 0
    total_actualizados = 0

    for nombre_hoja in wb.sheetnames:
        ws = wb[nombre_hoja]
        c, a = importar_hoja_rapido(ws, nombre_hoja)
        total_creados += c
        total_actualizados += a

    print(f"\n" + "="*50)
    print(f"[RESUMEN]")
    print(f"   Creados: {total_creados}")
    print(f"   Actualizados: {total_actualizados}")
    print(f"   Locales: {Local.objects.count()}")
    print(f"   Pagos: {Pago.objects.count()}")
    print("="*50)


if __name__ == '__main__':
    main()
