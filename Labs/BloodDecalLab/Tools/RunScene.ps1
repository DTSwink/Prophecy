param([switch]$Render, [switch]$Performance)
$ErrorActionPreference = 'Stop'
$labRoot = (Split-Path -Parent $PSScriptRoot).Replace('\','/')
$labProject = "$labRoot/BloodDecalLab.uproject"
$labScript = "$labRoot/Tools/run_scene.py"
if ($Performance) {
    if ($Render) { throw 'Performance script measures NullRHI CPU cost only' }
    $labScript = "$labRoot/Tools/perf_scene.py"
}
$labLog = "$labRoot/Saved/scene-validation.log"
# Forward slashes avoid the Python commandlet interpreting \r in \run_scene.py.
$labArgs = @(
    ('"' + $labProject + '"'),
    '-run=pythonscript',
    ('-script="' + $labScript + '"'),
    '-unattended', '-nosound', '-nocef', '-NoSplash',
    ('-abslog="' + $labLog + '"')
)
if ($Render) { $labArgs += @('-AllowCommandletRendering','-RenderOffscreen') }
else { $labArgs += '-NullRHI' }
$labProcess = Start-Process `
    -FilePath 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' `
    -ArgumentList $labArgs -WindowStyle Hidden -PassThru
$labProcess.PriorityClass = 'BelowNormal'
$labProcess.Id
