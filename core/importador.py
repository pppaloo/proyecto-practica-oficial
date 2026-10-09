import re
import unicodedata
from datetime import date, datetime

from core.models import Local, Pago, TIPOS_LOCAL


MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def norm(s):
    if s is None:
        return ""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()


def nombre_columa_limpio(s):
    n = norm(s)
    n = n.replace("n°", "numero").replace("no.", "numero").replace("#", "numero")
    n = n.replace("nro", "numero").replace("num", "numero")
    return n


def parsear_fecha(valor):
    if valor is None or str(valor).strip() == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def parsear_decimal(valor):
    if valor is None or str(valor).strip() == "":
        return None
    if isinstance(valor, (int, float)):
        return valor
    s = str(valor).replace("$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parsear_mes(mes):
    if not mes:
        return ""
    n = norm(mes)
    for i, m in enumerate(MESES_ES, start=1):
        if norm(m) == n or norm(m)[:3] == n[:3]:
            return m
    return mes


def _clave(nombre):
    """Normaliza un nombre para comparar: 'Centro Comercial' -> 'centrocomercial'."""
    if not nombre:
        return ""
    return re.sub(r"[^a-z0-9]", "", norm(nombre))


def tipo_desde_hoja(nombre_hoja):
    """Devuelve el tipo de local según el nombre de la hoja, o None si no coincide."""
    clave = _clave(nombre_hoja)
    if not clave:
        return None
    for valor, _nombre in TIPOS_LOCAL:
        if clave == _clave(valor):
            return valor
    return None


def importar_workbook(ws, tipo_default=None):
    """Lee una hoja de Excel y crea/actualiza Pagos por lotes. Devuelve dict de contador."""
    contador = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "errores": 0, "fila": []}

    iterador = ws.iter_rows(values_only=True)
    try:
        primera = next(iterador)
    except StopIteration:
        contador["error"] = "El Excel está vacío."
        return contador

    headers = [nombre_columa_limpio(c) for c in primera]
    idx = {
        "numero": next((i for i, h in enumerate(headers) if "numero" in h and "local" not in h and "folio" not in h), None),
        "local": next((i for i, h in enumerate(headers) if "local" in h and "numero" not in h), None),
        "empresario": next((i for i, h in enumerate(headers) if "empresario" in h or "nombre" in h), None),
        "rut": next((i for i, h in enumerate(headers) if "rut" in h), None),
        "descripcion": next((i for i, h in enumerate(headers) if "descripcion" in h), None),
        "tipo_deuda": next((i for i, h in enumerate(headers) if "deuda" in h or "tipo" in h), None),
        "domicilio": next((i for i, h in enumerate(headers) if "domicilio" in h or "direccion" in h), None),
        "fono": next((i for i, h in enumerate(headers) if "fono" in h or "telefono" in h or "telef" in h), None),
        "correo": next((i for i, h in enumerate(headers) if "correo" in h or "email" in h), None),
        "periodo": next((i for i, h in enumerate(headers) if "periodo" in h), None),
        "valor": next((i for i, h in enumerate(headers) if "valor" in h or "monto" in h), None),
        "fecha_pago": next((i for i, h in enumerate(headers) if "pago" in h and "fecha" in h), None),
        "fecha": next((i for i, h in enumerate(headers) if h == "fecha"), None),
        "mes": next((i for i, h in enumerate(headers) if h == "mes"), None),
        "anio": next((i for i, h in enumerate(headers) if h in ("anio", "año") or "anio" in h), None),
        "folio": next((i for i, h in enumerate(headers) if "folio" in h), None),
        "tipo": next(
            (i for i, h in enumerate(headers) if h == "tipo"),
            next((i for i, h in enumerate(headers) if "tipo" in h and "deuda" not in h), None),
        ),
    }
    if idx["numero"] is None and idx["local"] is None:
        contador["error"] = "No se encontró la columna 'N° Local'. Cabeceras: %s" % [h or "?" for h in headers]
        return contador

    locales = {l.numero: l for l in Local.objects.all()}
    tamano = 2000
    lote_rows = []
    for num_fila, fila in enumerate(iterador, start=2):
        if not any(c not in (None, "") for c in fila):
            continue
        lote_rows.append((num_fila, fila))
        if len(lote_rows) >= tamano:
            _procesar_lote(lote_rows, idx, tipo_default, locales, contador)
            lote_rows = []
    if lote_rows:
        _procesar_lote(lote_rows, idx, tipo_default, locales, contador)

    return contador


def _procesar_lote(filas, idx, tipo_default, locales, contador):
    """Procesa un lote de filas: parsea, crea Locales faltantes y crea/actualiza Pagos en bloque."""
    filas_parseadas = []
    for num_fila, fila in filas:
        numero_celda = fila[idx["numero"] if idx["numero"] is not None else idx["local"]]
        numero = str(numero_celda).strip() if numero_celda is not None else ""
        if not numero:
            contador["errores"] += 1
            contador["fila"].append(f"Fila {num_fila}: N° Local vacío, se omitió.")
            continue

        tipo = fila[idx["tipo"]] if idx["tipo"] is not None else None
        tipo = (str(tipo).strip() if tipo else tipo_default) or "local"

        fecha_pago_obj = parsear_fecha(fila[idx["fecha_pago"]] if idx["fecha_pago"] is not None else None)
        fecha_obj = parsear_fecha(fila[idx["fecha"]] if idx["fecha"] is not None else None)
        if fecha_obj is None and fecha_pago_obj is not None:
            fecha_obj = fecha_pago_obj
        if fecha_obj is None:
            anio = str(fila[idx["anio"]]).strip() if idx["anio"] is not None and fila[idx["anio"]] else None
            if anio and anio.isdigit():
                fecha_obj = date(int(anio), 1, 1)

        mes_salida = parsear_mes(fila[idx["mes"]] if idx["mes"] is not None else None)
        if not mes_salida and fecha_obj:
            mes_salida = MESES_ES[fecha_obj.month - 1]
        periodo = str(fila[idx["periodo"]]).strip() if idx["periodo"] is not None and fila[idx["periodo"]] else ""
        if not periodo and fecha_obj:
            periodo = f"{mes_salida} {fecha_obj.year}"

        valor = parsear_decimal(fila[idx["valor"]] if idx["valor"] is not None else None)
        if valor is None:
            contador["errores"] += 1
            contador["fila"].append(f"Fila {num_fila}: valor inválido o faltante en local {numero}.")
            continue

        folio = str(fila[idx["folio"]]).strip() if idx["folio"] is not None and fila[idx["folio"]] else ""
        if not folio and fecha_obj:
            folio = f"{numero}-{fecha_obj.year}-{fecha_obj.month}"
        if not folio:
            contador["errores"] += 1
            contador["fila"].append(f"Fila {num_fila}: sin folio y sin fecha para generarlo en local {numero}, se omitió.")
            continue

        filas_parseadas.append({
            "num_fila": num_fila,
            "numero": numero,
            "tipo": tipo,
            "folio": folio,
            "datos": {
                "fecha": fecha_obj,
                "mes": mes_salida,
                "empresario": str(fila[idx["empresario"]]).strip() if idx["empresario"] is not None and fila[idx["empresario"]] else "",
                "rut": str(fila[idx["rut"]]).strip() if idx["rut"] is not None and fila[idx["rut"]] else "",
                "descripcion": str(fila[idx["descripcion"]]).strip() if idx["descripcion"] is not None and fila[idx["descripcion"]] else "",
                "tipo_deuda": str(fila[idx["tipo_deuda"]]).strip() if idx["tipo_deuda"] is not None and fila[idx["tipo_deuda"]] else "",
                "domicilio": str(fila[idx["domicilio"]]).strip() if idx["domicilio"] is not None and fila[idx["domicilio"]] else "",
                "fono": str(fila[idx["fono"]]).strip() if idx["fono"] is not None and fila[idx["fono"]] else "",
                "correo": str(fila[idx["correo"]]).strip() if idx["correo"] is not None and fila[idx["correo"]] else "",
                "periodo": periodo,
                "valor": valor,
                "fecha_pago": fecha_pago_obj,
            },
        })

    if not filas_parseadas:
        return

    numeros = {r["numero"] for r in filas_parseadas}
    for n in numeros:
        if n in locales:
            continue
        tipo_nuevo = next((r["tipo"] for r in filas_parseadas if r["numero"] == n), tipo_default) or "local"
        locales[n] = Local.objects.create(numero=n, tipo=tipo_nuevo, ocupado=True)

    folios = {r["folio"] for r in filas_parseadas}
    pagos_existentes = {
        p.folio: p for p in Pago.objects.filter(folio__in=folios)
    }

    nuevos = []
    a_actualizar = []
    memo_lote = {}

    for r in filas_parseadas:
        folio = r["folio"]
        local = locales[r["numero"]]
        if r["tipo"] and local.tipo != r["tipo"]:
            local.tipo = r["tipo"]
            local.save()

        pago = pagos_existentes.get(folio)
        if pago is None and folio in memo_lote:
            pago = memo_lote[folio]
            for campo, valor in r["datos"].items():
                setattr(pago, campo, valor)
            pago.local = local
            continue

        if pago is None:
            pago = Pago(local=local, folio=folio, **r["datos"])
            memo_lote[folio] = pago
            nuevos.append(pago)
            contador["creados"] += 1
            continue

        cambiado = False
        for campo, valor_campo in r["datos"].items():
            if getattr(pago, campo) != valor_campo:
                setattr(pago, campo, valor_campo)
                cambiado = True
        if pago.local != local:
            pago.local = local
            cambiado = True
        if cambiado:
            a_actualizar.append(pago)
            contador["actualizados"] += 1
        else:
            contador["sin_cambios"] += 1

    if nuevos:
        Pago.objects.bulk_create(nuevos)
    if a_actualizar:
        Pago.objects.bulk_update(
            a_actualizar,
            ["fecha", "mes", "empresario", "rut", "descripcion", "tipo_deuda",
             "domicilio", "fono", "correo", "periodo", "valor", "fecha_pago", "local"],
        )


def importar_excel_desde_bytes(contenido, tipo_default=None):
    """Recibe bytes de un .xlsx y devuelve el dict de contador (o mensaje de error).

    Lee todas las hojas: el tipo de local se deduce del nombre de la hoja
    ('Centro Comercial' -> centro_comercial, 'Lote 6' -> lote6, etc.).
    Hojas cuyo nombre no coincide con ningún tipo se omiten.
    """
    from django.core.files.uploadedfile import InMemoryUploadedFile

    if isinstance(contenido, InMemoryUploadedFile):
        contenido = contenido.read()

    from io import BytesIO
    from openpyxl import load_workbook

    try:
        wb = load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    except Exception as exc:
        return {"error": f"No se pudo leer el archivo como Excel: {exc}"}

    contador = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "errores": 0, "fila": []}
    hojas_procesadas = []
    hojas_omitidas = []

    try:
        for ws in wb.worksheets:
            tipo = tipo_desde_hoja(ws.title)
            if tipo is None and tipo_default:
                tipo = tipo_default
            if tipo is None:
                hojas_omitidas.append(ws.title)
                continue
            r = importar_workbook(ws, tipo)
            if r.get("error"):
                return {"error": f"{ws.title}: {r['error']}"}
            for k in ("creados", "actualizados", "sin_cambios", "errores"):
                contador[k] += r[k]
            contador["fila"].extend(r["fila"])
            hojas_procesadas.append(ws.title)
    finally:
        wb.close()

    contador["hojas_procesadas"] = hojas_procesadas
    contador["hojas_omitidas"] = hojas_omitidas
    return contador