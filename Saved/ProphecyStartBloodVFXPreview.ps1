param(
    [int]$ResX = 1280,
    [int]$ResY = 720,
    [double]$Scale = 1.0,
    [double]$TimeScale = 1.0
)

$StartLivePreview = Join-Path $PSScriptRoot "ProphecyStartLivePreview.ps1"
$extraArgs = @(
    "-ProphecyNNBloodVFX=1",
    "-ProphecyNNBloodVFXScale=$Scale",
    "-ProphecyNNBloodVFXTimeScale=$TimeScale",
    "-ProphecyNNGrass=0",
    "-ProphecyNNTrees=0",
    "-ProphecyNNFloor=1",
    "-ProphecyNNLights=1",
    "-ProphecyNNPreviewCameraSide=Front"
)

& $StartLivePreview -ResX $ResX -ResY $ResY -ExtraArgs $extraArgs
