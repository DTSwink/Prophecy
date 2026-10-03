$ErrorActionPreference='Stop'
$base=(Resolve-Path -LiteralPath 'C:/Users/singerie/.codex/tmp/ProphecyJolt').ProviderPath
$targets=@(
    @{name='NNPkg-Development-20260909-190730-013';bytes=1026631221;count=59},
    @{name='NNPkg-Development-20260909-193703-769';bytes=1025920420;count=59},
    @{name='NNPkg-Shipping-20260909-192846-832';bytes=820051125;count=44}
)
$report=Join-Path $PSScriptRoot 'RemovedObsoleteNNStages-20260910.json'
if(Test-Path -LiteralPath $report){throw 'Cleanup already recorded.'}
if(Get-Process -Name UnrealEditor,UnrealEditor-Cmd,UnrealPak,GameAnimationSample3,GameAnimationSample3-Win64-Shipping -ErrorAction SilentlyContinue){throw 'Unreal workload must finish first.'}
$records=@()
foreach($target in $targets){
    $parent=Join-Path $base $target.name
    $stage=(Resolve-Path -LiteralPath (Join-Path $parent 'Stage')).ProviderPath
    if($stage -ne (Join-Path $parent 'Stage') -or !$stage.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected cleanup scope.'}
    $ownershipPath=Join-Path $parent 'ownership.json'
    $ownership=Get-Content -LiteralPath $ownershipPath -Raw|ConvertFrom-Json
    $package=Get-Content -LiteralPath $ownership.packageResult -Raw|ConvertFrom-Json
    if($ownership.kind -ne 'ProphecyPackagedNNShortOutputs' -or $ownership.stage -ne $stage -or
       $package.success -ne $true -or $package.stage -ne $stage -or
       (Get-FileHash -LiteralPath $ownershipPath -Algorithm SHA256).Hash -ne $package.shortOutputOwnershipSha256){throw 'Old generated package ownership mismatch.'}
    $entries=@(Get-Item -LiteralPath $stage)+@(Get-ChildItem -LiteralPath $stage -Recurse -Force)
    if(@($entries|Where-Object{($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0}).Count){throw 'Reparse point in cleanup scope.'}
    $files=@($entries|Where-Object{!$_.PSIsContainer})
    if($files.Count -ne $target.count -or ($files|Measure-Object Length -Sum).Sum -ne $target.bytes){throw 'Old stage inventory changed.'}
    foreach($file in $files){
        if(!$file.FullName.StartsWith($stage+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'File outside exact stage.'}
        $records+=@{path=$file.FullName;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
    }
}
$inventory=Join-Path $PSScriptRoot 'ObsoleteNNStageInventory-20260910.json'
if(Test-Path -LiteralPath $inventory){throw 'Inventory already exists.'}
@{purpose='Remove only three obsolete generated stages; retain sources, cooks, immutable package and benchmark reports.';files=$records}|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $inventory -Encoding utf8
foreach($file in $records){
    if((Get-Item -LiteralPath $file.path).Length -ne $file.bytes -or (Get-FileHash -LiteralPath $file.path -Algorithm SHA256).Hash -ne $file.sha256){throw 'File changed before deletion.'}
    Remove-Item -LiteralPath $file.path -Force
}
@{files=$records.Count;bytes=($records|Measure-Object bytes -Sum).Sum;inventory=$inventory;free=(Get-PSDrive C).Free;completedUtc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath $report -Encoding utf8
Get-Content -LiteralPath $report
