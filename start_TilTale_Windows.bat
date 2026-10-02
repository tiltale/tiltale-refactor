@echo off
title Starting TilTale
rem start_TilTale for Windows: put this file in an empty folder and double-click it.
rem   [1/3] Python:  makes sure Python 3.12 or newer exists (installs it when missing).
rem   [2/3] TilTale: downloads TilTale from GitHub into this folder when it is not there yet.
rem   [3/3] Window:  opens scripts\start_tiltale.py (the visible to-do list: Git, updates, packages,
rem                  start), waits until its window is open, and then closes this black window.
setlocal
cd /d "%~dp0"

rem Colours for headings (Windows 10/11 understand these codes).
for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"
set "HEAD=%ESC%[1;36m"
set "GOOD=%ESC%[32m"
set "BAD=%ESC%[1;31m"
set "OFF=%ESC%[0m"

rem One log for the whole start, from the very first line: start_TilTale.log next to this file.
rem start_tiltale.py adds to it (TILTALE_LOG_STARTED tells newer versions not to empty it).
set "LOG=%~dp0start_TilTale.log"
set "TILTALE_LOG_STARTED=1"
>"%LOG%" echo %date% %time%  %~nx0 started
>>"%LOG%" echo Folder: "%~dp0"
>>"%LOG%" ver

rem ==================================================================== what is here already?
set "FIRST=1"
set "DAMAGED="
if exist "scripts\start_tiltale.py" set "FIRST="
if not defined FIRST goto :detect
rem First start: the folder must be empty apart from this file and its log, so TilTale never
rem gets unpacked into, say, the Downloads folder or the desktop.
if exist "_tiltale_download" rd /s /q "_tiltale_download"
if exist "tiltale.zip" del "tiltale.zip"
set "OTHER="
for /f "delims=" %%I in ('dir /b /a 2^>nul') do if /i not "%%I"=="%~nx0" if /i not "%%I"=="start_TilTale.log" if /i not "%%I"=="start_TilTale_Mac.command" if /i not "%%I"=="start_TilTale_Linux.sh" if /i not "%%I"=="desktop.ini" if /i not "%%I"=="Thumbs.db" set "OTHER=%%I"
if not defined OTHER goto :detect
rem Not empty: maybe a TilTale folder with files deleted (scripts\ among them). Then get only the
rem TilTale window back; that window shows what is missing and offers Repair. Only things a TilTale
rem folder has count, so a folder of unrelated files never gets TilTale files added.
set "TRACES="
for %%T in (studio frame-types components "runtime\tiltale.js" "branding\logo-tiltale.png" "project\project.sqlite3") do if exist "%%~T" set "TRACES=1"
for %%F in (".git\config" "README.md" "config\settings.py") do if exist "%%~F" findstr /i /m "tiltale" "%%~F" >nul 2>&1 && set "TRACES=1"
if not defined TRACES goto :not_empty
>>"%LOG%" echo Damaged TilTale folder: scripts\start_tiltale.py is missing.
set "FIRST="
set "DAMAGED=1"
echo %BAD%Some of TilTale's own files are missing in this folder.%OFF%
echo The TilTale window will open and offer to repair it. Your project is not touched.
echo.
goto :detect

:not_empty
>>"%LOG%" echo Folder is not empty, it contains for example: %OTHER%
echo %BAD%This folder already contains other files.%OFF%
echo Put %~nx0 in a new, empty folder and double-click it there.
set "RC=4"
goto :failed

:detect
rem Python: TilTale needs 3.12 or newer (Django 6). "where python" is not enough: every Windows
rem 10/11 PC has a fake python.exe (the Microsoft Store shortcut) that only prints a message.
set "PY="
set "PYVERSION="
set "OLDPY="
set "CHECK=import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
call :trypython python
if not defined PY call :trypython py -3
if not defined PY call :trypath
>>"%LOG%" echo Python: %PY% %PYVERSION% / older Python: %OLDPY%
set "HAVE_GIT="
git --version >>"%LOG%" 2>&1 && set "HAVE_GIT=1"
if not defined FIRST goto :python

rem ==================================================================== welcome
set /a "SPACE=150"
if not defined PY set /a "SPACE+=100"
if not defined HAVE_GIT set /a "SPACE+=350"
echo.
echo %HEAD%Welcome to TilTale!%OFF%
echo.
echo TilTale will be set up in this folder:
echo     "%~dp0"
echo.
echo What will happen:
if defined PY echo   1. Python   Python %PYVERSION% is already on this PC: nothing to install.
if not defined PY if not defined OLDPY echo   1. Python   Not on this PC yet: Python 3.12 will be installed, about 100 MB.
if not defined PY if defined OLDPY echo   1. Python   This PC has Python %OLDPY%, but TilTale needs 3.12 or newer.
if not defined PY if defined OLDPY echo               Python 3.12 is added next to it, about 100 MB. Python %OLDPY% stays
if not defined PY if defined OLDPY echo               installed and remains the default, so nothing that uses it changes.
echo   2. TilTale  Downloaded from GitHub into this folder.
if defined HAVE_GIT echo   3. Setup    A small window installs TilTale's packages, about 150 MB,
if not defined HAVE_GIT echo   3. Setup    A small window installs Git, about 350 MB, and TilTale's packages,
if not defined HAVE_GIT echo               about 150 MB.
echo               Then TilTale opens in your browser.
echo.
echo Disk space needed: about %SPACE% MB. The first start takes about 5 to 15 minutes.
echo.
choice /c yn /n /m "Continue? Type Y for yes or N for no: "
if not errorlevel 2 goto :yes
>>"%LOG%" echo User chose not to continue.
echo.
echo Nothing was changed. You can close this window.
pause
exit /b 0
:yes
>>"%LOG%" echo User chose to continue.

rem ==================================================================== [1/3] Python
:python
if defined FIRST call :step 1 "Python"
if not defined PY goto :python_install
if defined FIRST call :say "Python %PYVERSION% is already on this PC."
goto :python_done

:python_install
if not defined FIRST call :say "TilTale needs Python 3.12 or newer. Installing it now..."
set "PYVER=3.12.10"
set "PYFILE=python-%PYVER%-amd64.exe"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PYFILE=python-%PYVER%-arm64.exe"
set "PYSETUP=%TEMP%\%PYFILE%"
rem With an older Python on the PC, the new one is not put on PATH, so the old one stays the default.
set "PYPATH=PrependPath=1"
if defined OLDPY set "PYPATH=PrependPath=0"
set "PYOPTIONS=/passive InstallAllUsers=0 InstallLauncherAllUsers=0 Include_launcher=1 Include_test=0 %PYPATH%"
call :say "Downloading Python %PYVER%, about 27 MB..."
>>"%LOG%" echo --- download https://www.python.org/ftp/python/%PYVER%/%PYFILE%
curl.exe -fL -# -o "%PYSETUP%" "https://www.python.org/ftp/python/%PYVER%/%PYFILE%"
if errorlevel 1 goto :python_winget
call :say "Installing Python. A Python window shows the progress and closes by itself."
>>"%LOG%" echo --- "%PYSETUP%" %PYOPTIONS%
start "" /wait "%PYSETUP%" %PYOPTIONS%
>>"%LOG%" echo --- Python installer finished with code %errorlevel%
del "%PYSETUP%" >nul 2>&1
goto :python_find

:python_winget
rem No curl.exe or no connection to python.org: the Windows package manager is the fallback.
del "%PYSETUP%" >nul 2>&1
>>"%LOG%" echo --- download failed, trying winget
call :say "Trying the Windows package manager instead..."
winget install -e --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements --override "%PYOPTIONS%"
>>"%LOG%" echo --- winget finished with code %errorlevel%

:python_find
rem This window does not see the new PATH yet, so also look where the installer puts Python.
call :trypython py -3
if not defined PY call :trypath
if defined PY goto :python_done
echo.
echo %BAD%Python could not be installed automatically.%OFF%
echo Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"),
echo restart the PC, then double-click %~nx0 again.
start "" https://www.python.org/downloads/
set "RC=1"
goto :failed

:python_done
>>"%LOG%" echo Using Python: %PY%
%PY% --version >>"%LOG%" 2>&1
if defined DAMAGED goto :download
if not defined FIRST goto :window
call :done

rem ==================================================================== [2/3] TilTale
rem GitHub's ZIP of the repository: no Git needed yet (the TilTale window installs Git afterwards
rem and connects this folder to GitHub). curl.exe is built into Windows 10/11; Python is the fallback.
call :step 2 "TilTale"
:download
set "ZIP=tiltale.zip"
set "URL=https://github.com/tiltale/tiltale-refactor/archive/refs/heads/main.zip"
call :say "Downloading TilTale from GitHub..."
>>"%LOG%" echo --- download %URL%
curl.exe -fL -# -o "%ZIP%" "%URL%" || del "%ZIP%" >nul 2>&1
if not exist "%ZIP%" %PY% -c "import urllib.request; urllib.request.urlretrieve('%URL%', '%ZIP%')" >>"%LOG%" 2>&1
if exist "%ZIP%" goto :unpack
echo %BAD%TilTale could not be downloaded. Check the internet connection and try again.%OFF%
set "RC=3"
goto :failed

:unpack
call :say "Unpacking TilTale..."
>>"%LOG%" echo --- unpack %ZIP%
%PY% -m zipfile -e "%ZIP%" "_tiltale_download" >>"%LOG%" 2>&1
if defined DAMAGED goto :restore_window
rem The ZIP holds one folder (tiltale-refactor-main): move its contents here, next to this file.
rem Nothing that already exists is replaced: above all not this .bat, which Windows is still reading.
for /d %%D in ("_tiltale_download\*") do for /f "delims=" %%I in ('dir /b /a "%%D"') do if not exist "%%I" move "%%D\%%I" . >>"%LOG%" 2>&1
rd /s /q "_tiltale_download" >nul 2>&1
del "%ZIP%" >nul 2>&1
if exist "scripts\start_tiltale.py" goto :unpacked
echo %BAD%TilTale was downloaded but could not be unpacked.%OFF%
set "RC=5"
goto :failed
:unpacked
call :done
goto :window

:restore_window
rem Damaged folder: put back only the TilTale window (and its pictures when missing). Nothing else is
rem changed here; the window's Repair button puts back the rest, after asking.
if not exist "scripts" mkdir "scripts"
if not exist "branding" mkdir "branding"
for /d %%D in ("_tiltale_download\*") do copy /y "%%D\scripts\start_tiltale.py" "scripts\" >>"%LOG%" 2>&1
for /d %%D in ("_tiltale_download\*") do for %%B in (launcher-logo.png launcher-logo@2x.png favicon.ico) do if not exist "branding\%%B" copy "%%D\branding\%%B" "branding\" >>"%LOG%" 2>&1
rd /s /q "_tiltale_download" >nul 2>&1
del "%ZIP%" >nul 2>&1
if exist "scripts\start_tiltale.py" goto :window
echo %BAD%The TilTale window could not be put back.%OFF%
set "RC=5"
goto :failed

rem ==================================================================== [3/3] the TilTale window
:window
if defined FIRST call :step 3 "TilTale window"
if not defined FIRST echo %HEAD%Starting TilTale...%OFF%
rem pythonw.exe: the same Python, but without a black window of its own. Started with "start",
rem so this window can close while the TilTale window keeps running.
set "PYW="
%PY% -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))" >"%TEMP%\tiltale_pythonw.txt" 2>nul
set /p PYW=<"%TEMP%\tiltale_pythonw.txt"
del "%TEMP%\tiltale_pythonw.txt" >nul 2>&1
>>"%LOG%" echo --- start "%PYW%" scripts\start_tiltale.py
if defined PYW if exist "%PYW%" start "" "%PYW%" scripts\start_tiltale.py
if not defined PYW start "" %PY% scripts\start_tiltale.py
if defined PYW if not exist "%PYW%" start "" %PY% scripts\start_tiltale.py
call :say "Opening the TilTale window..."

rem Wait until the window is really open: start_tiltale.py writes its first log line once its
rem window exists ("start_TilTale on" in older versions, "Window open" in newer ones).
set /a "WAITED=0"
:wait_window
findstr /c:"start_TilTale on" /c:"Window open" "%LOG%" >nul 2>&1 && goto :window_open
findstr /c:"Crashed:" "%LOG%" >nul 2>&1 && goto :window_failed
if %WAITED% geq 30 goto :window_failed
timeout /t 1 /nobreak >nul
set /a "WAITED+=1"
goto :wait_window

:window_open
if defined FIRST call :done
echo.
echo %GOOD%All set: the "Start TilTale" window is open.%OFF%
if defined FIRST echo Click Start in that window. It installs what TilTale still needs, and then you
if defined FIRST echo can open TilTale in your browser. Next time, just double-click %~nx0 again.
if defined DAMAGED echo Click Start in that window: it shows what is missing and offers Repair.
if not defined FIRST if not defined DAMAGED echo Click Start in that window to open TilTale in your browser.
echo.
echo This black window closes in 10 seconds.
timeout /t 10 >nul
exit /b 0

:window_failed
echo %BAD%The TilTale window did not open.%OFF%
set "RC=6"
goto :failed

rem ==================================================================== helpers
:failed
rem Keep this window open and show the log, so the problem can be read (and sent to someone).
>>"%LOG%" echo %date% %time%  stopped with code %RC%
echo.
echo %BAD%Starting TilTale did not work (code %RC%).%OFF%
echo The log opens now: "%LOG%"
start "" notepad "%LOG%"
pause
exit /b %RC%

rem Try one way to run Python (the command is everything after the label): if it is 3.12 or newer,
rem use it (PY); if it is older, remember its version (OLDPY) for the welcome text.
:trypython
%* -c "import sys" >nul 2>&1 || exit /b 0
%* -c "import platform; print(platform.python_version())" >"%TEMP%\tiltale_python_version.txt" 2>nul
set "FOUNDVER="
set /p FOUNDVER=<"%TEMP%\tiltale_python_version.txt"
del "%TEMP%\tiltale_python_version.txt" >nul 2>&1
%* -c "%CHECK%" >nul 2>&1 || goto :trypython_old
set "PY=%*"
set "PYVERSION=%FOUNDVER%"
exit /b 0
:trypython_old
if not defined OLDPY set "OLDPY=%FOUNDVER%"
exit /b 0

rem Where the Python installer puts a per-user Python 3.12 (not on PATH in this window yet).
:trypath
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" call :trypython "%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PY exit /b 0
if exist "%LocalAppData%\Programs\Python\Python312-arm64\python.exe" call :trypython "%LocalAppData%\Programs\Python\Python312-arm64\python.exe"
exit /b 0

rem A numbered step heading.
:step
echo.
echo %HEAD%[%~1/3] %~2%OFF%
>>"%LOG%" echo === [%~1/3] %~2
exit /b 0

rem A line under the current step, in this window and in the log.
:say
echo(    %~1
>>"%LOG%" echo(%time:~0,8%  %~1
exit /b 0

:done
echo     %GOOD%Done.%OFF%
exit /b 0
