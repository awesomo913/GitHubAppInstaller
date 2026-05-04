@echo off
title GitHub App Manager — Push to GitHub
color 0B
echo.
echo  ============================================================
echo    GitHub App Manager — Push to GitHub
echo  ============================================================
echo.

REM ── Check git ─────────────────────────────────────────────────
git --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: git is not installed or not on PATH.
    echo  Download from https://git-scm.com/download/win
    echo.
    pause & exit /b 1
)

REM ── Get repo URL from user ─────────────────────────────────────
echo  Enter your GitHub repository URL.
echo  Example: https://github.com/awesomo913/GitHubAppInstaller
echo  (Create the repo on GitHub first — keep it empty, no README)
echo.
set /p REMOTE_URL=  Repo URL: 

if "%REMOTE_URL%"=="" (
    echo  No URL entered. Exiting.
    pause & exit /b 1
)

REM ── Move into the project folder ──────────────────────────────
cd /d "%~dp0"

REM ── Init git if needed ────────────────────────────────────────
if not exist ".git" (
    echo.
    echo  Initializing git repository...
    git init -b main
    if errorlevel 1 git init && git checkout -b main
)

REM ── Stage all files ───────────────────────────────────────────
echo.
echo  Staging files...
git add .
git status --short

REM ── Commit ────────────────────────────────────────────────────
echo.
echo  Committing...
git commit -m "Initial commit — GitHub App Manager v3.1"

REM ── Set remote ────────────────────────────────────────────────
echo.
echo  Setting remote origin to: %REMOTE_URL%
git remote remove origin 2>nul
git remote add origin "%REMOTE_URL%"

REM ── Push ──────────────────────────────────────────────────────
echo.
echo  Pushing to GitHub...
echo  (A login window may appear — use your GitHub username)
echo  (For password, use a Personal Access Token, not your password)
echo.
git push -u origin main

if errorlevel 1 (
    echo.
    echo  ============================================================
    echo  Push failed. Common fixes:
    echo    - Make sure the repo exists on GitHub and is EMPTY
    echo    - Use a Personal Access Token as your password:
    echo      github.com → Settings → Developer settings → Tokens
    echo    - If you see "rejected", try:  git push -u origin main --force
    echo  ============================================================
    pause & exit /b 1
)

echo.
echo  ============================================================
echo   SUCCESS! Code is now live at:
echo   %REMOTE_URL%
echo  ============================================================
echo.
pause
