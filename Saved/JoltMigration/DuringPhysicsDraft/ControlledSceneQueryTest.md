# Controlled post-EndPhysics query regression

The two patches are independent. `ControlledSceneQueryTest.merge.patch` adds the source-only foundation test `Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose`. Promote `ControlledSceneCoverageGate.merge.patch` only after a matching-source run of that test passes. The latter records natural crowd edge coverage without requiring arbitrary extra crowd movement and states the separate foundation-evidence requirement. It does not weaken any per-frame query-body pose, head identity/impact, all-88-bone, cadence, or lifecycle assertion.

No active source, builds, Unreal processes, world ticks, tick-group fields, engine files or global simulation settings were changed by this agent. Both patches matched their current active targets uniquely at handoff. Root owns promotion and runtime proof.

## What the control establishes

The test creates one transient Game world with its ordinary public physics scene and the actual project mannequin: 88 bones, 22 PHAT query bodies, retained mesh/actor identity, native completed-pose AnimInstance, disabled postprocess pose evaluation, and the existing query publication hook. It uses the nonuniform root scale already covered by the immediate-query foundation test; repeated movements must retain geometry identity and the scale-cache count.

Each controlled attempt:

1. Publishes the old full pose through the normal animation/query path, and independently selects a head-first ray against all 22 body geometries. The old-location scene query must hit the original head.
2. Records the external query-tree timestamp and the marshalling timestamp, then calls public `SetUpForFrame` and `StartFrame` with 1/60 second and no substeps. The marshalling timestamp must advance.
3. Publishes a new full pose translated 150 cm, using the same animation/query hook, **after** StartFrame has marshalled the old pose. It asserts this publication did not advance another solver packet.
4. Calls public `WaitPhysScenes` and `EndFrame`. All native query body X/R, all 88 completed bones, scales, and native geometry identities must still match the new full pose.
5. Requires the current head ray to be completely outside the old head AABB, hit the current original head at the independently predicted impact, and leave the old head ray empty.

The test also requires a returned query-tree timestamp advance that is strictly older than the newer GT write. This is the guard against falsely passing an EndFrame call that never copied a newer completed PT tree. AABB rebuilding may span physics frames, so at most eight attempts are allowed. Every physics packet deliberately contains the **old** pose; only the game-thread query state receives the 150 cm offset. Thus even a delayed returned PT tree cannot already contain the new pose and make the preservation test vacuous. Missing timestamp evidence fails explicitly; there is no fallback to a weaker ray check.

If a failure occurs after StartFrame, scope cleanup waits and ends that started scene frame before the world and mesh are destroyed. No worker accesses released fixture state.

The control targets the ordering after marshalling and before EndFrame. It does not require the worker to still be running at the instant of publication; a completed-but-not-yet-copied old tree is also the relevant preservation hazard. Performance overlap is measured separately in the crowd run.

## Verified public source contracts

Paths below are under `C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime`:

- `PhysicsCore/Public/Chaos/ChaosScene.h:101,113–142`: public solver/query-tree access, `WaitPhysScenes`, `SetUpForFrame`, `StartFrame`, and `EndFrame`.
- `PhysicsCore/Private/ChaosScene.cpp:331–389`: Setup chooses the step parameters; StartFrame invokes `OnStartFrame` and `AdvanceAndDispatch_External`.
- `Engine/Private/PhysicsEngine/Experimental/PhysScene_Chaos.cpp:2157`: the ordinary Game scene's OnStartFrame services normal deferred kinematics and pre-step callbacks. The fixture has no deferred skeletal query update and does not substitute an engine/private scene path.
- `Experimental/Chaos/Public/Chaos/ChaosMarshallingManager.h:455`: public `GetExternalTimestamp_External` accessor.
- `Experimental/Chaos/Public/Chaos/ISpatialAcceleration.h:411`: public `GetSyncTimestamp` accessor.
- `Experimental/Chaos/Private/Chaos/PBDRigidsEvolution.cpp:674,698–699`: acceleration-tree timestamps identify consumed external packets.
- The same file at `:705,972`: a returned PT structure replays newer/equal external changes using current external particle state.
- `PhysicsCore/Private/ChaosScene.cpp:545–590`: EndFrame requires completed scene events, copies solver acceleration data, synchronizes bodies, and broadcasts completion; `WaitPhysScenes` waits for the recorded events on the GT.

The source draft has not itself been run. A passing foundation log is required before the report's separate control requirement can be considered satisfied; a crowd benchmark success does not certify that external evidence.
