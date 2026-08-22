@echo off
title Launch Elsewhere in Windows Terminal
set "GAME_DIR=%~dp0"
if "%GAME_DIR:~-1%"=="\" set "GAME_DIR=%GAME_DIR:~0,-1%"
cd /d "%GAME_DIR%"

where wt >nul 2>nul
if %errorlevel%==0 (
    wt -d "%GAME_DIR%" cmd /k run_elsewhere.bat
) else (
    echo Windows Terminal ^(wt.exe^) was not found on PATH.
    echo Install it from the Microsoft Store, then run this again.
    echo.
    pause
)
