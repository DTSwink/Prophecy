<#
.SYNOPSIS
Runs one already-staged current-source NN crowd and validates its complete JSON.
.DESCRIPTION
No build/cook. Development smoke (Count2/Samples60) precedes 100/360 measurement.
Shipping logging is optional; exit zero alone never passes. Only the owned child
may be stopped on timeout. Native padding applies/restores without ExecCmds.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][Alias('Package')][string]$PackageResult,
    [ValidateRange(2,100)][int]$Count=2,
    [ValidateRange(30,3600)][int]$Warmup=60,
    [ValidateRange(60,3600)][int]$Samples=60,
    [ValidateRange(0,32)][int]$JoltWorkerThreads=7,
    [ValidateSet(0,1,2)][int]$OrtIntraOpThreads=0, # 0 preserves packaged settings; 1/2 are Development startup factors.
    [ValidateRange(0,1000)][double]$QueryTreePaddingCm=40,
    [switch]$PClassGameThread,
    [switch]$PauseChaos,
    [ValidateSet('Original','PreparedSerial','PreparedParallel')][string]$FeedbackMode='Original',
    [ValidateRange(30,1800)][int]$TimeoutSeconds=300,
    [string]$Python=''
)
. (Join-Path $PSScriptRoot 'PackagedNN.Common.ps1')
Assert-NNIdle
$FeedbackMode=@{Original='Original';PreparedSerial='PreparedSerial';PreparedParallel='PreparedParallel'}[$FeedbackMode]
if($Samples % 2){throw 'Use an even sample count for exact 30/60Hz cadence totals.'}
if([double]::IsNaN($QueryTreePaddingCm)-or[double]::IsInfinity($QueryTreePaddingCm)){throw 'Padding must be finite.'}
$packagePath=Resolve-NNAbsolute $PackageResult
$package=Get-Content -LiteralPath $packagePath -Raw|ConvertFrom-Json
if($package.kind -ne 'ProphecyPackagedNNCrowd' -or $package.success -ne $true){throw 'Expected a successful packaged NN result.'}
if($OrtIntraOpThreads -ne 0 -and $package.configuration -ne 'Development'){throw 'ORT startup overrides are Development-only; Shipping Game compiles out -ini overrides.'}
$snapshot=Read-NNSnapshot $package.snapshot
$snapshotHash=Get-NNHash $package.snapshot
if($snapshotHash -ne $package.snapshotSha256){throw 'Snapshot changed after packaging.'}
$exe=Resolve-NNAbsolute $package.executable
$expectedName=if($package.configuration -eq 'Shipping'){'GameAnimationSample3-Win64-Shipping.exe'}else{'GameAnimationSample3.exe'}
$exeItem=Get-Item -LiteralPath $exe
if($exeItem.Name -ne $expectedName -or $exeItem.Directory.Name -ne 'Win64' -or $exeItem.Directory.Parent.Name -ne 'Binaries' -or
    -not $exe.StartsWith($package.stage.TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Expected the owned direct staged executable, not a bootstrap or unrelated game.'}
if((Get-NNHash $exe) -ne $package.executableSha256){throw 'Packaged executable changed.'}
foreach($file in @($package.stagedModels)+@($package.stagedNativeDlls)){if((Get-NNHash $file.path) -ne $file.sha256){throw "Staged dependency changed: $($file.path)"}}
if(-not $Python){$command=Get-Command python.exe -ErrorAction Stop;$Python=$command.Source}
$pythonPath=Resolve-NNAbsolute $Python
if($pythonPath -match '\\WindowsApps\\'){throw 'Use a real Python executable, not a Windows Store alias.'}
$validator=Join-Path $PSScriptRoot 'Validate-PackagedNNCrowd.py'
Assert-NNFile $validator
$out=New-NNDirectory (Join-Path (Split-Path -Parent $package.snapshot) 'Runs') "$($package.configuration)-C$Count"
$result=Join-Path $out 'benchmark.json'
$validation=Join-Path $out 'validation.json'
$runnerPath=Join-Path $out 'runner.json'
$stdout=Join-Path $out 'stdout.log';$stderr=Join-Path $out 'stderr.log';$log=Join-Path $out 'Unreal.log'
$padding=$QueryTreePaddingCm.ToString('R',[Globalization.CultureInfo]::InvariantCulture)
$arguments='-nullrhi -RenderOffscreen -nosound -unattended -NoSplash -NoLoadingScreen -NoScreenMessages -NoVSync -nowrite -stdout -FullStdOutLogOutput -ProphecyPhysicsBenchmark'+
    " -PhysicsBenchMethods=NNJoltCrowd -PhysicsBenchCount=$Count -PhysicsBenchWarmup=$Warmup -PhysicsBenchSamples=$Samples -PhysicsBenchRepeats=1"+
    ' -PhysicsBenchFloorOnly -PhysicsBenchMovementOnly -ProphecyJoltDuringPhysics -ProphecyJoltNoLockIdleReads'+
    " -PhysicsBenchFeedbackMode=$FeedbackMode"+
    " -PhysicsBenchJoltWorkerThreads=$JoltWorkerThreads -PhysicsBenchQueryTreePaddingCm=$padding -PhysicsBenchApplyNativeQueryPadding"+
    ' -PhysicsBenchJson="'+$result+'" -abslog="'+$log+'"'
if($PClassGameThread){$arguments+=' -PhysicsBenchPClassGameThread'}
if($PauseChaos){$arguments+=' -PhysicsBenchPauseChaos'}
$ortOverrideTuple=$null
if($OrtIntraOpThreads -ne 0){
    $ortOverrideTuple="(bUseGlobalThreadPool=False,IntraOpNumThreads=$OrtIntraOpThreads,InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)"
    $arguments+=' -ini:Engine:[/Script/NNERuntimeORT.NNERuntimeORTSettings]:GameThreadingOptions='+$ortOverrideTuple
}
$envNames=@('PROPHECY_GAME_DIAGNOSTIC_EXPECTED_PROFILE','PROPHECY_GAME_DIAGNOSTIC_PREFLIGHT')
$oldEnv=@{};foreach($name in $envNames){$oldEnv[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$process=$null;$pidOwned=$null;$exitCode=$null;$timedOut=$false;$killIssued=$false;$validationSuccess=$false
$failures=[Collections.Generic.List[string]]::new()
$started=[DateTime]::UtcNow;$timer=[Diagnostics.Stopwatch]::StartNew()
try {
    foreach($name in $envNames){[Environment]::SetEnvironmentVariable($name,$null,'Process')}
    Assert-NNIdle
    $launch=@{FilePath=$exe;ArgumentList=$arguments;WorkingDirectory=$exeItem.DirectoryName;WindowStyle='Hidden';PassThru=$true;RedirectStandardOutput=$stdout;RedirectStandardError=$stderr}
    $process=Start-Process @launch
    $pidOwned=$process.Id
    try{$process.PriorityClass=[Diagnostics.ProcessPriorityClass]::Normal}catch{$failures.Add("Normal priority failed: $($_.Exception.Message)")}
    while(-not $process.WaitForExit(1000)){
        if($timer.Elapsed.TotalSeconds -ge $TimeoutSeconds){
            $timedOut=$true;$failures.Add("Owned game exceeded $TimeoutSeconds seconds.")
            if(-not $process.HasExited){$process.Kill();$killIssued=$true}
            if(-not $process.WaitForExit(5000)){$failures.Add('Owned process did not complete timeout cleanup.')}
            break
        }
    }
    if($process.HasExited){$exitCode=$process.ExitCode}
} catch {
    $failures.Add("Owned launch/wait failed: $($_.Exception.Message)")
    if($process -and -not $process.HasExited){$process.Kill();$killIssued=$true;$null=$process.WaitForExit(5000)}
} finally {
    foreach($name in $envNames){[Environment]::SetEnvironmentVariable($name,$oldEnv[$name],'Process')}
    $timer.Stop()
}
if($exitCode -ne 0 -or $null -eq $exitCode){$failures.Add("Exit code was not zero: $exitCode")}
if(-not $timedOut -and (Test-Path -LiteralPath $result -PathType Leaf)){
    $validatorArgs=@($validator,'--package',$packagePath,'--result',$result,'--output',$validation,'--configuration',$package.configuration,
        '--count',"$Count",'--warmup',"$Warmup",'--samples',"$Samples",'--workers',"$JoltWorkerThreads",'--padding',$padding,'--feedback-mode',$FeedbackMode,'--ort-intra-op-threads',"$OrtIntraOpThreads")
    if($PClassGameThread){$validatorArgs+='--pclass'}
    if($PauseChaos){$validatorArgs+='--paused'}
    try {
        & $pythonPath @validatorArgs
        $validatorExit=$LASTEXITCODE
        if(Test-Path -LiteralPath $validation -PathType Leaf){
            $validated=Get-Content -LiteralPath $validation -Raw|ConvertFrom-Json
            $validationSuccess=$validatorExit -eq 0 -and $validated.success -eq $true
        }
    } catch {
        $failures.Add("Validator launch/read failed: $($_.Exception.Message)")
    }
    if(-not $validationSuccess){$failures.Add("Complete native JSON validation failed; see $validation")}
} else {$failures.Add('No fresh complete benchmark JSON was produced.')}
$passed=$failures.Count -eq 0 -and $validationSuccess
$record=[ordered]@{
    schema=1;success=$passed;configuration=$package.configuration;count=$Count;warmup=$Warmup;samples=$Samples
    packageResult=$packagePath;packageSha256=(Get-NNHash $packagePath);snapshotSha256=$snapshotHash
    executable=$exe;executableSha256=(Get-NNHash $exe);arguments=$arguments;requestedPriority='Normal'
    pClassGameThread=[bool]$PClassGameThread;pauseChaos=[bool]$PauseChaos;joltWorkerThreads=$JoltWorkerThreads;paddingCm=$QueryTreePaddingCm;feedbackMode=$FeedbackMode
    ortIntraOpThreadsOverride=$OrtIntraOpThreads;ortStartupTuple=$ortOverrideTuple
    processId=$pidOwned;exitCode=$exitCode;timedOut=$timedOut;ownedKillIssued=$killIssued;timeoutSeconds=$TimeoutSeconds
    startedUtc=$started.ToString('o');finishedUtc=[DateTime]::UtcNow.ToString('o');processElapsedSeconds=$timer.Elapsed.TotalSeconds
    nativeResult=$result;nativeResultSha256=$(if(Test-Path -LiteralPath $result -PathType Leaf){Get-NNHash $result}else{$null})
    validation=$validation;validationSuccess=$validationSuccess;validationSha256=$(if(Test-Path -LiteralPath $validation -PathType Leaf){Get-NNHash $validation}else{$null})
    validatorSha256=(Get-NNHash $validator);python=$pythonPath
    stdout=$stdout;stderr=$stderr;failures=@($failures.ToArray())
}
Write-NNJson $runnerPath $record
if($process){$process.Dispose()}
if(-not $passed){throw "Packaged NN run failed. See $runnerPath"}
[pscustomobject]@{Success=$true;Runner=$runnerPath;NativeResult=$result;Validation=$validation}
