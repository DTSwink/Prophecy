$ErrorActionPreference = 'Stop'
$footikRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$footikPort = 8890
$footikUrl = "http://127.0.0.1:$footikPort/"
$footikState = Join-Path $footikRoot 'snapshots/overnight-state.json'
try {
    $footikHealth = $null
    try { $footikHealth = Invoke-RestMethod -Uri ($footikUrl + 'health') -TimeoutSec 2 } catch {}
    if ($footikHealth -and ($footikHealth.app -ne 'foot-ik-lab' -or $footikHealth.root -ne $footikRoot)) { throw "Port $footikPort belongs to another app." }
    if ($footikHealth -and ($footikHealth.apiVersion -lt 7 -or $footikHealth.stateProtocol -ne 2)) { throw 'Foot IK server is outdated. No process was stopped.' }
    if (-not $footikHealth) {
        $footikPython = 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/pythonw.exe'
        if (-not (Test-Path -LiteralPath $footikPython)) { throw 'The lab Python runtime is missing.' }
        # Keep old sessions from overwriting the migrated app's playback state.
        if (-not (Test-Path -LiteralPath $footikState)) {
            $footikOldState = Join-Path $footikRoot 'state.json'
            if (Test-Path -LiteralPath $footikOldState) { Copy-Item -LiteralPath $footikOldState -Destination $footikState }
        }
        Start-Process -FilePath $footikPython -ArgumentList @(('"' + (Join-Path $footikRoot 'server.py') + '"'), '--port', $footikPort, '--state-file', ('"' + $footikState + '"')) -WorkingDirectory $footikRoot -WindowStyle Hidden
        for ($footikAttempt = 0; $footikAttempt -lt 40; $footikAttempt++) {
            Start-Sleep -Milliseconds 250
            try { $footikHealth = Invoke-RestMethod -Uri ($footikUrl + 'health') -TimeoutSec 1; break } catch {}
        }
        if (-not $footikHealth -or $footikHealth.app -ne 'foot-ik-lab' -or $footikHealth.root -ne $footikRoot -or ($footikHealth.apiVersion -lt 7 -or $footikHealth.stateProtocol -ne 2)) { throw 'Foot IK Lab could not start.' }
    }
    $footikCandidates = @((Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Microsoft/Edge/Application/msedge.exe'), (Join-Path $env:ProgramFiles 'Google/Chrome/Application/chrome.exe'))
    $footikBrowser = $footikCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $footikBrowser) { throw 'Edge or Chrome is required.' }
    $footikProfile = Join-Path $env:LOCALAPPDATA 'FootIKLab/browser-profile'
    # This is the interactive app requested by the user. The server stays hidden.
    Start-Process -FilePath $footikBrowser -ArgumentList @(('--app=' + $footikUrl), ('--user-data-dir="' + $footikProfile + '"'), '--no-first-run', '--no-default-browser-check', '--start-maximized')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Foot IK Lab') | Out-Null
    exit 1
}
