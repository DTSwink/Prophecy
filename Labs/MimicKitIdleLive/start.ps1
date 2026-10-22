$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$ready = Join-Path $projectRoot 'Saved/MimicKitIdleLive/server-ready.json'
if (Get-NetTCPConnection -LocalPort 8850 -State Listen -ErrorAction SilentlyContinue) {
    Write-Output 'Already listening: http://127.0.0.1:8850/'
    exit
}
$python = Join-Path $projectRoot 'Saved/Robotics/env/Scripts/python.exe'
$script = Join-Path $PSScriptRoot 'server.py'
$log = Join-Path $projectRoot 'Saved/MimicKitIdleLive/server.log'
$errors = Join-Path $projectRoot 'Saved/MimicKitIdleLive/server-errors.log'
if (Test-Path -LiteralPath $ready) { Remove-Item -LiteralPath $ready }
$serverProcess = Start-Process -FilePath $python -ArgumentList @('-u', ('"' + $script + '"')) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $errors -PassThru
@{pid=$serverProcess.Id;url='http://127.0.0.1:8850/'} | ConvertTo-Json | Set-Content (Join-Path $projectRoot 'Saved/MimicKitIdleLive/server-process.json')
Write-Output 'Starting paused at http://127.0.0.1:8850/ (initial load takes about a minute).'
