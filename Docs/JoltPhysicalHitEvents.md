# Jolt PhysicalMesh hit events

Status: installed in the normal Development editor build on 2026-09-15. Focused hit-event automation passed without warnings, followed by four successful 100-agent contact benchmark runs. The saved testNN map and BP_ProphecyManualPoseAgent bytes were verified unchanged before reopening Unreal.

Use the existing **Set Generate Physical Hit Events** Agent node. It defaults to false. When enabled, Jolt contacts for that Agent's PhysicalMesh feed Unreal's `DispatchPhysicsCollisionHit`, providing `OnComponentHit`, `OnActorHit` and the Agent's `OnPhysicalHit`. The separate target/ghost mesh is not a receiver. No overlap-event bridge is added.

The native patch observes actual normal impulses after the discrete contact velocity solver and after the separate CCD solver. It does not estimate impulses from incoming velocities and does not modify contact response. Speculative contacts with zero solved impulse produce no hit. Resting active contacts can emit on subsequent steps; sleeping contacts do not produce solver events. Values use Unreal units: positions in cm, normal impulse in kg cm/s. Friction impulse is not exposed by the Blueprint hit signature.

Callbacks only append plain native data while workers run. No UObject access, Blueprint execution or locking body-interface calls occur there. After all registered clients publish their completed poses, the game thread aggregates body pairs across subshapes/substeps and dispatches events. Rig bodies carry the PhysicalMesh receiver, PHAT body index and bone name; welded shape attribution resolves to its source body. Only explicitly enabled receiver bodies receive events. Collision partners need not enable events themselves.

Handles include world lifetime and slot generation. Every dispatch rechecks ownership and opt-in state; a handler can disable events or destroy bodies. Recursively stepping from a hit callback is rejected. With no opted-in bodies, the native observer is null, no contact data is collected, and the dispatcher returns with an empty queue. There is still a null-observer branch at the native contact solve boundary; do not describe this as literally zero CPU cost.

Validation passed: `Prophecy.Jolt.HitEvents.SolvedImpulseAndLifetime` checks off/on/off, persistent contacts, deferred game-thread delivery, component/actor identity, normal sign and impulse against momentum balance, one-time draining, removal during callbacks, and CCD crossing. Report: `Saved/Diagnostics/JoltHitEventsReport/index.json` (1 success, 0 warnings/errors). The retained NNJoltCrowd benchmark binds a minimal native observer to the real Agent delegate in both runs, requires zero events when off and positive events when on, and reports measured delivery counts. This excludes arbitrary downstream Blueprint combat/blood effects.

The comparison retains the `standalone_main_control_20260909_220737` setup: 100 agents, 60 warmup frames, 360 measured frames, real CPU NN at 30 Hz and Jolt/presentation at 60 Hz, NullRHI, floor-only movement, 7 Jolt workers, original feedback path, ORT intra-op 1, DuringPhysics, existing P-class game-thread setting, idle no-lock reads, native query padding 40 cm. The old post-measurement admission regression was updated to explicitly select Physical: selecting Jolt alone now correctly preserves Kinematic. Its synthetic floor now retains the existing floor component as collision identity.

**Necessary contact stimulus:** the original NN walking fixture produced zero solved contact impulses despite all 2,200 bodies being enabled. Therefore it cannot measure event delivery cost. The measured variant uses `-ContactFloorLiftCm 20`, which raises only the benchmark's native Jolt floor by 20 cm relative to the unchanged mover/NN inputs. This is an artificial floor-contact workload, identical in both cases, not a change to the user's level or a claim about the normal fixture. The source floor transform recorded in provenance remains the original; add the explicit `contact_benchmark_floor_lift_cm` to obtain the native floor position.

`Tools/NN/RunSterilePhysicsBenchmark.ps1 -HitEvents` enables the on case. All four accepted trials used the same final binary and settings in order On A, Off A, Off B, On B:

| Trial | Mean world time | Median | p95 | Delivered OnPhysicalHit events |
|---|---:|---:|---:|---:|
| On A | 13.877 ms | 15.053 ms | 16.886 ms | 63,478 |
| Off A | 13.454 ms | 14.446 ms | 16.982 ms | 0 |
| Off B | 13.059 ms | 14.122 ms | 16.151 ms | 0 |
| On B | 14.702 ms | 15.082 ms | 19.183 ms | 63,478 |

Across the two independent repeats: **13.257 ms off, 14.290 ms on: +1.033 ms (+7.79%)**, with 176.328 delivered events per frame when on. Paired mean deltas range from +0.423 to +1.643 ms; this is a quick indicative measurement with run-to-run noise, not a precise universal per-agent cost. These are measured CPU world wall intervals including NN/physics/presentation, not rendered frame times or a sum of all worker CPU time. Arbitrary user Blueprint hit handlers add their own work.

Summary: `Saved/Benchmarks/JoltHitEventsSummary_20260915.json`. Accepted raw reports: `Saved/Benchmarks/jolt_hits_contact_{on,off}_{A,B}_20260915.json`. Earlier failed/preflight reports are retained for diagnosis and excluded from the quoted performance result. Build logs: `Saved/JoltHitNativeInstall.log`, `Saved/JoltHitGameBuild2.log`, `Saved/JoltHitBenchmarkContactBuild.log`.
