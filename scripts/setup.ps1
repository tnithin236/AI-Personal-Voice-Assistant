# One-time setup. Run from anywhere:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"

Write-Host "==> Creating virtual environment (.venv)" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { python -m venv .venv }
& $py -m pip install --upgrade pip

Write-Host "==> Installing PyTorch (CPU build, keeps the 4 GB GPU free for Gemma)" -ForegroundColor Cyan
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw "PyTorch install failed" }

Write-Host "==> Installing backend requirements" -ForegroundColor Cyan
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed - copy the error and send it to me" }

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Write-Host "==> Downloading the English Piper voice" -ForegroundColor Cyan
New-Item -ItemType Directory -Force "data\models\piper" | Out-Null
Push-Location "data\models\piper"
& "..\..\..\.venv\Scripts\python.exe" -m piper.download_voices en_US-lessac-medium
if ($LASTEXITCODE -ne 0) { Write-Warning "Piper voice download failed. See README section 'Piper voice' for the manual steps." }
Pop-Location

Write-Host "==> Installing frontend packages" -ForegroundColor Cyan
Push-Location "frontend"
npm install
Pop-Location

Write-Host "`nSetup finished. Next:  python scripts\check_env.py   (activate .venv first)" -ForegroundColor Green
