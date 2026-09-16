#include "ProphecyPelvisInertiaLibrary.h"
#include "ProphecyPelvisInertia.h"
#include "ProphecyPelvisInertiaMath.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Engine/World.h"

namespace ProphecyPelvisInertia
{
struct FState
{
    FVector Linear = FVector::OneVector, Angular = FVector::OneVector;
    bool bEnabled = false, bSimulatedBody = false, bSeeded = false;
    double Time = 0., IntervalSeconds = 0.;
    FMotion Motion, IntervalStart;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Jolt;
    FProphecyJoltBodyHandle Handle;
    bool Active() const { return bEnabled && (Linear != FVector::OneVector || Angular != FVector::OneVector); }
};
// Separate state keeps existing live actor/manager layouts unchanged. No components or timers.
static TMap<TWeakObjectPtr<const AProphecyAgent>, FState> States;
static bool BodyMode(const AProphecyAgent* Agent, const FState& S)
{
    return S.bSimulatedBody && Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Physical;
}
bool HasTarget(const AProphecyAgent* Agent)
{
    auto* S = States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!S || !S->Active()) return false;
    if (BodyMode(Agent,*S)) { S->bSeeded=false; return false; }
    return true;
}
static void ClearJolt(FState& S)
{
    if (S.Handle.IsSet() && S.Jolt.IsValid())
        S.Jolt->SetBodyServoFollow(S.Handle, FVector::OneVector, FVector::OneVector);
    S.Jolt.Reset(); S.Handle = {};
}
bool GetBodyFollow(const AProphecyAgent* Agent, FVector& Linear, FVector& Angular)
{
    const auto* S=States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!S || !S->Active() || !BodyMode(Agent,*S)) return false;
    Linear=S->Linear; Angular=S->Angular; return true;
}
void Remove(const AProphecyAgent* Agent)
{
    if (auto* S = States.Find(Agent)) ClearJolt(*S);
    States.Remove(Agent);
}
void ResetMotion(const AProphecyAgent* Agent)
{
    if (auto* S = States.Find(Agent))
    { S->bSeeded = false; S->Time = S->IntervalSeconds = 0.; S->Motion = {}; S->IntervalStart = {}; }
}
void SynchronizeJolt(const AProphecyAgent* Agent)
{
    auto* S = States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!S) return;
    if (!S->Active() || !BodyMode(Agent,*S))
    { if (S->Handle.IsSet()) ClearJolt(*S); return; }
    FProphecyJoltBodyHandle Handle;
    auto* Jolt = Agent->GetJoltCharacterComponent();
    auto* World = Agent->GetWorld() ? Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Jolt || !World || !Jolt->GetBodyHandle(TEXT("pelvis"),Handle))
    { if (S->Handle.IsSet()) ClearJolt(*S); return; }
    if (S->Jolt.Get() == World && S->Handle.WorldLifetime == Handle.WorldLifetime
        && S->Handle.Slot == Handle.Slot && S->Handle.Generation == Handle.Generation) return;
    ClearJolt(*S);
    if (World->SetBodyServoFollow(Handle,S->Linear,S->Angular).IsSuccess())
    { S->Jolt=World; S->Handle=Handle; }
}
bool ApplyTarget(const AProphecyAgent* Agent, double Time, double StepSeconds,
    const FTransform& PreviousCarrier, const FTransform& Carrier,
    FTransform& PreviousPelvis, FTransform& Pelvis)
{
    auto* S = States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!S || !S->Active()) return false;
    if (BodyMode(Agent,*S)) { S->bSeeded=false; return false; }
    if (!FMath::IsFinite(Time) || !FMath::IsFinite(StepSeconds) || StepSeconds <= UE_SMALL_NUMBER) return false;
    const FTransform Target = Pelvis * Carrier;
    if (!S->bSeeded || Time < S->Time)
    {
        S->Motion.Seed(PreviousPelvis*PreviousCarrier,Target,StepSeconds);
        S->IntervalStart=S->Motion;
        S->IntervalSeconds=StepSeconds;
        S->Time=Time; S->bSeeded=true;
    }
    else if (Time > S->Time + 1.e-8)
    {
        S->IntervalStart=S->Motion;
        S->IntervalSeconds=Time-S->Time;
        S->Time=Time;
    }
    // Re-evaluate from the same start if collision rebases this interval. One-follow
    // axes receive the corrected target; zero-follow axes never integrate twice.
    S->Motion=S->IntervalStart;
    S->Motion.Step(Target,S->Linear,S->Angular,S->IntervalSeconds);
    PreviousPelvis=S->IntervalStart.World.GetRelativeTransform(PreviousCarrier);
    Pelvis=S->Motion.World.GetRelativeTransform(Carrier);
    return true;
}
bool ApplyChaosDrive(const AProphecyAgent* Agent, FName Bone, FBodyInstance* Body,
    const FTransform& Target, float Dt, float LinearScale, float AngularScale,
    bool bCancelGravity, float GravityZ)
{
    if (States.IsEmpty() || Bone != TEXT("pelvis")) return false;
    const auto* S=States.Find(Agent);
    if (!S || !S->Active() || !BodyMode(Agent,*S)) return false;
    const FTransform Actual=Body->GetUnrealWorldTransform();
    if (LinearScale>0)
    {
        FVector Acc=(Target.GetLocation()-Actual.GetLocation()-Body->GetUnrealWorldVelocity()*Dt)/FMath::Square(Dt);
        // Gravity policy stays independent of inertia; only the tracking acceleration is scaled.
        Acc*=S->Linear;
        if (bCancelGravity) Acc.Z-=GravityZ;
        Body->AddForce(Acc*LinearScale,true,true);
    }
    if (AngularScale>0)
    {
        const FVector Acc=(RotationVector(Target.GetRotation()*Actual.GetRotation().Inverse())/Dt
            -Body->GetUnrealWorldAngularVelocityInRadians())/Dt;
        Body->AddTorqueInRadians(Acc*S->Angular*AngularScale,true,true);
    }
    return true;
}
}

bool UProphecyPelvisInertiaLibrary::SetPelvisInertia(AProphecyAgent* Agent, bool bEnabled,
    float HorizontalFollow, float VerticalFollow, float YawFollow, float PitchRollFollow, bool bSimulatedBody)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    for (float Value : {HorizontalFollow,VerticalFollow,YawFollow,PitchRollFollow})
        if (!FMath::IsFinite(Value) || Value<0.f || Value>1.f) return false;
    using namespace ProphecyPelvisInertia;
    auto& S=States.FindOrAdd(Agent);
    const FVector Linear(HorizontalFollow,HorizontalFollow,VerticalFollow), Angular(PitchRollFollow,PitchRollFollow,YawFollow);
    const bool bWasActive=S.Active();
    const bool bModeChanged=S.bSimulatedBody!=bSimulatedBody;
    const bool bChanged=S.Linear!=Linear || S.Angular!=Angular || S.bEnabled!=bEnabled || bModeChanged;
    if (!bChanged) return true;
    ClearJolt(S);
    S.bEnabled=bEnabled; S.Linear=Linear; S.Angular=Angular; S.bSimulatedBody=bSimulatedBody;
    if (!bWasActive || !S.Active() || bModeChanged) S.bSeeded=false;
    SynchronizeJolt(Agent);
    return true;
}
void UProphecyPelvisInertiaLibrary::GetPelvisInertia(AProphecyAgent* Agent, bool& bEnabled,
    float& HorizontalFollow, float& VerticalFollow, float& YawFollow, float& PitchRollFollow, bool& bSimulatedBody)
{
    using namespace ProphecyPelvisInertia;
    const auto* S=States.IsEmpty() ? nullptr : States.Find(Agent);
    bEnabled=S && S->bEnabled; bSimulatedBody=S && S->bSimulatedBody;
    HorizontalFollow=S ? S->Linear.X : 1.f; VerticalFollow=S ? S->Linear.Z : 1.f;
    YawFollow=S ? S->Angular.Z : 1.f; PitchRollFollow=S ? S->Angular.X : 1.f;
}
