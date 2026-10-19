@echo off
REM run.bat — One-command startup for the ARIA dashboard (Windows)

cd /d "%~dp0"

echo.
REM .env is loaded by the app itself (python-dotenv)
if not exist .env (
    echo [ERROR] No .env file found. Copy .env.example to .env and set DATABASE_URL
    exit /b 1
)

REM Create venv if missing
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate
call venv\Scripts\activate

REM Install deps
echo Installing dependencies...
pip install -q -r requirements.txt

echo.
echo ==========================================
echo   ARIA - AI Agent Dashboard
echo   http://localhost:8000
echo ==========================================
echo.

uvicorn main:app --host 127.0.0.1 --port 8000 --reload
