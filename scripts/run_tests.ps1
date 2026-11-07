# Script to execute automated test suite
$ErrorActionPreference = "Stop"

Write-Host "Running AURA Test Suite..." -ForegroundColor Cyan

if (-Not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found." -ForegroundColor Red
    exit 1
}

.\.venv\Scripts\python.exe -m pytest -v

