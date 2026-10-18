$ErrorActionPreference = 'Stop'
$taskAppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskUrl = 'http://127.0.0.1:8873/'
# Chromium app identity uses host + path, omitting the port. A unique path keeps
# REACH separate from the D/S lab at 127.0.0.1:<other-port>/.
$taskAppUrl = $taskUrl + 'reach'
$taskPython = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe'
$taskPythonWindowless = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/pythonw.exe'
try {
    $taskHealth = $null
    try { $taskHealth = Invoke-RestMethod ($taskUrl + 'health') -TimeoutSec 2 } catch {}
    if ($taskHealth -and ($taskHealth.app -ne 'reach-lab' -or $taskHealth.root -ne $taskAppRoot)) { throw 'Port 8873 belongs to a different app.' }
    if (-not $taskHealth) {
        if (Get-NetTCPConnection -LocalPort 8873 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8873 is already occupied by another service.' }
        if (-not (Test-Path -LiteralPath (Join-Path $taskAppRoot 'bin/reach.dll'))) {
            & $taskPython (Join-Path $taskAppRoot 'build.py')
            if ($LASTEXITCODE -ne 0) { throw 'Standalone reach solver build failed.' }
        }
        Start-Process $taskPythonWindowless -ArgumentList ('"' + (Join-Path $taskAppRoot 'server.py') + '"') -WorkingDirectory $taskAppRoot -WindowStyle Hidden
        for ($taskAttempt=0; $taskAttempt -lt 40; $taskAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $taskHealth=Invoke-RestMethod ($taskUrl+'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $taskHealth -or $taskHealth.app -ne 'reach-lab' -or $taskHealth.root -ne $taskAppRoot) { throw 'Reach lab server did not start.' }
    }
    if ($taskHealth.apiVersion -lt 3) { throw 'Restart the REACH lab server to load the compact recording service update.' }
    $taskDesktopSession=[guid]::NewGuid().ToString('N')
    Invoke-RestMethod -Method Post -Uri ($taskUrl+'desktop-session') -ContentType 'application/json' -Body (@{token=$taskDesktopSession}|ConvertTo-Json -Compress) -TimeoutSec 2 | Out-Null
    $taskAppUrl+='?desktopSession='+$taskDesktopSession
    $taskBrowser=Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'
    if (-not (Test-Path -LiteralPath $taskBrowser)) { $taskBrowser=Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe' }
    if (-not (Test-Path -LiteralPath $taskBrowser)) { throw 'Edge or Chrome is required.' }
    $taskProfile=Join-Path $env:LOCALAPPDATA 'ProphecyReachLab/browser-profile'
    # User-facing app MUST be visible. Only the background server is hidden.
    Start-Process $taskBrowser -ArgumentList @(('--app='+$taskAppUrl),('--user-data-dir="'+$taskProfile+'"'),'--no-first-run','--no-default-browser-check','--start-maximized','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows') -WindowStyle Normal
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'REACH — Hand & Body Lab') | Out-Null
    exit 1
}
