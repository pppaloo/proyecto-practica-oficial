# -*- coding: utf-8 -*-
"""
Importa TODOS los datos del Excel 'DEUDA CENTRO COMERCIAL (2).xlsx' a MySQL.

Uso:
    python importar_excel_mysql.py            # importa de verdad
    python importar_excel_mysql.py --dry-run  # solo parsea y reporta, no escribe

Estrategia:
  - 1 Pago por (tipo, local, mes) con valor = suma de los dias.
  - 1 PagoDiario por (local, fecha) con el valor del dia (suma si hay varios contratos).
  - Folio generado: {CODIGO}-{local}-{YYYY}-{MM} (ignora la columna Folio del Excel,
    que NO es unica y colapsaria los datos).
  - Clave unica de Local: (numero, tipo) (no solo numero).
  - Dedup: se descartan solo las filas EXACTAMENTE identicas (mismo local, fecha,
    valor, folio y empresario). Los dias con dos contratos distintos se suman.
"""
import argparse
import sys
import time
from datetime import date, datetime
from decimal import Decimal

import openpyxl
import mysql.connector

sys.stdout.reconfigure(encoding="utf-8")

ARCHIVO = r"C:\Users\palom\Downloads\DEUDA CENTRO COMERCIAL (2).xlsx"

HOJAS = {
    "Centro Comercial": "centro_comercial",
    "Boleterias": "boleteria",
    "Pescaderias": "pescaderia",
    "Lote 6": "lote6",
    "Ex Copihue": "kiosco",
    "Kiosco": "kiosco",
}

# Hojas con un registro por mes (no diario): no generan PagoDiario.
HOJAS_MENSUALES = {"Boleterias", "Pescaderias"}

CODIGO_TIPO = {
    "centro_comercial": "CC",
    "boleteria": "BO",
    "pescaderia": "PE",
    "lote6": "L6",
    "kiosco": "KI",
}

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS_SEMANA_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MES_NOMBRES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]

DB = {"host": "localhost", "user": "root", "password": "12345", "database": "centro_comercial"}


def nombre_columa_limpio(s):
    if s is None:
        return ""
    import unicodedata, re
    n = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()
    n = n.replace("n°", "numero").replace("no.", "numero").replace("#", "numero")
    n = n.replace("nro", "numero").replace("num", "numero")
    return n


def parsear_mes_anio(valor, fecha_fallback):
    if hasattr(valor, "year"):
        return valor.year, valor.month
    if valor is None or str(valor).strip() == "":
        return fecha_fallback.year, fecha_fallback.month
    s = str(valor).strip().lower()
    import re
    m_anio = re.search(r"(19|20)\d{2}", s)
    anio = int(m_anio.group(0)) if m_anio else fecha_fallback.year
    mes = None
    for i, m in enumerate(MES_NOMBRES, start=1):
        if m in s:
            mes = i
            break
    if mes is None:
        partes = s.replace("-", " ").replace(".", " ").split()
        for pt in partes:
            if pt.isdigit() and 1 <= int(pt) <= 12:
                mes = int(pt)
                break
    if mes is None:
        mes = fecha_fallback.month
    return anio, mes


def parsear_decimal(valor):
    if valor is None or str(valor).strip() == "":
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    s = str(valor).replace("$", "").replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(s)
    except Exception:
        return None


def leer_excel():
    t0 = time.time()
    wb = openpyxl.load_workbook(ARCHIVO, read_only=True, data_only=True)

    # (tipo, numero) -> info del local
    locales = {}
    # (tipo, numero, anio, mes) -> pago
    pagos = {}
    # (tipo, numero, fecha) -> valor (sumado si hay varios contratos)
    dias = {}
    # dedup de filas exactamente identicas
    vistos = set()

    filas_total = 0
    filas_usadas = 0
    filas_descartadas = 0
    dedup_count = 0
    dedup_con_folio = 0
    dedup_sin_folio = 0

    last_local = None
    last_emp = ""
    last_rut = ""
    last_desc = ""

    for nombre, tipo in HOJAS.items():
        ws = wb[nombre]
        # leer encabezado completo
        try:
            header = next(ws.iter_rows(values_only=True, min_col=1, max_col=ws.max_column))
        except StopIteration:
            continue
        headers = [nombre_columa_limpio(c) if c is not None else "" for c in header]

        def find(keywords, exclude=()):
            for i, h in enumerate(headers):
                if not h:
                    continue
                if any(k in h for k in keywords) and not any(e in h for e in exclude):
                    return i
            return None

        idx_local = find(["local"], exclude=["numero"])
        if idx_local is None:
            idx_local = find(["numero"])
        idx_fecha = None
        for i, h in enumerate(headers):
            if h == "fecha" or ("fecha" in h and "pago" not in h and "termino" not in h and "contrato" not in h and "final" not in h):
                idx_fecha = i
                break
        idx_mes = next((i for i, h in enumerate(headers) if h == "mes"), None)
        idx_emp = find(["empresario", "nombre"])
        idx_rut = find(["rut"])
        idx_desc = find(["descripcion"])
        idx_valor = find(["valor", "monto"])
        idx_fpago = find(["fecha", "pago"])
        idx_folio = find(["folio"])

        if idx_local is None or idx_fecha is None:
            print(f"  [ADVERTENCIA] {nombre}: no se encontro local/fecha, se omite.")
            continue

        max_needed = max(x for x in [idx_local, idx_fecha, idx_mes, idx_emp, idx_rut,
                                     idx_desc, idx_valor, idx_fpago, idx_folio] if x is not None)
        it = ws.iter_rows(values_only=True, min_col=1, max_col=max_needed + 1)
        next(it)  # saltar encabezado

        # reset forward-fill por hoja
        last_local = None
        last_emp = ""
        last_rut = ""
        last_desc = ""

        for r in it:
            if not any(v not in (None, "") for v in r):
                continue
            filas_total += 1

            # forward-fill de celdas combinadas (Local, Empresario, Rut, Descripcion)
            raw_local = r[idx_local] if idx_local < len(r) else None
            if raw_local not in (None, ""):
                last_local = str(raw_local).strip()
            raw_emp = r[idx_emp] if (idx_emp is not None and idx_emp < len(r)) else None
            if raw_emp not in (None, ""):
                last_emp = str(raw_emp).strip()
            raw_rut = r[idx_rut] if (idx_rut is not None and idx_rut < len(r)) else None
            if raw_rut not in (None, ""):
                last_rut = str(raw_rut).strip()
            raw_desc = r[idx_desc] if (idx_desc is not None and idx_desc < len(r)) else None
            if raw_desc not in (None, ""):
                last_desc = str(raw_desc).strip()

            num = last_local if last_local else ""
            fraw = r[idx_fecha] if idx_fecha < len(r) else None
            if not num or not hasattr(fraw, "date"):
                filas_descartadas += 1
                continue
            f = fraw.date()

            mes_raw = r[idx_mes] if (idx_mes is not None and idx_mes < len(r)) else None
            anio, mes = parsear_mes_anio(mes_raw, f)
            if anio == 1900:
                filas_descartadas += 1
                continue
            try:
                fecha_real = date(anio, mes, f.day)
            except ValueError:
                filas_descartadas += 1
                continue

            valor_raw = r[idx_valor] if (idx_valor is not None and idx_valor < len(r)) else None
            v = parsear_decimal(valor_raw)
            if v is None:
                v = Decimal("0")

            empresario = last_emp
            rut = last_rut
            descripcion = last_desc if last_desc else nombre
            fp_raw = r[idx_fpago] if (idx_fpago is not None and idx_fpago < len(r)) else None
            fecha_pago = fp_raw.date() if hasattr(fp_raw, "date") else None
            folio_excel = str(r[idx_folio]).strip() if (idx_folio is not None and idx_folio < len(r) and r[idx_folio] not in (None, "")) else ""

            # NO se deduplica: se conservan TODAS las filas del Excel (incluidas las identicas)
            # (el usuario requiere los 205.199 datos sin excepcion)

            filas_usadas += 1
            locales.setdefault((tipo, num), {
                "empresario": empresario, "rut": rut, "descripcion": descripcion,
            })

            k_pago = (tipo, num, anio, mes)
            if k_pago not in pagos:
                pagos[k_pago] = {
                    "tipo": tipo, "numero": num, "anio": anio, "mes": mes,
                    "empresario": empresario, "rut": rut, "descripcion": descripcion,
                    "fecha_pago": fecha_pago, "valor": Decimal("0"), "dias": 0,
                }
            p = pagos[k_pago]
            p["valor"] += v
            p["dias"] += 1
            if p["fecha_pago"] is None and fecha_pago is not None:
                p["fecha_pago"] = fecha_pago

            k_dia = (tipo, num, fecha_real)
            if nombre not in HOJAS_MENSUALES:
                dias[k_dia] = dias.get(k_dia, Decimal("0")) + v

    wb.close()
    t1 = time.time()
    print(f"Lectura Excel: {t1-t0:.2f} s | filas total={filas_total:,} usadas={filas_usadas:,} descartadas={filas_descartadas:,} (sin dedup)")
    print(f"  locales={len(locales)}  pagos={len(pagos)}  dias={len(dias)}")
    print(f"  pagos con valor>0={sum(1 for x in pagos.values() if x['valor']>0)}")
    print(f"  suma total={sum(x['valor'] for x in pagos.values()):,.0f}")
    return locales, pagos, dias


def importar(dry_run):
    locales, pagos, dias = leer_excel()

    if dry_run:
        print("\n[DRY-RUN] No se escribio nada en MySQL.")
        return

    conn = mysql.connector.connect(**DB)
    cur = conn.cursor()
    t0 = time.time()

    # 1) limpiar
    print("\n[1/5] Limpiando tablas actuales...")
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    cur.execute("DELETE FROM core_pagodiario")
    cur.execute("DELETE FROM core_pago")
    cur.execute("DELETE FROM core_local")
    cur.execute("ALTER TABLE core_local AUTO_INCREMENT = 1")
    cur.execute("ALTER TABLE core_pago AUTO_INCREMENT = 1")
    cur.execute("ALTER TABLE core_pagodiario AUTO_INCREMENT = 1")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.commit()

    # 2) locales
    print("[2/5] Insertando locales...")
    items_loc = sorted(locales.items())  # ((tipo, numero), info)
    cur.executemany(
        "INSERT INTO core_local (numero, tipo, cantidad_utm, ocupado) VALUES (%s, %s, %s, %s)",
        [(num, tipo, "1.00", 1) for (tipo, num), _ in items_loc],
    )
    conn.commit()
    # mapear (tipo, numero) -> id
    cur.execute("SELECT id, numero, tipo FROM core_local")
    loc_id = {}
    for lid, num, tipo in cur.fetchall():
        loc_id[(tipo, num)] = lid
    print(f"   locales insertados: {len(loc_id)}")

    # 3) pagos
    print("[3/5] Insertando pagos...")
    filas_pago = []
    for p in pagos.values():
        code = CODIGO_TIPO[p["tipo"]]
        folio = f"{code}-{p['numero']}-{p['anio']}-{p['mes']:02d}"
        p["_folio"] = folio
        mes_nombre = MESES_ES[p["mes"] - 1]
        fecha = date(p["anio"], p["mes"], 1)
        periodo = f"{mes_nombre} {p['anio']}"
        fp = p["fecha_pago"].isoformat() if p["fecha_pago"] else None
        filas_pago.append((
            loc_id[(p["tipo"], p["numero"])],
            fecha.isoformat(),
            mes_nombre,
            p["empresario"],
            p["rut"],
            p["descripcion"],
            "",
            "",
            "",
            "",
            periodo,
            str(p["valor"]),
            fp,
            folio,
        ))
    # insertar en lotes
    BATCH = 2000
    for i in range(0, len(filas_pago), BATCH):
        cur.executemany(
            "INSERT INTO core_pago (local_id, fecha, mes, empresario, rut, descripcion, "
            "tipo_deuda, domicilio, fono, correo, periodo, valor, fecha_pago, folio) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            filas_pago[i:i + BATCH],
        )
    conn.commit()

    # mapear folio -> pago_id
    folios = [p["_folio"] for p in pagos.values()]
    pago_id = {}
    for i in range(0, len(folios), 2000):
        chunk = folios[i:i + 2000]
        placeholders = ",".join(["%s"] * len(chunk))
        cur.execute(f"SELECT id, folio FROM core_pago WHERE folio IN ({placeholders})", chunk)
        for pid, folio in cur.fetchall():
            pago_id[folio] = pid
    print(f"   pagos insertados: {len(pago_id)}")

    # 4) dias
    print("[4/5] Insertando dias (PagoDiario)...")
    filas_dia = []
    for (tipo, num, fecha_real), valor in dias.items():
        # encontrar el pago correspondiente: hay uno por mes; si hay varios folios, tomar el primero
        # (los dias se asignan al pago cuyo mes coincide)
        anio, mes = fecha_real.year, fecha_real.month
        code = CODIGO_TIPO[tipo]
        # buscar folio que exista
        folio_pago = f"{code}-{num}-{anio}-{mes:02d}"
        pid = pago_id.get(folio_pago)
        if pid is None:
            # puede que el pago se haya creado con otro folio (varios contratos) -> tomar cualquiera del mes
            # buscar en pagos
            candidatos = [pp["_folio"] for pp in pagos.values()
                          if pp["tipo"] == tipo and pp["numero"] == num
                          and pp["anio"] == anio and pp["mes"] == mes]
            if candidatos:
                pid = pago_id.get(candidatos[0])
        if pid is None:
            continue
        dia_nombre = DIAS_SEMANA_ES[fecha_real.weekday()]
        folio_dia = f"{folio_pago}-D{fecha_real.day:02d}"
        filas_dia.append((pid, fecha_real.isoformat(), dia_nombre, str(valor), folio_dia))

    for i in range(0, len(filas_dia), 2000):
        cur.executemany(
            "INSERT INTO core_pagodiario (pago_id, fecha, dia, valor, folio) VALUES (%s,%s,%s,%s,%s)",
            filas_dia[i:i + 2000],
        )
    conn.commit()
    print(f"   dias insertados: {len(filas_dia)}")

    cur.close()
    conn.close()
    t1 = time.time()
    print(f"\n[5/5] Importacion completa en {t1-t0:.2f} s (lectura incluida en paso 0).")

    # verificacion
    print("\n=== VERIFICACION ===")
    c2 = mysql.connector.connect(**DB)
    cu = c2.cursor()
    cu.execute("SELECT COUNT(*) FROM core_local"); print("  locales     :", cu.fetchone()[0])
    cu.execute("SELECT COUNT(*) FROM core_pago"); print("  pagos       :", cu.fetchone()[0])
    cu.execute("SELECT COUNT(*) FROM core_pagodiario"); print("  dias        :", cu.fetchone()[0])
    cu.execute("SELECT COALESCE(SUM(valor),0) FROM core_pago"); print("  suma pagos  :", cu.fetchone()[0])
    cu.execute("SELECT COALESCE(SUM(valor),0) FROM core_pagodiario"); print("  suma dias   :", cu.fetchone()[0])
    c2.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    importar(args.dry_run)


if __name__ == "__main__":
    main()
