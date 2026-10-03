# Deferred Chaos maintenance: independent 100-character audit

Both retained reports pass every independently evaluated check: 33 for the normal control and 35 for deferred maintenance. Deferred maintenance changes the mean measured world interval by -0.113206 ms (-1.008%). This pair does not meet the under-10-ms goal or establish a reliable production speedup.

The reports contain all 360 measured frames. The deferred run includes its two positive-delta Chaos admission frames in those samples, followed by exactly 358 zero-delta maintenance frames; no frames were removed from the statistics.

| Measured world interval | Normal control, 1546 | Deferred maintenance, 1545 |
| --- | ---: | ---: |
| Mean, ms | 11.231969 | 11.118764 |
| Reported median, ms | 11.221703 | 11.215702 |
| Reported p95, ms | 13.832800 | 13.718899 |
| Conventional median of 360 samples, ms | 11.147952 | 11.168251 |
| Frames above 10 ms | 212 | 208 |
| Minimum / maximum, ms | 8.233801 / 23.483802 | 7.952500 / 22.217199 |

The report's median selects sorted index 180; its p95 selects index 342. The conventional median averages indices 179 and 180 and is included explicitly. Timings are elapsed world/game-thread wall intervals, including real manager work, target publication, native Jolt, full pose publication and engine work inside that boundary. They are not CPU time summed across workers or rendered FPS. Post-world functional diagnostics are excluded; profiling itself remains inside the measured world interval.

## Retained workload and per-frame evidence

- Each run has 100 agents, 60 warmup frames, 360 measured frames, fixed 1/60-second world/Jolt steps, and one actual `TG_DuringPhysics` step per measured frame. Substepping and async Chaos are disabled. Every agent revision increases once per frame and matches the world step.
- Every measured frame retains 2,200 active Jolt dynamic bodies, 2,100 joints and one static floor (2,201 total bodies), 100 coordinator owners, and zero Chaos dynamic bodies. The immutable source captures retain 22 bodies, 21 joints and 47 disabled pairs per character. The recorded policy uses the original PHAT angular values with the user-approved hard Jolt limits; it does not claim soft-limit response equivalence.
- Independent reduction checks all 36,000 agent-frame records, 792,000 dynamic-body checks, 3,168,000 skeleton-bone comparisons and 792,000 native query-body pose checks. Each character retains all 88 presented bones.
- Real CPU run/walk/upper models each retain batch size 100. The measured interval has exactly 180 NN increments and 180 interpolation-only frames, 18,000 physical feedback samples, zero failed feedback samples and four foot-roll steps. No synthetic pose producer runs after manager adoption. Minimum managed-root travel is **1,200.010681 cm in both runs**.
- All 100 actual movement capsules retain object channel 21, QueryAndPhysics, WorldStatic blocking, radius 30 cm and half-height 86 cm. All 100 unused camera subtrees are detached; their 200 components remain present. Camera/fist movement-only trimming is explicit. No bone, joint or cadence reduction is used.
- All 36,000 post-EndPhysics head rays succeed against the original `PhysicalMesh` and `head` identity. They are normal unfiltered rays: zero ignored-capsule fallback traces and zero diagnostic capsule filters. All 36,000 capsule identity checks and 792,000 exact native query-body comparisons pass.
- Maximum feedback/render error is 1.287049e-12 cm / 3.415095e-6 degrees; native query/bone error is 2.343714e-13 cm / 6.156649e-6 degrees. Scale and capsule pose errors are zero; maximum head-ray impact error is 1.719664e-6 cm. These maxima match between the two retained reports; no Chaos/Jolt trajectory gate is inferred.

## Exact deferred state transition

Before admission, the game-thread view has zero dynamics, while the prior physics-thread view still records 2,200 dynamic/sleeping particles at solver frame 59. The diagnostic records that stale pre-admission state explicitly. It does not assume the physics-thread buffers have already consumed the handoff.

Measured sample frames 0 and 1 complete ordinary positive-delta Chaos frames 60 and 61. Both have zero GT and PT dynamics. Pause is applied only after frame 61. Samples 2 through 359 complete paused maintenance frames 62 through 419, with `solver_last_dt == 0` while world delta remains 1/60 second and ordinary world physics ticks remain enabled.

Every one of these 360 records has 203 components with native objects, 2,303 unique native objects, 2,303 GT kinematic objects, 2,303 PT particles, zero GT static objects, zero GT/PT dynamic or sleeping objects, matching solver-frame/external-packet timestamps, one maximum solver substep, and completed scene synchronization.

The original pause flag is false. The diagnostic restores false at settled solver frame 419, preserves all 2,303 objects and leaves no armed transition. No extra Chaos frame is injected into this restoration. The next ordinary positive-delta frame is an explicit separate controlled-test requirement, not evidence supplied by this crowd JSON. The normal control records `requested=false, applied=false` and has no per-frame paused-maintenance records.

## Native settings, placement and lifetime

All 720 measured rows across both runs record seven Jolt workers, configured job concurrency eight, enabled idle NoLock reads, one collision step, zero update-error bits and no world fault. Capacity is 2,201 bodies / 17,608 pairs / 35,216 contacts, with a 32 MiB temporary allocator. Query-tree padding is explicitly 40 cm. Matching log line 918 in each run reports Jolt 5.6.0, double precision, SSE2, 16-bit ObjectLayer, assertions, object stream, C++ exceptions and shared library; the captured source commit is `e77f175595e64cb44218cc9d9d56fc365ad0e36a`.

Both runs apply the explicit game-thread P-class diagnostic mask `0xff` from original `0xfff`, and restore exactly `0xfff`. Process and system masks remain `0xfff`; Normal process priority (32) and game-thread priority (1) are unchanged. All measured frame start/end samples and all 36,000 RefreshBones scope entries per run are on class-1 logical processors 0-7. Frame endpoints differ 286 times in the normal run and 302 in deferred; RefreshBones endpoints differ 21 and 28 times respectively. Those are sampled migration observations, not continuous residency or worker utilization. Processor scope time/count partitions match with no overflow.

Both runs safely remove one character from its bone-finalization callback: 22 removed handles become stale and 2,178 survivor handles remain valid. The 99 survivors advance to revision 363 after the explicit follow-up step. Exactly two additional Jolt lifecycle steps are outside the measured samples. Final teardown leaves the single static floor, zero constraints, zero coordinator owners and zero Chaos dynamic bodies; all 2,200 former character handles are stale and agents return kinematic. The pending-enable cancellation test clears its token and delegate without a cancellation callback, preserves all 2,178 survivor body states, and returns its temporary 22 Chaos dynamics to zero.

## Attribution limits

| Existing nested phase mean, ms | Normal | Deferred |
| --- | ---: | ---: |
| Agent tick | 1.209772 | 1.230664 |
| Coordinator total | 6.260629 | 6.267885 |
| Native step total | 1.906223 | 1.863277 |
| Jolt Update including servo | 1.474949 | 1.442223 |
| Manager total | 2.329700 | 2.333091 |
| Completed serial publication | 3.629388 | 3.680928 |
| Joined composition batch | 0.534981 | 0.530650 |
| Query update | 1.472576 | 1.494562 |

These phases overlap by nesting and must not be added together. The native step timer's four historical parts and all reported phase means independently reconcile. The small world difference cannot be attributed solely to solver pausing from this single pair; manager, coordinator and publication changes are within the observed variation. Same-binary identity is supplied by the run operator; these older report JSONs do not contain the actual game/plugin DLL hashes.

Contact coverage is the explicitly captured WorldStatic-only fixture. Self/crowd collisions, rasterized blood pixels and rendering are not exercised here. Natural motion-edge rays are zero in both runs, so `Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose` remains required independent evidence. Deferred pause additionally requires `Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle` in the matching binary. The actual-NN case deliberately skips synthetic pose-store callback mutation; the real removal callback is exercised. Next-frame deferred-admission and cancellation-drain execution are outside this report's coverage.

Sources: [normal JSON](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_deferred_control_B_100_20260909_1546.json>), [normal log](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_deferred_control_B_100_20260909_1546.log:918>), [deferred JSON](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_deferred_A_100_20260909_1545.json>), [deferred log](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_deferred_A_100_20260909_1545.log:918>). [Machine reduction with source hashes and all checks](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/DeferredPauseComparison.json>).
