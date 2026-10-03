# Native parallel skeletal refresh: bounded source audit

2026-09-09. Read-only audit against installed UE 5.7.4 and current project source. No builds, UE launches or active source edits. Recommendation: defer this redesign; it is not a safe small replacement for the present synchronous publication call.

## Supported mechanics

`USkeletalMeshComponent::RefreshBoneTransforms(FActorComponentTickFunction*)` can dispatch evaluation to UE workers when the animation instances support parallel work, the engine parallel-animation switch is enabled, and the supplied tick has a valid completion handle. It then creates one worker evaluation task and one dependent game-thread completion task per mesh. The latter performs the normal post-evaluation, query hook, buffer flip and finalization callbacks.

The current coordinator's `FProphecyJoltCharacterWorldTickFunction` derives from `FTickFunction`, not `FActorComponentTickFunction`. It cannot be passed to Refresh through a cast. A real compatible executing tick would be necessary; passing disabled mesh ticks or fabricating a completion handle does not supply this contract. The public completion handle is valid only during the owning tick's execution.

Public `HandleExistingParallelEvaluationTask(true, true)` waits for that mesh's worker and invokes completion on the game thread. Therefore, a coordinator that dispatches and joins while still inside its tick is mechanically possible after changing the tick type and splitting publication. Waiting on the coordinator's own completion event inside that executing tick would instead wait for the current task itself; join mesh work, not the enclosing tick.

Sources:

- UE `Engine/Private/Components/SkeletalMeshComponent.cpp:2712`: parallel eligibility; `:2855`: dispatch and dependent game-thread completion; `:4722`: completion; `:4737`: public blocking join.
- UE `Engine/Classes/Components/SkeletalMeshComponent.h:2037`: Refresh signature; `:2527` and `:2548`: private dispatch/task/context; `:2559`: public completion wrappers.
- UE `Engine/Classes/Engine/EngineBaseTypes.h:346`: completion-handle lifetime; `:570`: actor-component tick type.
- Project `Source/GameAnimationSample3/Public/ProphecyJoltCharacterWorldSubsystem.h:16`: current coordinator tick type.

## Why this is not a drop-in batch

1. **The current query hook has synchronous stack lifetime.** `PublishCompletedPose` owns Completed, its identity captures, errors and timing locally. The hook captures them by reference, Refresh is immediately followed by clearing the hook, then the method validates and commits the revision. Letting Refresh return before completion would invalidate that lifetime/ordering contract. A complete owned work item and separate start/finish APIs would be required.

2. **The engine automatically queues individual game-thread completions.** On an ordinarily executing game-thread task, the join normally retracts worker work or stalls without pumping its current named-thread queue. This makes ordered manual joins plausible for a restricted callback set; it is not an unconditional callback-order guarantee. Other callback code can pump the game-thread queue or explicitly complete a later mesh. Each queued engine completion checks only whether that mesh currently has an evaluation task, then performs post-evaluation. The stock public API exposes neither the individual task event nor a way to suppress/chain that scheduled completion until an arbitrary coordinator publication turn.

3. **The existing removal path is a concrete reentrancy case.** A first character's finalized callback can disable a later character. Disable detaches its State/registration, then calls `Mesh->HandleExistingParallelEvaluationTask(true, true)` before restoring the mesh. If the later character has already been dispatched, that call completes its staged animation inside the earlier character's callback. Merely rechecking weak handles in the coordinator does not preserve the existing callback sequence.

4. **A later authored-pose change must invalidate evaluation too.** The current compose batch deliberately remains plain data. It checks AuthoredPublicationSerial at each character's original serial consume turn and recomposes if an earlier finalized callback changed that character. Dispatching all native evaluations before those callbacks freezes the later animation snapshot too early. Finish would have to discard stale animation work and reevaluate current authored data without publishing stale queries or notifications. The native pose AnimInstance presently rejects a second publication of the same completed revision, so this also requires an explicit staged-versus-committed revision contract, not a simple retry.

5. **Cancellation cannot simply discard the worker and replay post-evaluation later.** `CompleteParallelAnimationEvaluation(false)` skips the normal result acceptance and clears evaluation identity. The private evaluation context is not exposed as a public deferred-result object. Any discard/restart path must also finish outstanding worker references before destruction, remove its hook safely, and ensure old queued completion tasks cannot act upon replacement work.

Relevant project source:

- `Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp:598`: serial publication, local Completed and exact binding captures.
- Same file `:620`: identity validation; `:667` vicinity: authored serial/carrier match; `:710` vicinity: stack-capturing query delegate and synchronous Refresh.
- Same file `:835` vicinity: Disable detaches State, then joins with post-evaluation enabled before restoring the receiver.
- `Source/GameAnimationSample3/Private/ProphecyJoltPoseAnimInstance.cpp:86`: monotonically increasing published revision; `:136`: query hook.
- `Source/GameAnimationSample3/Private/ProphecyJoltCharacterWorldSubsystem.cpp:397`: plain-data compose batch joins before the original serial consume loop.

Engine queue details: `Engine/Private/Components/SkeletalMeshComponent.cpp:380` defines the independently queued completion task. `Core/Private/Async/TaskGraph.cpp:1451` and `:1495` distinguish worker retraction, named-thread queue processing and event stalling. The audit does not claim every join always pumps callbacks.

## Scope of a future implementation

An experiment would need owned staged publication records, exact registration/world/rig/mesh/AnimInstance/asset/revision/carrier/authored-serial guards, explicit ordered acceptance, cancellation-aware joining, and a same-step reevaluation path. Immediate admission and explicit manual stepping without an executing compatible tick must retain the synchronous path. Every queued worker must finish before the coordinator completes; query freshness and callbacks remain on the game thread.

An adopted skeletal mesh subclass could override the public virtual completion entry point to gate result acceptance, but that is a separate component-class integration effort. It cannot change the class of an already-bound receiver UObject. The current native AnimInstance alone does not provide an equivalent gate before all stock mesh post-evaluation work.

Required regression coverage would include earlier-callback mutation of later authored data, later-character removal/re-enable, world teardown, unexpected class/asset changes, explicit manual stepping, ordered callbacks, all 88 bones, and immediate finalized-callback/native post-EndPhysics ray checks. No new callbacks may run solely because a staged character was removed.

## Expected ceiling and current validation cost

Root's current measurements put non-query Refresh overhead near 1.3 ms per 100 agents, with pure animation processing around 0.7 ms. Approximately 0.7 ms is the optimistic evaluation-work ceiling before the added 100 worker tasks, 100 game-thread completion tasks, joining, allocation and invalidation handling. PreUpdate, TickAnimation, query publication and finalization remain game-thread work. The 1.3 ms total cannot all be counted as parallelizable. This is a bound from existing measurements, not a measured speedup.

The six current `ValidatePublication` checks do not each iterate the 22 bodies: native OwnsRig checks a slot/generation, GetDiagnostics copies the cached structure, and coordinator registration lookup uses its TMap. `IsAnySimulatingPhysics` is outside that lambda, in per-frame preparation and QueryPose::ValidateMesh. UE's skeletal implementation loops bodies and calls inline IsInstanceSimulatingPhysics. Native IsKinematic reads the game-thread particle ObjectState directly; it is not a native read lock.

QueryPose::Publish validates all 22 retained body identities, frames and scale policies once before its first mutation. That distinct preflight is measured at about 0.44 ms/100; publication guards about 0.166 ms/100, per root's latest profiles. They do not conceal six locked body scans. Any later optimization should preserve the before-first-mutation invariant and the checks after callback-capable operations.

Native references: `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltWorldSubsystem.cpp:402` (FindRig), `:1148` (OwnsRig), `:1587` (diagnostics copy). UE `Engine/Private/Components/SkeletalMeshComponent.cpp:3766` (IsAnySimulatingPhysics); `Engine/Classes/PhysicsEngine/BodyInstance.h:1570` (inline instance predicate); `PhysicsCore/Private/ChaosEngineInterface.cpp:425` (direct ObjectState read).
