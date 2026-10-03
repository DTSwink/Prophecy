<# Final functional verification only. Creates new reports/stages; never deletes or closes existing processes.
Development rebuilds the current Editor, builds/cooks/stages Game, then runs the three fight fixtures.
Shipping requires successful exact Development evidence and reuses that complete Windows cook. #>
[CmdletBinding()]
param(
    [ValidateSet('Development','Shipping')][string]$Configuration='Development',
    [string]$DevelopmentEvidence='',
    [ValidateRange(1,16)][int]$Jobs=3,
    [string]$Engine='C:/Program Files/Epic Games/UE_5.7'
)
. (Join-Path $PSScriptRoot 'FinalFight.Common.ps1')
Assert-FightIdle
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).ProviderPath
$engineRoot=(Resolve-Path -LiteralPath $Engine).ProviderPath
$engineVersion=Get-Content -LiteralPath (Join-Path $engineRoot 'Engine/Build/Build.version') -Raw|ConvertFrom-Json
if($engineVersion.MajorVersion -ne 5 -or $engineVersion.MinorVersion -ne 7 -or $engineVersion.PatchVersion -ne 4 -or $engineVersion.Changelist -ne 51494982){throw 'This final cook registry and recipe require the reviewed UE 5.7.4 engine.'}
$project=Join-Path $root 'GameAnimationSample3.uproject'
$registry=Join-Path $root 'Saved/JoltMigration/FightCookRegistry-20260910-023258.json'
$graph=Get-Content -LiteralPath $registry -Raw|ConvertFrom-Json
$native=Get-FightDependency $root $Configuration
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$out=New-FightDirectory (Join-Path $PSScriptRoot "Packages/$Configuration-$stamp")
$short=New-FightDirectory (Join-Path ([Environment]::GetFolderPath('UserProfile')) ".codex/tmp/ProphecyJolt/FinalFight-$Configuration-$stamp")
$stage=New-FightDirectory (Join-Path $short 'Stage')
$inputPath=Join-Path $out 'inputs.json'; $cookManifestPath=Join-Path $out 'cook.json'
$packagePath=Join-Path $out 'package.json'; $resultPath=Join-Path $out 'result.json'
$inputs=$null; $cook=$null; $cookFiles=@(); $editorFiles=@(); $developmentRecord=$null; $runtime=$null; $failure=$null; $success=$false
$oldEnv=@{}; foreach($name in @('PROPHECY_JOLT_SIMD','PROPHECY_GAME_SIMD')){$oldEnv[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$started=[DateTime]::UtcNow
$buildArgs=@(); $uatArgs=@()
try {
    [Environment]::SetEnvironmentVariable('PROPHECY_JOLT_SIMD','SSE2','Process')
    [Environment]::SetEnvironmentVariable('PROPHECY_GAME_SIMD','DEFAULT','Process')
    if($Configuration -eq 'Shipping'){
        if(!$DevelopmentEvidence){throw 'Shipping requires the successful Development result.json from this exact candidate.'}
        $DevelopmentEvidence=Resolve-FightPath $DevelopmentEvidence
        $developmentRecord=Get-Content -LiteralPath $DevelopmentEvidence -Raw|ConvertFrom-Json
        if($developmentRecord.kind -ne 'ProphecyFinalFightResult' -or $developmentRecord.success -ne $true -or $developmentRecord.configuration -ne 'Development'){throw 'Development final verification did not pass.'}
        foreach($file in @($developmentRecord.package,$developmentRecord.runtime,$developmentRecord.inputs,$developmentRecord.cook)){
            if((Get-FightHash $file.path) -ne $file.sha256){throw "Development evidence changed: $($file.path)"}
        }
        $previousPackage=Get-Content -LiteralPath $developmentRecord.package.path -Raw|ConvertFrom-Json
        $previousRuntime=Get-Content -LiteralPath $developmentRecord.runtime.path -Raw|ConvertFrom-Json
        if($previousRuntime.success -ne $true -or $previousRuntime.exitCode -ne 0){throw 'Development runtime evidence is not a pass.'}
        foreach($file in $previousRuntime.reports){if((Get-FightHash $file.path) -ne $file.sha256){throw "Development fixture evidence changed: $($file.path)"}}
        $inputs=Get-Content -LiteralPath $developmentRecord.inputs.path -Raw|ConvertFrom-Json
        if($inputs.projectRoot -ne $root -or $inputs.engine -ne $engineRoot -or $inputs.registry -ne $registry){throw 'Development project/engine/registry changed.'}
        Assert-FightInputs $inputs
        Assert-FightRecords $previousPackage.editorFiles (Get-FightFileRecords @($previousPackage.editorFiles|ForEach-Object path)) 'Cook Editor binaries'
        $priorCook=Get-Content -LiteralPath $developmentRecord.cook.path -Raw|ConvertFrom-Json
        $cook=$priorCook.directory; $cookFiles=@($priorCook.files)
        Assert-FightRecords $cookFiles (Get-FightFileRecords @((Get-FightTree $cook)|ForEach-Object FullName)) 'Shared cooked payload and metadata'
        $editorFiles=@($previousPackage.editorFiles)
    } else {
        $inputs=[pscustomobject]@{kind='ProphecyFinalFightInputs';projectRoot=$root;engine=$engineRoot;registry=$registry;files=@(Get-FightInputs $root $engineRoot $registry)}
        $cook=New-FightDirectory (Join-Path $short 'Cook/Windows')
        # Normal Editor target build is required: Live Coding patches alone cannot supply cooker code.
        $buildArgs=@('GameAnimationSample3Editor','Win64','Development',"-Project=$project",'-WaitMutex','-NoHotReload','-NoUBTMakefiles',"-MaxParallelActions=$Jobs")
        Invoke-FightBatch (Join-Path $engineRoot 'Engine/Build/BatchFiles/Build.bat') $buildArgs (Join-Path $out 'EditorBuild.log')
        Assert-FightInputs $inputs
        $editorPaths=@(
            (Join-Path $root 'Binaries/Win64/GameAnimationSample3Editor.target'),
            (Join-Path $root 'Binaries/Win64/UnrealEditor-GameAnimationSample3.dll'),
            (Join-Path $root 'Plugins/ProphecyJolt/Binaries/Win64/UnrealEditor-ProphecyJolt.dll'),
            (Join-Path $root 'Plugins/ProphecyJolt/Binaries/Win64/ProphecyJolt_5_6_Development.dll'))
        $editorFiles=Get-FightFileRecords $editorPaths
    }
    Write-FightJson $inputPath $inputs
    Write-FightJson (Join-Path $short 'ownership.json') ([ordered]@{kind='ProphecyFinalFightOutputs';configuration=$Configuration;result=$resultPath;stage=$stage;cook=$cook;createdUtc=$started.ToString('o')})
    $cookRoots=@($graph.rootPackages|Where-Object{$_ -ne '/Game/testNN'}) -join '+'
    $uatArgs=@('BuildCookRun',"-project=$project",'-noP4','-unattended','-utf8output','-platform=Win64',"-clientconfig=$Configuration",'-build',
        $(if($Configuration -eq 'Shipping'){'-skipcook'}else{'-cook'}),'-stage','-pak','-iostore','-package','-nodebuginfo','-nocompileeditor',
        '-map=/Engine/Maps/Entry+/Game/testNN',"-AdditionalCookerOptions=-NoDefaultMaps -PACKAGE=$cookRoots",
        "-stagingdirectory=$stage","-CookOutputDir=$cook","-UbtArgs=-NoUBTMakefiles -MaxParallelActions=$Jobs")
    Invoke-FightBatch (Join-Path $engineRoot 'Engine/Build/BatchFiles/RunUAT.bat') $uatArgs (Join-Path $out 'UAT.log')
    Assert-FightInputs $inputs
    Assert-FightRecords $editorFiles (Get-FightFileRecords @($editorFiles|ForEach-Object path)) 'Cook Editor binaries'
    foreach($name in @('packagestore.manifest','scriptobjects.bin')){
        if(!(Test-Path -LiteralPath (Join-Path $cook "GameAnimationSample3/Metadata/$name") -PathType Leaf)){throw "Cook metadata missing: $name"}
    }
    foreach($name in @($graph.runtimeGamePackageClosure)+@($graph.runtimeExternalPackageClosure)+@('/Engine/Maps/Entry')){
        if($name.StartsWith('/Game/')){$stem=Join-Path $cook ('GameAnimationSample3/Content/'+$name.Substring(6))}
        elseif($name -eq '/Engine/Maps/Entry'){$stem=Join-Path $cook 'Engine/Content/Maps/Entry'}
        else {
            $source=@($graph.files|Where-Object{$_.package -eq $name -and [IO.Path]::GetExtension($_.path) -in @('.uasset','.umap')})
            if($source.Count -ne 1 -or !$source[0].path.StartsWith($engineRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw "External cooked source is ambiguous/outside pinned engine: $name"}
            $relative=$source[0].path.Substring($engineRoot.Length+1)
            $stem=Join-Path $cook ([IO.Path]::ChangeExtension($relative,$null))
        }
        $present=@(@("$stem.uasset","$stem.umap")|Where-Object{Test-Path -LiteralPath $_ -PathType Leaf})
        if($present.Count -ne 1){throw "Required runtime cooked package missing/ambiguous: $name"}
    }
    $nowCook=Get-FightFileRecords @((Get-FightTree $cook)|ForEach-Object FullName)
    if($Configuration -eq 'Shipping'){Assert-FightRecords $cookFiles $nowCook 'Reused cook including staging metadata'}
    $cookFiles=$nowCook
    Write-FightJson $cookManifestPath ([ordered]@{directory=$cook;files=$cookFiles;reuseDevelopmentEvidence=$DevelopmentEvidence})
    $exeName=if($Configuration -eq 'Shipping'){'GameAnimationSample3-Win64-Shipping.exe'}else{'GameAnimationSample3.exe'}
    $executables=@(Get-ChildItem -LiteralPath $stage -File -Recurse -Filter $exeName|Where-Object{$_.Directory.Name -eq 'Win64' -and $_.Directory.Parent.Name -eq 'Binaries'})
    if($executables.Count -ne 1){throw 'Expected exactly one direct staged Game executable.'}
    $exe=$executables[0].FullName; $dll=Join-Path $executables[0].DirectoryName $native.dllFilename
    if((Get-FightHash $dll) -ne $native.dllSha256){throw 'Staged Jolt DLL does not match the selected configuration.'}
    $stageFiles=Get-FightFileRecords @((Get-FightTree $stage)|ForEach-Object FullName)
    $package=[ordered]@{kind='ProphecyFinalFightPackage';success=$true;configuration=$Configuration;project=$project;engine=$engineRoot;
        inputs=@{path=$inputPath;sha256=(Get-FightHash $inputPath)};cook=@{path=$cookManifestPath;sha256=(Get-FightHash $cookManifestPath)};
        stage=$stage;stageFiles=$stageFiles;executable=$exe;executableSha256=(Get-FightHash $exe);joltDll=$dll;joltDllSha256=(Get-FightHash $dll);
        editorFiles=$editorFiles;editorBuildArguments=$buildArgs;uatArguments=$uatArgs;shortOutput=$short;registrySha256=(Get-FightHash $registry)}
    Write-FightJson $packagePath $package
    $runtime=& (Join-Path $PSScriptRoot 'Run-FinalFightPackage.ps1') -Package $packagePath
    Assert-FightInputs $inputs
    $success=$true
} catch {$failure=$_.Exception.Message}
finally {
    foreach($name in $oldEnv.Keys){[Environment]::SetEnvironmentVariable($name,$oldEnv[$name],'Process')}
    $record=[ordered]@{kind='ProphecyFinalFightResult';success=$success;configuration=$Configuration;error=$failure;startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');
        editorBuildArguments=$buildArgs;uatArguments=$uatArgs;output=$out;shortOutput=$short;developmentEvidence=$DevelopmentEvidence;package=$null;runtime=$null;inputs=$null;cook=$null}
    foreach($pair in @(@('package',$packagePath),@('runtime',(Join-Path $out 'runtime.json')),@('inputs',$inputPath),@('cook',$cookManifestPath))){
        if(Test-Path -LiteralPath $pair[1] -PathType Leaf){$record[$pair[0]]=@{path=$pair[1];sha256=(Get-FightHash $pair[1])}}
    }
    Write-FightJson $resultPath $record
}
if(!$success){throw "Final $Configuration verification failed: $failure See $resultPath"}
[pscustomobject]@{Success=$true;Configuration=$Configuration;Result=$resultPath;Package=$packagePath;Runtime=$runtime.Result}
