$ErrorActionPreference = 'Stop'
$footikRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$footikUrl = 'http://127.0.0.1:8878/'
try {
    $footikHealth = $null
    try { $footikHealth = Invoke-RestMethod -Uri ($footikUrl + 'health') -TimeoutSec 2 } catch {}
    if ($footikHealth -and ($footikHealth.app -ne 'foot-ik-lab' -or $footikHealth.root -ne $footikRoot)) { throw 'Port 8878 belongs to another app.' }
    if (-not $footikHealth) {
        $footikPython = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/pythonw.exe'
        if (-not (Test-Path -LiteralPath $footikPython)) { throw 'The lab Python runtime is missing.' }
        Start-Process -FilePath $footikPython -ArgumentList @(('"' + (Join-Path $footikRoot 'server.py') + '"'), '--port', '8878') -WorkingDirectory $footikRoot -WindowStyle Hidden
        for ($footikAttempt = 0; $footikAttempt -lt 40; $footikAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $footikHealth = Invoke-RestMethod -Uri ($footikUrl + 'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $footikHealth -or $footikHealth.app -ne 'foot-ik-lab' -or $footikHealth.root -ne $footikRoot) { throw 'Foot IK Lab could not start.' }
    }
    $footikCandidates = @((Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'))
    $footikBrowser = $footikCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $footikBrowser) { throw 'Edge or Chrome is required.' }
    $footikProfile = Join-Path $env:LOCALAPPDATA 'FootIKLab/browser-profile'
    # This is the interactive app requested by the user. The server stays hidden.
    Start-Process -FilePath $footikBrowser -ArgumentList @('--app=http://127.0.0.1:8878/', ('--user-data-dir="' + $footikProfile + '"'), '--no-first-run', '--no-default-browser-check', '--start-maximized')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Foot IK Lab') | Out-Null
    exit 1
}
