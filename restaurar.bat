@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist respaldo_centro_comercial.sql (echo No hay archivo respaldo_centro_comercial.sql. & pause & exit /b 1)
set /p PASS=Password MySQL root: 
mysql -u root "-p%PASS%" -e "CREATE DATABASE IF NOT EXISTS centro_comercial CHARACTER SET utf8mb4;"
mysql --default-character-set=utf8mb4 -u root "-p%PASS%" centro_comercial < respaldo_centro_comercial.sql
if errorlevel 1 (echo Fallo al restaurar. & pause & exit /b 1)
echo Respaldo restaurado.
pause