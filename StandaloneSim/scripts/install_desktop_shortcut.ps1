param(
    [switch]$Launch
)

$ErrorActionPreference = 'Stop'
$standaloneRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $standaloneRoot
$launcher = Join-Path $PSScriptRoot 'live_simulation.ps1'
$icon = Join-Path $standaloneRoot 'assets\ProphecySimulationIcon.ico'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Prophecy Simulation.lnk'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $powershell
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = 'Launch the Prophecy standalone simulation with live rebuilds.'
$shortcut.WindowStyle = 7
$shortcut.Save()

Write-Output $shortcutPath

if ($Launch) {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
    Start-Process -FilePath $powershell -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden
}
