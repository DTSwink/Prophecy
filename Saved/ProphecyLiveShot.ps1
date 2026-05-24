param(
    [string]$Name = ("live_" + (Get-Date -Format "HHmmss")),
    [object[]]$GrassDistantColor = @(),
    [object]$GrassDistantStartCm = $null,
    [object]$GrassDistantRangeCm = $null,
    [object]$GrassDistantFlattenStartCm = $null,
    [object]$GrassDistantFlattenRangeCm = $null,
    [object]$GrassDistantFlattenCm = $null,
    [object]$GrassDebugDistanceKillStartCm = $null,
    [object]$GrassDebugDistanceKillRangeCm = $null,
    [object[]]$GrassFarRootLiftColor = @(),
    [object]$GrassFarRootLiftStartCm = $null,
    [object]$GrassFarRootLiftRangeCm = $null,
    [object]$GrassFarRootLiftStrength = $null,
    [object[]]$GroundBaseColor = @(),
    [object]$GroundNoiseStrength = $null,
    [object]$GroundNoiseWorldCm = $null,
    [object[]]$GroundGrassGrainDarkColor = @(),
    [object[]]$GroundGrassGrainLightColor = @(),
    [object]$GroundGrassGrainStrength = $null,
    [object]$GroundGrassGrainWorldCm = $null,
    [object]$GroundGrassGrainFrequency = $null,
    [object]$GroundGrassGrainFadeStartCm = $null,
    [object]$GroundGrassGrainFadeRangeCm = $null,
    [object]$GroundGrassGrainFadeInvRange = $null,
    [object[]]$GroundFarGrassBlendColor = @(),
    [object]$GroundFarGrassBlendStrength = $null,
    [object]$GroundFarGrassBlendStartCm = $null,
    [object]$GroundFarGrassBlendRangeCm = $null,
    [object]$GroundFarGrassBlendInvRange = $null,
    [object]$GroundGrassImpostorStrength = $null,
    [object]$GroundGrassImpostorWorldCm = $null,
    [object]$GroundGrassImpostorWorldXCm = $null,
    [object]$GroundGrassImpostorWorldYCm = $null,
    [object]$GroundGrassImpostorScale = $null,
    [object]$GroundGrassImpostorScaleX = $null,
    [object]$GroundGrassImpostorScaleY = $null,
    [object]$GroundGrassImpostorStartCm = $null,
    [object]$GroundGrassImpostorRangeCm = $null,
    [object]$GroundGrassImpostorInvRange = $null,
    [object[]]$DirtColor = @(),
    [object]$GrassShadowStrength = $null,
    [object]$DirtStrength = $null,
    [object]$DirtPatchWorldCm = $null,
    [object]$DirtPatchScale = $null,
    [object]$DirtPatchThreshold = $null,
    [object]$DirtPatchContrast = $null,
    [object]$DirtTextureWorldCm = $null,
    [object]$DirtTextureStrength = $null,
    [object]$DirtFadeStartCm = $null,
    [object]$DirtFadeRangeCm = $null,
    [object]$DirtViewMin = $null,
    [object]$DirtViewScale = $null,
    [switch]$HideGrass,
    [switch]$ShowGrass,
    [switch]$HideHills,
    [switch]$ShowHills,
    [object[]]$CameraLocation = @(),
    [object[]]$CameraLookAt = @(),
    [object]$CameraFov = $null,
    [object]$SunPitch = $null,
    [object]$SunYaw = $null,
    [object]$SunIntensity = $null,
    [object]$SkyIntensity = $null,
    [switch]$BloodPreview,
    [switch]$BloodClear,
    [object[]]$BloodColor = @(),
    [object[]]$BloodDarkColor = @(),
    [object[]]$BloodGrassRootColor = @(),
    [object[]]$BloodGrassColor = @(),
    [object]$BloodStrength = $null,
    [object]$BloodWetStrength = $null,
    [object]$BloodGrassStrength = $null,
    [object]$BloodRadiusScale = $null,
    [double]$SettleSeconds = 1.0,
    [double]$WakeSeconds = 0.50,
    [double]$ReadyTimeoutSeconds = 45.0,
    [int]$PreviewPid = 0,
    [switch]$KeepPreviewAwake,
    [switch]$SkipReadyWait,
    [switch]$NoScreenshot,
    [switch]$Wait
)

$PreviewPowerScript = Join-Path $PSScriptRoot "ProphecyLivePreviewPower.ps1"
if ((-not $KeepPreviewAwake) -and (Test-Path -LiteralPath $PreviewPowerScript)) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PreviewPowerScript -Action Resume -ProcessId $PreviewPid | Out-Null
    if ($WakeSeconds -gt 0.0) {
        Start-Sleep -Milliseconds ([Math]::Max(0, [int]($WakeSeconds * 1000.0)))
    }
}

function ConvertTo-DoubleArray {
    param([object[]]$Values)

    $result = @()
    foreach ($value in @($Values)) {
        if ($null -eq $value) {
            continue
        }

        foreach ($part in ($value.ToString() -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed.Length -eq 0) {
                continue
            }
            $result += [double]::Parse($trimmed, [System.Globalization.CultureInfo]::InvariantCulture)
        }
    }
    return [double[]]$result
}

function ConvertTo-DoubleValue {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    return [double]::Parse($Value.ToString(), [System.Globalization.CultureInfo]::InvariantCulture)
}

$GrassDistantColorValues = ConvertTo-DoubleArray $GrassDistantColor
$GrassFarRootLiftColorValues = ConvertTo-DoubleArray $GrassFarRootLiftColor
$GroundBaseColorValues = ConvertTo-DoubleArray $GroundBaseColor
$GroundGrassGrainDarkColorValues = ConvertTo-DoubleArray $GroundGrassGrainDarkColor
$GroundGrassGrainLightColorValues = ConvertTo-DoubleArray $GroundGrassGrainLightColor
$GroundFarGrassBlendColorValues = ConvertTo-DoubleArray $GroundFarGrassBlendColor
$DirtColorValues = ConvertTo-DoubleArray $DirtColor
$BloodColorValues = ConvertTo-DoubleArray $BloodColor
$BloodDarkColorValues = ConvertTo-DoubleArray $BloodDarkColor
$BloodGrassRootColorValues = ConvertTo-DoubleArray $BloodGrassRootColor
$BloodGrassColorValues = ConvertTo-DoubleArray $BloodGrassColor
$CameraLocationValues = ConvertTo-DoubleArray $CameraLocation
$CameraLookAtValues = ConvertTo-DoubleArray $CameraLookAt

$ConfigPath = "$PSScriptRoot\ProphecyLiveVisual.json"
$ReadyPath = [System.IO.Path]::ChangeExtension($ConfigPath, "ready.json")
$ShotDir = "$PSScriptRoot\LiveShots"
New-Item -ItemType Directory -Path $ShotDir -Force | Out-Null

function Wait-LivePreviewReady {
    param(
        [string]$Path,
        [int]$ProcessId,
        [double]$TimeoutSeconds
    )

    $processStart = $null
    if ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            throw "Live preview PID $ProcessId is not running."
        }
        $processStart = $process.StartTime
    }

    $deadline = (Get-Date).AddSeconds([Math]::Max(1.0, $TimeoutSeconds))
    while ((Get-Date) -lt $deadline) {
        $ready = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
        if ($null -ne $ready) {
            if ($null -eq $processStart -or $ready.LastWriteTime -ge $processStart) {
                Write-Output "Live preview ready: $Path"
                return
            }
        }
        Start-Sleep -Milliseconds 250
    }

    throw "Live preview did not report ready within $TimeoutSeconds seconds: $Path"
}

$payload = [ordered]@{
    nonce = [DateTime]::UtcNow.Ticks
}

if ($GrassDistantColorValues.Count -ge 3) {
    $payload.grass_distant_color = @($GrassDistantColorValues)
}

if ($null -ne $GrassDistantStartCm) {
    $payload.grass_distant_color_start_cm = ConvertTo-DoubleValue $GrassDistantStartCm
}

if ($null -ne $GrassDistantRangeCm) {
    $payload.grass_distant_color_range_cm = ConvertTo-DoubleValue $GrassDistantRangeCm
}

if ($null -ne $GrassDistantFlattenStartCm) {
    $payload.grass_distant_flatten_start_cm = ConvertTo-DoubleValue $GrassDistantFlattenStartCm
}

if ($null -ne $GrassDistantFlattenRangeCm) {
    $payload.grass_distant_flatten_range_cm = ConvertTo-DoubleValue $GrassDistantFlattenRangeCm
}

if ($null -ne $GrassDistantFlattenCm) {
    $payload.grass_distant_flatten_cm = ConvertTo-DoubleValue $GrassDistantFlattenCm
}

if ($null -ne $GrassDebugDistanceKillStartCm) {
    $payload.grass_debug_distance_kill_start_cm = ConvertTo-DoubleValue $GrassDebugDistanceKillStartCm
}

if ($null -ne $GrassDebugDistanceKillRangeCm) {
    $payload.grass_debug_distance_kill_range_cm = ConvertTo-DoubleValue $GrassDebugDistanceKillRangeCm
}

if ($GrassFarRootLiftColorValues.Count -ge 3) {
    $payload.grass_far_root_lift_color = @($GrassFarRootLiftColorValues)
}

if ($null -ne $GrassFarRootLiftStartCm) {
    $payload.grass_far_root_lift_start_cm = ConvertTo-DoubleValue $GrassFarRootLiftStartCm
}

if ($null -ne $GrassFarRootLiftRangeCm) {
    $payload.grass_far_root_lift_range_cm = ConvertTo-DoubleValue $GrassFarRootLiftRangeCm
}

if ($null -ne $GrassFarRootLiftStrength) {
    $payload.grass_far_root_lift_strength = ConvertTo-DoubleValue $GrassFarRootLiftStrength
}

if ($null -ne $GrassShadowStrength) {
    $payload.grass_shadow_strength = ConvertTo-DoubleValue $GrassShadowStrength
}

if ($GroundBaseColorValues.Count -ge 3) {
    $payload.ground_base_color = @($GroundBaseColorValues)
}

if ($null -ne $GroundNoiseStrength) {
    $payload.ground_noise_strength = ConvertTo-DoubleValue $GroundNoiseStrength
}

if ($null -ne $GroundNoiseWorldCm) {
    $payload.ground_noise_world_cm = ConvertTo-DoubleValue $GroundNoiseWorldCm
}

if ($GroundGrassGrainDarkColorValues.Count -ge 3) {
    $payload.ground_grass_grain_dark_color = @($GroundGrassGrainDarkColorValues)
}

if ($GroundGrassGrainLightColorValues.Count -ge 3) {
    $payload.ground_grass_grain_light_color = @($GroundGrassGrainLightColorValues)
}

if ($null -ne $GroundGrassGrainStrength) {
    $payload.ground_grass_grain_strength = ConvertTo-DoubleValue $GroundGrassGrainStrength
}

if ($null -ne $GroundGrassGrainWorldCm) {
    $payload.ground_grass_grain_world_cm = ConvertTo-DoubleValue $GroundGrassGrainWorldCm
}

if ($null -ne $GroundGrassGrainFrequency) {
    $payload.ground_grass_grain_frequency = ConvertTo-DoubleValue $GroundGrassGrainFrequency
}

if ($null -ne $GroundGrassGrainFadeStartCm) {
    $payload.ground_grass_grain_fade_start_cm = ConvertTo-DoubleValue $GroundGrassGrainFadeStartCm
}

if ($null -ne $GroundGrassGrainFadeRangeCm) {
    $payload.ground_grass_grain_fade_range_cm = ConvertTo-DoubleValue $GroundGrassGrainFadeRangeCm
}

if ($null -ne $GroundGrassGrainFadeInvRange) {
    $payload.ground_grass_grain_fade_inv_range = ConvertTo-DoubleValue $GroundGrassGrainFadeInvRange
}

if ($GroundFarGrassBlendColorValues.Count -ge 3) {
    $payload.ground_far_grass_blend_color = @($GroundFarGrassBlendColorValues)
}

if ($null -ne $GroundFarGrassBlendStrength) {
    $payload.ground_far_grass_blend_strength = ConvertTo-DoubleValue $GroundFarGrassBlendStrength
}

if ($null -ne $GroundFarGrassBlendStartCm) {
    $payload.ground_far_grass_blend_start_cm = ConvertTo-DoubleValue $GroundFarGrassBlendStartCm
}

if ($null -ne $GroundFarGrassBlendRangeCm) {
    $payload.ground_far_grass_blend_range_cm = ConvertTo-DoubleValue $GroundFarGrassBlendRangeCm
}

if ($null -ne $GroundFarGrassBlendInvRange) {
    $payload.ground_far_grass_blend_inv_range = ConvertTo-DoubleValue $GroundFarGrassBlendInvRange
}

if ($null -ne $GroundGrassImpostorStrength) {
    $payload.ground_grass_impostor_strength = ConvertTo-DoubleValue $GroundGrassImpostorStrength
}

if ($null -ne $GroundGrassImpostorWorldCm) {
    $payload.ground_grass_impostor_world_cm = ConvertTo-DoubleValue $GroundGrassImpostorWorldCm
}

if ($null -ne $GroundGrassImpostorWorldXCm) {
    $payload.ground_grass_impostor_world_x_cm = ConvertTo-DoubleValue $GroundGrassImpostorWorldXCm
}

if ($null -ne $GroundGrassImpostorWorldYCm) {
    $payload.ground_grass_impostor_world_y_cm = ConvertTo-DoubleValue $GroundGrassImpostorWorldYCm
}

if ($null -ne $GroundGrassImpostorScale) {
    $payload.ground_grass_impostor_scale = ConvertTo-DoubleValue $GroundGrassImpostorScale
}

if ($null -ne $GroundGrassImpostorScaleX) {
    $payload.ground_grass_impostor_scale_x = ConvertTo-DoubleValue $GroundGrassImpostorScaleX
}

if ($null -ne $GroundGrassImpostorScaleY) {
    $payload.ground_grass_impostor_scale_y = ConvertTo-DoubleValue $GroundGrassImpostorScaleY
}

if ($null -ne $GroundGrassImpostorStartCm) {
    $payload.ground_grass_impostor_start_cm = ConvertTo-DoubleValue $GroundGrassImpostorStartCm
}

if ($null -ne $GroundGrassImpostorRangeCm) {
    $payload.ground_grass_impostor_range_cm = ConvertTo-DoubleValue $GroundGrassImpostorRangeCm
}

if ($null -ne $GroundGrassImpostorInvRange) {
    $payload.ground_grass_impostor_inv_range = ConvertTo-DoubleValue $GroundGrassImpostorInvRange
}

if ($DirtColorValues.Count -ge 3) {
    $payload.dirt_color = @($DirtColorValues)
}

if ($null -ne $DirtStrength) {
    $payload.dirt_strength = ConvertTo-DoubleValue $DirtStrength
}

if ($null -ne $DirtPatchWorldCm) {
    $payload.dirt_patch_world_cm = ConvertTo-DoubleValue $DirtPatchWorldCm
}

if ($null -ne $DirtPatchScale) {
    $payload.dirt_patch_scale = ConvertTo-DoubleValue $DirtPatchScale
}

if ($null -ne $DirtPatchThreshold) {
    $payload.dirt_patch_threshold = ConvertTo-DoubleValue $DirtPatchThreshold
}

if ($null -ne $DirtPatchContrast) {
    $payload.dirt_patch_contrast = ConvertTo-DoubleValue $DirtPatchContrast
}

if ($null -ne $DirtTextureWorldCm) {
    $payload.dirt_texture_world_cm = ConvertTo-DoubleValue $DirtTextureWorldCm
}

if ($null -ne $DirtTextureStrength) {
    $payload.dirt_texture_strength = ConvertTo-DoubleValue $DirtTextureStrength
}

if ($null -ne $DirtFadeStartCm) {
    $payload.dirt_fade_start_cm = ConvertTo-DoubleValue $DirtFadeStartCm
}

if ($null -ne $DirtFadeRangeCm) {
    $payload.dirt_fade_range_cm = ConvertTo-DoubleValue $DirtFadeRangeCm
}

if ($null -ne $DirtViewMin) {
    $payload.dirt_view_min = ConvertTo-DoubleValue $DirtViewMin
}

if ($null -ne $DirtViewScale) {
    $payload.dirt_view_scale = ConvertTo-DoubleValue $DirtViewScale
}

if ($HideGrass) {
    $payload.hide_grass = $true
}
elseif ($ShowGrass) {
    $payload.hide_grass = $false
    $payload.grass_visible = $true
}

if ($HideHills) {
    $payload.hills_visible = $false
}
elseif ($ShowHills) {
    $payload.hills_visible = $true
}

if ($CameraLocationValues.Count -ge 3) {
    $payload.camera_location = @($CameraLocationValues)
}

if ($CameraLookAtValues.Count -ge 3) {
    $payload.camera_look_at = @($CameraLookAtValues)
}

if ($null -ne $CameraFov) {
    $payload.camera_fov = ConvertTo-DoubleValue $CameraFov
}

if ($null -ne $SunPitch) {
    $payload.sun_pitch = ConvertTo-DoubleValue $SunPitch
}

if ($null -ne $SunYaw) {
    $payload.sun_yaw = ConvertTo-DoubleValue $SunYaw
}

if ($null -ne $SunIntensity) {
    $payload.sun_intensity = ConvertTo-DoubleValue $SunIntensity
}

if ($null -ne $SkyIntensity) {
    $payload.sky_intensity = ConvertTo-DoubleValue $SkyIntensity
}

if ($BloodPreview) {
    $payload.blood_preview = $true
}

if ($BloodClear) {
    $payload.blood_clear = $true
}

if ($BloodColorValues.Count -ge 3) {
    $payload.blood_color = @($BloodColorValues)
}

if ($BloodDarkColorValues.Count -ge 3) {
    $payload.blood_dark_color = @($BloodDarkColorValues)
}

if ($BloodGrassRootColorValues.Count -ge 3) {
    $payload.blood_grass_root_color = @($BloodGrassRootColorValues)
}

if ($BloodGrassColorValues.Count -ge 3) {
    $payload.blood_grass_color = @($BloodGrassColorValues)
}

if ($null -ne $BloodStrength) {
    $payload.blood_strength = ConvertTo-DoubleValue $BloodStrength
}

if ($null -ne $BloodWetStrength) {
    $payload.blood_wet_strength = ConvertTo-DoubleValue $BloodWetStrength
}

if ($null -ne $BloodGrassStrength) {
    $payload.blood_grass_strength = ConvertTo-DoubleValue $BloodGrassStrength
}

if ($null -ne $BloodRadiusScale) {
    $payload.blood_radius_scale = ConvertTo-DoubleValue $BloodRadiusScale
}

$shotPath = $null
if (-not $NoScreenshot) {
    $shotPath = Join-Path $ShotDir ($Name + ".png")
}

if ($shotPath -and -not $SkipReadyWait) {
    Wait-LivePreviewReady -Path $ReadyPath -ProcessId $PreviewPid -TimeoutSeconds $ReadyTimeoutSeconds
}

if ($shotPath -and $SettleSeconds -gt 0.0) {
    $payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
    Write-Output "Wrote live config for settle: $ConfigPath"
    Start-Sleep -Milliseconds ([Math]::Max(0, [int]($SettleSeconds * 1000.0)))
    $payload.nonce = [DateTime]::UtcNow.Ticks
    $payload.request_screenshot = $true
    $payload.screenshot_path = $shotPath
}
elseif ($shotPath) {
    $payload.request_screenshot = $true
    $payload.screenshot_path = $shotPath
}

$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8
Write-Output "Wrote live config: $ConfigPath"
if ($shotPath) {
    Write-Output "Requested screenshot: $shotPath"
}

if ($Wait -and $shotPath) {
    $deadline = (Get-Date).AddSeconds(20)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $shotPath) {
            Write-Output "Screenshot ready: $shotPath"
            break
        }
        Start-Sleep -Milliseconds 250
    }
}

if ((-not $KeepPreviewAwake) -and (Test-Path -LiteralPath $PreviewPowerScript)) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $PreviewPowerScript -Action Suspend -ProcessId $PreviewPid | Out-Null
    Write-Output "Live preview suspended. Use -KeepPreviewAwake to leave it running after a shot."
}
