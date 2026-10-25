$ErrorActionPreference = 'Stop'
$footikRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$footikDesktop = [Environment]::GetFolderPath('Desktop')
$footikShortcutPath = Join-Path $footikDesktop 'Foot IK Lab.lnk'
$footikShell = New-Object -ComObject WScript.Shell
$footikShortcut = $footikShell.CreateShortcut($footikShortcutPath)
$footikShortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$footikShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $footikRoot 'launch.ps1') + '"'
$footikShortcut.WorkingDirectory = $footikRoot
$footikShortcut.IconLocation = (Join-Path $footikRoot 'assets/footik.ico') + ',0'
$footikShortcut.Description = 'Foot IK Lab: NN locomotion, terrain foot placement and stair IK'
$footikShortcut.WindowStyle = 7
$footikShortcut.Save()
Write-Output $footikShortcutPath
