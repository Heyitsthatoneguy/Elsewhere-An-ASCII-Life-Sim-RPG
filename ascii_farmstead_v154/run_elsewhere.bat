@echo off
title Elsewhere - an ASCII Life-Sim RPG
cd /d "%~dp0"

echo Starting Elsewhere...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 elsewhere.py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python elsewhere.py
    ) else (
        echo Python 3.11 or later was not found.
        echo Install Python, or add it to PATH.
        echo.
    )
)

echo.
echo Elsewhere closed.
echo.
pause
