@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "FT_PY=%ROOT%\.venv\Scripts\pythonw.exe"
cd /d "%ROOT%"
if exist "%ROOT%\dist\FrameTweak\FrameTweak.exe" goto :packaged
if not exist "%ROOT%\main.py" goto :e_main
if not exist "%FT_PY%" goto :e_env
"%ROOT%\.venv\Scripts\python.exe" -c "import PySide6.QtWidgets, psutil" >nul 2>&1
if errorlevel 1 goto :e_env
powershell -NoProfile -Command "if (Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $env:FT_PY }) { exit 0 } else { exit 1 }"
if not errorlevel 1 exit /b 0
start "" "%FT_PY%" "%ROOT%\main.py"
exit /b 0
:packaged
tasklist /FI "IMAGENAME eq FrameTweak.exe" 2>nul | find /I "FrameTweak.exe" >nul
if not errorlevel 1 exit /b 0
start "" "%ROOT%\dist\FrameTweak\FrameTweak.exe"
exit /b 0
:e_main
set "MSG=FrameTweak application files are missing (main.py). Re-extract the ZIP."
goto :fail
:e_env
set "MSG=FrameTweak is not installed or its environment is broken. Run Install-FrameTweak.bat."
goto :fail
:fail
set "FT_MSG=%MSG%"
echo ERROR: %MSG%
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show($env:FT_MSG,'FrameTweak')"
pause
exit /b 1
