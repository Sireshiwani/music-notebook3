@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\pip.exe install --upgrade pip
    call .venv\Scripts\pip.exe install -r requirements.txt
)
echo.
echo Starting Shajara at http://127.0.0.1:5000
echo Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
pause
