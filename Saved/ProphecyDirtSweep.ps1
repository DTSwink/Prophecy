param(
    [double]$SettleSeconds = 1.25,
    [switch]$Wait
)

$liveShot = Join-Path $PSScriptRoot "ProphecyLiveShot.ps1"

$waitArg = @{}
if ($Wait) {
    $waitArg.Wait = $true
}

& $liveShot `
    -Name "dirt_live_control_spotty" `
    -DirtStrength 0.72 `
    -DirtPatchWorldCm 18000 `
    -DirtPatchThreshold 0.08 `
    -DirtPatchContrast 1.80 `
    -SettleSeconds $SettleSeconds `
    @waitArg

& $liveShot `
    -Name "dirt_live_diffuse_broad_soft" `
    -DirtStrength 0.58 `
    -DirtPatchWorldCm 32000 `
    -DirtPatchThreshold -0.12 `
    -DirtPatchContrast 0.62 `
    -DirtColor @(0.155, 0.108, 0.062, 1.0) `
    -GroundNoiseStrength 0.48 `
    -SettleSeconds $SettleSeconds `
    @waitArg

& $liveShot `
    -Name "dirt_live_diffuse_visible_soft" `
    -DirtStrength 0.76 `
    -DirtPatchWorldCm 42000 `
    -DirtPatchThreshold -0.18 `
    -DirtPatchContrast 0.45 `
    -DirtColor @(0.165, 0.118, 0.070, 1.0) `
    -GroundNoiseStrength 0.44 `
    -SettleSeconds $SettleSeconds `
    @waitArg
