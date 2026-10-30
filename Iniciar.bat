@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "PY=python"
set "PYW=pythonw"
where py >NUL 2>NUL
if %errorlevel%==0 (
  set "PY=py -3"
  set "PYW=pyw -3"
)
%PY% --version >NUL 2>NUL
if errorlevel 1 (
  echo No se encuentra Python. Instala Python 3.10 o superior desde python.org
  echo marcando la casilla "Add python.exe to PATH" y vuelve a abrir este archivo.
  pause
  exit /b 1
)
if not exist ".deps_ok" (
  echo Instalando dependencias por primera vez...
  %PY% -m pip install --upgrade -r requirements.txt
  if errorlevel 1 (
    pause
    exit /b 1
  )
  echo ok> .deps_ok
)
start "" %PYW% main.py
