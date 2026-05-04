@echo off
title GitHub App Manager - Build .exe
color 0B
echo.
echo  ============================================================
echo    GitHub App Manager - Build Standalone .exe
echo  ============================================================
echo.
echo  Output goes to AppData (one exe). Desktop gets ONE shortcut only.
echo  You can delete old folders like Desktop\GitHubAppManager_EXE if present.
echo.

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found on PATH.
    echo  Install from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause & exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo  Found: %%i

REM --- Install / upgrade dependencies ---
echo.
echo  [1/3] Installing dependencies...
pip install pyinstaller requests pywin32 keyring --quiet --upgrade
if errorlevel 1 (
    echo  WARNING: Some packages may have failed. Continuing anyway...
)
echo  Done.

REM --- Paths ---
set SCRIPT=%~dp0github_app_manager.py
set OUTDIR=%LOCALAPPDATA%\GitHubAppManager
set ICON=%~dp0icons\github_app_manager.ico
set WORKDIR=%TEMP%\ghappmanager_build

set PYI_EXTRA=
if exist "%ICON%" set PYI_EXTRA=--icon "%ICON%" --add-data "%ICON%;icons"

echo.
echo  [2/3] Running PyInstaller...
echo  Script : %SCRIPT%
echo  Output : %OUTDIR%\GitHubAppManager.exe
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --clean ^
    --name "GitHubAppManager" ^
    --distpath "%OUTDIR%" ^
    --workpath "%WORKDIR%" ^
    --specpath "%TEMP%" ^
    --collect-submodules keyring ^
    --hidden-import gab ^
    --hidden-import gab.credentials ^
    --hidden-import gab.git_clone ^
    --hidden-import gab.zip_safe ^
    %PYI_EXTRA% ^
    "%SCRIPT%"

if errorlevel 1 (
    echo.
    echo  ============================================================
    echo  ERROR: PyInstaller failed. See messages above.
    echo  ============================================================
    pause & exit /b 1
)

REM --- Cleanup build temp ---
rmdir /s /q "%WORKDIR%" 2>nul
del "%TEMP%\GitHubAppManager.spec" 2>nul

REM --- One Desktop shortcut (must be ONE line: batch "^" breaks powershell -Command) ---
echo.
echo  [3/3] Desktop shortcut GitHubAppManager.lnk ...
set EXEPATH=%OUTDIR%\GitHubAppManager.exe
set LNKPATH=%USERPROFILE%\Desktop\GitHubAppManager.lnk

if exist "%ICON%" (
    set ICONLOC=%ICON%
) else (
    set ICONLOC=%EXEPATH%,0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNKPATH%'); $s.TargetPath='%EXEPATH%'; $s.WorkingDirectory='%OUTDIR%'; $s.IconLocation='%ICONLOC%'; $s.Description='GitHub App Manager'; $s.Save()"

echo.
echo  ============================================================
echo   SUCCESS
echo.
echo   Installed exe (keep this copy):
echo   %EXEPATH%
echo.
echo   Desktop: GitHubAppManager.lnk - you may delete OTHER exe copies
echo   or old Desktop\GitHubAppManager_EXE folders.
echo  ============================================================
echo.
pause
