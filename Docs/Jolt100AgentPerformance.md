# 100-agent Jolt CPU performance

User priority, 9 September 2026: work autonomously toward 100 simulated agents below 10 ms total CPU pipeline time without sacrificing quality, then continue the remaining Jolt integration. This target is not achieved yet.

## Acceptance

Retain 22 dynamic bodies and 21 authored hard PHAT joints per character, physical-animation control, all 88 skeletal bones, 60 Hz simulation/presentation in the current fixture, and the existing 30 Hz authored/NN stream. Preserve collision profiles, original UE query receivers, immediate blood traces, sockets and stable lifetime handling. No hidden reduction of solver cadence, bone count, query updates, collision coverage or controller quality may be used to pass. A CPU result excludes rendering; it must say so. Actual NN inference, capsule/intent work and physical feedback need representative final measurement, not addition of an old isolated inference number to a new solver number.

The user's follow-up explicitly authorizes removing unused crowd cameras and optional fist closing for this movement goal. `-MovementOnly` on the launcher selects this declared workload for the shared manual preparation in both backends: `bEnableAttackFists=false` and disabled camera/spring-arm component ticks on unpossessed fixture agents. Finger bones remain in the completed pose; optional fist closing and player cameras remain available outside this workload. This is an authorized scope change, not a same-workload optimization claim.

Measure warmed full world-tick means, medians and p95, and explain both load and workload. Aim for repeatable total times under 10 ms rather than one favorable frame. Detailed correctness validation stays outside the timing window but does not replace the production operations it validates. No speedup ratio may use a different Chaos controller as its denominator.

## Measured starting point

The 100-character floor fixture uses a 10-by-10 separated grid, synthetic moving 30 Hz poses, 60 Hz fixed world steps, original rig limits, static-only fixture contacts, NullRHI, 60 warmup and 180 samples. It does not run NN inference or inter-character contacts. All 2,200 bodies, 2,100 joints and 8,800 feedback/socket bones passed; zero Chaos dynamic bodies remained after handoff. Lifecycle removal and pending cancellation also passed.

- `Saved/Benchmarks/jolt_shared_100_20260909_1054.json`: Jolt Update mean **2.3484 ms**, world tick mean **32.0104 ms**, median **30.8066 ms**, p95 **41.4136 ms**.
- `Saved/Benchmarks/jolt_shared_profile_100_20260909_1101.json`: instrumented world tick mean **28.5843 ms**, median **28.1649 ms**, p95 **35.0218 ms**. This is a second run with profiling, not evidence of an optimization.

| Instrumented work, all 100 characters | Mean ms |
|---|---:|
| Publish authored targets | 10.0738 |
| Publish completed pose, inclusive | 8.4269 |
| Read Jolt bodies, inside completed pose | 0.4299 |
| Compose full pose, inside completed pose | 0.9699 |
| Animation buffer copy, inside completed pose | 0.1364 |
| Wait for prior animation, inside completed pose | 0.0170 |
| Tick animation, inside completed pose | 0.5472 |
| Refresh bones, inside completed pose | 4.2353 |
| Explicit query-body update, inside completed pose | 1.8716 |

The inclusive completed-pose value must not be added to its child scopes. Later nested scopes established the concrete costs below. Run-to-run variation is substantial, so the 28.6 ms run must not be used as evidence that later code regressed from an established optimized baseline.

## Detailed attribution and first optimization

`Saved/Benchmarks/jolt_full_scopes_100_20260909_1126.json` passed all 180 measured frames: world mean **36.6163 ms**, median **36.8491 ms**, p95 **40.4225 ms**, native Jolt Update **2.3539 ms**. Each frame had exactly 100 target publications, 100 completed-pose publications, 100 Agent ticks and one shared coordinator/native world step.

| Work for 100 characters | Mean ms | Relationship |
|---|---:|---|
| Agent ticks | 11.8867 | Includes targets |
| Target publication | 11.8363 | Includes following target scopes |
| Closed-fist extraction/retarget and blending | 8.9822 | Inside targets |
| Read previous/future authored world poses | 1.6032 | Inside targets |
| Build helper local pose | 0.6420 | Inside targets |
| Synthetic 30 Hz pose generation/publication | 1.1846 | Separate pre-actor work |
| Shared coordinator | 16.6742 | Includes native step and completed poses |
| Completed-pose publication | 13.7963 | Includes following pose scopes |
| Refresh skeletal bones | 7.0095 | Inside completed poses |
| Explicit UE query-body update | 3.1293 | Inside completed poses |
| Compose full 88-bone poses | 1.5179 | Inside completed poses |
| Native step wrapper | 2.6736 | Inside coordinator; Jolt Update is 2.3539 ms |

An independent engine CSV run (`jolt_engine_csv_100_20260909_1127.json`, CSV `Saved/Profiling/CSV/Profile(20260909_112442).csv`) measured world mean **37.8710 ms**. Its 161 explicitly marked measured CSV rows show **3.56 ms** of retained Chaos scene work, including **1.41 ms** pulling physics data and approximately **0.80 ms** updating spatial structures. Dynamic Chaos body count remains zero: these are UE query representations, not a second character solver. CSV also confirms 100 unused SpringArm and Camera component ticks; their contribution needs an attribution run. The 5.4 ms `WorldTickMisc` CSV scope includes the fixture's detailed validator after the world timer and must not be added to world time.

Normal process priority (`jolt_priority_normal_100_20260909_1129.json`) gave **37.1312 ms** mean. This early run did not record processor placement; later evidence shows that Normal priority alone does not ensure performance-core execution. No machine power, affinity or system scheduling settings were changed.

The first applied optimization reuses target/snapshot buffers and reads the authored pose store once for targets and helper bones, with exact layout comparison and unchanged pose mathematics. `jolt_target_buffers_100_20260909_1134.json` passed all 100-agent, full-pose and lifecycle checks: mean **35.7811 ms**, median **36.4400 ms**, p95 **37.7386 ms**, Jolt Update **2.3164 ms**. Helper construction fell to **0.2538 ms**; fist work remains **8.9633 ms**, and completed-pose publication **13.5599 ms**. This is a small measured improvement, not achievement of the 10 ms goal.

`Tools/Jolt/SummarizeCharacterPerformance.py` reads reports and optional CSV files without treating nested timings as additive. All these measurements still exclude actual NN inference, production capsule/intent work and rendering.

`Docs/AgentSimulationCostAudit.md` records an older 30 Hz actual-NN audit: 100 kinematic characters 5.021 ms median total; 100 fully physical Chaos characters 29.894 ms total and 12.663 ms solver. That is evidence that a cheaper CPU character pipeline existed. Its controller, cadence and contact workload differ from this fixture, so it is not a matched speed comparison.

## Movement profile and query publication

`jolt_movement_100_20260909_1151.json` applies the user-authorized omission of optional fists and unused cameras: all 100-character validations passed, world mean **27.9420 ms**, median **27.8511 ms**, p95 **30.9162 ms**. Target publication was **2.5712 ms**, including only **0.0503 ms** of disabled-overlay bookkeeping instead of approximately 9 ms of fist extraction. This run still had 100 empty inherited skeletal meshes ticking: runtime component identities proved that `FinishSpawning` had re-enabled their initial tick setting. The real PhysicalMesh tick was correctly disabled, so this was not a second physical pose evaluation.

The empty inherited mesh is now disabled after registration in the shared manual fixture. The query publisher now uses the existing composed world pose, retains every original PHAT body/shape/filter, batches X/R and spatial updates per character, and caches unchanged UE scale requests. It does not install a new Chaos kinematic target each frame. A one-shot game-thread pose-proxy hook commits queries before skeletal buffer finalization, allowing immediate finalized-bone traces to see the current pose. Disabled postprocess instances remain allocated and retain their callbacks: query publication precedes those disabled instances' post-evaluation callbacks; their pose evaluation stays disabled. Unexpected re-enabling or evaluator changes stop the binding through its existing error path.

The full **50/50** foundation run `Saved/JoltMigration/Foundation-20260909-120301-596/index.json` passed with zero warnings/errors. The new actual-mannequin test verifies native body/socket agreement and a native ray inside all four bone-finalization callbacks, unchanged nonuniform-scale geometry identity, changed-scale invalidation and agreement with UE's stock geometry result. Angle comparisons normalize both quaternions before AngularDistance, while independently requiring normalized inputs; this avoids treating float quaternion length error as a rotation difference.

`jolt_bulk_query_100_20260909_1204.json` then passed all 100-character, 180-frame and lifecycle checks: world mean **20.8337 ms**, median **20.6997 ms**, p95 **25.0213 ms**; Jolt Update **2.6235 ms**. Completed pose publication is **10.1661 ms**: body reads **0.5606**, full pose composition **1.5813**, animation tick **1.0380**, bone refresh **6.2135**, including **2.0805 ms** of query publication. Query timing is now a child of refresh and must not be added to it. Target reading remains **1.7880 ms** before the next sparse-layout optimization.

Its CSV `Saved/Profiling/CSV/Profile(20260909_120356).csv` has 161 marked measured rows: retained Chaos scene work fell to **1.7102 ms**, including pull-data **0.2065 ms**; the two spatial-update scopes still total approximately **0.857 ms**. No static proxy conversion or physics cadence change was required. These are synthetic movement diagnostics; actual NN inference is still a pending gate and the 10 ms goal remains unmet.

The matching unrecorded Chaos fixture is now available as `ManualCrowd`. Its Count 1 air/floor and Count 100 floor runs passed ownership/pose checks, but all bodies could sleep (minimum awake count zero). The 100 run `manual_crowd_100_20260909_1150.json` measured **29.8715 ms** mean with fists/cameras enabled. It cannot establish a matched fully-active solver speedup against Jolt; sleeping state is explicitly recorded, and no artificial wake calls were added.

## Active investigation

The sparse authored-target reader passed all three oracle/lifetime tests (`Foundation-20260909-121536-622/index.json`). It retains the exact previous/future pose mathematics and live layout validation while constructing only the needed ancestor closure. `jolt_finalization_profile_100_20260909_1218.json` passed all 100-agent checks: world mean **19.3580 ms**, median **19.7714 ms**, p95 **21.6132 ms**, Jolt Update **2.4556 ms**. Target reading fell from **1.7880** to **1.0140 ms**. Completed publication remains **9.7865 ms**, including composition **1.5377**, animation tick **0.9879**, and refresh **6.0092 ms** (query publication **2.0202 ms** nested inside). After-query finalization costs **1.5730 ms**; the old Chaos scale-repair callback still revisits the completed Jolt pose here.

Prepared immutable pose layouts, reusable completed-pose arrays and the Jolt ownership guard on the old Chaos correction passed **53/53** foundation tests (`Foundation-20260909-123009-190/index.json`), including exact full-pose scalar comparisons with the unchanged legacy composer and buffer lifetime checks. `jolt_prepared_finalizer_100_20260909_1232.json` passed at **13.0491 ms mean**, **12.3942 median**, **17.1776 p95**, Jolt **2.2140 ms**. Completed publication was **4.8720 ms**, composition **0.8091**, animation tick **0.5031**, refresh **2.7879** including query **1.3904**, and after-query finalization **0.2610 ms**. Its CSV shows approximately **1.7524 ms** waiting for UE physics at EndPhysics.

However, the same binary's longer 360-frame repeat `jolt_prepared_repeatA_100_20260909_1236.json` passed at **17.7570 ms mean**, **18.2289 median**, **20.5055 p95**, Jolt **2.3924 ms**. Composition rose to **1.3620**, animation tick **0.9517**, query publication **2.0071**, and completed publication **8.3296 ms**. Consequently, 13 ms is not a repeatable established baseline and the whole difference cannot be attributed to the edits. Game-thread core placement/efficiency and per-phase execution will be captured without changing affinity or power settings. An attempted Repeats=2 launch was rejected before sampling by the fixture's existing Repeats=1 restriction; it contains no timing evidence.

The next measured candidates are overlapping the independent Jolt and retained UE physics work through a DuringPhysics coordinator, with query-persistence checks after EndPhysics, and batching pure completed-pose composition across characters while keeping UE publication/callbacks serial. Full skeletal parallel evaluation alone has a small measured ceiling (approximately 0.69 ms in the favorable CSV); component replacement is not an acceptable shortcut for the existing receiver identities.

### Processor placement explains a major measurement difference

The next compiled checkpoint removes 100 empty Jolt component ticks, retains shared coordinator ownership and adds exact layout/name lookups (two regression tests passed in `Foundation-20260909-124327-078/index.json`). It also captures read-only processor placement, with explicit profiling overhead included in world time. The same binary and 360-frame workload were run in quiet measurement windows at two process priorities:

| Run | Process priority | Mean / median / p95 world ms | Observed game-thread placement |
|---|---|---|---|
| `jolt_processor_preA_100_20260909_1244.json` | BelowNormal | **17.8816 / 18.2678 / 20.2415** | All 360 frame starts and all 36,000 composition/36,000 refresh entries on OS efficiency class 0, logical CPUs 8–11 |
| `jolt_processor_normalA_100_20260909_1246.json` | Normal | **10.5153 / 10.5881 / 11.8856** | All 360 frame starts on class 1, CPUs 0–7; 99.83% of composition entries and 99.84% of refresh entries on class 1 |

On this i5-12450H, the reported topology maps the latter group to the four performance cores and their hardware threads, and CPUs 8–11 to the four efficiency cores. Composition averaged **13.835 microseconds per character** in the background-priority run and approximately **7.050 microseconds** for performance-core entries in the normal-priority run; refresh averaged **48.703** versus **23.330 microseconds**. Entry sampling does not prove continuous residency, but all per-frame sample durations/counts exactly partition the corresponding existing phase totals. The comparison is evidence of a scheduling association, **not a code speedup**. The favorable earlier 13 ms run had no processor observations, so its placement remains unknown.

Affinity stayed `0xfff` in both runs; no affinity, system power, clock or QoS settings were changed. QoS read APIs returned error 87, so that policy state is unknown. The launcher now defaults to the ordinary Normal game-process priority and retains explicit BelowNormal for diagnostic comparisons. Report metadata records the actual policy. The normal run's Jolt step was **1.7179 ms**, targets **1.1854**, completed publication **4.0573**, and synthetic pose generation **0.7740 ms**. NN inference is still absent and 10 ms has not been achieved. The analysis tool/evidence are under `Saved/JoltMigration/ProcessorProvenanceDraft`.

The CSV interval audit also resolved the apparent extra PreActor time: its first marked row contains **123.7674 ms** of fixture admission/audit before the world timer starts. For steady rows excluding that initialization row, PreActor time was **0.9367 ms** versus synthetic publication **0.9222 ms**. Do not average that startup work into a claimed steady per-frame integration cost. All-row WorldMs remains the original unaltered report statistic.

### Parallel pose construction and overlapping physics

The next checkpoint passed **55/55** native foundation tests with zero test warnings/errors (`Foundation-20260909-125840-976/index.json`). Pure immutable pose math now runs in a joined parallel batch, with all UObject access, native body reads, query writes and animation callbacks on the game thread. Prepared packets retain exact binding, carrier, completed-step and authored-publication identities; a changed later character falls back to fresh serial composition. The full 88-bone outputs match the unchanged serial oracle. A separate live callback-invalidation regression is added but is not runtime verified yet.

`-ProphecyJoltDuringPhysics` is an experimental coordinator option; PrePhysics remains the default. It overlaps the Jolt pipeline with the independent retained UE physics scene. `jolt_during_batch_100_20260909_1307.json` measured **14.9870 ms mean / 15.7568 median / 16.5786 p95**, Jolt **2.5230 ms**, batch capture/composition **0.8530 ms**, and serial publication **6.3795 ms**. Batch and serial publication are disjoint; body reads are nested in the batch, and query updates remain nested in refresh. There were no serial compose calls in the timed frames.

Despite Normal priority, all 360 frame starts and all 36,000 refresh entries were on efficiency-class-0 CPUs. Refresh averaged **47.748 microseconds per character**, close to the earlier efficiency-core result. The two Normal runs used the same reported process/thread priorities and affinity but opposite core classes; priority alone is therefore insufficient to stabilize this comparison. Do not call 14.987 versus 10.515 a code regression or use the latter as an established baseline for these edits.

Every timed frame passed group/cadence, body/pose and post-EndPhysics native head-query checks. The report nevertheless correctly remains **failed**: its additional coverage gate requires a ray wholly outside the preceding query AABB, which natural fixture motion did not supply. A controlled translated-pose foundation case is being built to prove this timestamp/broadphase edge without changing the timed crowd motion. No current successful DuringPhysics performance acceptance is claimed.

### Controlled placement comparison and actual NN checkpoint

The controlled query-persistence test passed with zero test warnings/errors in `Foundation-20260909-132035-560/index.json`. It publishes a 150 cm root translation after marshalling the old pose, then verifies all 22 current body poses, all 88 bones, a new-position head hit and an old-position miss after EndFrame. The returned physics tree advances to timestamp 1 while the newer GT write has timestamp 2, proving that the test actually crossed the older-tree return. The crowd now reports natural motion-edge coverage separately and requires this external controlled test for DuringPhysics acceptance; all per-frame body/head-query checks remain mandatory.

An explicit `-PClassGameThread` benchmark option derives all fastest-class logical CPUs from Windows topology, temporarily constrains only the game thread, verifies every sampled frame/compose/refresh location and restores the exact original affinity. On this host it records `0xfff -> 0xff -> 0xfff`; process and worker policies are unchanged. This is diagnostic placement control, not a production default or a code-only speedup. The helper is tied to its exact benchmark subsystem lifetime so another world's teardown cannot restore it.

The following same-binary, 100-character, 360-frame runs all passed, with identical movement/contact/cadence and query validation:

| Configuration | Mean world ms | Median ms | p95 ms |
|---|---:|---:|---:|
| PrePhysics, serial composition | 10.4195 | 10.4472 | 11.6524 |
| DuringPhysics, serial composition | 9.3093 | 9.4567 | 10.6541 |
| DuringPhysics, batch A | 9.0989 | 9.2715 | 10.3817 |
| DuringPhysics, batch B | 8.9860 | 9.1600 | 10.1711 |

The overlap removes approximately 1.11 ms of exposed world time; it does not make the solver faster. Batching removes a further 0.21-0.32 ms. Both batch runs average below 10 ms, but p95 remains above it and NN is absent. Exact reports, verified processor partitions, phase boundaries and lifecycle evidence are in [the controlled comparison](../Saved/JoltMigration/GameThreadPlacementDraft/ControlledComparison.md). No samples were dropped. All bodies retain dynamic ownership; the post-step active count is 2,200 on 356 frames and zero on four identical frames in each run, with all reactivated on the next frame. This is not a continuously awake-load claim.

The same-frame callback regression also passed in all four runs: the first finalizer changes the last character's authored local root by 11 cm, and its final local/world errors are zero. Batch runs execute one batch plus one correctly invalidated serial fallback; serial controls execute 100 serial composes. Removal, survivor continuation, stale handles and pending-admission cancellation still pass.

The actual NN two-character smoke `nn_jolt_pclass_smoke_2_20260909_1329.json` passed 30 real NN steps, 60 physical-feedback samples and at least 200 cm of managed root travel. All CPU models still use batch 100. The first 100-character run `nn_jolt_pclass_100_A_20260909_1330.json` stopped at frame 210 because the real movement capsule occluded the validation ray aimed at the head; its 22 body-pose checks agreed before that trace. It contains no completed timing pass. A capsule-aware validation correction is in progress, without gameplay filter changes. Actual 100-agent NN performance acceptance remains open.

The earlier CPU NN/capsule/feedback smoke (`actual_nn_jolt_2_20260909_1221.json`) rejected an incorrect fixture requirement for an NN AnimInstance on a manual Physical mesh. Manual physical control reads the pose registry directly. That requirement was fixed; the successful two-agent retry and complete 100-agent measurements below supersede this historical failure. Further prop/sword integration remains paused at source checkpoints during this priority.

The earlier foundation result `Saved/JoltMigration/Foundation-20260909-111905-528/index.json` had **49 passed, zero test warnings/errors**, superseded by the 50-test run above. It includes standalone cooked-convex preparation and six generic-joint lifetime/filter/limit tests. The generalized step-client coordinator passed the subsequent 100-character runs. The actual Training sword fixture has not yet produced a result; prop ownership work is paused for performance.

Real D3D12 blood validation was rerun after query and sparse-target changes: `Saved/Benchmarks/jolt_bulk_blood_20260909_1217.json` passed static mesh, Jolt character and two transformed ISM receivers, including localized mask pixels, independent instance render targets and repeated-callback behavior. All 88 character bones agreed with native feedback (maximum position error approximately 3.07e-13 cm and rotation error 2.4e-6 degrees). After prepared composition and the finalizer ownership guard, `jolt_prepared_blood_20260909_1240.json` also passed with an empty report error. Existing limitations include untested HISM/PCG, Niagara GPU emission/export and production material appearance.

## Reconstructing the historical 5.021 ms kinematic result

The retained `AgentAudit_p0_A1`, `A2`, `B1`, `B2` logs report warmed wall averages of **6.1768, 3.8650, 3.0610, 6.5970 ms** over 450 measured frames each. Their median is **5.0209 ms**. This is the median of four run averages, not the median of individual WorldTick samples. Corresponding August CSV frame averages corroborate it.

Those launches explicitly used `-benchmark -fps=30 -seconds=24`: world and NN updates advanced at 30 Hz. Current measurements present and simulate at 60 Hz with NN at 30 Hz. The old CSV records 100 skeletal mesh ticks, no Agent ticks and no camera/spring-arm ticks. The nearest retained source (`d3172cd`, August 12, after the August 10 measurements) uses one blocking capsule and a NoCollision skeletal mesh, a lower-body policy publishing nine bones, and no physical feedback for the kinematic case. The current workload adds upper-body inference, physical feedback, physical targets, full-pose composition and 2,200 limb query bodies. Exact old executable source, evaluated bone count, movement intent and physics substep settings were not exported; do not infer those from the later source snapshot. There is no evidence that the old result depended on visibility skipping.

The old normal skeletal component ticks could use UE parallel animation evaluation; current explicit `RefreshBoneTransforms(nullptr)` cannot, because UE requires an executing component tick's valid completion handle. The [parallel-refresh audit](../Saved/JoltMigration/ParallelRefreshAudit.md) identifies an approximately 0.7 ms optimistic ceiling and substantial callback-order/lifetime work; no async mesh publication change has been promoted. The historical number is useful evidence of a cheaper path, but adding its 5.021 ms to today's isolated Jolt step would omit current work and mix cadence and workload.

## Complete actual NN measurements

The query collector was corrected to inspect the owner's actual root capsule: `AProphecyAgent` inherits `APawn`, not `ACharacter`. Its regression now exercises the real collector on a native APawn root capsule with Block/Ignore changes, rather than injecting a capsule only into the analytic math test. All three query tests passed with zero warnings/errors in `Foundation-20260909-141336-210/index.json`. Gameplay collision filters were unchanged.

The incomplete frame-210 failures are retained as diagnostics: `nn_jolt_partial_100_20260909_1346.json` averaged 13.0728 ms over 211 timed frames with 210 completed validation rows, and `nn_jolt_capsule_100_20260909_1403.json` averaged 13.0348 ms with the same scope. Neither is a successful performance run. The latter still used the incorrect owner-class lookup; it was not evidence of a near-coincident hit tolerance problem.

Three same-binary actual-NN runs then passed all 360 measured frames, with 60 warmup frames, 60 Hz world/physics/presentation, 30 Hz real CPU NN, controlled/restored performance-core placement, movement-only features, static floor and the same separated grid:

| Query-tree padding | Report under Saved/Benchmarks | Mean / median / p95 world ms | Query scene update ms | Total query publication ms |
|---|---|---:|---:|---:|
| 5 cm | `nn_jolt_padding5_A_100_20260909_1415.json` | 12.8267 / 12.9605 / 15.6977 | 0.7476 | 1.7373 |
| 20 cm | `nn_jolt_padding20_A_100_20260909_1416.json` | 12.3733 / 12.6233 / 15.0099 | 0.6715 | 1.6783 |
| 40 cm | `nn_jolt_padding40_A_100_20260909_1417.json` | 12.2308 / 12.2890 / 15.0600 | 0.6066 | 1.6028 |

Each completed 180 NN steps, 18,000 successful physical-feedback samples, 36,000 character/head-query rows, 792,000 native query-body checks and 3,168,000 skeletal-bone checks. All models use ORTCpu batch 100; the required walk/upper policies run, with four foot-roll steps and at least 1200 cm managed root travel. All head rays remained unfiltered: the capsule-only validation fallback count is **zero**. Affinity was restored. Removal during finalization, surviving rigs, stale-handle rejection and disable checks passed. The synthetic authored-packet mutation is deliberately skipped in actual-NN mode; its separate synthetic regression remains the evidence for that callback. No natural disjoint-old-AABB ray occurred, so the independent 150 cm post-EndPhysics control remains required. Full evidence and report hashes are in [the padding audit](../Saved/JoltMigration/QueryTreePaddingDraft/PaddingRunsAudit.md).

Padding is an explicit process-global Chaos dynamic-tree diagnostic (`-QueryTreePaddingCm`), not a production default or a Jolt solver adjustment. Independent before/after reads confirm the requested CVar and all 2200 skeletal actors in bucket 0 / dynamic inner bucket 1. Exact shape bounds/geometry and query cadence are retained. Larger parent bounds can increase query candidates in denser worlds; no reinsert counter was measured and these three trials do not establish a universal optimum.

At 40 cm, world phases averaged Agent 1.2582 ms, coordinator 6.9467 ms and manager 2.5833 ms. The coordinator includes 2.3932 ms native step, 0.5574 ms completed-pose batch and 3.8001 ms serial publication. Query publication includes 0.4423 ms validation, 0.0564 ms scale checks, 0.4519 ms body writes and 0.6066 ms scene updates. These are nested phases, not additive world costs. Real NN inference alone averaged 0.4705 ms per world frame.

The subsequent instrumented CSV run `nn_jolt_padding40_csv_100_20260909_1421.json` passed at 12.9770 ms mean. Its 341 marked CSV rows (`Profile(20260909_142002).csv`) show just 0.0176 ms EndPhysics wait, 0.8481 ms game-thread Physics and 0.2122 ms SyncBodies. Existing overlap already hides the asynchronous solver work; moving the NN producer to DuringPhysics is not a demonstrated saving. A previously running read-only report parse may have overlapped startup, so this is profiler evidence, not another quiet baseline. CSV WorldTickMisc includes validation outside the benchmark world timer and must not be added to its reported total.

The movement-only fixture now detaches the unused SpringArm/Camera subtree after disabling its ticks, preserving both components and their world transforms. `nn_jolt_detached_camera_100_20260909_1428.json` passed at **12.1549 ms mean, 12.0498 median and 15.0672 p95** with 40 cm padding. The manager visual-root phase fell from 0.8752 to 0.6969 ms; total world time fell by 0.0759 ms while other phases varied. The fixture records and verifies detached-subtree identities; it does not change player-camera defaults. This remains above the goal and excludes rendering, crowd intercontacts and active blood emission. The remaining integration resumes after the requested performance gate is met.

### Native packet storage, idle reads and worker count

Target publication now uses inline scratch storage for the usual 22-body packet and reuses the accepted rig packet's allocation after full transactional validation. Invalid, duplicate, foreign or nonfinite input still leaves the last accepted packet intact. Target commit averaged 0.1611 ms in the next locking baseline versus 0.2092 ms before this change; whole-run variation prevents attributing the entire world difference to allocation reuse.

The optional `-NoLockIdleReads` diagnostic selects Jolt's no-lock read interface only under the game-thread world's exclusive ownership before synchronous Update or after all its jobs have joined. Full native ID/sequence, broadphase and finite-state checks remain; mutation and in-step policies are unchanged. All **56 foundation tests passed** with this option enabled in `Foundation-20260909-144533-972/index.json`, with zero test warnings/errors. `-JoltWorkerThreads` separately selects the same solver's worker count; its default remains three.

Three quiet, same-binary runs use 100 actual-NN agents, 60 warmup/360 measured frames, movement-only, DuringPhysics, restored P-class game-thread placement and 40 cm query padding:

| Report under Saved/Benchmarks | Idle read policy | Jolt workers | Mean / median / p95 world ms | Native Update including servo ms |
|---|---|---:|---:|---:|
| `nn_jolt_lock_parts_A_100_20260909_1448.json` | Ordinary locks | 3 | 11.9068 / 11.9688 / 14.3971 | 1.8147 |
| `nn_jolt_nolock_parts_A_100_20260909_1451.json` | Exclusive-owner no-lock reads | 3 | 11.7612 / 11.8458 / 14.4249 | 1.8376 |
| `nn_jolt_nolock_workers7_A_100_20260909_1452.json` | Exclusive-owner no-lock reads | 7 | 11.3043 / 11.4290 / 14.0141 | 1.4181 |

All three report success and an empty error, 180 real NN steps, 18,000 physical samples, 360 validated frames and at least 1200 cm of managed root travel. These retain the complete workload and limitations above. They are single trials per setting, not proof of a universal worker optimum.

New native scopes partition the historical step interval into packet preparation, activation, PhysicsSystem::Update (including the servo), and sample capture. Additional body-state validation is outside that historical interval but inside the native wrapper/world time. In the seven-worker run these average 0.1688 / 0.0718 / 1.4181 / 0.0631 ms, with 0.1749 ms additional validation and a 1.9512 ms complete native wrapper. The world also includes Agent 1.1906 ms, coordinator 6.3981 ms and manager 2.3027 ms. The coordinator includes 0.5280 ms pure completed-pose batching and 3.7254 ms serial completed publication; the latter includes 1.5723 ms UE query publication. Real inference alone averages 0.4018 ms per world frame. Nested phases must not be added twice. The complete target remains unmet.

### Optional AVX2 profile: tested, no demonstrated world gain

The isolated AVX2/FMA/precise dependency and every native Jolt consumer compiled successfully. The baseline CPU preflight recorded required/supported mask 2015, missing mask zero and XCR0=7. Actual compiler response files specify `/arch:AVX2` and `/fp:precise`; native DLL startup independently matches ISA 2015 and policy 3. Jolt keeps double world positions, the same body/constraint settings and cadence. The original SSE2 dependency and eleven consumer binary/receipt files were preserved under `SSE2Consumer-20260909-1500` before switching. This profile needs the external CPU preflight before launch and is not a portable runtime ISA selector.

All 56 tests passed in `Foundation-20260909-150204-686/index.json`; the actual-NN two-agent smoke `avx2_nn_smoke_20260909_1506.json` passed real inference, movement and game-to-plugin pose/query/lifetime checks. Two quiet 100-agent AVX2 runs retain the same 60 warmup/360 measured frames and settings as the SSE2 seven-worker control:

| Report under Saved/Benchmarks | Workers | Mean / median / p95 world ms | Update including servo ms |
|---|---:|---:|---:|
| `avx2_nn_workers7_A_100_20260909_1507.json` | 7 | 11.4970 / 11.3195 / 14.3286 | 1.5094 |
| `avx2_nn_workers11_A_100_20260909_1508.json` | 11 | 11.4849 / 11.4800 / 14.3022 | 1.3252 |

Both pass with an empty error, 180 NN steps, 18,000 feedback samples and at least 1200 cm managed root travel. Seven-worker SSE2 previously averaged 11.3043 ms world and 1.4181 ms Update. These single trials establish no AVX2 whole-pipeline benefit. Increasing AVX2 workers lowered Update while manager cost rose from 2.2965 to 2.4146 ms. The active consumer was consequently rebuilt for SSE2 (`UEBuild-SSE2-Paused-20260909-1509.log`); the optional AVX2 recipe remains available, without changing the default or claiming cross-profile cooked-game validation.

### Packet prevalidation and query-scene maintenance control

The native world now commits its already accepted, disjoint rig packets through a private friend-only servo method. Public publication retains complete transactional checks. Regression construction also identified and fixed an existing finite-quaternion gap: SIMD `IsNormalized()` alone can accept NaN. Both accepted boundaries now explicitly check `ContainsNaN()` before normalization. The new real-Update invalid/empty-packet regression and existing multi-rig atomicity cases passed in the 57-success/one-failure foundation run `Foundation-20260909-150956-598/index.json`.

That run's one failure was the new paused-scene control's configuration gate: the ordinary project enables substepping, whereas the isolated benchmark explicitly disables it. Test-only scoped settings now match the benchmark and restore the project values after world teardown. The corrected `Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle` passed with zero warnings/errors in `Foundation-20260909-151233-643/index.json`: three native capsule spawn/non-teleport move150cm/remove cycles, eight stationary maintenance frames per moved capsule, strictly newer returned physics trees, current-area hits/original receiver/analytic entry points, old-area misses, native particle retirement, and resumed positive-dt simulation after restoration. Unknown receivers and native dynamic bodies are rejected.

`-PauseChaos` is an optional, benchmark-owned diagnostic that retains normal UE Start/End physics processing with zero integration delta for the default query-only scene. It does not disable the world physics ticks or drop queries. Each completed measurement audits the native object inventory, zero dynamics, solver frame advancement and zero delta; the original pause policy is restored before unmeasured lifecycle tests. The first actual-NN smoke `nn_jolt_pause_smoke_2_20260909_1514.json` correctly refused admission because the Entry map's automatically spawned DefaultPawn was outside its explicit receiver allowlist. No pause was applied and it contains no accepted performance measurement. Explicit bootstrap-pawn ownership is being resolved before the next trial.

## Accepted packet/query/feedback changes and current actual-NN controls (15:25–15:40)

The SSE2/shared-PCH game with exclusive idle reads and seven Jolt workers passes all 59 Jolt automation tests (`Foundation-20260909-151928-849/index.json`) plus both NN physical-feedback tests (`Foundation-20260909-152027-191/index.json`), with zero test warnings/errors. The latter includes 256 cases comparing all 131 raw lower/upper state floats bitwise against the unchanged reference encoder. A fresh D3D12 blood run (`jolt_current_blood_20260909_1529.json`) passes all three receiver classes and the existing mask/identity/restoration gates.

| Actual 100-character run | Mean world ms | Median ms | p95 ms | Outcome |
|---|---:|---:|---:|---|
| `nn_jolt_cache_control_A_100_20260909_1525` | 11.275188 | 11.264101 | 13.917297 | Normal processing, all gates pass |
| `nn_jolt_pause_A_100_20260909_1526` | 11.624585 | 11.716202 | 14.236901 | Immediate pause, 360 zero-dt maintenance frames; restored |
| `nn_jolt_pause_csv_100_20260909_1527` | 11.718573 | 11.941999 | 14.748700 | Immediate pause with CSV overhead, all gates pass |
| `nn_jolt_feedback_parts_100_20260909_1540` | 11.445705 | 11.644199 | 14.490999 | Normal, new sampling/encoding timers only, all gates pass |

Every run retains 60 Hz world/Jolt/presentation, 30 Hz real lower/walk/upper CPU inference at batch 100, four foot-roll iterations, 22 bodies/21 hard joints/88 bones per character, 2,200 Unreal query receivers, all 360 samples, 180 NN steps and 18,000 physical feedback samples. Minimum managed-root travel was 1,200.010681 cm. These are NullRHI separated-grid/static-floor controls with explicit restored P-class game-thread placement, DuringPhysics, 40-cm broadphase padding and movement-only shells. They do not establish rendered FPS, dense contacts or active blood GPU cost.

The accepted private commit reduces native packet preparation from about 0.169 to 0.073 ms; it only consumes already accepted, disjoint owned rig packets and preserves public validation. The public boundaries now explicitly reject nonfinite quaternions before UE's normalization predicate. Query preflight remains before mutation, with authored/native simulation state checked separately; validation cost falls from about 0.429 to 0.355 ms. The 25-slot per-sample rotation cache changes 31 conversion requests to 21 unique conversions without persistent pose state; measured resampling savings are small and should not be exaggerated.

The new sampling split shows only **0.110431 ms** for completed physical component-pose reads and **0.080303 ms** for raw lower/upper encoding, within **0.545937 ms** total physical resampling. The rest includes lane checks, tolerance application and recurrent-state maintenance. Replacing relative-transform math cannot plausibly close the whole remaining 1.45-ms gap on this evidence. The same run measured **2.775640 ms** RefreshBones, including **1.497332 ms** retained query publication; those nested times must not be added.

Immediate pause admission was corrected to explicitly allow only Entry's exact native GameModeBase/DefaultPawn possessed bootstrap, after the first smoke properly refused that previously unlisted actor. Every admitted native object remains audited for exact scene, zero GT/PT dynamic state and current queries; arbitrary pawns remain refused. The source/CSV audit (`PausedSceneRemainderAudit.md`) finds SyncBodies about 0.466 ms in the paused trace versus 0.212 ms in the older normal trace. Those CSVs are not an exact same-binary attribution, but the retained warmup pull buffer is a concrete source-supported explanation. Neither trace contains extra PhysicalMesh primary/EndPhysics ticks. Normal Chaos scene maintenance remains preferred.

## Deferred maintenance and game compiler comparison (15:45–16:16)

Deferred pause now preserves the first two ordinary, counted positive-delta measurement frames before 358 zero-delta maintenance frames. The separate dynamic-to-kinematic/newer-tree query regression and full NN lifecycle gates pass. `nn_jolt_deferred_A_100_20260909_1545` measured **11.118764 ms mean / 11.215702 reported median / 13.718899 p95**; its same-binary ordinary control `nn_jolt_deferred_control_B_100_20260909_1546` measured **11.231969 / 11.221703 / 13.832800**. The 0.113206-ms mean difference is small, and conventional two-middle-value median slightly increases. `Saved/JoltMigration/DeferredPauseComparison.md` records the independent complete-row audit. No production pause default or sub-10-ms result is established.

An isolated game-module compiler comparison used private PCHs in **both** SSE2 and AVX2 controls, identical 109 source-file hashes, unchanged external Engine/Core/ORT libraries and the same SSE2 native Jolt DLL. Runtime admission probes and per-build response-file/layout evidence passed. Each profile passed all 59 Jolt, two feedback and three physical-target tests before its timed runs. The four complete actual-NN runs all preserve the existing 360-frame, 36,000-agent-row, 792,000-body/query-check, 3,168,000-bone-check and 18,000-feedback gates.

| Game profile / report stem | Mean world ms | Reported median ms | p95 ms |
|---|---:|---:|---:|
| `game_sse2_private_100_A_20260909_1557` | 11.246967 | 11.156701 | 13.928801 |
| `game_sse2_private_100_B_20260909_1558` | 11.538862 | 11.718299 | 14.539700 |
| `game_avx2_private_100_A_20260909_1608` | 11.416796 | 11.639301 | 13.962600 |
| `game_avx2_private_100_B_20260909_1609` | 11.338027 | 11.588901 | 14.120601 |

Mean-of-means is **11.392915 ms SSE2 versus 11.377411 ms AVX2**, a 0.015503-ms difference (0.136%): no meaningful gain. `Saved/JoltMigration/GameModuleSimdComparison.json` independently audits the four reports and retained provenance. The default shared-PCH/SSE2 game profile was restored successfully in `UEBuild-DefaultEndpoint-20260909-1616.log`. Optional compiler diagnostics remain explicit; they are not production requirements. Loaded Engine reports already show its bone-pose and skinned-asset ISPC controls enabled. Game-module ISA flags do not recompile those Engine routines or ORT.

## Endpoint cache rejected; native package setup validated (16:23–16:32)

The restored DEFAULT/shared-PCH build passed all 59 Jolt tests (`Foundation-20260909-162353-898`). An exact endpoint cache then passed eight physical-target tests (`Foundation-20260909-162723-443`): the original sparse/full-skeleton oracle plus invalidation, interpolation/rigid-forearm, nonfinite and repeated aliasing cases. The cache compares full operand bytes, including SIMD W lanes, and keeps live layout/PHAT checks. Its alias fallback preserves the original evaluator's ordered side effects.

Same-binary actual-NN runs `nn_jolt_endpoint_off_A_100_20260909_1630` and `nn_jolt_endpoint_on_B_100_20260909_1631` both pass all native runtime gates. Seven dependency/module hashes captured before the pair still match afterward (`EndpointCacheBinaryCapture-20260909-1630.json`, `EndpointCacheBinaryAfter-20260909-1632.json`).

| Endpoint path | Mean world ms | Reported median ms | p95 ms | Target-read ms | Endpoint expansion ms |
|---|---:|---:|---:|---:|---:|
| Original | 11.347207 | 11.535101 | 14.057901 | 0.578378 | 0.106519 |
| Exact cache | 11.394867 | 11.464700 | 14.220499 | 0.652015 | 0.054707 |

Expansion work halves, but its checking/copying overhead increases the inclusive target-read interval by 0.073637 ms. There is no demonstrated total improvement. The candidate is rejected and its measured source, alias fix and tests are archived under `Saved/JoltMigration/EndpointCacheComparisonDraft/CacheSourceArchive`; the original evaluation path and original three tests have been restored with exact source-hash checks. The endpoint phase timer remains useful measurement. The independent `EndpointCacheComparison.json` audits every row and confirms 36,000 versus 18,000 expansions, exactly tracking the 180 NN/interpolation frame pairs. All other workload/query/lifecycle checks pass.

The dormant native query-padding setup for packaged runs now passes a 2-agent/60-frame actual-NN smoke (`nn_jolt_native_padding_smoke_20260909_1629.json`): effective padding **5 → 40 → 5 cm**, priority flags **0 throughout**, full NN/body/bone/query/lifecycle gates pass. UE5.7 requires an explicit constructor-priority setter for a default CVar; implicit current-priority replacement was correctly rejected by the first smoke before measurement. The corrected helper captures the original priority/tag and restores the effective value/flags. It does not claim a byte-identical history-allocation snapshot or concurrent third-party history monitoring. Normal benchmarks keep their existing explicit ExecCmds setting; the native control is opt-in. No packaged current-source build/runtime result exists yet.

## Prepared feedback comparison and packaged checkpoint (16:37–16:47)

`UEBuild-FeedbackRollbackFreshInputs-20260909-1637.log` successfully compiles the restored original endpoint path plus optional prepared feedback. All three NN feedback tests pass (`Foundation-20260909-163756-375`), including the new full-state serial/parallel oracle, followed by all 59 Jolt tests (`Foundation-20260909-163819-866`). Each feedback mode then passes a 2-agent/60-frame live smoke. Original is still the default; the native setter accepts the optional mode only before manager BeginPlay, and synchronous mode-transition sampling retains the original serial helper.

Prepared modes capture the same physical pose and tolerance/flag inputs on GT, then operate on unique fixed per-agent state slices. The joined kernel makes no UObject calls, tolerance-map lookups or GT profiler calls. All kernel invocations finish before `ParallelFor` returns; scheduler cleanup objects may outlive that call. Original and prepared serial/parallel outputs match all eleven buffer families and recurrent flags in the native oracle, including equality/first-sample/run-walk/mixed omitted lanes. The live fixture independently preserves actual sampling and full runtime gates.

| Same-binary report suffix after `nn_jolt_feedback_` | Mean world ms | Reported median ms | p95 ms | Inclusive feedback ms | GT preparation ms | Joined kernel ms |
|---|---:|---:|---:|---:|---:|---:|
| `original_100_20260909_1641` | 11.521021 | 11.542801 | 14.564000 | 0.544910 | 0 | 0 |
| `preparedserial_100_20260909_1641` | 11.376522 | 11.458300 | 14.110100 | 0.535807 | 0.037457 | 0.376720 |
| `preparedparallel_100_20260909_1641` | 11.472184 | 11.642002 | 13.852797 | 0.258446 | 0.038692 | 0.091571 |

`Saved/JoltMigration/PhysicalFeedbackComparison.json` independently passes all 1,080 recorded frames and the seven before/after binary hashes. Every prepared run completes exactly 180 joins and 18,000 items, correlated with the 180 NN steps; Original's prepared counters stay zero. Full rig/bone/query counts, root travel, control restoration and teardown remain unchanged. Parallel feedback saves **0.286463 ms** in its inclusive interval versus Original, but the disjoint remainder grows **0.237627 ms** in this one run. The small total difference is not proof of an overall speedup or its cause. The goal is still unmet.

A fresh isolated snapshot under `Saved/JoltMigration/NNCrowd-20260909-144331-647` (directory timestamp UTC) contains 864 input files and the eight-package mannequin/PHAT closure. Copying does not modify original source/assets/models; `Preservation-20260909-1647.json` checks all 333 original tracked files and ten original untracked source copies, with no unexpected changes. Its fresh Editor build succeeds and all five matching-source query tests pass (`Project/Saved/JoltMigration/Foundation-20260909-164848-303`). The first Development Game compile finds two benchmark-only `UClass::ClassGeneratedBy` references unavailable without editor data. Both are replaced with `HasAnyClassFlags(CLASS_CompiledFromBlueprint)`, retaining the native/Blueprint admission check and count using the serialized runtime flag.

The reviewed source revision **`snapshot-r2.json`** records the single-file class-flag fix, predecessor/failed-package hashes and an archived original CPP. The first `snapshot.json` and failed package report remain historical evidence. The r2 Editor/Game builds and all five matching-source query controls pass, but its cook fails before staging. Main-project Editor was also rebuilt successfully after the two-line runtime class-flag fix (`UEBuild-MainRuntimeClassFlag-20260909-1815.log`). Optional prepared modes remain available, with Original as default and strict mode/counter validation.

The complete r2 cook log identifies five omitted native constructor assets and the configured mobile-input asset. Seven Engine/plugin package saves also exceed the cooker's 260-character path limit; the fourteen later NeverCook-reference errors point to those same failed targets. `Saved/JoltMigration/CookEngineDiagnosisDraft` records the source diagnosis. The packaging wrapper now uses fresh, owned short cook/stage directories through UE's supported `-CookOutputDir` option, retaining the plugin set and normal dependency validation. The snapshot's original registry inventory does not cover four newly required roots, so a focused registry export is required before extending its asset closure. Existing failed manifests, logs and output directories remain intact.

The drive reached approximately 0.4 GiB free during the first package build. Reversible NTFS compression of exactly two newly created snapshot PCH caches and 52 dated migration JSON reports recovered space to about 4.6 GiB. Every file's SHA256 was checked before/after; paths and contents remain identical. No files were deleted and no source, runtime executable/DLL, asset or unrelated project data was compressed. Records are `SnapshotPCHCompression-20260909-1656.json` and `ReportCompression-20260909-1658.json`. Future build/cook stages still require free-space monitoring.

## Native proxy correction and packaged runtime checkpoint (20:16–20:24)

The native snapshot proxy had no graph root and never advanced UE's graph traversal counter, causing RefreshBoneTransforms to repeat the explicit zero-delta animation update. Its new UpdateAnimationNode override records the actual update, following UE's native-proxy pattern. Both tick and refresh remain. All five query regressions pass (`Foundation-20260909-201658-412`), including all 88 evaluated bones and current queries across repeated same-frame publications, clear/reinitialization and revision reuse. Two-agent and complete 100-agent NN runs pass. The independent `RemainingTickAuditDraft/ProxyTraversalComparison.json` verifies all rows and seven before/after binary identities. This is synchronous publication coverage.

`nn_jolt_proxy_traversal_100_20260909_2019.json` records exactly **36,000 PreUpdates instead of 72,000**, retaining every evaluation/finalization, 792,000 body/query checks, 3,168,000 bone checks and 180 actual NN steps. RefreshBones falls from **2.823204 to 2.629975 ms**, but world mean is **11.878346 ms**, median **11.552498**, p95 **16.108699**. NN inference rises from 0.409541 to 0.714839 ms between these different-build, different-time runs. The duplicate work is removed; an overall speedup or cause of the inference variation is not established. The target remains unmet.

The active isolated manifest is now **`snapshot-r3.json`**: an asset-only revision retaining the pre-proxy-fix runtime code as a control. A successful focused registry export supplies all eight roots and 487 nodes. It adds 440 read-only files (286,329,756 bytes), for 1,304 inputs and 448 Game source packages; normal cooking must produce the independently verified 310 runtime Game packages plus 13 external packages. All 39 external source packages are hash-checked. The short-path Development build/cook/stage passes in `Packages/Development-20260909-182138-971/package.json`. Its first two-agent runtime crashes at frame 119 before writing the complete JSON (`Runs/Development-C2-20260909-182410-450`), so there is no accepted packaged performance result. The retained matching PDB/minidump are being used to identify the failure; no lifecycle validation is bypassed. Preservation audit `Preservation-20260909-182418-072.json` checks all 343 original tracked/untracked-source paths with no unexpected changes.

Matching-PDB symbolization resolves the r3 crash to `SaveMultiJoltCase`'s removal callback at line 684, immediately after it unregisters itself and frees its captured data. Both that callback and the synthetic mutation callback now remain bound until their existing post-StepAndPublish cleanup; their guards prevent reentry. This fixes the test lifetime error while retaining the actual removal/mutation checks. `PackagedCrashSymbolizationDraft/SymbolizedStack.json` retains all 26 resolved game frames and exact image/PDB hashes; the original r3 PDB is archived with hash-preserving NTFS compression. **`snapshot-r4.json`** replaces only the callback source, native proxy and strengthened query test, retaining all 1,304 inputs and the r3 asset/model/config closure. R3 source files are archived separately; its historical manifest intentionally no longer validates against the revised Project. The r4 package rebuild is pending. Main-project Editor must be rebuilt for the callback fix before further main-project runtime tests.

## First packaged actual-NN result (20:36)

R4 Editor/Game builds, all five strengthened query controls (`Project/Saved/JoltMigration/Foundation-20260909-203115-471`), cook/stage and fresh two-agent runtime pass. The first complete **Development 100-agent run averages 9.471366 ms**, with **10.352697 ms median / 12.583900 ms p95**. Its runner is `Runs/Development-C100-20260909-183617-557/runner.json`; the frozen manifest SHA256 is `6F574706F36DBDE8E99472870C175E0D273F6C647ECEBF5E2552BE6C71AB64B6`. All 360 frames, 36,000 agent rows, 792,000 body/query checks, 3,168,000 bone checks, 180 real NN steps and 18,000 physical samples pass, using Original feedback. This is the first below-10-ms average for the retained actual-NN workload, not a below-10-ms tail, repeated-trial result or rendered/full-world acceptance. Shipping is being built from the same manifest.

The packaged report checker now follows UE's case-insensitive FName identity for the head bone: cooked output displays `Head`, while the native validator already requires exact receiver/owner pointers and `FName("head")`. Only this display-case mismatch was corrected; native geometry/identity and all other gates remain. The initial rejected report and successful separate revalidation are retained, followed by a fresh passing runner.

A separate real lifecycle limitation remains: disabling inside bone finalization calls SetAnimInstanceClass while evaluation is active, so UE refuses it; the immediate NN kinematic-pose application then fails and its caller ignores that result. The existing body-removal checks do not establish successful animation restoration. This warning also appears in older Editor runs. A correction that restores animation after evaluation returns, with explicit fresh-pose tests, is required before claiming complete mode-transition behavior. No goal-completion claim is made from the timing average alone.

Independent R4 audit (`Saved/JoltMigration/PackagedR4AuditDraft/PackagedR4Comparison.md`) verifies 370 artifact hashes and all preserved workload counts, but finds a diagnostic export defect: ECC_MAX includes a deprecated flag beyond the response container's 32 stored channels. The exporter reads an invalid 33rd byte; the real 32-channel policy is identical for all 100 agents. The correction must derive the loop bound from the stored array and reject every extra response in future validation. Historical R4 reports remain unchanged and do not satisfy that corrected gate.

R4 Shipping compilation completes successfully (90 actions), but cooking fails with Zen storage errors in `Packages/Shipping-20260909-184041-894/package.json`. There is no Shipping runtime measurement. Generated compiler-cache compression retained exact content; after the user freed space and explicitly requested generated-junk cleanup, `SupersededPackageCleanup-20260909.json` records removal of the superseded R3 Cook/Stage and failed Shipping Cook/Stage. The R3 executable and complete crash directory are preserved under `PackagedCrashSymbolizationDraft/R3RuntimeArchive`, alongside the matching archived R3 PDB and symbol report. Working R4 Development staging, source/assets/models and historical reports remain. Automatic review separately rejected removal of two additional loose-cook folders before execution; those remain and are not retried through another mechanism.

## NN-frame timing diagnosis and corrected source revision

`Saved/JoltMigration/PackagedR4NNFrameDraft/NNFrameGroups.md` retains every measured frame and splits it by actual NN counter increments. All 180 intermediate frames are below 10 ms (7.405 ms mean, 9.558 ms maximum); all 180 NN frames are above 10 ms (11.538 ms mean, 10.353 ms minimum). The reported upper median is therefore the fastest NN frame, not a representative middle of a single timing cluster. The NN manager explains 4.054 ms of the 4.132 ms mean difference (98.1%); coordinator work differs by only 0.005 ms. The 18.379 ms first-frame maximum remains in the data and includes a separate 7.777 ms unassigned world remainder.

On NN frames, manager measurements include 2.058 ms inference, 0.924 ms physical resampling, 0.577 ms pose-store publication, 0.331 ms output processing, 0.140 ms remaining input construction and 0.479 ms visual-root work. These follow the documented timer hierarchy; nested intervals must not be added again. This benchmark is walking: the WALK and upper networks execute in sequence, and RUN is loaded/validated but is not executed while every lane has bRun=false. Upper input depends on the new lower output, so parallelizing the two calls would change behavior.

Installed UE5.7 source selects different ORT defaults: Editor uses the global pool with automatic intra-op threads, while packaged Game uses per-session pools with intra-op=1, inter-op=1 and sequential execution. No project override was found. That is a concrete configuration factor to measure, not yet a proven speedup. Development startup INI overrides are supported; ordinary non-server Shipping compiles that override parser out. Effective settings must be recorded, and a Shipping factor must be an explicit isolated packaged configuration. Models, cadence, feedback, completed poses and retained queries remain unchanged.

R5 (`snapshot-r5.json`, SHA256 `0699A1988BC17AB883B297D897F992583F5D29EF6FC1FFA9BBA722B07BD2CD3A`) replaces six reviewed source files and archives their R4 bytes. It fixes same-call-boundary NN restoration, guards reentrant ownership changes, covers direct component cleanup, and bounds the diagnostic response export to its actual array. The new validator passes 110 deliberately constructed positive/negative contract fixtures and matches its reviewed draft exactly. Snapshot Editor and Development Game compilation pass, as do all five matching query controls (`Project/Saved/JoltMigration/Foundation-20260909-210838-879`); cooking/runtime validation is still in progress. Preservation report `Preservation-20260909-191118-717.json` verifies all 343 original paths and the six source/archive pairs with no unexpected changes.

R5 Development cooking/staging completes successfully after rebuilding missing shader/asset caches (`Packages/Development-20260909-190729-992/package.json`, BuildCookRun 951.73 seconds). The fresh smoke `Runs/Development-C2-20260909-192634-306` passes every restoration/response gate and contains no SetAnimInstanceClass warning. Its measured probe shifts are 17.000000000000046 and 24.000000000000064 cm, within the declared conversion tolerance. Two quiet complete 100-agent runs then pass:

| R5 Development run suffix | Mean world ms | Reported upper median ms | p95 ms | Maximum ms | NN-frame mean ms | Intermediate mean ms |
|---|---:|---:|---:|---:|---:|---:|
| `192656-176` | 9.145706 | 10.208301 | 11.617500 | 17.998103 | 11.109899 | 7.181512 |
| `192745-905` | 9.248746 | 10.263298 | 11.860304 | 19.315399 | 11.243387 | 7.254106 |

`Saved/JoltMigration/PackagedR5ComparisonDraft/BaselineR5Development.json/.md` independently passes all 19 gates per run and retains all rows, including maxima. Each run has 36,000 agent records, 792,000 body/query checks, 3,168,000 bones, 180 real NN updates and 18,000 feedback samples. The repeated mean is 9.197226 ms, but all 360 NN frames across both runs remain above 10 ms and all 360 intermediate frames below. The complete target is still unmet; this is corrected/repeated Development evidence, not Shipping, dense contacts, active blood rendering or final game frame time. Shipping is building from the exact R5 manifest and matching Development controls before any inference factor is changed.

## Standalone iteration resumed (22:00–22:05)

R5 Shipping repeats pass the corrected complete native workload at 7.976 / 8.006 ms mean, 9.039 / 9.095 ms upper median and 10.918 / 10.694 ms p95. See `Saved/JoltMigration/PackagedR5ComparisonDraft/BaselineR5AllBuilds.json/.md`; slow frames and representative full-world acceptance remain open.

R6 Development same-executable ABBA trials find no total gain from per-session intra-op 2: approximately 9.347 ms with one versus 9.356 ms with two. `ORTThreadingR6Draft/FactorComparison.json/.md` retains all four runs. No production default changed.

Per the user's instruction, further source iteration uses standalone, with packaging reserved for the final candidate. `Tools/NN/RunSterilePhysicsBenchmark.ps1` can select the already-built project snapshot and apply a process-only EditorThreadingOptions tuple matching Game settings. Native capture verifies the selected tuple before and after model creation. The two-agent smoke passes. Four 100-agent/360-frame runs all pass native checks with empty errors:

| Standalone factor | Mean world ms | p95 ms |
|---|---:|---:|
| Per-session, intra-op 1 | 10.608 | 13.450 |
| Shared pool, intra-op 2 | 10.701 | 13.484 |
| Per-session 1, prepared parallel feedback | 10.677 | 13.434 |
| Per-session 1, original feedback repeat | 10.512 | 13.239 |

Pointers: `Saved/JoltMigration/CurrentStandaloneOrtComparison-20260909.json` and `CurrentStandaloneFeedbackComparison-20260909.json`. Shared inference and parallel feedback shorten their local phases but establish no whole-world improvement; retain Original feedback and one-thread Game defaults. These standalone numbers are relative iteration evidence, not substitutes for Shipping timings. No build or cook was needed for these trials.

The main Editor is now current (`UEBuild-StandaloneCurrent-20260909-220522.log`, successful 83.81-second incremental build). `CurrentStandaloneMainControl-20260909.json` points to its complete passing 100-agent run: 10.599528 ms mean / 11.763901 median / 13.300501 p95. An otherwise matching automatic Editor ORT-pool run (`CurrentStandaloneMainAutomaticOrt-20260909.json`, native global=true/intra=0/inter=0) passes correctness but measures 17.816931 mean / 40.096100 p95, with 4.745962 ms average inference per world frame. That single trial establishes no useful improvement; no automatic-pool production override is proposed.

## Pose batching experiment closed; integration resumed

The optional pose-math batch compiled and passed exact serial/parallel equivalence (`Foundation-20260909-221745-642`). Both directions of a 100-agent standalone comparison passed full native validation. Serial means were 11.053900 / 11.257971 ms; parallel 10.446403 / 11.513155 ms. Pose-store time fell consistently (about 0.29 to 0.20 ms per world frame), but whole-tick improvement did not repeat. The candidate and its launcher flag were rolled back to exact pre-candidate source; rebuild passed (`UEBuild-PoseBatchRollback-20260909-222254.log`, 39.48 seconds). Raw report pointers are `CurrentStandalonePoseComparison-20260909.json` and `CurrentStandalonePoseRepeat-20260909.json` under Saved/JoltMigration.

The user explicitly accepts the best R5 Shipping setup as enough optimization for now and requests resuming integration. `Docs/JoltAcceptedPerformance.md` is the accepted checkpoint. Do not continue performance trials or require the old tail target before gameplay integration.
