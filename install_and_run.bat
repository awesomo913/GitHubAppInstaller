@echo off
title GitHub App Manager - Setup
color 0B
echo.
echo  ===================================================
echo    GitHub App Manager - First-Time Setup
echo  ===================================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not on PATH.
    echo  Please install Python from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo  Python found. Installing dependencies...
echo.
pip install requests pywin32 --quiet --upgrade

if errorlevel 1 (
    echo.
    echo  WARNING: Some packages may not have installed correctly.
    echo  The app will still run but shortcut creation may use a fallback method.
    echo.
)

echo.
echo  Starting GitHub App Manager...
echo.
python "%~dp0github_app_manager.py"

if errorlevel 1 (
    echo.
    echo  The app exited with an error. See the message above.
    pause
)
