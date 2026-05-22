param(
    [string]$Name = ("live_" + (Get-Date -Format "HHmmss")),
    [double[]]$GrassDistantColor = @(0.105, 0.245, 0.048, 1.0),
    [double]$GrassDistantStartCm = 6000.0,
    [double]$GrassDistantRangeCm = 5200.0,
    [double]$GrassDistantFlattenStartCm = 10500.0,
    [double]$GrassDistantFlattenRangeCm = 9500.0,
    [double]$GrassDistantFlattenCm = 78.0,
    [double]$GrassDistantOpacityStartCm = 15000.0,
    [double]$GrassDistantOpacityRangeCm = 7000.0,
    [Nullable[double]]$GrassShadowStrength = $null,
    [Nullable[double]]$DirtStrength = $null,
    [double]$SettleSeconds = 1.0,
    [switch]$NoScreenshot,
    [switch]$Wait
)

$ConfigPath = "$PSScriptRoot\ProphecyLiveVisual.json"
$ShotDir = "$PSScriptRoot\LiveShots"
New-Item -ItemType Directory -Path $ShotDir -Force | Out-Null

$payload = [ordered]@{
    nonce = [DateTime]::UtcNow.Ticks
    grass_distant_color = @($GrassDistantColor)
    grass_distant_color_start_cm = $GrassDistantStartCm
    grass_distant_color_range_cm = $GrassDistantRangeCm
    grass_distant_flatten_start_cm = $GrassDistantFlattenStartCm
    grass_distant_flatten_range_cm = $GrassDistantFlattenRangeCm
    grass_distant_flatten_cm = $GrassDistantFlattenCm
    grass_distant_opacity_start_cm = $GrassDistantOpacityStartCm
    grass_distant_opacity_range_cm = $GrassDistantOpacityRangeCm
}

if ($GrassShadowStrength.HasValue) {
    $payload.grass_shadow_strength = $GrassShadowStrength.Value
}

if ($DirtStrength.HasValue) {
    $payload.dirt_strength = $DirtStrength.Value
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
