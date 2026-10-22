# -*- coding: utf-8 -*-
"""Actualiza los valores de los pagos en la base de datos desde el Excel."""
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


def main():
    archivo = r'C:\Users\cfernandez\Downloads\DEUDA ARRIENDO.xlsx'
    print(f'[ABRIENDO] {archivo}')
    inicio = time.time()
    wb = load_workbook(archivo, data_only=True, read_only=True)

    total_actualizados = 0

    for nombre_hoja in wb.sheetnames:
        tipo_local = TIPOS_HOJA.get(nombre_hoja.lower())
        if not tipo_local:
            continue

        ws = wb[nombre_hoja]
        print(f'\n[ACTUALIZANDO] {nombre_hoja} -> {tipo_local}')

        filas_iter = ws.iter_rows(values_only=True)
        try:
            headers_row = next(filas_iter)
        except StopIteration:
            continue

        headers = [str(h).strip().lower() if h else '' for h in headers_row]

        col_local = next((i for i, h in enumerate(headers) if 'local' in h), None)
        col_fecha = next((i for i, h in enumerate(headers) if 'fecha' in h and 'pago' not in h and 'termino' not in h and 'contrato' not in h), None)
        col_valor = next((i for i, h in enumerate(headers) if 'valor' in h), None)

        if col_local is None or col_fecha is None or col_valor is None:
            print(f'  [ERROR] No se encontraron columnas necesarias')
            continue

        print(f'  Columna valor: {headers[col_valor]}')

        actualizados = 0
        contador = 0

        for fila in filas_iter:
            contador += 1
            try:
                fecha = parsear_fecha(fila[col_fecha] if col_fecha is not None else None)
                if fecha is None:
                    continue

                numero_local = str(fila[col_local]).strip() if fila[col_local] is not None else ''
                if not numero_local:
                    continue

                valor = parsear_decimal(fila[col_valor] if col_valor is not None else None)
                if valor is None:
                    continue

                # Buscar el pago correspondiente
                try:
                    local = Local.objects.get(numero=numero_local, tipo=tipo_local)
                    pago = Pago.objects.filter(local=local, fecha=fecha).first()
                    if pago and pago.valor != valor:
                        pago.valor = valor
                        pago.save()
                        actualizados += 1
                except Local.DoesNotExist:
                    pass

                if contador % 5000 == 0:
                    print(f'    Procesados {contador}...')

            except Exception:
                pass

        print(f'  [OK] {actualizados} valores actualizados')
        total_actualizados += actualizados

    wb.close()
    tiempo = time.time() - inicio

    print(f'\n{"="*50}')
    print(f'[RESUMEN]')
    print(f'   Valores actualizados: {total_actualizados}')
    print(f'   Tiempo: {tiempo:.1f} segundos')
    print('='*50)


if __name__ == '__main__':
    main()
