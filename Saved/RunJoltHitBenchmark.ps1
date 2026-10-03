$ErrorActionPreference = 'Stop'
$benchRoot = 'C:/Users/singerie/Documents/Unreal Projects/Prophecy'
foreach ($trial in @(@('on','A'), @('off','A'), @('off','B'), @('on','B'))) {
    $label = 'jolt_hits_contact_' + $trial[0] + '_' + $trial[1] + '_20260915'
    $params = @{
        Count=100; Warmup=60; Samples=360; Repeats=1; Label=$label; Methods='NNJoltCrowd';
        FloorOnly=$true; MovementOnly=$true; DuringPhysics=$true; PClassGameThread=$true;
        NoLockIdleReads=$true; FeedbackMode='Original'; JoltWorkerThreads=7;
        QueryTreePaddingCm=40; ApplyNativeQueryPadding=$true; OrtIntraOpThreads=1;
        HitEvents=($trial[0] -eq 'on')
        ContactFloorLiftCm=20
    }
    $launch = & "$benchRoot/Tools/NN/RunSterilePhysicsBenchmark.ps1" @params | Out-String | ConvertFrom-Json
    Write-Output "Started $label PID $($launch.ProcessId)"
    Wait-Process -Id $launch.ProcessId -ErrorAction SilentlyContinue
    if (!(Test-Path -LiteralPath $launch.Report)) { throw "No report for $label" }
    $report = Get-Content -LiteralPath $launch.Report -Raw | ConvertFrom-Json
    if ($report.error) { throw "$label failed: $($report.error)" }
    Write-Output "Completed $label"
}
