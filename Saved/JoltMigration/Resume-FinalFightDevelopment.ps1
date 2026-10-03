<# Recovery for the exact completed Development cook/stage below. No build, cook, stage copy, deletion or asset save.
Only the reviewed one-line verifier path fix may differ from the original candidate inputs. #>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'FinalFight/FinalFight.Common.ps1')
Assert-FightIdle
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).ProviderPath
$recipe=Join-Path $PSScriptRoot 'FinalFight'
$original=Join-Path $recipe 'Packages/Development-20260910-003428-361'
$originalResult=Join-Path $original 'result.json'
$preparation=Join-Path $PSScriptRoot 'FinalFightRecovery-20260910'
$preservationPath=Join-Path $preparation 'original-evidence-and-editor.json'
$originalBuild=Join-Path $preparation 'Build-FinalFightPackage.original.ps1'
$build=Join-Path $recipe 'Build-FinalFightPackage.ps1'
$beforeBuildSha='AA6742A5D86701AA1683ED6A4A440C84A40A21D0350D7D1B7B39D2077DE707A7'
$afterBuildSha='CBA74FC766605C5AAC86C18B279434EB11AAE6DEA020BCF735E3042507010272'
if((Get-FightHash $preservationPath) -ne 'F250689CA76FD9DE2382FB72F83C4B98F75B3ADC5A76777743C810D563206476' -or
    (Get-FightHash $originalBuild) -ne $beforeBuildSha -or (Get-FightHash $build) -ne $afterBuildSha){throw 'Reviewed recovery evidence/verifier revision changed.'}
$preserved=@(Get-Content -LiteralPath $preservationPath -Raw|ConvertFrom-Json)
Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Original evidence and captured Editor binaries'
$prior=Get-Content -LiteralPath $originalResult -Raw|ConvertFrom-Json
if($prior.kind -ne 'ProphecyFinalFightResult' -or $prior.success -ne $false -or $prior.configuration -ne 'Development' -or
    $prior.error -ne 'Required runtime cooked package missing/ambiguous: /ACLPlugin/ACLAnimBoneCompressionSettings' -or
    $prior.output -ne $original -or $prior.package -or $prior.runtime -or $prior.cook){throw 'Expected the exact post-UAT verifier failure.'}
$priorInputs=Get-Content -LiteralPath $prior.inputs.path -Raw|ConvertFrom-Json
if($prior.inputs.path -ne (Join-Path $original 'inputs.json') -or (Get-FightHash $prior.inputs.path) -ne $prior.inputs.sha256 -or
    $priorInputs.projectRoot -ne $root){throw 'Original candidate identity changed.'}
$engineRoot=$priorInputs.engine; $registry=$priorInputs.registry
$editorLog=Get-Content -LiteralPath (Join-Path $original 'EditorBuild.log') -Raw
$uatLog=Get-Content -LiteralPath (Join-Path $original 'UAT.log') -Raw
if($editorLog -notmatch 'Result: Succeeded' -or $uatLog -notmatch 'AutomationTool exiting with ExitCode=0 \(Success\)' -or
    $uatLog -notmatch '\*{10} COOK COMMAND COMPLETED \*{10}' -or $uatLog -notmatch '\*{10} STAGE COMMAND COMPLETED \*{10}' -or
    $uatLog -notmatch '\*{10} PACKAGE COMMAND COMPLETED \*{10}'){throw 'The preserved Editor/UAT logs do not prove completed build/cook/stage/package commands.'}
$freshFiles=@(Get-FightInputs $root $engineRoot $registry)
$oldBuildRecord=@($priorInputs.files|Where-Object{$_.path -eq $build})
$newBuildRecord=@($freshFiles|Where-Object{$_.path -eq $build})
if($oldBuildRecord.Count -ne 1 -or $oldBuildRecord[0].sha256 -ne $beforeBuildSha -or
    $newBuildRecord.Count -ne 1 -or $newBuildRecord[0].sha256 -ne $afterBuildSha){throw 'The single allowed verifier revision does not match the original/current manifests.'}
$expected=@($priorInputs.files|ForEach-Object{if($_.path -eq $build){$newBuildRecord[0]}else{$_}})
Assert-FightRecords $expected $freshFiles 'Candidate inputs, allowing only the pinned one-line verifier revision'
$editorFiles=@($preserved|Where-Object{!$_.path.StartsWith($original+'\',[StringComparison]::OrdinalIgnoreCase)})
$cookStartBound=(Get-Item -LiteralPath $prior.inputs.path).LastWriteTimeUtc
foreach($file in $editorFiles){
    $item=Get-Item -LiteralPath $file.path
    if($item.LastWriteTimeUtc -gt $cookStartBound -or $item.LastWriteTimeUtc -ne ([DateTime]$file.lastWriteTimeUtc).ToUniversalTime()){throw "Editor binary timestamp no longer agrees with the preserved build: $($file.path)"}
}
$ownershipPath=Join-Path $prior.shortOutput 'ownership.json'
$ownership=Get-Content -LiteralPath $ownershipPath -Raw|ConvertFrom-Json
$stage=Join-Path $prior.shortOutput 'Stage'; $cook=Join-Path $prior.shortOutput 'Cook/Windows'
if($ownership.kind -ne 'ProphecyFinalFightOutputs' -or $ownership.configuration -ne 'Development' -or
    $ownership.result -ne $originalResult -or $ownership.stage -ne $stage -or $ownership.cook -ne $cook -or
    $prior.uatArguments -notcontains "-stagingdirectory=$stage" -or $prior.uatArguments -notcontains "-CookOutputDir=$cook"){
    throw 'Original cook/stage ownership does not match the completed UAT command.'
}
$native=Get-FightDependency $root 'Development'
$graph=Get-Content -LiteralPath $registry -Raw|ConvertFrom-Json
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$out=New-FightDirectory (Join-Path $recipe "Packages/Development-Resume-$stamp")
$short=New-FightDirectory (Join-Path ([Environment]::GetFolderPath('UserProfile')) ".codex/tmp/ProphecyJolt/FinalFight-Development-Resume-$stamp")
$inputPath=Join-Path $out 'inputs.json'; $cookManifestPath=Join-Path $out 'cook.json'; $packagePath=Join-Path $out 'package.json'
$resultPath=Join-Path $out 'result.json'; $auditPath=Join-Path $out 'recovery.json'
$started=[DateTime]::UtcNow; $success=$false; $failure=$null; $runtime=$null
try {
    $inputs=[pscustomobject]@{kind='ProphecyFinalFightInputs';projectRoot=$root;engine=$engineRoot;registry=$registry;files=$freshFiles}
    Write-FightJson $inputPath $inputs
    Write-FightJson $auditPath ([ordered]@{kind='ProphecyFinalFightVerifierRecovery';originalResult=$originalResult;originalEvidence=$preserved;
        originalInputs=@{path=$prior.inputs.path;sha256=$prior.inputs.sha256};originalOwnership=@{path=$ownershipPath;sha256=(Get-FightHash $ownershipPath)};
        verifierRevision=@{path=$build;beforeSha256=$beforeBuildSha;afterSha256=$afterBuildSha;originalCopy=$originalBuild;
            change='Replace PowerShell ChangeExtension(relative,null), which retains a trailing dot, with directory plus GetFileNameWithoutExtension. All required package gates remain.'};
        recoveryScript=@{path=$PSCommandPath;sha256=(Get-FightHash $PSCommandPath)};preservation=@{path=$preservationPath;sha256=(Get-FightHash $preservationPath)};
        editorProvenance='The original wrapper successfully compared its in-memory Editor hashes after UAT, before the failing path gate. It did not persist those hashes. These hashes were captured after that failure; unchanged timestamps predate UAT, and the successful build logs plus exact candidate inputs are preserved. This does not reconstruct an unrecorded pre-cook hash.';
        cookAndStageProvenance='Existing successful UAT output; full cook/stage hashes are first persisted by this recovery. No build, cook or stage command is rerun.';
        configuration='Development';stage=$stage;cook=$cook;recordedUtc=$started.ToString('o')})
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
    $cookFiles=Get-FightFileRecords @((Get-FightTree $cook)|ForEach-Object FullName)
    Write-FightJson $cookManifestPath ([ordered]@{directory=$cook;files=$cookFiles;reuseDevelopmentEvidence=$originalResult})
    $executables=@(Get-ChildItem -LiteralPath $stage -File -Recurse -Filter 'GameAnimationSample3.exe'|Where-Object{$_.Directory.Name -eq 'Win64' -and $_.Directory.Parent.Name -eq 'Binaries'})
    if($executables.Count -ne 1){throw 'Expected exactly one direct staged Development executable.'}
    $exe=$executables[0].FullName; $dll=Join-Path $executables[0].DirectoryName $native.dllFilename
    if((Get-FightHash $dll) -ne $native.dllSha256){throw 'Staged Jolt DLL does not match Development.'}
    $stageFiles=Get-FightFileRecords @((Get-FightTree $stage)|ForEach-Object FullName)
    Write-FightJson $packagePath ([ordered]@{kind='ProphecyFinalFightPackage';success=$true;configuration='Development';project=(Join-Path $root 'GameAnimationSample3.uproject');engine=$engineRoot;
        inputs=@{path=$inputPath;sha256=(Get-FightHash $inputPath)};cook=@{path=$cookManifestPath;sha256=(Get-FightHash $cookManifestPath)};
        stage=$stage;stageFiles=$stageFiles;executable=$exe;executableSha256=(Get-FightHash $exe);joltDll=$dll;joltDllSha256=(Get-FightHash $dll);
        editorFiles=$editorFiles;editorBuildArguments=$prior.editorBuildArguments;uatArguments=$prior.uatArguments;shortOutput=$short;registrySha256=(Get-FightHash $registry);
        recovery=@{path=$auditPath;sha256=(Get-FightHash $auditPath)}})
    $runtime=& (Join-Path $recipe 'Run-FinalFightPackage.ps1') -Package $packagePath
    Assert-FightInputs $inputs
    Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Original evidence and captured Editor binaries after runtime'
    Assert-FightRecords $cookFiles (Get-FightFileRecords @((Get-FightTree $cook)|ForEach-Object FullName)) 'Original cooked payload and metadata after runtime'
    $success=$true
} catch {$failure=$_.Exception.Message}
finally {
    $record=[ordered]@{kind='ProphecyFinalFightResult';success=$success;configuration='Development';error=$failure;startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');
        editorBuildArguments=$prior.editorBuildArguments;uatArguments=$prior.uatArguments;output=$out;shortOutput=$short;developmentEvidence=$originalResult;
        package=$null;runtime=$null;inputs=$null;cook=$null;recovery=$null}
    foreach($pair in @(@('package',$packagePath),@('runtime',(Join-Path $out 'runtime.json')),@('inputs',$inputPath),@('cook',$cookManifestPath),@('recovery',$auditPath))){
        if(Test-Path -LiteralPath $pair[1] -PathType Leaf){$record[$pair[0]]=@{path=$pair[1];sha256=(Get-FightHash $pair[1])}}
    }
    Write-FightJson $resultPath $record
}
if(!$success){throw "Development recovery failed: $failure See $resultPath"}
[pscustomobject]@{Success=$true;Configuration='Development';Result=$resultPath;Package=$packagePath;Runtime=$runtime.Result}
