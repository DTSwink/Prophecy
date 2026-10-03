# First packaged Development 100-agent run: independently audited

The first complete packaged R4 run records **9.471366 ms mean world time** for 100 agents. It retains all 360 measured samples and the required simulation/query workload. This is evidence of a mean below 10 ms in one Development run; it does not complete the goal. The report contains a newly identified out-of-bounds diagnostic export, and full animation-class restoration after callback removal remains unresolved.

| Result | Packaged R4 Development | Earlier Editor with native proxy fix |
|---|---:|---:|
| Mean world ms | 9.471366 | 11.878346 |
| Reported median, sorted index 180 | 10.352697 | 11.552498 |
| Conventional two-middle-value median | 9.955348 | 11.552349 |
| p95, sorted index 342 | 12.583900 | 16.108699 |
| Samples above 10 ms | 180 / 360 | 246 / 360 |
| Interpolation-only frame mean ms | 7.405145 | 9.708209 |
| Inference-frame mean ms | 11.537586 | 14.048483 |

The 2.406980-ms lower world mean is an observed difference between different Editor/module and cooked Development binaries in separate process sessions. The later source also fixes the self-unregistering lifecycle callbacks, and query padding is applied/restored natively rather than through ExecCmds. The comparison does not isolate a single cause. RefreshBones averages 1.858721 ms, including 1.072372 ms query publication; coordinator averages 4.899044 ms, including 1.719503 ms native wrapper and 0.517721 ms completed-pose batch. These scopes overlap and must not be added twice. Actual NN inference averages 1.028991 ms per world frame, versus 0.714839 ms in the earlier Editor run.

## Preserved measured workload

The independent auditor checks every recorded row. **51 of 52 strict runtime checks pass**; the one failure is the invalid 33-entry diagnostic described below. All other required recorded gates pass:

- Exactly 100 agents, 60 warmup frames and **360 measured frames**, 60 Hz world/Jolt/presentation, 30 Hz real ORTCpu lower/walk/upper inference at batch 100 and four foot-roll iterations.
- All 2,200 Jolt bodies active on every frame, 2,100 joints, 22 bodies/88 bones per character, 36,000 agent records, 792,000 dynamic-body checks and 3,168,000 bone checks.
- Exactly **36,000 PreUpdates**, PreEvaluate, Evaluate, PostEvaluate and finalization scopes; 216,000 publication identity validations. Every frame retains one complete update/evaluation/query/finalization cycle per character.
- 792,000 retained UE query-body pose checks and 36,000 ordinary unfiltered head rays. Each receiver equals its own lane's captured physical component; no own-capsule fallback or capsule filter is used. Native/component errors remain within original tolerances.
- 180 actual NN steps, 18,000 physical samples, zero failed samples, Original feedback and no prepared work. All roots travel at least 1,200.010681 cm.
- Seven Jolt workers, NoLock idle reads, DuringPhysics, no Chaos pause, zero Chaos dynamics, movement-only detached camera subtrees with components retained, and restored P-class game-thread placement.
- Native padding records 5 → 40 → 5 cm with flags 0 throughout. Both before/after measurement scene snapshots record 40 cm; the final CVar read is correctly 5 after restoration.
- The recorded removal-during-finalization, survivor handles/poses, two unmeasured lifecycle steps, pending cancellation, stale-handle retirement, disable and floor-only teardown gates all pass. These checks have the animation-class restoration limitation below.

All **22 package/provenance checks** pass, including **370 independently rehashed files**: package/snapshot/report/validation/query artifacts, staged executable, dependency manifest, six raw NN files, 33 staged DLLs, 311 cooked game packages and 13 cooked external packages. The executable SHA256 is `00d863d10531e31242a8278e7fa1ce2b924256f1374e23c8b2dbc92b25120e85`. All five matching-snapshot query tests pass cleanly, including five logged publications in the strengthened reinitialization control. This audit checks the manifest hash and those staged/cooked artifacts; it does not rehash all 1,304 snapshot inputs or prove continuous loaded-memory identity.

## Diagnostic export defect: retained as a failure

`ProphecyPhysicsBenchmarkNNJolt.cpp:261` loops to ECC_MAX, which includes the deprecated transient value ECC_OverlapAll_Deprecated at index 32. UE stores only `FCollisionResponseContainer::EnumArray[32]`, with valid indices 0–31, and GetResponse indexes that array without a bounds check. The export therefore reads one byte past the actual responses before measurement.

All 100 real 32-channel policies are identical: object channel 21, QueryAndPhysics, radius 30 cm, half-height 86 cm, WorldStatic Block and every other stored channel Ignore. The report appends an invalid 33rd byte: 50 zeroes and 50 values of 128. Those bytes are not collision policy. Historical Editor exports happened to contain zero in that same invalid slot.

The original report remains unchanged. The machine audit keeps `all_recorded_gates_verified=false` and `diagnostic_export_clean=false`, while recording `individual_runtime_evidence_verified=true` for the valid simulation/query evidence. The future R5 validator must require exactly 32 responses and reject every extra entry, including zero. The source and validator drafts are supplied beside this audit.

## Head-name casing and outstanding restoration

Cooked ray results display `Head`; Editor results display `head`. UE FName equality is case-insensitive (`Core/Public/UObject/NameTypes.h:614`), and the native validator itself compares `Hit.BoneName == FName(TEXT("head"))` before serializing ToString (`ProphecyJoltPostPhysicsQueryValidation.cpp:279`). Casefolding that one serialized bone field is justified. This independent auditor additionally checks exact per-lane component identity and retains every ordinary ray/capsule/native-pose gate.

UE's SetAnimInstanceClass returns while bPostEvaluatingAnimation is true (`SkeletalMeshComponent.cpp:3458`). Current callback removal can retire the Jolt rig and pass the reported kinematic/no-dynamic/handle checks while its animation-class restoration is refused. That restoration is not asserted by the present benchmark. A deferred restoration fix is being prepared separately; neither this run nor its successful recorded flags prove a complete mode handoff.

The result remains a separated-grid/static-floor **NullRHI Development** benchmark. Rendering, active blood GPU work, dense contacts, Shipping and the remaining full migration are separate. No complete-goal claim is made.

Artifacts: `AuditPackagedR4.py`, `PackagedR4Comparison.json`, `CollisionPolicyExport.patch`, `CollisionPolicyValidator-r5.patch`, `CollisionPolicyDraftBaseline.json`.
