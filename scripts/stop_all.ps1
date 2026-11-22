# Stops Vaani's backend, Tamil voice service and frontend dev server. Ollama is left running.
#   powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1
$root = Split-Path $PSScriptRoot -Parent
$procs = Get-CimInstance Win32_Process | Where-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return $false }
    ($cmd -match 'backend\.main') -or
    ($cmd -match 'tamil_tts[\\/]server\.py') -or
    ($_.Name -match '^(node|esbuild)(\.exe)?$' -and $cmd -like "*$root*")      # only THIS project's dev server
}
if (-not $procs) { "Nothing of Vaani is running."; return }
foreach ($p in $procs) {
    "Stopping $($p.Name) (pid $($p.ProcessId))"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
"Done. You can close the leftover PowerShell windows."
