<# Runtime-only retry of the exact Shipping package with a separate saved Engine.ini selecting Entry.
No build, cook, staging, project configuration change, or modification of prior reports. #>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'FinalFight/FinalFight.Common.ps1')
Assert-FightIdle
$recipe=Join-Path $PSScriptRoot 'FinalFight'
$original=Join-Path $recipe 'Packages/Shipping-StageResume-20260910-021815-430'
$prepare=Join-Path $PSScriptRoot 'ShippingRuntimeRecovery-20260910'
$capture=Join-Path $prepare 'original-shipping-runtime-evidence.json'
$runner=Join-Path $prepare 'Run-FinalFightPackage-EngineIni.ps1'
if((Get-FightHash $capture) -ne '5F6BBB5DD40DCE3A1D9FB4DB164719A3901078473987D990B51CD66DBB46BC5D' -or
    (Get-FightHash $runner) -ne '287DCF7F38E92D2333C0358230054EF4D1A03934831FC3DD8F20BB2DECD20EF1' -or
    (Get-FightHash (Join-Path $prepare 'Run-FinalFightPackage.original.ps1')) -ne '7463CE8CFA943D8FA3FFB18D858641DE052ED060E7AF23F8947830661BBEBAA5'){
    throw 'Reviewed runtime-only recovery evidence or runner changed.'
}
$preserved=@(Get-Content -LiteralPath $capture -Raw|ConvertFrom-Json)
Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Original Shipping package and runtime failure'
$originalPackage=Join-Path $original 'package.json'
$package=Get-Content -LiteralPath $originalPackage -Raw|ConvertFrom-Json
$oldRuntime=Get-Content -LiteralPath (Join-Path $original 'runtime.json') -Raw|ConvertFrom-Json
$oldResult=Get-Content -LiteralPath (Join-Path $original 'result.json') -Raw|ConvertFrom-Json
if($package.kind -ne 'ProphecyFinalFightPackage' -or $package.success -ne $true -or $package.configuration -ne 'Shipping' -or
    $oldRuntime.success -ne $false -or $oldRuntime.exitCode -ne 3 -or $oldRuntime.packageSha256 -ne (Get-FightHash $originalPackage) -or
    $oldResult.success -ne $false -or $oldResult.configuration -ne 'Shipping'){throw 'Expected the exact successful stage and failed Shipping startup.'}
if((Get-Content -LiteralPath (Join-Path $original 'UAT.log') -Raw) -notmatch 'AutomationTool exiting with ExitCode=0 \(Success\)' -or
    (Get-Content -LiteralPath (Join-Path $original 'runtime-stdout.log') -Raw) -notmatch "map specified on the commandline '/Game/mybasic' could not be found"){
    throw 'Preserved logs do not identify the successful stage and default-map startup error.'
}
foreach($file in @($package.inputs,$package.cook)){if((Get-FightHash $file.path) -ne $file.sha256){throw "Package metadata changed: $($file.path)"}}
$inputs=Get-Content -LiteralPath $package.inputs.path -Raw|ConvertFrom-Json
Assert-FightInputs $inputs
Assert-FightRecords $package.editorFiles (Get-FightFileRecords @($package.editorFiles|ForEach-Object path)) 'Cook Editor binaries'
Assert-FightRecords $package.shippingBuildFiles (Get-FightFileRecords @($package.shippingBuildFiles|ForEach-Object path)) 'Completed Shipping binaries'
Assert-FightRecords $package.stageFiles (Get-FightFileRecords @((Get-FightTree $package.stage)|ForEach-Object FullName)) 'Exact original stage before runtime'
$cook=Get-Content -LiteralPath $package.cook.path -Raw|ConvertFrom-Json
Assert-FightRecords $cook.files (Get-FightFileRecords @((Get-FightTree $cook.directory)|ForEach-Object FullName)) 'Exact original cooked payload'
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')
$out=New-FightDirectory (Join-Path $recipe "Packages/Shipping-RuntimeResume-$stamp")
$short=New-FightDirectory (Join-Path ([Environment]::GetFolderPath('UserProfile')) ".codex/tmp/ProphecyJolt/FinalFight-Shipping-RuntimeResume-$stamp")
$iniPath=Join-Path $short 'Engine.ini'; $packagePath=Join-Path $out 'package.json'; $auditPath=Join-Path $out 'recovery.json'; $resultPath=Join-Path $out 'result.json'
$iniBytes=[Text.UTF8Encoding]::new($false).GetBytes("[/Script/EngineSettings.GameMapsSettings]`nGameDefaultMap=/Engine/Maps/Entry.Entry`n")
$stream=[IO.File]::Open($iniPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
try{$stream.Write($iniBytes,0,$iniBytes.Length)}finally{$stream.Dispose()}
$iniRecord=@{path=$iniPath;sha256=(Get-FightHash $iniPath)}
$started=[DateTime]::UtcNow; $success=$false; $failure=$null; $runtime=$null
try {
    Write-FightJson $auditPath ([ordered]@{kind='ProphecyFinalFightShippingRuntimeRecovery';originalEvidence=$preserved;originalPackage=@{path=$originalPackage;sha256=(Get-FightHash $originalPackage)};
        previousRecovery=$package.recovery;capture=@{path=$capture;sha256=(Get-FightHash $capture)};runtimeEngineIni=$iniRecord;
        runner=@{path=$runner;sha256=(Get-FightHash $runner);originalSha256='7463CE8CFA943D8FA3FFB18D858641DE052ED060E7AF23F8947830661BBEBAA5';
            changes='Adjust Common.ps1 relative import; require the exact Shipping Engine.ini contents/hash; append -EngineINI; verify its hash after process exit; record its identity. All existing payload, process-exit, fixture and ensure checks remain.'};
        recoveryScript=@{path=$PSCommandPath;sha256=(Get-FightHash $PSCommandPath)};
        sourceSupport='UE5.7 ConfigCacheIni.cpp:6017-6041 accepts EngineINI= unconditionally; ConfigContext.cpp:74-80 enables saved configs, 1137-1148 reads them and 1227 applies them after defaults. ConfigCacheIni.cpp:6299-6305 applies saved configs even after BinaryConfig load. Shipping-disabled -ini: overrides are a separate path.';
        policy='Only this runtime saved-config layer selects Entry; source project defaults, cooked payload, staged payload and existing evidence remain unchanged. No UAT or target build.';recordedUtc=$started.ToString('o')})
    $package.shortOutput=$short
    $package.recovery=@{path=$auditPath;sha256=(Get-FightHash $auditPath)}
    $package|Add-Member -NotePropertyName runtimeEngineIni -NotePropertyValue $iniRecord
    Write-FightJson $packagePath $package
    $runtime=& $runner -Package $packagePath
    if((Get-FightHash $iniPath) -ne $iniRecord.sha256){throw 'Runtime Engine.ini changed.'}
    Assert-FightInputs $inputs
    Assert-FightRecords $preserved (Get-FightFileRecords @($preserved|ForEach-Object path)) 'Original package and failure evidence after runtime'
    Assert-FightRecords $package.editorFiles (Get-FightFileRecords @($package.editorFiles|ForEach-Object path)) 'Cook Editor binaries after runtime'
    Assert-FightRecords $package.shippingBuildFiles (Get-FightFileRecords @($package.shippingBuildFiles|ForEach-Object path)) 'Shipping binaries after runtime'
    Assert-FightRecords $cook.files (Get-FightFileRecords @((Get-FightTree $cook.directory)|ForEach-Object FullName)) 'Cooked payload after runtime'
    $success=$true
} catch {$failure=$_.Exception.Message}
finally {
    $record=[ordered]@{kind='ProphecyFinalFightResult';success=$success;configuration='Shipping';error=$failure;startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');
        editorBuildArguments=@();uatArguments=@();output=$out;shortOutput=$short;developmentEvidence=$oldResult.developmentEvidence;
        package=$null;runtime=$null;inputs=$package.inputs;cook=$package.cook;recovery=$null;runtimeEngineIni=$iniRecord;
        runtimeEngineIniAfterSha256=$(if(Test-Path -LiteralPath $iniPath -PathType Leaf){Get-FightHash $iniPath}else{$null})}
    foreach($pair in @(@('package',$packagePath),@('runtime',(Join-Path $out 'runtime.json')),@('recovery',$auditPath))){
        if(Test-Path -LiteralPath $pair[1] -PathType Leaf){$record[$pair[0]]=@{path=$pair[1];sha256=(Get-FightHash $pair[1])}}
    }
    Write-FightJson $resultPath $record
}
if(!$success){throw "Shipping runtime recovery failed: $failure See $resultPath"}
[pscustomobject]@{Success=$true;Configuration='Shipping';Result=$resultPath;Package=$packagePath;Runtime=$runtime.Result}
