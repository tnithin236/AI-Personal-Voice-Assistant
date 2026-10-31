# Opens the backend and the frontend in two windows, then the browser.
$here = $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File","$here\start_backend.ps1"
Start-Process powershell -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File","$here\start_frontend.ps1"
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
