# -*- coding: utf-8 -*-
"""Importa los registros de Boleterías del Excel a la base de datos."""
import os
import sys
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'practicavega.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import datetime, date
from decimal import Decimal
from openpyxl import load_workbook
from core.models import Local, Pago
from django.db import transaction


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


def main():
    archivo = r'C:\Users\cfernandez\Downloads\DEUDA ARRIENDO.xlsx'
    print(f'[ABRIENDO] {archivo}')
    inicio = time.time()
    wb = load_workbook(archivo, data_only=True, read_only=True)

    nombre_hoja = 'Boleterias'
    tipo_local = 'boleteria'

    ws = wb[nombre_hoja]
    print(f'[IMPORTANDO] {nombre_hoja} -> {tipo_local}')

    filas_iter = ws.iter_rows(values_only=True)
    try:
        headers_row = next(filas_iter)
    except StopIteration:
        print('  (vacia)')
        return

    headers = [str(h).strip().lower() if h else '' for h in headers_row]

    col_local = next((i for i, h in enumerate(headers) if 'local' in h), None)
    col_fecha = next((i for i, h in enumerate(headers) if 'fecha' in h and 'pago' not in h and 'termino' not in h and 'contrato' not in h), None)
    col_mes = next((i for i, h in enumerate(headers) if h == 'mes'), None)
    col_empresario = next((i for i, h in enumerate(headers) if 'empresario' in h), None)
    col_rut = next((i for i, h in enumerate(headers) if 'rut' in h), None)
    col_descripcion = next((i for i, h in enumerate(headers) if 'descripc' in h), None)
    col_valor = next((i for i, h in enumerate(headers) if 'valor' in h and 'pendiente' in h), None)
    if col_valor is None:
        col_valor = next((i for i, h in enumerate(headers) if 'valor' in h), None)
    col_fecha_pago = next((i for i, h in enumerate(headers) if 'fecha pago' in h), None)

    if col_local is None or col_fecha is None:
        print('  [ERROR] No se encontraron columnas necesarias')
        return

    folios_existentes = set(Pago.objects.filter(local__tipo=tipo_local).values_list('folio', flat=True))

    nuevos_pagos = []
    creados = 0
    actualizados = 0
    locales_creados = 0
    total_filas = 0
    contador_folio = 0

    for fila in filas_iter:
        total_filas += 1
        try:
            fecha = parsear_fecha(fila[col_fecha] if col_fecha is not None else None)
            if fecha is None:
                continue

            numero_local = str(fila[col_local]).strip() if fila[col_local] is not None else ''
            if not numero_local:
                continue

            valor = parsear_decimal(fila[col_valor] if col_valor is not None else None)
            if valor is None:
                valor = Decimal('0')

            mes = str(fila[col_mes]).strip() if col_mes is not None and fila[col_mes] else ''
            empresario = str(fila[col_empresario]).strip() if col_empresario is not None and fila[col_empresario] else ''
            rut = str(fila[col_rut]).strip() if col_rut is not None and fila[col_rut] else ''
            descripcion = str(fila[col_descripcion]).strip() if col_descripcion is not None and fila[col_descripcion] else 'Boleterias'
            fecha_pago = parsear_fecha(fila[col_fecha_pago] if col_fecha_pago is not None else None)

            # Usar get_or_create para manejar locales existentes
            local, created = Local.objects.get_or_create(
                numero=numero_local,
                defaults={'tipo': tipo_local, 'ocupado': True}
            )
            if created:
                locales_creados += 1

            contador_folio += 1
            folio = f'{numero_local}-{fecha.year}-{fecha.month:02d}-{fecha.day:02d}-{contador_folio}'

            if folio in folios_existentes:
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
                folios_existentes.add(folio)
                creados += 1

            if len(nuevos_pagos) >= 2000:
                with transaction.atomic():
                    Pago.objects.bulk_create(nuevos_pagos, batch_size=1000)
                    nuevos_pagos = []
                print(f'    Creados: {creados}...')

        except Exception:
            pass

    # Insertar resto
    if nuevos_pagos:
        with transaction.atomic():
            Pago.objects.bulk_create(nuevos_pagos, batch_size=1000)

    wb.close()
    tiempo = time.time() - inicio

    print(f'\n{"="*50}')
    print(f'[RESUMEN - BOLETERIAS]')
    print(f'   Filas procesadas: {total_filas}')
    print(f'   Locales creados: {locales_creados}')
    print(f'   Creados: {creados}')
    print(f'   Actualizados: {actualizados}')
    print(f'   Pagos boleteria: {Pago.objects.filter(local__tipo=tipo_local).count()}')
    print(f'   Tiempo: {tiempo:.1f} segundos')
    print('='*50)


if __name__ == '__main__':
    main()
