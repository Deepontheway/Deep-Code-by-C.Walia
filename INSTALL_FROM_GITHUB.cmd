@echo off
setlocal
title Deep Code by C.Walia - Install From GitHub
echo ====================================================
echo    DEEP CODE BY C.WALIA - INSTALL FROM GITHUB
echo ====================================================
echo.
echo This downloads the latest source from GitHub and installs
echo dependencies, an online AI model, shortcuts and the uninstaller.
echo No local model files are downloaded.
echo.
powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://raw.githubusercontent.com/Deepontheway/Deep-Code-by-C.Walia/main/Install-FromGitHub.ps1 | iex"
echo.
pause
