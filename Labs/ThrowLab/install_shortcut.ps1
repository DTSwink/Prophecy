$ErrorActionPreference = 'Stop'
$throwRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$throwDesktop = [Environment]::GetFolderPath('Desktop')
$throwShortcutPath = Join-Path $throwDesktop 'Throw Lab.lnk'
$throwShell = New-Object -ComObject WScript.Shell
$throwShortcut = $throwShell.CreateShortcut($throwShortcutPath)
$throwShortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$throwShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $throwRoot 'launch.ps1') + '"'
$throwShortcut.WorkingDirectory = $throwRoot
$throwShortcut.IconLocation = (Join-Path $throwRoot 'assets/throw-target.ico') + ',0'
$throwShortcut.Description = 'Throw Lab: authored throws and movable target'
$throwShortcut.WindowStyle = 7
$throwShortcut.Save()
Write-Output $throwShortcutPath
