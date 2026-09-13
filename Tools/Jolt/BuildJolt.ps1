[CmdletBinding()]
param(
    [ValidateSet('Development', 'Shipping')]
    [string]$Configuration = 'Development',
    [ValidateSet('SSE2', 'AVX2')]
    [string]$Simd = 'SSE2',
    [ValidateRange(1, 32)]
    [int]$Jobs = 4,
    [string]$CMake = '',
    [string]$ToolsetVersion = '14.44.35207',
    [string]$WindowsSdkVersion = '10.0.22621.0'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE. Stopping." }
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$upstreamSha = 'e77f175595e64cb44218cc9d9d56fc365ad0e36a'
$workRoot = Join-Path $projectRoot 'Intermediate/JoltMigration'
$sourceRoot = Join-Path $workRoot 'Upstream'
# The optional profile never overwrites the verified SSE2 dependency artifacts.
$profileDirectory = if ($Simd -eq 'AVX2') { "AVX2/$Configuration" } else { $Configuration }
$buildRoot = Join-Path $workRoot "Build/$profileDirectory"
$installRoot = Join-Path $workRoot "Install/$profileDirectory"
$profileSuffix = if ($Simd -eq 'AVX2') { '_AVX2' } else { '' }
$libraryBaseName = "ProphecyJolt_5_6_$Configuration$profileSuffix"
$dllFilename = "$libraryBaseName.dll"
$importLibraryFilename = "$libraryBaseName.lib"

$activeUnreal = @(Get-Process -Name 'UnrealEditor', 'UnrealEditor-Cmd', 'GameAnimationSample3', 'GameAnimationSample3-Win64-Shipping' -ErrorAction SilentlyContinue)
if ($activeUnreal.Count -gt 0) {
    throw 'An Unreal editor/game process is running. Stop and obtain authorization before closing it or replacing the Jolt dependency.'
}

if (-not $CMake) {
    $cmakeCommand = Get-Command cmake -ErrorAction SilentlyContinue
    if ($cmakeCommand) { $CMake = $cmakeCommand.Source }
    else {
        $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
        if (Test-Path -LiteralPath $vswhere) {
            $candidates = @(& $vswhere -latest -products '*' -find 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe')
            if ($candidates.Count -gt 0) { $CMake = $candidates[0] }
        }
    }
}
if (-not $CMake -or -not (Test-Path -LiteralPath $CMake)) {
    throw 'CMake was not found. Pass -CMake with the installed executable path.'
}
if (-not (Test-Path -LiteralPath $sourceRoot)) {
    New-Item -ItemType Directory -Force -Path $workRoot | Out-Null
    Invoke-Checked git @('clone', '--depth', '1', '--branch', 'v5.6.0', '--single-branch',
        '--no-recurse-submodules', 'https://github.com/jrouwe/JoltPhysics.git', $sourceRoot)
}
$resolvedSha = (& git -C $sourceRoot rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $resolvedSha -ne $upstreamSha) {
    throw "Unexpected Jolt checkout: '$resolvedSha'; required $upstreamSha. No checkout was changed."
}
$sourceChanges = (& git -C $sourceRoot status --porcelain | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the pinned Jolt checkout.' }
$safetyPatch = Join-Path $PSScriptRoot 'Patches/NumericalSafety.patch'
if (-not (Test-Path -LiteralPath $safetyPatch)) { throw "Missing required dependency patch: $safetyPatch" }
if (-not $sourceChanges) {
    Invoke-Checked git @('-C', $sourceRoot, 'apply', '--check', $safetyPatch)
    Invoke-Checked git @('-C', $sourceRoot, 'apply', $safetyPatch)
}
# Accept only the exact reviewed patch, including on incremental rebuilds. Never
# reset a checkout or overwrite an unrelated dependency edit.
$actualPatch = (& git -C $sourceRoot diff --no-ext-diff --binary | Out-String).Replace("`r`n", "`n").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot verify the Jolt numerical-safety patch.' }
$expectedPatch = [IO.File]::ReadAllText($safetyPatch).Replace("`r`n", "`n").Trim()
$untrackedSource = (& git -C $sourceRoot ls-files --others --exclude-standard | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $untrackedSource -or $actualPatch -cne $expectedPatch) {
    throw 'Jolt source differs from the exact reviewed dependency patches. No unrelated local edits will be overwritten.'
}

# Compile and execute a separate SSE2-only process before compiling/using the
# AVX2 DLL. This probe must also be run before every later AVX2 UE/game launch.
$cpuPreflight = $null
$probeExe = $null
if ($Simd -eq 'AVX2') {
    $probeBuildRoot = Join-Path $workRoot 'CpuPreflightBuild'
    Invoke-Checked $CMake @('-S', (Join-Path $PSScriptRoot 'CpuPreflight'), '-B', $probeBuildRoot,
        '-G', 'Visual Studio 17 2022', '-A', "x64,version=$WindowsSdkVersion",
        '-T', "v143,host=x64,version=$ToolsetVersion", '-DCMAKE_CONFIGURATION_TYPES=Release')
    Invoke-Checked $CMake @('--build', $probeBuildRoot, '--config', 'Release',
        '--target', 'ProphecyJoltCpuPreflight', '--parallel', "$Jobs")
    $probeExe = Join-Path $probeBuildRoot 'Release/ProphecyJoltCpuPreflight.exe'
    $probeOutput = @(& $probeExe)
    if ($LASTEXITCODE -ne 0) { throw "CPU/OS does not support the complete AVX2/FMA diagnostic profile: $probeOutput" }
    $cpuPreflight = ($probeOutput -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $cpuPreflight.supported -or $cpuPreflight.required_instruction_mask -ne 2015) {
        throw 'CPU preflight did not return the expected supported AVX2/FMA contract.'
    }
}
$advancedSimd = if ($Simd -eq 'AVX2') { 'ON' } else { 'OFF' }
$asserts = if ($Configuration -eq 'Development') { 'ON' } else { 'OFF' }
$cmakeArgs = @(
    '-S', $PSScriptRoot, '-B', $buildRoot, '-G', 'Visual Studio 17 2022',
    '-A', "x64,version=$WindowsSdkVersion", '-T', "v143,host=x64,version=$ToolsetVersion",
    "-DPROPHECY_JOLT_SOURCE=$sourceRoot", "-DCMAKE_INSTALL_PREFIX=$installRoot",
    "-DPROPHECY_JOLT_CONFIGURATION=$Configuration", "-DPROPHECY_JOLT_SIMD=$Simd",
    '-DCMAKE_CONFIGURATION_TYPES=Release', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
    '-DCMAKE_CXX_STANDARD=20', '-DJPH_BUILD_SHARED_LIBS=ON', '-DUSE_STATIC_MSVC_RUNTIME_LIBRARY=OFF',
    '-DDOUBLE_PRECISION=ON', "-DUSE_ASSERTS=$asserts", '-DCROSS_PLATFORM_DETERMINISTIC=OFF',
    '-DFLOATING_POINT_EXCEPTIONS_ENABLED=OFF', '-DINTERPROCEDURAL_OPTIMIZATION=OFF',
    '-DCPP_EXCEPTIONS_ENABLED=ON', '-DCPP_RTTI_ENABLED=OFF',
    '-DDEBUG_RENDERER_IN_DEBUG_AND_RELEASE=OFF', '-DDEBUG_RENDERER_IN_DISTRIBUTION=OFF',
    '-DPROFILER_IN_DEBUG_AND_RELEASE=OFF', '-DPROFILER_IN_DISTRIBUTION=OFF',
    '-DENABLE_OBJECT_STREAM=ON', '-DENABLE_INSTALL=ON',
    '-DJPH_USE_DX12=OFF', '-DJPH_USE_VK=OFF', '-DJPH_USE_MTL=OFF', '-DJPH_USE_CPU_COMPUTE=OFF',
    "-DUSE_SSE4_1=$advancedSimd", "-DUSE_SSE4_2=$advancedSimd", "-DUSE_AVX=$advancedSimd", "-DUSE_AVX2=$advancedSimd",
    '-DUSE_AVX512=OFF', "-DUSE_LZCNT=$advancedSimd", "-DUSE_TZCNT=$advancedSimd",
    "-DUSE_F16C=$advancedSimd", "-DUSE_FMADD=$advancedSimd"
)
Invoke-Checked $CMake $cmakeArgs
Invoke-Checked $CMake @('--build', $buildRoot, '--config', 'Release', '--target', 'Jolt', '--parallel', "$Jobs")
Invoke-Checked $CMake @('--install', $buildRoot, '--config', 'Release')
$dll = Join-Path $installRoot "bin/$dllFilename"
$lib = Join-Path $installRoot "lib/$importLibraryFilename"
foreach ($artifact in @($dll, $lib, (Join-Path $installRoot 'include/Jolt/Jolt.h'))) {
    if (-not (Test-Path -LiteralPath $artifact)) { throw "Missing dependency artifact: $artifact" }
}
Copy-Item -LiteralPath (Join-Path $sourceRoot 'LICENSE') -Destination (Join-Path $installRoot 'Jolt-LICENSE.txt')
if ($Simd -eq 'AVX2') {
    $contractHeader = Join-Path $installRoot 'include/ProphecyJoltBuildContract.h'
    if (-not (Test-Path -LiteralPath $contractHeader)) { throw "Missing native contract header: $contractHeader" }
    $probeInstallRoot = Join-Path $installRoot 'tools'
    New-Item -ItemType Directory -Force -Path $probeInstallRoot | Out-Null
    Copy-Item -LiteralPath $probeExe -Destination (Join-Path $probeInstallRoot 'ProphecyJoltCpuPreflight.exe')
}
$manifest = [ordered]@{
    schema = $(if ($Simd -eq 'AVX2') { 3 } else { 2 }); version = '5.6.0'; sourceSha = $upstreamSha
    upstream = 'https://github.com/jrouwe/JoltPhysics'; configuration = $Configuration
    toolsetDirectory = $ToolsetVersion; windowsSdk = $WindowsSdkVersion
    runtime = 'MD'; library = 'shared'; worldPrecision = 'double'; simd = $Simd
    floatingPoint = 'precise'; crossPlatformDeterministic = $false; cppExceptions = $true
    assertions = ($Configuration -eq 'Development')
    debugRenderer = $false; profiler = $false; objectStream = $true
    dllFilename = $dllFilename; importLibraryFilename = $importLibraryFilename
    cmakeArguments = $cmakeArgs
    dllSha256 = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
    importLibrarySha256 = (Get-FileHash -LiteralPath $lib -Algorithm SHA256).Hash
    numericalSafetyPatchVersion = 1
    numericalSafetyPatchSha256 = (Get-FileHash -LiteralPath $safetyPatch -Algorithm SHA256).Hash
}
if ($Simd -eq 'AVX2') {
    $manifest['buildContractVersion'] = 1
    $manifest['instructionMask'] = 2015
    $manifest['fma'] = $true
    $manifest['compilerArchitecture'] = 'AVX2'
    $manifest['cpuPreflight'] = $cpuPreflight
    $manifest['cpuPreflightSha256'] = (Get-FileHash -LiteralPath $probeExe -Algorithm SHA256).Hash
    $manifest['contractHeaderSha256'] = (Get-FileHash -LiteralPath $contractHeader -Algorithm SHA256).Hash
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $installRoot 'manifest.json') -Encoding UTF8
Write-Output "Jolt $Configuration $Simd prepared: $installRoot"
