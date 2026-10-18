$ErrorActionPreference='Stop'
$taskAppRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
$taskDesktop=[Environment]::GetFolderPath('Desktop')
$taskLinkPath=Join-Path $taskDesktop 'REACH - Hand & Body Lab.lnk'
$taskShell=New-Object -ComObject WScript.Shell
$taskLink=$taskShell.CreateShortcut($taskLinkPath)
$taskLink.TargetPath=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$taskLink.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+(Join-Path $taskAppRoot 'launch.ps1')+'"'
$taskLink.WorkingDirectory=$taskAppRoot
$taskLink.IconLocation=(Join-Path $taskAppRoot 'icon.ico')+',0'
$taskLink.Description='REACH: two draggable hand targets and the whole-body reach solver'
$taskLink.WindowStyle=7
$taskLink.Save()
Write-Output $taskLinkPath
