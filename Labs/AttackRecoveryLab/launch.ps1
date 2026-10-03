param([string]$PythonExecutable = $env:PROPHECY_LAB_PYTHON)
$ErrorActionPreference = 'Stop'
$taskAppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskPort = 8817
$taskUrl = "http://127.0.0.1:$taskPort/"
try {
    $taskHealth = $null
    try { $taskHealth = Invoke-RestMethod -Uri ($taskUrl + 'health') -TimeoutSec 2 } catch {}
    if ($taskHealth -and ($taskHealth.app -ne 'attack-recovery-lab' -or $taskHealth.root -ne $taskAppRoot)) {
        throw "Port $taskPort belongs to a different application."
    }
    if (-not $taskHealth) {
        $taskPython = $PythonExecutable
        if (-not $taskPython) {
            $taskLegacyPython = [System.IO.Path]::GetFullPath((Join-Path $taskAppRoot '..\..\..\.tools\python310\pythonw.exe'))
            if (Test-Path -LiteralPath $taskLegacyPython) { $taskPython = $taskLegacyPython }
            else {
                $taskPythonCommand = Get-Command pythonw.exe -ErrorAction SilentlyContinue
                if ($taskPythonCommand) { $taskPython = $taskPythonCommand.Source }
                else {
                    $taskPyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
                    if ($taskPyLauncher) { $taskPython = (& $taskPyLauncher.Source -3 -c 'import sys; print(sys.executable)').Trim() }
                }
            }
        }
        if (-not $taskPython -or -not (Test-Path -LiteralPath $taskPython)) { throw 'Install Python 3.10+ or set PROPHECY_LAB_PYTHON to its executable path.' }
        if (-not (Test-Path -LiteralPath (Join-Path $taskAppRoot 'data\manifest.json'))) { throw 'The attack dataset is missing.' }
        $taskServer = Join-Path $taskAppRoot 'server.py'
        Start-Process -FilePath $taskPython -ArgumentList @(('"' + $taskServer + '"'), '--port', "$taskPort") -WorkingDirectory $taskAppRoot -WindowStyle Hidden
        for ($taskAttempt = 0; $taskAttempt -lt 40; $taskAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $taskHealth = Invoke-RestMethod -Uri ($taskUrl + 'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $taskHealth -or $taskHealth.app -ne 'attack-recovery-lab' -or $taskHealth.root -ne $taskAppRoot) { throw 'The local app server could not start.' }
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
    $taskProfile = Join-Path $env:LOCALAPPDATA 'AttackRecoveryLab\browser-profile'
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
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Attack Recovery Lab') | Out-Null
    exit 1
}
