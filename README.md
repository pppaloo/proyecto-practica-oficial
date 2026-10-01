# Vega Los Ángeles - Sistema de Pagos Web

Sistema web para el registro de pagos de los locales del Centro Comercial Vega de Los Ángeles (Chile). Reemplaza la versión de escritorio (Tkinter) por una aplicación web.

## Requisitos

- Python 3.10+
- MySQL (base de datos `centro_comercial`)

## Instalación

1. Crear la base de datos en MySQL:

```sql
CREATE DATABASE centro_comercial CHARACTER SET utf8mb4;
```

2. Instalar dependencias:

```
pip install -r requirements.txt
```

3. Ajustar la conexión a MySQL en `practicavega/settings.py` (DATABASES).

4. Aplicar migraciones y crear el primer usuario administrador:

```
python manage.py migrate
python manage.py createsuperuser
```

> El usuario creado con `createsuperuser` tendrá rol `administrador` por defecto (el perfil se crea automáticamente).

5. Crear usuarios de caja/tesorería desde el panel **Usuarios** (menú superior).

## Ejecutar

```
python manage.py runserver
```

Abrir http://127.0.0.1:8000

## Instalar en otra PC (la PC donde quedará el sistema)

1. Instalar **Python 3.10–3.13** marcando "Add python.exe to PATH".
2. Instalar **MySQL Server 8** (recordar la password de `root`).
3. Clonar el repo y entrar en la carpeta:

```
git clone https://github.com/pppaloo/proyecto-practica-oficial.git
cd proyecto-practica-oficial
```

4. Ejecutar el instalador (crea la BD, configura `settings.py`, instala dependencias, migra y crea el admin):

```
python instalar.py
```

5. Iniciar el sistema:

```
iniciar.bat
```

Abrir http://127.0.0.1:8000 (en la misma PC). Desde **otra PC de la red**: `http://IP_DE_ESTA_PC:8000` (permitir el puerto 8000 en el Firewall de Windows).

- **Respaldar datos:** `respaldar.bat` crea `respaldo_centro_comercial.sql`.
- **Restaurar datos:** `restaurar.bat` carga ese respaldo en otra PC.
- No subir `practicavega/settings.py` modificado a GitHub (contiene la password de MySQL).

## Funcionalidades

- Registro de pagos por tipo de local (el mes se autocompleta desde la fecha elegida).
- El calendario bloquea domingos y feriados para Lote 6 y Kiosco.
- Generación automática de la deuda del mes: disponible solo los primeros 5 días de cada mes; crea un registro por local ocupado hasta el fin de mes (folio `GEN-AAAAMM-N°`, monto precargado con el mayor registro anterior y editable antes de confirmar).
- Selección múltiple de registros de una misma persona con suma total al instante.
- Abonos parciales (al saldar se marca la fecha de pago).
- Búsqueda por N° de local.
- Locales desocupados.
- Historial de operaciones (quién creó/abonó, cuándo y por cuánto).
- Roles con permisos.

## Roles

| Rol | Permisos |
|---|---|
| Administrador | Gestionar usuarios y consultar todo |
| Caja | Registrar y abonar pagos, consultar |
| Tesorería | Solo consultar |

## Tipos de local

- Local
- Boletería
- Pescadería
- Lote 6 (no paga domingos ni feriados)
- Kiosco (no paga domingos ni feriados)
- Centro Comercial

Los feriados se definen en `core/feriados.py`.
