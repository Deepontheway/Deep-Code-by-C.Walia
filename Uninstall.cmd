@echo off
setlocal
title Uninstall Deep Code by C.Walia
cd /d "%~dp0"

set "HERE=%~dp0"
set "MANIFEST=%HERE%install-manifest.json"
set "TMPSCRIPT=%TEMP%\walia-uninstall-%RANDOM%%RANDOM%.ps1"

if not exist "%HERE%uninstall.ps1" (
  echo [ERROR] uninstall.ps1 not found next to this file.
  pause
  exit /b 1
)

copy /y "%HERE%uninstall.ps1" "%TMPSCRIPT%" >nul

cd /d "%TEMP%"

powershell -ExecutionPolicy Bypass -NoProfile -File "%TMPSCRIPT%" -Full -InstallDir "%HERE%" -ManifestPath "%MANIFEST%"

del "%TMPSCRIPT%" >nul 2>&1

echo.
echo Uninstall finished.
pause
