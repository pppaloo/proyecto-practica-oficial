import datetime

FERIADOS_2026 = {
    datetime.date(2026, 1, 1),
    datetime.date(2026, 4, 3),
    datetime.date(2026, 4, 4),
    datetime.date(2026, 5, 1),
    datetime.date(2026, 5, 21),
    datetime.date(2026, 6, 29),
    datetime.date(2026, 7, 16),
    datetime.date(2026, 8, 15),
    datetime.date(2026, 9, 18),
    datetime.date(2026, 9, 19),
    datetime.date(2026, 10, 12),
    datetime.date(2026, 10, 31),
    datetime.date(2026, 11, 1),
    datetime.date(2026, 12, 8),
    datetime.date(2026, 12, 25),
}

TIPOS_RESTRINGIDOS = ("lote6", "kiosco")


def dia_habil_para(tipo, fecha):
    if tipo in TIPOS_RESTRINGIDOS:
        es_domingo = fecha.weekday() == 6
        es_feriado = fecha in FERIADOS_2026
        return not es_domingo and not es_feriado
    return True


def mensaje_no_habil(tipo, fecha):
    if dia_habil_para(tipo, fecha):
        return ""
    if fecha.weekday() == 6:
        return "Este tipo de local no paga domingos."
    return "Este tipo de local no paga feriados."


def siguiente_dia_habil(tipo, fecha):
    while not dia_habil_para(tipo, fecha):
        fecha = fecha + datetime.timedelta(days=1)
    return fecha
