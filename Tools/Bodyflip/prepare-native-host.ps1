# Copy only native binaries/configuration for an isolated automation host.
# Content is read through junctions; tests must use transient worlds and assets.
param([string]$Destination = 'Saved/Diagnostics/BodyflipPort20261030/NativeHost')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$hostRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $Destination))
$ownedRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'Saved/Diagnostics/BodyflipPort20261030'))
if (-not $hostRoot.StartsWith($ownedRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The diagnostic host must remain inside BodyflipPort20261030.'
}
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'UnrealEditor*' -and $_.CommandLine -and
    ($_.CommandLine.Replace('/', '\').IndexOf($hostRoot, [StringComparison]::OrdinalIgnoreCase) -ge 0)
}
if ($running) { throw 'The Bodyflip diagnostic host is still running; do not replace its binaries.' }
New-Item -ItemType Directory -Path $hostRoot -Force | Out-Null
foreach ($folder in @('Binaries/Win64', 'Config', 'Plugins/ProphecyJolt/Binaries/Win64')) {
    New-Item -ItemType Directory -Path (Join-Path $hostRoot $folder) -Force | Out-Null
}
Copy-Item -LiteralPath (Join-Path $projectRoot 'GameAnimationSample3.uproject') -Destination $hostRoot
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'Config') -File -Filter '*.ini' |
    Copy-Item -Destination (Join-Path $hostRoot 'Config')
foreach ($pair in @(
    @('Binaries/Win64', 'Binaries/Win64'),
    @('Plugins/ProphecyJolt/Binaries/Win64', 'Plugins/ProphecyJolt/Binaries/Win64')
)) {
    Get-ChildItem -LiteralPath (Join-Path $projectRoot $pair[0]) -File |
        Where-Object { $_.Extension -in '.dll', '.modules' } |
        Copy-Item -Destination (Join-Path $hostRoot $pair[1])
}
Copy-Item -LiteralPath (Join-Path $projectRoot 'Plugins/ProphecyJolt/ProphecyJolt.uplugin') -Destination (Join-Path $hostRoot 'Plugins/ProphecyJolt')
$fixtureRelative = 'Saved/Diagnostics/BodyflipPort20261030/embedded-fixture.json'
if (Test-Path -LiteralPath (Join-Path $projectRoot $fixtureRelative)) {
    $fixtureTarget = Join-Path $hostRoot $fixtureRelative
    New-Item -ItemType Directory -Path (Split-Path $fixtureTarget) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot $fixtureRelative) -Destination $fixtureTarget
}
foreach ($relative in @('Content', 'Tools', 'Labs', 'StandaloneSim', 'Plugins/ProphecyJolt/Content', 'Plugins/ProphecyJolt/Config', 'Plugins/ProphecyJolt/Resources')) {
    $source = Join-Path $projectRoot $relative
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $target = Join-Path $hostRoot $relative
    if (Test-Path -LiteralPath $target) {
        $existing = Get-Item -LiteralPath $target
        if ($existing.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath($existing.Target) -ne [IO.Path]::GetFullPath($source)) {
            throw "Unexpected existing diagnostic link: $target"
        }
    } else {
        New-Item -ItemType Junction -Path $target -Target $source | Out-Null
    }
}
$binaries = @('Binaries/Win64', 'Plugins/ProphecyJolt/Binaries/Win64') | ForEach-Object {
    Get-ChildItem -LiteralPath (Join-Path $hostRoot $_) -File | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($hostRoot.Length + 1); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    }
}
[ordered]@{ createdUtc = [DateTime]::UtcNow.ToString('o'); source = $projectRoot; binaries = @($binaries) } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $hostRoot 'binary-receipt.json') -Encoding utf8
Write-Output (Join-Path $hostRoot 'GameAnimationSample3.uproject')
