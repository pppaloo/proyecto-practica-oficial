# -*- coding: utf-8 -*-
"""Instalador del sistema Vega Los Angeles en una PC nueva.

Crea la base de datos en MySQL, configura las credenciales en settings.py,
instala dependencias, ejecuta las migraciones y crea el usuario administrador.

Uso:
    python instalar.py
"""
import getpass
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SETTINGS = BASE / "practicavega" / "settings.py"


def ejecutar(args):
    print(">", " ".join(map(str, args)), flush=True)
    return subprocess.run(args).returncode


def escapar(password):
    return password.replace("\\", "\\\\").replace("'", "\\'")


def crear_base(root_pass):
    cmd = "CREATE DATABASE IF NOT EXISTS centro_comercial CHARACTER SET utf8mb4;"
    args = ["mysql", "-u", "root", "-e", cmd]
    if root_pass:
        args = ["mysql", "-u", "root", "-p%s" % root_pass, "-e", cmd]
    if subprocess.run(args).returncode != 0:
        print("No se pudo crear la base de datos. Revisa la password de MySQL.")
        sys.exit(1)


def main():
    print("=== Instalador Vega Los Angeles ===\n")

    if shutil.which("mysql") is None:
        print(
            "MySQL no esta en el PATH.\n"
            "Instala MySQL Server 8 y agrega su carpeta 'bin' al PATH,\n"
            "ejemplo: C:\\Program Files\\MySQL\\MySQL Server 8.0\\bin"
        )
        sys.exit(1)

    print("Paso 1/5 - Base de datos")
    root_pass = getpass.getpass("Password del usuario root de MySQL de este PC: ")
    crear_base(root_pass)

    texto = SETTINGS.read_text(encoding="utf-8")
    nuevo, n = re.subn(
        r"('PASSWORD':\s*)'[^']*'",
        lambda m: "%s'%s'" % (m.group(1), escapar(root_pass)),
        texto,
    )
    if n == 0:
        print("No se encontro 'PASSWORD' en settings.py")
        sys.exit(1)
    SETTINGS.write_text(nuevo, encoding="utf-8")
    print("settings.py actualizado con las credenciales de MySQL.\n")

    print("Paso 2/5 - Instalando dependencias")
    ejecutar([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    print("\nPaso 3/5 - Migraciones (estructura de la base de datos)")
    if ejecutar([sys.executable, "manage.py", "migrate"]) != 0:
        print("Las migraciones fallaron. Revisa los mensajes anteriores.")
        sys.exit(1)

    print("\nPaso 4/5 - Usuario administrador")
    usuario = input("Nombre de usuario del administrador [admin]: ").strip() or "admin"
    pass1 = getpass.getpass("Password del administrador (minimo 8 caracteres): ")
    while len(pass1) < 8:
        print("La password debe tener al menos 8 caracteres.")
        pass1 = getpass.getpass("Password del administrador (minimo 8 caracteres): ")
    env = dict(os.environ)
    env["DJANGO_SUPERUSER_USERNAME"] = usuario
    env["DJANGO_SUPERUSER_PASSWORD"] = pass1
    env["DJANGO_SUPERUSER_EMAIL"] = ""
    if subprocess.run(
        [sys.executable, "manage.py", "createsuperuser", "--noinput"], env=env
    ).returncode != 0:
        print("No se pudo crear el administrador (quizas ya existe). Puedes crearlo luego con:")
        print("    python manage.py createsuperuser")

    print("\nPaso 5/5 - LISTO!\n")
    print("Para iniciar:            iniciar.bat")
    print("Entrar desde este PC:    http://127.0.0.1:8000")
    print("Usuario administrador:   %s" % usuario)
    print("\nIMPORTANTE:")
    print("  - No subas 'practicavega/settings.py' a GitHub (contiene la password de MySQL).")
    print("  - Usuarios de caja/tesoreria se crean desde el menu 'Usuarios' en la web.")