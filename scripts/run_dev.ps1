# Script to start MARY in local development mode
$ErrorActionPreference = "Stop"

Write-Host "=== Starting MARY Local Development Server ===" -ForegroundColor Cyan

# -------------------------------------------------
# 0️⃣ Clean ngrok from PATH (if any) and add new one
$oldNgrokPath = "$HOME\.ngrok"
if ($env:Path -like "*ngrok*") {
    $env:Path = ($env:Path -split ';' | Where-Object { $_ -notmatch '\\ngrok' }) -join ';'
}
$env:Path = "$HOME\.ngrok;$env:Path"

# 1️⃣ Verify virtual‑env
if (-Not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run:" -ForegroundColor Yellow
    Write-Host "    python -m venv .venv" -ForegroundColor Yellow
    Write-Host "    .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# 2️⃣ Load .env variables and set NGROK_AUTHTOKEN
$envFile = Join-Path $PSScriptRoot "..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile |
        Where-Object { $_ -match '^\s*[^#\s][^=]*=.*$' } |
        ForEach-Object {
            $pair = $_ -split '=',2
            $key = $pair[0].Trim()
            $value = $pair[1].Trim()
            Set-Item -Path ("env:" + $key) -Value $value
        }
    Write-Host ".env variables loaded into session." -ForegroundColor Green
}

# 3️⃣ Activate virtual‑env
. .venv\Scripts\Activate.ps1

# 4️⃣ Start FastAPI in background
$projectRoot = Split-Path -Parent $PSScriptRoot
Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    & ".\.venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port 8000
} -ArgumentList $projectRoot | Out-Null
Start-Sleep -Seconds 2
Write-Host "FastAPI server started (background job)." -ForegroundColor Green

# 5️⃣ Path to the new ngrok binary
$ngrokPath = Join-Path $HOME ".ngrok\ngrok.exe"

# 6️⃣ Verify ngrok version (must be >= 3.28)
$ngrokVersion = & $ngrokPath version
Write-Host "Using ngrok version: $ngrokVersion" -ForegroundColor Yellow

# 7️⃣ Set ngrok authtoken (case‑sensitive!)
if ($env:NGROK_AUTHTOKEN) {
    Write-Host "Saving ngrok authtoken…" -ForegroundColor Cyan
    & $ngrokPath authtoken $env:NGROK_AUTHTOKEN
    Write-Host "ngrok authtoken saved." -ForegroundColor Green
}

# 8️⃣ Launch tunnel with the reserved domain/url
Write-Host "Launching ngrok tunnel…" -ForegroundColor Cyan
& $ngrokPath http 8000 --url=salvation-canary-skewer.ngrok-free.dev
