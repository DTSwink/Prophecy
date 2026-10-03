$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'PackagedNNCrowdDraft/PackagedNN.Common.ps1')
Assert-NNIdle
$root=Resolve-NNAbsolute (Join-Path $PSScriptRoot '../..')
$snapshotRoot=Join-Path $PSScriptRoot 'NNCrowd-20260909-144331-647'
$oldPath=Join-Path $snapshotRoot 'snapshot-r3.json'
$newPath=Join-Path $snapshotRoot 'snapshot-r4.json'
if(Test-Path -LiteralPath $newPath){throw 'R4 already exists.'}
$data=Read-NNSnapshot $oldPath
$oldHash=Get-NNHash $oldPath
$runnerPath=Join-Path $snapshotRoot 'Runs/Development-C2-20260909-182410-450/runner.json'
$runner=Get-Content -LiteralPath $runnerPath -Raw | ConvertFrom-Json
if($runner.success -or $runner.snapshotSha256 -ne $oldHash -or $runner.exitCode -ne 3){throw 'Unexpected R3 crash evidence.'}
$symbolsPath=Join-Path $PSScriptRoot 'PackagedCrashSymbolizationDraft/SymbolizedStack.json'
$symbols=Get-Content -LiteralPath $symbolsPath -Raw | ConvertFrom-Json
if($symbols.module_info.pdb_unmatched -or $symbols.stack[0].line -ne 684 -or $symbols.source_exe_sha256 -ne $runner.executableSha256){throw 'Crash symbols do not match failed executable.'}
$relativePaths=@(
    'Source/GameAnimationSample3/Private/ProphecyJoltPoseAnimInstance.cpp',
    'Source/GameAnimationSample3/Private/ProphecyJoltQueryPoseTests.cpp',
    'Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkMultiJolt.cpp'
)
$proxyBaseline=Get-Content (Join-Path $PSScriptRoot 'RemainingTickAuditDraft/Baseline.json') -Raw | ConvertFrom-Json
foreach($file in $proxyBaseline.files){
    $old=Get-NNHash (Join-Path $data.projectDirectory $file.path)
    if($old -ne $file.sha256){throw 'Snapshot does not match proxy baseline.'}
    $current=[IO.File]::ReadAllText((Join-Path $root $file.path)).Replace("`r`n","`n")
    $draft=[IO.File]::ReadAllText((Join-Path $root $file.draft)).Replace("`r`n","`n")
    if($current -cne $draft){throw 'Current proxy files differ from tested candidate.'}
}
$multi=$relativePaths[2]
$before=[IO.File]::ReadAllText((Join-Path $data.projectDirectory $multi)).Replace("`r`n","`n")
$after=[IO.File]::ReadAllText((Join-Path $root $multi)).Replace("`r`n","`n")
$expected=$before.Replace('                Meshes[0]->UnregisterOnBoneTransformsFinalizedDelegate(MutationCallback);', '                // Keep the executing functor alive; unregister after StepAndPublish returns.').Replace('            Meshes[RemovedIndex]->UnregisterOnBoneTransformsFinalizedDelegate(RemovalCallback);', '            // Nested finalization is guarded above. Removing this binding here frees its captures.')
if($expected -ceq $before -or $after -cne $expected){throw 'Callback fix differs from the two reviewed inner-unregister replacements.'}
$archive=Join-Path $snapshotRoot 'SourceArchive-r3'
if(Test-Path -LiteralPath $archive){throw 'Source archive already exists.'}
New-Item -ItemType Directory -Path $archive | Out-Null
$changes=@()
foreach($relative in $relativePaths){
    $source=Join-Path $root $relative
    $target=[IO.Path]::GetFullPath((Join-Path $data.projectDirectory $relative))
    if(-not $target.StartsWith($data.projectDirectory+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Snapshot target escaped Project.'}
    $entry=@($data.inputs | Where-Object relativePath -eq $relative)
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
foreach($entry in $data.inputs){if((Get-NNHash (Join-Path $data.projectDirectory $entry.relativePath)) -ne $entry.snapshotSha256){throw 'Resulting snapshot differs from revised input hashes.'}}
$data.createdUtc=[DateTime]::UtcNow.ToString('o')
$data.revision=[ordered]@{
    number=4;predecessor=$oldPath;predecessorSha256=$oldHash
    failedRunner=$runnerPath;failedRunnerSha256=(Get-NNHash $runnerPath)
    symbolizedStack=$symbolsPath;symbolizedStackSha256=(Get-NNHash $symbolsPath)
    reason='Keep executing benchmark callback captures alive until the existing post-step unregister; matching PDB identifies the old use-after-free at line684. Include the independently tested native animation traversal correction and strengthened query test.'
    changedInputs=$changes
    scope='Only three reviewed source files replaced. R3 source archive and historical manifests/reports remain. Same full asset/model/config closure; existing Project now represents R4 and R3 source hashes intentionally no longer match it.'
}
Write-NNJson $newPath $data
$null=Read-NNSnapshot $newPath
[pscustomobject]@{Snapshot=$newPath;ChangedFiles=$changes.Count;Files=$data.inputs.Count;Sha256=(Get-NNHash $newPath)} | ConvertTo-Json -Depth 4
