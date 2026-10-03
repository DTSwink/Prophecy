from pathlib import Path
import hashlib, json, difflib

root = Path(__file__).resolve().parents[3]
draft = Path(__file__).resolve().parent
paths = [
    'Tools/Jolt/BuildJolt.ps1', 'Tools/Jolt/CMakeLists.txt',
    'Plugins/ProphecyJolt/Source/ProphecyJoltLibrary/ProphecyJoltLibrary.Build.cs',
    'Plugins/ProphecyJolt/Source/ProphecyJolt/ProphecyJolt.Build.cs',
    'Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltModule.cpp',
]
original = {p: (root / p).read_text(encoding='utf-8-sig') for p in paths}
updated = original.copy()

def replace(path, old, new):
    assert updated[path].count(old) == 1, (path, old[:100], updated[path].count(old))
    updated[path] = updated[path].replace(old, new)

p = paths[0]
replace(p, "    [string]$Configuration = 'Development',", "    [string]$Configuration = 'Development',\n    [ValidateSet('SSE2', 'AVX2')]\n    [string]$Simd = 'SSE2',")
replace(p, '$buildRoot = Join-Path $workRoot "Build/$Configuration"\n$installRoot = Join-Path $workRoot "Install/$Configuration"\n$libraryBaseName = "ProphecyJolt_5_6_$Configuration"', '''# The optional profile never overwrites the verified SSE2 dependency artifacts.
$profileDirectory = if ($Simd -eq 'AVX2') { "AVX2/$Configuration" } else { $Configuration }
$buildRoot = Join-Path $workRoot "Build/$profileDirectory"
$installRoot = Join-Path $workRoot "Install/$profileDirectory"
$profileSuffix = if ($Simd -eq 'AVX2') { '_AVX2' } else { '' }
$libraryBaseName = "ProphecyJolt_5_6_$Configuration$profileSuffix"''')
replace(p, "$asserts = if ($Configuration -eq 'Development') { 'ON' } else { 'OFF' }", '''# Compile and execute a separate SSE2-only process before compiling/using the
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
$asserts = if ($Configuration -eq 'Development') { 'ON' } else { 'OFF' }''')
replace(p, '    "-DPROPHECY_JOLT_CONFIGURATION=$Configuration",', '    "-DPROPHECY_JOLT_CONFIGURATION=$Configuration", "-DPROPHECY_JOLT_SIMD=$Simd",')
replace(p, "    '-DUSE_SSE4_1=OFF', '-DUSE_SSE4_2=OFF', '-DUSE_AVX=OFF', '-DUSE_AVX2=OFF',\n    '-DUSE_AVX512=OFF', '-DUSE_LZCNT=OFF', '-DUSE_TZCNT=OFF', '-DUSE_F16C=OFF', '-DUSE_FMADD=OFF'", '''    "-DUSE_SSE4_1=$advancedSimd", "-DUSE_SSE4_2=$advancedSimd", "-DUSE_AVX=$advancedSimd", "-DUSE_AVX2=$advancedSimd",
    '-DUSE_AVX512=OFF', "-DUSE_LZCNT=$advancedSimd", "-DUSE_TZCNT=$advancedSimd",
    "-DUSE_F16C=$advancedSimd", "-DUSE_FMADD=$advancedSimd"''')
replace(p, "$manifest = [ordered]@{", '''if ($Simd -eq 'AVX2') {
    $contractHeader = Join-Path $installRoot 'include/ProphecyJoltBuildContract.h'
    if (-not (Test-Path -LiteralPath $contractHeader)) { throw "Missing native contract header: $contractHeader" }
    $probeInstallRoot = Join-Path $installRoot 'tools'
    New-Item -ItemType Directory -Force -Path $probeInstallRoot | Out-Null
    Copy-Item -LiteralPath $probeExe -Destination (Join-Path $probeInstallRoot 'ProphecyJoltCpuPreflight.exe')
}
$manifest = [ordered]@{''')
replace(p, "    schema = 2; version = '5.6.0'; sourceSha = $upstreamSha", "    schema = $(if ($Simd -eq 'AVX2') { 3 } else { 2 }); version = '5.6.0'; sourceSha = $upstreamSha")
replace(p, "worldPrecision = 'double'; simd = 'SSE2'", "worldPrecision = 'double'; simd = $Simd")
replace(p, '$manifest | ConvertTo-Json -Depth 5', '''if ($Simd -eq 'AVX2') {
    $manifest['buildContractVersion'] = 1
    $manifest['instructionMask'] = 2015
    $manifest['fma'] = $true
    $manifest['compilerArchitecture'] = 'AVX2'
    $manifest['cpuPreflight'] = $cpuPreflight
    $manifest['cpuPreflightSha256'] = (Get-FileHash -LiteralPath $probeExe -Algorithm SHA256).Hash
    $manifest['contractHeaderSha256'] = (Get-FileHash -LiteralPath $contractHeader -Algorithm SHA256).Hash
}
$manifest | ConvertTo-Json -Depth 5''')
replace(p, 'Write-Output "Jolt $Configuration prepared: $installRoot"', 'Write-Output "Jolt $Configuration $Simd prepared: $installRoot"')

p = paths[1]
replace(p, 'add_subdirectory("${PROPHECY_JOLT_SOURCE}/Build" JoltBuild)', '''if(NOT DEFINED PROPHECY_JOLT_SIMD)
    set(PROPHECY_JOLT_SIMD SSE2)
endif()
if(NOT PROPHECY_JOLT_SIMD STREQUAL "SSE2" AND NOT PROPHECY_JOLT_SIMD STREQUAL "AVX2")
    message(FATAL_ERROR "PROPHECY_JOLT_SIMD must be SSE2 or AVX2.")
endif()
set(PROPHECY_JOLT_PROFILE_SUFFIX "")
if(PROPHECY_JOLT_SIMD STREQUAL "AVX2")
    foreach(FEATURE USE_SSE4_1 USE_SSE4_2 USE_AVX USE_AVX2 USE_LZCNT USE_TZCNT USE_F16C USE_FMADD)
        if(NOT ${FEATURE})
            message(FATAL_ERROR "The declared AVX2/FMA profile requires ${FEATURE}=ON.")
        endif()
    endforeach()
    if(USE_AVX512 OR CROSS_PLATFORM_DETERMINISTIC)
        message(FATAL_ERROR "The AVX2/FMA diagnostic profile excludes AVX512 and cross-platform determinism.")
    endif()
    set(PROPHECY_JOLT_PROFILE_SUFFIX "_AVX2")
endif()
add_subdirectory("${PROPHECY_JOLT_SOURCE}/Build" JoltBuild)''')
replace(p, 'OUTPUT_NAME "ProphecyJolt_5_6_${PROPHECY_JOLT_CONFIGURATION}"', 'OUTPUT_NAME "ProphecyJolt_5_6_${PROPHECY_JOLT_CONFIGURATION}${PROPHECY_JOLT_PROFILE_SUFFIX}"')
updated[p] += '''
if(PROPHECY_JOLT_SIMD STREQUAL "AVX2")
    target_sources(Jolt PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/ProphecyJoltBuildContract.cpp")
    target_compile_definitions(Jolt PRIVATE PROPHECY_JOLT_BUILD_CONTRACT_EXPORTS=1 PROPHECY_JOLT_PRECISE_BUILD=1)
    install(FILES "${CMAKE_CURRENT_SOURCE_DIR}/ProphecyJoltBuildContract.h" DESTINATION include)
endif()
'''

p = paths[2]
replace(p, 'using System.IO;', 'using System.IO;\nusing System.Security.Cryptography;')
replace(p, '        string Configuration =', '''        // This opt-in is evaluated while generating the UBT makefile. A scoped
        // profile switch MUST build with -NoUBTMakefiles (see the diagnostic notes).
        string Simd = (Environment.GetEnvironmentVariable("PROPHECY_JOLT_SIMD") ?? "SSE2").Trim().ToUpperInvariant();
        if (Simd != "SSE2" && Simd != "AVX2")
            throw new BuildException("PROPHECY_JOLT_SIMD must be SSE2 or AVX2.");
        bool IsAvx2 = Simd == "AVX2";
        string Configuration =''')
replace(p, 'string LibraryBaseName = "ProphecyJolt_5_6_" + Configuration;', 'string LibraryBaseName = "ProphecyJolt_5_6_" + Configuration + (IsAvx2 ? "_AVX2" : "");')
replace(p, 'string InstallRoot = Path.Combine(ProjectRoot, "Intermediate", "JoltMigration", "Install", Configuration);', '''string InstallBase = Path.Combine(ProjectRoot, "Intermediate", "JoltMigration", "Install");
        string InstallRoot = IsAvx2 ? Path.Combine(InstallBase, "AVX2", Configuration) : Path.Combine(InstallBase, Configuration);''')
replace(p, ' + Configuration);\n\n        JsonObject Manifest', ' + Configuration + " -Simd " + Simd);\n\n        JsonObject Manifest')
replace(p, 'Manifest.GetIntegerField("schema") != 2', 'Manifest.GetIntegerField("schema") != (IsAvx2 ? 3 : 2)')
replace(p, '            || Manifest.GetStringField("runtime") != "MD"', '''            || Manifest.GetStringField("simd") != Simd
            || Manifest.GetStringField("floatingPoint") != "precise"
            || Manifest.GetBoolField("crossPlatformDeterministic")
            || Manifest.GetBoolField("debugRenderer") || Manifest.GetBoolField("profiler")
            || !Manifest.GetBoolField("objectStream")
            || Manifest.GetStringField("runtime") != "MD"''')
replace(p, '        ExternalDependencies.Add(ManifestPath);', '''        if (IsAvx2)
        {
            string ContractHeader = Path.Combine(InstallRoot, "include", "ProphecyJoltBuildContract.h");
            string CpuProbe = Path.Combine(InstallRoot, "tools", "ProphecyJoltCpuPreflight.exe");
            if (Manifest.GetIntegerField("buildContractVersion") != 1
                || Manifest.GetIntegerField("instructionMask") != 2015
                || Manifest.GetStringField("compilerArchitecture") != "AVX2" || !Manifest.GetBoolField("fma")
                || !File.Exists(ContractHeader) || !File.Exists(CpuProbe))
                throw new BuildException("The AVX2 native dependency contract/preflight is incomplete.");
            VerifyHash(DllPath, Manifest.GetStringField("dllSha256"));
            VerifyHash(LibraryPath, Manifest.GetStringField("importLibrarySha256"));
            VerifyHash(ContractHeader, Manifest.GetStringField("contractHeaderSha256"));
            VerifyHash(CpuProbe, Manifest.GetStringField("cpuPreflightSha256"));
            ExternalDependencies.Add(ContractHeader);
            ExternalDependencies.Add(CpuProbe);
            PublicDefinitions.AddRange(new[] { "JPH_USE_SSE4_1", "JPH_USE_SSE4_2", "JPH_USE_AVX", "JPH_USE_AVX2",
                "JPH_USE_LZCNT", "JPH_USE_TZCNT", "JPH_USE_F16C", "JPH_USE_FMADD", "PROPHECY_JOLT_PRECISE_BUILD=1" });
        }
        PublicDefinitions.Add("PROPHECY_JOLT_PROFILE_AVX2=" + (IsAvx2 ? "1" : "0"));
        ExternalDependencies.Add(ManifestPath);''')
replace(p, '    }\n}', '''    }

    private static void VerifyHash(string PathName, string Expected)
    {
        using (SHA256 Hasher = SHA256.Create())
        using (FileStream Input = File.OpenRead(PathName))
        {
            string Actual = BitConverter.ToString(Hasher.ComputeHash(Input)).Replace("-", "");
            if (!string.Equals(Actual, Expected, StringComparison.OrdinalIgnoreCase))
                throw new BuildException("Jolt dependency hash mismatch: " + PathName);
        }
    }
}''')

p = paths[3]
replace(p, 'using UnrealBuildTool;', 'using System;\nusing UnrealBuildTool;')
replace(p, '        FPSemantics = FPSemanticsMode.Precise;', '''        FPSemantics = FPSemanticsMode.Precise;
        // Module-local ISA: every Jolt inline consumer needs the same signature
        // contract. Leave the game/editor/engine modules on their existing ISA.
        string Simd = (Environment.GetEnvironmentVariable("PROPHECY_JOLT_SIMD") ?? "SSE2").Trim().ToUpperInvariant();
        if (Simd != "SSE2" && Simd != "AVX2")
            throw new BuildException("PROPHECY_JOLT_SIMD must be SSE2 or AVX2.");
        MinCpuArchX64 = Simd == "AVX2" ? MinimumCpuArchitectureX64.AVX2 : MinimumCpuArchitectureX64.None;''')

p = paths[4]
replace(p, '#include <Jolt/RegisterTypes.h>', '''#include <Jolt/RegisterTypes.h>
#if PROPHECY_JOLT_PROFILE_AVX2
#include <ProphecyJoltBuildContract.h>
#endif''')
replace(p, 'DEFINE_LOG_CATEGORY_STATIC(LogProphecyJolt, Log, All);', '''DEFINE_LOG_CATEGORY_STATIC(LogProphecyJolt, Log, All);

// Narrow UE 5.7 Win64 storage guards, evaluated for both profiles. These do
// not certify every inline function or cross-module calling convention.
static_assert(sizeof(FVector) == 24 && alignof(FVector) == 8, "Review the UE FVector boundary.");
static_assert(sizeof(FQuat) == 32 && alignof(FQuat) == 16, "Review the UE FQuat boundary.");
static_assert(sizeof(TPersistentVectorRegisterType<double>) == 32
    && alignof(TPersistentVectorRegisterType<double>) == 16, "UE persistent SIMD storage must stay 16-aligned.");
static_assert(sizeof(FTransform) == 96 && alignof(FTransform) == 16, "Review the UE FTransform boundary.");

#if PROPHECY_JOLT_PROFILE_AVX2
static_assert(ProphecyJoltBuildContract::CompilationInstructions() == ProphecyJoltBuildContract::ExpectedAVX2FMA,
    "Rebuild every native Jolt consumer with the declared AVX2/FMA profile.");
static_assert(ProphecyJoltBuildContract::CompilationPolicy() == ProphecyJoltBuildContract::ExpectedPolicy,
    "The AVX2 Jolt consumer must retain precise FP, exceptions, no RTTI and no determinism override.");
#endif''')
replace(p, '        if (!JPH::VerifyJoltVersionID())', '''#if PROPHECY_JOLT_PROFILE_AVX2
        // This is a post-load ABI/fingerprint check. It is NOT a pre-DLL CPU
        // guard: the baseline preflight must run before launching this process.
        if (ProphecyJolt_GetContractVersion() != ProphecyJoltBuildContract::ProtocolVersion
            || ProphecyJolt_GetNativeVersionId() != JPH_VERSION_ID
            || ProphecyJolt_GetNativeInstructions() != ProphecyJoltBuildContract::CompilationInstructions()
            || ProphecyJolt_GetNativePolicy() != ProphecyJoltBuildContract::CompilationPolicy())
        {
            UE_LOG(LogProphecyJolt, Fatal, TEXT("Jolt native DLL/consumer AVX2 build-contract mismatch."));
            return;
        }
        UE_LOG(LogProphecyJolt, Display, TEXT("Local AVX2 diagnostic native DLL: %s; ISA mask=%u, policy=%u. External CPU preflight required."),
            UTF8_TO_TCHAR(ProphecyJolt_GetNativeConfiguration()), ProphecyJolt_GetNativeInstructions(), ProphecyJolt_GetNativePolicy());
#endif
        if (!JPH::VerifyJoltVersionID())''')

patch = []
hashes = {}
for p in paths:
    target = draft / p
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(updated[p], encoding='utf-8', newline='\n')
    hashes[p] = hashlib.sha256((root / p).read_bytes()).hexdigest()
    patch.extend(difflib.unified_diff(original[p].splitlines(True), updated[p].splitlines(True), fromfile='a/'+p, tofile='b/'+p))
(draft/'ExistingFiles.patch').write_text(''.join(patch), encoding='utf-8', newline='\n')
(draft/'BaselineHashes.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
print('Saved draft copies, isolated patch and baseline hashes; no active files changed.')
