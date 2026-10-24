$ErrorActionPreference = 'Stop'
$bodyflipRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bodyflipDesktop = [Environment]::GetFolderPath('Desktop')
$bodyflipShortcutPath = Join-Path $bodyflipDesktop 'Bodyflip Lab.lnk'
$bodyflipShell = New-Object -ComObject WScript.Shell
$bodyflipShortcut = $bodyflipShell.CreateShortcut($bodyflipShortcutPath)
$bodyflipShortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$bodyflipShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $bodyflipRoot 'launch.ps1') + '"'
$bodyflipShortcut.WorkingDirectory = $bodyflipRoot
$bodyflipShortcut.IconLocation = (Join-Path $bodyflipRoot 'assets/bodyflip.ico') + ',0'
$bodyflipShortcut.Description = 'Bodyflip Lab: full-body Jolt flips, pelvis twist and aimed attacks'
$bodyflipShortcut.WindowStyle = 7
$bodyflipShortcut.Save()
Write-Output $bodyflipShortcutPath
