$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/PackagedNN.Common.ps1')
Assert-NNIdle
$generatedRoot = [IO.Path]::GetFullPath('C:/Users/singerie/.codex/tmp/ProphecyJolt')
$oldPackageRoot = Join-Path $generatedRoot 'NNPkg-Development-20260909-182138-994'
$failedPackageRoot = Join-Path $generatedRoot 'NNPkg-Shipping-20260909-184041-911'
$archiveRoot = Join-Path $PSScriptRoot 'PackagedCrashSymbolizationDraft/R3RuntimeArchive'
$cleanupRecord = Join-Path $PSScriptRoot 'SupersededPackageCleanup-20260909.json'
if (Test-Path -LiteralPath $cleanupRecord) { throw 'Cleanup record already exists.' }
function Assert-OwnedPath([string]$Target, [string]$ExpectedRoot) {
    $resolved = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Target).Path)
    $root = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $ExpectedRoot).Path)
    if (-not $resolved.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Target escapes owned root: $resolved" }
    $cursor = Get-Item -LiteralPath $resolved
    while ($null -ne $cursor) {
        if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse ancestor: $($cursor.FullName)" }
        $cursor = if ($cursor -is [IO.FileInfo]) { $cursor.Directory } else { $cursor.Parent }
    }
    if (@(Get-ChildItem -LiteralPath $resolved -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Reparse descendant: $resolved" }
    return $resolved
}
foreach ($packageRoot in @($oldPackageRoot, $failedPackageRoot)) {
    $owner = Get-Content -LiteralPath (Join-Path $packageRoot 'ownership.json') -Raw | ConvertFrom-Json
    if ($owner.kind -ne 'ProphecyPackagedNNShortOutputs') { throw 'Unexpected output ownership.' }
    $manifestHash = (Get-FileHash -LiteralPath $owner.snapshot -Algorithm SHA256).Hash
    if ($manifestHash -ne $owner.snapshotSha256) { throw 'Historical snapshot identity changed.' }
    if ([IO.Path]::GetFullPath($owner.cookOutputDirectory) -ne (Join-Path $packageRoot 'Cook/Windows') -or
        [IO.Path]::GetFullPath($owner.stage) -ne (Join-Path $packageRoot 'Stage')) { throw 'Unexpected output paths.' }
}
$oldExe = Join-Path $oldPackageRoot 'Stage/Windows/GameAnimationSample3/Binaries/Win64/GameAnimationSample3.exe'
$oldCrashes = Join-Path $oldPackageRoot 'Stage/Windows/GameAnimationSample3/Saved/Crashes'
$null = Assert-OwnedPath $oldExe $oldPackageRoot
$null = Assert-OwnedPath $oldCrashes $oldPackageRoot
if ((Get-FileHash -LiteralPath $oldExe -Algorithm SHA256).Hash -ne '6D6E1F3657E17FC85FD15AA869FD41776EB739AF98AD413E7D30668907314559') { throw 'R3 crash image hash differs.' }
New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
$archiveInputs = @((Get-Item -LiteralPath $oldExe)) + @(Get-ChildItem -LiteralPath $oldCrashes -Recurse -File)
$preserved = @()
foreach ($inputFile in $archiveInputs) {
    $relative = if ($inputFile.FullName -eq $oldExe) { 'GameAnimationSample3-r3.exe' } else { 'Crashes/' + $inputFile.FullName.Substring($oldCrashes.Length + 1) }
    $destination = Join-Path $archiveRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    $before = (Get-FileHash -LiteralPath $inputFile.FullName -Algorithm SHA256).Hash
    if (-not (Test-Path -LiteralPath $destination)) { Copy-Item -LiteralPath $inputFile.FullName -Destination $destination }
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $before) { throw 'Crash evidence archive differs.' }
    $preserved += [pscustomobject]@{ source=$inputFile.FullName; archive=$destination; sha256=$before; bytes=$inputFile.Length }
}
$targets = @(
    (Join-Path $oldPackageRoot 'Cook'),
    (Join-Path $oldPackageRoot 'Stage'),
    (Join-Path $failedPackageRoot 'Cook')
)
$failedStage = Join-Path $failedPackageRoot 'Stage'
if (Test-Path -LiteralPath $failedStage) { $targets += $failedStage }
$verifiedTargets = @()
foreach ($target in $targets) {
    $resolved = Assert-OwnedPath $target $generatedRoot
    $files = @(Get-ChildItem -LiteralPath $resolved -Recurse -File -Force)
    $logicalBytes = 0L
    foreach ($file in $files) { $logicalBytes += $file.Length }
    $verifiedTargets += [pscustomobject]@{ path=$resolved; fileCount=$files.Count; logicalBytes=$logicalBytes }
}
$record = [ordered]@{ status='prepared'; createdUtc=[DateTime]::UtcNow.ToString('o'); authorization='User explicitly requested deleting generated junk after freeing storage.'; scope='Only superseded R3 Cook/Stage and failed R4 Shipping Cook/Stage. Logs, manifests, source archives, R3 crash image/minidump and matching PDB retained. Current R4 Development controls retained.'; preserved=$preserved; targets=$verifiedTargets; freeBefore=(Get-PSDrive C).Free }
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $cleanupRecord -Encoding utf8
foreach ($target in $verifiedTargets) {
    $null = Assert-OwnedPath $target.path $generatedRoot
    Remove-Item -LiteralPath $target.path -Recurse -Force
    if (Test-Path -LiteralPath $target.path) { throw 'Superseded output remains.' }
}
$record.status='complete'
$record.freeAfter=(Get-PSDrive C).Free
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $cleanupRecord -Encoding utf8
$record | ConvertTo-Json -Depth 4
