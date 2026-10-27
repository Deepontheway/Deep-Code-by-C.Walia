@echo off
setlocal
title Deep Code by C.Walia - Install From GitHub
echo ====================================================
echo    DEEP CODE BY C.WALIA - INSTALL FROM GITHUB
echo ====================================================
echo.
echo This downloads the latest source from GitHub and installs
echo everything (dependencies, AI models, shortcuts, uninstaller).
echo.
powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://raw.githubusercontent.com/Deepontheway/Deep-Code-by-C.Walia/main/Install-FromGitHub.ps1 | iex"
echo.
pause
