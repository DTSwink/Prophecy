$ErrorActionPreference = 'Stop'
$bodyflipRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bodyflipUrl = 'http://127.0.0.1:8876/'
try {
    $bodyflipHealth = $null
    try { $bodyflipHealth = Invoke-RestMethod -Uri ($bodyflipUrl + 'health') -TimeoutSec 2 } catch {}
    if ($bodyflipHealth -and ($bodyflipHealth.app -ne 'bodyflip-lab' -or $bodyflipHealth.root -ne $bodyflipRoot)) { throw 'Port 8876 belongs to another app.' }
    if (-not $bodyflipHealth) {
        $bodyflipPython = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/pythonw.exe'
        if (-not (Test-Path -LiteralPath $bodyflipPython)) { throw 'The lab Python runtime is missing.' }
        Start-Process -FilePath $bodyflipPython -ArgumentList @(('"' + (Join-Path $bodyflipRoot 'server.py') + '"'), '--port', '8876') -WorkingDirectory $bodyflipRoot -WindowStyle Hidden
        for ($bodyflipAttempt = 0; $bodyflipAttempt -lt 40; $bodyflipAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $bodyflipHealth = Invoke-RestMethod -Uri ($bodyflipUrl + 'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $bodyflipHealth -or $bodyflipHealth.app -ne 'bodyflip-lab' -or $bodyflipHealth.root -ne $bodyflipRoot) { throw 'Bodyflip Lab could not start.' }
    }
    $bodyflipCandidates = @((Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'))
    $bodyflipBrowser = $bodyflipCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $bodyflipBrowser) { throw 'Edge or Chrome is required.' }
    $bodyflipProfile = Join-Path $env:LOCALAPPDATA 'BodyflipLab/browser-profile'
    # This is the interactive app requested by the user. The server stays hidden.
    Start-Process -FilePath $bodyflipBrowser -ArgumentList @('--app=http://127.0.0.1:8876/', ('--user-data-dir="' + $bodyflipProfile + '"'), '--no-first-run', '--no-default-browser-check', '--start-maximized')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Bodyflip Lab') | Out-Null
    exit 1
}
