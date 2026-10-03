# Controlled 100-character scheduling comparison - September 9, 2026

DuringPhysics plus batched pose composition averaged **9.098914 and 8.985956 ms** in two complete 360-frame synthetic JoltCrowd runs. Both are below 10 ms on average; their p95 values remain above 10 ms. This is a verified diagnostic checkpoint, **not completion of the actual-NN CPU goal**, a production P-class policy, or a decision to make DuringPhysics the default.

The root task confirmed the four runs used the same game binary. The retained logs agree on UE5.7.4 CL51494982 and the command-line workload; each report contains no game-binary hash, so the artifact alone cannot independently establish binary identity. [Compact measurements, hashes and checks](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/GameThreadPlacementDraft/ControlledComparison.json>) retain all four reports separately. No measured samples were removed.

## Workload and timing

All four run one floor-gravity case with 100 separated characters, 60 warmup frames, 360 measured frames, 30 Hz synthetic authored-pose publication and fixed 60 Hz physics/presentation. Each retains 22 dynamic Jolt bodies, 21 joints and the full 88-bone skeleton. Native manual fixture cameras and fist overlay are disabled under the explicitly authorized movement profile. Materials/query receivers remain present; no angles, precision, pose cadence or geometry are reduced by the compared flags.

These are NullRHI runs with static-floor contacts; self/crowd contacts, NN inference, recurrent manager updates, rasterized pixels and blood rendering are outside this workload. The measured world interval includes synthetic publication, Agent target preparation, the shared native step, full skeletal presentation and query synchronization. Exhaustive body/bone/ray validation and lifecycle regressions run afterward. World elapsed time includes waits/overlap; it is not summed CPU consumption across workers. Frame intervals include those diagnostics and are larger than the measured world interval.

| Run | World mean ms | Benchmark median ms | Benchmark p95 ms | Frames >10 ms | Frame-interval mean ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| [PrePhysics, serial](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_pclass_pre_serial_100_20260909_1326.json>) | 10.419513 | 10.447200 | 11.652399 | 196/360 | 16.226346 |
| [DuringPhysics, serial](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_pclass_during_serial_100_20260909_1327.json>) | 9.309291 | 9.456702 | 10.654099 | 101/360 | 15.122718 |
| [DuringPhysics, batch A](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_pclass_during_batchA_100_20260909_1325.json>) | 9.098914 | 9.271499 | 10.381699 | 52/360 | 14.961397 |
| [DuringPhysics, batch B](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_pclass_during_batchB_100_20260909_1328.json>) | 8.985956 | 9.160001 | 10.171100 | 36/360 | 14.698300 |

The benchmark sorts all 360 observations and reports index180 as its median and index342 as p95 (`ProphecyPhysicsBenchmark.cpp:67-75`). These exact conventions were independently checked. Conventional medians averaging indices179/180 are respectively **10.447150, 9.456351, 9.263000, 9.158699 ms**, also retained in JSON. The two equal-sized batch runs have a mean of run means of **9.042435 ms**; this aggregate does not replace their individual tails. Cold initial samples remain included; maximum world times were 22.521701, 17.373700, 14.312599 and 14.163900 ms.

## Placement control verified

Every report records request/apply/restore success, with no pending restoration or affinity error:

- Original GT affinity: group0, `0xfff`; requested/applied: group0, `0xff`; restored: group0, `0xfff`.
- Selection includes all eight logical CPUs in the highest exposed EfficiencyClass1: logical0-7, including both SMT threads of four physical cores. The helper derives these indices from topology.
- Process and system masks remain `0xfff`; process priority remains Normal32, GT priority remains +1. Profiler initial/final policy snapshots independently observe applied/restored GT masks.
- All **1,440 measured frame starts and ends**, all **72,000 serial compose entries**, and all **144,000 refresh entries** are within the selected class. No sampled E-class entry or provenance overflow occurred. Per-frame processor duration partitions differ by exactly **0 ms** and **0 calls** from their corresponding phase totals.
- Begin/end CPU IDs differ on 226/253/261/265 frames respectively, all within the permitted P-class mask. Entry observations are not continuous residency. Batch worker residency was not sampled, and worker scheduling was not restricted by the helper.

No process affinity, CPU-set assignment, power plan, QoS or worker policy was changed. Native power-throttling reads still return error87, so QoS is unknown. Frequency and thermal state are unmeasured; this controls GT class rather than every source of timing variation.

## What changed in the measured phases

All entries below are means in milliseconds. Child scopes must not be added again to their parents. The serial completed-pose total and joined batch stage are disjoint; adding those two gives completed-pose staging plus publication. The native wrapper includes work beyond the internal Jolt Update timer.

| Scope | Pre serial | During serial | During batch A | During batch B |
| --- | ---: | ---: | ---: | ---: |
| Agent tick total, including targets | 1.232174 | 1.212164 | 1.237876 | 1.219832 |
| Synthetic fixture publication | 0.803419 | 0.789437 | 0.797267 | 0.786431 |
| Shared coordinator total | 6.066362 | 6.151690 | 5.906288 | 5.811953 |
| World remainder outside those three totals | 2.317557 | 1.156000 | 1.157482 | 1.167739 |
| Native-step wrapper, inside coordinator | 1.808571 | 1.924547 | 1.986750 | 1.967478 |
| Internal synchronous Jolt Update | 1.624973 | 1.739791 | 1.784246 | 1.774592 |
| Serial completed-pose publication/staging | 4.087525 | 4.031595 | 3.149018 | 3.078479 |
| Joined batch stage, including GT input/body capture | 0 | 0 | 0.595956 | 0.597218 |
| Completed staging + publication | 4.087525 | 4.031595 | 3.744975 | 3.675697 |
| Serial compose child | 0.713625 | 0.709016 | 0 | 0 |
| Refresh-bones child | 2.339055 | 2.299072 | 2.379760 | 2.321873 |
| Query-update child | 1.272146 | 1.245062 | 1.300816 | 1.291308 |

**Changing serial PrePhysics to serial DuringPhysics** reduces world mean by **1.110221 ms (10.6552%)**. The coordinator actually increases by 0.085327 ms and the native wrapper by 0.115976 ms. The world remainder decreases by **1.161556 ms**, accounting for the gain. This is consistent with the intended phase overlap and reduced exposed waiting, not faster solver work. These runs did not capture engine CSV scopes, so the remainder cannot identify the exact individual engine wait/tick responsible.

**Adding batching within DuringPhysics** reduces completed staging plus publication by **0.286620/0.355898 ms** and coordinator time by **0.245402/0.339737 ms**. World mean decreases **0.210377/0.323335 ms (2.2599%/3.4733%)**. Other phase variation partly offsets the composition savings. Joined batch wall time includes GT body/input capture and parallel scheduling/join overhead; comparing it only to the serial compose child would omit those different boundaries.

## Functionality and lifecycle evidence

Every report has an empty error string and `multi_jolt_validation.success=true`. Independent rechecks cover all **36,000 character-frames per run**, or **792,000 dynamic body-frame checks and 3,168,000 skeleton bone-frame checks per run**. Every measured frame has 2,201 world bodies including the floor, 2,100 joints, exactly one shared step, 100 coordinator owners and zero Chaos dynamic bodies. Configured, actual and observed coordinator groups agree: 0 for PrePhysics, 2 for DuringPhysics. Completed revisions advance once per frame for every character.

The native post-step active-body snapshot is 2,200 on 356 frames and 0 on four frames: **70,159,256,353**, identically in every run. Every following frame has all 2,200 active again. This is transient post-step sleeping, not a continuously sleeping crowd; it also means these results must not be described as continuously awake load. All 360 samples remain included. The existing servo explicitly activates target bodies before Update; the post-step snapshot does not describe how many bodies were integrated throughout the preceding solver update.

All four modes perform the same **36,000 post-EndPhysics per-character query validations**. They verify all 22 current native query-body poses and a ray against retained head geometry/receiver identity. Maximum feedback/socket disagreement across every run is **1.2869261e-12 cm / 2.4148365e-6 degrees**, with zero scale disagreement. Maximum query-body/bone disagreement is **1.3406494e-13 cm / 5.3997387e-6 degrees**.

Natural crowd motion yields no ray wholly outside the prior query AABB; the report explicitly references separate controlled evidence. The retained [foundation result](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Foundation-20260909-132035-560/index.json>) contains `Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose`: **Success, zero warnings/errors**, with two controlled 150 cm updates. Its log records prior-tree/old-PT/new-GT versions 0/0/1 then 0/1/2, testing a newer external pose across EndPhysics. Root ran this against the matching source before these measurements; the benchmark JSON itself does not execute or certify that separate test.

Each run also passes these unmeasured lifecycle checks:

- First character's bone-finalization callback changes character 99's local-only authored root by exactly 11 cm and republishes in the same engine frame before character 99 consumes its pose. Original source values are restored afterward. Final local/world root position errors are both exactly 0.
- Serial diagnostic runs record **0 batch calls /100 serial compose calls** in this callback step. Both batch runs record **1 joined batch /1 serial fallback**, proving the later callback invalidates the cached pose and recomputes that character.
- Removal during bone finalization rejects all 22 removed handles, preserves 2,178 survivor handles, and allows 99 survivors to advance through a further explicit world step. Remaining resources are 2,179 bodies including floor and 2,079 joints.
- Final disable leaves one floor body, zero joints, zero coordinator owners and zero Chaos dynamic bodies, rejects all 2,200 former rig handles, and returns characters to kinematic mode.
- Pending late-admission request/idempotence/cancellation passes, preserving 2,178 survivor states and emitting no completion callback on cancellation. The artifact explicitly does **not** exercise next-frame admission/drain or deferred failure callbacks.

There are **three** native steps beyond the 360 timed samples: callback invalidation at 361, removal at 362, survivor step at 363. The report's `extra_unmeasured_lifecycle_steps=2` counts the latter two; the callback step is separately recorded. None is included in the timing table.

## Acceptance remains bounded

This confirms the synthetic static-contact integration improves under controlled GT placement while preserving the checked bodies, joints, full pose presentation and query behavior. It does not prove actual 100-agent NN inference/feedback/capsule workload below 10 ms, a p95/worst-frame 10 ms budget, rendered gameplay cost, production contact stress or blood pixels. DuringPhysics and GT placement remain explicit opt-ins. Continue the real-NN validation and retain this comparison as a diagnostic baseline rather than silently applying its scheduling control to production.
