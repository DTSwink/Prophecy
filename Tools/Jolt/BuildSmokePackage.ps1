<#
.SYNOPSIS
Builds, cooks and stages the isolated Jolt smoke host using prepared dependencies and editor binaries.
.DESCRIPTION
Does not prepare Jolt, rebuild the editor, launch the packaged game, or close running processes.
Every invocation gets a new report/stage directory. A failed UAT invocation is reported without retries.
On success, pass the returned Executable to Tools/Jolt/RunPackagedFixture.ps1.
#>
[CmdletBinding()]
param(
    [ValidateSet('Development', 'Shipping')]
    [string]$Configuration = 'Development',

    [ValidateNotNullOrEmpty()]
    [string]$Engine = 'C:/Program Files/Epic Games/UE_5.7',

    [ValidateRange(1, 32)]
    [int]$Jobs = 3
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-JoltFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required prepared input is missing: $Path"
    }
    if ((Get-Item -LiteralPath $Path).Length -eq 0) {
        throw "Required prepared input is empty: $Path"
    }
}

function Assert-NoJoltHostProcess {
    $joltRunning = @(Get-Process | Where-Object {
        $_.ProcessName -in @('UnrealEditor', 'UnrealEditor-Cmd') -or
        $_.ProcessName -match '^ProphecyJoltSmokeHost(?:-Win64-[A-Za-z]+)?$'
    })
    if ($joltRunning.Count -gt 0) {
        $joltProcessDescriptions = ($joltRunning | ForEach-Object { "$($_.ProcessName) (PID $($_.Id))" }) -join ', '
        throw "An editor or smoke-host game is running: $joltProcessDescriptions. This wrapper will not close it."
    }
}

Assert-NoJoltHostProcess
$joltProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).ProviderPath
$joltEngineRoot = (Resolve-Path -LiteralPath $Engine).ProviderPath
$joltHostDirectory = Join-Path $PSScriptRoot 'SmokeHost'
$joltHostProject = Join-Path $joltHostDirectory 'ProphecyJoltSmokeHost.uproject'
$joltFixture = Join-Path $joltHostDirectory 'Content/Fixture/DA_CompoundFixture.uasset'
$joltRunUat = Join-Path $joltEngineRoot 'Engine/Build/BatchFiles/RunUAT.bat'
$joltEngineVersionPath = Join-Path $joltEngineRoot 'Engine/Build/Build.version'
$joltEditorReceipt = Join-Path $joltHostDirectory 'Binaries/Win64/ProphecyJoltSmokeHostEditor.target'
$joltEditorModule = Join-Path $joltHostDirectory 'Binaries/Win64/UnrealEditor-ProphecyJoltSmokeHost.dll'
$joltRuntimeEditorModule = Join-Path $joltProjectRoot 'Plugins/ProphecyJolt/Binaries/Win64/UnrealEditor-ProphecyJolt.dll'
$joltEditorDependency = Join-Path $joltProjectRoot 'Plugins/ProphecyJolt/Binaries/Win64/ProphecyJolt_5_6_Development.dll'
$joltInstallRoot = Join-Path $joltProjectRoot "Intermediate/JoltMigration/Install/$Configuration"
$joltManifestPath = Join-Path $joltInstallRoot 'manifest.json'
$joltDllName = "ProphecyJolt_5_6_$Configuration.dll"
$joltImportLibraryName = "ProphecyJolt_5_6_$Configuration.lib"
$joltDependencyDll = Join-Path $joltInstallRoot "bin/$joltDllName"
$joltImportLibrary = Join-Path $joltInstallRoot "lib/$joltImportLibraryName"
foreach ($joltInput in @($joltHostProject, $joltFixture, $joltRunUat, $joltEngineVersionPath,
        $joltEditorReceipt, $joltEditorModule, $joltRuntimeEditorModule, $joltEditorDependency,
        $joltManifestPath, $joltDependencyDll, $joltImportLibrary)) {
    Assert-JoltFile $joltInput
}

$joltEngineVersion = Get-Content -LiteralPath $joltEngineVersionPath -Raw | ConvertFrom-Json
if ($joltEngineVersion.MajorVersion -ne 5 -or $joltEngineVersion.MinorVersion -ne 7) {
    throw 'This smoke-package recipe is verified against UE 5.7. Select that engine installation.'
}
$joltManifest = Get-Content -LiteralPath $joltManifestPath -Raw | ConvertFrom-Json
if ($joltManifest.schema -ne 2 -or $joltManifest.version -ne '5.6.0' -or
    $joltManifest.sourceSha -ne 'e77f175595e64cb44218cc9d9d56fc365ad0e36a' -or
    $joltManifest.configuration -ne $Configuration -or $joltManifest.dllFilename -ne $joltDllName -or
    $joltManifest.importLibraryFilename -ne $joltImportLibraryName -or
    $joltManifest.runtime -ne 'MD' -or $joltManifest.library -ne 'shared' -or
    $joltManifest.worldPrecision -ne 'double' -or
    $joltManifest.cppExceptions -isnot [bool] -or -not $joltManifest.cppExceptions -or
    $joltManifest.assertions -isnot [bool] -or $joltManifest.assertions -ne ($Configuration -eq 'Development')) {
    throw 'The selected dependency manifest does not match the schema-2 Jolt build contract. Prepare the dependency first.'
}
$joltManifestHash = (Get-FileHash -LiteralPath $joltManifestPath -Algorithm SHA256).Hash
$joltDependencyHash = (Get-FileHash -LiteralPath $joltDependencyDll -Algorithm SHA256).Hash
$joltImportHash = (Get-FileHash -LiteralPath $joltImportLibrary -Algorithm SHA256).Hash
if ($joltDependencyHash -ne $joltManifest.dllSha256 -or $joltImportHash -ne $joltManifest.importLibrarySha256) {
    throw 'The selected dependency DLL/import-library hashes do not match their manifest.'
}

$joltReportParent = Join-Path $joltProjectRoot 'Saved/JoltMigration'
[System.IO.Directory]::CreateDirectory($joltReportParent) | Out-Null
$joltReportDirectory = Join-Path $joltReportParent ("SmokePackage-$Configuration-" + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff'))
# No -Force: never reuse another invocation's directory, including on a timestamp collision.
New-Item -ItemType Directory -Path $joltReportDirectory | Out-Null
$joltStageDirectory = Join-Path $joltReportDirectory 'stage'
New-Item -ItemType Directory -Path $joltStageDirectory | Out-Null
$joltLogPath = Join-Path $joltReportDirectory 'UAT.log'
$joltMetadataPath = Join-Path $joltReportDirectory 'package.json'
$joltLogStream = [System.IO.File]::Open($joltLogPath, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
$joltLogStream.Dispose()

# UE 5.7 source contracts:
# AutomationUtils/ProjectParams.cs:738 nocompileeditor, :906 stagingdirectory,
# :952/:1217 map -> MapsToCook, :1041 ubtargs; BuildProjectCommand.Automation.cs:130 forwards UbtArgs.
# UnrealBuildTool/Configuration/BuildConfiguration.cs:119 accepts -MaxParallelActions.
$joltArguments = @(
    'BuildCookRun', "-project=$joltHostProject", '-noP4', '-unattended', '-utf8output',
    '-platform=Win64', "-clientconfig=$Configuration", '-build', '-cook', '-stage',
    '-pak', '-iostore', '-package', '-nodebuginfo', '-nocompileeditor',
    '-map=/Engine/Maps/Entry', "-stagingdirectory=$joltStageDirectory", "-UbtArgs=-MaxParallelActions=$Jobs"
)
$joltFailures = [System.Collections.Generic.List[string]]::new()
$joltExitCode = $null
$joltExePath = $null
$joltExeHash = $null
$joltStagedDllPath = $null
$joltStagedDllHash = $null
$joltManifestHashAfter = $null
$joltStartedUtc = [DateTime]::UtcNow
$joltElapsed = [System.Diagnostics.Stopwatch]::StartNew()
$joltPreparedInputs = [ordered]@{
    hostProject = $joltHostProject
    hostProjectSha256 = (Get-FileHash -LiteralPath $joltHostProject -Algorithm SHA256).Hash
    fixture = $joltFixture
    fixtureSha256 = (Get-FileHash -LiteralPath $joltFixture -Algorithm SHA256).Hash
    editorReceipt = $joltEditorReceipt
    editorReceiptSha256 = (Get-FileHash -LiteralPath $joltEditorReceipt -Algorithm SHA256).Hash
    editorModule = $joltEditorModule
    editorModuleSha256 = (Get-FileHash -LiteralPath $joltEditorModule -Algorithm SHA256).Hash
    runtimeEditorModule = $joltRuntimeEditorModule
    runtimeEditorModuleSha256 = (Get-FileHash -LiteralPath $joltRuntimeEditorModule -Algorithm SHA256).Hash
    editorDependency = $joltEditorDependency
    editorDependencySha256 = (Get-FileHash -LiteralPath $joltEditorDependency -Algorithm SHA256).Hash
    dependencyManifest = $joltManifestPath
    dependencyManifestSha256 = $joltManifestHash
    dependencyDll = $joltDependencyDll
    dependencyDllSha256 = $joltDependencyHash
    dependencyImportLibrary = $joltImportLibrary
    dependencyImportLibrarySha256 = $joltImportHash
}

try {
    # Recheck immediately before UAT. Never stop a process found by this guard.
    Assert-NoJoltHostProcess
    Write-Host "Packaging Jolt $Configuration; UAT log: $joltLogPath"
    Push-Location -LiteralPath $joltHostDirectory
    try {
        # Treat native stderr as captured UAT output (also on Windows PowerShell 5.1).
        # Explicit exit-code validation below is authoritative; log-write errors still terminate.
        $joltSavedErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $joltRunUat @joltArguments 2>&1 | Tee-Object -FilePath $joltLogPath -Append -ErrorAction Stop | Out-Host
            $joltExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $joltSavedErrorActionPreference
        }
    }
    finally {
        Pop-Location
    }
    if ($null -eq $joltExitCode -or $joltExitCode -ne 0) {
        throw "BuildCookRun failed with exit code '$joltExitCode'. No retry or fallback was attempted."
    }

    $joltManifestHashAfter = (Get-FileHash -LiteralPath $joltManifestPath -Algorithm SHA256).Hash
    if ($joltManifestHashAfter -ne $joltManifestHash) {
        throw 'The selected dependency manifest changed while UAT was running; this package is not accepted.'
    }
    $joltExpectedExeName = if ($Configuration -eq 'Shipping') {
        'ProphecyJoltSmokeHost-Win64-Shipping.exe'
    } else {
        'ProphecyJoltSmokeHost.exe'
    }
    # Restrict discovery to our new stage. A root bootstrap never satisfies this predicate.
    $joltExecutables = @(Get-ChildItem -LiteralPath $joltStageDirectory -Recurse -File -Filter $joltExpectedExeName |
        Where-Object { $_.Directory.Name -eq 'Win64' -and $_.Directory.Parent.Name -eq 'Binaries' })
    if ($joltExecutables.Count -ne 1) {
        throw "Expected exactly one staged Binaries/Win64/$joltExpectedExeName; found $($joltExecutables.Count)."
    }
    $joltExePath = $joltExecutables[0].FullName
    $joltExeHash = (Get-FileHash -LiteralPath $joltExePath -Algorithm SHA256).Hash
    $joltStagedDllPath = Join-Path $joltExecutables[0].DirectoryName $joltDllName
    Assert-JoltFile $joltStagedDllPath
    $joltStagedDllHash = (Get-FileHash -LiteralPath $joltStagedDllPath -Algorithm SHA256).Hash
    if ($joltStagedDllHash -ne $joltDependencyHash) {
        throw 'The Jolt DLL beside the staged game does not match the selected dependency manifest.'
    }
}
catch {
    $joltFailures.Add($_.Exception.Message)
}
finally {
    $joltElapsed.Stop()
    $joltSuccess = $joltFailures.Count -eq 0 -and $joltExitCode -eq 0 -and
        $null -ne $joltExePath -and $joltStagedDllHash -eq $joltDependencyHash
    $joltMetadata = [ordered]@{
        schema = 1
        success = [bool]$joltSuccess
        validationScope = 'UAT exit and staged executable/dependency provenance; packaged fixture has not been run'
        configuration = $Configuration
        jobs = $Jobs
        engine = $joltEngineRoot
        engineVersion = $joltEngineVersion
        engineVersionPath = $joltEngineVersionPath
        runUat = $joltRunUat
        arguments = $joltArguments
        workingDirectory = $joltHostDirectory
        preparedInputs = $joltPreparedInputs
        dependencyManifestSha256AfterUat = $joltManifestHashAfter
        startedUtc = $joltStartedUtc.ToString('o')
        finishedUtc = [DateTime]::UtcNow.ToString('o')
        elapsedSeconds = $joltElapsed.Elapsed.TotalSeconds
        exitCode = $joltExitCode
        stageDirectory = $joltStageDirectory
        uatLog = $joltLogPath
        result = $joltMetadataPath
        executable = $joltExePath
        executableSha256 = $joltExeHash
        stagedDependencyDll = $joltStagedDllPath
        stagedDependencyDllSha256 = $joltStagedDllHash
        failures = @($joltFailures.ToArray())
    }
    $joltMetadataBytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($joltMetadata | ConvertTo-Json -Depth 8))
    $joltMetadataStream = [System.IO.File]::Open($joltMetadataPath, [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
    try { $joltMetadataStream.Write($joltMetadataBytes, 0, $joltMetadataBytes.Length) }
    finally { $joltMetadataStream.Dispose() }
}

if (-not $joltSuccess) {
    throw "Smoke package failed: $($joltFailures -join ' ') See $joltMetadataPath and $joltLogPath"
}
[pscustomobject]@{
    Success = $true
    Configuration = $Configuration
    Executable = $joltExePath
    Result = $joltMetadataPath
    UatLog = $joltLogPath
    FixtureRunner = (Join-Path $PSScriptRoot 'RunPackagedFixture.ps1')
}
