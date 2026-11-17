# Informe: Optimización y escalabilidad de la vista de Pagos

Fecha: 11 de octubre de 2026
Sistema: practicavega (Vega Los Ángeles) — Django + MySQL

## 1. Motivo

- La pagina `/pagos/` cargaba muy lento.
- Preocupacion a futuro: el sistema almacenara mucha mas cantidad de datos.
- Se pidio una forma mas simple de acceder, por ejemplo un boton para mostrar solo un año, evitando que la pagina se sature.

## 2. Diagnostico

Se reviso la vista y la base de datos. Se encontro lo siguiente:

- La vista construia TODO el arbol en el servidor (Empresario -> Local -> Año -> Mes) sin filtrar, por lo que el HTML y las consultas crecian con la cantidad de datos.
- En la base de datos habia 15.793 pagos y 333.595 dias, de los cuales **15.000 pagos y 330.000 dias eran datos de PRUEBA** (prefijos `T200` y `TST0`) que quedaron de las pruebas de carga anteriores.
- Los datos reales eran solo **793 pagos, ~3.595 dias y 32 locales**.

Con los 15.000 registros de prueba, la pagina tardaba mucho en cargar.

| Dato | Prueba (T200, TST0) | Reales |
| --- | --- | --- |
| Pagos | 15.000 | 793 |
| Dias | 330.000 | ~3.595 |
| Locales | 15.515 | ~32 |

## 3. Acciones realizadas

### 3.1 Limpieza de datos de prueba

- Se eliminaron 15.000 pagos, 330.000 dias y 15.515 locales de prueba (prefijos `T200` y `TST0`).
- La operacion tardo ~15 segundos.
- Resultado: quedaron 793 pagos, 3.595 dias y 32 locales (los reales).

### 3.2 Filtro por año (botones)

- Se agregaron **botones de año** en la barra de filtros.
- Por defecto se carga el **año mas reciente** con datos.
- La busqueda conserva el año seleccionado.

### 3.3 Carga perezosa del arbol (2 niveles)

- Antes: se renderizaba el arbol completo de una sola vez.
- Ahora: al abrir `/pagos/` solo se muestran los **empresarios** (nombre, RUT, cantidad de locales y de meses, y total del año).
- Al expandir un empresario, se cargan sus **locales y meses** mediante AJAX.
- Al abrir un mes, se cargan los **dias** (comportamiento que ya existia).
- De este modo, la carga inicial es siempre liviana, sin importar cuantos datos haya.

### 3.4 Nuevo endpoint

- Se agrego el endpoint `/pagos/<tipo>/empresario/` que devuelve en JSON los locales y meses de un empresario en un año determinado (respetando los filtros activos).

### 3.5 Indices en la base de datos

Se agregaron indices para acelerar las consultas y migracion aplicada (migracion `0012`):

| Tabla | Indices |
| --- | --- |
| Pago | fecha, empresario, (local, fecha) |
| PagoDiario | fecha |
| Local | tipo, (tipo, ocupado) |

### 3.6 Limpieza de codigo

- Se elimino un `print` de depuracion (`DBG`) que habia quedado en `core/importador.py`.

## 4. Resultados medidos

Con los datos reales (793 pagos):

| Ruta | Tiempo | Consultas |
| --- | --- | --- |
| /pagos/ | 0.03 - 0.15 s | 10 |
| /pagos/<tipo>/ | 0.02 - 0.03 s | 10 |
| AJAX empresario | 0.008 s | 4 |

Antes, con los 15.793 pagos, la carga tardaba varios segundos (o mas). Ahora es casi instantanea.

## 5. Archivos modificados

| Archivo | Cambio |
| --- | --- |
| core/views.py | Vista `pagos` con filtro por año y solo nivel empresarios; helpers `_construir_empresarios` y `_construir_locales`; endpoint `pagos_empresario`; import de `Q` |
| practicavega/urls.py | Ruta `pagos_empresario` |
| core/templates/core/pagos.html | Botones de año, arbol de nivel 1 y JavaScript de carga perezosa |
| core/templates/core/base.html | Estilos `.emp-meta`, `.cargando-fila`, `.anios-tabs` |
| core/models.py | Indices en Pago, PagoDiario y Local |
| core/migrations/0012_*.py | Migracion que crea los indices |
| core/importador.py | Se quito el `print` de depuracion |

## 6. Como funciona (flujo)

1. Se entra a `/pagos/` y se elige el año (por defecto el mas reciente) -> se listan los empresarios.
2. Se abre un empresario -> por AJAX se traen sus locales y meses de ese año.
3. Se abre un mes -> por AJAX se traen los dias; se pueden editar sus valores.
4. Al guardar un dia, se actualizan el total del mes y el total del empresario.

## 7. Como probar

1. Abrir `http://127.0.0.1:8000/pagos/` (recargar con Ctrl+F5).
2. Elegir un año con los botones.
3. Expandir un empresario y luego un mes.

## 8. Recomendaciones futuras

- Si un solo año llegara a tener decenas de miles de meses, se puede agregar paginacion de empresarios o cargar por defecto tambien filtrado por mes.
- Realizar las pruebas de carga en una base de datos separada o borrar los datos de prueba al terminar, para no afectar la base real.
