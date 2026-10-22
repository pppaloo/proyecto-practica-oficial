# -*- coding: utf-8 -*-
"""Importador personalizado para el Excel DEUDA ARRIENDO.xlsx

Lee todas las hojas del Excel y crea registros de pago para cada tipo de local.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'practicavega.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from datetime import datetime, date
from decimal import Decimal
from openpyxl import load_workbook
from core.models import Local, Pago, Historial
from django.contrib.auth.models import User


# Mapeo de nombres de hojas a tipos de local
TIPOS_HOJA = {
    'centro comercial': 'centro_comercial',
    'boleterias': 'boleteria',
    'pescaderias': 'pescaderia',
    'lote 6': 'lote6',
    'kiosco': 'kiosco',
    'ex copihue': 'kiosco',
}


def parsear_fecha(valor):
    """Convierte un valor a fecha."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def parsear_decimal(valor):
    """Convierte un valor a Decimal."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    try:
        return Decimal(str(valor))
    except:
        return None


def importar_hoja(ws, nombre_hoja, usuario):
    """Importa una hoja del Excel y crea registros de pago."""
    tipo_local = TIPOS_HOJA.get(nombre_hoja.lower())
    if not tipo_local:
        print(f"  [ADVERTENCIA] Hoja '{nombre_hoja}' no reconocida, se omite.")
        return None

    print(f"\n[IMPORTANDO] Hoja: {nombre_hoja} (tipo: {tipo_local})")

    # Obtener encabezados de la primera fila
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        print(f"  [ADVERTENCIA] Hoja vacia.")
        return None

    headers = [str(h).strip().lower() if h else "" for h in filas[0]]
    print(f"  Columnas: {headers}")

    # Mapear columnas
    col_local = next((i for i, h in enumerate(headers) if 'local' in h), None)
    col_fecha = next((i for i, h in enumerate(headers) if 'fecha' in h and 'pago' not in h and 'termino' not in h and 'contrato' not in h), None)
    col_mes = next((i for i, h in enumerate(headers) if h == 'mes'), None)
    col_empresario = next((i for i, h in enumerate(headers) if 'empresario' in h), None)
    col_rut = next((i for i, h in enumerate(headers) if 'rut' in h), None)
    col_descripcion = next((i for i, h in enumerate(headers) if 'descripc' in h), None)
    col_valor = next((i for i, h in enumerate(headers) if 'valor' in h and 'diario' not in h and 'pendiente' not in h and 'arriendo' not in h), None)
    col_valor_diario = next((i for i, h in enumerate(headers) if 'valor diario' in h), None)
    col_fecha_pago = next((i for i, h in enumerate(headers) if 'fecha pago' in h), None)

    # Si no hay columna de valor, usar valor diario
    if col_valor is None and col_valor_diario is not None:
        col_valor = col_valor_diario

    print(f"  Mapeo: local={col_local}, fecha={col_fecha}, mes={col_mes}, empresario={col_empresario}, rut={col_rut}, valor={col_valor}, fecha_pago={col_fecha_pago}")

    if col_local is None:
        print(f"  [ADVERTENCIA] No se encontro columna 'Local'.")
        return None

    # Importar filas
    creados = 0
    actualizados = 0
    errores = 0

    for num_fila, fila in enumerate(filas[1:], start=2):
        try:
            # Obtener número de local
            numero_local = str(fila[col_local]).strip() if fila[col_local] is not None else ""
            if not numero_local:
                continue

            # Obtener valor
            valor = parsear_decimal(fila[col_valor] if col_valor is not None else None)
            if valor is None:
                valor = Decimal("0")

            # Obtener fecha
            fecha = parsear_fecha(fila[col_fecha] if col_fecha is not None else None)
            if fecha is None:
                fecha = date.today()

            # Obtener otros campos
            mes = str(fila[col_mes]).strip() if col_mes is not None and fila[col_mes] else ""
            empresario = str(fila[col_empresario]).strip() if col_empresario is not None and fila[col_empresario] else ""
            rut = str(fila[col_rut]).strip() if col_rut is not None and fila[col_rut] else ""
            descripcion = str(fila[col_descripcion]).strip() if col_descripcion is not None and fila[col_descripcion] else nombre_hoja
            fecha_pago = parsear_fecha(fila[col_fecha_pago] if col_fecha_pago is not None else None)

            # Crear o actualizar local
            local, _ = Local.objects.get_or_create(
                numero=numero_local,
                defaults={'tipo': tipo_local, 'ocupado': True}
            )
            if local.tipo != tipo_local:
                local.tipo = tipo_local
                local.save()

            # Generar folio
            folio = f"{numero_local}-{fecha.year}-{fecha.month:02d}"

            # Verificar si ya existe
            pago_existente = Pago.objects.filter(folio=folio, local=local).first()

            if pago_existente:
                # Actualizar
                pago_existente.empresario = empresario
                pago_existente.rut = rut
                pago_existente.descripcion = descripcion
                pago_existente.valor = valor
                pago_existente.fecha_pago = fecha_pago
                pago_existente.save()
                actualizados += 1
            else:
                # Crear
                Pago.objects.create(
                    local=local,
                    folio=folio,
                    fecha=fecha,
                    mes=mes,
                    empresario=empresario,
                    rut=rut,
                    descripcion=descripcion,
                    valor=valor,
                    fecha_pago=fecha_pago,
                )
                creados += 1

        except Exception as exc:
            errores += 1
            if errores <= 5:
                print(f"  [ERROR] Fila {num_fila}: {exc}")

    print(f"  [OK] Creados: {creados}, Actualizados: {actualizados}, Errores: {errores}")
    return {
        'creados': creados,
        'actualizados': actualizados,
        'errores': errores,
    }


def main():
    archivo = r'C:\Users\cfernandez\Downloads\DEUDA ARRIENDO.xlsx'

    if not os.path.exists(archivo):
        print(f"[ERROR] No se encontro el archivo: {archivo}")
        return

    print(f"[ABRIENDO] Archivo: {archivo}")
    wb = load_workbook(archivo, data_only=True)

    # Obtener usuario admin
    try:
        usuario = User.objects.get(username='admin')
    except User.DoesNotExist:
        print("[ERROR] No se encontro el usuario 'admin'")
        return

    total_creados = 0
    total_actualizados = 0
    total_errores = 0

    # Importar cada hoja
    for nombre_hoja in wb.sheetnames:
        ws = wb[nombre_hoja]
        resultado = importar_hoja(ws, nombre_hoja, usuario)
        if resultado:
            total_creados += resultado['creados']
            total_actualizados += resultado['actualizados']
            total_errores += resultado['errores']

    print(f"\n" + "="*50)
    print(f"[RESUMEN TOTAL]")
    print(f"   Creados: {total_creados}")
    print(f"   Actualizados: {total_actualizados}")
    print(f"   Errores: {total_errores}")
    print(f"   Locales totales: {Local.objects.count()}")
    print(f"   Pagos totales: {Pago.objects.count()}")
    print("="*50)


if __name__ == '__main__':
    main()
