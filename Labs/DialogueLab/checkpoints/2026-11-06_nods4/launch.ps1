# Dialogue Lab: starts the hidden local service on 127.0.0.1:8842 (if not already running).
# Open http://127.0.0.1:8842/ in Claude's browser pane, or pass -Window for a standalone Edge/Chrome app window.
param([switch]$Window, [switch]$Stop)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8842; $url = "http://127.0.0.1:$port/"
function Get-Health { try { Invoke-RestMethod -Uri ($url + 'health') -TimeoutSec 2 } catch { $null } }
$h = Get-Health
if ($Stop) {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" | Where-Object { $_.CommandLine -match 'DialogueLab\\server.py' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force; "stopped $($_.ProcessId)" }
    exit 0
}
if ($h -and ($h.app -ne 'dialogue-lab' -or $h.root -ne $root)) { throw "Port $port belongs to a different application." }
if (-not $h) {
    $py = @('C:\Users\singerie\Documents\Cursor\stepper\.tools\python310\pythonw.exe',
            [IO.Path]::GetFullPath((Join-Path $root '..\..\..\.tools\python310\pythonw.exe'))) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $py) { throw 'The local Python runtime (python310) is missing.' }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'data\boss.glb'))) { throw 'data\boss.glb is missing: run build\lab_build.py first (see README).' }
    $p = Start-Process -FilePath $py -ArgumentList @(('"' + (Join-Path $root 'server.py') + '"'), '--port', "$port") -WorkingDirectory $root -WindowStyle Hidden -PassThru
    try { $p.PriorityClass = 'BelowNormal' } catch {}
    for ($i = 0; $i -lt 40 -and -not $h; $i++) { Start-Sleep -Milliseconds 250; $h = Get-Health }
    if (-not $h) { throw 'The Dialogue Lab server could not start.' }
}
"Dialogue Lab running at $url (pid file-less; stop with launch.ps1 -Stop)"
if ($Window) {
    $b = @((Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'), (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe')) |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    Start-Process -FilePath $b -ArgumentList @("--app=$url", ('--user-data-dir="' + (Join-Path $env:LOCALAPPDATA 'DialogueLab\browser-profile') + '"'), '--no-first-run')
}
