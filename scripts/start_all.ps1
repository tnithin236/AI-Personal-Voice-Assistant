# One command to start everything for a demo.
#   powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1            backend + frontend
#   powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -Tamil     ...and the Tamil voice service
#   add -NoBrowser to skip opening the page.
# Safe to run twice: anything already running is left alone (two backends would fight over the memory database).
param([switch]$Tamil, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

function Test-Url([string]$url, [int]$seconds = 2) {
    try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $seconds | Out-Null; return $true } catch { return $false }
}
# Opens a script in its own PowerShell window. The path is wrapped in quotes because folders such as
# "C:\Users\Nithin T\..." contain spaces; without the quotes PowerShell would split the path.
function Start-Window([string]$script) {
    $argText = "-NoExit -ExecutionPolicy Bypass -File `"$PSScriptRoot\$script`""
    Start-Process powershell -ArgumentList $argText
}
function Wait-Url([string]$url, [int]$maxSeconds) {
    for ($i = 0; $i -lt $maxSeconds; $i++) { if (Test-Url $url) { return $true }; Start-Sleep -Seconds 1 }
    return $false
}

# 1. Ollama (the language model server)
if (-not (Test-Url "http://localhost:11434/api/tags")) {
    Write-Host "Starting Ollama..." -ForegroundColor Cyan
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    [void](Wait-Url "http://localhost:11434/api/tags" 40)
}
$ollamaOk = Test-Url "http://localhost:11434/api/tags"

# 2. Backend
if (Test-Url "http://127.0.0.1:8000/api/health" 3) { Write-Host "Backend already running." -ForegroundColor Yellow }
else {
    Write-Host "Starting backend..." -ForegroundColor Cyan
    Start-Window "start_backend.ps1"
}

# 3. Tamil voice service (optional)
if ($Tamil) {
    if (Test-Url "http://127.0.0.1:8010/health" 3) { Write-Host "Tamil voice already running." -ForegroundColor Yellow }
    else {
        Write-Host "Starting Tamil voice service..." -ForegroundColor Cyan
        Start-Window "start_tamil_tts.ps1"
    }
}

# 4. Frontend
if (Test-Url "http://localhost:5173") { Write-Host "Frontend already running." -ForegroundColor Yellow }
else {
    Write-Host "Starting frontend..." -ForegroundColor Cyan
    Start-Window "start_frontend.ps1"
}

# 5. Wait until things answer, then report
Write-Host "Waiting for the backend (it loads speech and memory models; up to 90 s)..." -ForegroundColor Cyan
$backendOk  = Wait-Url "http://127.0.0.1:8000/api/health" 90
$frontendOk = Wait-Url "http://localhost:5173" 30
$tamilOk    = if ($Tamil) { Wait-Url "http://127.0.0.1:8010/health" 90 } else { $null }

""
"Ollama   : $(if ($ollamaOk)  { 'ready' } else { 'NOT reachable - install/start Ollama' })"
"Backend  : $(if ($backendOk) { 'ready' } else { 'not answering yet - check its window' })"
"Frontend : $(if ($frontendOk){ 'ready' } else { 'not answering yet - check its window' })"
if ($Tamil) { "Tamil    : $(if ($tamilOk) { 'ready' } else { 'not answering yet - check its window' })" }
if ($frontendOk -and -not $NoBrowser) { Start-Process "http://localhost:5173" }
"First reply after a start can take a few seconds while the models finish loading."
