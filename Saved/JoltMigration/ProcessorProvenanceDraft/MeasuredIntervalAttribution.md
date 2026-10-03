# Timed fixture attribution before processor instrumentation

Read-only source/artifact audit, 2026-09-09. These measurements describe the 12:32 prepared-finalizer checkpoint, before removal of the 100 empty Jolt component ticks and before processor sampling. They are not a causal estimate of either later change.

Evidence: [full JSON](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_prepared_finalizer_100_20260909_1232.json>), [compact summary](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_prepared_finalizer_100_20260909_1232-summary.json>), [engine CSV](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Profiling/CSV/Profile(20260909_123112).csv>).

## Exact timer boundary

[StartTick](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp:359>) executes its one-time `Before=Audit()` and crowd initialization at `Frame==Warmup` **before** the timestamp at line 400. It then starts `TickStart` at line 403 and publishes synthetic targets inside the measured interval. [EndTick](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp:437>) takes the end timestamp immediately at line 440; CSV markers, `WorldMs.Add`, all full-frame validators, serialization and teardown follow it. There is no repeated per-frame RigAudit inside `world_ms`.

The benchmark binds to `OnWorldPreActorTick` / `OnWorldPostActorTick`. UE [LevelTick.cpp:1493](</C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/LevelTick.cpp:1493>) broadcasts `OnWorldTickStart` before this interval; `OnWorldPreActorTick` is at 1646 and the post-actor broadcast at 1877. Earlier pre-actor delegates are excluded if they execute before the benchmark callback; later delegates are included. The CSV `WorldPreActorTick` scope encloses the entire broadcast, so its first sample also includes setup that the benchmark deliberately excludes.

The [coordinator's pre-actor callback](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyJoltCharacterWorldSubsystem.cpp:149>) only snapshots pending admissions and invokes pending callbacks; its steady-state list is empty in this fixture. The normal world-start callback sets admission state/refreshes tick enablement; it does not capture rigs. `StepRegisteredClients` performs generation/lifetime checks and client preparation/consumption as production adapter work. Its `GetDiagnostics` reads are native counters, not RigAudit extraction. `TickAutomatic`'s registration pruning and automatic-owner checks precede the `coordinator_total` scope and therefore remain outside that custom phase, while still inside world timing.

## Why WorldPreActorTick looked 0.77 ms too large

Match CSV frames 60–220 to JSON `multi_jolt_frames[0..160]`, using `sample_frame = ProphecyBenchmarkFrame - warmup_frames`. This gives exactly 161 common samples; do not compare their means against the 180-frame JSON aggregate.

The first common row, sample 0, has CSV `WorldPreActorTick = 123.7674 ms`, timed fixture publication `2.32939795 ms`, and `WorldMs = 27.4999 ms`. The large pre-actor duration includes excluded initialization/audit before `TickStart`.

Across all 161 rows, pre-actor mean is `1.69960559 ms` and fixture mean is `0.93096488 ms`. For the same rows excluding only sample 0, these become `0.936681875 ms` and `0.922224671 ms`: the steady-state difference is **0.014457204 ms**, not 0.77 ms. This exclusion is only for understanding the CSV scope; the original reported world metric is unchanged.

## Remaining timed work, using identical 161 samples

| Independent metric | Mean ms |
|---|---:|
| Timed world | 13.16877453 |
| Agent tick total | 1.47374664 |
| Coordinator total | 7.54143730 |
| Synthetic fixture publication | 0.93096488 |
| World minus those three phases | **3.22262571** |
| CSV exclusive TickActors | 9.82538944 |
| TickActors minus Agent + Coordinator | **0.81020550** |
| CSV exclusive EndPhysics wait | 1.75240186 |
| CSV exclusive Physics | 0.18868385 |
| CSV exclusive SyncBodies | 0.14723727 |
| CSV exclusive QueueTicks | 0.10602112 |
| CSV exclusive Tickables | 0.10755714 |
| CSV exclusive Camera | 0.02607764 |

Chaos's worker `StepSolver` overlaps the end-physics wait; adding both double-counts. `WorldTickMisc = 3.76485776 ms` includes the detailed validator after the benchmark timestamp and cannot be assigned wholesale to the measured interval. Likewise `FrameTime` / `frame_interval` include work outside it. Nested custom phases such as target-read, completed-pose, query-update and native-step must not be added to their parents.

The recorded tick inventory had 100 Agent ticks, 100 empty Jolt component compatibility ticks, one coordinator, zero PhysicalMesh component ticks and no camera/spring-arm component ticks; total engine tick functions were 228. The component stub called only `Super::TickComponent` ([source](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp:689>)). Its removal is a later, separate checkpoint; the 0.8102 ms residual does not measure that stub's isolated cost.

## Synthetic producer overhead is real fixture work

[MakePose/Publish](</C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkManual.cpp:33>) copies the reference local pose, generates names and full 88-bone forward kinematics twice per publication (current and previous endpoint), with fresh arrays. The previous names and previous local-pose arrays are discarded. All 100 lanes use the same time and identical local/component pose; only their carrier transform/source ID differs. Thus 100 identical current/previous pose calculations occur on each 30 Hz publication frame. This is simple native sine/ref-pose generation, not retargeting, animation-sequence extraction or actual NN inference. PoseStore publication remains genuine producer work and must be accounted for.

A separate synthetic microbenchmark could precompute an immutable shared moving-pose sequence outside timing, then time all per-lane PoseStore publications with unchanged current/previous endpoint semantics, source IDs, timestamp, carrier and 30 Hz cadence. Alternatively generate the shared identical pose once per publication frame and reuse it across lanes. Keep real current physical feedback and the existing controller active; never replay completed physical poses or final body velocities. Clearly label preprocessing/recording, timed publication and adapter work separately. Such a microbenchmark does not satisfy the actual NN + movement pipeline goal, and no overhead is silently subtracted from reported totals. The actual NN fixture already bypasses all synthetic publication after manager adoption.
