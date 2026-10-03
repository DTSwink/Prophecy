# Query publication validation simplification — draft only

No active source edits, builds, or UE processes. QueryPose.merge.patch is isolated; the new native test is under Source/GameAnimationSample3/Private/ProphecyJoltQueryValidationTests.cpp relative to this draft.

This is a small removal of duplicate work inside the existing .43 ms/100-character validation phase. There are no hidden native scene locks in the inspected checks, and the entire measured phase is an upper bound on possible savings. No numerical speedup is claimed before A/B measurement.

## Exact retained coverage

USkeletalMeshComponent::IsAnySimulatingPhysics (UE Engine/Private/Components/SkeletalMeshComponent.cpp:3766) loops every Bodies entry and calls FBodyInstance::IsInstanceSimulatingPhysics. BodyInstance.h:1570 defines that as ShouldInstanceSimulatingPhysics() && IsValidBodyInstance().

FBodyInstanceCore::ShouldInstanceSimulatingPhysics (PhysicsCore/Private/BodyInstanceCore.cpp:27) is the authored flag plus valid BodySetup and its effective collision-trace policy. It is not equivalent to native IsKinematic, so the draft retains both checks. It folds ShouldInstanceSimulatingPhysics into each existing mandatory slot preflight, after verifying a real native actor. This removes the separate body scan and lets the mandatory null-slot guard run before a premature mesh-wide dereference.

BodyInstance.cpp:2701 defines IsValidBodyInstance as FPhysicsInterface::IsValid(GetPhysicsActor()). ChaosEngineInterface.h:354 defines IsValid as actor pointer != nullptr. Initialization already checks Actor explicitly. Each publish already compares its live actor with the private, nonnull actor cached by successful initialization. Dropping this second call preserves the same accepted set; deleted/sync-timestamp/native-state checks remain.

BodyInstance.cpp:3038–3045 defines GetPhysicsScene as GetCurrentScene(GetPhysicsActor()). The draft supplies the already checked actor directly to the same public GetCurrentScene function, retaining the scene check and reducing repeated cross-module actor getters. ChaosEngineInterface.cpp:2531 confirms that function resolves the actor's solver scene without a lock. IsKinematic at :425 is a GT object-state read, also without a scene lock.

The current PhysicsAsset is fetched once for publish's binding/slot checks instead of again for every body's scale-policy read. All these reads occur synchronously on the GT before the first mutation and before any subsequent callback. The per-call const MeshScale.IsUniform result is also reused in the scale phase.

## Unchanged

- Every mesh/world/physics-state/query-only/PHAT ownership requirement.
- Every live body pointer, native actor identity, native kinematic state, authored effective simulation state, scene, deletion/sync timestamp, bone index, and current scale-policy check.
- All finite/normalized/positive-scale checks on completed body transforms.
- Full validation before the first scale or pose mutation.
- Current shape geometry/applied-scale cache invalidation, all 22 body writes, and immediate native scene/pending-query update.
- Every caller callback/lifetime guard and all 88-bone publication.

The caller does validate all composed local/component/world transforms in ProphecyJoltPose.cpp:137–138 and :208–209, so the 22 body numerical checks are mathematically repeated. They are deliberately retained here: Publish is also a direct helper entry point used outside the character's private composed-pose path. Removing them would require an explicit private proof-carrying or trusted entry point and adds an API boundary for a presently unmeasured small benefit.

The caller's repeated ValidatePublication checks do not scan 22 bodies or lock native physics. They check exact binding/registration/revision/world-step ownership across callback-capable engine calls. They are unrelated to the removed mesh-wide scan and remain intact.

## Test

Prophecy.Jolt.QueryPose.RejectsChangedBodiesBeforeMutation uses the actual 88-bone/22-body mannequin in a transient game world. After a valid publish, it verifies rejection for:
- authored simulation enabled while native state remains kinematic;
- native dynamic state while authored simulation remains disabled;
- a null live body slot;
- nonfinite late-body transform;
- nonpositive late-body scale.

Each failed attempt uses otherwise translated targets and requires every native body transform and the scale-write counter to stay unchanged. A final valid publish must still succeed. The existing immediate-finalization/scale-cache and post-EndPhysics tests remain necessary and unchanged.

The deliberately nonfinite setter case runs when ENABLE_NAN_DIAGNOSTIC=0, including the current Development Editor target. In Debug's diagnostic mode UE sanitizes that setter to zero and emits an ensure, so only that unrepresentable input case is explicitly omitted with a test info message; the production finite guard is unchanged. Native-state/flag/null-slot/scale and mutation-boundary cases still run.

The body-array and authored/native flags are perturbed only in the owned transient test and restored before destruction. No persistent asset field is edited.
