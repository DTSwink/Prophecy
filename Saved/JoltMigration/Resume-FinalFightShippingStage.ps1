<# Exact Shipping recovery after completed build and disk-full staging. Creates a fresh stage and reports.
Never builds targets, cooks, deletes files, or modifies the frozen FinalFight recipe/candidate. #>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'FinalFight/FinalFight.Common.ps1')
Assert-FightIdle
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).ProviderPath
$recipe=Join-Path $PSScriptRoot 'FinalFight'
$original=Join-Path $recipe 'Packages/Shipping-20260910-020434-294'
$capture=Join-Path $PSScriptRoot 'ShippingStageRecovery-20260910/original-shipping-build-evidence.json'
if((Get-FightHash $capture) -ne 'E96D3B0E557C847AECD242D37EDF9CCD028B2825D3E231DDB30D1DE75F724ADA'){throw 'Shipping build/evidence capture changed.'}
$preserved=@(Get-Content -LiteralPath $capture -Raw|ConvertFrom-Json)
Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Completed Shipping build and original evidence'
$originalLog=Get-Content -LiteralPath (Join-Path $original 'UAT.log') -Raw
if($originalLog -notmatch 'Result: Succeeded' -or $originalLog -notmatch '\*{10} BUILD COMMAND COMPLETED \*{10}' -or
    $originalLog -notmatch 'There is not enough space on the disk'){throw 'Expected successful Shipping build followed by the recorded staging disk failure.'}
$developmentEvidence=Join-Path $recipe 'Packages/Development-Resume-20260910-020305-616/result.json'
$development=Get-Content -LiteralPath $developmentEvidence -Raw|ConvertFrom-Json
if($development.kind -ne 'ProphecyFinalFightResult' -or $development.success -ne $true -or $development.configuration -ne 'Development'){throw 'Development verification did not pass.'}
foreach($file in @($development.package,$development.runtime,$development.inputs,$development.cook)){
    if((Get-FightHash $file.path) -ne $file.sha256){throw "Development evidence changed: $($file.path)"}
}
$previousPackage=Get-Content -LiteralPath $development.package.path -Raw|ConvertFrom-Json
$previousRuntime=Get-Content -LiteralPath $development.runtime.path -Raw|ConvertFrom-Json
if($previousRuntime.success -ne $true -or $previousRuntime.exitCode -ne 0){throw 'Development runtime did not pass.'}
foreach($file in $previousRuntime.reports){if((Get-FightHash $file.path) -ne $file.sha256){throw "Development fixture changed: $($file.path)"}}
if((Get-FightHash (Join-Path $original 'inputs.json')) -ne $development.inputs.sha256){throw 'Completed Shipping build used different candidate inputs.'}
$inputs=Get-Content -LiteralPath $development.inputs.path -Raw|ConvertFrom-Json
if($inputs.projectRoot -ne $root){throw 'Candidate project changed.'}
Assert-FightInputs $inputs
$engineRoot=$inputs.engine; $registry=$inputs.registry; $project=Join-Path $root 'GameAnimationSample3.uproject'
$editorFiles=@($previousPackage.editorFiles)
Assert-FightRecords $editorFiles (Get-FightFileRecords @($editorFiles|ForEach-Object path)) 'Cook Editor binaries'
$priorCook=Get-Content -LiteralPath $development.cook.path -Raw|ConvertFrom-Json
$cook=$priorCook.directory; $cookFiles=@($priorCook.files)
Assert-FightRecords $cookFiles (Get-FightFileRecords @((Get-FightTree $cook)|ForEach-Object FullName)) 'Exact Development cook before Shipping stage'
$originalOwnershipPath=@($preserved|Where-Object{$_.path.EndsWith('\ownership.json',[StringComparison]::OrdinalIgnoreCase)})[0].path
$originalOwnership=Get-Content -LiteralPath $originalOwnershipPath -Raw|ConvertFrom-Json
if($originalOwnership.kind -ne 'ProphecyFinalFightOutputs' -or $originalOwnership.configuration -ne 'Shipping' -or
    $originalOwnership.result -ne (Join-Path $original 'result.json') -or $originalOwnership.cook -ne $cook){throw 'Failed Shipping ownership does not identify this cook/candidate.'}
$native=Get-FightDependency $root 'Shipping'
$shippingFiles=@($preserved|Where-Object{$_.path.StartsWith((Join-Path $root 'Binaries/Win64')+'\',[StringComparison]::OrdinalIgnoreCase)})
$receiptPath=Join-Path $root 'Binaries/Win64/GameAnimationSample3-Win64-Shipping.target'
$receipt=Get-Content -LiteralPath $receiptPath -Raw|ConvertFrom-Json
if($shippingFiles.Count -ne 3 -or $receipt.TargetName -ne 'GameAnimationSample3' -or $receipt.Platform -ne 'Win64' -or
    $receipt.Configuration -ne 'Shipping' -or $receipt.TargetType -ne 'Game' -or $receipt.Version.Changelist -ne 51494982 -or
    (Get-FightHash (Join-Path $root "Binaries/Win64/$($native.dllFilename)")) -ne $native.dllSha256){throw 'Completed Shipping receipt/native DLL contract mismatch.'}
$graph=Get-Content -LiteralPath $registry -Raw|ConvertFrom-Json
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$out=New-FightDirectory (Join-Path $recipe "Packages/Shipping-StageResume-$stamp")
$short=New-FightDirectory (Join-Path ([Environment]::GetFolderPath('UserProfile')) ".codex/tmp/ProphecyJolt/FinalFight-Shipping-StageResume-$stamp")
$stage=New-FightDirectory (Join-Path $short 'Stage')
$inputPath=Join-Path $out 'inputs.json'; $cookManifestPath=Join-Path $out 'cook.json'; $packagePath=Join-Path $out 'package.json'
$resultPath=Join-Path $out 'result.json'; $auditPath=Join-Path $out 'recovery.json'
$cookRoots=@($graph.rootPackages|Where-Object{$_ -ne '/Game/testNN'}) -join '+'
# UE ProjectParams.cs:730-734 forces Build=false for -skipbuild; Project.Build returns at BuildProjectCommand.cs:64-67.
# CookCommand.cs:269 returns for -skipcook, preserving the exact Windows cooked payload checked above.
$uatArgs=@('BuildCookRun',"-project=$project",'-noP4','-unattended','-utf8output','-platform=Win64','-clientconfig=Shipping',
    '-skipbuild','-skipcook','-stage','-pak','-iostore','-package','-nodebuginfo','-nocompileeditor',
    '-map=/Engine/Maps/Entry+/Game/testNN',"-AdditionalCookerOptions=-NoDefaultMaps -PACKAGE=$cookRoots",
    "-stagingdirectory=$stage","-CookOutputDir=$cook")
$started=[DateTime]::UtcNow; $success=$false; $failure=$null; $runtime=$null
try {
    Write-FightJson $inputPath $inputs
    Write-FightJson $auditPath ([ordered]@{kind='ProphecyFinalFightShippingStageRecovery';originalShippingEvidence=$preserved;developmentEvidence=@{path=$developmentEvidence;sha256=(Get-FightHash $developmentEvidence)};
        shippingBuildFiles=$shippingFiles;capture=@{path=$capture;sha256=(Get-FightHash $capture)};recoveryScript=@{path=$PSCommandPath;sha256=(Get-FightHash $PSCommandPath)};
        policy='Use the completed Shipping executable/receipt/DLL, exact successful Development candidate/Editor/cook, and a fresh stage. No target build or cook is requested. Original inputs/logs and failed output remain untouched.';
        buildProvenance='Current Shipping hashes captured after the recorded successful build; the original disk-full wrapper did not persist a package/result. Original UAT log and inputs are preserved.';
        uatArguments=$uatArgs;recordedUtc=$started.ToString('o')})
    Write-FightJson (Join-Path $short 'ownership.json') ([ordered]@{kind='ProphecyFinalFightOutputs';configuration='Shipping';result=$resultPath;stage=$stage;cook=$cook;createdUtc=$started.ToString('o')})
    Invoke-FightBatch (Join-Path $engineRoot 'Engine/Build/BatchFiles/RunUAT.bat') $uatArgs (Join-Path $out 'UAT.log')
    Assert-FightInputs $inputs
    Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Original Shipping build/evidence after stage'
    Assert-FightRecords $editorFiles (Get-FightFileRecords @($editorFiles|ForEach-Object path)) 'Cook Editor binaries after stage'
    Assert-FightRecords $cookFiles (Get-FightFileRecords @((Get-FightTree $cook)|ForEach-Object FullName)) 'Exact reused cook including staging metadata'
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
            $stem=Join-Path $cook (Join-Path ([IO.Path]::GetDirectoryName($relative)) ([IO.Path]::GetFileNameWithoutExtension($relative)))
        }
        $present=@(@("$stem.uasset","$stem.umap")|Where-Object{Test-Path -LiteralPath $_ -PathType Leaf})
        if($present.Count -ne 1){throw "Required runtime cooked package missing/ambiguous: $name"}
    }
    Write-FightJson $cookManifestPath ([ordered]@{directory=$cook;files=$cookFiles;reuseDevelopmentEvidence=$developmentEvidence})
    $executables=@(Get-ChildItem -LiteralPath $stage -File -Recurse -Filter 'GameAnimationSample3-Win64-Shipping.exe'|Where-Object{$_.Directory.Name -eq 'Win64' -and $_.Directory.Parent.Name -eq 'Binaries'})
    if($executables.Count -ne 1){throw 'Expected exactly one direct staged Shipping executable.'}
    $exe=$executables[0].FullName; $dll=Join-Path $executables[0].DirectoryName $native.dllFilename
    $builtExe=@($shippingFiles|Where-Object{[IO.Path]::GetExtension($_.path) -eq '.exe'})[0]
    if((Get-FightHash $exe) -ne $builtExe.sha256 -or (Get-FightHash $dll) -ne $native.dllSha256){throw 'Staged Shipping executable/native DLL do not match the completed build.'}
    $stageFiles=Get-FightFileRecords @((Get-FightTree $stage)|ForEach-Object FullName)
    Write-FightJson $packagePath ([ordered]@{kind='ProphecyFinalFightPackage';success=$true;configuration='Shipping';project=$project;engine=$engineRoot;
        inputs=@{path=$inputPath;sha256=(Get-FightHash $inputPath)};cook=@{path=$cookManifestPath;sha256=(Get-FightHash $cookManifestPath)};
        stage=$stage;stageFiles=$stageFiles;executable=$exe;executableSha256=(Get-FightHash $exe);joltDll=$dll;joltDllSha256=(Get-FightHash $dll);
        editorFiles=$editorFiles;editorBuildArguments=@();uatArguments=$uatArgs;shortOutput=$short;registrySha256=(Get-FightHash $registry);
        recovery=@{path=$auditPath;sha256=(Get-FightHash $auditPath)};shippingBuildFiles=$shippingFiles})
    $runtime=& (Join-Path $recipe 'Run-FinalFightPackage.ps1') -Package $packagePath
    Assert-FightInputs $inputs
    Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Original Shipping build/evidence after runtime'
    Assert-FightRecords $editorFiles (Get-FightFileRecords @($editorFiles|ForEach-Object path)) 'Cook Editor binaries after runtime'
    $success=$true
} catch {$failure=$_.Exception.Message}
finally {
    $record=[ordered]@{kind='ProphecyFinalFightResult';success=$success;configuration='Shipping';error=$failure;startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');
        editorBuildArguments=@();uatArguments=$uatArgs;output=$out;shortOutput=$short;developmentEvidence=$developmentEvidence;
        package=$null;runtime=$null;inputs=$null;cook=$null;recovery=$null}
    foreach($pair in @(@('package',$packagePath),@('runtime',(Join-Path $out 'runtime.json')),@('inputs',$inputPath),@('cook',$cookManifestPath),@('recovery',$auditPath))){
        if(Test-Path -LiteralPath $pair[1] -PathType Leaf){$record[$pair[0]]=@{path=$pair[1];sha256=(Get-FightHash $pair[1])}}
    }
    Write-FightJson $resultPath $record
}
if(!$success){throw "Shipping stage recovery failed: $failure See $resultPath"}
[pscustomobject]@{Success=$true;Configuration='Shipping';Result=$resultPath;Package=$packagePath;Runtime=$runtime.Result}
