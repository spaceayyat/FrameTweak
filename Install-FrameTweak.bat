@echo off
setlocal EnableExtensions
title FrameTweak Installer
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV=%ROOT%\.venv"
set "VPY=%VENV%\Scripts\python.exe"
set "FT_ROOT=%ROOT%"
set "FT_TARGET=%VENV%\Scripts\pythonw.exe"
set FT_ARGS="%ROOT%\main.py"
echo ==================================================
echo  FrameTweak setup  (current user, no admin needed)
echo ==================================================
echo.
echo [1/6] Checking Windows version...
ver | findstr /R /C:"Version 10\.0\." >nul
if errorlevel 1 goto :e_win
echo       OK.
set "PACKAGED="
if exist "%ROOT%\dist\FrameTweak\FrameTweak.exe" set "PACKAGED=1"
if defined PACKAGED echo [2/6] Packaged FrameTweak.exe found - Python is not needed.
if defined PACKAGED goto :prepare
if not exist "%ROOT%\main.py" goto :e_files
if not exist "%ROOT%\requirements.txt" goto :e_files
echo [2/6] Looking for Python 3.10 or newer, 64-bit...
set "PYCMD="
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) and sys.maxsize>2**32 else 1)" >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD python -c "import sys;sys.exit(0 if sys.version_info>=(3,10) and sys.maxsize>2**32 else 1)" >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD goto :e_python
echo       Found: %PYCMD%
echo [3/6] Preparing virtual environment in "%VENV%"...
"%VPY%" -c "import sys" >nul 2>&1
if not errorlevel 1 goto :venv_ok
%PYCMD% -m venv --clear "%VENV%"
if errorlevel 1 goto :e_venv
:venv_ok
echo       OK.
echo [4/6] Installing dependencies into the environment (needs internet)...
"%VPY%" -m pip install --disable-pip-version-check -r "%ROOT%\requirements.txt"
if errorlevel 1 goto :e_pip
"%VPY%" -c "import PySide6.QtWidgets, psutil" >nul 2>&1
if errorlevel 1 goto :e_pip
echo       Dependencies verified.
:prepare
echo [5/6] Preparing application folders...
if not defined APPDATA goto :e_appdata
if not exist "%APPDATA%\FrameTweak" mkdir "%APPDATA%\FrameTweak"
if not exist "%APPDATA%\FrameTweak" goto :e_appdata
echo       OK.
echo [6/6] Creating desktop shortcut...
set "FT_ICON=%ROOT%\assets\frametweak.ico"
if defined PACKAGED set "FT_TARGET=%ROOT%\dist\FrameTweak\FrameTweak.exe"
if defined PACKAGED set "FT_ARGS="
if not exist "%FT_TARGET%" goto :e_files
if not exist "%FT_ICON%" set "FT_ICON=%FT_TARGET%,0"
powershell -NoProfile -Command "$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'FrameTweak.lnk'; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); $s.TargetPath=$env:FT_TARGET; $s.Arguments=$env:FT_ARGS; $s.WorkingDirectory=$env:FT_ROOT; $s.WindowStyle=7; $s.IconLocation=$env:FT_ICON; $s.Description='FrameTweak'; $s.Save()"
if errorlevel 1 goto :e_lnk
powershell -NoProfile -Command "$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'FrameTweak.lnk'; if (-not (Test-Path -LiteralPath $p)) { exit 1 }; $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); if ($s.TargetPath -eq $env:FT_TARGET -and (Test-Path -LiteralPath $s.TargetPath)) { exit 0 } else { exit 1 }"
if errorlevel 1 goto :e_lnk
echo.
echo SUCCESS: FrameTweak is set up and the desktop shortcut was verified.
echo Launch it with the "FrameTweak" shortcut on your desktop.
echo Safe to re-run this installer at any time.
echo.
pause
exit /b 0

:e_win
set "MSG=FrameTweak supports Windows 10 and Windows 11 only."
goto :fail
:e_files
set "MSG=Required FrameTweak files are missing. Re-extract the whole ZIP and run this file from the extracted folder."
goto :fail
:e_python
echo Python 3.10+ (64-bit) was not found. Python 3.12 is recommended.
echo When installing, tick "Add python.exe to PATH".
choice /C YN /N /M "Open the official Python download page (python.org) in your browser? [Y/N] "
if not errorlevel 2 start "" "https://www.python.org/downloads/windows/"
set "MSG=Install Python, then run Install-FrameTweak.bat again. Nothing was installed."
goto :fail
:e_venv
set "MSG=Could not create the virtual environment."
goto :fail
:e_pip
set "MSG=Dependency installation failed. Check your internet connection and the messages above, then run this file again."
goto :fail
:e_appdata
set "MSG=Could not create the settings folder in %%APPDATA%%."
goto :fail
:e_lnk
set "MSG=The desktop shortcut could not be created or verified."
goto :fail
:fail
echo.
echo ERROR: %MSG%
echo.
pause
exit /b 1
