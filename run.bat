@echo off
REM run.bat — One-command startup for the ARIA dashboard (Windows)

echo.
echo Loading environment variables...
if exist .env (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set %%a=%%b
    )
    echo [OK] .env loaded
) else (
    echo [WARN] No .env file found. Copy .env.example to .env
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

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
