# Shared Jolt character coordinator draft

Draft only, 2026-09-09. No active source files were changed or builds/processes run for this draft. The last verified single-character checkpoint remains the 09:58 report; this multi-character conversion has not been compiled or executed.

## Files and API boundary

The two modified character copies and the new coordinator header/cpp are under `Source/GameAnimationSample3` beneath this draft directory, ready for review before deliberate promotion. They use the native agent's agreed API in the existing `ProphecyJoltWorldSubsystem.h` include:

```cpp
FProphecyJoltRigHandle { FGuid WorldLifetime; int32 Slot; uint64 Generation; bool IsSet() const; };
CreateRig(Snapshot, Prepared, OutRig, OutBodies, OutNotes);
DestroyRig(RigHandle);
OwnsRig(RigHandle);
PublishRigVelocityTargets(RigHandle, Targets, DenominatorSeconds);
ReadRigServoSamples(RigHandle, OutState);
```

`OwnsRig` is identity-only and must remain usable after a native fault or during world teardown. Component cleanup checks it before `DestroyRig`, preserving idempotency while protecting replacement generations. Body handles and `ReadBody` remain unchanged. The old fixture APIs remain native compatibility wrappers; this character copy no longer uses them. No bulk read or shared shape cache is introduced here.

The new `UProphecyJoltCharacterWorldSubsystem` exposes `RequestEnable`, `CancelPendingEnable`, `CanRegisterCharacter`, `RegisterCharacter`, `UnregisterCharacter`, `HasAutomaticStepOwners`, `StepExplicit`, registered-count diagnostics and a stopped/error state. Its custom `FProphecyJoltCharacterWorldTickFunction` is registered with the persistent level at world-tick start, runs on the game thread in PrePhysics, and holds a weak subsystem target. Registrations hold weak character/actor references, not ownership of gameplay objects.

The character keeps its existing public controls, hit bridge and lifecycle, plus private coordinator seams: `PrepareForCoordinatedWorldStep`, `ConsumeCompletedWorldStep` and `LatchSteppingStopped`. `EnablePhysicalAnimation` returning true now means either immediately enabled or accepted pending admission; `IsEnablePending` distinguishes these states, and `IsJoltPhysical` remains false while pending. `OnDeferredEnableCompleted(bool, const FString&)` is a native one-shot multicast result for a deferred attempt. `WasEnableCancelled` distinguishes an explicit cancellation during synchronous priming from a failed handoff. `StepAndPublish` routes an explicit shared-world step through the coordinator. It never calls the native `Step` itself. Its ordinary enabled component tick remains physics-free so the existing live-fixture enabled-state assertions continue to work without changing benchmark files.

## Automatic frame contract

1. Existing manager prerequisites precede Agent ticks; the coordinator adds a prerequisite on every registered publishing Agent tick. Registration/removal installs/removes these dependencies. There is no coordinator→visible-mesh→Agent dependency cycle.
2. Agent/Blueprint publishers route their current per-rig packet as before. Immediately before native Update, the coordinator validates every registered binding and fills only a missing publication permitted by `bAutoPublishManualFollowerSubstepTargets`. Publication stamps prevent a duplicate fallback within the same engine frame. A disabled auto-publication gate retains its previous packet, including its denominator and helper local pose. Automatic publication requires an enabled Agent tick so the manager prerequisite cannot disappear silently.
3. The coordinator calls the plugin's `Step` once for the entire world. Collision steps retain the current project formula: `clamp(ceil(delta / MaxSubstepDeltaTime), 1, MaxSubsteps)` when project substepping is enabled, otherwise one. Each rig's servo denominator remains the independently published existing manual denominator. The coordinator does not clamp away elapsed world time or retune controller strengths.
4. Every still-registered binding consumes that completed world step exactly once, then uses the existing full-skeleton composer, AnimInstance and synchronous query-body update. Native step count/lifetime and each binding's consumed count must agree. A direct external plugin Step while characters are bound is detected and stops coordination.

Any registered `bAutomaticStep=true` requests this automatic world step. A registered character with `bAutomaticStep=false` still physically advances and consumes the shared result when another character requests a step. The flag chooses a step caller, not a per-rig timescale or freeze mode. The coordinator remains cheaply scheduled with manual-only registrations to observe later flag changes, but performs no native Step until an automatic owner appears.

Explicit `Character.StepAndPublish` is refused while any automatic owner exists. With all flags false, the caller publishes packets explicitly and controls step cadence; one explicit call advances and presents all registered rigs. Multiple explicit calls in one engine frame remain possible for a deliberate synchronous benchmark, so the caller must designate one loop rather than call once per character. Automatic stepping is suppressed if an explicit step already occurred in that engine frame. No automatic initialization, floor, geometry, capacity increase or PhysicsSystem-per-character is introduced.

## Activation, removal and faults

Admission is allowed only before the current frame's tick dependencies have been queued. `OnWorldTickStart` opens the admission window and enables the coordinator tick even in an empty or stopped session. Its public `IsCompletionHandleValid` becomes true when Unreal queues the tick, closing admission before the tick can execute; the tick then closes the window flag before any early return. `OnWorldTickEnd` closes the frame. This small empty-session tick only observes the admission boundary; it does not initialize Jolt, create bodies, or call native Step. A paused frame without actor ticks has no new tick graph to modify.

Requests between world ticks, in ordinary pre-tick BeginPlay, in `OnWorldTickStart`, or in `OnWorldPreActorTick` remain synchronous. This preserves benchmark initialization at its pre-actor callback regardless of callback registration order. A request from a running actor tick, runtime-spawn BeginPlay, or a presentation callback queues the **whole handoff** for the next `OnWorldPreActorTick`. It performs no capture, rig creation, Chaos shutdown, pose priming, or registration while waiting. Existing rigs can therefore continue consuming every shared step without a partially registered native rig advancing unexpectedly.

Pending records contain a weak component plus a unique admission id. Repeated enable requests are idempotent. Cancellation invalidates the id and removes the record; a moved local queue cannot resurrect a cancelled/requeued request. EndPlay, OnUnregister and coordinator teardown cancel without a result callback. On a deferred attempt, the token is cleared, source state is validated again, and activation runs at the safe boundary. The completion delegate is moved to a local value and cleared before broadcasting once, so callbacks may bind a new request independently. A failed attempt remains in `GetLastError` and is logged; it is not automatically retried.

Activation preflights the coordinator before creating a native rig. It captures the current live rig/offsets, creates only its own native rig, commits Chaos-off/QueryOnly ownership, primes targets and completed pose, and registers with the coordinator last. The Agent wrapper remains responsible for failed-activation mode restoration. It binds a weak one-shot deferred callback capturing the mode preceding the request. If final registration fails, component unwind removes only its own rig and restores kinematic presentation before reporting failure. An explicit cancellation during immediate priming must bypass Agent failure rollback (`WasEnableCancelled`), preserving the callback's requested mode/removal.

Component-only pending cancellation leaves its pre-admission Chaos ownership unchanged. The Agent's public Disable operation cancels first and then performs the ordinary `SetSimulationMode(Kinematic)` transition. A non-Physical `SetSimulationMode` request also cancels before changing Chaos mode. Merely changing the cached mode would leave dynamic Chaos bodies behind, and failing to cancel would allow the pending handoff to undo a later Kinematic request.

Disable first detaches the private binding into local cleanup ownership, then removes registration/prerequisites before destroying that character's generation-checked rig. Reentrant Disable is harmless and Enable is refused until cleanup ends. Restore operations use the detached data and revalidate the weak mesh/asset after callback-capable animation operations. Removing one character leaves other rigs, packets, floor bodies and the native world intact. Completed pose, feedback-frame conversion, original actor/mesh/material identity, source skeletal Item and stale-safe `MakeHitResult` behavior are retained. The native owner remains the final world-resource owner; coordinator teardown removes its delegate handles, unregisters its tick, and clears pending/registered weak entries.

Completed-pose publication snapshots the exact state address, world/slot/generation rig handle, weak actor/mesh/asset/AnimInstance/native-owner identities, revision, component transform and completed step count. It revalidates after finishing a parallel evaluation, TickAnimation, RefreshBoneTransforms and the explicit query-body update. These operations can dispatch animation-finalization callbacks. If such a callback disables or destroys this binding, publication stops before touching detached state or writing a replacement. The coordinator skips that removed target and continues presenting survivors. A still-live binding with an external mesh/native-step change remains a reportable shared failure.

A preparation, native step or completed-pose failure latches the shared coordinator and every registered binding. One Jolt Update advances all bodies, so continuing only a subset would silently violate the stopped binding's ownership contract. The error persists, later packets cannot clear it, and Jolt ownership stays active to block legacy Chaos writes. Remove the stopped bindings explicitly before registration resumes; a faulted native owner additionally requires explicit shutdown/reinitialization. If presentation fails after Update, some poses may already have published; the draft stops and reports this rather than claiming rollback of a completed solver step.

## Remaining validation before promotion

- Compile/UHT the new subsystem and tick struct together with the native multi-rig API. The prior 33 tests do not validate this draft.
- Rerun both existing one-character JoltLive cases: exactly 60 shared native steps, 22/21, all 88 completed feedback/socket bones, QueryOnly/no Chaos dynamics, ray/receiver generation checks and clean teardown. The coordinator replaces the old step owner without changing those expected measurements.
- Add a two-character shared-world fixture: different target packets and denominators, exactly one world Update per frame, both completed revisions incrementing, independent body/rig/query identities, and correct original per-rig PHAT filters/disabled pairs. Do not force PhysicsBody-to-PhysicsBody contacts on where the captured policy ignores them.
- Remove/recreate one rig while another continues; prove surviving packets/poses and floor unchanged, old rig/body/query handles rejected, and actor prerequisites removed without losing another actor's dependencies.
- Exercise mixed automatic flags and automatic-publication gates, all-manual explicit stepping, external-Step detection, stopped-state recovery, teardown with live rigs and repeated PIE worlds.
- Request a second enable during an existing Agent tick and after the shared tick; require pending/Chaos ownership and unchanged registered/native rig counts until the next pre-actor callback, then one primed registration and one shared step for that frame. Verify immediate benchmark admission still works before queueing.
- Cancel a pending enable via Agent Disable and via `SetSimulationMode(Kinematic)`; require no later admission, no deferred callback, and no Chaos dynamic bodies after the requested mode transition. Force a deferred preflight failure and require exactly one callback with the captured previous-mode rollback.
- Register a one-shot `OnBoneTransformsFinalized` callback which disables/destroys its own character during completed-pose publication; require no stale state access, removed native handles rejected, and every survivor's revision/step count advancing once. Repeat during initial priming and verify cancellation does not restore the cancelled mode.
- Defaults remain 256 bodies, 1024 body pairs/contacts and 8 MiB temporary storage. A 100-character fixture must request suitable explicit capacities; this draft does not choose them. Per-bone reads and synchronous mesh evaluation remain current costs, so this is not a crowd-performance claim.

## Source validation for the two lifecycle fixes

Read-only verification used Launcher UE 5.7 source under `C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime`:

- `Engine/Private/LevelTick.cpp`: `OnWorldTickStart` is broadcast at line 1493, `bInTick=true` at 1535, `OnWorldPreActorTick` at 1646, and `FTickTaskManagerInterface::StartFrame` at 1713. Thus the benchmark's pre-actor initialization is before dependency queueing. A plain bInTick check would incorrectly defer that benchmark and is insufficient by itself.
- `Engine/Private/TickTaskManager.cpp`: `AddPrerequisite` at 2476 only mutates the prerequisite list; `QueueTickFunction` at 2618 snapshots it once per frame. `IsCompletionHandleValid` at 2534 reads the public task state. The custom tick's default `bAllowTickBatching=false` is established at 2363. The boundary tick is enabled before queueing even when no characters are active, covering the first runtime-spawn request as well as later ones. The ordinary `QueueNewlySpawned` path at 1514 can demote a newly registered tick, so late handoffs do not rely on it.
- `Engine/Private/Components/SkeletalMeshComponent.cpp`: synchronous RefreshBoneTransforms invokes PostAnimEvaluation, which calls FinalizeAnimationUpdate at 3136/3142. `FinalizeBoneTransform` at 4879 explicitly warns that event dispatch can destroy the component and broadcasts `OnBoneTransformsFinalizedMC` at 4894. Guarding only the coordinator's outer weak array cannot protect a publisher's subsequent private-state dereference.
- `Core/Public/Delegates/DelegateSignatureImpl.inl:1065` provides the multicast delegate move constructor used to clear one-shot ownership before dispatch.

This pass reviewed the source/API paths and whitespace only. It did not compile UHT/C++, run a world, or validate the new runtime-spawn/callback-removal cases. The runtime checks above remain required after deliberate promotion.

Source-copy provenance, SHA256 of active files read for this draft:

| Active source | SHA256 |
|---|---|
| `Source/GameAnimationSample3/Public/ProphecyJoltCharacterComponent.h` | `aa970d977d121d7e417158a0a4ff56d24ee369ffb16cba6f8e23663eef93331d` |
| `Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp` | `6884ae0e2247141b62169039052c2c767867668d0b057db5815a916a9598251e` |
