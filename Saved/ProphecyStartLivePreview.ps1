param(
    [int]$ResX = 1280,
    [int]$ResY = 720,
    [string]$ConfigPath = "$PSScriptRoot\ProphecyLiveVisual.json",
    [switch]$HideGrass,
    [switch]$HideGrassBladesOnly
)

$Editor = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
$Project = "C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject"

$argsList = @(
    "`"$Project`"",
    "-game",
    "-RenderOffscreen",
    "-Unattended",
    "-NoSplash",
    "-NoSound",
    "-windowed",
    "-ResX=$ResX",
    "-ResY=$ResY",
    "-ForceRes",
    "-ProphecyNNBenchmark",
    "-ProphecyNNLiveVisual=1",
    "`"-ProphecyNNLiveConfig=$ConfigPath`"",
    "-ProphecyNNLivePoll=0.10",
    "-ProphecyNNBenchmarkSeconds=0",
    "-ProphecyNNSceneryOnly=1",
    "-ProphecyNNAgents=0",
    "-ProphecyNNVisuals=0",
    "-ProphecyNNGrass=1",
    "-ProphecyNNTrees=0",
    "-ProphecyNNTreeCount=0",
    "-ProphecyNNRenderProfile=1",
    "-ProphecyNNShadows=0",
    "-ProphecyNNShadowMode=None",
    "-ProphecyNNContactShadows=0"
)

if ($HideGrass) {
    $argsList += "-ProphecyNNHideGrass=1"
}

if ($HideGrassBladesOnly) {
    $argsList += "-ProphecyNNHideGrassBladesOnly=1"
}

$process = Start-Process -FilePath $Editor -ArgumentList ($argsList -join " ") -WindowStyle Hidden -PassThru
Write-Output "Started live Prophecy preview PID=$($process.Id)"
Write-Output "Config: $ConfigPath"
