#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyPelvisInertia.h"
#include "ProphecyJointDampingPolicy.h"
#include "ProphecyLimbCollision.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltStepTiming.h"
#include "ProphecyJoltAuthoredTargetHistory.h"
#include "ProphecyPhysicalFootTarget.h"
#include "ProphecyKickFootLeeway.h"

#include "ProphecyAgent.h"
#include "ProphecyAngularLimits.h"
#include "ProphecyAttackFists.h"
#include "ProphecyJoltPose.h"
#include "ProphecyJoltPoseBatch.h"
#include "ProphecyJoltQueryPose.h"
#include "ProphecyJoltPoseAnimInstance.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyCrowdNameLookup.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/HitResult.h"
#include "Engine/World.h"
#include "GameFramework/Controller.h"
#include "PhysicsEngine/PhysicalAnimationComponent.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Physics/PhysicsFiltering.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/ScopeExit.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltCharacter, Log, All);

struct FProphecyJoltCompletedPosePacket
{
    FProphecyJoltComposedPose Pose;
    FTransform ComponentWorld = FTransform::Identity;
    TWeakObjectPtr<AProphecyAgent> Agent;
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<USkeletalMesh> MeshAsset;
    TWeakObjectPtr<UProphecyJoltPoseAnimInstance> Anim;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Owner;
    FProphecyJoltRigHandle Rig;
    FGuid Registration;
    uint64 Revision = 0;
    uint64 CompletedSteps = 0;
    uint64 AuthoredSerial = 0;
    FString Error;
    bool bReady = false;
    bool bSucceeded = false;
};

struct FProphecyJoltCharacterState
{
    ECollisionChannel LastObjectChannel = ECC_MAX;
    FCollisionResponseContainer LastCollisionResponses;
    TWeakObjectPtr<AProphecyAgent> Agent;
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TWeakObjectPtr<USkeletalMesh> MeshAsset;
    TWeakObjectPtr<UPhysicsAsset> PhysicsAsset;
    TArray<FProphecyJoltRigJoint> JointSettings;
    TArray<const FConstraintInstance*> SourceConstraints; // Identity only; validate current pointer before dereference.
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> WorldOwner;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> Coordinator;
    FProphecyJoltRigHandle RigHandle;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FName> BodyNames;
    TArray<double> CapturedBodyMassesKg; // Captured before Chaos becomes a query-only receiver.
    TArray<FProphecyJoltBodyMaterial> OriginalBodyMaterials; // Immutable reset values for this admission.
    TArray<FName> SkeletonNames;
    TArray<int32> Parents;
    TArray<FProphecyJoltPoseBodyMapping> Mappings;
    TArray<FTransform> BaseLocalPose;
    FProphecyNNPoseSnapshot AuthoredSnapshot;
    TArray<FName> TargetNames;
    TArray<FTransform> FutureTargets;
    TArray<FTransform> InterpolatedTargets;
    TArray<FTransform> AuthoredLocalScratch;
    TArray<FName> HelperSourceNames;
    TArray<int32> HelperSourceIndices;
    ProphecyCrowd::FNameIndexLookup TargetNameLookup;
    ProphecyCrowd::FNameIndexLookup FeedbackNameLookup;
    TArray<FProphecyJoltRigVelocityTarget> TargetScratch;
    FProphecyJoltAuthoredTargetHistory AuthoredTargetHistory;
    TArray<FTransform> AuthoredBodyScratch;
    ProphecyJolt::Pose::FPreparedLayout ComposeLayout;
    TArray<FTransform> CompletedBodyScratch;
    FProphecyJoltComposedPose Completed;
    FProphecyJoltComposedPose CompletedScratch;
    FProphecyJoltCompletedPosePacket CompletedPacket;
    uint64 AuthoredPublicationSerial = 0;
    FProphecyJoltQueryPose QueryPose;
    bool bBulkQueryPublication = false;
    FGuid WorldLifetime;
    uint64 Revision = 0;
    uint64 LastPublicationFrame = MAX_uint64;
    uint64 LastStepFrame = MAX_uint64;
    uint64 ExpectedWorldSteps = 0;
    bool bActive = false;
    bool bSteppingStopped = false;
    bool bOwnsRig = false;
    bool bMeshTickEnabled = false;
    bool bEnableAnimation = false;
    bool bPauseAnims = false;
    bool bNoSkeletonUpdate = false;
    bool bForceRefPose = false;
    bool bUpdateRateOptimizations = false;
    bool bDeferKinematicBoneUpdate = false;
    bool bDisablePostProcess = false;
    ECollisionEnabled::Type CollisionEnabled = ECollisionEnabled::NoCollision;
    TEnumAsByte<EKinematicBonesUpdateToPhysics::Type> KinematicUpdate;
    TEnumAsByte<EPhysicsTransformUpdateMode::Type> PhysicsTransformUpdate;
};

void FProphecyJoltCharacterStateDeleter::operator()(FProphecyJoltCharacterState* InState) const
{
    delete InState;
}

namespace
{
// Separate storage: never grow the native character allocation under Live Coding.
struct FLowerFeedbackCapture
{
    const FProphecyJoltCharacterState* Binding = nullptr;
    TArray<FName> Names;
    TArray<int32> Bones;
    TArray<int32> Bodies;
    TArray<TArray<int32, TInlineAllocator<4>>> LocalChains;
    TArray<FTransform> AuthoredWorld;
    uint64 Revision = MAX_uint64;
    uint64 AuthoredSerial = MAX_uint64;
    double ElapsedSeconds = 0.0;
};
TMap<TWeakObjectPtr<const UProphecyJoltCharacterComponent>, FLowerFeedbackCapture> LowerFeedbackCaptures;

void CaptureLowerFeedbackTargets(const UProphecyJoltCharacterComponent* Character,
    const FProphecyJoltCharacterState& State, float DeltaSeconds)
{
    auto* Capture = LowerFeedbackCaptures.Find(Character);
    if (!Capture || Capture->Binding != &State) return;
    Capture->Revision = MAX_uint64;
    if (Capture->AuthoredSerial != State.AuthoredPublicationSerial)
    {
        Capture->AuthoredSerial = State.AuthoredPublicationSerial;
        Capture->ElapsedSeconds = 0.0;
    }
    Capture->ElapsedSeconds += DeltaSeconds;
    for (int32 I = 0; I < Capture->Bones.Num(); ++I)
    {
        if (!State.AuthoredBodyScratch.IsValidIndex(Capture->Bodies[I])) return;
        FTransform Target = State.AuthoredBodyScratch[Capture->Bodies[I]];
        // Explicit callers may step less than the authored trajectory duration.
        // Match the servo's endpoint at this completed time, including substeps.
        const int32 Slot = State.Handles[Capture->Bodies[I]].Slot;
        for (const auto& Trajectory : State.TargetScratch)
            if (Trajectory.Handle.Slot == Slot && Trajectory.TrajectoryDurationSeconds > 0.f)
            {
                const double Alpha = FMath::Clamp(Capture->ElapsedSeconds / Trajectory.TrajectoryDurationSeconds, 0.0, 1.0);
                Target.SetLocation(FMath::Lerp(Trajectory.StartPositionCm, Trajectory.TargetPositionCm, Alpha));
                Target.SetRotation(FQuat::Slerp(Trajectory.StartRotation, Trajectory.TargetRotation, Alpha).GetNormalized());
                break;
            }
        const auto& Chain = Capture->LocalChains[I];
        // Helpers without a PHAT body (notably toes) inherit precisely the local
        // pose used to compose the completed physical skeleton for this step.
        for (int32 J = Chain.Num() - 1; J >= 0; --J)
            Target = State.BaseLocalPose[Chain[J]] * Target;
        Capture->AuthoredWorld[I] = Target;
    }
    Capture->Revision = State.Revision + 1;
}
}

namespace
{
bool BuildAuthoredHelperPose(const AProphecyAgent& Agent, USkeletalMeshComponent& Mesh,
    TConstArrayView<FName> SkeletonNames, TArray<FTransform>& OutLocal, FString& OutError)
{
    OutLocal = Mesh.GetSkeletalMeshAsset()->GetRefSkeleton().GetRefBonePose();
    int32 PoseId = INDEX_NONE;
    float Interval = 0.0f;
    bool bInterpolate = false;
    FProphecyNNPoseSnapshot Pose;
    if (!Agent.GetNNPoseDataSource(PoseId, Interval, bInterpolate)
        || !FProphecyNNPoseStore::GetAgentLocalPose(PoseId, Pose) || !Pose.IsValid())
    {
        OutError = TEXT("The manual Jolt binding requires the agent's published native NN pose source.");
        return false;
    }
    // Simulated bones are replaced by completed rigid states. Unmapped authored bones keep their local
    // pose, and missing helpers retain their reference offsets instead of disappearing from the skeleton.
    for (int32 BoneIndex = 0; BoneIndex < SkeletonNames.Num(); ++BoneIndex)
    {
        const int32 PoseIndex = Pose.BoneNames.IndexOfByKey(SkeletonNames[BoneIndex]);
        if (Pose.LocalTransforms.IsValidIndex(PoseIndex)) OutLocal[BoneIndex] = Pose.LocalTransforms[PoseIndex];
    }
    return ProphecyJolt::Pose::ValidateLocalPose(OutLocal, OutError);
}

bool BuildAuthoredHelperPoseFromSnapshot(USkeletalMeshComponent& Mesh,
    FProphecyJoltCharacterState& State, FString& OutError)
{
    const auto& Pose = State.AuthoredSnapshot;
    if (!Pose.IsValid()) { OutError = TEXT("The target source snapshot is invalid."); return false; }
    State.AuthoredLocalScratch = Mesh.GetSkeletalMeshAsset()->GetRefSkeleton().GetRefBonePose();
    if (State.AuthoredLocalScratch.Num() != State.SkeletonNames.Num())
    { OutError = TEXT("The bound reference skeleton changed; disable and rebind it."); return false; }
    // Check the full layout, not just a hash. Missing helpers still retain their reference pose.
    if (State.HelperSourceNames != Pose.BoneNames || State.HelperSourceIndices.Num() != State.SkeletonNames.Num())
    {
        State.HelperSourceNames = Pose.BoneNames;
        State.HelperSourceIndices.SetNumUninitialized(State.SkeletonNames.Num());
        for (int32 BoneIndex = 0; BoneIndex < State.SkeletonNames.Num(); ++BoneIndex)
            State.HelperSourceIndices[BoneIndex] = Pose.BoneNames.IndexOfByKey(State.SkeletonNames[BoneIndex]);
    }
    for (int32 BoneIndex = 0; BoneIndex < State.SkeletonNames.Num(); ++BoneIndex)
    {
        const int32 PoseIndex = State.HelperSourceIndices[BoneIndex];
        if (Pose.LocalTransforms.IsValidIndex(PoseIndex)) State.AuthoredLocalScratch[BoneIndex] = Pose.LocalTransforms[PoseIndex];
    }
    return ProphecyJolt::Pose::ValidateLocalPose(State.AuthoredLocalScratch, OutError);
}

bool StillOwnsRig(const FProphecyJoltCharacterState& State)
{
    UProphecyJoltWorldSubsystem* Owner = State.WorldOwner.Get();
    return State.bOwnsRig && Owner && Owner->OwnsRig(State.RigHandle);
}

bool SameRig(const FProphecyJoltRigHandle& A, const FProphecyJoltRigHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

bool GetEnableSource(const UProphecyJoltCharacterComponent& Character, AProphecyAgent*& OutAgent,
    USkeletalMeshComponent*& OutMesh, FString& OutError)
{
    OutAgent = Cast<AProphecyAgent>(Character.GetOwner());
    OutMesh = IsValid(OutAgent) ? OutAgent->GetPoseReferenceMesh() : nullptr;
    if (!Character.IsRegistered() || !IsValid(OutAgent) || OutAgent->IsActorBeingDestroyed()
        || !OutAgent->bManualNNPoseApplication
        || OutAgent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical
        || !IsValid(OutMesh) || OutMesh == OutAgent->GetAgentMesh() || OutMesh->GetFName() != TEXT("PhysicalMesh")
        || !OutMesh->IsRegistered() || !OutMesh->GetSkeletalMeshAsset() || !OutMesh->IsAnySimulatingPhysics())
    {
        OutError = TEXT("Enable requires a registered manual Physical agent with its existing live, separate PhysicalMesh.");
        return false;
    }
    if (!OutMesh->GetComponentTransform().GetScale3D().Equals(FVector::OneVector, 1.0e-6))
    {
        OutError = TEXT("The first Jolt character binding requires unit component-to-world scale.");
        return false;
    }
    return true;
}
}

UProphecyJoltCharacterComponent::UProphecyJoltCharacterComponent()
{
    // Targets belong to the Agent tick; stepping/presentation belong to the shared coordinator.
    PrimaryComponentTick.bCanEverTick = false;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

UProphecyJoltCharacterComponent::~UProphecyJoltCharacterComponent() = default;

bool UProphecyJoltCharacterComponent::Fail(FString& OutError, const FString& Message)
{
    LastError = Message;
    OutError = Message;
    return false;
}

bool UProphecyJoltCharacterComponent::EnablePhysicalAnimation(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread()) return Fail(OutError, TEXT("Jolt character binding requires the game thread."));
    if (bEnableInProgress || IsKinematicRestorePending())
        return Fail(OutError, TEXT("A Jolt character handoff cannot reenter its own enable/disable operation."));
    if (IsSteppingStopped()) { OutError = LastError; return false; }
    if (IsJoltPhysical()) return true;
    if (IsEnablePending()) return true;
    bEnableCancelled = false;
    AProphecyAgent* Agent = nullptr;
    USkeletalMeshComponent* Mesh = nullptr;
    FString Error;
    if (!GetEnableSource(*this, Agent, Mesh, Error)) return Fail(OutError, Error);
    UProphecyJoltCharacterWorldSubsystem* Coordinator = GetWorld()
        ? GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>() : nullptr;
    bool bDeferred = false;
    if (!Coordinator || !Coordinator->RequestEnable(*this, bDeferred, Error))
        return Fail(OutError, Coordinator ? Error : TEXT("The game-world Jolt character coordinator is unavailable."));
    if (bDeferred)
    {
        LastError.Reset();
        return true; // No capture, native rig, mesh mutation or physics ownership change has occurred.
    }
    return EnablePhysicalAnimationNow(OutError);
}

void UProphecyJoltCharacterComponent::CompleteDeferredEnable(const FGuid& AdmissionId)
{
    check(IsInGameThread());
    if (PendingAdmissionId != AdmissionId || !AdmissionId.IsValid()) return;
    PendingAdmissionId.Invalidate();
    AdmissionCoordinator.Reset();
    FString Error;
    const bool bSucceeded = EnablePhysicalAnimationNow(Error);
    if (bEnableCancelled || !IsValid(this) || !IsRegistered() || !IsValid(GetOwner())
        || GetOwner()->IsActorBeingDestroyed())
    {
        OnDeferredEnableCompleted.Clear();
        return;
    }
    // Move before dispatch: a completion callback may request another enable and bind its own result.
    FProphecyJoltDeferredEnableCompleted Completion = MoveTemp(OnDeferredEnableCompleted);
    OnDeferredEnableCompleted.Clear();
    if (!bSucceeded)
    {
        LastError = Error;
        UE_LOG(LogProphecyJoltCharacter, Error, TEXT("Deferred Jolt character enable failed: %s"), *Error);
    }
    Completion.Broadcast(bSucceeded, Error);
}

void UProphecyJoltCharacterComponent::CancelDeferredEnable(const FGuid& AdmissionId)
{
    check(IsInGameThread());
    if (PendingAdmissionId == AdmissionId && AdmissionId.IsValid()) DisablePhysicalAnimation();
}

bool UProphecyJoltCharacterComponent::EnablePhysicalAnimationNow(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || bEnableInProgress || IsKinematicRestorePending())
        return Fail(OutError, TEXT("Immediate Jolt admission requires a non-reentrant game-thread handoff."));
    TGuardValue<bool> EnableGuard(bEnableInProgress, true);
    bEnableCancelled = false;
    AProphecyAgent* Agent = nullptr;
    USkeletalMeshComponent* Mesh = nullptr;
    FString Error;
    if (!GetEnableSource(*this, Agent, Mesh, Error)) return Fail(OutError, Error);

    UProphecyJoltWorldSubsystem* Owner = GetWorld() ? GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Owner || !Owner->GetDiagnostics(Diagnostics).IsSuccess() || !Diagnostics.bInitialized || Diagnostics.bFaulted)
        return Fail(OutError, TEXT("Initialize the per-world Jolt owner and explicitly register any required environment before enabling a character. Air is valid."));
    UProphecyJoltCharacterWorldSubsystem* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    FString CoordinatorError;
    if (!Coordinator || !Coordinator->CanRegisterCharacter(*this, CoordinatorError))
        return Fail(OutError, Coordinator ? CoordinatorError : TEXT("The game-world Jolt character coordinator is unavailable."));

    // Finish outstanding animation before reading the source skeleton; this does not advance either solver.
    const TWeakObjectPtr<AProphecyAgent> SourceAgent = Agent;
    const TWeakObjectPtr<USkeletalMeshComponent> SourceMesh = Mesh;
    const TWeakObjectPtr<USkeletalMesh> SourceAsset = Mesh->GetSkeletalMeshAsset();
    Mesh->HandleExistingParallelEvaluationTask(true, true);
    if (bEnableCancelled || !IsValid(this) || !SourceAgent.IsValid() || !SourceMesh.IsValid()
        || SourceAgent->IsActorBeingDestroyed() || !IsRegistered() || !SourceMesh->IsRegistered())
    {
        OutError = TEXT("Jolt admission was cancelled while finishing the source animation.");
        return false;
    }
    if (!GetEnableSource(*this, Agent, Mesh, Error) || Agent != SourceAgent.Get() || Mesh != SourceMesh.Get()
        || Mesh->GetSkeletalMeshAsset() != SourceAsset.Get())
        return Fail(OutError, TEXT("The source agent/mesh changed while finishing animation; admission was not committed."));
    if (!Coordinator->CanRegisterCharacter(*this, Error) || !Owner->GetDiagnostics(Diagnostics).IsSuccess()
        || !Diagnostics.bInitialized || Diagnostics.bFaulted)
        return Fail(OutError, TEXT("The coordinator/native owner changed while finishing source animation."));
    FProphecyJoltRigSnapshot Snapshot;
    FProphecyJoltPreparedRig Prepared;
    if (!ProphecyJolt::Rig::CaptureLiveRig(*Mesh, Snapshot, Error) || !Prepared.Build(Snapshot, Error))
        return Fail(OutError, Error);
    if (Snapshot.Bodies.Num() != 22 || Snapshot.Joints.Num() != 21)
        return Fail(OutError, TEXT("This first character pilot requires the current 22-body / 21-joint manual rig."));

    TUniquePtr<FProphecyJoltCharacterState> Pending = MakeUnique<FProphecyJoltCharacterState>();
    Pending->Agent = Agent;
    Pending->Mesh = Mesh;
    Pending->MeshAsset = Mesh->GetSkeletalMeshAsset();
    Pending->PhysicsAsset = Mesh->GetPhysicsAsset();
    Pending->JointSettings = Snapshot.Joints;
    for (const FConstraintInstance* Joint : Mesh->Constraints) Pending->SourceConstraints.Add(Joint);
    Pending->WorldOwner = Owner;
    Pending->Coordinator = Coordinator;
    Pending->WorldLifetime = Diagnostics.WorldLifetime;
    Pending->ExpectedWorldSteps = Diagnostics.CompletedSteps;
    const FReferenceSkeleton& Skeleton = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    for (int32 BoneIndex = 0; BoneIndex < Skeleton.GetNum(); ++BoneIndex)
    {
        Pending->SkeletonNames.Add(Skeleton.GetBoneName(BoneIndex));
        Pending->Parents.Add(Skeleton.GetParentIndex(BoneIndex));
    }
    if (!BuildAuthoredHelperPose(*Agent, *Mesh, Pending->SkeletonNames, Pending->BaseLocalPose, Error))
        return Fail(OutError, Error);

    TArray<FTransform> InitialBodies;
    for (const FProphecyJoltRigBody& Body : Snapshot.Bodies)
    {
        const FTransform BoneWorld = Mesh->GetSocketTransform(Body.BodyName, RTS_World);
        FProphecyJoltPoseBodyMapping& Mapping = Pending->Mappings.AddDefaulted_GetRef();
        Mapping.BoneIndex = Body.BoneIndex;
        // UE initializes an unwelded skeletal body at its bone frame. Shape/COM offsets
        // are already captured separately. Live physics and rendered bones may describe
        // different poses at handoff: that transient error must never become an offset.
        Mapping.BodyFromBoneRigid = FTransform::Identity;
        Mapping.VisualScale = BoneWorld.GetScale3D();
        Pending->BodyNames.Add(Body.BodyName);
        Pending->CapturedBodyMassesKg.Add(Body.MassKg);
        Pending->OriginalBodyMaterials.Add({float(Body.Friction), float(Body.Restitution),
            Body.EffectiveFrictionCombineMode, Body.EffectiveRestitutionCombineMode});
        InitialBodies.Add(Body.BodyOriginToWorld);
    }
    if (!Pending->ComposeLayout.Build(Pending->BaseLocalPose.Num(), Pending->Parents, Pending->Mappings, Error)
        || !Pending->ComposeLayout.Compose(Pending->BaseLocalPose, InitialBodies,
            Mesh->GetComponentTransform(), Pending->Completed, Error)) return Fail(OutError, Error);

    TArray<FString> Coverage;
    const FProphecyJoltWorldStatus Created = Owner->CreateRig(Snapshot, Prepared, Pending->RigHandle, Pending->Handles, Coverage,
        Agent->IsJoltJointLimitPredictionEnabled() && Agent->GetController() && Agent->GetController()->IsPlayerController());
    if (!Created.IsSuccess()) return Fail(OutError, Created.Message);
    Pending->bOwnsRig = true;
    if (Agent->Mesh && Agent->Mesh != Mesh)
        Agent->Mesh->OnComponentHit.RemoveDynamic(Agent, &AProphecyAgent::HandleMeshHit);
    Mesh->OnComponentHit.AddUniqueDynamic(Agent, &AProphecyAgent::HandleMeshHit);
    auto SolverPolicy = Owner->SetRigHitEvents(Pending->RigHandle, Mesh, Agent->bGeneratePhysicalHitEvents);
    if (SolverPolicy.IsSuccess())
        SolverPolicy = Owner->SetRigCCDMode(Pending->RigHandle, uint8(Agent->GetJoltCCDMode()));
    if (SolverPolicy.IsSuccess())
    {
        int32 Velocity,Position; Agent->GetJoltSolverIterations(Velocity,Position);
        SolverPolicy = Owner->SetRigSolverIterations(Pending->RigHandle, Velocity, Position);
    }
    if (!SolverPolicy.IsSuccess())
    {
        Owner->DestroyRig(Pending->RigHandle);
        return Fail(OutError, SolverPolicy.Message);
    }
    Pending->bMeshTickEnabled = Mesh->IsComponentTickEnabled();
    Pending->bEnableAnimation = Mesh->bEnableAnimation;
    Pending->bPauseAnims = Mesh->bPauseAnims;
    Pending->bNoSkeletonUpdate = Mesh->bNoSkeletonUpdate;
    Pending->bForceRefPose = Mesh->bForceRefpose;
    Pending->bUpdateRateOptimizations = Mesh->bEnableUpdateRateOptimizations;
    Pending->bDeferKinematicBoneUpdate = Mesh->bDeferKinematicBoneUpdate;
    Pending->bDisablePostProcess = Mesh->GetDisablePostProcessBlueprint();
    Pending->CollisionEnabled = Mesh->GetCollisionEnabled();
    Pending->KinematicUpdate = Mesh->KinematicBonesUpdateType;
    Pending->PhysicsTransformUpdate = Mesh->PhysicsTransformUpdateMode;
    State.Reset(Pending.Release());
    FProphecyJoltCharacterState* const CommittingState = State.Get();
    const FProphecyJoltRigHandle CommittingRig = State->RigHandle;
    const auto CommitIsValid = [&]()
    {
        return !bEnableCancelled && IsValid(this) && IsRegistered() && SourceAgent.IsValid()
            && !SourceAgent->IsActorBeingDestroyed() && SourceMesh.IsValid() && SourceMesh->IsRegistered()
            && SourceMesh->GetSkeletalMeshAsset() == SourceAsset.Get() && State.Get() == CommittingState
            && SameRig(State->RigHandle, CommittingRig) && StillOwnsRig(*State);
    };
    const auto AbortCommit = [&]()
    {
        const bool bCancelled = bEnableCancelled;
        if (State.Get() == CommittingState && SameRig(State->RigHandle, CommittingRig))
            DisablePhysicalAnimationInternal(false);
        const FString Message = TEXT("The Jolt binding was removed or changed during its pose handoff.");
        if (bCancelled) { OutError = Message; return false; }
        return Fail(OutError, Message);
    };

    // Commit only after complete Jolt creation. Retain mesh, actor, PHAT and materials for query identity.
    Agent->ReleaseManualFollowerSubstepTargets();
    if (!CommitIsValid()) return AbortCommit();
    TInlineComponentArray<UPhysicalAnimationComponent*> PhysicalAnimations(Agent);
    for (UPhysicalAnimationComponent* PhysicalAnimation : PhysicalAnimations)
    {
        PhysicalAnimation->SetStrengthMultiplyer(0.0f);
        PhysicalAnimation->SetComponentTickEnabled(false);
        if (!CommitIsValid()) return AbortCommit();
    }
    Mesh->SetAllBodiesSimulatePhysics(false);
    if (!CommitIsValid()) return AbortCommit();
    Mesh->SetSimulatePhysics(false);
    if (!CommitIsValid()) return AbortCommit();
    Mesh->SetAllBodiesPhysicsBlendWeight(0.0f);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    if (!CommitIsValid()) return AbortCommit();
    // QueryOnly may recreate UE physics state from PHAT defaults. Retain the live angular
    // overrides captured for Jolt, and only then bind the new receiver constraint identities.
    if (Mesh->GetPhysicsAsset() != State->PhysicsAsset.Get()
        || Mesh->Constraints.Num() != State->JointSettings.Num()) return AbortCommit();
    for (const FProphecyJoltRigJoint& Joint : State->JointSettings)
    {
        const int32 Index = Joint.SourceConstraintIndex;
        FConstraintInstance* Current = Mesh->Constraints.IsValidIndex(Index) ? Mesh->Constraints[Index] : nullptr;
        if (!Current || Current->JointName != Joint.JointName || Current->ConstraintBone1 != Joint.Bone1
            || Current->ConstraintBone2 != Joint.Bone2) return AbortCommit();
    }
    for (const FProphecyJoltRigJoint& Joint : State->JointSettings)
    {
        const int32 Index = Joint.SourceConstraintIndex;
        if (!ProphecyAngularLimits::Equal(Mesh->Constraints[Index]->ProfileInstance, Joint.CurrentProfile))
            ProphecyAngularLimits::Apply(*Mesh->Constraints[Index], Joint.CurrentProfile);
        State->SourceConstraints[Index] = Mesh->Constraints[Index];
    }
    Mesh->PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
    Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
    Mesh->bDeferKinematicBoneUpdate = false;
    Mesh->bEnableUpdateRateOptimizations = false;
    Mesh->bPauseAnims = false;
    Mesh->bNoSkeletonUpdate = false;
    Mesh->bForceRefpose = false;
    Mesh->SetEnableAnimation(true);
    if (!CommitIsValid()) return AbortCommit();
    Mesh->SetDisablePostProcessBlueprint(true);
    Mesh->SetComponentTickEnabled(false); // One explicit completed-pose evaluation, including query updates.
    Mesh->SetAnimInstanceClass(UProphecyJoltPoseAnimInstance::StaticClass());
    if (!CommitIsValid()) return AbortCommit();
    // A disabled postprocess instance may remain allocated. Its callbacks still run normally,
    // but it does not evaluate a later pose. Commit before the final skeletal buffer flip.
    if (Mesh->GetAnimInstance() && Mesh->GetAnimInstance()->GetClass() == UProphecyJoltPoseAnimInstance::StaticClass()
        && static_cast<const USkeletalMeshComponent*>(Mesh)->GetLinkedAnimInstances().IsEmpty()
        && (!Mesh->GetPostProcessInstance() || Mesh->GetDisablePostProcessBlueprint()))
    {
        FString QueryError;
        if (!State->QueryPose.Initialize(*Mesh, QueryError))
        {
            DisablePhysicalAnimationInternal(false);
            return Fail(OutError, QueryError);
        }
        State->bBulkQueryPublication = true;
        Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;
    }
    State->bActive = true;
    AddTickPrerequisiteActor(Agent);
    if (!PublishAuthoredTargets(GetWorld()->GetDeltaSeconds(), Error) || !PublishCompletedPose(Error)
        || !CommitIsValid() || !SynchronizeAngularLimits(Error) || !ProphecyKickFootLeeway::Reapply(Agent,Error)
        || !Coordinator->RegisterCharacter(*this, Error))
    {
        if (State.Get() == CommittingState && SameRig(State->RigHandle, CommittingRig))
            DisablePhysicalAnimationInternal(false);
        if (bEnableCancelled) { OutError = Error; return false; }
        return Fail(OutError, FString::Printf(TEXT("Jolt creation succeeded but pose handoff failed; restored kinematic presentation: %s"), *Error));
    }
    LastError.Reset();
    return true;
}

bool UProphecyJoltCharacterComponent::PublishAuthoredTargets(float DeltaSeconds, FString& OutError)
{
    namespace Profile = ProphecyJolt::CharacterProfiling;
    Profile::FScope Timing(Profile::EPhase::Targets);
    OutError.Reset();
    if (IsInGameThread() && IsSteppingStopped()) { OutError = LastError; return false; }
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State))
        return Fail(OutError, TEXT("Target publication requires this component's live Jolt rig on the game thread."));
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds < 0.0f)
        return Fail(OutError, TEXT("Target frame duration must be finite and nonnegative."));
    AProphecyAgent* Agent = State->Agent.Get();
    USkeletalMeshComponent* Mesh = State->Mesh.Get();
    if (!Agent || !Mesh || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get())
        return Fail(OutError, TEXT("The bound agent/mesh changed; disable the Jolt binding before replacing assets."));
    FProphecyJoltCharacterState* const PublishingState = State.Get();
    const FProphecyJoltRigHandle PublishingRig = State->RigHandle;
    TArray<FName>& Names = State->TargetNames;
    TArray<FTransform>& Future = State->FutureTargets;
    TArray<FTransform>& Interpolated = State->InterpolatedTargets;
    float Alpha = 1.0f;
    {
        Profile::FScope PhaseTiming(Profile::EPhase::TargetRead);
        if (!Agent->ReadNNFutureWorldPoseWithSnapshot(Names, Future, Interpolated, Alpha, State->AuthoredSnapshot)
            || Names.Num() != Interpolated.Num())
            return Fail(OutError, TEXT("The manual authored pose is unavailable; the last valid Jolt packet remains published."));
    }
    ProphecyPelvisInertia::SynchronizeJolt(Agent);
    TArray<FTransform>& NewBaseLocal = State->AuthoredLocalScratch;
    FString Error;
    {
        Profile::FScope PhaseTiming(Profile::EPhase::HelperPose);
        if (!BuildAuthoredHelperPoseFromSnapshot(*Mesh, *State, Error)) return Fail(OutError, Error);
    }
    {
        Profile::FScope PhaseTiming(Profile::EPhase::Fingers);
        ProphecyAttackFists::PreUpdate(this, Agent);
        // A first-use animation load may dispatch callbacks. Do not use scratch references after
        // a callback removes/replaces this exact binding; normal self-disable keeps its clean state.
        if (State.Get() != PublishingState || !State || !SameRig(State->RigHandle, PublishingRig)
            || !State->bActive || State->bSteppingStopped || State->Agent.Get() != Agent
            || !State->Agent.IsValid() || State->Agent->IsActorBeingDestroyed() || State->Mesh.Get() != Mesh
            || !State->Mesh.IsValid() || State->Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get()
            || !StillOwnsRig(*State))
        { OutError = TEXT("The Jolt binding changed while preparing its authored finger pose."); return false; }
        ProphecyAttackFists::ApplyToLocalPose(this, State->SkeletonNames, NewBaseLocal);
    }
    if (!ProphecyJolt::Pose::ValidateLocalPose(NewBaseLocal, Error)) return Fail(OutError, Error);
    TArray<FProphecyJoltRigVelocityTarget>& Targets = State->TargetScratch;
    Targets.Reset(State->Handles.Num());
    State->AuthoredBodyScratch.SetNum(State->Handles.Num());
    {
    Profile::FScope PhaseTiming(Profile::EPhase::TargetPacket);
    State->TargetNameLookup.Update(Names, State->BodyNames);
    const float FootTargetLeeway=ProphecyPhysicalFootTarget::Leeway(Agent);
    const float KickFootLeeway=ProphecyKickFootLeeway::Current(Agent);
    for (int32 Index = 0; Index < State->Handles.Num(); ++Index)
    {
        const int32 TargetIndex = State->TargetNameLookup.GetIndices()[Index];
        if (!Interpolated.IsValidIndex(TargetIndex))
            return Fail(OutError, FString::Printf(TEXT("Published authored pose is missing rig bone %s."), *State->BodyNames[Index].ToString()));
        FTransform BodyWorld = Interpolated[TargetIndex];
        State->AuthoredBodyScratch[Index] = BodyWorld;
        FProphecyBodyMagnetizationSettings Settings;
        Agent->GetBodyMagnetizationSettings(State->BodyNames[Index], Settings); // Missing entries intentionally use native defaults.
        if (!Agent->bWorldMagnetizationEnabled || !Settings.bSimulateBody || !Settings.bMagnetizationEnabled) continue;
        // Foot translation follows the end of the authored calf, even when NN
        // presentation clamps are off. Leave NN data and every rotation untouched.
        // Use the reference offset, not the stretched foot local from the NN pose.
        static const FName Feet[] = {TEXT("foot_l"),TEXT("foot_r")};
        static const FName Calves[] = {TEXT("calf_l"),TEXT("calf_r")};
        const int32 Side = State->BodyNames[Index]==Feet[0] ? 0 : State->BodyNames[Index]==Feet[1] ? 1 : INDEX_NONE;
        if (Side!=INDEX_NONE)
        {
            const auto& Skeleton=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
            const int32 FootBone=State->Mappings[Index].BoneIndex;
            const int32 Parent=Skeleton.GetParentIndex(FootBone);
            const int32 CalfTarget=Names.IndexOfByKey(Calves[Side]);
            if (Parent!=INDEX_NONE && Skeleton.GetBoneName(Parent)==Calves[Side] && Interpolated.IsValidIndex(CalfTarget))
            {
                const FVector Offset=Skeleton.GetRefBonePose()[FootBone].GetTranslation();
                const FTransform& Calf=Interpolated[CalfTarget];
                const FVector End=Calf.TransformPosition(Offset),Original=BodyWorld.GetLocation();
                FVector Target=ProphecyPhysicalFootTarget::Clamp(Original,End,FootTargetLeeway);
                if (KickFootLeeway>0) Target=ProphecyKickFootLeeway::Target(Original,Target,End,
                    Calf.TransformVector(Offset).GetSafeNormal(),KickFootLeeway);
                BodyWorld.SetLocation(Target);
            }
            // Start/end trajectories and lower feedback must agree with the drive.
            State->AuthoredBodyScratch[Index]=BodyWorld;
        }
        FProphecyJoltRigVelocityTarget& Target = Targets.AddDefaulted_GetRef();
        Target.Handle = State->Handles[Index];
        Target.TargetPositionCm = BodyWorld.GetLocation();
        Target.TargetRotation = BodyWorld.GetRotation();
        if (DeltaSeconds > 0.0f)
        {
            if (const FTransform* Start = State->AuthoredTargetHistory.GetStart(Index, State->ExpectedWorldSteps))
            {
                Target.StartPositionCm = Start->GetLocation();
                Target.StartRotation = Start->GetRotation();
                Target.TrajectoryDurationSeconds = DeltaSeconds;
            }
        }
        Target.LinearStrength = FMath::Max(0.0f, Agent->WorldMagnetizationLinearStrengthScale * Settings.LinearStrengthScale);
        Target.AngularStrength = FMath::Max(0.0f, Agent->WorldMagnetizationAngularStrengthScale * Settings.AngularStrengthScale);
        Target.GravityCompensationCmPerSecondSquared = Settings.bCancelGravity ? -Agent->GetWorld()->GetGravityZ() : 0.0f;
    }
    }
    const UPhysicsSettings* Physics = UPhysicsSettings::Get();
    const float H = ProphecyJolt::StepTiming::Duration(DeltaSeconds, Physics, GetWorld());
    if (State->AuthoredPublicationSerial == MAX_uint64)
        return Fail(OutError, TEXT("Authored pose publication serial exhausted; disable and rebind the character."));
    {
        Profile::FScope PhaseTiming(Profile::EPhase::TargetCommit);
        const FProphecyJoltWorldStatus Published = State->WorldOwner->PublishRigVelocityTargets(State->RigHandle, Targets, H);
        if (!Published.IsSuccess()) return Fail(OutError, Published.Message);
    }
    State->AuthoredTargetHistory.Commit(State->AuthoredBodyScratch, State->ExpectedWorldSteps);
    Swap(State->BaseLocalPose, State->AuthoredLocalScratch);
    ++State->AuthoredPublicationSerial;
    State->LastPublicationFrame = GFrameCounter;
    LastError.Reset();
    return true;
}

void UProphecyJoltCharacterComponent::PrepareCompletedPoseBatch(TConstArrayView<UProphecyJoltCharacterComponent*> Characters, float DeltaSeconds)
{
    check(IsInGameThread());
    // Capture before any completed-pose callback can publish the NEXT target.
    // Runs for the serial/single-character path as well; only requested lower bones.
    for (const auto* Character : Characters)
        if (IsValid(Character) && Character->IsJoltPhysical() && !Character->IsSteppingStopped())
            CaptureLowerFeedbackTargets(Character, *Character->State, DeltaSeconds);
    // The coordinator supplies unique exact native characters. Small/admission paths remain serial.
    static const bool bSerialCompose = FParse::Param(FCommandLine::Get(), TEXT("ProphecyJoltSerialCompose"));
    if (Characters.Num() < 2 || bSerialCompose) return;
    namespace Profile = ProphecyJolt::CharacterProfiling;
    // This wall scope includes GT capture, parallel math and result installation. BodyRead is nested.
    Profile::FScope BatchTiming(Profile::EPhase::ComposeBatch);
    TArray<ProphecyJolt::Pose::FComposeBatchItem, TInlineAllocator<128>> Jobs;
    TArray<FProphecyJoltCompletedPosePacket*, TInlineAllocator<128>> Packets;
    {
        Profile::FScope ReadTiming(Profile::EPhase::BodyRead);
        for (UProphecyJoltCharacterComponent* Character : Characters)
        {
            if (!IsValid(Character) || Character->GetClass() != StaticClass() || !Character->IsRegistered()
                || !Character->IsJoltPhysical() || Character->IsSteppingStopped()) continue;
            FProphecyJoltCharacterState& Current = *Character->State;
            Current.CompletedPacket.bReady = false;
            auto* Owner = Current.WorldOwner.Get();
            auto* Mesh = Current.Mesh.Get();
            auto* Anim = Mesh ? Cast<UProphecyJoltPoseAnimInstance>(Mesh->GetAnimInstance()) : nullptr;
            FProphecyJoltWorldDiagnostics Diagnostics;
            if (!Owner || !Owner->OwnsRig(Current.RigHandle) || !Mesh || !Mesh->IsRegistered() || !Anim
                || !Current.Agent.IsValid() || Current.Agent->IsActorBeingDestroyed()
                || Mesh->GetSkeletalMeshAsset() != Current.MeshAsset.Get() || !Current.ComposeLayout.IsValid()
                || Current.Revision == MAX_uint64 || Current.ExpectedWorldSteps == MAX_uint64
                || !Owner->GetDiagnostics(Diagnostics).IsSuccess() || Diagnostics.bFaulted
                || Diagnostics.CompletedSteps != Current.ExpectedWorldSteps + 1) continue;

            auto& Packet = Current.CompletedPacket;
            Packet.Pose = MoveTemp(Current.CompletedScratch);
            Packet.ComponentWorld = Mesh->GetComponentTransform();
            Packet.Agent = Current.Agent; Packet.Mesh = Mesh; Packet.MeshAsset = Current.MeshAsset;
            Packet.Anim = Anim; Packet.Owner = Owner; Packet.Rig = Current.RigHandle;
            Packet.Registration = Character->StepRegistrationId;
            Packet.Revision = Current.Revision; Packet.CompletedSteps = Diagnostics.CompletedSteps;
            Packet.AuthoredSerial = Current.AuthoredPublicationSerial;
            Packet.Error.Reset(); Packet.bSucceeded = false;
            Current.CompletedBodyScratch.Reset(Current.Handles.Num());
            bool bReadSucceeded = true;
            for (const auto& Handle : Current.Handles)
            {
                FProphecyJoltBodyState Body;
                const auto Read = Owner->ReadBody(Handle, Body);
                if (!Read.IsSuccess()) { Packet.Error = Read.Message; bReadSucceeded = false; break; }
                Current.CompletedBodyScratch.Emplace(Body.Rotation, Body.PositionCm);
            }
            if (!bReadSucceeded)
            {
                Packet.Pose.LocalTransforms.Reset(); Packet.Pose.ComponentTransforms.Reset(); Packet.Pose.WorldTransforms.Reset();
                Packet.bReady = true; // Report only if this exact binding reaches its original consume turn.
                continue;
            }
            auto& Job = Jobs.AddDefaulted_GetRef();
            Job.Layout = &Current.ComposeLayout;
            Job.BaseLocal = Current.BaseLocalPose;
            Job.BodyWorld = Current.CompletedBodyScratch;
            Job.ComponentWorld = Packet.ComponentWorld;
            Job.Output = &Packet.Pose;
            Packets.Add(&Packet);
        }
    }
    // ParallelFor(None) helps with these jobs and then waits; it does not pump game-thread callbacks.
    // State-owned plain layouts/arrays are immutable and alive until this call has joined every job.
    ProphecyJolt::Pose::ComposeBatch(Jobs);
    for (int32 Index = 0; Index < Jobs.Num(); ++Index)
    {
        Packets[Index]->bSucceeded = Jobs[Index].bSucceeded;
        Packets[Index]->Error = MoveTemp(Jobs[Index].Error);
        Packets[Index]->bReady = true;
    }
}

bool UProphecyJoltCharacterComponent::PublishCompletedPose(FString& OutError)
{
    namespace Profile = ProphecyJolt::CharacterProfiling;
    Profile::FScope Timing(Profile::EPhase::CompletedPose);
    OutError.Reset();
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State))
        return Fail(OutError, TEXT("Completed pose publication requires a live owned rig."));
    USkeletalMeshComponent* Mesh = State->Mesh.Get();
    UProphecyJoltPoseAnimInstance* Anim = Mesh ? Cast<UProphecyJoltPoseAnimInstance>(Mesh->GetAnimInstance()) : nullptr;
    if (!Mesh || !Anim || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get() || State->Revision == MAX_uint64)
        return Fail(OutError, TEXT("Completed Jolt pose publication lost its bound mesh/AnimInstance or exhausted its revision."));
    // Refresh(nullptr), TickAnimation and a pending parallel-task completion can run user callbacks.
    // Keep detached cleanup alive until those engine calls have fully returned. No timer or extra tick.
    check(!bPublishingCompletedPose);
    TGuardValue<bool> PublicationGuard(bPublishingCompletedPose, true);
    ON_SCOPE_EXIT
    {
        if (DeferredMeshRestore)
        {
            TWeakObjectPtr<AProphecyAgent> RestoringAgent = DeferredMeshRestore->Agent;
            RestoreKinematicMesh(MoveTemp(DeferredMeshRestore));
            if (RestoringAgent.IsValid()) RestoringAgent->FinishJoltBackendRestore();
        }
    };
    FProphecyJoltCharacterState* const PublishingState = State.Get();
    const FProphecyJoltRigHandle PublishingRig = State->RigHandle;
    const TWeakObjectPtr<USkeletalMeshComponent> PublishingMesh = Mesh;
    const TWeakObjectPtr<UProphecyJoltPoseAnimInstance> PublishingAnim = Anim;
    const TWeakObjectPtr<USkeletalMesh> PublishingAsset = State->MeshAsset;
    const TWeakObjectPtr<AProphecyAgent> PublishingAgent = State->Agent;
    const TWeakObjectPtr<UProphecyJoltWorldSubsystem> PublishingOwner = State->WorldOwner;
    const FTransform ComponentToWorld = Mesh->GetComponentTransform();
    const uint64 Revision = State->Revision;
    const FGuid PublishingRegistration = StepRegistrationId;
    const uint64 CompletedSteps = State->ExpectedWorldSteps;
    const auto ValidatePublication = [&]()
    {
        Profile::FScope ValidationTiming(Profile::EPhase::PublicationValidation);
        FProphecyJoltWorldDiagnostics Diagnostics;
        const bool bValid = IsValid(this) && IsRegistered() && State.Get() == PublishingState
            && State->bActive && !State->bSteppingStopped && SameRig(State->RigHandle, PublishingRig)
            && State->Revision == Revision && StepRegistrationId == PublishingRegistration
            && (!PublishingRegistration.IsValid() || (State->Coordinator.IsValid()
                && State->Coordinator->IsStepClientRegistered(*this, PublishingRegistration)))
            && PublishingAgent.IsValid() && !PublishingAgent->IsActorBeingDestroyed()
            && PublishingMesh.IsValid() && PublishingMesh->IsRegistered() && PublishingAnim.IsValid()
            && State->Mesh == PublishingMesh && State->MeshAsset == PublishingAsset
            && PublishingMesh->GetSkeletalMeshAsset() == PublishingAsset.Get()
            && PublishingMesh->GetAnimInstance() == PublishingAnim.Get()
            && (!State->bBulkQueryPublication || !PublishingMesh->GetPostProcessInstance()
                || PublishingMesh->GetDisablePostProcessBlueprint())
            && PublishingMesh->GetComponentTransform().Equals(ComponentToWorld, 1.0e-6)
            && PublishingOwner.IsValid() && State->WorldOwner == PublishingOwner
            && PublishingOwner->OwnsRig(PublishingRig)
            && PublishingOwner->GetDiagnostics(Diagnostics).IsSuccess() && !Diagnostics.bFaulted
            && Diagnostics.CompletedSteps == CompletedSteps;
        if (!bValid)
        {
            OutError = TEXT("The exact Jolt rig/mesh/pose binding was removed or changed during animation publication.");
            // Normal self-disable deliberately cleared its error and state. Do not overwrite that or
            // a replacement binding's error; the coordinator skips this removed presentation target.
            if (State.Get() == PublishingState && State->bActive && !State->bSteppingStopped) LastError = OutError;
        }
        return bValid;
    };
    if (!ValidatePublication()) return false;
    // Locally own whichever working buffer is used before any animation callback can remove State.
    FProphecyJoltComposedPose Completed;
    FString Error;
    bool bUsePrepared = false;
    auto& Packet = State->CompletedPacket;
    if (Packet.bReady)
    {
        const FQuat A = Packet.ComponentWorld.GetRotation(), B = ComponentToWorld.GetRotation();
        const bool bSameCarrier = A.X == B.X && A.Y == B.Y && A.Z == B.Z && A.W == B.W
            && Packet.ComponentWorld.GetTranslation() == ComponentToWorld.GetTranslation()
            && Packet.ComponentWorld.GetScale3D() == ComponentToWorld.GetScale3D();
        const bool bMatches = Packet.Agent == PublishingAgent && Packet.Mesh == PublishingMesh
            && Packet.MeshAsset == PublishingAsset && Packet.Anim == PublishingAnim && Packet.Owner == PublishingOwner
            && SameRig(Packet.Rig, PublishingRig) && Packet.Registration == PublishingRegistration
            && Packet.Revision == Revision && Packet.CompletedSteps == CompletedSteps
            && Packet.AuthoredSerial == State->AuthoredPublicationSerial && bSameCarrier;
        Packet.bReady = false;
        Completed = MoveTemp(Packet.Pose);
        if (bMatches)
        {
            if (!Packet.bSucceeded) return Fail(OutError, Packet.Error);
            bUsePrepared = true;
        }
        // Earlier publication callbacks may change a later carrier or authored pose. Reuse storage,
        // but recompute current inputs. A destroyed/replaced state has no old packet to consume.
    }
    else Completed = MoveTemp(State->CompletedScratch);
    if (!bUsePrepared)
    {
        TArray<FTransform>& Bodies = State->CompletedBodyScratch;
        Bodies.Reset(State->Handles.Num());
        {
            Profile::FScope PhaseTiming(Profile::EPhase::BodyRead);
            for (const FProphecyJoltBodyHandle& Handle : State->Handles)
            {
                FProphecyJoltBodyState Body;
                const auto Read = State->WorldOwner->ReadBody(Handle, Body);
                if (!Read.IsSuccess()) return Fail(OutError, Read.Message);
                Bodies.Emplace(Body.Rotation, Body.PositionCm);
            }
        }
        {
            Profile::FScope PhaseTiming(Profile::EPhase::Compose);
            if (!State->ComposeLayout.Compose(State->BaseLocalPose, Bodies, ComponentToWorld,
                Completed, Error)) return Fail(OutError, Error);
        }
    }
    {
        Profile::FScope PhaseTiming(Profile::EPhase::AnimBuffer);
        if (!Anim->PublishCompletedLocalPose(Completed.LocalTransforms, Revision + 1, Error)) return Fail(OutError, Error);
    }
    { Profile::FScope PhaseTiming(Profile::EPhase::ParallelWait); Mesh->HandleExistingParallelEvaluationTask(true, true); }
    if (!ValidatePublication()) return false;
    { Profile::FScope PhaseTiming(Profile::EPhase::AnimTick); Mesh->TickAnimation(0.0f, false); }
    if (!ValidatePublication()) return false;
    const bool bBulkQueries = State->bBulkQueryPublication;
    double QueryCompletedAt = 0.0;
    if (bBulkQueries)
    {
        if (!Anim->ArmPostEvaluateQueryCommit(FProphecyJoltPostEvaluateQueryCommit::CreateLambda([&](FString& QueryError)
        {
            Profile::FScope PhaseTiming(Profile::EPhase::QueryUpdate);
            if (!ValidatePublication()) { QueryError = OutError; return false; }
            const bool bPublished = State->QueryPose.Publish(*Mesh, Completed.WorldTransforms, QueryError);
            QueryCompletedAt = Profile::Timestamp();
            return bPublished;
        }), Revision + 1, Error)) return Fail(OutError, Error);
    }
    { Profile::FScope PhaseTiming(Profile::EPhase::RefreshBones); Mesh->RefreshBoneTransforms(nullptr); }
    Profile::RecordElapsed(Profile::EPhase::FinalizeAfterQuery, QueryCompletedAt);
    if (PublishingAnim.IsValid()) PublishingAnim->ClearPostEvaluateQueryCommit();
    // Queries were committed before buffer flip, notifies and finalization callbacks.
    // Those callbacks can remove/replace the binding; preserve existing exact-identity guards.
    if (!ValidatePublication()) return false;
    if (bBulkQueries)
    {
        if (!Anim->GetPostEvaluateQueryCommitResult(Revision + 1, Error)) return Fail(OutError, Error);
    }
    else
    {
        Profile::FScope PhaseTiming(Profile::EPhase::QueryUpdate);
        Mesh->UpdateKinematicBonesToAnim(Mesh->GetComponentSpaceTransforms(), ETeleportType::TeleportPhysics,
            true, EAllowKinematicDeferral::DisallowDeferral);
    }
    if (!ValidatePublication()) return false;
    Swap(State->Completed, Completed);
    State->CompletedScratch = MoveTemp(Completed);
    ++State->Revision;
    return true;
}

bool UProphecyJoltCharacterComponent::StepAndPublish(float DeltaSeconds, FString& OutError)
{
    OutError.Reset();
    if (IsInGameThread() && IsSteppingStopped()) { OutError = LastError; return false; }
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State))
        return Fail(OutError, TEXT("Step requires this component's live Jolt rig on the game thread."));
    UProphecyJoltCharacterWorldSubsystem* Coordinator = State->Coordinator.Get();
    if (!Coordinator) return Fail(OutError, TEXT("The shared Jolt character coordinator is unavailable."));
    if (!Coordinator->StepExplicit(*this, DeltaSeconds, OutError))
    {
        if (!IsSteppingStopped()) LastError = OutError;
        return false;
    }
    return true;
}

bool UProphecyJoltCharacterComponent::PrepareJoltWorldStep(float DeltaSeconds,
    bool bPublishMissingTargets, FString& OutError)
{
    return PrepareForCoordinatedWorldStep(DeltaSeconds, bPublishMissingTargets, OutError);
}

bool UProphecyJoltCharacterComponent::ConsumeCompletedJoltWorldStep(FString& OutError)
{
    return ConsumeCompletedWorldStep(OutError);
}

void UProphecyJoltCharacterComponent::LatchJoltStepError(const FString& Error)
{
    LatchSteppingStopped(Error);
}

bool UProphecyJoltCharacterComponent::PrepareForCoordinatedWorldStep(float DeltaSeconds,
    bool bPublishMissingTargets, FString& OutError)
{
    OutError.Reset();
    if (IsInGameThread() && IsSteppingStopped()) { OutError = LastError; return false; }
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State))
        return Fail(OutError, TEXT("The shared step requires this character's live rig ownership."));
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f)
        return Fail(OutError, TEXT("Jolt character step duration must be finite and positive."));
    USkeletalMeshComponent* Mesh = State->Mesh.Get();
    AProphecyAgent* Agent = State->Agent.Get();
    if (Mesh && !Mesh->IsAnySimulatingPhysics() && Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics)
    {
        const auto* Binding = State.Get();
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        if (State.Get() != Binding || !State || !StillOwnsRig(*State)) return false;
        if (!State->QueryPose.Initialize(*Mesh, OutError)) return false;
        State->LastObjectChannel = ECC_MAX;
        // UE can recreate its PHAT query bodies/constraints when a preset toggles
        // physics flags. Rebind that proxy identity, retaining the Jolt articulation.
        if (Mesh->GetPhysicsAsset() != State->PhysicsAsset.Get() || Mesh->Constraints.Num() != State->JointSettings.Num())
            return Fail(OutError, TEXT("Collision preset changed the bound PHAT layout."));
        for (const auto& Joint : State->JointSettings)
        {
            const auto* Constraint = Mesh->Constraints[Joint.SourceConstraintIndex];
            if (!Constraint || Constraint->JointName != Joint.JointName
                || Constraint->ConstraintBone1 != Joint.Bone1 || Constraint->ConstraintBone2 != Joint.Bone2)
                return Fail(OutError, TEXT("Collision preset changed a bound joint identity."));
            State->SourceConstraints[Joint.SourceConstraintIndex] = Constraint;
        }
    }
    if (!Agent || !Mesh || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get()
        || Mesh->IsAnySimulatingPhysics() || Mesh->GetCollisionEnabled() != ECollisionEnabled::QueryOnly
        || !Cast<UProphecyJoltPoseAnimInstance>(Mesh->GetAnimInstance()))
        return Fail(OutError, TEXT("PhysicalMesh ownership was changed externally; Jolt requires Chaos simulation off, QueryOnly and its completed-pose AnimInstance."));
    if (bPublishMissingTargets && Agent->bAutoPublishManualFollowerSubstepTargets && !Agent->IsActorTickEnabled())
        return Fail(OutError, TEXT("Automatic target ordering requires the publishing Agent tick to remain enabled."));
    FProphecyJoltWorldDiagnostics Diagnostics;
    const FProphecyJoltWorldStatus Read = State->WorldOwner->GetDiagnostics(Diagnostics);
    if (!Read.IsSuccess()) return Fail(OutError, Read.Message);
    if (Diagnostics.CompletedSteps != State->ExpectedWorldSteps)
        return Fail(OutError, TEXT("This rig has an unconsumed external world step; only the shared coordinator may advance bound rigs."));
    if (bPublishMissingTargets && Agent->bAutoPublishManualFollowerSubstepTargets
        && State->LastPublicationFrame != GFrameCounter && !PublishAuthoredTargets(DeltaSeconds, OutError)) return false;
    // Publication can invoke callbacks. Revalidate the live binding before reading UE constraint state.
    if (!SynchronizeAngularLimits(OutError)) return false;
    if (!ProphecyJointDamping::Update(Agent,State->Handles[0],OutError)) return false;
    Mesh = State->Mesh.Get();
    const auto Channel = Mesh->GetCollisionObjectType();
    const auto Responses = Mesh->GetCollisionResponseToChannels();
    if (Channel != State->LastObjectChannel || Responses != State->LastCollisionResponses)
    {
        TArray<FProphecyJoltCollisionUpdate, TInlineAllocator<32>> Updates;
        for (int32 Index = 0; Index < State->Handles.Num(); ++Index)
        {
            const auto* Body = Mesh->GetBodyInstance(State->BodyNames[Index]);
            if (!Body || !Body->IsValidBodyInstance()) return Fail(OutError, TEXT("Collision update lost a PHAT body."));
            // Ask UE to resolve PHAT overrides and component responses exactly as Chaos does.
            FBodyCollisionFilterData Filters;
            Body->BuildBodyFilterData(Filters);
            auto& Update = Updates.AddDefaulted_GetRef();
            Update.Handle = State->Handles[Index];
            Update.ObjectChannel = GetCollisionChannel(Filters.SimFilter.Word3);
            Update.Responses = ExtractSimCollisionResponseContainer(Filters.SimFilter);
        }
        const auto Result = State->WorldOwner->UpdateBodyCollision(Updates);
        if (!Result.IsSuccess()) return Fail(OutError, Result.Message);
        State->LastObjectChannel = Channel;
        State->LastCollisionResponses = Responses;
        ProphecyLimbCollision::Invalidate(Agent);
    }
    return ProphecyLimbCollision::Update(Agent,State->Handles[0],OutError);
}

bool UProphecyJoltCharacterComponent::ValidateAngularLimitSource(FString& OutError) const
{
    if (!IsInGameThread() || !IsJoltPhysical() || IsSteppingStopped() || !StillOwnsRig(*State))
    { OutError = TEXT("Angular-limit changes require this character's healthy live Jolt rig on the game thread."); return false; }
    const USkeletalMeshComponent* Mesh = State->Mesh.Get();
    if (!Mesh || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get()
        || !State->PhysicsAsset.IsValid() || Mesh->GetPhysicsAsset() != State->PhysicsAsset.Get()
        || Mesh->Constraints.Num() != State->SourceConstraints.Num()
        || Mesh->Constraints.Num() != State->JointSettings.Num())
    { OutError = TEXT("The bound mesh/PHAT joint layout changed; disable and rebind Jolt before changing limits."); return false; }
    for (const FProphecyJoltRigJoint& Joint : State->JointSettings)
    {
        const int32 Index = Joint.SourceConstraintIndex;
        if (!Mesh->Constraints.IsValidIndex(Index) || !Mesh->Constraints[Index]
            || Mesh->Constraints[Index] != State->SourceConstraints[Index])
        { OutError = TEXT("A bound PHAT constraint was removed or replaced; disable and rebind Jolt."); return false; }
        const FConstraintInstance& Current = *Mesh->Constraints[Index];
        if (Current.JointName != Joint.JointName || Current.ConstraintBone1 != Joint.Bone1
            || Current.ConstraintBone2 != Joint.Bone2)
        { OutError = TEXT("A bound PHAT joint identity changed; disable and rebind Jolt."); return false; }
    }
    return true;
}

void UProphecyJoltCharacterComponent::RefreshPlayerSwingLimits()
{
    // Admission reads possession independently, including deferred enable requests.
    if (!State || !StillOwnsRig(*State)) return;
    const AProphecyAgent* Agent = Cast<AProphecyAgent>(GetOwner());
    const auto Result = State->WorldOwner->SetRigPlayerSwingLimits(State->RigHandle,
        Agent && Agent->IsJoltJointLimitPredictionEnabled() && Agent->GetController() && Agent->GetController()->IsPlayerController());
    if (!Result.IsSuccess()) LatchJoltStepError(Result.Message);
}

bool UProphecyJoltCharacterComponent::SetCCDMode(uint8 Mode, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || !State || !StillOwnsRig(*State))
    { OutError = TEXT("No active Jolt rig is available."); return false; }
    const auto Result = State->WorldOwner->SetRigCCDMode(State->RigHandle, Mode);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::SetSolverIterations(int32 Velocity, int32 Position, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || !State || !StillOwnsRig(*State))
    { OutError = TEXT("No active Jolt rig is available."); return false; }
    const auto Result = State->WorldOwner->SetRigSolverIterations(State->RigHandle, Velocity, Position);
    OutError = Result.Message;
    return Result.IsSuccess();
}

int32 UProphecyJoltCharacterComponent::GetSpeculativeSwingJointCount() const
{
    if (!State || !StillOwnsRig(*State)) return 0;
    TArray<FProphecyJoltRigJoint> Joints;
    int32 Count = 0;
    return State->WorldOwner->ReadRigAngularLimits(State->RigHandle, Joints, &Count).IsSuccess() ? Count : 0;
}

bool UProphecyJoltCharacterComponent::ApplyAngularLimitProfiles(
    TConstArrayView<FConstraintProfileProperties> Profiles, FString& OutError)
{
    OutError.Reset();
    if (!ValidateAngularLimitSource(OutError)) return Fail(OutError, OutError);
    if (Profiles.Num() != State->SourceConstraints.Num())
        return Fail(OutError, TEXT("Angular-limit changes require one profile for every bound PHAT constraint."));
    TArray<FProphecyJoltRigJoint> Updated = State->JointSettings;
    for (FProphecyJoltRigJoint& Joint : Updated)
        ProphecyAngularLimits::Copy(Joint.CurrentProfile, Profiles[Joint.SourceConstraintIndex]);
    const FProphecyJoltWorldStatus Result = State->WorldOwner->UpdateRigAngularLimits(State->RigHandle, Updated);
    if (!Result.IsSuccess()) return Fail(OutError, Result.Message);
    // The native update prevalidates the whole request. Mirror into UE only after success.
    USkeletalMeshComponent* Mesh = State->Mesh.Get();
    for (const FProphecyJoltRigJoint& Joint : Updated)
    {
        FConstraintInstance& Current = *Mesh->Constraints[Joint.SourceConstraintIndex];
        if (!ProphecyAngularLimits::Equal(Current.ProfileInstance, Joint.CurrentProfile))
            ProphecyAngularLimits::Apply(Current, Joint.CurrentProfile);
    }
    State->JointSettings = MoveTemp(Updated);
    LastError.Reset();
    return true;
}

bool UProphecyJoltCharacterComponent::SynchronizeAngularLimits(FString& OutError)
{
    if (!ValidateAngularLimitSource(OutError)) return Fail(OutError, OutError);
    const USkeletalMeshComponent* Mesh = State->Mesh.Get();
    bool bChanged = false;
    for (const FProphecyJoltRigJoint& Joint : State->JointSettings)
        bChanged |= !ProphecyAngularLimits::Equal(Joint.CurrentProfile,
            Mesh->Constraints[Joint.SourceConstraintIndex]->ProfileInstance);
    if (!bChanged) return true; // Normal preparation allocates nothing and leaves solver warm starts intact.
    TArray<FProphecyJoltRigJoint> Updated = State->JointSettings;
    for (FProphecyJoltRigJoint& Joint : Updated)
        ProphecyAngularLimits::Copy(Joint.CurrentProfile,
            Mesh->Constraints[Joint.SourceConstraintIndex]->ProfileInstance);
    const FProphecyJoltWorldStatus Result = State->WorldOwner->UpdateRigAngularLimits(State->RigHandle, Updated);
    if (!Result.IsSuccess()) return Fail(OutError, Result.Message);
    State->JointSettings = MoveTemp(Updated);
    return true;
}

bool UProphecyJoltCharacterComponent::ValidateSelfCollisionSource(FString& OutError) const
{
    OutError.Reset();
    if (!IsInGameThread() || !IsJoltPhysical() || IsSteppingStopped() || !StillOwnsRig(*State))
    { OutError = TEXT("Self-collision controls require this character's healthy live Jolt rig on the game thread."); return false; }
    const USkeletalMeshComponent* Mesh = State->Mesh.Get();
    if (!Mesh || !Mesh->IsRegistered() || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get()
        || !State->PhysicsAsset.IsValid() || Mesh->GetPhysicsAsset() != State->PhysicsAsset.Get())
    { OutError = TEXT("The bound mesh/PHAT changed; disable and rebind Jolt before changing self-collision."); return false; }
    return true;
}

bool UProphecyJoltCharacterComponent::SetBodiesPhysicalMaterialOverride(
    TConstArrayView<FName> BodyBones, UPhysicalMaterial* Material, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || !IsJoltPhysical() || IsSteppingStopped() || !StillOwnsRig(*State))
    { OutError = TEXT("Material overrides require this character's healthy live Jolt rig on the game thread."); return false; }
    const auto* Mesh = State->Mesh.Get();
    if (!Mesh || !Mesh->IsRegistered() || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get()
        || !State->PhysicsAsset.IsValid() || Mesh->GetPhysicsAsset() != State->PhysicsAsset.Get())
    { OutError = TEXT("The bound mesh/PHAT changed; disable and rebind Jolt before changing materials."); return false; }
    if (BodyBones.IsEmpty() || (Material && !IsValid(Material)))
    { OutError = TEXT("Select at least one PHAT body bone and a valid material (None restores originals)."); return false; }
    FProphecyJoltBodyMaterial Override;
    if (Material)
    {
        Override.Friction = Material->Friction; Override.Restitution = Material->Restitution;
        Override.FrictionCombineMode = uint8(Material->bOverrideFrictionCombineMode
            ? Material->FrictionCombineMode.GetValue() : UPhysicsSettings::Get()->FrictionCombineMode.GetValue());
        Override.RestitutionCombineMode = uint8(Material->bOverrideRestitutionCombineMode
            ? Material->RestitutionCombineMode.GetValue() : UPhysicsSettings::Get()->RestitutionCombineMode.GetValue());
    }
    TArray<FProphecyJoltMaterialUpdate, TInlineAllocator<8>> Updates;
    TArray<int32, TInlineAllocator<8>> Indices;
    for (FName Bone : BodyBones)
    {
        const int32 Index = State->BodyNames.IndexOfByKey(Bone);
        if (!State->Handles.IsValidIndex(Index) || !State->OriginalBodyMaterials.IsValidIndex(Index))
        { OutError = FString::Printf(TEXT("'%s' is not a PHAT body bone in this Jolt rig; no materials changed."), *Bone.ToString()); return false; }
        if (Indices.Contains(Index)) continue;
        Indices.Add(Index);
        Updates.Add({State->Handles[Index], Material ? Override : State->OriginalBodyMaterials[Index]});
    }
    const auto Result = State->WorldOwner->UpdateBodyMaterials(Updates);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::SetSelfCollisionEnabled(bool bEnabled, FString& OutError)
{
    if (!ValidateSelfCollisionSource(OutError)) return false;
    const FProphecyJoltWorldStatus Result = State->WorldOwner->SetRigSelfCollisionEnabled(State->RigHandle, bEnabled);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::SetBodiesSelfCollisionEnabled(
    TConstArrayView<FName> BodyBones, bool bEnabled, FString& OutError)
{
    if (!ValidateSelfCollisionSource(OutError)) return false;
    if (BodyBones.IsEmpty())
    { OutError = TEXT("Select at least one PHAT body bone for self-collision."); return false; }
    TArray<int32> Indices;
    Indices.Reserve(BodyBones.Num());
    for (FName Bone : BodyBones)
    {
        const int32 Index = State->BodyNames.IndexOfByKey(Bone);
        if (Index == INDEX_NONE)
        { OutError = FString::Printf(TEXT("'%s' is not a PHAT body bone in this Jolt rig."), *Bone.ToString()); return false; }
        Indices.AddUnique(Index);
    }
    const FProphecyJoltWorldStatus Result = State->WorldOwner->SetRigBodiesSelfCollisionEnabled(State->RigHandle, Indices, bEnabled);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::SetSelfCollisionBelow(
    FName BoneName, bool bEnabled, bool bIncludeSelf, FString& OutError)
{
    if (!ValidateSelfCollisionSource(OutError)) return false;
    const int32 Root = State->SkeletonNames.IndexOfByKey(BoneName);
    if (Root == INDEX_NONE)
    { OutError = FString::Printf(TEXT("'%s' is not a bone in the bound skeleton."), *BoneName.ToString()); return false; }
    TArray<int32> Indices;
    for (int32 BodyIndex = 0; BodyIndex < State->BodyNames.Num(); ++BodyIndex)
    {
        int32 BoneIndex = State->SkeletonNames.IndexOfByKey(State->BodyNames[BodyIndex]);
        if (!bIncludeSelf && BoneIndex == Root) continue;
        while (BoneIndex != INDEX_NONE && BoneIndex != Root) BoneIndex = State->Parents[BoneIndex];
        if (BoneIndex == Root) Indices.Add(BodyIndex);
    }
    if (Indices.IsEmpty())
    { OutError = TEXT("The selected skeletal subtree contains no PHAT bodies with this Include Self setting."); return false; }
    const FProphecyJoltWorldStatus Result = State->WorldOwner->SetRigBodiesSelfCollisionEnabled(State->RigHandle, Indices, bEnabled);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::SetBodyPairSelfCollisionEnabled(
    FName Bone1, FName Bone2, bool bEnabled, FString& OutError)
{
    if (!ValidateSelfCollisionSource(OutError)) return false;
    const int32 Index1 = State->BodyNames.IndexOfByKey(Bone1);
    const int32 Index2 = State->BodyNames.IndexOfByKey(Bone2);
    if (Index1 == INDEX_NONE || Index2 == INDEX_NONE || Index1 == Index2)
    { OutError = TEXT("Select two distinct PHAT body bone names in this Jolt rig."); return false; }
    const FProphecyJoltWorldStatus Result = State->WorldOwner->SetRigBodyPairSelfCollisionEnabled(
        State->RigHandle, Index1, Index2, bEnabled);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::ResetSelfCollision(FString& OutError)
{
    if (!ValidateSelfCollisionSource(OutError)) return false;
    const FProphecyJoltWorldStatus Result = State->WorldOwner->ResetRigSelfCollision(State->RigHandle);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::GetBodyPairSelfCollisionEnabled(
    FName Bone1, FName Bone2, bool& bOutEnabled, FString& OutError) const
{
    bOutEnabled = false;
    if (!ValidateSelfCollisionSource(OutError)) return false;
    const int32 Index1 = State->BodyNames.IndexOfByKey(Bone1);
    const int32 Index2 = State->BodyNames.IndexOfByKey(Bone2);
    if (Index1 == INDEX_NONE || Index2 == INDEX_NONE || Index1 == Index2)
    { OutError = TEXT("Select two distinct PHAT body bone names in this Jolt rig."); return false; }
    const FProphecyJoltWorldStatus Result = State->WorldOwner->ReadRigBodyPairSelfCollisionEnabled(
        State->RigHandle, Index1, Index2, bOutEnabled);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltCharacterComponent::ConsumeCompletedWorldStep(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || !IsJoltPhysical() || IsSteppingStopped() || !StillOwnsRig(*State))
        return Fail(OutError, IsSteppingStopped() ? LastError : TEXT("Completed pose consumption requires live owned rig state."));
    FProphecyJoltWorldDiagnostics Diagnostics;
    const FProphecyJoltWorldStatus Read = State->WorldOwner->GetDiagnostics(Diagnostics);
    if (!Read.IsSuccess()) return Fail(OutError, Read.Message);
    if (State->ExpectedWorldSteps == MAX_uint64 || Diagnostics.CompletedSteps != State->ExpectedWorldSteps + 1)
        return Fail(OutError, TEXT("Every shared world step must be consumed exactly once by each registered character."));
    State->ExpectedWorldSteps = Diagnostics.CompletedSteps;
    State->LastStepFrame = GFrameCounter;
    if (!PublishCompletedPose(OutError)) return false;
    LastError.Reset();
    return true;
}

void UProphecyJoltCharacterComponent::LatchSteppingStopped(const FString& Error)
{
    check(IsInGameThread());
    if (!IsJoltPhysical()) return;
    if (!State->bSteppingStopped) LastError = Error;
    State->bSteppingStopped = true;
    SetComponentTickEnabled(false);
}

void UProphecyJoltCharacterComponent::DisablePhysicalAnimation()
{
    DisablePhysicalAnimationInternal(true);
}

void UProphecyJoltCharacterComponent::DisablePhysicalAnimationInternal(bool bCancelEnable)
{
    if (!IsInGameThread()) return;
    LowerFeedbackCaptures.Remove(this);
    if (bCancelEnable)
    {
        bEnableCancelled |= bEnableInProgress || IsEnablePending();
        PendingAdmissionId.Invalidate();
        if (UProphecyJoltCharacterWorldSubsystem* Coordinator = AdmissionCoordinator.Get())
            Coordinator->CancelPendingEnable(*this);
        AdmissionCoordinator.Reset();
        OnDeferredEnableCompleted.Clear();
        LastError.Reset();
    }
    if (bDisableInProgress) return;
    TWeakObjectPtr<AProphecyAgent> RestoringAgent = Cast<AProphecyAgent>(GetOwner());
    ON_SCOPE_EXIT
    {
        if (!DeferredMeshRestore && RestoringAgent.IsValid()) RestoringAgent->FinishJoltBackendRestore();
    };
    TGuardValue<bool> DisableGuard(bDisableInProgress, true);
    // Detach before any animation/delegate work. Reentrant Disable sees no binding and Enable is
    // refused until this cleanup finishes; an outer publisher can compare its old identity safely.
    auto RemovedState = MoveTemp(State);
    SetComponentTickEnabled(false);
    ProphecyAttackFists::ReleaseProxy(this);
    if (!RemovedState) return; // Pending cancellation leaves pre-admission Chaos ownership intact.
    RemovedState->bActive = false;
    if (UProphecyJoltCharacterWorldSubsystem* Coordinator = RemovedState->Coordinator.Get()) Coordinator->UnregisterCharacter(*this);
    StepRegistrationId.Invalidate();
    if (StillOwnsRig(*RemovedState))
    {
        const FProphecyJoltWorldStatus Destroyed = RemovedState->WorldOwner->DestroyRig(RemovedState->RigHandle);
        if (!Destroyed.IsSuccess()) LastError = Destroyed.Message;
    }
    if (AProphecyAgent* Agent = RemovedState->Agent.Get()) RemoveTickPrerequisiteActor(Agent);
    if (bPublishingCompletedPose)
    {
        // DestroyRig and coordinator removal above are immediate. Changing AnimInstance while its
        // finalizer is still on the stack is forbidden by UE; retain only the cleanup ownership.
        check(!DeferredMeshRestore);
        DeferredMeshRestore = MoveTemp(RemovedState);
        return;
    }
    RestoreKinematicMesh(MoveTemp(RemovedState));
}

void UProphecyJoltCharacterComponent::RestoreKinematicMesh(
    TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> RemovedState)
{
    check(IsInGameThread());
    // Keep admission/mode changes barred across every callback from class initialization and refresh.
    TGuardValue<bool> DisableGuard(bDisableInProgress, true);
    AProphecyAgent* Agent = RemovedState->Agent.Get();
    USkeletalMeshComponent* Mesh = RemovedState->Mesh.Get();
    const auto CanRestoreMesh = [&]()
    {
        return RemovedState->Agent.IsValid() && !RemovedState->Agent->IsActorBeingDestroyed()
            && RemovedState->Mesh.IsValid() && RemovedState->Mesh->IsRegistered()
            && RemovedState->Mesh->GetSkeletalMeshAsset() == RemovedState->MeshAsset.Get();
    };
    if (CanRestoreMesh())
    {
        // Direct component Disable/OnUnregister also bypasses the Agent wrapper. The guard routes
        // this request through its cached-mode-only path before any restored NN callback can run.
        if (!Agent->SetSimulationModeInternal(EProphecyAgentSimulationMode::Kinematic))
        {
            LastError = TEXT("Jolt cleanup could not restore its Agent's kinematic mode.");
            UE_LOG(LogProphecyJoltCharacter, Error, TEXT("%s"), *LastError);
            return;
        }
        Mesh->HandleExistingParallelEvaluationTask(true, true);
        if (!CanRestoreMesh()) return;
        Mesh->SetAllBodiesSimulatePhysics(false);
        if (!CanRestoreMesh()) return;
        Mesh->SetSimulatePhysics(false);
        if (!CanRestoreMesh()) return;
        Mesh->SetAllBodiesPhysicsBlendWeight(0.0f);
        Mesh->SetCollisionEnabled(RemovedState->CollisionEnabled);
        if (!CanRestoreMesh()) return;
        Mesh->PhysicsTransformUpdateMode = RemovedState->PhysicsTransformUpdate;
        Mesh->KinematicBonesUpdateType = RemovedState->KinematicUpdate;
        Mesh->bDeferKinematicBoneUpdate = RemovedState->bDeferKinematicBoneUpdate;
        Mesh->bEnableUpdateRateOptimizations = RemovedState->bUpdateRateOptimizations;
        Mesh->bPauseAnims = RemovedState->bPauseAnims;
        Mesh->bNoSkeletonUpdate = RemovedState->bNoSkeletonUpdate;
        Mesh->bForceRefpose = RemovedState->bForceRefPose;
        Mesh->SetEnableAnimation(RemovedState->bEnableAnimation);
        if (!CanRestoreMesh()) return;
        Mesh->SetDisablePostProcessBlueprint(RemovedState->bDisablePostProcess);
        if (Agent && Agent->GetAgentMesh())
            Mesh->SetRelativeTransform(Agent->GetAgentMesh()->GetRelativeTransform(), false, nullptr, ETeleportType::TeleportPhysics);
        if (!CanRestoreMesh()) return;
        Mesh->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
        if (!CanRestoreMesh()) return;
        if (UProphecyNNLocomotionAnimInstance* Anim = Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance()))
        {
            int32 PoseId = INDEX_NONE;
            float Interval = 1.0f / 30.0f;
            bool bInterpolate = true;
            if (Agent && Agent->GetNNPoseDataSource(PoseId, Interval, bInterpolate))
            {
                Anim->AgentId = PoseId;
                Anim->NNPoseIntervalSeconds = Interval;
                Anim->bInterpolateNNPose = bInterpolate;
            }
        }
        if (Agent && !Agent->IsActorBeingDestroyed() && !Agent->ApplyNNPoseKinematically(0.0f))
        {
            LastError = TEXT("Jolt removal could not restore the NN kinematic AnimInstance and pose.");
            UE_LOG(LogProphecyJoltCharacter, Error, TEXT("%s"), *LastError);
        }
        if (!CanRestoreMesh()) return;
        Mesh->SetComponentTickEnabled(RemovedState->bMeshTickEnabled);
    }
}

bool UProphecyJoltCharacterComponent::IsJoltPhysical() const { return State && State->bActive; }
bool UProphecyJoltCharacterComponent::IsSteppingStopped() const { return State && State->bSteppingStopped; }
uint64 UProphecyJoltCharacterComponent::GetRevision() const { return State ? State->Revision : 0; }

bool UProphecyJoltCharacterComponent::SampleCompletedComponentPose(TConstArrayView<FName> BoneNames,
    TArrayView<FTransform> OutTransforms) const
{
    if (!IsInGameThread() || !IsJoltPhysical() || BoneNames.Num() != OutTransforms.Num()) return false;
    const AProphecyAgent* Agent = State->Agent.Get();
    const USkeletalMeshComponent* Mesh = State->Mesh.Get();
    if (!Agent || !Mesh || !Mesh->IsRegistered() || State->Revision == 0) return false;
    const USceneComponent* Reference = Agent->GetAgentMesh() && Agent->GetAgentMesh()->IsRegistered()
        ? Agent->GetAgentMesh() : Mesh;
    // Feedback is in the same inherited AgentMesh frame used by SampleActualComponentPose, even when
    // the PhysicalMesh/component has moved since the completed world-space snapshot was produced.
    State->FeedbackNameLookup.Update(State->SkeletonNames, BoneNames);
    const TArray<int32>& Indices = State->FeedbackNameLookup.GetIndices();
    for (const int32 Index : Indices)
        if (!State->Completed.WorldTransforms.IsValidIndex(Index)) return false;
    for (int32 Index = 0; Index < BoneNames.Num(); ++Index)
        OutTransforms[Index] = State->Completed.WorldTransforms[Indices[Index]]
            .GetRelativeTransform(Reference->GetComponentTransform());
    return true;
}

bool UProphecyJoltCharacterComponent::SampleCompletedLowerFeedbackPose(TConstArrayView<FName> BoneNames,
    const FTransform& Reference, TArrayView<FTransform> OutActual, TArrayView<FTransform> OutAuthored) const
{
    if (!IsInGameThread() || !IsJoltPhysical() || IsSteppingStopped()
        || BoneNames.Num() != OutActual.Num() || BoneNames.Num() != OutAuthored.Num()) return false;
    auto& Capture = LowerFeedbackCaptures.FindOrAdd(this);
    bool bSame = Capture.Binding == State.Get() && Capture.Names.Num() == BoneNames.Num();
    for (int32 I = 0; bSame && I < BoneNames.Num(); ++I) bSame = Capture.Names[I] == BoneNames[I];
    if (!bSame)
    {
        Capture = {};
        Capture.Binding = State.Get();
        Capture.Names.Append(BoneNames.GetData(), BoneNames.Num());
        for (const FName Name : BoneNames)
        {
            const int32 Bone = State->SkeletonNames.IndexOfByKey(Name);
            if (Bone == INDEX_NONE) { Capture = {}; return false; }
            Capture.Bones.Add(Bone);
            auto& Chain = Capture.LocalChains.AddDefaulted_GetRef();
            int32 Ancestor = Bone;
            int32 Body = State->BodyNames.IndexOfByKey(Name);
            while (Body == INDEX_NONE && Ancestor != INDEX_NONE)
            {
                Chain.Add(Ancestor);
                Ancestor = State->Parents[Ancestor];
                if (Ancestor != INDEX_NONE) Body = State->BodyNames.IndexOfByKey(State->SkeletonNames[Ancestor]);
            }
            if (Body == INDEX_NONE) { Capture = {}; return false; }
            Capture.Bodies.Add(Body);
        }
        Capture.AuthoredWorld.SetNum(BoneNames.Num());
        return false;
    }
    if (Capture.Revision != State->Revision || State->Revision == 0) return false;
    for (int32 I = 0; I < BoneNames.Num(); ++I)
    {
        if (!State->Completed.WorldTransforms.IsValidIndex(Capture.Bones[I])) return false;
        OutActual[I] = State->Completed.WorldTransforms[Capture.Bones[I]].GetRelativeTransform(Reference);
        OutAuthored[I] = Capture.AuthoredWorld[I].GetRelativeTransform(Reference);
    }
    return true;
}

void UProphecyJoltCharacterComponent::SetHitEventsEnabled(bool bEnabled)
{
    if (State && State->WorldOwner.IsValid() && State->Mesh.IsValid())
        State->WorldOwner->SetRigHitEvents(State->RigHandle, State->Mesh.Get(), bEnabled);
}

bool UProphecyJoltCharacterComponent::GetRigIdentityBody(FProphecyJoltBodyHandle& OutHandle) const
{
    OutHandle={};
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State) || State->Handles.IsEmpty()) return false;
    OutHandle=State->Handles[0];return true;
}

bool UProphecyJoltCharacterComponent::GetBodyHandle(FName BoneName, FProphecyJoltBodyHandle& OutHandle) const
{
    OutHandle = {};
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State)) return false;
    const int32 Index = State->BodyNames.IndexOfByKey(BoneName);
    if (!State->Handles.IsValidIndex(Index)) return false;
    OutHandle = State->Handles[Index];
    return true;
}

double UProphecyJoltCharacterComponent::GetCapturedBodyMassKg(FName BoneName) const
{
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State)) return 0;
    const int32 Index = State->BodyNames.IndexOfByKey(BoneName);
    return State->CapturedBodyMassesKg.IsValidIndex(Index) ? State->CapturedBodyMassesKg[Index] : 0;
}

bool UProphecyJoltCharacterComponent::ReadPoseErrorBody(FName BoneName, int32& OutBodyIndex,
    double& OutMassKg, FTransform& OutBodyWorld) const
{
    OutBodyIndex = INDEX_NONE;
    OutMassKg = 0.0;
    OutBodyWorld = FTransform::Identity;
    if (!IsInGameThread() || !IsJoltPhysical() || IsSteppingStopped() || !StillOwnsRig(*State)) return false;
    const int32 Index = State->BodyNames.IndexOfByKey(BoneName);
    if (!State->Handles.IsValidIndex(Index) || !State->CapturedBodyMassesKg.IsValidIndex(Index)) return false;
    FProphecyJoltBodyState Body;
    if (!State->WorldOwner->ReadBody(State->Handles[Index], Body).IsSuccess() || !Body.bDynamic) return false;
    // Keep the original API's body-origin-versus-presented-target error, not COM or skinned-bone error.
    OutBodyIndex = Index;
    OutMassKg = State->CapturedBodyMassesKg[Index];
    OutBodyWorld = FTransform(Body.Rotation, Body.PositionCm);
    return true;
}

bool UProphecyJoltCharacterComponent::GetBodyState(FName BoneName, FTransform& OutBodyWorld,
    FVector& OutLinearVelocity, FVector& OutAngularVelocity, bool& bOutSimulating) const
{
    OutBodyWorld = FTransform::Identity;
    OutLinearVelocity = OutAngularVelocity = FVector::ZeroVector;
    bOutSimulating = false;
    FProphecyJoltBodyHandle Handle;
    if (!GetBodyHandle(BoneName, Handle)) return false;
    FProphecyJoltBodyState Body;
    if (!State->WorldOwner->ReadBody(Handle, Body).IsSuccess()) return false;
    OutBodyWorld = FTransform(Body.Rotation, Body.PositionCm);
    OutLinearVelocity = Body.CenterOfMassVelocityCmPerSecond;
    OutAngularVelocity = Body.AngularVelocityRadiansPerSecond;
    bOutSimulating = Body.bDynamic;
    return true;
}

bool UProphecyJoltCharacterComponent::MakeHitResult(const FProphecyJoltRayHit& Hit, FHitResult& OutHit) const
{
    OutHit = FHitResult();
    if (!IsInGameThread() || !IsJoltPhysical() || !StillOwnsRig(*State)
        || Hit.PositionCm.ContainsNaN() || Hit.Normal.ContainsNaN() || !FMath::IsFinite(Hit.Fraction)
        || Hit.Fraction < 0.0f || Hit.Fraction > 1.0f) return false;
    AProphecyAgent* Agent = State->Agent.Get();
    USkeletalMeshComponent* Mesh = State->Mesh.Get();
    if (!Agent || !Mesh || !Mesh->IsRegistered() || Mesh->GetSkeletalMeshAsset() != State->MeshAsset.Get()) return false;
    for (int32 Index = 0; Index < State->Handles.Num(); ++Index)
    {
        const FProphecyJoltBodyHandle& Handle = State->Handles[Index];
        if (Handle.WorldLifetime != Hit.Handle.WorldLifetime || Handle.Slot != Hit.Handle.Slot
            || Handle.Generation != Hit.Handle.Generation) continue;
        FProphecyJoltBodyState Body;
        if (!State->WorldOwner->ReadBody(Handle, Body).IsSuccess()) return false;
        OutHit = FHitResult(Agent, Mesh, Hit.PositionCm, Hit.Normal);
        OutHit.bBlockingHit = true;
        OutHit.Time = Hit.Fraction;
        OutHit.Location = OutHit.ImpactPoint = Hit.PositionCm;
        OutHit.Normal = OutHit.ImpactNormal = Hit.Normal;
        OutHit.Distance = 0.0f; // This result has no source ray segment from which to compute a distance.
        OutHit.FaceIndex = INDEX_NONE;
        // CaptureLiveRig/ValidateSnapshot guarantee descriptor order equals the source PHAT body index.
        OutHit.Item = Index;
        OutHit.BoneName = State->BodyNames[Index];
        return true;
    }
    return false;
}

void UProphecyJoltCharacterComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    ProphecyKickFootLeeway::Remove(Cast<AProphecyAgent>(GetOwner()));
    ProphecyLimbCollision::Remove(Cast<AProphecyAgent>(GetOwner()));
    ProphecyJointDamping::Remove(Cast<AProphecyAgent>(GetOwner()));
    DisablePhysicalAnimation();
    Super::EndPlay(EndPlayReason);
}

void UProphecyJoltCharacterComponent::OnUnregister()
{
    DisablePhysicalAnimation();
    Super::OnUnregister();
}
