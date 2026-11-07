# Script to start AURA in local development mode
$ErrorActionPreference = "Stop"

Write-Host "Starting AURA Local Development Server..." -ForegroundColor Cyan

if (-Not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Please run: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

