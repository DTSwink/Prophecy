# Idle body reads and worker-count comparison

Independent read-only audit, 2026-09-09. All 26 checks pass for each complete report. [Compact JSON evidence](C:/Users/singerie/Documents/Unreal%20Projects/Prophecy/Saved/JoltMigration/IdleWorkerComparison.json) contains source SHA256 hashes, exact per-run checks, phase means, CPU placement and lifecycle evidence. No UE process, build or active-source edit was performed.

| Retained report | Every row: NoLock / workers / job concurrency | World mean / median / p95, ms | Native Update including servo, ms | Historical Jolt step, ms | Frames over 10 ms |
| --- | --- | --- | --- | --- | --- |
| [1448 locking](C:/Users/singerie/Documents/Unreal%20Projects/Prophecy/Saved/Benchmarks/nn_jolt_lock_parts_A_100_20260909_1448.json) | false / 3 / 4 | 11.906763 / 11.968799 / 14.397100 | 1.814681 | 2.144577 | 294 / 360 |
| [1451 NoLock](C:/Users/singerie/Documents/Unreal%20Projects/Prophecy/Saved/Benchmarks/nn_jolt_nolock_parts_A_100_20260909_1451.json) | true / 3 / 4 | 11.761240 / 11.845797 / 14.424901 | 1.837611 | 2.137608 | 277 / 360 |
| [1452 NoLock, seven workers](C:/Users/singerie/Documents/Unreal%20Projects/Prophecy/Saved/Benchmarks/nn_jolt_nolock_workers7_A_100_20260909_1452.json) | true / 7 / 8 | 11.304268 / 11.428997 / 14.014099 | 1.418071 | 1.721786 | 219 / 360 |

Flags above are verified from every `multi_jolt_frames[].jolt` object, not inferred from filenames. Job concurrency is the configured capacity (workers plus participating caller), not measured simultaneous utilization. Root identified these as the same binary; the JSONs do not contain game/plugin DLL hashes, so this audit does not independently certify binary identity. Each setting has one retained process here, not repeated trials establishing a variance distribution.

World statistics were independently recomputed from all 360 `world_ms` entries without trimming. The table preserves the native summary's upper middle value at sorted index 180 and p95 at index 342. Conventional medians are 11.941599, 11.825349 and 11.386499 ms and are separately recorded in JSON. These are elapsed world/GT wall intervals, including waits/overlap; neither worker CPU-time sums nor rendered FPS.

## Attribution

| Mean native part, ms | Locking, 3 | NoLock, 3 | NoLock, 7 |
| --- | --- | --- | --- |
| Servo packet preparation | 0.167604 | 0.168345 | 0.168780 |
| Servo activation | 0.102742 | 0.071146 | 0.071807 |
| Physics Update, including servo | 1.814681 | 1.837611 | 1.418071 |
| Servo sample capture | 0.059550 | 0.060506 | 0.063128 |
| Post-update validation | 0.202287 | 0.174257 | 0.174905 |
| Full native wrapper | 2.400381 | 2.365246 | 1.951192 |
| Whole coordinator | 6.933360 | 6.828325 | 6.398092 |
| Whole actual NN manager | 2.347120 | 2.311769 | 2.302683 |

The first four native parts partition the historical Jolt timer exactly in every frame (maximum residual 0). Post-update validation is additional inside the native wrapper. Coordinator includes native and completed-pose work; do not add those parent and child scopes again.

NoLock at three workers associates with a 0.145523 ms lower world mean (1.222%), but native Update is 0.022929 ms higher. Its native-wrapper reduction is 0.035135 ms; the larger whole-world delta also includes other phase differences and cannot all be assigned to lock removal.

Increasing three to seven workers with NoLock associates with a 0.456972 ms lower world mean (3.885%), a 0.419540 ms lower Update, and a 0.414054 ms lower native wrapper. The Update reduction accounts for most of this observed difference. Relative to the locking baseline, the seven-worker result is 0.602495 ms lower (5.060%). It still exceeds the 10 ms goal on both mean and p95.

## Retained workload and full record counts

All three runs use **60 warmup frames**, 360 measured frames, 100 actual NN characters, fixed 60 Hz world/physics/presentation, one collision step, no async physics/substepping, DuringPhysics group 2, query-tree padding 40 cm and the explicit movement-only profile. The before/after audits retain 100 detached camera subtrees with 200 registered components. All source captures have 22 bodies, 21 joints and 47 authored disabled body pairs. Contact scope remains static floor contacts; self/crowd contacts are outside this fixture.

In each report, all 360 frames have 2,201 native bodies including the floor, 2,100 joints, 100 registered characters, zero Chaos dynamic bodies and zero native error bits/faults. All 2,200 native dynamic bodies remain active in every measured frame. Native and automatic-step counters advance exactly once per frame, with matching engine-frame stamps; all completed pose revisions advance from 2 through 361.

Each run independently verifies:

- 36,000 successful character-frame records, each containing 22 dynamic-body and 88 skeleton-bone checks: **792,000 dynamic-body checks and 3,168,000 skeleton-bone checks**.
- 180 actual NN steps and 18,000 recurrent physical-feedback samples during measurement. All rows retain `NNERuntimeORTCpu` for run/walk/upper models, batch size 100, foot-roll steps 4, and zero failed feedback samples. Initial counters are 29 / 2,900 and final counters 209 / 20,900. Synthetic producer calls are zero.
- 360 joined compose batches and zero ordinary serial-compose fallbacks. Each character still receives full completed animation/socket presentation; optional fist closing and unused cameras are the explicit movement-profile exclusions.
- 36,000 successful post-EndPhysics query records, **792,000 query-body pose checks**, 36,000 correct original PhysicalMesh/head ray identities, and 36,000 verified own-capsule identities. All head visibility tests are normal/unfiltered; ignored-capsule fallback and capsule-filter counts are both **zero**. Analytic candidate selection attempted 72,446 candidates and rejected 36,446 occluded candidates in each run; these are candidate tests, not additional successful scene rays.

Across all three, maximum feedback/render disagreement is 1.287049e-12 cm / 3.415095e-6 degrees, query-body disagreement is 2.343714e-13 cm / 6.156649e-6 degrees, and head impact error is 1.719664e-6 cm. Scale discrepancy and capsule/native pose discrepancy are zero. No rasterized pixels, blood render targets or stain correctness are tested here.

## Placement and lifecycle

Every sampled frame begin/end and every RefreshBones scope entry is on efficiency class 1, logical processors 0-7. Each run contains 36,000 refresh entries with exact duration/call partition agreement and zero provenance overflow. Different frame begin/end processors occur on 295 / 304 / 295 frames; differing refresh entry/exit processors occur on 28 / 29 / 43 scopes. These are migrations among sampled P-class processors; matching endpoints cannot exclude intervening migration/preemption. Worker residency, frequency, temperature and utilization are not measured.

Each run records GT affinity `0xfff -> 0xff -> 0xfff`, requested/applied/restored true, no pending restoration, and unchanged process/system masks `0xfff`. Process priority remains Normal (32), GT priority +1. Power-throttling reads fail with error 87, so QoS state is unavailable rather than verified disabled. P-class placement is an explicit benchmark control, not a production default.

All runs remove one character during bone-finalization, reject its 22 stale handles and preserve 2,178 survivor handles. Ninety-nine survivors pass their explicit subsequent step, leaving 2,179 bodies and 2,079 joints. Two unmeasured lifecycle steps advance world counters to 362; final teardown leaves the floor only, zero joints/registered characters/Chaos dynamics and 2,200 rejected stale handles, with agents returned to kinematic mode.

Late admission tests verify same-frame pending idempotence and cancellation: the pending character has 22 Chaos bodies, adds no native rig, cancellation removes those dynamics, clears token/delegate and invokes no completion callback, while all 2,178 survivor body states remain unchanged. They do **not** exercise next-frame admission/drain or deferred failure callbacks.

The synthetic 11-cm pose-store mutation callback is deliberately **not exercised in actual-NN mode**. That is distinct from the exercised removal-during-finalization check. Natural motion-edge rays are zero; these files explicitly require separate matching-source `Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose` foundation evidence and do not certify that external result by themselves.
