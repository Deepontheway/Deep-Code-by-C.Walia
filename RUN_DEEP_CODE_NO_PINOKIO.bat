@echo off
title Deep Code by C.Walia - Run (No Pinokio)
cd /d "%~dp0"

if not exist node_modules (
  echo node_modules not found. Running setup first...
  call "%~dp0FULL_SETUP_NO_PINOKIO.bat"
  exit /b
)

call npm.cmd run dev
pause
