@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VPY=%ROOT%\.venv\Scripts\python.exe"
cd /d "%ROOT%"
echo [1/5] Looking for Python 3.10+ (64-bit)...
set "PYCMD="
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) and sys.maxsize>2**32 else 1)" >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD python -c "import sys;sys.exit(0 if sys.version_info>=(3,10) and sys.maxsize>2**32 else 1)" >nul 2>&1 && set "PYCMD=python"
if not defined PYCMD goto :e_python
"%VPY%" -c "import sys" >nul 2>&1
if not errorlevel 1 goto :venv_ok
%PYCMD% -m venv --clear "%ROOT%\.venv"
if errorlevel 1 goto :e_venv
:venv_ok
echo [2/5] Installing build dependencies into .venv...
"%VPY%" -m pip install --disable-pip-version-check -r "%ROOT%\requirements-dev.txt"
if errorlevel 1 goto :e_pip
echo [3/5] Running tests...
"%VPY%" -m pytest -q
if errorlevel 1 goto :e_tests
echo [4/5] Building with PyInstaller...
"%VPY%" -m PyInstaller --noconfirm --clean "%ROOT%\FrameTweak.spec"
if errorlevel 1 goto :e_build
if not exist "%ROOT%\dist\FrameTweak\FrameTweak.exe" goto :e_build
echo       Built: %ROOT%\dist\FrameTweak\FrameTweak.exe
echo [5/5] Optional installer (Inno Setup 6)...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if not defined ISCC echo       Inno Setup 6 not found - skipped (optional).
if not defined ISCC goto :ok
"%ISCC%" "%ROOT%\installer\FrameTweak.iss"
if errorlevel 1 goto :e_build
if not exist "%ROOT%\dist-installer\FrameTweak-Setup.exe" goto :e_build
echo       Built: %ROOT%\dist-installer\FrameTweak-Setup.exe
:ok
echo.
echo BUILD SUCCEEDED. Run Install-FrameTweak.bat to create a shortcut to the packaged app.
goto :end
:e_python
set "MSG=Python 3.10+ (64-bit) not found. Install it from python.org first."
goto :fail
:e_venv
set "MSG=Could not create the virtual environment."
goto :fail
:e_pip
set "MSG=Installing build dependencies failed (internet needed)."
goto :fail
:e_tests
set "MSG=Tests failed, so nothing was built."
goto :fail
:e_build
set "MSG=Build failed or the expected output file is missing."
:fail
echo.
echo BUILD FAILED: %MSG%
if /I not "%~1"=="/nopause" pause
exit /b 1
:end
if /I not "%~1"=="/nopause" pause
exit /b 0
