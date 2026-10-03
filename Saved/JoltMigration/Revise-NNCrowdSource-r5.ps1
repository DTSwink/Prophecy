$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/PackagedNN.Common.ps1')
Assert-NNIdle
$root=Resolve-NNAbsolute (Join-Path $PSScriptRoot '../..')
$snapshotRoot=Join-Path $PSScriptRoot 'NNCrowd-20260909-144331-647'
$oldPath=Join-Path $snapshotRoot 'snapshot-r4.json'
$newPath=Join-Path $snapshotRoot 'snapshot-r5.json'
if(Test-Path -LiteralPath $newPath){throw 'R5 already exists.'}
$data=Read-NNSnapshot $oldPath
$oldHash=Get-NNHash $oldPath
if($oldHash -ne '6F574706F36DBDE8E99472870C175E0D273F6C647ECEBF5E2552BE6C71AB64B6'){throw 'Unexpected R4 identity.'}
$draftRoot=Join-Path $PSScriptRoot 'CallbackMeshRestoreDraft'
$evidence=Get-Content (Join-Path $draftRoot 'Evidence.json') -Raw|ConvertFrom-Json
$relativePaths=@($evidence.files.path)+@('Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp')
foreach($entry in $evidence.files){
    if((Get-NNHash (Join-Path $data.projectDirectory $entry.path)) -ne $entry.active_sha256){throw 'R4 source differs from restoration baseline.'}
    $current=[IO.File]::ReadAllText((Join-Path $root $entry.path)).Replace("`r`n","`n")
    $draft=[IO.File]::ReadAllText((Join-Path $draftRoot $entry.path)).Replace("`r`n","`n")
    if($current -cne $draft){throw 'Main source differs from reviewed restoration draft.'}
}
$policyRelative=$relativePaths[-1]
$policy=Get-Content (Join-Path $PSScriptRoot 'PackagedR4AuditDraft/CollisionPolicyDraftBaseline.json') -Raw|ConvertFrom-Json
if((Get-NNHash (Join-Path $data.projectDirectory $policyRelative)) -ne $policy.sourceSha256){throw 'R4 response export baseline differs.'}
$current=[IO.File]::ReadAllText((Join-Path $root $policyRelative)).Replace("`r`n","`n")
$draft=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'PackagedR4AuditDraft/ProphecyPhysicsBenchmarkNNJolt.cpp')).Replace("`r`n","`n")
if($current -cne $draft){throw 'Main response export differs from reviewed draft.'}
$archive=Join-Path $snapshotRoot 'SourceArchive-r4'
if(Test-Path -LiteralPath $archive){throw 'Source archive already exists.'}
New-Item -ItemType Directory -Path $archive|Out-Null
$changes=@()
foreach($relative in $relativePaths){
    $source=Join-Path $root $relative
    $target=[IO.Path]::GetFullPath((Join-Path $data.projectDirectory $relative))
    if(-not $target.StartsWith($data.projectDirectory+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Snapshot target escaped Project.'}
    $entry=@($data.inputs|Where-Object relativePath -eq $relative)
    if($entry.Count -ne 1){throw 'Missing unique frozen source input.'}
    $oldSourceHash=Get-NNHash $target
    $newSourceHash=Get-NNHash $source
    $archived=Join-Path $archive ((Split-Path -Leaf $relative)+'.txt')
    Copy-Item -LiteralPath $target -Destination $archived
    if((Get-NNHash $archived) -ne $oldSourceHash){throw 'Archive mismatch.'}
    Copy-Item -LiteralPath $source -Destination $target
    (Get-Item -LiteralPath $target).LastWriteTimeUtc=[DateTime]::UtcNow
    if((Get-NNHash $target) -ne $newSourceHash -or (Get-NNHash $source) -ne $newSourceHash){throw 'Source changed during replacement.'}
    $entry[0].source=$source
    $entry[0].sourceSha256=$newSourceHash
    $entry[0].snapshotSha256=$newSourceHash
    $entry[0].bytes=(Get-Item -LiteralPath $source).Length
    $entry[0].sourceLastWriteUtc=(Get-Item -LiteralPath $source).LastWriteTimeUtc.ToString('o')
    $changes+=[pscustomobject]@{relativePath=$relative;beforeSha256=$oldSourceHash;afterSha256=$newSourceHash;archivedSource=$archived}
}
foreach($entry in $data.inputs){if((Get-NNHash (Join-Path $data.projectDirectory $entry.relativePath)) -ne $entry.snapshotSha256){throw 'Revised snapshot input mismatch.'}}
$data.createdUtc=[DateTime]::UtcNow.ToString('o')
$data.revision=[ordered]@{
    number=5;predecessor=$oldPath;predecessorSha256=$oldHash
    reason='Restore NN animation after the owned publication callback returns, with fresh same-frame pose and direct-component cleanup regressions; bound diagnostic collision responses to the actual stored array.'
    reviewedPatch=(Join-Path $draftRoot 'Proposed.patch');reviewedPatchSha256=(Get-NNHash (Join-Path $draftRoot 'Proposed.patch'))
    validator=(Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py');validatorSha256=(Get-NNHash (Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/Validate-PackagedNNCrowd.py'))
    changedInputs=$changes
    scope='Only six reviewed source files replaced; archive retains R4 source bytes. Same 1304 input set and asset/model/config closure. R4 is historical and intentionally no longer matches revised Project source.'
}
Write-NNJson $newPath $data
$null=Read-NNSnapshot $newPath
[pscustomobject]@{Snapshot=$newPath;ChangedFiles=$changes.Count;Files=$data.inputs.Count;Sha256=(Get-NNHash $newPath)}|ConvertTo-Json -Depth 4
