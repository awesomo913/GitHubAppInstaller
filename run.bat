@echo off
cd /d "%~dp0"

where python >nul 2>&1 || (
    echo Python not found. Install from https://python.org
    pause & exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

python -m pip install -r requirements.txt -q 2>nul

pythonw github_app_manager.py
