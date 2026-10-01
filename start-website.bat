@echo off
setlocal
cd /d "%~dp0"
echo Starting Digital Twin at http://127.0.0.1:8000/ ...
powershell.exe -NoProfile -Command "$root=(Get-Location).Path; $listeners=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; foreach($listener in $listeners) { $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess); if($process.CommandLine -like ('*'+$root+'\.venv\Scripts\python.exe*') -and $process.CommandLine -like '*digital_twin.cli serve*') { Stop-Process -Id $process.ProcessId -Force } else { Write-Error 'Port 8000 is used by another application.'; exit 1 } }; Start-Process -FilePath ($root+'\.venv\Scripts\python.exe') -ArgumentList '-B','-m','digital_twin.cli','serve','--port','8000','--host','0.0.0.0' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput ($root+'\data\twin\server.stdout.log') -RedirectStandardError ($root+'\data\twin\server.stderr.log'); for($attempt=0;$attempt -lt 60;$attempt++) { try { $spec=Invoke-RestMethod 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 2; if($spec.paths.PSObject.Properties.Name -contains '/api/ask/stream') { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; Write-Error 'Server did not start. Check data\twin\server.stderr.log.'; exit 1"
if errorlevel 1 exit /b 1
start "" "http://127.0.0.1:8000/#/chat"
echo Ready. The server is running in the background.
echo Phone access: connect to the same Wi-Fi and use the laptop IPv4 address on port 8000.
