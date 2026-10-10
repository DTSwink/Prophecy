$ErrorActionPreference = 'Stop'
$taskAppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskDesktop = [Environment]::GetFolderPath('Desktop')
$taskShortcutPath = Join-Path $taskDesktop 'D-S Sword Holster Lab.lnk'
$taskShell = New-Object -ComObject WScript.Shell
$taskShortcut = $taskShell.CreateShortcut($taskShortcutPath)
$taskShortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $taskAppRoot 'launch.ps1') + '"'
$taskShortcut.WorkingDirectory = $taskAppRoot
$taskShortcut.IconLocation = (Join-Path $taskAppRoot 'assets\sword-holster-lab.ico') + ',0'
$taskShortcut.Description = 'D/S: sword drawing and sheathing, idle/walk, reach and holster tuning'
$taskShortcut.WindowStyle = 7
$taskShortcut.Save()
Write-Output $taskShortcutPath
