# Blood collision: current routing and native-query experiment

October 1, 2026. User explicitly resumed blood investigation and permitted isolated performance experiments. This page records the first query-only stage. The subsequent [actual CPU emitter experiment](JoltBloodEmitterExperiment.md) compares stock async UE, buffered UE, pure Jolt and hit-refined Jolt, including exported-position checks, a diagnostic crash/recovery and an editor rebuild. Production blood effects and the disconnected cutting loop remain unchanged; no push.

## What the earlier tests proved

[September10 receiver validation](JoltBloodVisualValidation.md) proved persistent painting on Jolt-driven static/moving meshes, swords, characters and promoted ISM/HISM/CPU-PCG objects. The fighter report explicitly records Jolt=true, Chaos simulation=false, **collision=QueryOnly**. The four real traces hit head/spine/upperarm/calf and painting accepted them. This used retained UE query geometry, not native Jolt particle collision. The instance tests invoked the real Niagara callback directly; they did not run an emitter.

There are two different compatibility mechanisms:

- **UE query-only geometry** follows Jolt bodies so ordinary UE/Niagara traces can find them. It is not a second dynamic character simulation.
- **`SM impostors`** are individually painted actors promoted from ISM instances, because the existing blood mask is per component/material slot. Their purpose is independent paint storage. Changing the collision backend alone does not provide independent per-instance masks.

## Current compiled emitter inspection

Read the loaded systems through their selected emitter versions and compiled scripts, without editing them:

| System | Enabled collision/export emitters |
|---|---|
| NS_bloodsplat | GPU Fountain; CPU Fountain001 |
| NS_bloodarc | GPU Fountain; CPU Fountain001 |
| NS_bloodwound | CPU Fountain001 and Fountain002; GPU Fountain disabled |

Every enabled CPU emitter above calls **two `PerformCollisionQueryAsyncCPU` functions** (`CollisionQueryAndResponse` and `CollisionQueryAndResponse001`) and **ExportParticleData**. This establishes two compiled query sites, not that both necessarily submit for every particle on every frame. Do not remove one without inspecting its channel/skip/response semantics. Their collision interfaces are the stock `NiagaraDataInterfaceCollisionQuery`; export uses the stock export DI.

Installed UE5.7 `NiagaraDataInterfaceCollisionQuery.cpp` queues these CPU requests. `NiagaraCollision.cpp` dispatches `UWorld::AsyncLineTraceByChannel` on the game thread, then collects the results. The current native Jolt `RayCast` API is game-thread-only, requires an idle Jolt world, and explicitly does **not** implement UE query-channel/complex-trace filtering. A downstream decal-manager trace replacement alone would not migrate the upstream particle collision.

The enabled GPU emitters have the stock collision-query DI. This inspection does not identify their exact depth/distance-field branch. GPU render-based collision is separate from the Jolt CPU world; [Epic's GPU collision documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/gpu-raytracing-collisions-in-niagara-for-unreal-engine) describes those rendering routes. No claim of GPU-to-Jolt integration or live emitter visual acceptance is made.

## Native-query experiment

Opt-in editor command: `Prophecy.Blood.NativeQueryExperiment`. Source: `Source/GameAnimationSample3/Private/ProphecyJoltBloodQueryExperiment.cpp`. It refuses active PIE and creates/destroys a separate transient world. No game ticks or allocations are installed in the production path.

Equal radius20cm spheres are registered in both backends on a100cm grid. UE shapes are QueryOnly; Jolt bodies have zero gravity/velocity. Test22,220,2200 bodies,8 warm-up simulation/world steps,4096 rays per sample,8 rounds alternating backend order. Each ray is isolated to one sphere; every measured pass must hit4096/4096. The UE trace uses stock Niagara CPU query policy (physical material, ignore touches, no complex trace); the Jolt fixture has no equivalent filtering. Thus this compares query backends in an all-blocking case, **not** the full asynchronous Niagara pipeline, paint cost, physics cost, collider publication, rendering or FPS.

Median milliseconds per1000 rays:

| Bodies | UE queries | Native Jolt queries |
|---:|---:|---:|
| 22 | 1.187 | 0.383 |
| 220 | 1.329 | 0.455 |
| 2200 | 1.941 | 0.650 |

Jolt is approximately3× faster for these warmed simple-shape queries. This does not establish a3× game or blood-effect speedup, nor the cost of adding the missing channel/identity/complex-query behavior.

Isolation checks pass:

- After disabling all UE query shapes, UE traces miss while native Jolt still hits and returns the correct associated component.
- Making the nearest UE sphere ignore Visibility lets the UE trace reach the next sphere. The existing unfiltered Jolt ray still hits the first. This deliberately demonstrates why it cannot be substituted directly for a blood trace.

**Corrected benchmark caveat:** the first two captures queried newly added bodies before any physics step. Jolt's admission-time search structure made2200-body queries approximately30–31ms/1000. Those cold captures are not representative running-world results and must not be attributed to the registry optimization below. Warming the world, not merely changing the lookup, removed that large cost.

## Small native improvement retained

`UProphecyJoltWorldSubsystem::RayCast` previously scanned every registered slot after a hit. It now uses the existing `NativeBodySlots` lookup maintained by admission/removal, checking the full BodyID including its sequence before using the slot. It retains handle generation, stale-body rejection, surface normal and welded-source mapping. No new registry, body data, per-frame work or changed physics/filter policy.

Live Coding loaded the lookup change00:12:50UTC October1. Both focused native tests passed00:13:34UTC: `ClosestHitsNormalsAndArguments` and `MovedPoseAndHandleLifetime`. The final warmed diagnostic loaded00:16:15UTC and completed successfully00:16:26UTC. The lookup-only cold comparison did not show a material overall gain; no isolated speedup is claimed for that small code change. The warm result compares final native queries against UE, not against the old lookup implementation.

Evidence: `Saved/Diagnostics/BloodNative20261001/{before.json,lookup-cold.json,warmed.json,warmed-summary.json}` and `run_experiment.py`, `analyze.py`, `test_queries.py`. All scenes cleaned up; editor left outside PIE. No images or full suite.

## Requirements for a complete native blood path

1. Give the native query layer correct blood-channel/ignore/query-enabled filtering and generation-checked receiver, bone and instance identity. Keep exact static UV queries where native collision triangles lack a verified UE FaceIndex/UV mapping.
2. Provide an opt-in Niagara CPU data interface that buffers requests from particle simulation, queries completed Jolt state on the game thread, and delivers results with the existing async timing. Keep GPU emitters on their existing render collision route. Preserve material response, LWC offsets, missed/skipped queries and callback lifetime.
3. Migrate the actual blood collision modules and downstream callback together in duplicate test assets. Verify live particle collision/export, moving-bone paint placement, floor/static/instance cases, queue growth and end-to-end frame cost before replacing production assets. Keep retained UE query colliders required by other gameplay callers. Replacing ISM paint impostors requires separate per-instance mask storage work.

The query-only experiment establishes feasibility and a promising query budget. The [follow-up emitter experiment](JoltBloodEmitterExperiment.md) found approximately47–58% lower isolated CPU producer cost for the best quality-preserving choices and caught a pure-native splat-placement discrepancy that ray timings alone missed. **The production Niagara effects have not been switched to native Jolt collision.**
