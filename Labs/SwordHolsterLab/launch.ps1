$ErrorActionPreference = 'Stop'
$taskAppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskPort = 8818
$taskUrl = "http://127.0.0.1:$taskPort/"
try {
    $taskHealth = $null
    try { $taskHealth = Invoke-RestMethod -Uri ($taskUrl + 'health') -TimeoutSec 2 } catch {}
    if ($taskHealth -and ($taskHealth.app -ne 'sword-holster-lab' -or $taskHealth.root -ne $taskAppRoot)) {
        throw "Port $taskPort belongs to a different application."
    }
    if (-not $taskHealth) {
        $taskPython = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/pythonw.exe'
        if (-not (Test-Path -LiteralPath $taskPython)) { throw 'The local Python runtime is missing.' }
        if (-not (Test-Path -LiteralPath (Join-Path $taskAppRoot 'data\manifest.json'))) { throw 'The D/S dataset is missing.' }
        $taskServer = Join-Path $taskAppRoot 'server.py'
        Start-Process -FilePath $taskPython -ArgumentList @(('"' + $taskServer + '"'), '--port', "$taskPort") -WorkingDirectory $taskAppRoot -WindowStyle Hidden
        for ($taskAttempt = 0; $taskAttempt -lt 40; $taskAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $taskHealth = Invoke-RestMethod -Uri ($taskUrl + 'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $taskHealth -or $taskHealth.app -ne 'sword-holster-lab' -or $taskHealth.root -ne $taskAppRoot) { throw 'The local app server could not start.' }
    }
    if ($taskHealth.apiVersion -lt 2) { throw 'The local server needs its version 2 update before opening this build.' }
    $taskDesktopSession = [guid]::NewGuid().ToString('N')
    $taskPayload = @{ token = $taskDesktopSession } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri ($taskUrl + 'desktop-session') -ContentType 'application/json' -Body $taskPayload -TimeoutSec 2 | Out-Null
    $taskUrl += '?desktopSession=' + $taskDesktopSession
    $taskCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe')
    )
    $taskBrowser = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $taskBrowser) { throw 'Microsoft Edge or Google Chrome is required for the 3D app.' }
    $taskProfile = Join-Path $env:LOCALAPPDATA 'SwordHolsterLab\browser-profile'
    # This is the requested interactive app window; the local server stays hidden.
    Start-Process -FilePath $taskBrowser -ArgumentList @(
        "--app=$taskUrl",
        ('--user-data-dir="' + $taskProfile + '"'),
        '--no-first-run', '--no-default-browser-check', '--start-maximized',
        '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
        '--disable-backgrounding-occluded-windows'
    )
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'D-S Sword Holster Lab') | Out-Null
    exit 1
}

