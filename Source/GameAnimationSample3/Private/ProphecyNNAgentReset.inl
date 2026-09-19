// Event-only reset implementation, included at the end of the manager translation unit.
// Kept outside FImpl/FAgent so Live Coding does not resize existing native allocations.
#include "ProphecyJoltStandardPhysicsLibrary.h"
#include "GameFramework/PawnMovementComponent.h"

namespace ProphecyNNAgentReset
{
struct FComponent
{
    TWeakObjectPtr<USceneComponent> Component;
    FTransform World;
};
struct FCheckpoint
{
    TWeakObjectPtr<AProphecyAgent> Actor;
    FProphecyAgentHandle Handle;
    FVector3f Root;
    float Yaw = 0;
    bool bWalk = true;
    float Lower[StateDim]{};
    float Upper[UpperStateDim]{};
    TArray<FComponent> Components;
};
static TMap<TWeakObjectPtr<AProphecyNNLocomotionManager>, TArray<FCheckpoint>> Checkpoints;

static void ClearMotion(AProphecyNNLocomotionManager::FImpl::FAgent& A, const FCheckpoint& S, float Step)
{
    A.CurRootPos = A.PrevRootPos = A.PublishedRoot = A.PreviousPublishedRoot = S.Root;
    A.CurRootYaw = A.PrevRootYaw = A.PublishedYaw = A.PreviousPublishedYaw = S.Yaw;
    A.MoverState = {};
    A.MoverState.position = {S.Root.X, S.Root.Z};
    A.MoverState.yaw_radians = A.MoverState.previous_yaw_radians = S.Yaw;
    A.MoverIntent.speed_amplitude = 0.;
    A.MoverIntent.speed_direction_radians = 0.;
    A.MoverIntent.orientation_yaw_radians = S.Yaw;
    A.MoverIntent.mode = S.bWalk ? prophecy::sim::LocomotionMode::Walk : prophecy::sim::LocomotionMode::Run;
    A.FedInputRoot = A.WindowPreviousRoot = S.Root;
    A.FedInputYaw = A.WindowPreviousYaw = S.Yaw;
    A.WindowVerticalVelocity = 0.; A.WindowStepSeconds = Step;
    for (int32 I = 0; I < FutureWindow; ++I)
    { A.FedFutureRootPositions[I] = S.Root; A.FedFutureRootYaws[I] = S.Yaw; }
    A.bHasFedFutureRoots = true;
    A.bHasAppliedVisualRoot = true;
    A.bPhysicalWorldBlockedPending = A.bHasPhysicalSample = false;
    A.bHasBridgeActualRoot = A.bHasBridgeIntent = false;
    A.LastBridgeActualRoot = S.Root; A.LastBridgePublishSeconds = 0.;
    A.PinProbability = FVector2f::ZeroVector;
    A.bUseWalkPolicy = A.bPublishedUseWalkPolicy = A.bPreviousPublishedUseWalkPolicy = S.bWalk;
    A.PolicyBlend.Reset(S.bWalk);
    A.PublishedWalkWeight = A.PreviousPublishedWalkWeight = A.PolicyBlend.WalkWeight;
    A.AnimationLayer.Reset();
    A.Slash = {};
}
}

int32 AProphecyNNLocomotionManager::CaptureInitialAgentResetState(FString& Error)
{
    using namespace ProphecyNNAgentReset;
    Error.Reset();
    if (!IsInGameThread() || !Impl || !Impl->bInitialized || IsSimBridgeActive())
    { Error = TEXT("Reset capture needs an initialized native NN manager (standalone Sim Bridge must be off)."); return 0; }
    if (const auto* Existing = Checkpoints.Find(this)) return Existing->Num();
    TArray<FCheckpoint> Captured;
    for (int32 I = 0; I < AgentActors.Num(); ++I)
    {
        auto* Actor = AgentActors[I].Get();
        if (!IsValid(Actor) || !Impl->Agents.IsValidIndex(I)) continue;
        const auto& A = Impl->Agents[I];
        if (A.Slash.bActive || A.DefensePose || A.AnimationLayer.IsActive())
        { Error = TEXT("Capture the initial reset state before attacks, defense or animation layers start."); return 0; }
        auto& S = Captured.AddDefaulted_GetRef();
        S.Actor = Actor; S.Handle = Actor->GetAgentHandle();
        S.Root = A.PublishedRoot; S.Yaw = A.PublishedYaw; S.bWalk = A.bPublishedUseWalkPolicy;
        FMemory::Memcpy(S.Lower, StateSlice(Impl->PublishedStateBuffer, I), sizeof(S.Lower));
        FMemory::Memcpy(S.Upper, UpperStateSlice(Impl->UpperPublishedStateBuffer, I), sizeof(S.Upper));
        TInlineComponentArray<USceneComponent*> Components(Actor);
        for (auto* Component : Components)
        {
            // Skeleton pose comes from NN state; camera/capsule follow their normal hierarchy.
            // Retain authored auxiliary primitives too (including the user's magic cube).
            if (!IsValid(Component) || Component == Actor->GetRootComponent()
                || Component->IsA<USkeletalMeshComponent>() || !Component->IsA<UPrimitiveComponent>()) continue;
            S.Components.Add({Component, Component->GetComponentTransform()});
        }
    }
    const int32 Count = Captured.Num();
    if (Count) Checkpoints.Add(this, MoveTemp(Captured));
    return Count;
}

void AProphecyNNLocomotionManager::ClearInitialAgentResetState()
{
    ProphecyNNAgentReset::Checkpoints.Remove(this);
}

int32 AProphecyNNLocomotionManager::RestoreInitialAgentResetState(FString& Error)
{
    using namespace ProphecyNNAgentReset;
    Error.Reset();
    const auto* Stored = Checkpoints.Find(this);
    if (!IsInGameThread() || !Stored || !Impl || !Impl->bInitialized || IsSimBridgeActive())
    { Error = TEXT("No usable native NN reset checkpoint."); return 0; }
    const auto Captured = *Stored; // Survives callbacks/world cleanup while rebinding physics.
    int32 Restored = 0;
    const float Step = 1.f / FMath::Max(1.f, NNUpdateHz);
    for (const auto& S : Captured)
    {
        AProphecyAgent* Actor = S.Actor.Get();
        if (!IsValid(Actor) || Actor->IsActorBeingDestroyed() || ResolveAgent(S.Handle) != Actor) continue;
        const int32 I = S.Handle.Index;
        if (!Impl->Agents.IsValidIndex(I)) continue;
        const auto Mode = Actor->GetSimulationMode();
        if (auto* Mesh = Actor->GetPoseReferenceMesh())
        {
            UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsLinearVelocity(Mesh, FVector::ZeroVector, false);
            UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsAngularVelocityInRadians(Mesh, FVector::ZeroVector, false);
        }
        // Recreate the rig at the restored authored pose: clears native velocities, contact/
        // constraint warm starts and completed feedback snapshots together. Reset is infrequent.
        if (!Actor->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))
        { Error += FString::Printf(TEXT("%s could not leave physics; "), *Actor->GetName()); continue; }
        StopAgentNNDefense(S.Handle);
        StopAgentNNAttack(S.Handle);
        ProphecyAttackRecovery::Cancel(Actor);
        if (!IsValid(Actor) || Actor->IsActorBeingDestroyed() || ResolveAgent(S.Handle) != Actor) continue;
        Actor->StopLocomotionInput();
        Actor->ConsumeMovementInputVector();
        if (auto* Movement = Actor->GetMovementComponent()) Movement->StopMovementImmediately();
        ProphecyRootMagic::Remove(Actor); // Both independent sets, including cancelling values.
        RootYawImpulseAgents.Remove(Actor);
        RootImpulseSmoothingYaw.Remove(Actor);
        ProphecyRootFacing::Explicit(Actor);
        ProphecyRootBalance::ResetMotion(Actor);
        ProphecyPelvisInertia::ResetMotion(Actor);
        ProphecyHandInertia::ResetMotion(Actor);
        if (auto* W = ProphecyNNRootWindow::Find(Actor))
        {
            const FVector Factors = W->Factors;
            *W = {}; W->Factors = Factors;
            // A zero-smoothed window must remain collapsed after resetting.
            for (auto& Sample : W->Samples) Sample.bInitialized = true;
        }
        auto& A = Impl->Agents[I];
        ClearMotion(A, S, Step);
        A.DefensePose = nullptr;
        auto CopyLower = [&](TArray<float>& Buffer) { FMemory::Memcpy(StateSlice(Buffer, I), S.Lower, sizeof(S.Lower)); };
        CopyLower(Impl->PrevStateBuffer); CopyLower(Impl->CurStateBuffer); CopyLower(Impl->NextStateBuffer);
        CopyLower(Impl->PublishedStateBuffer); CopyLower(Impl->PreviousPublishedStateBuffer);
        CopyLower(Impl->PhysicalStateBuffer); CopyLower(Impl->PreviousPhysicalStateBuffer);
        auto CopyUpper = [&](TArray<float>& Buffer) { FMemory::Memcpy(UpperStateSlice(Buffer, I), S.Upper, sizeof(S.Upper)); };
        CopyUpper(Impl->UpperPreviousStateBuffer); CopyUpper(Impl->UpperCurrentStateBuffer);
        CopyUpper(Impl->UpperPreviousPublishedStateBuffer); CopyUpper(Impl->UpperPublishedStateBuffer);
        CopyUpper(Impl->UpperPhysicalStateBuffer); CopyUpper(Impl->UpperPreviousPhysicalStateBuffer);
        BuildUpperBaseFromLower(S.Lower, *Impl, UpperStateSlice(Impl->UpperCurrentBaseBuffer, I));
        BuildUpperBaseFromLower(S.Lower, *Impl, UpperStateSlice(Impl->UpperNextBaseBuffer, I));
        LowerTransformToHeading(S.Lower, 0, 3, *Impl, TransformStateSlice(Impl->PreviousPelvisHeadingBuffer, I));
        LowerTransformToHeading(S.Lower, 0, 3, *Impl, TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, I));
        FMemory::Memzero(Impl->InputBuffer.GetData() + I * InputDim, InputDim * sizeof(float));
        float* Input = Impl->InputBuffer.GetData() + I * InputDim;
        FMemory::Memcpy(Input, S.Lower, sizeof(S.Lower));
        FMemory::Memcpy(Input + StateDim, S.Lower, sizeof(S.Lower));
        for (int32 R = 0; R < FutureWindow; ++R) Input[120 + R * 4 + 2] = 1.f;
        if (auto* Targets = ResolvedMoverTargets.Find(this); Targets && Targets->IsValidIndex(I))
        { (*Targets)[I] = {}; (*Targets)[I].Target.orientation_yaw_radians = S.Yaw; }
        if (auto* Debug = Impl->PinningDebug.Find(I)) { Debug->Locomotion = {}; Debug->Attack = {}; Debug->Frozen = {}; }
        Actor->TeleportManagedRootLowPoint(TrainingToUnreal(S.Root), -FMath::RadiansToDegrees(S.Yaw));
        const int32 PoseId = PoseStoreAgentBase + I;
        FProphecyNNPoseStore::ClearAgentPose(PoseId); // Remove old Hermite tangents/presentation history.
        FProphecyNNPoseStore::SetInterpolationMode(PoseId, Actor->GetNNInterpolationMode());
        PublishAgentPose(I, GetWorld()->GetTimeSeconds());
        ProphecyNNPresentation::Publish(PoseId, A.PublishedPoseTimeSeconds, 1.f);
        ProphecyPhysicalContext::Update(Actor);
        if (auto* Mesh = Actor->GetPoseReferenceMesh())
        {
            Mesh->TickAnimation(0.f, false); Mesh->RefreshBoneTransforms();
            // Jolt admission captures the native Chaos source bodies, including stored velocity.
            // Clear that source as well, not just the old Jolt rig that was retired above.
            Mesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector, false);
            Mesh->SetAllPhysicsAngularVelocityInRadians(FVector::ZeroVector, false);
        }
        for (const auto& C : S.Components)
        {
            if (!C.Component.IsValid()) continue;
            FHitResult Hit;
            UProphecyJoltStandardPhysicsLibrary::K2_SetWorldTransform(C.Component.Get(), C.World, false, Hit, true);
            if (auto* Primitive = Cast<UPrimitiveComponent>(C.Component.Get()))
            {
                UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsLinearVelocity(Primitive, FVector::ZeroVector, false);
                UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsAngularVelocityInRadians(Primitive, FVector::ZeroVector, false);
            }
        }
        if (!Actor->SetSimulationMode(Mode)) Error += FString::Printf(TEXT("%s reset but could not restore simulation mode; "), *Actor->GetName());
        ++Restored;
    }
    if (!Impl->PreviousPoseDebugAgents.IsEmpty()) UpdatePreviousPoseDebug(false);
    return Restored;
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAgentResetMotionTest,
    "Prophecy.NN.AgentReset.MotionAndWindow", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyAgentResetMotionTest::RunTest(const FString&)
{
    using namespace ProphecyNNAgentReset;
    FCheckpoint S; S.Root = FVector3f(15.f, 2.f, -8.f); S.Yaw = 1.2f; S.bWalk = true;
    AProphecyNNLocomotionManager::FImpl::FAgent A;
    A.UpperRootRotationHorizon = .42f;
    A.PhysicalFeedbackTolerances.FindOrAdd(TEXT("foot_r")).LinearCm = 3.f;
    for (int32 Repeat = 0; Repeat < 3; ++Repeat)
    {
        A.MoverState.velocity = {14., -5.};
        A.MoverState.yaw_radians = 50.; A.MoverState.previous_yaw_radians = 45.;
        A.MoverIntent.speed_amplitude = 1.; A.MoverIntent.orientation_yaw_radians = 90.;
        A.WindowVerticalVelocity = 4.; A.Slash.bActive = true;
        A.bHasPhysicalSample = true; A.bPhysicalWorldBlockedPending = true;
        ClearMotion(A, S, 1.f/30.f);
        TestTrue(TEXT("root and previous root restored"), A.CurRootPos == S.Root && A.PrevRootPos == S.Root);
        TestTrue(TEXT("linear motion cleared"), A.MoverState.velocity.x == 0. && A.MoverState.velocity.z == 0.);
        TestTrue(TEXT("yaw velocity and spring target reset"), A.MoverState.previous_yaw_radians == A.MoverState.yaw_radians
            && A.MoverIntent.orientation_yaw_radians == A.MoverState.yaw_radians);
        TestTrue(TEXT("inputs/transient flags cleared"), A.MoverIntent.speed_amplitude == 0. && A.WindowVerticalVelocity == 0.
            && !A.bHasPhysicalSample && !A.bPhysicalWorldBlockedPending && !A.Slash.bActive);
        for (int32 I = 0; I < FutureWindow; ++I)
            TestTrue(TEXT("every future root collapsed at restored root"), A.FedFutureRootPositions[I] == S.Root && A.FedFutureRootYaws[I] == S.Yaw);
        TestEqual(TEXT("horizon tuning preserved"), A.UpperRootRotationHorizon, .42f);
        TestEqual(TEXT("feedback tuning preserved"), A.PhysicalFeedbackTolerances[TEXT("foot_r")].LinearCm, 3.f);
    }
    return true;
}
#endif
