<# Runs only the direct staged game owned by package.json. No build, cook, asset save or performance run. #>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Package,[ValidateRange(30,1800)][int]$TimeoutSeconds=300)
. (Join-Path $PSScriptRoot 'FinalFight.Common.ps1')
Assert-FightIdle
$Package=Resolve-FightPath $Package
$data=Get-Content -LiteralPath $Package -Raw|ConvertFrom-Json
if($data.kind -ne 'ProphecyFinalFightPackage' -or $data.success -ne $true){throw 'Expected successful final fight package metadata.'}
if((Get-FightHash $data.inputs.path) -ne $data.inputs.sha256 -or (Get-FightHash $data.cook.path) -ne $data.cook.sha256){throw 'Package input/cook metadata changed.'}
$inputs=Get-Content -LiteralPath $data.inputs.path -Raw|ConvertFrom-Json
Assert-FightInputs $inputs
Assert-FightRecords $data.stageFiles (Get-FightFileRecords @((Get-FightTree $data.stage)|ForEach-Object FullName)) 'Staged package'
$exe=Get-Item -LiteralPath $data.executable
$expected=if($data.configuration -eq 'Shipping'){'GameAnimationSample3-Win64-Shipping.exe'}else{'GameAnimationSample3.exe'}
if($exe.Name -ne $expected -or $exe.Directory.Name -ne 'Win64' -or $exe.Directory.Parent.Name -ne 'Binaries' -or
    !$exe.FullName.StartsWith($data.stage.TrimEnd('\','/')+'\',[StringComparison]::OrdinalIgnoreCase) -or
    (Get-FightHash $exe.FullName) -ne $data.executableSha256 -or (Get-FightHash $data.joltDll) -ne $data.joltDllSha256){throw 'Executable or native DLL provenance mismatch.'}
$out=Split-Path -Parent $Package
$result=Join-Path $out 'runtime.json'; $stdout=Join-Path $out 'runtime-stdout.log'; $stderr=Join-Path $out 'runtime-stderr.log'; $log=Join-Path $out 'runtime-Unreal.log'
$validationDir=Join-Path $data.shortOutput 'Validation'
foreach($path in @($result,$stdout,$stderr,$log,$validationDir)){if(Test-Path -LiteralPath $path){throw "Runtime output already exists: $path"}}
$arguments='/Engine/Maps/Entry -nullrhi -unattended -nosound -nosplash -nowrite -stdout -FullStdOutLogOutput'+
    ' -JoltFightValidationDir="'+$validationDir+'" -abslog="'+$log+'"'
$process=$null; $code=$null; $timedOut=$false; $killed=$false; $passed=$false; $failure=$null; $aggregate=$null; $reports=@(); $generatedStageFiles=@(); $started=[DateTime]::UtcNow
try {
    Assert-FightIdle
    $process=Start-Process -FilePath $exe.FullName -ArgumentList $arguments -WorkingDirectory $exe.DirectoryName -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if(!$process.WaitForExit($TimeoutSeconds*1000)){
        $timedOut=$true
        if(!$process.HasExited){$process.Kill();$killed=$true;$null=$process.WaitForExit(5000)}
        throw 'Owned validation process timed out.'
    }
    $process.Refresh(); $code=$process.ExitCode
    if($code -ne 0){throw "Validation process exit was $code, not zero."}
    $aggregatePath=Join-Path $validationDir 'validation.json'
    $aggregate=Get-Content -LiteralPath $aggregatePath -Raw|ConvertFrom-Json
    if($aggregate.success -isnot [bool] -or !$aggregate.success -or $aggregate.error -ne '' -or $aggregate.editor -ne $false -or
        $aggregate.configuration -ne $data.configuration -or $aggregate.fixtures.Count -ne 3 -or !$aggregate.saved_floor.static){throw 'Aggregate functional/configuration/floor validation failed.'}
    $commands=@('Prophecy.Jolt.SwordFixture','Prophecy.Jolt.SwordContactFixture','Prophecy.Jolt.SwordFighterContactFixture')
    for($index=0;$index -lt 3;$index++){
        $path=Join-Path $validationDir "fixture_$index.json"
        $row=$aggregate.fixtures[$index]
        if($row.command -ne $commands[$index] -or $row.success -ne $true -or [IO.Path]::GetFullPath($row.report) -ne [IO.Path]::GetFullPath($path)){throw 'Aggregate fixture identity mismatch.'}
        $fixture=Get-Content -LiteralPath $path -Raw|ConvertFrom-Json
        if($fixture.success -isnot [bool] -or !$fixture.success -or $fixture.error -ne '' -or $fixture.assets_saved -ne $false -or $fixture.asset_preflight_passed -ne $true){throw "Fixture failed: $($commands[$index])"}
        if($index -lt 2){
            $count=if($index -eq 0){28}else{10}
            if($fixture.stage -ne 'complete' -or @($fixture.checks).Count -ne $count -or @($fixture.checks|Where-Object{$_.passed -ne $true}).Count){throw 'Incomplete sword lifecycle/floor-contact checks.'}
        } else {
            if(!$fixture.all_45_initial_native_states_match -or !$fixture.only_sword_victim_filter_differs -or
                !($fixture.max_contact_control_head_position_delta_cm -gt 0.05) -or !($fixture.max_contact_control_head_velocity_delta_cm_s -gt 1.0)){throw 'Sword/victim causal control failed.'}
            foreach($trial in @($fixture.authored_contact_on,$fixture.control_contact_off)){
                if($trial.stage -ne 'complete' -or !$trial.shared_steps_and_cleanup_passed -or @($trial.samples).Count -ne 12){throw 'Incomplete contact trial or cleanup.'}
            }
        }
        $reports+=@{path=$path;sha256=(Get-FightHash $path)}
    }
    $reports+=@{path=$aggregatePath;sha256=(Get-FightHash $aggregatePath)}
    Assert-FightInputs $inputs
    Assert-FightRecords $data.stageFiles (Get-FightFileRecords @($data.stageFiles|ForEach-Object path)) 'Known staged payload after runtime'
    $knownStage=@{}; foreach($file in $data.stageFiles){$knownStage[$file.path]=$true}
    foreach($file in (Get-FightTree $data.stage)){
        if(!$knownStage.ContainsKey($file.FullName)){
            $relative=$file.FullName.Substring($data.stage.Length+1).Replace('\','/')
            if($relative -notmatch '^(GameAnimationSample3|Engine)/Saved/'){throw "Unexpected file appeared alongside staged payload: $relative"}
            $generatedStageFiles+=Get-FightFileRecords @($file.FullName)
        }
    }
    $passed=$true
} catch {$failure=$_.Exception.Message}
finally {
    $pidOwned=if($process){$process.Id}else{$null}
    if($process){$process.Dispose()}
    Write-FightJson $result ([ordered]@{kind='ProphecyFinalFightRuntime';success=$passed;error=$failure;configuration=$data.configuration;package=$Package;packageSha256=(Get-FightHash $Package);
        executable=$exe.FullName;executableSha256=$data.executableSha256;arguments=$arguments;processId=$pidOwned;exitCode=$code;timedOut=$timedOut;ownedKillIssued=$killed;
        startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');reports=$reports;runtimeGeneratedStageFiles=@($generatedStageFiles);
        ensureCountDelta=$(if($aggregate){$aggregate.ensure_count_delta}else{$null});ensurePolicy='Recorded separately; functional success does not claim an ensure-free process.';
        stdout=$stdout;stderr=$stderr;unrealLog=$log})
}
if(!$passed){throw "Final fight runtime failed: $failure See $result"}
[pscustomobject]@{Success=$true;Result=$result;EnsureCountDelta=$aggregate.ensure_count_delta}
