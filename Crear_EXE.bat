@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "PY=python"
where py >NUL 2>NUL
if %errorlevel%==0 set "PY=py -3"
%PY% -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 (
  pause
  exit /b 1
)
%PY% -m PyInstaller --noconfirm --onefile --windowed --name NuzRandom --collect-all UnityPy --collect-all archspec --add-data "nuzrandom\data;nuzrandom\data" main.py
echo.
echo Ejecutable creado en dist\NuzRandom.exe
pause
