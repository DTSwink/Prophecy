# Retained endpoint-cache comparison and rollback

Research date: 2026-09-09. These are draft/audit artifacts; no active source edits, builds, or Unreal launches were performed by this task.

## Complete-row result: PASS

`AuditEndpointCacheReports.py` independently reduced both retained reports named in `../EndpointCacheBinaryCapture-20260909-1630.json`. Each report passes 48 checks across all 360 measured frames, plus six checks of the saved seven-binary before/after capture. Detailed results and every frame's inference/expansion correlation are in `EndpointCacheComparison.json`.

The standalone auditor was adapted from `../AuditGameModuleSimdReports.py` (SHA-256 `d2eaf754dbd26382e5a8baab839e1445311becc2e19ec25520a0e1e13727520b`). It retains the existing complete workload, query, cadence, lifecycle, timer-partition, camera, processor-policy, and CPU-entry checks. It replaces private-ISA/PCH comparisons with the saved DEFAULT same-binary capture and adds the cache-specific checks. `BuildAuditor.py` records that source transformation; it need not be run to use the resulting standalone auditor.

| Mean elapsed time per world frame | Cache disabled | Cache enabled | Enabled minus disabled |
| --- | ---: | ---: | ---: |
| World tick | 11.347207 ms | 11.394867 ms | +0.047660 ms |
| Agent tick | 1.227501 ms | 1.301890 ms | +0.074390 ms |
| Target read | 0.578378 ms | 0.652015 ms | +0.073637 ms |
| Endpoint expansion | 0.106519 ms | 0.054707 ms | -0.051812 ms |
| Target read minus expansion | 0.471859 ms | 0.597308 ms | +0.125449 ms |

The last row includes all remaining target-read work; it does not isolate only cache comparisons or copying. This one sequential A/B pair does not establish a confidence interval or exclude scheduler/thermal variation. It shows the intended reduction in actual expansion calls, while the enclosing target-read phase became more expensive. The cache was therefore declined and rolled back by the parent task.

## Verified workload and expansion behavior

- Both runs use the same 100 actual NN agents, 60 warmup frames, and 360 measured frames at 60 Hz presentation with 30 Hz NN inference. Each run completes 180 inference steps and 18,000 physical feedback samples, with no failed samples or synthetic pose publication after adoption.
- Every frame retains 2,200 active Jolt bodies, 2,100 joints, 8,800 presented bones, and zero Chaos dynamic character bodies. Each report checks 792,000 body instances and 3,168,000 bone instances over the measured interval.
- All 36,000 head visibility queries per report succeed on the original PhysicalMesh and head bone with unfiltered normal visibility. Own-capsule fallback count is zero. Capsule policy, geometry, and native/component agreement remain intact.
- Cache disabled: all 360 frames perform exactly 100 endpoint expansions, totaling 36,000. The 180 inference frames and 180 interpolation frames both perform 100.
- Cache enabled: all 180 inference frames perform exactly 100 endpoint expansions; all 180 interpolation frames perform exactly zero, totaling 18,000. Zero-expansion frames report zero time in the expansion scope. Every frame retains 100 target reads.
- The first measured row in both runs has NN delta 1 and 100 expansions. No exceptional first-frame allowance was needed or silently accepted.
- Both before/after case fields and the report finish field match the captured command-line cache control. Query padding is 40 cm at all recorded boundaries, ordinary Chaos remains unpaused, and stock Engine ISPC controls remain enabled.
- Normal process priority, the requested/restored GT affinity, all recorded P-class frame endpoints, and all 36,000 P-class RefreshBoneTransforms entries per report are verified. These observations do not prove continuous CPU residency or worker utilization.
- Unmeasured removal during finalization, the two survivor/lifecycle steps, stale-handle rejection, late pending cancellation, and full teardown pass. The synthetic authored-pose callback mutation is explicitly **not exercised** by the actual-NN cases; its independent synthetic regression is outside these two reports.

## Provenance boundary

The audit binds both reports to the saved DEFAULT runtime fingerprint and the same captured game, Unreal Jolt, native Jolt, Core, Engine, ORT, and commandlet executable identities. All seven recorded hashes match the subsequent saved after-verification file. The loaded Engine module path matches the captured Engine path. No current DLLs are read, because later builds can replace them.

The saved before/after file hashes and the operator's no-build-between-runs attestation are evidence for this pair; they are not continuous process-memory monitoring or a complete ABI proof. The runtime game fingerprint is not used to infer Engine ISPC compilation.

## Rollback checkpoint

`RollbackEndpointCache.apply-patch.txt`, `RollbackVerification.json`, and the seven paths under `Rollback/` contain the surgical rollback based on the current files after the feedback-mode promotion. `CacheSourceArchive/` preserves the measured cache implementation, including the alias fallback and its tests.

The rollback removes only the cache caller/class/implementation/tests and its benchmark flag/report controls. It retains the `TargetEndpointExpand` profiling phase and `FLayout::Evaluate` scope, original uncached transform math, the original three target tests, feedback-mode controls, native query-padding controls, and game ISA controls. The original target header/tests and Agent source match their pre-cache baselines exactly; the target implementation differs only by the retained timing include/scope. Both draft PowerShell scripts passed AST parsing. The parent subsequently promoted the seven guarded replacements, rebuilt affected source, and reported the three target tests plus 59 Jolt tests passing.

Run only the read-only audit from the project root:

```powershell
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/ThirdParty/Python3/Win64/python.exe' -B 'Saved/JoltMigration/EndpointCacheComparisonDraft/AuditEndpointCacheReports.py'
```

Output defaults to this draft directory; the auditor refuses output outside `Saved/JoltMigration`. It returns nonzero if a checked report or comparison fails. Missing required schema fields are errors, not silently omitted checks.
