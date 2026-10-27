$ErrorActionPreference = 'Stop'
$throwRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$throwUrl = 'http://127.0.0.1:8893/'
# Chromium URL-app taskbar identity uses host + path, not the port.
$throwAppUrl = $throwUrl + 'throw-lab.html'
try {
    $throwHealth = $null
    try { $throwHealth = Invoke-RestMethod -Uri ($throwUrl + 'health') -TimeoutSec 2 } catch {}
    if ($throwHealth -and ($throwHealth.app -ne 'throw-lab' -or $throwHealth.root -ne $throwRoot)) { throw 'Port 8893 belongs to another app.' }
    if (-not $throwHealth) {
        $throwPython = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/pythonw.exe'
        if (-not (Test-Path -LiteralPath $throwPython)) { throw 'The lab Python runtime is missing.' }
        $throwService = Start-Process -FilePath $throwPython -ArgumentList @(('"' + (Join-Path $throwRoot 'server.py') + '"'), '--port', '8893') -WorkingDirectory $throwRoot -WindowStyle Hidden -PassThru
        $throwService.PriorityClass = 'BelowNormal'
        for ($throwAttempt = 0; $throwAttempt -lt 40; $throwAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $throwHealth = Invoke-RestMethod -Uri ($throwUrl + 'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $throwHealth -or $throwHealth.app -ne 'throw-lab' -or $throwHealth.root -ne $throwRoot) { throw 'Throw Lab could not start.' }
    }
    $throwCandidates = @((Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'))
    $throwBrowser = $throwCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $throwBrowser) { throw 'Edge or Chrome is required.' }
    $throwProfile = Join-Path $env:LOCALAPPDATA 'ThrowLab/browser-profile'
    # This is the interactive app requested by the user. The server stays hidden.
    Start-Process -FilePath $throwBrowser -ArgumentList @(('--app=' + $throwAppUrl), ('--user-data-dir="' + $throwProfile + '"'), '--no-first-run', '--no-default-browser-check', '--start-maximized')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Throw Lab') | Out-Null
    exit 1
}
