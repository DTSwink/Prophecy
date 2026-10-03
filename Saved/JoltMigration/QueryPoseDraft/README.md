# Completed pose and immediate UE query publication

Draft only: not compiled, run, or timed. Active files and builds were not modified. The BodyComponent task remains frozen. The performance goal is 100 agents with total CPU world tick below 10 ms while retaining animation cadence, every bone, query geometry, socket/blood behavior and lifecycle callbacks. This draft does not claim that goal has been reached.

## Changes ready for review

The tree mirrors six game-module files: CharacterComponent.cpp; PoseAnimInstance.h/.cpp; new private QueryPose.h/.cpp; and new QueryPoseTests.cpp. **Merge only the four focused CharacterComponent hunks** (include, state fields, enable setup, completed-pose publication) so concurrent target caching/profiling and empty inherited mesh tick fixes are preserved. The pose instance files were otherwise untouched. No Build.cs change is required beyond the game's existing Engine/PhysicsCore/Chaos dependencies.

1. Bind a query publisher to the exact live UE PHAT body slots and actor handles after Chaos dynamics are disabled. Clear any earlier kinematic position target and V/W once when this publisher takes ownership. Preserve the original UObject/component, PHAT, query filters and shape data.
2. Select `SkipAllBones` for this mesh's default skeletal kinematic update while the fast publisher owns it. The existing saved setting is still restored on disable. The actual native pose evaluator continues to produce the full local skeleton through the usual proxy and `RefreshBoneTransforms` path.
3. Arm a one-shot synchronous GT callback on the native pose proxy. `PostEvaluate` invokes it after this instance's native/Blueprint post-evaluation and base proxy hooks, before UE flips bone buffers or dispatches finalized-bone callbacks. The delegate is detached before invocation and cleared after Refresh on every ordinary return path. Existing exact state/rig/registration/mesh revision guards remain.
4. Use the already composed world pose to update every retained query body. Apply scales through UE only when needed. Set GT X/R and shape bounds, then call the public `FChaosScene::UpdateActorsInAccelerationStructure` once for all bodies in that mesh. That API updates both the immediate external query tree and the solver's pending spatial operations. No native mirror is bypassed, and no query geometry is replaced or simplified.
5. Omit the second explicit teleport for this fast publisher. No kinematic target is created each frame, so there is no temporary Chaos velocity trajectory to resolve for a query-only body. Native Jolt simulation cadence and velocities are unchanged.

The fast hook requires the exact native `UProphecyJoltPoseAnimInstance`, with no linked or postprocess evaluator after its proxy hook. At admission, a mesh with those evaluators retains the existing publication path so their callback order is preserved. Once fast ownership is selected, an unexpected evaluator/class change fails the hook and uses the existing stopped-binding error behavior. It does not silently discard callbacks or switch cadence.

## The scale cache preserves UE's result

`FBodyInstance::UpdateBodyScale` checks requested scale against `Scale3D`, but the latter stores the **shape-adjusted** scale. `ComputeScalingVectors` can constrain sphere/capsule scale, leaving the same raw authored nonuniform request unequal to the previous adjusted result. Repeated calls can therefore reconstruct the same native geometry every animation update.

The cache remembers the exact raw request, resulting `Scale3D`, and resulting native geometry pointer for each exact body/actor identity. It skips UE scaling only when all three are unchanged. A changed request, applied scale, or geometry pointer runs the normal UE update again. `bSkipScaleFromAnimation` and the engine's uniform-component/nonuniform-component branch are preserved. Stock UE's own tolerance is used only to recognize its no-change return; cache reuse requires exact values. A failed update is reported explicitly.

This does not assume all bones have unit or uniform scale. It also does not suppress a real geometry change. Runtime PHAT/body mapping or scale-policy replacement invalidates the binding rather than guessing a new shape mapping.

## Decisive local source

All paths below are under `C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/`.

- `Engine/Private/Components/SkeletalMeshComponent.cpp:3119,3125`: PostAnimEvaluation calls `UpdateKinematicBonesToAnim(None)` before finalization; the current project then calls a second explicit teleport.
- `Engine/Private/PhysicsEngine/PhysAnim.cpp:538`: normal update loops each body and invokes per-body target/global-pose operations plus `UpdateBodyScale`.
- `Engine/Private/PhysicsEngine/BodyInstance.cpp:2178,2188,2217,2531`: early scale comparison uses stored adjusted `Scale3D`; geometry is rebuilt and the adjusted scale stored after success.
- `Engine/Private/PhysicsEngine/Experimental/PhysScene_Chaos.cpp:1735`: `ProcessTeleportActors` sets GT X with dirty=false, R, shape bounds, and updates the acceleration structure in one batch. The draft follows this public-source operation sequence. It does not copy unsafe parallel mutation or bypass pending solver spatial updates.
- `Engine/Public/Physics/Experimental/PhysScene_Chaos.h:357,457`: `UpdateKinematicsOnDeferredSkelMeshes` is private, so it is not a callable public immediate flush.
- `PhysicsCore/Private/ChaosScene.cpp:236`: public bulk update holds one external acceleration lock, updates each element, and queues each corresponding solver spatial update.
- `Engine/Private/Animation/AnimInstance.cpp:921`: native/Blueprint post-evaluation happens before proxy PostEvaluate. `Engine/Private/Components/SkeletalMeshComponent.cpp:2638` then visits linked/postprocess instances; that is why the fast path checks they are absent.
- `Engine/Private/PhysicsEngine/PhysAnim.cpp:468` and `Engine/Private/Components/SkeletalMeshComponent.cpp:4879`: bone buffer finalization precedes notify/finalized-bone callback dispatch. Query publication occurs before that boundary.
- `Experimental/Chaos/Public/PhysicsProxy/SingleParticlePhysicsProxy.h:1238`: dynamic-to-kinematic transition clears the target to mode None. The draft also clears an earlier animation target once on binding; it does not install a new position target every frame.
- `PhysicsCore/Private/BodyInstanceCore.cpp:17`: `bUpdateKinematicFromSimulation` defaults false. The draft does not change that setting; the actual per-body runtime setting has not been measured here.

## Validation required before accepting a speedup

New test: `Prophecy.Jolt.QueryPose.ImmediateFinalizeTraceAndScaleCache`.

It loads the actual 88-bone/22-body project mannequin in a real Game physics/query world, publishes translated and rotated poses with nonuniform scale, and checks every retained body's position/rotation against the skeletal pose **inside** `OnBoneTransformsFinalized`. It performs a native world visibility ray there and requires the original mesh and a PHAT bone identity. Repeated requests must retain geometry pointers without extra scale calls; changed requested scale and an explicit external native scale perturbation must invalidate the cache. Finally it runs the stock UE teleport/scaling path with the same pose and compares applied scales and geometry bounds.

This test is written but uncompiled/unrun. Re-run the existing character pose/feedback/blood, one/two-character lifecycle/callback removal, pending cancellation and 100-agent measured fixtures after the full Editor build. A passing ordinary frame test alone is insufficient for the immediate-finalization query contract. Parent should confirm the actual fixture selects the fast path, since a postprocess instance retained from its asset could select the existing path.

Timing interpretation: `QueryUpdate` is now nested inside `RefreshBones` through the GT proxy hook. Those inclusive numbers must not be added together; subtract QueryUpdate to compare exclusive refresh overhead. CompletedPose and coordinator/world totals remain directly comparable. Solver dirty/spatial work still exists because the supported scene API maintains both query representations; any reduction must be measured rather than assumed. No frequency or physics-quality reduction is part of this draft.
