param(
    [int]$Count=100,
    [int]$Warmup=120,
    [int]$Samples=300,
    [int]$Repeats=3,
    [string]$Label='sterile_100',
    [string]$Methods='',
    [switch]$FloorOnly,
    [switch]$RigAudit,
    [switch]$ManualChaosOnly,
    [switch]$BloodValidation,
    [switch]$MovementOnly,
    [switch]$DuringPhysics,
    [switch]$SerialCompose,
    [switch]$PClassGameThread,
    [switch]$NoLockIdleReads,
    [switch]$PauseChaos,
    [ValidateSet('Original','PreparedSerial','PreparedParallel')][string]$FeedbackMode='Original',
    [ValidateRange(0,32)][int]$JoltWorkerThreads=3,
    [switch]$CsvProfile,
    [double]$QueryTreePaddingCm=5.0,
    [switch]$ApplyNativeQueryPadding,
    [ValidateSet('BelowNormal','Normal')][string]$ProcessPriority='Normal',
    [string]$Project='',
    [ValidateSet(0,1,2)][int]$OrtIntraOpThreads=0,
    [switch]$OrtGlobalThreadPool,
    [string]$Engine='C:/Program Files/Epic Games/UE_5.7'
)
$ErrorActionPreference='Stop'
if (@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {
    throw 'An editor process is already running. This isolated runner will not close it.'
}
if ($BloodValidation -and $Methods -ne 'JoltLive') { throw 'BloodValidation requires the explicit JoltLive method.' }
if ($Methods -in @('JoltLive','JoltCrowd','NNJoltCrowd') -and $Repeats -ne 1) { throw 'The live Jolt fixtures require Repeats=1. Use separate labels/processes for independent repeats.' }
if ($DuringPhysics -and $Methods -notin @('JoltLive','JoltCrowd','NNJoltCrowd')) { throw 'DuringPhysics requires an explicit live Jolt fixture.' }
if ($SerialCompose -and $Methods -notin @('JoltLive','JoltCrowd','NNJoltCrowd')) { throw 'SerialCompose requires an explicit live Jolt fixture.' }
if ($NoLockIdleReads -and $Methods -notin @('JoltLive','JoltCrowd','NNJoltCrowd')) { throw 'NoLockIdleReads requires an explicit live Jolt fixture.' }
if ($PauseChaos -and ($Methods -ne 'NNJoltCrowd' -or -not $FloorOnly -or -not $MovementOnly -or $Repeats -ne 1)) { throw 'PauseChaos is a benchmark-only default Chaos solver maintenance diagnostic requiring sole NNJoltCrowd, FloorOnly, MovementOnly and Repeats=1.' }
if ($FeedbackMode -ne 'Original' -and $Methods -ne 'NNJoltCrowd') { throw 'Prepared feedback requires the explicit NNJoltCrowd fixture.' }
$benchHasJoltWorkers = $PSBoundParameters.ContainsKey('JoltWorkerThreads')
if ($benchHasJoltWorkers -and $Methods -notin @('JoltCrowd','NNJoltCrowd')) { throw 'JoltWorkerThreads requires JoltCrowd or NNJoltCrowd.' }
if ($PClassGameThread -and $Methods -notin @('JoltCrowd','NNJoltCrowd')) { throw 'PClassGameThread is an explicit game-thread placement diagnostic for JoltCrowd or NNJoltCrowd only.' }
if ($CsvProfile -and ($Samples -lt 60 -or $Warmup -lt 30)) { throw 'CsvProfile requires at least 30 warmup and 60 measured frames.' }
$benchHasQueryPadding = $PSBoundParameters.ContainsKey('QueryTreePaddingCm')
if ($ApplyNativeQueryPadding -and ($Methods -ne 'NNJoltCrowd' -or -not $benchHasQueryPadding)) { throw 'ApplyNativeQueryPadding requires sole NNJoltCrowd and explicit QueryTreePaddingCm.' }
if ($benchHasQueryPadding) {
    if ($Methods -notin @('JoltLive','JoltCrowd','NNJoltCrowd')) { throw 'QueryTreePaddingCm is an opt-in diagnostic for an explicit live Jolt fixture.' }
    if ([double]::IsNaN($QueryTreePaddingCm) -or [double]::IsInfinity($QueryTreePaddingCm) -or $QueryTreePaddingCm -lt 0.0 -or $QueryTreePaddingCm -gt 1000.0) { throw 'QueryTreePaddingCm must be finite and between 0 and 1000 cm.' }
}
if ($Label -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Label must contain only letters, digits, underscores or hyphens.' }
$benchRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$benchProject=Join-Path $benchRoot 'GameAnimationSample3.uproject'
if ($Project) {
    $benchProject=(Resolve-Path -LiteralPath $Project).Path
    if ([IO.Path]::GetFileName($benchProject) -ne 'GameAnimationSample3.uproject') { throw 'Use the current project or its owned snapshot.' }
    $benchRoot=Split-Path -Parent $benchProject
}
if (($OrtIntraOpThreads -ne 0 -or $OrtGlobalThreadPool) -and $Methods -ne 'NNJoltCrowd') { throw 'ORT controls require NNJoltCrowd.' }
if ($OrtGlobalThreadPool -and $OrtIntraOpThreads -eq 0) { throw 'Specify the ORT thread count for a shared-pool trial.' }
$benchDir=Join-Path $benchRoot 'Saved/Benchmarks'
New-Item -ItemType Directory -Force -Path $benchDir | Out-Null
$benchJson=Join-Path $benchDir "$Label.json"
if (Test-Path -LiteralPath $benchJson) { throw "Report already exists: $benchJson. Use another label." }
$benchLog=Join-Path $benchDir "$Label.log"
if ($Methods -and $Methods -notmatch '^[a-zA-Z,]+$') { throw 'Methods must be comma-separated native method names.' }
$benchRendering = if ($BloodValidation) { ' -RenderOffscreen -d3d12' } else { ' -nullrhi -RenderOffscreen' }
$benchArgs='"'+$benchProject+'" /Engine/Maps/Entry?game=/Script/Engine.GameModeBase'+
    ' -game'+$benchRendering+' -nosound -unattended -NoSplash -NoLoadingScreen -NoLiveCoding -NoScreenMessages -NoVSync -nowrite'+
    ' -ProphecyPhysicsBenchmark'+
    " -PhysicsBenchCount=$Count -PhysicsBenchWarmup=$Warmup -PhysicsBenchSamples=$Samples -PhysicsBenchRepeats=$Repeats"+
    ' -PhysicsBenchJson="'+$benchJson+'" -abslog="'+$benchLog+'"'
if ($Methods) { $benchArgs+=' -PhysicsBenchMethods="'+$Methods+'"' }
if ($FloorOnly) { $benchArgs+=' -PhysicsBenchFloorOnly' }
if ($RigAudit) { $benchArgs+=' -PhysicsBenchRigAudit' }
if ($ManualChaosOnly) { $benchArgs+=' -PhysicsBenchManualChaosOnly' }
if ($BloodValidation) { $benchArgs+=' -PhysicsBenchBloodValidation' }
if ($MovementOnly) { $benchArgs+=' -PhysicsBenchMovementOnly' }
if ($DuringPhysics) { $benchArgs+=' -ProphecyJoltDuringPhysics' }
if ($SerialCompose) { $benchArgs+=' -ProphecyJoltSerialCompose' }
if ($PClassGameThread) { $benchArgs+=' -PhysicsBenchPClassGameThread' }
if ($NoLockIdleReads) { $benchArgs+=' -ProphecyJoltNoLockIdleReads' }
if ($PauseChaos) { $benchArgs+=' -PhysicsBenchPauseChaos' }
if ($Methods -eq 'NNJoltCrowd') { $benchArgs+=' -PhysicsBenchFeedbackMode=' + $FeedbackMode }
$benchOrtTuple=$null
if ($OrtIntraOpThreads -ne 0) {
    # UnrealEditor -game selects EditorThreadingOptions. Match packaged settings explicitly.
    $benchOrtGlobal=if ($OrtGlobalThreadPool) { 'True' } else { 'False' }
    $benchOrtTuple="(bUseGlobalThreadPool=$benchOrtGlobal,IntraOpNumThreads=$OrtIntraOpThreads,InterOpNumThreads=1,ExecutionMode=SEQUENTIAL)"
    $benchArgs+=' -ini:Engine:[/Script/NNERuntimeORT.NNERuntimeORTSettings]:EditorThreadingOptions='+$benchOrtTuple
}
if ($benchHasJoltWorkers) { $benchArgs+=' -PhysicsBenchJoltWorkerThreads=' + $JoltWorkerThreads }
$benchStartupCommands = [System.Collections.Generic.List[string]]::new()
if ($benchHasQueryPadding) {
    $benchPaddingText = $QueryTreePaddingCm.ToString('R', [System.Globalization.CultureInfo]::InvariantCulture)
    if ($ApplyNativeQueryPadding) { $benchArgs += ' -PhysicsBenchApplyNativeQueryPadding' }
    else { $benchStartupCommands.Add('p.aabbtree.DynamicTreeBoundingBoxPadding ' + $benchPaddingText) }
    # The native report independently reads the CVar and checks this requested value.
    $benchArgs += ' -PhysicsBenchQueryTreePaddingCm=' + $benchPaddingText
}
if ($CsvProfile) {
    # Finish the native CSV before the benchmark exits; CSV rows carry explicit measured/frame markers.
    $benchCsvFrames = $Warmup + $Samples - 20
    $benchStartupCommands.Add('csv.DetailedTickContext 1')
    $benchStartupCommands.Add('csvprofile frames=' + $benchCsvFrames)
    $benchArgs += ' -csvCompression=0 -csvCategories=Basic,Exclusive,Physics,PhysicsVerbose,ChaosPhysicsTimers,Ticks,Animation'
}
if ($benchStartupCommands.Count) {
    # One quoted ExecCmds argument preserves both diagnostics; all inserted values are numeric.
    $benchArgs += ' -ExecCmds="' + ($benchStartupCommands -join ',') + '"'
}
$benchProcess=Start-Process -FilePath (Join-Path $Engine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe') -ArgumentList $benchArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $benchDir "$Label.stdout.log") -RedirectStandardError (Join-Path $benchDir "$Label.stderr.log")
# Background priority placed the measured game thread on efficiency cores in the retained
# September 9 CPU traces. Normal is the ordinary game-process policy; BelowNormal stays explicit
# for diagnostics. No processor affinity or machine power policy is changed by this launcher.
# PClassGameThread asks the native benchmark to temporarily constrain/restore only its game thread.
$benchProcess.PriorityClass=$ProcessPriority
[pscustomobject]@{ProcessId=$benchProcess.Id;Report=$benchJson;Log=$benchLog;Priority=$ProcessPriority;PClassGameThread=[bool]$PClassGameThread;QueryTreePaddingRequested=$benchHasQueryPadding;QueryTreePaddingCm=$(if ($benchHasQueryPadding) { $QueryTreePaddingCm } else { $null });Rendering=$benchRendering.Trim();OrtStartupTuple=$benchOrtTuple;Project=$benchProject} | ConvertTo-Json
