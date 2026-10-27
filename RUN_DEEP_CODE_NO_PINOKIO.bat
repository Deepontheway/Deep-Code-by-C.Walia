@echo off
title Deep Code by C.Walia - Run (No Pinokio)
cd /d "%~dp0"

set "HOME_FILE=%~dp0walia-home.txt"
if exist "%HOME_FILE%" set /p WALIACODE_HOME=<"%HOME_FILE%"
if not defined WALIACODE_HOME set "WALIACODE_HOME=%LOCALAPPDATA%\Deep Code by C.Walia"
if not exist "%WALIACODE_HOME%" mkdir "%WALIACODE_HOME%" >nul 2>&1

set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" if exist "%~dp0app\venv\Scripts\python.exe" set "PY=%~dp0app\venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Python environment not found. Running setup first...
  call "%~dp0FULL_SETUP_NO_PINOKIO.bat"
  exit /b
)

if not exist "%~dp0app\walia\main.py" (
  echo App files not found in %~dp0app. Reinstall Deep Code by C.Walia.
  pause
  exit /b 1
)

echo Starting Deep Code by C.Walia at http://127.0.0.1:8765
echo Model calls run online through your configured provider.
echo Close this window to stop the app.
echo.

pushd "%~dp0app"
"%PY%" -m walia.run
set "RC=%ERRORLEVEL%"
popd

if not "%RC%"=="0" (
  echo.
  echo The app stopped with error code %RC%.
  pause
)
