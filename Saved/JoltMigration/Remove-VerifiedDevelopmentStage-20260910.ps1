[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ShippingResult)
. (Join-Path $PSScriptRoot 'FinalFight/FinalFight.Common.ps1')
Assert-FightIdle
$shipping=Get-Content -LiteralPath $ShippingResult -Raw|ConvertFrom-Json
if($shipping.kind -ne 'ProphecyFinalFightResult' -or $shipping.success -ne $true -or $shipping.configuration -ne 'Shipping'){throw 'Final Shipping validation must pass before cleanup.'}
foreach($item in @($shipping.package,$shipping.runtime)){
    if((Get-FightHash $item.path) -ne $item.sha256){throw 'Shipping evidence changed.'}
}
$runtime=Get-Content -LiteralPath $shipping.runtime.path -Raw|ConvertFrom-Json
if(!$runtime.success -or $runtime.exitCode -ne 0){throw 'Shipping runtime did not pass.'}
$devResult=Join-Path $PSScriptRoot 'FinalFight/Packages/Development-Resume-20260910-020305-616/result.json'
$dev=Get-Content -LiteralPath $devResult -Raw|ConvertFrom-Json
if(!$dev.success -or (Get-FightHash $dev.package.path) -ne $dev.package.sha256){throw 'Development evidence mismatch.'}
$package=Get-Content -LiteralPath $dev.package.path -Raw|ConvertFrom-Json
$expected='C:\Users\singerie\.codex\tmp\ProphecyJolt\FinalFight-Development-20260910-003428-361\Stage'
$stage=(Resolve-Path -LiteralPath $package.stage).ProviderPath
if($stage -ne $expected -or $package.configuration -ne 'Development'){throw 'Unexpected cleanup scope.'}
$shippingPackage=Get-Content -LiteralPath $shipping.package.path -Raw|ConvertFrom-Json
if($shippingPackage.stage -eq $stage){throw 'Shipping must retain its own package.'}
$files=@($package.stageFiles)
Assert-FightRecords $files (Get-FightFileRecords @((Get-FightTree $stage)|ForEach-Object FullName)) 'Verified Development stage before cleanup'
foreach($file in $files){if(!$file.path.StartsWith($stage+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'File outside exact Development stage.'}}
$report=Join-Path $PSScriptRoot 'RemovedVerifiedDevelopmentStage-20260910.json'
if(Test-Path -LiteralPath $report){throw 'Cleanup already recorded.'}
foreach($file in $files){Remove-Item -LiteralPath $file.path -Force}
Write-FightJson $report ([ordered]@{kind='ProphecyGeneratedStageCleanup';purpose='Both configurations passed; remove duplicate Development stage and retain Shipping, shared cook and all evidence.';
    developmentResult=$devResult;shippingResult=$ShippingResult;stage=$stage;inventory=$dev.package;files=$files.Count;bytes=($files|Measure-Object bytes -Sum).Sum;
    completedUtc=[DateTime]::UtcNow.ToString('o');free=(Get-PSDrive C).Free})
Get-Content -LiteralPath $report
