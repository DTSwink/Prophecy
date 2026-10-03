<#
.SYNOPSIS
Builds snapshot Editor and Game targets, cooks normal references, stages a new package.
.DESCRIPTION
Does not prepare Jolt or launch the game. Shipping requires a passing packaged
Development runner result from the exact same immutable snapshot.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Snapshot,
    [ValidateSet('Development','Shipping')][string]$Configuration='Development',
    [ValidateRange(1,32)][int]$Jobs=3,
    [string]$DevelopmentEvidence=''
)
. (Join-Path $PSScriptRoot 'PackagedNN.Common.ps1')
Assert-NNIdle
$snapshotPath=Resolve-NNAbsolute $Snapshot
$data=Read-NNSnapshot $snapshotPath
$snapshotHash=Get-NNHash $snapshotPath
$project=$data.projectDirectory
$engine=$data.engine
$versionPath=Join-Path $engine 'Engine/Build/Build.version'
if ((Get-NNHash $versionPath) -ne $data.engineVersionSha256) { throw 'Engine version changed since snapshot creation.' }
if ((Get-NNHash (Join-Path $engine 'Engine/Content/Maps/Entry.umap')) -ne $data.engineMapSha256) { throw 'Engine Entry map changed since snapshot creation.' }
$native=Assert-NNDependency $project $Configuration
$null=Assert-NNDependency $project 'Development'
if ($Configuration -eq 'Shipping') {
    if (-not $DevelopmentEvidence) { throw 'Shipping requires -DevelopmentEvidence from a passing packaged Development NN run.' }
    $evidence=Get-Content -LiteralPath (Resolve-NNAbsolute $DevelopmentEvidence) -Raw | ConvertFrom-Json
    if (-not $evidence.success -or $evidence.configuration -ne 'Development' -or $evidence.snapshotSha256 -ne $snapshotHash -or -not $evidence.validationSuccess) { throw 'Development evidence does not validate this exact snapshot.' }
    if ((Get-NNHash $evidence.packageResult) -ne $evidence.packageSha256) { throw 'Development package evidence changed after validation.' }
    if ((Get-NNHash $evidence.nativeResult) -ne $evidence.nativeResultSha256 -or (Get-NNHash $evidence.validation) -ne $evidence.validationSha256) { throw 'Development runtime validation evidence changed.' }
}
$buildBat=Join-Path $engine 'Engine/Build/BatchFiles/Build.bat'
$uatBat=Join-Path $engine 'Engine/Build/BatchFiles/RunUAT.bat'
Assert-NNFile $buildBat; Assert-NNFile $uatBat
$out=New-NNDirectory (Join-Path (Split-Path -Parent $snapshotPath) 'Packages') $Configuration
# UE's loose cooked-package writer rejects absolute paths >=260 characters.
# Keep this immutable snapshot in place, but give cook/stage fresh short outputs.
$shortParent=[IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex/tmp/ProphecyJolt'))
$ancestor=$shortParent
while ($ancestor) {
    if (Test-Path -LiteralPath $ancestor) {
        $item=Get-Item -LiteralPath $ancestor -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Short output ancestor is not a direct directory: $ancestor" }
    }
    $parent=[IO.Path]::GetDirectoryName($ancestor)
    if ($parent -eq $ancestor) { break }
    $ancestor=$parent
}
$shortOutput=New-NNDirectory $shortParent ('NNPkg-'+$Configuration)
$shortOutput=Resolve-NNAbsolute $shortOutput
$cookOutput=Join-Path $shortOutput 'Cook/Windows'
$stage=Join-Path $shortOutput 'Stage'
# The leaf must be Windows: CookByTheBook uses this exact single-platform path;
# UAT staging appends the platform only when it is not already the leaf.
New-Item -ItemType Directory -Path $cookOutput | Out-Null
New-Item -ItemType Directory -Path $stage | Out-Null
$ownershipPath=Join-Path $shortOutput 'ownership.json'
Write-NNJson $ownershipPath ([ordered]@{
    kind='ProphecyPackagedNNShortOutputs';schema=1;snapshot=$snapshotPath;snapshotSha256=$snapshotHash
    packageResult=(Join-Path $out 'package.json');configuration=$Configuration
    cookOutputDirectory=$cookOutput;stage=$stage;createdUtc=[DateTime]::UtcNow.ToString('o')
})
$buildLog=Join-Path $out 'EditorBuild.log'
$uatLog=Join-Path $out 'UAT.log'
$reportPath=Join-Path $out 'package.json'
$editorArgs=@('GameAnimationSample3Editor','Win64','Development',"-Project=$($data.projectFile)",'-WaitMutex','-NoHotReload','-NoUBTMakefiles',"-MaxParallelActions=$Jobs")
$cookRoots=$data.gamePackageRoots -join '+'
$uatArgs=@('BuildCookRun',"-project=$($data.projectFile)",'-noP4','-unattended','-utf8output','-platform=Win64',"-clientconfig=$Configuration",'-build','-cook','-stage','-pak','-iostore','-package','-nodebuginfo','-nocompileeditor','-map=/Engine/Maps/Entry',"-AdditionalCookerOptions=-PACKAGE=$cookRoots","-stagingdirectory=$stage","-CookOutputDir=$cookOutput","-UbtArgs=-NoUBTMakefiles -MaxParallelActions=$Jobs")
$envNames=@('PROPHECY_JOLT_SIMD','PROPHECY_GAME_SIMD')
$oldEnv=@{}; foreach($name in $envNames){$oldEnv[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$failure=$null; $success=$false; $buildExit=$null; $uatExit=$null; $exe=$null
$stagedModels=@(); $nativeDlls=@(); $cookedPackages=@(); $receipts=@(); $controls=$null
$started=[DateTime]::UtcNow
function Invoke-NNBatch([string]$File,[string[]]$Arguments,[string]$Log) {
    $savedPreference=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $File @Arguments 2>&1 | Tee-Object -FilePath $Log -ErrorAction Stop | Out-Host
        return $LASTEXITCODE
    } finally { $ErrorActionPreference=$savedPreference }
}
try {
    [Environment]::SetEnvironmentVariable('PROPHECY_JOLT_SIMD','SSE2','Process')
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_SIMD','DEFAULT','Process')
    Assert-NNIdle
    $buildExit=Invoke-NNBatch $buildBat $editorArgs $buildLog
    if ($buildExit -ne 0) { throw "Snapshot Editor build failed: $buildExit" }
    foreach($name in @('GameAnimationSample3Editor.target','UnrealEditor-GameAnimationSample3.dll','UnrealEditor-ProphecyEditor.dll')) { Assert-NNFile (Join-Path $project "Binaries/Win64/$name") }
    Assert-NNFile (Join-Path $project 'Plugins/ProphecyJolt/Binaries/Win64/UnrealEditor-ProphecyJolt.dll')
    $null=Read-NNSnapshot $snapshotPath
    if($Configuration -eq 'Development'){
        # Reuse the existing bounded, isolated automation runner against this freshly built
        # snapshot editor. The raw report remains in the snapshot's own Saved directory.
        $testOutput=@(& (Join-Path $project 'Tools/Jolt/RunFoundationTests.ps1') -Engine $engine -Project $data.projectFile -NoLockIdleReads -Filter 'Prophecy.Jolt.QueryPose')
        $jsonOutput=@($testOutput | Where-Object { $_ -is [string] -and $_.TrimStart().StartsWith('{') })
        if($jsonOutput.Count -ne 1){throw 'Foundation runner did not return one explicit result object.'}
        $result=$jsonOutput[0]|ConvertFrom-Json
        if(-not $result.Success){throw 'Snapshot query controls did not pass.'}
        $index=Get-Content -LiteralPath $result.Report -Raw|ConvertFrom-Json
        foreach($testName in @('Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose','Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle')){
            $test=@($index.tests|Where-Object fullTestPath -eq $testName)
            if($test.Count -ne 1 -or $test[0].state -ne 'Success' -or $test[0].errors -ne 0 -or $test[0].warnings -ne 0){throw "Required snapshot query control did not pass: $testName"}
        }
        $controls=[ordered]@{success=$true;snapshotSha256=$snapshotHash;report=$result.Report;reportSha256=(Get-NNHash $result.Report);editorModuleSha256=(Get-NNHash (Join-Path $project 'Binaries/Win64/UnrealEditor-GameAnimationSample3.dll'))}
    } else {
        $developmentPackage=Get-Content -LiteralPath $evidence.packageResult -Raw|ConvertFrom-Json
        $controls=$developmentPackage.controlledQueryTests
        if(-not $controls.success -or $controls.snapshotSha256 -ne $snapshotHash -or (Get-NNHash $controls.report) -ne $controls.reportSha256 -or (Get-NNHash (Join-Path $project 'Binaries/Win64/UnrealEditor-GameAnimationSample3.dll')) -ne $controls.editorModuleSha256){throw 'Matching-source Development query control evidence changed.'}
    }
    $null=Read-NNSnapshot $snapshotPath
    Assert-NNIdle
    $uatExit=Invoke-NNBatch $uatBat $uatArgs $uatLog
    if ($uatExit -ne 0) { throw "BuildCookRun failed: $uatExit. No fallback/retry was attempted." }
    # A successful cook must not conceal omitted required/config/plugin packages.
    $missing=Select-String -LiteralPath $uatLog -Pattern "Can't find file|Unable to find package|Failed to load package|DoesPackageExist FAILED|Unable to find plugin" -CaseSensitive:$false
    if ($missing) { throw "Cook emitted unresolved package/plugin diagnostics; review $uatLog before changing the snapshot closure." }
    $null=Read-NNSnapshot $snapshotPath
    $name=if($Configuration -eq 'Shipping'){'GameAnimationSample3-Win64-Shipping.exe'}else{'GameAnimationSample3.exe'}
    $candidates=@(Get-ChildItem -LiteralPath $stage -Recurse -File -Filter $name | Where-Object {$_.Directory.Name -eq 'Win64' -and $_.Directory.Parent.Name -eq 'Binaries'})
    if($candidates.Count -ne 1){throw "Expected one direct Binaries/Win64/$name, found $($candidates.Count)."}
    $exe=$candidates[0].FullName
    $stageProject=Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $exe))
    if((Split-Path -Leaf $stageProject) -ne 'GameAnimationSample3'){throw 'Unexpected staged project identity.'}
    $dll=Join-Path (Split-Path -Parent $exe) $native.dllFilename
    if((Get-NNHash $dll) -ne $native.dllSha256){throw 'Staged Jolt DLL mismatch.'}
    $ortSource=Join-Path $engine 'Engine/Plugins/NNE/NNERuntimeORT/Binaries/ThirdParty/Onnxruntime/Win64/onnxruntime.dll'
    $ort=@(Get-ChildItem -LiteralPath $stage -Recurse -File -Filter 'onnxruntime.dll')
    if($ort.Count -ne 1 -or (Get-NNHash $ort[0].FullName) -ne (Get-NNHash $ortSource)){throw 'Staged ORT runtime is missing, ambiguous or mismatched.'}
    foreach($relative in $data.modelRelativePaths){
        $source=Join-Path $project $relative
        $destination=Join-Path $stageProject $relative
        $sourceHash=Get-NNHash $source
        $origin='exact raw file copied after cook'
        if(Test-Path -LiteralPath $destination){
            if((Get-NNHash $destination) -ne $sourceHash){throw "Cook staged a different raw model/contract: $relative"}
            $origin='already staged by UAT; exact source hash verified'
        } else {
            $null=Copy-NNInput $source $stageProject $relative $true
        }
        $stagedModels += [pscustomobject]@{relativePath=$relative;path=$destination;sha256=$sourceHash;bytes=(Get-Item -LiteralPath $source).Length;origin=$origin}
    }
    foreach($package in $data.gamePackageClosure){
        $stem=Join-Path $cookOutput ('GameAnimationSample3/Content/'+$package.Substring(6))
        $cooked=@(@("$stem.uasset","$stem.umap")|Where-Object{Test-Path -LiteralPath $_ -PathType Leaf})
        if($cooked.Count -ne 1){throw "Expected cooked package missing: $package"}
        $cookedPackages += [pscustomobject]@{package=$package;file=$cooked[0];sha256=(Get-NNHash $cooked[0])}
    }
    foreach($file in (Get-ChildItem -LiteralPath $stage -Recurse -File -Filter '*.dll')){
        $nativeDlls += [pscustomobject]@{relativePath=$file.FullName.Substring($stage.Length+1);path=$file.FullName;sha256=(Get-NNHash $file.FullName)}
    }
    foreach($file in (Get-ChildItem -LiteralPath (Join-Path $project 'Binaries/Win64') -File -Filter '*.target')){
        $receipts += [pscustomobject]@{path=$file.FullName;sha256=(Get-NNHash $file.FullName)}
    }
    $success=$true
} catch { $failure=$_.Exception.Message }
finally {
    foreach($name in $envNames){[Environment]::SetEnvironmentVariable($name,$oldEnv[$name],'Process')}
    $report=[ordered]@{
        schema=1;kind='ProphecyPackagedNNCrowd';success=$success;error=$failure;configuration=$Configuration
        snapshot=$snapshotPath;snapshotSha256=$snapshotHash;project=$project;engine=$engine;engineVersion=$data.engineVersion
        sourceProfiles=@{jolt='SSE2';game='DEFAULT';environmentRestored=$true};jobs=$Jobs
        editorBuildArguments=$editorArgs;uatArguments=$uatArgs;editorBuildExitCode=$buildExit;uatExitCode=$uatExit
        startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');stage=$stage
        shortOutputDirectory=$shortOutput;cookOutputDirectory=$cookOutput
        shortOutputOwnership=$ownershipPath;shortOutputOwnershipSha256=(Get-NNHash $ownershipPath)
        executable=$exe;executableSha256=$(if($exe){Get-NNHash $exe}else{$null})
        dependencyManifest=(Join-Path $project "Intermediate/JoltMigration/Install/$Configuration/manifest.json")
        dependencyManifestSha256=(Get-NNHash (Join-Path $project "Intermediate/JoltMigration/Install/$Configuration/manifest.json"))
        stagedModels=$stagedModels;stagedNativeDlls=$nativeDlls;cookedGamePackages=$cookedPackages;receipts=$receipts
        logs=@($buildLog,$uatLog);developmentEvidence=$DevelopmentEvidence;controlledQueryTests=$controls
        validationScope='Build/cook/stage and immutable input provenance only. This package has not yet passed runtime NN, 22/21/88, query or lifecycle validation.'
    }
    Write-NNJson $reportPath $report
}
if(-not $success){throw "Package failed: $failure See $reportPath"}
[pscustomobject]@{Package=$reportPath;Executable=$exe;Configuration=$Configuration}
