$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/PackagedNN.Common.ps1')
Assert-NNIdle
$root=Resolve-NNAbsolute (Join-Path $PSScriptRoot '../..')
$snapshotRoot=Join-Path $PSScriptRoot 'NNCrowd-20260909-144331-647'
$oldPath=Join-Path $snapshotRoot 'snapshot-r5.json'
$newPath=Join-Path $snapshotRoot 'snapshot-r6.json'
if(Test-Path -LiteralPath $newPath){throw 'R6 already exists.'}
$data=Read-NNSnapshot $oldPath
$oldHash=Get-NNHash $oldPath
if($oldHash -ne '0699A1988BC17AB883B297D897F992583F5D29EF6FC1FFA9BBA722B07BD2CD3A'){throw 'Unexpected R5 manifest.'}
$draftRoot=Join-Path $PSScriptRoot 'ORTThreadingR6Draft'
$relative='Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp'
$source=Join-Path $root $relative
$target=[IO.Path]::GetFullPath((Join-Path $data.projectDirectory $relative))
if(-not $target.StartsWith($data.projectDirectory+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Snapshot target escaped Project.'}
$entry=@($data.inputs|Where-Object relativePath -eq $relative)
if($entry.Count -ne 1 -or (Get-NNHash $target) -ne '958217AD00DA9ACD4632238B4A1F85F1C8B0F8C381DE480925C8FA8A61A674FE'){throw 'R5 source baseline differs.'}
$draft=[IO.File]::ReadAllText((Join-Path $draftRoot 'ProphecyPhysicsBenchmarkNNJolt.cpp')).Replace("`r`n","`n")
if([IO.File]::ReadAllText($source).Replace("`r`n","`n") -cne $draft){throw 'Main source differs from reviewed R6 draft.'}
foreach($name in @('Run-NNCrowdPackage.ps1','Validate-PackagedNNCrowd.py')){
    $current=[IO.File]::ReadAllText((Join-Path $PSScriptRoot ('PackagedNNCrowdDraft/'+$name))).Replace("`r`n","`n")
    $expected=[IO.File]::ReadAllText((Join-Path $draftRoot $name)).Replace("`r`n","`n")
    if($current -cne $expected){throw 'Active runner/validator differs from reviewed R6 draft.'}
}
$archive=Join-Path $snapshotRoot 'SourceArchive-r5'
if(Test-Path -LiteralPath $archive){throw 'R5 source archive already exists.'}
New-Item -ItemType Directory -Path $archive|Out-Null
$archived=Join-Path $archive 'ProphecyPhysicsBenchmarkNNJolt.cpp.txt'
$oldSourceHash=Get-NNHash $target
$newSourceHash=Get-NNHash $source
Copy-Item -LiteralPath $target -Destination $archived
if((Get-NNHash $archived) -ne $oldSourceHash){throw 'Source archive mismatch.'}
Copy-Item -LiteralPath $source -Destination $target
(Get-Item -LiteralPath $target).LastWriteTimeUtc=[DateTime]::UtcNow
if((Get-NNHash $target) -ne $newSourceHash -or (Get-NNHash $source) -ne $newSourceHash){throw 'Source changed during copy.'}
$entry[0].source=$source
$entry[0].sourceSha256=$newSourceHash
$entry[0].snapshotSha256=$newSourceHash
$entry[0].bytes=(Get-Item -LiteralPath $source).Length
$entry[0].sourceLastWriteUtc=(Get-Item -LiteralPath $source).LastWriteTimeUtc.ToString('o')
foreach($input in $data.inputs){if((Get-NNHash (Join-Path $data.projectDirectory $input.relativePath)) -ne $input.snapshotSha256){throw 'Revised snapshot input mismatch.'}}
$data.createdUtc=[DateTime]::UtcNow.ToString('o')
$data.revision=[ordered]@{
    number=6;predecessor=$oldPath;predecessorSha256=$oldHash
    reason='Read-only ORT selected-settings capture before/after NN model creation, outside measurement; supports explicit Development startup intra-op 1/2 experiments with unchanged other runtime settings.'
    changedInputs=@([ordered]@{relativePath=$relative;beforeSha256=$oldSourceHash;afterSha256=$newSourceHash;archivedSource=$archived})
    reviewedManifest=(Join-Path $draftRoot 'FinalManifest.json');reviewedManifestSha256=(Get-NNHash (Join-Path $draftRoot 'FinalManifest.json'))
    validator=(Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py');validatorSha256=(Get-NNHash (Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py'))
    scope='One diagnostic benchmark source file replaced. Same1304inputs and identical copied config/assets/models; no ORT setting changed by this source revision. R5 source/validator/comparator/runner bytes and staged executables remain historical controls.'
}
Write-NNJson $newPath $data
$null=Read-NNSnapshot $newPath
[pscustomobject]@{Snapshot=$newPath;ChangedFiles=1;Files=$data.inputs.Count;Sha256=(Get-NNHash $newPath)}|ConvertTo-Json
