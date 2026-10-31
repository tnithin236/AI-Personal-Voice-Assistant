# Starts the OPTIONAL Tamil TTS service from its own virtual environment (.venv-tamil).
Set-Location (Split-Path $PSScriptRoot -Parent)
& .\.venv-tamil\Scripts\python.exe services\tamil_tts\server.py
