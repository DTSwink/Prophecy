Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-NNFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing required file: $Path" }
}
function Resolve-NNAbsolute([string]$Path) {
    if ($Path -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])' -or $Path -match '["\r\n]') { throw "Expected a quoted-safe absolute Windows path: $Path" }
    return (Resolve-Path -LiteralPath $Path).ProviderPath
}
function Assert-NNIdle {
    $running = @(Get-Process | Where-Object { $_.ProcessName -in @('UnrealEditor','UnrealEditor-Cmd') -or $_.ProcessName -match '^(GameAnimationSample3|ProphecyJoltSmokeHost)(-Win64-[A-Za-z]+)?$' })
    if ($running.Count) { throw "A UE editor/game is running; nothing will be closed: $(($running | ForEach-Object { "$($_.ProcessName):$($_.Id)" }) -join ', ')" }
}
function Write-NNJson([string]$Path, $Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 40))
    $stream = [IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
}
function New-NNDirectory([string]$Parent,[string]$Prefix) {
    [IO.Directory]::CreateDirectory($Parent) | Out-Null
    $path = Join-Path $Parent ($Prefix + '-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $path | Out-Null
    return $path
}
function Get-NNHash([string]$Path) { Assert-NNFile $Path; return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
function Get-NNTreeFiles([string]$Directory) {
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { throw "Required directory missing: $Directory" }
    $all = @(Get-ChildItem -LiteralPath $Directory -Recurse -Force)
    if (@($all | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Reparse points require explicit review: $Directory" }
    return @($all | Where-Object { -not $_.PSIsContainer } | Sort-Object FullName)
}
function Copy-NNInput([string]$Source,[string]$Project,[string]$Relative,[bool]$ReadOnly = $false) {
    Assert-NNFile $Source
    if ($Relative -match '(^|[\\/])\.\.([\\/]|$)' -or [IO.Path]::IsPathRooted($Relative)) { throw "Unsafe snapshot-relative path: $Relative" }
    $sourceHash = Get-NNHash $Source
    $target = Join-Path $Project $Relative
    if (Test-Path -LiteralPath $target) { throw "Snapshot input already exists: $target" }
    [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $target
    $snapshotHash = Get-NNHash $target
    if ($snapshotHash -ne $sourceHash -or (Get-NNHash $Source) -ne $sourceHash) { throw "Input changed during copy: $Source" }
    if ($ReadOnly) { (Get-Item -LiteralPath $target).IsReadOnly = $true }
    return [pscustomobject]@{ relativePath=$Relative.Replace('\','/'); source=$Source; bytes=(Get-Item -LiteralPath $Source).Length; sourceLastWriteUtc=(Get-Item -LiteralPath $Source).LastWriteTimeUtc.ToString('o'); sourceSha256=$sourceHash; snapshotSha256=$snapshotHash; readOnlyCopy=$ReadOnly }
}
function Read-NNSnapshot([string]$Manifest) {
    $resolved = Resolve-NNAbsolute $Manifest
    $data = Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
    if ($data.kind -ne 'ProphecyCurrentSourceNNCrowdSnapshot' -or $data.schema -ne 1 -or -not $data.success) { throw 'Not a successful owned NN snapshot manifest.' }
    $project = Resolve-NNAbsolute $data.projectDirectory
    if ((Split-Path -Parent $resolved) -ne (Split-Path -Parent $project) -or (Split-Path -Leaf $project) -ne 'Project') { throw 'Snapshot ownership/path mismatch.' }
    foreach ($entry in $data.inputs) {
        if ($entry.relativePath -match '(^|[\\/])\.\.([\\/]|$)' -or [IO.Path]::IsPathRooted($entry.relativePath)) { throw 'Invalid manifest path.' }
        if ((Get-NNHash (Join-Path $project $entry.relativePath)) -ne $entry.snapshotSha256) { throw "Snapshot input changed: $($entry.relativePath)" }
    }
    return $data
}
function Assert-NNDependency([string]$Project,[string]$Configuration) {
    $install = Join-Path $Project "Intermediate/JoltMigration/Install/$Configuration"
    $path = Join-Path $install 'manifest.json'
    $data = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($data.schema -ne 2 -or $data.sourceSha -ne 'e77f175595e64cb44218cc9d9d56fc365ad0e36a' -or $data.version -ne '5.6.0' -or $data.configuration -ne $Configuration -or $data.simd -ne 'SSE2' -or $data.runtime -ne 'MD' -or $data.library -ne 'shared' -or $data.worldPrecision -ne 'double' -or $data.floatingPoint -ne 'precise' -or -not $data.cppExceptions -or -not $data.objectStream -or $data.assertions -ne ($Configuration -eq 'Development') -or $data.debugRenderer -or $data.profiler -or $data.crossPlatformDeterministic) { throw "Unexpected native dependency contract: $path" }
    if ($data.dllFilename -ne "ProphecyJolt_5_6_$Configuration.dll" -or $data.importLibraryFilename -ne "ProphecyJolt_5_6_$Configuration.lib") { throw 'Dependency filenames do not match configuration.' }
    if ((Get-NNHash (Join-Path $install "bin/$($data.dllFilename)")) -ne $data.dllSha256 -or (Get-NNHash (Join-Path $install "lib/$($data.importLibraryFilename)")) -ne $data.importLibrarySha256) { throw 'Dependency hashes disagree with manifest.' }
    return $data
}
