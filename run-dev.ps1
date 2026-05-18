# Shajara — local development server
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & .\.venv\Scripts\pip.exe install --upgrade pip
    & .\.venv\Scripts\pip.exe install -r requirements.txt
}

Write-Host "Starting Shajara at http://127.0.0.1:5000"
Write-Host "Press Ctrl+C to stop."
& .\.venv\Scripts\python.exe -m flask --app app:create_app run --host 127.0.0.1 --port 5000
