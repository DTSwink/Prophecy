param(
    [string]$Name = ("live_" + (Get-Date -Format "HHmmss")),
    [object[]]$GrassDistantColor = @(),
    [double]$GrassDistantStartCm = 6000.0,
    [double]$GrassDistantRangeCm = 5200.0,
    [double]$GrassDistantFlattenStartCm = 10500.0,
    [double]$GrassDistantFlattenRangeCm = 9500.0,
    [double]$GrassDistantFlattenCm = 78.0,
    [double]$GrassDistantOpacityStartCm = 15000.0,
    [double]$GrassDistantOpacityRangeCm = 7000.0,
    [object[]]$GroundBaseColor = @(),
    [object]$GroundNoiseStrength = $null,
    [object]$GroundNoiseWorldCm = $null,
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
    [int]$PreviewPid = 0,
    [switch]$KeepPreviewAwake,
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
$GroundBaseColorValues = ConvertTo-DoubleArray $GroundBaseColor
$DirtColorValues = ConvertTo-DoubleArray $DirtColor
$BloodColorValues = ConvertTo-DoubleArray $BloodColor
$BloodDarkColorValues = ConvertTo-DoubleArray $BloodDarkColor
$BloodGrassRootColorValues = ConvertTo-DoubleArray $BloodGrassRootColor
$BloodGrassColorValues = ConvertTo-DoubleArray $BloodGrassColor
$CameraLocationValues = ConvertTo-DoubleArray $CameraLocation
$CameraLookAtValues = ConvertTo-DoubleArray $CameraLookAt

$ConfigPath = "$PSScriptRoot\ProphecyLiveVisual.json"
$ShotDir = "$PSScriptRoot\LiveShots"
New-Item -ItemType Directory -Path $ShotDir -Force | Out-Null

$payload = [ordered]@{
    nonce = [DateTime]::UtcNow.Ticks
    grass_distant_color_start_cm = $GrassDistantStartCm
    grass_distant_color_range_cm = $GrassDistantRangeCm
    grass_distant_flatten_start_cm = $GrassDistantFlattenStartCm
    grass_distant_flatten_range_cm = $GrassDistantFlattenRangeCm
    grass_distant_flatten_cm = $GrassDistantFlattenCm
    grass_distant_opacity_start_cm = $GrassDistantOpacityStartCm
    grass_distant_opacity_range_cm = $GrassDistantOpacityRangeCm
}

if ($GrassDistantColorValues.Count -ge 3) {
    $payload.grass_distant_color = @($GrassDistantColorValues)
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
