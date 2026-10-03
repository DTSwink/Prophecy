# Same-boundary callback removal draft

Draft only. No active source, config, assets, snapshot, package or engine files were changed. No UE process, build or runtime test was run for this draft. `Proposed.patch` contains five files; complete proposed source copies are under `Source/`. `Evidence.json` pins the active and proposed bytes before promotion.

## Proven failure and safe boundary

UE 5.7 `Engine/Source/Runtime/Engine/Private/Components/SkeletalMeshComponent.cpp:3458–3470` returns without changing the class during animation post evaluation/update. `PostAnimEvaluation`, lines 2965–2970, holds its post-evaluation guard until the function returns (the assignment is under DO_CHECK). The publisher explicitly passes nullptr to RefreshBoneTransforms. Parallel evaluation requires a non-null tick completion handle at line 2714; this call instead completes evaluation and PostAnimEvaluation synchronously at line 2826, or synchronously completes any existing task at 2719 / 4737–4770. Therefore function-scope cleanup in PublishCompletedPose runs after the engine call's guards and animation callbacks have unwound, in the same engine frame. It does not require a timer or another world tick.

The active implementation calls SetAnimInstanceClass inside the bone-finalization callback, then ignores ApplyNNPoseKinematically's false return. Its existing ValidateDisabled only verifies ownership/mode, so it misses the retained Jolt AnimInstance. The warning is also present in old editor runs; it is not specific to cooked FName behavior or the package.

## Proposed ownership behavior

Disable still moves State out first, unregisters the coordinator identity, invalidates StepRegistrationId, destroys all rig bodies/constraints, disables the component tick and releases the fists proxy immediately. If the component is currently publishing a completed pose, it retains that detached state in DeferredMeshRestore and returns. PublishCompletedPose's scope exit restores the existing mesh properties/class/NN source and performs a zero-time kinematic refresh. Its existing identity guards correctly report the old binding removed; the coordinator at ProphecyJoltCharacterWorldSubsystem.cpp:403 ignores the removed registration's failed consume and continues survivors.

The unique pointer holds only native cleanup/saved state and weak actor/mesh references. Existing weak actor, destruction, registered-mesh and unchanged-asset checks are retained throughout restoration. Destroyed/unregistered meshes and replaced assets are not resurrected. Reentrant removal during restore sees no active State. The new restore-pending predicate also covers the cleanup's disable guard so native enable admission and Agent mode changes cannot replace the binding or reactivate Chaos inside a restore callback. Once the same boundary returns those paths remain available. Pending pre-tick admissions retain their existing cancellation behavior; they have not taken mesh ownership and do not queue mesh restoration.

Agent Disable sets its cached Kinematic mode before immediate/deferred NN refresh. Otherwise the NN proxy's first PreUpdate can observe Physical mode even though its rig has already been removed (affecting kinematic calf handling). Agent SetSimulationMode permits an idempotent Kinematic request during restore, and refuses Physical/HalfSim; EnableJoltPhysicalAnimation refuses before it can perform its preparatory Chaos transition. The benchmark tests these refusals.

This is a bounded fix for callbacks reached from the owned completed-pose publisher (including its synchronous wait/update/refresh calls). It does not add a scheduler for an unrelated external caller that manually evaluates this disabled-tick mesh outside the owned publisher.

## Meaningful regression

The existing unmeasured real bone-finalization removal now verifies:

- Native registration/body/constraint removal and rejection of every old handle happen inside the callback.
- Jolt animation remains installed while the finalizer runs, with restoration pending; reentrant ownership changes are refused.
- StepAndPublish returns in the same GFrameCounter with exactly UProphecyNNLocomotionAnimInstance, zero Jolt revision, no pending restoration and no Chaos simulation.
- A temporary isolated NN pose ID is bound only after removal inside that callback. The returned mesh must already contain a head-local pose shifted by 17 cm, proving cleanup actually evaluated the new source.
- Publishing another source revision in the same frame must produce a 24 cm shift after ApplyNNPoseKinematically, proving continued live kinematic evaluation.
- The original actual/synthetic NN source binding and animation fields are restored and the temporary store entry cleared using scope cleanup. No original NN source values are overwritten. The existing survivor/handle, late admission cancellation, and final complete removal checks remain.

New native JSON field: multi-character summary `callback_kinematic_restore` with success, boundary/ownership assertions, actual class and both pose shifts. Root should add strict offline validator assertions for that object when promoting and bump any relevant schema/version if required. This draft does not mutate the validator.

## Validation before promotion

Source review only; no runtime pass claimed. All five active source hashes were rechecked after writing the draft. Root should compare hashes before promotion, build, run the existing query suite and the packaged two-agent smoke, verify the warning is gone, and confirm this new native regression before any further performance run. The existing original performance result remains separate evidence and is not rerun or reinterpreted by this draft.

## Final R5 additions and Python contract fixtures

The draft now also corrects direct Character DisablePhysicalAnimation/OnUnregister: RestoreKinematicMesh calls Agent SetSimulationMode(Kinematic) while bDisableInProgress is held, before any animation task completion or class initialization. This uses the new cached-mode-only guard path. Final cleanup removes survivor 0 directly through Character, and its NN bone finalizer must already observe Kinematic mode before the disable call returns. The JSON object includes direct_component_cleanup_kinematic=true.

The combined proposed validator is `Validate-PackagedNNCrowd-r5.py`, extended from PackagedR4AuditDraft's exact-32-channel draft. It requires the callback object, strict true booleans, exact native NN class path, case-insensitive head identity, and finite nonboolean 17/24 cm displacements with abs_tol=1e-5 and rel_tol=0. That tolerance matches the native transform comparison and allows compact-pose float conversion; it does not alter physics/pose quality gates.

`Test-ValidatorFixtures.py` executes the whole proposed validate() function with isolated in-memory result mutations while still reading the real matching-source snapshot/query control evidence. The final audit is `ValidatorFixtureAudit-20260909-210421-986822.json`: 110 cases PASS (18 augmented fixtures accepted; 92 malformed inputs rejected). Historic R4 input is explicitly rejected unchanged. Accepted fixtures deliberately add fabricated R5 callback evidence and corrected 32-channel arrays solely to test validator contracts; they are not benchmark or native runtime acceptance. Both sides of the displacement tolerance are tested. Earlier 102-case audit tested the superseded exact-equality proposal; it is retained as history and is not the final validator result.

Source still has not been built or run in UE. Active validator, historical result, runner and package hashes were unchanged by all fixture tests. See FinalDraftManifest.json for final reviewed artifact hashes.
