@echo off
title Deep Code by C.Walia - Terminal
cd /d "%~dp0"

set "HOME_FILE=%~dp0walia-home.txt"
if exist "%HOME_FILE%" set /p WALIACODE_HOME=<"%HOME_FILE%"
if not defined WALIACODE_HOME set "WALIACODE_HOME=%LOCALAPPDATA%\Deep Code by C.Walia"
if not exist "%WALIACODE_HOME%" mkdir "%WALIACODE_HOME%" >nul 2>&1

set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" if exist "%~dp0app\venv\Scripts\python.exe" set "PY=%~dp0app\venv\Scripts\python.exe"

if not exist "%~dp0app\walia\main.py" (
  echo App files not found in %~dp0app. Reinstall Deep Code by C.Walia.
  pause
  exit /b 1
)

if exist "%~dp0node_modules\.bin\tsx.cmd" (
  call "%~dp0node_modules\.bin\tsx.cmd" "%~dp0bin\run.ts"
  exit /b %ERRORLEVEL%
)

if exist "%~dp0dist\bin\run.js" (
  node "%~dp0dist\bin\run.js"
  exit /b %ERRORLEVEL%
)

echo Terminal UI dependencies are missing. Run setup again or run: npm install
pause
exit /b 1
