@echo off
setlocal
title ARIA - AI Agent Dashboard
cd /d "%~dp0"

REM ------------------------------------------------------------------
REM  ARIA launcher (Windows): double-click to start the app.
REM  Opens in its own terminal window; close the window to stop ARIA.
REM ------------------------------------------------------------------

if "%PORT%"=="" set PORT=8000

REM --- Python present? -------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Install Python 3.10+ from https://python.org and tick "Add python.exe to PATH".
    goto :fail
)

REM --- .env present? (the app reads it itself) --------------------------
if not exist .env (
    if exist .env.example (
        copy /y .env.example .env >nul
        echo [INFO] Created .env from .env.example.
    )
    echo [ERROR] Open the .env file in this folder, set DATABASE_URL and your API keys, save it, then run this again.
    start notepad .env
    goto :fail
)

REM --- Virtual environment ---------------------------------------------
if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 goto :fail
)
call venv\Scripts\activate
if errorlevel 1 goto :fail

echo Installing / checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency install failed. See the messages above.
    goto :fail
)

echo.
echo ==========================================
echo   ARIA - AI Agent Dashboard
echo   http://localhost:%PORT%
echo   Close this window to stop the server.
echo ==========================================
echo.

REM Open the browser a few seconds after the server starts
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:%PORT%"

uvicorn main:app --host 127.0.0.1 --port %PORT%

echo.
echo The server stopped. Scroll up for the reason (e.g. database connection error).
goto :fail

:fail
echo.
pause
exit /b 1
