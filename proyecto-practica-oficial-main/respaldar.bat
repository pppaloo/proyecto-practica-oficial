@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p PASS=Password MySQL root: 
mysqldump --default-character-set=utf8mb4 -u root "-p%PASS%" centro_comercial > respaldo_centro_comercial.sql
if errorlevel 1 (echo Fallo al respaldar. & pause & exit /b 1)
echo Respaldo guardado en respaldo_centro_comercial.sql
pause