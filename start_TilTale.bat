@echo off
rem start_TilTale for Windows: double-click to set up and start TilTale.
rem Makes sure Python exists, then hands over to scripts\start_tiltale.py (the visible to-do list).
setlocal
cd /d "%~dp0"

set PY=
where python >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py -3
if not defined PY (
    echo Python was not found. Installing it in the background with winget...
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    where python >nul 2>nul && set PY=python
)
if not defined PY (
    echo Python could not be installed automatically.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^),
    echo restart the PC, then double-click start_TilTale.bat again.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

if exist scripts\start_tiltale.py (
    %PY% scripts\start_tiltale.py
) else (
    rem Only this launcher is here yet: fetch the to-do app itself, which then downloads the rest.
    %PY% -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/tiltale/tiltale-refactor/main/scripts/start_tiltale.py', 'start_tiltale_tmp.py')"
    %PY% start_tiltale_tmp.py
    del start_tiltale_tmp.py
)
