[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('SSE2_PRIVATE', 'AVX2_PRIVATE')]
    [string]$GameProfile,
    [Parameter(Mandatory = $true)]
    [string]$Label,
    [ValidateRange(2, 100)][int]$Count = 100,
    [ValidateRange(30, 10000)][int]$Warmup = 60,
    [ValidateRange(2, 10000)][int]$Samples = 360,
    [ValidateRange(0, 32)][int]$JoltWorkerThreads = 7,
    [double]$QueryTreePaddingCm = 40.0,
    [switch]$DuringPhysics,
    [switch]$SerialCompose,
    [switch]$PClassGameThread,
    [switch]$NoLockIdleReads,
    [switch]$PauseChaos,
    [ValidateSet('Original', 'PreparedSerial', 'PreparedParallel')][string]$FeedbackMode = 'Original',
    [ValidateSet('BelowNormal', 'Normal')][string]$ProcessPriority = 'Normal',
    [string]$Engine = 'C:/Program Files/Epic Games/UE_5.7'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-GamePeImports {
    param([Parameter(Mandatory = $true)][string]$Path)
    # Read-only PE import names, without loading any target DLL or depending on
    # a compiler tool's localized output. Only x64 PE32+ modules are accepted.
    $peBytes = [IO.File]::ReadAllBytes($Path)
    $read16 = {
        param([long]$Offset)
        if ($Offset -lt 0 -or $Offset + 2 -gt $peBytes.Length) { throw "Truncated PE: $Path" }
        [BitConverter]::ToUInt16($peBytes, [int]$Offset)
    }
    $read32 = {
        param([long]$Offset)
        if ($Offset -lt 0 -or $Offset + 4 -gt $peBytes.Length) { throw "Truncated PE: $Path" }
        [BitConverter]::ToUInt32($peBytes, [int]$Offset)
    }
    if ((& $read16 0) -ne 0x5a4d) { throw "Not a PE image: $Path" }
    $peOffset = [long](& $read32 0x3c)
    if ((& $read32 $peOffset) -ne 0x4550 -or (& $read16 ($peOffset + 4)) -ne 0x8664) {
        throw "Not an x64 PE image: $Path"
    }
    $sectionCount = & $read16 ($peOffset + 6)
    $optionalSize = & $read16 ($peOffset + 20)
    $optionalOffset = $peOffset + 24
    if ((& $read16 $optionalOffset) -ne 0x20b -or $optionalSize -lt 128 -or $sectionCount -gt 96) {
        throw "Unsupported PE header: $Path"
    }
    $sizeOfHeaders = & $read32 ($optionalOffset + 60)
    $importRva = & $read32 ($optionalOffset + 120)
    $importSize = & $read32 ($optionalOffset + 124)
    if ($importRva -eq 0) { return }
    $sections = @()
    for ($sectionIndex = 0; $sectionIndex -lt $sectionCount; ++$sectionIndex) {
        $sectionOffset = $optionalOffset + $optionalSize + 40 * $sectionIndex
        $sections += [pscustomobject]@{
            VirtualSize = (& $read32 ($sectionOffset + 8))
            VirtualAddress = (& $read32 ($sectionOffset + 12))
            RawSize = (& $read32 ($sectionOffset + 16))
            RawOffset = (& $read32 ($sectionOffset + 20))
        }
    }
    $resolveRva = {
        param([long]$Rva)
        if ($Rva -lt $sizeOfHeaders -and $Rva -lt $peBytes.Length) { return $Rva }
        foreach ($section in $sections) {
            $relative = $Rva - [long]$section.VirtualAddress
            if ($relative -ge 0 -and $relative -lt [long]$section.RawSize) {
                $offset = [long]$section.RawOffset + $relative
                if ($offset -ge $peBytes.Length) { throw "PE RVA outside file: $Path" }
                return $offset
            }
        }
        throw "Unmapped PE RVA: $Path"
    }
    $limit = [Math]::Min(2048, [int]([long]$importSize / 20))
    for ($descriptorIndex = 0; $descriptorIndex -lt $limit; ++$descriptorIndex) {
        $descriptor = & $resolveRva ([long]$importRva + 20 * $descriptorIndex)
        $nameRva = & $read32 ($descriptor + 12)
        if ($nameRva -eq 0) { return }
        $nameOffset = & $resolveRva $nameRva
        $nameLength = 0
        while ($nameLength -lt 512 -and $nameOffset + $nameLength -lt $peBytes.Length -and $peBytes[$nameOffset + $nameLength] -ne 0) {
            ++$nameLength
        }
        if ($nameLength -eq 512 -or $nameOffset + $nameLength -ge $peBytes.Length) { throw "Invalid PE import name: $Path" }
        [Text.Encoding]::ASCII.GetString($peBytes, [int]$nameOffset, $nameLength)
    }
    throw "PE import descriptors did not terminate: $Path"
}

function Get-GameFileIdentity {
    param([Parameter(Mandatory = $true)][string]$Path)
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) { throw "Expected a file: $Path" }
    [ordered]@{ path = $item.FullName; bytes = $item.Length; sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash }
}

if ($Label -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Label must contain only letters, digits, underscores or hyphens.' }
if ([double]::IsNaN($QueryTreePaddingCm) -or [double]::IsInfinity($QueryTreePaddingCm) -or $QueryTreePaddingCm -lt 0 -or $QueryTreePaddingCm -gt 1000) {
    throw 'QueryTreePaddingCm must be finite and between 0 and 1000.'
}
if (@(Get-Process -Name UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'An editor is already running. This launcher does not stop existing processes.'
}
$gameProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$gameDllPath = Join-Path $gameProjectRoot 'Binaries/Win64/UnrealEditor-GameAnimationSample3.dll'
$consumerDllPath = Join-Path $gameProjectRoot 'Plugins/ProphecyJolt/Binaries/Win64/UnrealEditor-ProphecyJolt.dll'
$nativeManifestPath = Join-Path $gameProjectRoot 'Intermediate/JoltMigration/Install/Development/manifest.json'
$nativeManifest = Get-Content -LiteralPath $nativeManifestPath -Raw | ConvertFrom-Json
if ($nativeManifest.schema -ne 2 -or $nativeManifest.simd -ne 'SSE2' -or $nativeManifest.version -ne '5.6.0' -or
    $nativeManifest.sourceSha -ne 'e77f175595e64cb44218cc9d9d56fc365ad0e36a' -or
    $nativeManifest.configuration -ne 'Development' -or $nativeManifest.dllFilename -ne 'ProphecyJolt_5_6_Development.dll' -or
    $nativeManifest.worldPrecision -ne 'double' -or -not $nativeManifest.assertions) {
    throw 'This game-module-only diagnostic requires the retained Development SSE2 native Jolt manifest.'
}
$nativeDllPath = Join-Path $gameProjectRoot ('Plugins/ProphecyJolt/Binaries/Win64/' + $nativeManifest.dllFilename)
$nativeIdentity = Get-GameFileIdentity $nativeDllPath
if ($nativeIdentity.sha256 -ne $nativeManifest.dllSha256) { throw 'Staged native Jolt DLL does not match the SSE2 manifest.' }
$consumerImports = @(Get-GamePeImports $consumerDllPath | Where-Object { $_ -match '^ProphecyJolt_5_6_.*\.dll$' })
if ($consumerImports.Count -ne 1 -or $consumerImports[0] -ne $nativeManifest.dllFilename) {
    throw 'The actual Unreal Jolt consumer is not importing the expected SSE2 native DLL. Rebuild/restore the consumer before launch.'
}
$gameImports = @(Get-GamePeImports $gameDllPath)
if ($gameImports -notcontains 'UnrealEditor-ProphecyJolt.dll') { throw 'The game DLL does not import the expected native-owner module.' }

# Reuse the existing baseline instruction probe without modifying it. Its
# original AVX2_FMA_PRECISE label belongs to that probe, not this game's FP mode.
$probeInstall = Join-Path $gameProjectRoot 'Intermediate/JoltMigration/Install/AVX2/Development'
$probeManifestPath = Join-Path $probeInstall 'manifest.json'
$probeManifest = Get-Content -LiteralPath $probeManifestPath -Raw | ConvertFrom-Json
$probePath = Join-Path $probeInstall 'tools/ProphecyJoltCpuPreflight.exe'
$probeIdentity = Get-GameFileIdentity $probePath
if ($probeManifest.schema -ne 3 -or $probeManifest.instructionMask -ne 2015 -or $probeIdentity.sha256 -ne $probeManifest.cpuPreflightSha256) {
    throw 'Baseline CPU probe does not match its retained build manifest.'
}
$reportDirectory = Join-Path $gameProjectRoot 'Saved/JoltMigration'
[IO.Directory]::CreateDirectory($reportDirectory) | Out-Null
$sidecarPath = Join-Path $reportDirectory ($Label + '.game-simd.cpu.json')
$benchmarkPath = Join-Path $gameProjectRoot ('Saved/Benchmarks/' + $Label + '.json')
if ((Test-Path -LiteralPath $sidecarPath) -or (Test-Path -LiteralPath $benchmarkPath)) { throw 'Output label is already in use.' }
$probeLines = @(& $probePath)
$probeExit = $LASTEXITCODE
$probeResult = ($probeLines -join [Environment]::NewLine) | ConvertFrom-Json
$accepted = $probeExit -eq 0 -and $probeResult.supported -and $probeResult.baseline_probe -and
    $probeResult.required_instruction_mask -eq 2015 -and $probeResult.supported_instruction_mask -eq 2015 -and
    $probeResult.missing_instruction_mask -eq 0 -and $probeResult.popcnt -and $probeResult.xsave -and
    $probeResult.osxsave -and $probeResult.avx_os_context -and (($probeResult.xcr0 -band 6) -eq 6)
$record = [ordered]@{
    schema = 1; timestampUtc = [DateTime]::UtcNow.ToString('o'); accepted = [bool]$accepted
    kind = 'game_module_isa_diagnostic'; expectedGameProfile = $GameProfile
    gameModule = (Get-GameFileIdentity $gameDllPath)
    joltUnrealModule = (Get-GameFileIdentity $consumerDllPath)
    joltNativeProfile = 'SSE2'; joltNative = $nativeIdentity; joltNativeImportedFilename = $consumerImports[0]
    joltManifest = (Get-GameFileIdentity $nativeManifestPath)
    cpuProbe = $probeIdentity; cpuProbeBuildManifest = (Get-GameFileIdentity $probeManifestPath)
    cpuProbeExitCode = $probeExit; cpu = $probeResult
    engineExecutable = (Get-GameFileIdentity (Join-Path $Engine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'))
    engineCoreModule = (Get-GameFileIdentity (Join-Path $Engine 'Engine/Binaries/Win64/UnrealEditor-Core.dll'))
    engineRuntimeModule = (Get-GameFileIdentity (Join-Path $Engine 'Engine/Binaries/Win64/UnrealEditor-Engine.dll'))
    ortNative = (Get-GameFileIdentity (Join-Path $Engine 'Engine/Plugins/NNE/NNERuntimeORT/Binaries/ThirdParty/Onnxruntime/Win64/onnxruntime.dll'))
    benchmarkReport = $benchmarkPath
    requested = [ordered]@{ count = $Count; warmup = $Warmup; samples = $Samples; repeats = 1; method = 'NNJoltCrowd'; movementOnly = $true; floorOnly = $true; workers = $JoltWorkerThreads; paddingCm = $QueryTreePaddingCm; duringPhysics = [bool]$DuringPhysics; serialCompose = [bool]$SerialCompose; pClassGameThread = [bool]$PClassGameThread; noLockIdleReads = [bool]$NoLockIdleReads; pauseChaos = [bool]$PauseChaos; feedbackMode = $FeedbackMode; processPriority = $ProcessPriority }
    scope = 'External admission and pre-launch file hashes only, not a benchmark success result. The unchanged conservative CPU probe label does not describe game floating-point semantics. Runtime game_module_build_profile must match expectedGameProfile. Jolt native remains SSE2; no Engine/ORT/DLL ISA substitution, affinity or power changes are made here.'
}
$json = $record | ConvertTo-Json -Depth 8
$stream = [IO.File]::Open($sidecarPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
try {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
    $stream.Write($bytes, 0, $bytes.Length)
}
finally { $stream.Dispose() }
if (-not $accepted) { throw "CPU/OS preflight refused this diagnostic. See $sidecarPath" }

$oldExpected = [Environment]::GetEnvironmentVariable('PROPHECY_GAME_DIAGNOSTIC_EXPECTED_PROFILE', 'Process')
$oldPreflight = [Environment]::GetEnvironmentVariable('PROPHECY_GAME_DIAGNOSTIC_PREFLIGHT', 'Process')
try {
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_DIAGNOSTIC_EXPECTED_PROFILE', $GameProfile, 'Process')
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_DIAGNOSTIC_PREFLIGHT', $sidecarPath, 'Process')
    $arguments = @{
        Count = $Count; Warmup = $Warmup; Samples = $Samples; Repeats = 1; Label = $Label
        Methods = 'NNJoltCrowd'; FloorOnly = $true; MovementOnly = $true
        JoltWorkerThreads = $JoltWorkerThreads; QueryTreePaddingCm = $QueryTreePaddingCm
        DuringPhysics = [bool]$DuringPhysics; SerialCompose = [bool]$SerialCompose
        PClassGameThread = [bool]$PClassGameThread; NoLockIdleReads = [bool]$NoLockIdleReads
        PauseChaos = [bool]$PauseChaos; FeedbackMode = $FeedbackMode; ProcessPriority = $ProcessPriority; Engine = $Engine
    }
    Write-Output "Game-module preflight passed: $sidecarPath"
    # The existing launcher creates the one hidden owned child and returns its
    # PID/report. It inherits the two scoped provenance variables before restore.
    & (Join-Path $gameProjectRoot 'Tools/NN/RunSterilePhysicsBenchmark.ps1') @arguments
}
finally {
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_DIAGNOSTIC_EXPECTED_PROFILE', $oldExpected, 'Process')
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_DIAGNOSTIC_PREFLIGHT', $oldPreflight, 'Process')
}
