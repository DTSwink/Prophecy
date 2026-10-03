param(
    [string]$Name = ("live_" + (Get-Date -Format "HHmmss")),
    [double[]]$GrassDistantColor = @(0.245, 0.470, 0.105, 1.0),
    [double]$GrassDistantStartCm = 6400.0,
    [double]$GrassDistantRangeCm = 7200.0,
    [Nullable[double]]$GrassShadowStrength = $null,
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
}

if ($GrassShadowStrength.HasValue) {
    $payload.grass_shadow_strength = $GrassShadowStrength.Value
}

$shotPath = $null
if (-not $NoScreenshot) {
    $shotPath = Join-Path $ShotDir ($Name + ".png")
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
