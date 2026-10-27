@echo off
title Deep Code by C.Walia - Run (No Pinokio)
cd /d "%~dp0"

if not exist node_modules (
  echo node_modules not found. Running setup first...
  call "%~dp0FULL_SETUP_NO_PINOKIO.bat"
  exit /b
)

set "NPM=npm.cmd"
where %NPM% >nul 2>&1
if errorlevel 1 (
  if exist "C:\Program Files\nodejs\npm.cmd" (
    set "NPM=C:\Program Files\nodejs\npm.cmd"
  ) else (
    echo Node.js/npm not found. Run the setup first.
    pause
    exit /b 1
  )
)

call "%NPM%" run dev
pause
