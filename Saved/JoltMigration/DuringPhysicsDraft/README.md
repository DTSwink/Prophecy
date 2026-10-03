# DuringPhysics opt-in experiment — source-only draft

No active source edits, builds or Unreal processes were performed for this draft. It is not runtime proof and does not change the default PrePhysics policy.

Promotion consists of `Coordinator.merge.patch`, the two new files under `Source/GameAnimationSample3/Private`, then `MultiJolt.merge.patch`. The patches deliberately avoid the existing character tick-enabled predicates and profiling/processor JSON changes. They do not replace a whole active coordinator or benchmark file. The launcher is root-owned: pass `-ProphecyJoltDuringPhysics` only for the experiment. Without it, the coordinator remains PrePhysics.

## Behavior and measured scope

Only the automatic coordinator tick's start/end group changes. It still executes on the game thread, prepares the same current target packets after the existing actor prerequisites, steps the native owner once, and synchronously publishes every completed skeleton/query receiver. Explicit manual callers, target cadence, physics dt/substeps, collision policy, body/joint counts, 88-bone publication, callbacks, and late admission/cancellation semantics remain unchanged. No native world or geometry is automatically created.

The coordinator exposes read-only configured group, resolved actual start/end groups, observed UWorld group, engine frame of the last successful automatic step, and cumulative successful automatic step count. A prepare callback that removes all clients without taking a step does not increase the count. Explicit lifecycle steps do not masquerade as automatic ones.

`GetActualTickGroup` and `GetActualEndTickGroup` are sampled from the executing tick, when UE says their values are valid. UWorld's observed group is separately captured. MultiJolt rejects promotion to an unintended group, a missing/current-frame mismatch, or a count other than one automatic step per measured frame. The source path currently drains available game-thread DuringPhysics tasks before advancing the world group; if the runtime shows a later observed group, retain the failure/provenance and investigate rather than quietly weakening this check.

The new post-EndPhysics validation runs where existing MultiJolt validation already runs: `OnWorldPostActorTick`, after the world-tick stopwatch stops. Its cost is included in frame intervals but excluded from the reported world-tick interval. It adds no timed callback or pose write.

For every measured agent/frame it checks all 22 native external query body X/R transforms against their completed skeletal bone transforms at the existing 0.02 cm/0.02 degree tolerance, with normalized quaternion comparison. These are query body/bone transforms; they must not be confused with offset Jolt body-origin transforms. Existing actual-feedback versus all-88 socket checks remain intact.

Every agent also receives a short current-head ray on WorldStatic, the fixture's captured blocking response. An independent raycast against its actual, already-scaled native geometry at the completed bone pose calculates the expected impact. The world query must return the original component, original actor, `head` bone, blocking hit and matching impact within 0.02 cm. Native geometry misses are not accepted as query successes.

Ordinary center rays are **not** counted as broadphase motion evidence. The helper tries additional rays through newly exposed current head bounds. A qualifying segment must miss the entire preceding exact GT query AABB plus 0.04 cm clearance, and must intersect the actual current native geometry (rejecting empty corners of a transformed AABB). Only a successful world query with expected identity/impact then counts. Each row records the rays, bounds and coverage; summary records total qualifying rays and distinct agents. A DuringPhysics case requires at least one qualifying ray, otherwise it fails with explicit missing-motion-coverage diagnostics. It does not change fixture movement to manufacture a pass.

This disjoint-bound test concerns the exact external query AABB used by `FChaosScene::UpdateActorsInAccelerationStructure`; it is not a claim about every possible padded or historically inflated PT node. All-body X/R checks independently guard against stale pose. The default PrePhysics control reports absent motion-edge coverage without failing solely for that coverage gap.

## Source-backed safety and limitations

The supporting full audit is `Saved/JoltMigration/RefreshPublicationDraft/DuringPhysics.md`. Relevant UE5.7 source paths are relative to `C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime`:

- `Engine/Private/LevelTick.cpp:1721–1749`: Pre → StartPhysics → DuringPhysics without blocking → EndPhysics → PostPhysics. `UWorld::RunTickGroup` advances the current group only after the tick manager returns, at line 781.
- `Engine/Private/TickTaskManager.cpp:1059`: the nonblocking DuringPhysics release drains available GT tasks with `ProcessThreadUntilIdle`.
- `Engine/Classes/Engine/EngineBaseTypes.h:370,379`: public actual tick-group getters and their within-frame validity contract.
- `PhysicsCore/Private/ChaosScene.cpp:236`: public actor batch immediately updates the external query tree using geometry's transformed AABB and records pending solver spatial changes under the external-data lock.
- `Experimental/Chaos/Private/Chaos/Framework/PhysicsSolverBase.cpp:354` and `Chaos/ChaosMarshallingManager.cpp:95,117`: the write receives the newer external timestamp after StartPhysics marshals its current packet.
- `Experimental/Chaos/Private/Chaos/PBDRigidsEvolution.cpp:705,972`: swapping a completed PT acceleration structure replays newer/equal pending changes using current external geometry and transforms.
- `Experimental/Chaos/Public/PhysicsProxy/SingleParticlePhysicsProxy.h:1178,1186` and corresponding private `.cpp:491,497`: GT X/R overwrite timestamps prevent older solver output from overwriting a newer external pose.
- `Experimental/Chaos/Public/Chaos/ImplicitObject.h:299`: public native-geometry raycast used for independent expected impacts.

This is limited to the validated QueryOnly, zero-Chaos-dynamic pilot. DuringPhysics writes become inputs to a subsequent Chaos simulation packet; no same-step Chaos/Jolt collision coupling is promised. Consumers before the coordinator still observe the previous completed pose; real NN manager timing needs its own dependency review before using this experiment there. Immediate own-mesh query publication/finalized callbacks remain synchronous and unchanged, but the newly added checks specifically prove the post-EndPhysics state.

The performance opportunity is overlapping the existing Jolt game-thread step with Chaos query-scene work. This may lower elapsed world-tick time; it does not lower the sum of all worker CPU time by the same amount. Compare Normal-priority Pre/During runs from the same built source, same workload, and recorded processor provenance. Do not attribute E-core/P-core scheduling differences to the group switch.

## Root validation before accepting the experiment

1. Compile the new helper and coordinator patches; run existing foundation tests unchanged.
2. Run identical moving 100-agent PrePhysics and DuringPhysics controls. Require every frame's actual-group/count, all query-body transforms, all-88 completed/socket/feedback checks, per-agent head rays, and During motion-edge evidence.
3. Keep callback removal, surviving explicit steps and pending cancellation gates. The automatic counter is intentionally unaffected by these extra explicit teardown steps.
4. Run the current RHI blood fixture with the experimental flag, retaining original mesh/receiver identity and stain correctness.
5. Compare complete world-tick timings and EndPhysics waits at the same Windows priority/processor policy; report functionality or scheduling failures without claiming a speedup.
