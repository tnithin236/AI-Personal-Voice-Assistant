# Starts the OPTIONAL Tamil speech service on port 8010.
#   default:                         MMS-TTS Tamil, runs in the main .venv (no extra install)
#   $env:TAMIL_TTS_ENGINE = "indic": AI4Bharat Indic-TTS from .venv-tamil (advanced, unverified)
Set-Location (Split-Path $PSScriptRoot -Parent)
$engine = if ($env:TAMIL_TTS_ENGINE) { $env:TAMIL_TTS_ENGINE } else { "mms" }
$py = if ($engine -eq "indic") { ".\.venv-tamil\Scripts\python.exe" } else { ".\.venv\Scripts\python.exe" }
Write-Host "Tamil TTS engine: $engine" -ForegroundColor Cyan
& $py services\tamil_tts\server.py
