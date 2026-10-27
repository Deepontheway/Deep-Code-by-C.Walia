@echo off
title Deep Code by C.Walia - Full Setup (No Pinokio)
cd /d "%~dp0"

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0FULL_SETUP_NO_PINOKIO.ps1"

if errorlevel 1 pause
