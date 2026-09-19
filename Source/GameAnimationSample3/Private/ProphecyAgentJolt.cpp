#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecySwordComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "ProphecyAngularLimits.h"
#include "ProphecySpecialSolver.h"

namespace ProphecySpecialSolver
{
struct FState { bool Attack=false, Defense=false; };
// Event-owned state preserves existing live UObject/native layouts. Locomotion has no entry.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
bool IsActive(const AProphecyAgent* Agent) { return !States.IsEmpty() && States.Contains(Agent); }
void Remove(const AProphecyAgent* Agent) { States.Remove(Agent); }
static void Change(AProphecyAgent* Agent,bool Defense,bool Active)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return;
    const bool WasActive=IsActive(Agent);
    if (!WasActive && !Active) return;
    auto& State=States.FindOrAdd(Agent);
    (Defense ? State.Defense : State.Attack)=Active;
    const bool NowActive=State.Attack || State.Defense;
    if (!NowActive) States.Remove(Agent);
    if (WasActive==NowActive || !Agent->IsJoltPhysicalAnimationEnabled()) return;
    int32 Velocity,Position; Agent->GetJoltSolverIterations(Velocity,Position);
    FString Error;
    if (!Agent->GetJoltCharacterComponent()->SetSolverIterations(Velocity,Position,Error))
        UE_LOG(LogTemp,Error,TEXT("Special solver transition failed on %s: %s"),*Agent->GetName(),*Error);
}
void AttackChanged(AProphecyAgent* Agent,bool Active) { Change(Agent,false,Active); }
void DefenseChanged(AProphecyAgent* Agent,bool Active) { Change(Agent,true,Active); }
}

namespace
{
bool ApplyParentJointLimits(AProphecyAgent& Agent, FName ChildBone,
    const FConstraintProfileProperties* Requested, FString& Error)
{
    Error.Reset();
    if (!IsInGameThread() || Agent.IsActorBeingDestroyed())
    { Error = TEXT("Joint limit changes require a live agent on the game thread."); return false; }
    USkeletalMeshComponent* Mesh = Agent.GetPoseReferenceMesh();
    if (!IsValid(Mesh)) { Error = TEXT("No PhysicalMesh is available."); return false; }
    TArray<FConstraintProfileProperties> Profiles;
    int32 Index = INDEX_NONE;
    if (!ProphecyAngularLimits::PrepareParentJoint(*Mesh, ChildBone, Profiles, Index, Error)) return false;
    const auto& Limits = Requested ? *Requested
        : Mesh->GetPhysicsAsset()->ConstraintSetup[Index]->DefaultInstance.ProfileInstance;
    ProphecyAngularLimits::Copy(Profiles[Index], Limits);
    if (Agent.IsJoltPhysicalAnimationEnabled())
        return Agent.GetJoltCharacterComponent()->ApplyAngularLimitProfiles(Profiles, Error);
    if (!ProphecyAngularLimits::Equal(Mesh->Constraints[Index]->ProfileInstance, Profiles[Index]))
    {
        ProphecyAngularLimits::Apply(*Mesh->Constraints[Index], Profiles[Index]);
        Mesh->WakeAllRigidBodies();
    }
    return true;
}
}

void AProphecyAgent::NotifyControllerChanged()
{
    // Update physics policy before Blueprint/controller-change listeners run.
    if (JoltCharacter) JoltCharacter->RefreshPlayerSwingLimits();
    Super::NotifyControllerChanged();
}

void AProphecyAgent::SetJoltJointLimitPredictionEnabled(bool bEnabled)
{
    if (!IsInGameThread() || IsActorBeingDestroyed() || bJoltJointLimitPredictionEnabled == bEnabled) return;
    bJoltJointLimitPredictionEnabled = bEnabled;
    if (JoltCharacter) JoltCharacter->RefreshPlayerSwingLimits();
}

bool AProphecyAgent::SetJoltCCDMode(EProphecyJoltCCDMode Mode, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || IsActorBeingDestroyed() || uint8(Mode) > uint8(EProphecyJoltCCDMode::Continuous))
    { OutError = TEXT("CCD mode requires a live agent and a valid mode on the game thread."); return false; }
    if (IsJoltPhysicalAnimationEnabled() && !JoltCharacter->SetCCDMode(uint8(Mode), OutError)) return false;
    JoltCCDMode = Mode;
    return true;
}

bool AProphecyAgent::SetJoltSolverIterations(int32 VelocityIterations, int32 PositionIterations, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || IsActorBeingDestroyed() || VelocityIterations < 0 || VelocityIterations > 128
        || PositionIterations < 0 || PositionIterations > 128)
    { OutError = TEXT("Solver iterations require a live agent and counts in 0..128; zero restores world defaults."); return false; }
    // During a special, edits configure the locomotion settings restored on exit.
    if (!ProphecySpecialSolver::IsActive(this) && IsJoltPhysicalAnimationEnabled()
        && !JoltCharacter->SetSolverIterations(VelocityIterations, PositionIterations, OutError)) return false;
    JoltVelocityIterations = VelocityIterations;
    JoltPositionIterations = PositionIterations;
    return true;
}

void AProphecyAgent::GetJoltSolverIterations(int32& VelocityIterations, int32& PositionIterations) const
{
    const bool Special=ProphecySpecialSolver::IsActive(this);
    VelocityIterations = Special ? 10 : JoltVelocityIterations;
    PositionIterations = Special ? 32 : JoltPositionIterations;
}

bool AProphecyAgent::SetPhysicalJointAngularLimits(FName ChildBone,
    EAngularConstraintMotion Swing1Motion, float Swing1LimitDegrees,
    EAngularConstraintMotion Swing2Motion, float Swing2LimitDegrees,
    EAngularConstraintMotion TwistMotion, float TwistLimitDegrees, FString& OutError)
{
    OutError.Reset();
    for (auto Motion : { Swing1Motion, Swing2Motion, TwistMotion })
        if (Motion != ACM_Free && Motion != ACM_Limited && Motion != ACM_Locked)
        { OutError = TEXT("Every angular motion must be Free, Limited or Locked."); return false; }
    for (float Angle : { Swing1LimitDegrees, Swing2LimitDegrees, TwistLimitDegrees })
        if (!FMath::IsFinite(Angle) || Angle < 0.0f || Angle > 180.0f)
        { OutError = TEXT("Every angle must be finite and within 0..180 degrees, including Free/Locked fields."); return false; }
    FConstraintProfileProperties Limits;
    Limits.ConeLimit.Swing1Motion = Swing1Motion;
    Limits.ConeLimit.Swing1LimitDegrees = Swing1LimitDegrees;
    Limits.ConeLimit.Swing2Motion = Swing2Motion;
    Limits.ConeLimit.Swing2LimitDegrees = Swing2LimitDegrees;
    Limits.TwistLimit.TwistMotion = TwistMotion;
    Limits.TwistLimit.TwistLimitDegrees = TwistLimitDegrees;
    return ApplyParentJointLimits(*this, ChildBone, &Limits, OutError);
}

bool AProphecyAgent::ResetPhysicalJointAngularLimits(FName ChildBone, FString& OutError)
{
    return ApplyParentJointLimits(*this, ChildBone, nullptr, OutError);
}

bool AProphecyAgent::SetUseAuthoredAngularLimits(bool bEnabled)
{
    if (!IsInGameThread() || IsActorBeingDestroyed()) return false;
    USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
    TArray<FConstraintProfileProperties> Profiles;
    FString Error;
    if (!PhysicalMesh || !ProphecyAngularLimits::Prepare(*PhysicalMesh, bEnabled, Profiles, Error))
    {
        UE_LOG(LogTemp, Error, TEXT("Angular-limit change failed for %s: %s"), *GetName(), *Error);
        return false;
    }
    if (IsJoltPhysicalAnimationEnabled())
    {
        if (!JoltCharacter->ApplyAngularLimitProfiles(Profiles, Error))
        {
            UE_LOG(LogTemp, Error, TEXT("Jolt angular-limit change failed for %s: %s"), *GetName(), *Error);
            return false;
        }
        return true;
    }
    for (int32 Index = 0; Index < Profiles.Num(); ++Index)
        ProphecyAngularLimits::Apply(*PhysicalMesh->Constraints[Index], Profiles[Index]);
    PhysicalMesh->WakeAllRigidBodies();
    return true;
}

bool AProphecyAgent::EnableJoltPhysicalAnimation()
{
    if (!IsInGameThread() || !bManualNNPoseApplication || !HasActorBegunPlay()) return false;
    if (JoltCharacter && JoltCharacter->IsKinematicRestorePending()) return false;
    if (JoltCharacter && JoltCharacter->IsSteppingStopped())
    {
        UE_LOG(LogTemp, Error, TEXT("Jolt character %s remains stopped; Disable then Enable to recover: %s"),
            *GetName(), *JoltCharacter->GetLastError());
        return false;
    }
    if (IsJoltPhysicalAnimationEnabled())
    {
        bUseJoltForPhysicalMode = true;
        return true;
    }
    if (JoltCharacter && JoltCharacter->IsEnablePending()) return true;
    const EProphecyAgentSimulationMode PreviousMode = GetSimulationMode();
    if (PreviousMode != EProphecyAgentSimulationMode::Physical)
    {
        // Selecting a solver must not start simulation or replace the HalfSim controller.
        bUseJoltForPhysicalMode = true;
        return true;
    }
    UProphecyJoltWorldSubsystem* JoltWorld = GetWorld() ? GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!JoltWorld || !JoltWorld->GetDiagnostics(Diagnostics).IsSuccess() || !Diagnostics.bInitialized || Diagnostics.bFaulted)
    {
        UE_LOG(LogTemp, Error, TEXT("Initialize a healthy Jolt world before enabling character %s."), *GetName());
        return false;
    }
    if (!JoltCharacter)
    {
        JoltCharacter = NewObject<UProphecyJoltCharacterComponent>(this, TEXT("JoltCharacter"));
        AddInstanceComponent(JoltCharacter);
        JoltCharacter->RegisterComponent();
    }
    const auto RestorePreviousMode = [this, PreviousMode]()
    {
        // Failed preflight retains Chaos; failed committed handoff restores a kinematic mesh.
        // Reconcile the cached mode so the normal transition cannot incorrectly early out.
        const USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
        SimulationMode = PhysicalMesh && PhysicalMesh->IsAnySimulatingPhysics()
            ? EProphecyAgentSimulationMode::Physical : EProphecyAgentSimulationMode::Kinematic;
        // Rollback restores the source controller without retrying the failed Jolt admission.
        if (SimulationMode != PreviousMode && !SetSimulationModeInternal(PreviousMode))
            UE_LOG(LogTemp, Error, TEXT("Jolt activation rollback could not restore the previous mode for %s."), *GetName());
    };
    FString Error;
    if (!JoltCharacter->EnablePhysicalAnimation(Error))
    {
        // A pose-finalization callback may explicitly cancel admission or destroy the owner.
        // Its later request wins; failure recovery must not turn its Chaos simulation back on.
        if (!IsValid(this) || IsActorBeingDestroyed() || !IsValid(JoltCharacter.Get())
            || JoltCharacter->WasEnableCancelled()) return false;
        UE_LOG(LogTemp, Error, TEXT("Jolt character enable failed for %s: %s"), *GetName(), *Error);
        RestorePreviousMode();
        return false;
    }
    if (JoltCharacter->IsEnablePending())
    {
        JoltCharacter->OnDeferredEnableCompleted.AddWeakLambda(this,
            [this, RestorePreviousMode](bool bSucceeded, const FString& DeferredError)
            {
                if (!bSucceeded)
                {
                    UE_LOG(LogTemp, Error, TEXT("Deferred Jolt character enable failed for %s: %s"), *GetName(), *DeferredError);
                    RestorePreviousMode();
                }
                else if (IsJoltPhysicalAnimationEnabled())
                {
                    // Earlier completion callbacks may explicitly disable this binding.
                    bUseJoltForPhysicalMode = true;
                }
                if (auto* Sword = FindComponentByClass<UProphecySwordComponent>()) Sword->RefreshHandConstraint();
            });
    }
    SimulationMode = EProphecyAgentSimulationMode::Physical;
    bPendingHalfSimulation = false;
    if (!JoltCharacter->IsEnablePending())
    {
        bUseJoltForPhysicalMode = true;
        if (auto* Sword = FindComponentByClass<UProphecySwordComponent>()) Sword->RefreshHandConstraint();
    }
    return true;
}

void AProphecyAgent::DisableJoltPhysicalAnimation()
{
    if (!IsInGameThread()) return;
    bUseJoltForPhysicalMode = false;
    if (JoltCharacter && JoltCharacter->IsEnablePending() && !JoltCharacter->IsJoltPhysical())
    {
        // A pending admission still belongs to Chaos; cancel it without changing that mode.
        JoltCharacter->DisablePhysicalAnimation();
        return;
    }
    if (!IsJoltPhysicalAnimationEnabled()) return;
    bResumeChaosPhysicalAfterJoltRestore = !IsActorBeingDestroyed() && HasActorBegunPlay();
    DisableJoltPhysicalAnimationForModeChange();
}

void AProphecyAgent::FinishJoltBackendRestore()
{
    if (!bResumeChaosPhysicalAfterJoltRestore) return;
    bResumeChaosPhysicalAfterJoltRestore = false;
    if (IsActorBeingDestroyed() || !HasActorBegunPlay() || bUseJoltForPhysicalMode) return;
    if (!SetSimulationModeInternal(EProphecyAgentSimulationMode::Physical))
        UE_LOG(LogTemp, Error, TEXT("Could not restore Chaos Sim after disabling Jolt for %s."), *GetName());
    if (auto* Sword = FindComponentByClass<UProphecySwordComponent>()) Sword->RefreshHandConstraint();
}

void AProphecyAgent::DisableJoltPhysicalAnimationForModeChange()
{
    if (!JoltCharacter || (!JoltCharacter->IsJoltPhysical() && !JoltCharacter->IsEnablePending())) return;
    const bool bWasPending = JoltCharacter->IsEnablePending();
    // The restored NN proxy must observe kinematic mode on its first update, including immediate cleanup.
    if (!bWasPending) SimulationMode = EProphecyAgentSimulationMode::Kinematic;
    JoltCharacter->DisablePhysicalAnimation();
    if (bWasPending)
    {
        // Admission has not taken ownership yet; perform the ordinary Chaos-to-kinematic transition.
        SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
        if (auto* Sword = FindComponentByClass<UProphecySwordComponent>()) Sword->RefreshHandConstraint();
        return;
    }
    if (auto* Sword = FindComponentByClass<UProphecySwordComponent>()) Sword->RefreshHandConstraint();
}

bool AProphecyAgent::IsJoltPhysicalAnimationEnabled() const
{
    return JoltCharacter && JoltCharacter->IsJoltPhysical();
}

UProphecyJoltCharacterComponent* AProphecyAgent::GetJoltCharacterComponent() const
{
    return JoltCharacter.Get();
}

namespace
{
UProphecyJoltCharacterComponent* GetSelfCollisionCharacter(const AProphecyAgent& Agent, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || Agent.IsActorBeingDestroyed() || !Agent.IsJoltPhysicalAnimationEnabled())
    {
        OutError = TEXT("Self-collision controls require an active Jolt character on the game thread; call after admission completes.");
        return nullptr;
    }
    return Agent.GetJoltCharacterComponent();
}
}

bool AProphecyAgent::SetJoltSelfCollisionEnabled(bool bEnabled, FString& OutError)
{
    auto* Character = GetSelfCollisionCharacter(*this, OutError);
    return Character && Character->SetSelfCollisionEnabled(bEnabled, OutError);
}

bool AProphecyAgent::SetJoltBodiesSelfCollisionEnabled(const TArray<FName>& BodyBones, bool bEnabled, FString& OutError)
{
    auto* Character = GetSelfCollisionCharacter(*this, OutError);
    return Character && Character->SetBodiesSelfCollisionEnabled(BodyBones, bEnabled, OutError);
}

bool AProphecyAgent::SetJoltSelfCollisionBelow(FName BoneName, bool bEnabled, bool bIncludeSelf, FString& OutError)
{
    auto* Character = GetSelfCollisionCharacter(*this, OutError);
    return Character && Character->SetSelfCollisionBelow(BoneName, bEnabled, bIncludeSelf, OutError);
}

bool AProphecyAgent::SetJoltBodyPairSelfCollisionEnabled(FName Bone1, FName Bone2, bool bEnabled, FString& OutError)
{
    auto* Character = GetSelfCollisionCharacter(*this, OutError);
    return Character && Character->SetBodyPairSelfCollisionEnabled(Bone1, Bone2, bEnabled, OutError);
}

bool AProphecyAgent::ResetJoltSelfCollision(FString& OutError)
{
    auto* Character = GetSelfCollisionCharacter(*this, OutError);
    return Character && Character->ResetSelfCollision(OutError);
}

bool AProphecyAgent::SetJoltBodiesPhysicalMaterialOverride(const TArray<FName>& BodyBones,
    UPhysicalMaterial* Material, FString& OutError)
{
    OutError.Reset();
    auto* Character = IsInGameThread() && !IsActorBeingDestroyed() ? GetJoltCharacterComponent() : nullptr;
    if (!Character || !IsJoltPhysicalAnimationEnabled())
    { OutError = TEXT("Material overrides require an active Jolt character; call after admission completes."); return false; }
    return Character->SetBodiesPhysicalMaterialOverride(BodyBones, Material, OutError);
}

bool AProphecyAgent::ResetJoltBodiesPhysicalMaterialOverride(const TArray<FName>& BodyBones, FString& OutError)
{
    return SetJoltBodiesPhysicalMaterialOverride(BodyBones, nullptr, OutError);
}

bool AProphecyAgent::GetJoltBodyPairSelfCollisionEnabled(FName Bone1, FName Bone2,
    bool& bOutEnabled, FString& OutError) const
{
    bOutEnabled = false;
    auto* Character = GetSelfCollisionCharacter(*this, OutError);
    return Character && Character->GetBodyPairSelfCollisionEnabled(Bone1, Bone2, bOutEnabled, OutError);
}
