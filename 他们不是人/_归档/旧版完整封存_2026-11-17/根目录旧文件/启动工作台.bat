@echo off
setlocal enabledelayedexpansion

REM ============================================
REM  Story Dashboard one-click launcher
REM  Double-click this file to start the local
REM  dashboard in background and open browser.
REM  To STOP: close the minimized console window.
REM ============================================

set "SKILL_DIR=C:\Users\jia\.workbuddy\skills\story"
set "DASHBOARD=%SKILL_DIR%\scripts\dashboard-server.mjs"
set "WORKSPACE=D:\code\stroy"
set "NODE_CMD=node"

REM ---- Check node ----
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found in PATH. Please install Node.js first.
    pause
    exit /b 1
)

REM ---- Check dashboard script ----
if not exist "%DASHBOARD%" (
    echo [ERROR] dashboard-server.mjs not found: %DASHBOARD%
    pause
    exit /b 1
)

REM ---- Check workspace ----
if not exist "%WORKSPACE%" (
    echo [ERROR] Workspace not found: %WORKSPACE%
    pause
    exit /b 1
)

echo [INFO] Starting story Dashboard...
echo        Workspace : %WORKSPACE%
echo        Port      : 127.0.0.1 (local only)
echo.
echo [INFO] Dashboard will open in your browser automatically.
echo        To STOP it, close the minimized console window.

REM ---- Start in background, minimized ----
start "story-dashboard" /min cmd /k ""%NODE_CMD%" "%DASHBOARD%" --root "%WORKSPACE%" --open"

timeout /t 2 /nobreak >nul
exit /b 0
