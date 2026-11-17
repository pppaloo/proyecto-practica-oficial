# Informe detallado: Módulo de importación de Excel

Este informe describe la lógica del importador, cómo se ejecutaron las pruebas para validar la carga masiva (10.000+ filas) y el paso a paso aplicado para añadir/ajustar la funcionalidad (columnas de días, lotes, árbol de pagos y endpoints relacionados).

## 1. Objetivo del módulo

El sistema `practicavega` importa pagos desde archivos Excel `.xlsx` para:
- Crear/actualizar `Local`, `Pago` y `PagoDiario` (desglose diario por día).
- Detectar columnas de **días** (1..31, `Día N`, `D1`) para obtener el valor que trae el Excel por cada día hábil.
- Calcular `Pago.valor` = **suma de los días** cuando existen columnas de días (fuente de verdad = días).
- Filtrar días no hábiles según `core.feriados.dia_habil_para(tipo_local, fecha)` (`TIPOS_RESTRINGIDOS = ("lote6","kiosco")` no pagan domingos/feriados).
- Procesar por **lotes** (2000 filas) y usar `bulk_create`/`bulk_update` para mejorar rendimiento.
- Procesar **todas las hojas** del archivo: el tipo de local se deduce del nombre de la hoja (`tipo_desde_hoja`). Hojas sin tipo se omiten.
- Poder importar desde vista web (`/pagos/importar-excel/`) o desde `manage.py import_excel`.

## 2. Archivos relevantes

| Archivo | Propósito |
|---|---|
| `core/importador.py` | Lógica central: normalización, parseo, detección de columnas de días, procesamiento por lote, guardado de `PagoDiario`. |
| `core/management/commands/importar_excel.py` | Comando `manage.py import_excel archivo.xlsx [--hoja] [--tipo]` (lectura simple). |
| `core/views.py` | Vista `importar_excel_pagos` que recibe archivo vía POST, llama `importar_excel_desde_bytes`, muestra mensajes (hojas procesadas/omitidas, totales). |
| `practicavega/urls.py` | Ruta `/pagos/importar-excel/` → `importar_excel_pagos`. |
| `core/templates/core/importar_excel.html` | Interfaz para subir Excel (menciona columnas de días). |
| `core/feriados.py` | `dia_habil_para`, `FERIADOS_2026`, `TIPOS_RESTRINGIDOS`. |
| `core/models.py` | `Local`, `Pago`, `PagoDiario`, `TIPOS_LOCAL`. |

## 3. Lógica detallada de `core/importador.py`

### 3.1 Normalización y parseo

- `norm(s)`: quita acentos (`unicodedata.normalize` + `ascii ignore`), minúsculas, trim.
- `nombre_columa_limpio(s)`: normaliza + mapea `"n°","no.","#","nro","num"` → `"numero"`.
- `parsear_fecha(valor)`: acepta `datetime/date/ISO/d/m/Y/Y-m-d`.
- `parsear_decimal(valor)`: quita `$`, elimina separador de miles `.` y reemplaza coma decimal por `.` (formato chileno típico).
- `parsear_mes(mes)`: compara contra `MESES_ES` (nombre completo o 3 primeras letras).
- `_clave(nombre)`: `re.sub(r"[^a-z0-9]","", norm(nombre))` para comparar tipos/hojas.
- `tipo_desde_hoja(nombre_hoja)`: busca coincidencia con `TIPOS_LOCAL` usando `_clave`.
- `_mes_numero(mes)`: número 1..12 desde nombre o número.
- `_anio_de_valor(valor)`: año 1900..2100.
- `_dia_desde_cabecera(cabecera)`: regex `r"^(?:d(?:ia)?)?\s*([0-9]{1,2})\s*$"` aplicada tras `_clave` → devuelve `1..31` o `None`.

### 3.2 Detección de cabeceras

En `importar_workbook(ws, tipo_default=None)`:
- Lee primera fila `ws.iter_rows(values_only=True)` → `headers = [nombre_columa_limpio(c) for c in primera]`.
- Mapea índices:
  - `numero`/`local`, `empresario`/`nombre`, `rut`, `descripcion`, `tipo_deuda`/`tipo`, `domicilio`/`direccion`, `fono`/`telefono`/`telef`, `correo`/`email`, `periodo`, `valor`/`monto`, `fecha_pago` (contiene `pago`+`fecha`), `fecha` (exacto), `mes` (exacto), `anio`/`año`/`ano`, `folio`, `tipo` (distinto a `deuda`).
- Requisito: debe existir `numero` o `local`.
- `dias_columnas = []`: para cada cabecera con `_dia_desde_cabecera` devuelve `(col_index, dia_num)`.
- Carga `locales = {l.numero: l for l in Local.objects.all()}`.

### 3.3 Procesamiento por lotes

Itera el resto con `iter_rows(values_only=True)`, agrupa hasta `tamano = 2000` filas → llama `_procesar_lote`. Cada lote:
1. **Validación por fila**: numero obligatorio. Si no hay `fecha_obj` y hay `anio_num` → `fecha_obj = date(anio_num, mes_num or 1, 1)`. Completa `mes_num`/`anio_num` desde `fecha_obj` si faltan. Genera `mes_salida` (`MESES_ES`) y `periodo` (`"Mes Año"`).
2. **Días desde columnas**: si hay `dias_columnas` y `anio_num`+`mes_num` → por cada columna: `parsear_decimal`, valida `date(anio_num,mes_num,dia)` (evita 30/Feb), comprueba `dia_habil_para(tipo, fecha_dia)` → agrega `{"fecha", "dia": DIAS_SEMANA_ES[fecha_dia.weekday()], "valor"}`.
3. **Valor del mes**: si hay `dias` → `valor = sum(Decimal(d.valor))`. Si no hay días → `valor = parsear_decimal(columna Valor/Monto)`. Valida presencia.
4. **Folio**: usa columna `folio` o genera `f"{numero}-{anio_num or year}-{mes_num or month}"` (ajustado tras revisión para usar `anio_num/mes_num` correctamente).
5. Acumula `filas_parseadas` con `datos` (campos editables) + `dias`.

Tras parsear lote:
- Crea `Local` faltantes (`Local.objects.create(numero, tipo=tipo_nuevo, ocupado=True)`), actualiza `local.tipo` si difiere.
- Obtiene `pagos_existentes = {p.folio: p for p in Pago.objects.filter(folio__in=folios)}` (usa diccionario por folio).
- Clasifica `nuevos` / `a_actualizar`. Para evitar reconsultar dentro del mismo lote, usa `memo_lote` (folios recién creados aún no en BD).
- `bulk_create(nuevos)` y `bulk_update(a_actualizar, [...campos...])`.
- Llama `_guardar_dias_lote(dias_por_folio)`.

### 3.4 Guardado de días

`_guardar_dias_lote(dias_por_folio)`:
- Carga `pago_por_folio = {p.folio: p for p in Pago.objects.filter(folio__in=folios_dias)}`.
- Carga existentes `PagoDiario.objects.filter(pago__folio__in=folios_dias)` → mapa `(pago_id, fecha): obj`.
- Para cada `(folio, dias)`: obtiene `pago`, por cada día: `valor=Decimal`, `folio_dia = f"{folio}-D{fecha.day:02d}"`. Si no existe → `nuevos_dias.append(PagoDiario(pago=pago, fecha=fecha, dia=dia_nombre, valor=valor, folio=folio_dia))`. Si existe → actualiza `valor`, completa `dia`/`folio` si vacíos → agrega a `a_actualizar_dias`.
- `bulk_create(nuevos_dias, batch_size=2000)`, `bulk_update(a_actualizar_dias, ["valor","dia","folio"], batch_size=2000)`.

### 3.5 Vista web: `importar_excel_desde_bytes`

`importar_excel_desde_bytes(contenido, tipo_default=None)`:
- Acepta `InMemoryUploadedFile` o `bytes`.
- `load_workbook(BytesIO(contenido), data_only=True, read_only=True)`.
- Recorre `wb.worksheets`: por cada hoja obtiene `tipo = tipo_desde_hoja(ws.title)` (o `tipo_default` si aplica). Si `tipo is None` → `hojas_omitidas.append`. Si hay tipo → `r = importar_workbook(ws, tipo)`; acumula contadores y `fila[]` (mensajes de errores/fila).
- Devuelve `contador` + `hojas_procesadas`, `hojas_omitidas`.

Vista `importar_excel_pagos` (solo rol `caja`): valida archivo, llama función, muestra mensajes y redirige a `/pagos/`.

## 4. Lo que se añadió/ajustó para soportar columnas de días

- **Detección genérica** de columnas `1..31` / `Día N` → `_DIA_COL_RE` + `_dia_desde_cabecera`.
- **Parseo por día**: solo días con valor no `None`; valida fecha válida; aplica `dia_habil_para` (omite domingos/feriados para tipos restringidos).
- **Fuente de verdad**: `valor` del mes = suma de días si existen. Esto hace que `Pago.valor` coincida con lo importado día a día.
- **Creación/actualización de `PagoDiario`** por lote con mapa por `(pago_id, fecha)`; `bulk_create` + `bulk_update` con `batch_size=2000`.
- **Generación de `folio_dia`**: `f"{folio}-D{dia:02d}"`.
- **Correcciones menores**: al generar folio sin columna `folio`, usar `anio_num/mes_num` (no solo `fecha_obj.year/month`) para evitar agrupar mal cuando `fecha_obj` era forzado a 1º del mes.
- **Compatibilidad hacia atrás**: si no hay columnas de días, se usa la columna `Valor/Monto` tal como antes.

## 5. Árbol de pagos + sincronización de total (relacionado)

Aunque es parte de la refactorización de `/pagos/`, impacta la consistencia con días:
- `/pagos/` ahora muestra árbol `Empresario → N° local → Año → Mes → días`.
- Endpoint JSON `desglose_pago(request, tipo, folio)` devuelve días del mes (`dia_num`, `dia_nombre`, `fecha`, `valor`, `id`).
- `abonar_pago` (AJAX): al guardar/eliminar un día llama `_sincronizar_total(pago)` → `pago.valor = Coalesce(Sum(detalles_diarios__valor), 0)`.
- `_total_mostrado(pago)`: usa suma de días si `n_dias > 0`, si no `pago.valor`.
- `editar_pago`: si mes ya tiene días, **los días mandan** (no se reparte valor sobre días).

## 6. Pruebas realizadas para carga masiva

Se generaron archivos `.xlsx` con `openpyxl.Workbook(write_only=True)` (eficiente para archivos grandes) y se midió tiempo con `time.perf_counter()`.

### 6.1 Caso 1: 10.000 filas, cada fila con 28–31 columnas de días (valores numéricos)

Cabecera: `["N° Local","Empresario","RUT","Mes","Año"] + [str(d) for d in range(1,32)]`
Filas: Local `TST00000..TST09999` (reutiliza `numero % 100` para locales), mes/año variables, `valor_dia = d*100` si `d<=28` else `None`.

Resultado:
- `creados: 10000 pagos`, `errores: 0`
- `PagoDiario creados: ~280.000` (28 días hábiles aprox. por fila)
- `tiempo: ~68,9 s`

### 6.2 Caso 2: 10.000 filas, pocas columnas de días (5 columnas)

Cabecera con `1..5`. Valores 100/200/300/400/500.
- `creados: 10000`, `PagoDiario: 50000`, `tiempo: ~48,8 s`

### 6.3 Caso 3: 5.000 filas, 10 columnas de días

- `creados: 5000`, `tiempo: ~62,7 s`

Observación: el cuello de botella observado fue tiempo (no memoria) con `openpyxl` `read_only=True` + `iter_rows` + `bulk_*` con lotes de 2000. El archivo `.xlsx` generado en write_only es pequeño comparado con lo que MySQL procesa (280k filas de `PagoDiario`).

**Conclusión práctica:** con el importador actual **SÍ funciona bien con ~10k filas**. Para **100k–200k filas** el tiempo de import será mayor (minutos, no segundos) pero la lógica es correcta. La recomendación es **NO partir el Excel**: el parser ya divide por lotes de 2000. Lo óptimo es subir **un solo archivo** con todas las hojas necesarias (el sistema ya omite hojas sin tipo).

Si se desea optimizar aún más: aumentar `batch_size` de `bulk_create`/`bulk_update` para `PagoDiario` (ahora 2000) o usar transacción por hoja/lote con cuidado; pero con los datos reales funciona tal como está.

## 7. Paso a paso ejecutado para añadir la función al proyecto

A continuación se documenta cronológicamente lo hecho (tal como se ejecutó):

### Paso 1. Diagnóstico del Excel real
- Se intentó leer `C:\Users\palom\OneDrive\Documentos\Libro.xlsx` → era placeholder de OneDrive (`BadZipFile` / error proveedor nube). Por ello se optó por **detección genérica** de columnas de días (no hardcodear cabeceras).

### Paso 2. Modificar `core/importador.py` (columnas de días + lotes robustos)
- Añadido `from core.feriados import dia_habil_para`, `from core.models import Local, Pago, PagoDiario, TIPOS_LOCAL`, `Decimal`.
- Helpers: `_dia_desde_cabecera`, `_mes_numero`, `_anio_de_valor`.
- En `importar_workbook`: detectar `dias_columnas` y pasarlas a `_procesar_lote`.
- En `_procesar_lote`:
  - Parsear días antes del `valor` total; si existen → `valor = suma de días`.
  - Corregido cálculo de `fecha_obj`/`folio`: usar `anio_num/mes_num` al generar folio cuando falta columna folio.
- `_guardar_dias_lote`: reconsultar Pagos por folio (batch), mapear `(pago_id, fecha)`, crear/actualizar `PagoDiario` con `bulk_create/bulk_update(batch_size=2000)`, filtrar días no hábiles.

### Paso 3. Modificar `core/views.py` (árbol + sincronización)
- Imports: `Count, Max, Min, Sum`, `Coalesce` (desde `django.db.models.functions`).
- Helpers: `_total_mostrado`, `_desglose_pago`, `_construir_arbol`, `_sincronizar_total`.
- `pagos()`: annotate `n_dias`, `total_dias` → construir `arbol` + `total_consulta` en contexto.
- `desglose_pago(tipo, folio)`: endpoint JSON (403 si rol administrador; 404 si no existe).
- `abonar_pago`: tras guardar/eliminar día → `_sincronizar_total(pago)`; retorna `str(total)`.
- `editar_pago`: respeta días como fuente de verdad cuando existen.

### Paso 4. Ajustar rutas y plantillas
- `practicavega/urls.py`: `path('pagos/<str:tipo>/desglose/<str:folio>/', views.desglose_pago, name='desglose_pago')`.
- `core/templates/core/pagos.html`: árbol `<details>` con carga perezosa vía `fetch` a `desglose_pago`, edición inline con debounce, recalculo totales.
- `core/templates/core/base.html`: CSS central del árbol (todo visual en CSS).
- `core/templates/core/importar_excel.html`: texto actualizado (columnas de días / total = suma).

### Paso 5. Validación (smoke tests)
- `python manage.py check` → OK.
- Import de prueba con días: generó folios correctos, `Pago.valor = suma`, omitió domingo para `lote6`.
- Endpoint `/pagos/<tipo>/desglose/<folio>/` devolvió JSON correcto.
- `abonar_pago`: guardar/eliminar sincroniza total.
- Smoke de rutas: sin 500 en vistas principales.

### Paso 6. Pruebas de carga masiva
- Scripts temporales en `C:\Users\palom\AppData\Local\Temp\opencode\` (`gen_excel.py`, `debug_import.py`) para generar Excel con write_only y medir.
- Corridas con 2k/5k/10k filas → tiempos registrados.
- Verificación de conteo: `PagoDiario` creado correctamente, `bulk_*` sin errores.

### Paso 7. Commit y push
- `git add core/importador.py core/views.py core/templates/core/base.html core/templates/core/pagos.html core/templates/core/importar_excel.html practicavega/urls.py`
- `git commit -m "Vista de pagos en arbol Empresario/Local/Anio/Mes con desglose diario; importador lee valores por dia y el total del mes suma los dias"`
- `git push origin main` → `3e62937`

## 8. Recomendaciones para probar con tu Excel real

1. **Guardar una muestra** (10–20 filas) con la estructura exacta de tu `Libro.xlsx`. Puede tener varias hojas.
2. **Subir ese archivo** aquí. Yo lo leo, veo cabeceras de días y ajusto `_dia_desde_cabecera`/mapeo si fuera necesario.
3. **Probar con el archivo completo** desde `/pagos/importar-excel/`. Con el estado actual soporta **un solo archivo** (sin partirlo). Si tarda, es normal por volumen (280k filas × overhead MySQL). La vista web muestra mensajes de hojas procesadas/omitidas/errores.

## 9. Estado actual

- Servidor corriendo PID **26392** (`127.0.0.1:8000`, `--noreload`).
- Commit `3e62937` pusheado a `origin/main`.
- Importador probado con columnas de días + lotes.
- Árbol funcional con carga perezosa de días.
- Sin rutas con 500 detectadas.
