<#
.SYNOPSIS
Copies a frozen current-source NN crowd snapshot. Does not build, cook or run UE.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [string]$Engine = 'C:/Program Files/Epic Games/UE_5.7',
    [string]$AssetInventory = ''
)
. (Join-Path $PSScriptRoot 'PackagedNN.Common.ps1')
Assert-NNIdle
$root = Resolve-NNAbsolute $ProjectRoot
$engineRoot = Resolve-NNAbsolute $Engine
$uproject = Join-Path $root 'GameAnimationSample3.uproject'
Assert-NNFile $uproject
if (-not $AssetInventory) { $AssetInventory = Join-Path $root 'Saved/JoltMigration/Inventory-20260909-051135/AssetManifest.json' }
$inventoryPath = Resolve-NNAbsolute $AssetInventory
# This is the source-backed retained inventory, not an unverified hand-authored dependency list.
if ((Get-NNHash $inventoryPath) -ne 'EE378BCE8F54D2371C379C876B726BEDA2569F07AD86059E3F3CF51FF3FFA20F') { throw 'Inventory changed. Review/regenerate its closure rather than silently accepting another schema.' }
$inventoryTime = (Get-Item -LiteralPath $inventoryPath).LastWriteTimeUtc
$reader = [IO.StreamReader]::new($inventoryPath)
$section = [Text.StringBuilder]::new()
$inside = $false; $closed = $false
try {
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        if (-not $inside) {
            if ($line.Trim() -eq '"packages": [') { $inside=$true; [void]$section.AppendLine('[') }
            continue
        }
        if ($line -eq ([char]9 + '],')) { [void]$section.AppendLine(']'); $closed=$true; break }
        [void]$section.AppendLine($line)
    }
} finally { $reader.Dispose() }
if (-not $closed) { throw 'Could not extract the declared package registry section.' }
$byPackage = @{}
foreach ($node in ($section.ToString() | ConvertFrom-Json)) { $byPackage[$node.package]=$node }
$roots = @('/Game/_mygame/SKM_UEFN_Mannequin','/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin')
$queue = [Collections.Generic.Queue[string]]::new()
foreach ($package in $roots) { $queue.Enqueue($package) }
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$packages = [Collections.Generic.List[string]]::new()
while ($queue.Count) {
    $name=$queue.Dequeue()
    if (-not $seen.Add($name) -or $name.StartsWith('/Script/')) { continue }
    if (-not $name.StartsWith('/Game/')) { throw "Unreviewed external mount in closure: $name" }
    if (-not $byPackage.ContainsKey($name) -or -not $byPackage[$name].registryDependencyNodeAvailable) { throw "Missing registry dependency node: $name" }
    $packages.Add($name)
    foreach ($dependency in $byPackage[$name].packageDependencies) { if ($dependency.package) { $queue.Enqueue([string]$dependency.package) } }
}
$modelNames = @('prophecy_lower_body_run_b100.onnx','prophecy_lower_body_runtime.json','prophecy_lower_body_walk_b100.onnx','prophecy_lower_body_walk_runtime.json','prophecy_upper_body_b100.onnx','prophecy_upper_body_runtime.json')
$versionPath=Join-Path $engineRoot 'Engine/Build/Build.version'
$version=Get-Content -LiteralPath $versionPath -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 7 -or $version.PatchVersion -ne 4) { throw 'This recipe is pinned to UE5.7.4.' }
foreach ($configuration in @('Development','Shipping')) { $null=Assert-NNDependency $root $configuration }
$snapshot = New-NNDirectory (Join-Path $root 'Saved/JoltMigration') 'NNCrowd'
$project = Join-Path $snapshot 'Project'
New-Item -ItemType Directory -Path $project | Out-Null
$inputs=[Collections.Generic.List[object]]::new()
$success=$false; $failure=$null
try {
    $relativeFiles=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    [void]$relativeFiles.Add('GameAnimationSample3.uproject')
    foreach ($tree in @('Source','Config','StandaloneSim/sim_core/include','Plugins/ProphecyJolt','Intermediate/JoltMigration/Install/Development','Intermediate/JoltMigration/Install/Shipping')) {
        foreach ($file in (Get-NNTreeFiles (Join-Path $root $tree))) {
            $relative=$file.FullName.Substring($root.Length+1).Replace('\','/')
            if ($tree -eq 'Plugins/ProphecyJolt' -and $relative -match '^Plugins/ProphecyJolt/(Binaries|Intermediate|Saved|\.git)/') { continue }
            [void]$relativeFiles.Add($relative)
        }
    }
    foreach ($relative in @('StandaloneSim/sim_core/src/locomotion.cpp','StandaloneSim/bridge/sim_bridge_protocol.h','Tools/Jolt/RunFoundationTests.ps1')) { [void]$relativeFiles.Add($relative) }
    foreach ($name in $modelNames) { [void]$relativeFiles.Add("Content/locomotion/NN/$name") }
    foreach ($package in $packages) {
        $stem='Content/'+$package.Substring(6)
        $main=@("$stem.uasset","$stem.umap") | Where-Object { Test-Path -LiteralPath (Join-Path $root $_) -PathType Leaf }
        if (@($main).Count -ne 1) { throw "Expected one source package for $package" }
        foreach ($relative in @($main)+@("$stem.uexp","$stem.ubulk","$stem.uptnl")) {
            $source=Join-Path $root $relative
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
            if ((Get-Item -LiteralPath $source).LastWriteTimeUtc -gt $inventoryTime) { throw "Package is newer than dependency inventory: $source" }
            [void]$relativeFiles.Add($relative)
        }
    }
    foreach ($relative in @($relativeFiles | Sort-Object)) {
        $inputs.Add((Copy-NNInput (Join-Path $root $relative) $project $relative ($relative.StartsWith('Content/'))))
    }
    # Only snapshot startup differs. Original config bytes and hashes remain recorded below.
    $engineIni=Join-Path $project 'Config/DefaultEngine.ini'
    $override=[Environment]::NewLine+'[/Script/EngineSettings.GameMapsSettings]'+[Environment]::NewLine+
        'EditorStartupMap=/Engine/Maps/Entry'+[Environment]::NewLine+'GameDefaultMap=/Engine/Maps/Entry'+[Environment]::NewLine+
        'ServerDefaultMap=/Engine/Maps/Entry'+[Environment]::NewLine+'GlobalDefaultGameMode=/Script/Engine.GameModeBase'+[Environment]::NewLine+
        'GlobalDefaultServerGameMode=/Script/Engine.GameModeBase'+[Environment]::NewLine
    [IO.File]::AppendAllText($engineIni,$override,[Text.UTF8Encoding]::new($false))
    ($inputs | Where-Object relativePath -eq 'Config/DefaultEngine.ini').snapshotSha256=Get-NNHash $engineIni
    foreach ($entry in $inputs) { if ((Get-NNHash $entry.source) -ne $entry.sourceSha256) { throw "Original input changed during snapshot: $($entry.source)" } }
    foreach ($tree in @('Source','Config','StandaloneSim/sim_core/include','Plugins/ProphecyJolt','Intermediate/JoltMigration/Install/Development','Intermediate/JoltMigration/Install/Shipping')) {
        foreach ($file in (Get-NNTreeFiles (Join-Path $root $tree))) {
            $relative=$file.FullName.Substring($root.Length+1).Replace('\','/')
            if ($tree -eq 'Plugins/ProphecyJolt' -and $relative -match '^Plugins/ProphecyJolt/(Binaries|Intermediate|Saved|\.git)/') { continue }
            if (-not $relativeFiles.Contains($relative)) { throw "Source file appeared during snapshot: $relative" }
        }
    }
    $success=$true
} catch { $failure=$_.Exception.Message }
$manifest=[ordered]@{
    schema=1;kind='ProphecyCurrentSourceNNCrowdSnapshot';success=$success;error=$failure;createdUtc=[DateTime]::UtcNow.ToString('o')
    originalProject=$uproject;projectDirectory=$project;projectFile=(Join-Path $project 'GameAnimationSample3.uproject')
    engine=$engineRoot;engineVersion=$version;engineVersionSha256=(Get-NNHash $versionPath)
    inventory=$inventoryPath;inventorySha256=(Get-NNHash $inventoryPath);gamePackageRoots=$roots;gamePackageClosure=@($packages | Sort-Object)
    engineMap='/Engine/Maps/Entry';engineMapSha256=(Get-NNHash (Join-Path $engineRoot 'Engine/Content/Maps/Entry.umap'))
    modelRelativePaths=@($modelNames | ForEach-Object { "Content/locomotion/NN/$_" });inputs=@($inputs.ToArray())
    changedSnapshotConfig='Only appended Entry/native GameMode startup override. Original source assets/config never written. Copied package files are read-only.'
    limitations='Registry closure does not discover arbitrary future string/config/plugin loads. Normal cooker references remain enabled; any missing-package diagnostic requires review. Runtime 22/21/88/model/query gates remain mandatory.'
}
$manifestPath=Join-Path $snapshot 'snapshot.json'
Write-NNJson $manifestPath $manifest
if (-not $success) { throw "Snapshot failed: $failure See $manifestPath" }
[pscustomobject]@{Snapshot=$manifestPath;Project=$project;Packages=$packages.Count;Files=$inputs.Count}
