@echo off
setlocal EnableExtensions
title FrameTweak Uninstaller
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "FT_TARGET=%ROOT%\Launch-FrameTweak.bat"
set "FT_T2=%ROOT%\.venv\Scripts\pythonw.exe"
set "FT_T3=%ROOT%\dist\FrameTweak\FrameTweak.exe"
if not exist "%ROOT%\main.py" goto :e_root
echo This removes the FrameTweak desktop shortcut, and optionally its environment.
echo Tweaks you applied stay applied. Undo them inside FrameTweak first if you want them reverted.
choice /C YN /N /M "Continue? [Y/N] "
if errorlevel 2 goto :cancel
echo.
echo Removing desktop shortcut...
powershell -NoProfile -Command "$p=Join-Path ([Environment]::GetFolderPath('Desktop')) 'FrameTweak.lnk'; if (Test-Path -LiteralPath $p) { $s=(New-Object -ComObject WScript.Shell).CreateShortcut($p); if (@($env:FT_TARGET,$env:FT_T2,$env:FT_T3) -contains $s.TargetPath) { Remove-Item -LiteralPath $p -Force; 'Shortcut removed.' } else { 'Shortcut belongs to another location - left alone.' } } else { 'No shortcut found.' }"
echo.
echo Optional: remove the virtual environment (.venv) and build output (build, dist) inside this folder.
echo Your source files are NOT deleted.
choice /C YN /N /M "Remove environment and build output? [Y/N] "
if errorlevel 2 goto :keepenv
if exist "%ROOT%\.venv\Scripts\python.exe" rmdir /s /q "%ROOT%\.venv"
if exist "%ROOT%\build\FrameTweak" rmdir /s /q "%ROOT%\build"
if exist "%ROOT%\dist\FrameTweak" rmdir /s /q "%ROOT%\dist"
if exist "%ROOT%\.venv" echo WARNING: .venv could not be fully removed (is FrameTweak still running?).
:keepenv
echo.
echo Your settings, logs and backups in %%APPDATA%%\FrameTweak are KEPT by default.
echo They contain the backups needed to undo changes.
choice /C YN /N /M "Also permanently delete that user data folder? [Y/N] (default recommendation: N) "
if errorlevel 2 goto :done
if not defined APPDATA goto :done
if exist "%APPDATA%\FrameTweak\frametweak.log" rmdir /s /q "%APPDATA%\FrameTweak"
if exist "%APPDATA%\FrameTweak\backups.json" rmdir /s /q "%APPDATA%\FrameTweak"
:done
echo.
echo Done. You can delete this extracted folder manually if you no longer need it.
pause
exit /b 0
:cancel
echo Cancelled. Nothing was changed.
pause
exit /b 0
:e_root
echo ERROR: Run this file from the FrameTweak folder. Nothing was changed.
pause
exit /b 1
