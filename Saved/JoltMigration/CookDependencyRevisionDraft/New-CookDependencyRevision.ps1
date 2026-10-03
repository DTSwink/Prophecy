<#
.SYNOPSIS
DRAFT FOR ROOT REVIEW. Adds only freshly audited /Game package dependencies to the
owned r2 project and writes a create-new sibling r3 manifest. Does not run UE/build.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Snapshot,
    [Parameter(Mandatory=$true)][string]$FreshRegistry,
    [Parameter(Mandatory=$true)][string]$FailedPackage,
    [string]$NewManifestName = 'snapshot-r3.json'
)
. (Join-Path $PSScriptRoot '../PackagedNNCrowdDraft/PackagedNN.Common.ps1')
Assert-NNIdle
# No copying while the owner has a build/cook worker active, including a detached UAT.
$workers = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('UnrealBuildTool.exe','AutomationTool.exe','cl.exe','link.exe') -or
    ($_.Name -eq 'dotnet.exe' -and $_.CommandLine -match '(UnrealBuildTool|AutomationTool)')
})
if ($workers.Count) { throw 'A UE build worker is active; finish it before revising snapshot inputs.' }
$manifestPath = Resolve-NNAbsolute $Snapshot
$oldHash = Get-NNHash $manifestPath
$data = Read-NNSnapshot $manifestPath
if ($data.revision.number -ne 2) { throw 'This bounded revision expects the reviewed r2 snapshot.' }
$project = Resolve-NNAbsolute $data.projectDirectory
$original = Split-Path -Parent (Resolve-NNAbsolute $data.originalProject)
$registryPath = Resolve-NNAbsolute $FreshRegistry
$registryHash = Get-NNHash $registryPath
$registry = Get-Content -LiteralPath $registryPath -Raw | ConvertFrom-Json
if ($registry.kind -ne 'ProphecyFreshCookRegistry' -or $registry.schema -ne 1 -or -not $registry.success -or
    -not $registry.sourceHashesAndTimestampsUnchanged -or $registry.assetsLoadedOrSavedByExporter -or
    (Resolve-NNAbsolute $registry.projectDirectory) -ne $original -or $registry.engineVersion -notlike '5.7.4-*') {
    throw 'Fresh registry report does not match the original UE5.7.4 project and read-only export contract.'
}
$failedPath = Resolve-NNAbsolute $FailedPackage
$failedHash = Get-NNHash $failedPath
$failed = Get-Content -LiteralPath $failedPath -Raw | ConvertFrom-Json
if ($failed.kind -ne 'ProphecyPackagedNNCrowd' -or $failed.success -or $failed.snapshotSha256 -ne $oldHash) {
    throw 'Failure report is not the recorded failed r2 package.'
}
if ($NewManifestName -ne 'snapshot-r3.json') { throw 'Only the reviewed create-new r3 filename is allowed.' }
$newPath = Join-Path (Split-Path -Parent $manifestPath) $NewManifestName
if (Test-Path -LiteralPath $newPath) { throw "Revision already exists: $newPath" }
$roots = @($data.gamePackageRoots) + @(
    '/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface',
    '/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle',
    '/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest',
    '/Game/_mygame/blood2/MI_blooddecal',
    '/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop',
    '/Game/Input/TIS_MobileControls'
)
if (@(Compare-Object @($roots | Sort-Object) @($registry.rootPackages | Sort-Object)).Count) { throw 'Unexpected fresh-registry root set.' }
$byPackage = @{}
foreach ($node in $registry.packages) {
    if ($byPackage.ContainsKey($node.package)) { throw 'Duplicate package node.' }
    $byPackage[$node.package] = $node
}
$queue = [Collections.Generic.Queue[string]]::new()
foreach ($name in $roots) { $queue.Enqueue($name) }
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
while ($queue.Count) {
    $name = $queue.Dequeue()
    if ($name.StartsWith('/Script/') -or -not $seen.Add($name)) { continue }
    if (-not $byPackage.ContainsKey($name) -or -not $byPackage[$name].registryDependencyNodeAvailable) { throw "Missing freshly scanned dependency node: $name" }
    foreach ($edge in $byPackage[$name].packageDependencies) { $queue.Enqueue([string]$edge.package) }
}
if ($seen.Count -ne $registry.packageCount -or $seen.Count -ne $byPackage.Count -or $seen.Count -gt 5000) { throw 'Fresh registry has unexpected graph coverage.' }
$game = @($seen | Where-Object { $_.StartsWith('/Game/') } | Sort-Object)
if (@(Compare-Object $game @($registry.gamePackageClosure | Sort-Object)).Count) { throw 'Fresh full /Game closure differs from independently walked graph.' }
$runtime = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($name in $roots) { $queue.Enqueue($name) }
while ($queue.Count) {
    $name = $queue.Dequeue()
    if ($name.StartsWith('/Script/') -or -not $runtime.Add($name)) { continue }
    foreach ($edge in $byPackage[$name].packageDependencies) { if ($edge.game) { $queue.Enqueue([string]$edge.package) } }
}
$runtimeGame = @($runtime | Where-Object { $_.StartsWith('/Game/') } | Sort-Object)
$runtimeExternal = @($runtime | Where-Object { -not $_.StartsWith('/Game/') } | Sort-Object)
if (@(Compare-Object $runtimeGame @($registry.runtimeGamePackageClosure | Sort-Object)).Count -or
    @(Compare-Object $runtimeExternal @($registry.runtimeExternalPackageClosure | Sort-Object)).Count) { throw 'Fresh runtime closure differs from independently walked game-reference graph.' }
$inputs = [Collections.Generic.List[object]]::new()
$byRelative = @{}
foreach ($entry in $data.inputs) { $inputs.Add($entry); $byRelative[$entry.relativePath] = $entry }
$toCopy = [Collections.Generic.List[object]]::new()
$external = [Collections.Generic.List[object]]::new()
$freshFileKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($file in $registry.files) {
    $source = Resolve-NNAbsolute $file.path
    if (-not $freshFileKeys.Add($source)) { throw "Duplicate fresh input: $source" }
    if (-not $seen.Contains([string]$file.package)) { throw "Fresh source outside graph: $source" }
    if ((Get-NNHash $source) -ne $file.sha256 -or (Get-Item -LiteralPath $source).Length -ne $file.bytes) { throw "Fresh source changed: $source" }
    if ($file.package.StartsWith('/Game/')) {
        $stem = 'Content/' + $file.package.Substring(6)
        $extension = [IO.Path]::GetExtension($source)
        if ($extension -notin @('.uasset','.umap','.uexp','.ubulk','.uptnl')) { throw 'Unexpected package sidecar extension.' }
        $relative = $stem + $extension
        $expected = [IO.Path]::GetFullPath((Join-Path $original $relative))
        if ($source -ne $expected) { throw "Game package path mismatch: $source" }
        $target = [IO.Path]::GetFullPath((Join-Path $project $relative))
        if (-not $target.StartsWith($project + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Destination escaped owned Project.' }
        if ($byRelative.ContainsKey($relative)) {
            if ($byRelative[$relative].sourceSha256 -ne $file.sha256 -or $byRelative[$relative].snapshotSha256 -ne $file.sha256) { throw "Existing frozen package differs from fresh source: $relative" }
        } else {
            if (Test-Path -LiteralPath $target) { throw "Unrecorded package already exists in snapshot: $target" }
            $toCopy.Add([pscustomobject]@{source=$source; relative=$relative; sha256=$file.sha256; bytes=$file.bytes})
        }
    } else { $external.Add($file) }
}
foreach ($name in $game) {
    $mains = @($registry.files | Where-Object { $_.package -eq $name -and [IO.Path]::GetExtension($_.path) -in @('.uasset','.umap') })
    if ($mains.Count -ne 1) { throw "Expected one fresh main package: $name" }
}
# Preserve historical bytes. Unlike r1->r2, adding inputs does not invalidate the
# old input hashes; r2 still describes only its incomplete historical cook set.
$provenance = [ordered]@{
    number=3; predecessor=$manifestPath; predecessorSha256=$oldHash
    supersedesFailedPackage=$failedPath; failedPackageSha256=$failedHash
    previousInventory=$data.inventory; previousInventorySha256=$data.inventorySha256
    reason='R2 cook identified five native constructor asset loads and the configured touch interface outside its original two-root closure. Copy complete freshly scanned hard/soft game/editor closure; require cooked outputs for the independently walked Game-edge closure. Normal UE cooking excludes editor-only soft references and strips editor-only objects.'
    freshRegistry=$registryPath; freshRegistrySha256=$registryHash
    addedRelativePaths=@($toCopy | ForEach-Object relative)
    additionalBytes=($toCopy | Measure-Object -Property bytes -Sum).Sum
    scope='Same owned Project reuses build outputs. Original r2 manifest, failed package and logs remain unchanged historical evidence. Source/config/model/runtime code bytes are preserved. Only new read-only Content copies and a new sibling manifest are written.'
}
$mutationStarted=$false
try {
    foreach ($file in $toCopy) {
        $mutationStarted=$true
        $entry = Copy-NNInput $file.source $project $file.relative $true
        if ($entry.sourceSha256 -ne $file.sha256) { throw "Source changed after audit: $($file.source)" }
        $inputs.Add($entry)
    }
    foreach ($entry in $inputs) {
        if ((Get-NNHash (Join-Path $project $entry.relativePath)) -ne $entry.snapshotSha256) { throw "Resulting input changed: $($entry.relativePath)" }
    }
    foreach ($file in $registry.files) {
        if ((Get-NNHash $file.path) -ne $file.sha256) { throw "Source changed during copying: $($file.path)" }
    }
    if ((Get-NNHash $manifestPath) -ne $oldHash -or (Get-NNHash $failedPath) -ne $failedHash -or (Get-NNHash $registryPath) -ne $registryHash) { throw 'Provenance bytes changed during revision.' }
    $data.createdUtc=[DateTime]::UtcNow.ToString('o')
    $data.inventory=$registryPath; $data.inventorySha256=$registryHash
    $data.gamePackageRoots=$roots; $data.gamePackageClosure=$game
    $data.inputs=@($inputs.ToArray() | Sort-Object relativePath)
    $data.revision=$provenance
    $data | Add-Member -NotePropertyName externalPackageClosure -NotePropertyValue @($registry.externalPackageClosure)
    $data | Add-Member -NotePropertyName externalPackageInputs -NotePropertyValue @($external.ToArray())
    $data | Add-Member -NotePropertyName requiredCookedGamePackages -NotePropertyValue $runtimeGame
    $data | Add-Member -NotePropertyName requiredCookedExternalPackages -NotePropertyValue $runtimeExternal
    $data | Add-Member -NotePropertyName dependencyInventoryKind -NotePropertyValue 'ProphecyFreshCookRegistry: full hard/soft game/editor graph; script edges recorded but not content files'
    Write-NNJson $newPath $data
    $null=Read-NNSnapshot $newPath
} catch {
    if ($mutationStarted) {
        $failurePath=Join-Path (Split-Path -Parent $manifestPath) ('snapshot-r3-incomplete-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') + '.json')
        Write-NNJson $failurePath ([ordered]@{success=$false; error=$_.Exception.Message; revision=$provenance; copiedInputs=@($inputs.ToArray()); note='Do not rerun blindly; inspect which new Content inputs were copied. Old manifests were not modified.'})
    }
    throw
}
[pscustomobject]@{Snapshot=$newPath; AddedFiles=$toCopy.Count; Packages=$game.Count; Files=$inputs.Count; AdditionalBytes=$provenance.additionalBytes}
