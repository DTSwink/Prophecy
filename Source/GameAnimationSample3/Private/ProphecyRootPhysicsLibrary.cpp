#include "ProphecyRootPhysicsLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyRootBalance.h"
#include "ProphecyRootMagic.h"
#include "Components/SkeletalMeshComponent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
#include "ProphecyNNPolicyBlend.h"
#include "ProphecyBlendClock.h"
#include "Engine/World.h"

namespace ProphecyAutoRun
{
static TMap<TWeakObjectPtr<const AProphecyAgent>, float> Thresholds;
float Threshold(const AProphecyAgent* Agent)
{
    const float* Value = Thresholds.IsEmpty() ? nullptr : Thresholds.Find(Agent);
    return Value ? *Value : 100000.f;
}
void Remove(const AProphecyAgent* Agent) { Thresholds.Remove(Agent); }
}
bool UProphecyRootPhysicsLibrary::SetLocomotionAutoRunSpeedThreshold(AProphecyAgent* Agent, float SpeedCmPerSecond)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(SpeedCmPerSecond) || SpeedCmPerSecond < 0.f) return false;
    if (SpeedCmPerSecond == 100000.f) ProphecyAutoRun::Remove(Agent);
    else ProphecyAutoRun::Thresholds.Add(Agent, SpeedCmPerSecond);
    return true;
}
float UProphecyRootPhysicsLibrary::GetLocomotionAutoRunSpeedThreshold(AProphecyAgent* Agent)
{
    return IsInGameThread() && IsValid(Agent) ? ProphecyAutoRun::Threshold(Agent) : 100000.f;
}

namespace ProphecyRootMagic
{
static TMap<TWeakObjectPtr<const AProphecyAgent>, FVelocity> Velocities;
// Velocities retains its existing allocation layout and becomes the cached sum.
// Extra source storage exists only for agents with a nonzero second set.
struct FVelocityPair { FVelocity First, Second; };
static TMap<TWeakObjectPtr<const AProphecyAgent>, FVelocityPair> PairedVelocities;
const FVelocity* Find(const AProphecyAgent* Agent) { return Velocities.IsEmpty() ? nullptr : Velocities.Find(Agent); }
void Remove(const AProphecyAgent* Agent) { Velocities.Remove(Agent); PairedVelocities.Remove(Agent); }
static const FVelocity* FindChannel(const AProphecyAgent* Agent, bool Second)
{
    if (const auto* Pair = PairedVelocities.IsEmpty() ? nullptr : PairedVelocities.Find(Agent))
        return Second ? &Pair->Second : &Pair->First;
    return Second ? nullptr : Find(Agent);
}
static bool StoreChannel(const AProphecyAgent* Agent, const FVelocity& Value, bool Second)
{
    FVelocityPair Pair;
    if (const auto* Existing = PairedVelocities.IsEmpty() ? nullptr : PairedVelocities.Find(Agent)) Pair = *Existing;
    else if (const auto* First = Find(Agent)) Pair.First = *First;
    (Second ? Pair.Second : Pair.First) = Value;
    const FVelocity Total{Pair.First.Linear + Pair.Second.Linear, Pair.First.Yaw + Pair.Second.Yaw};
    if (Total.Linear.ContainsNaN() || !FMath::IsFinite(Total.Yaw) || !FMath::IsFinite(float(Total.Yaw))) return false;
    for (auto It = Velocities.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    for (auto It = PairedVelocities.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    if (Total.Linear.IsZero() && Total.Yaw == 0) Velocities.Remove(Agent);
    else Velocities.Add(Agent, Total);
    // Opposing sets may cancel in the sum but must remain independently editable.
    if (Pair.Second.Linear.IsZero() && Pair.Second.Yaw == 0) PairedVelocities.Remove(Agent);
    else PairedVelocities.Add(Agent, Pair);
    return true;
}

static bool SetLinear(AProphecyAgent* Agent, FVector WorldLinearVelocity, bool bAddToCurrent, bool Second)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || WorldLinearVelocity.ContainsNaN()) return false;
    const auto* Current = FindChannel(Agent, Second);
    auto Value = Current ? *Current : ProphecyRootMagic::FVelocity{};
    const FVector3f Incoming(WorldLinearVelocity.X * .01, WorldLinearVelocity.Z * .01, WorldLinearVelocity.Y * .01);
    Value.Linear = bAddToCurrent ? Value.Linear + Incoming : Incoming;
    if (Value.Linear.ContainsNaN()) return false;
    return StoreChannel(Agent, Value, Second);
}

static bool SetAngular(AProphecyAgent* Agent, FVector WorldAngularVelocityDegrees, bool bAddToCurrent, bool Second)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || WorldAngularVelocityDegrees.ContainsNaN()) return false;
    const auto* Current = FindChannel(Agent, Second);
    auto Value = Current ? *Current : ProphecyRootMagic::FVelocity{};
    const double Incoming = -FMath::DegreesToRadians(WorldAngularVelocityDegrees.Z);
    Value.Yaw = bAddToCurrent ? Value.Yaw + Incoming : Incoming;
    if (!FMath::IsFinite(Value.Yaw) || !FMath::IsFinite(float(Value.Yaw))) return false;
    return StoreChannel(Agent, Value, Second);
}
}

bool UProphecyRootPhysicsLibrary::SetRootMagicVelocity(AProphecyAgent* Agent, FVector Value, bool Add)
{ return ProphecyRootMagic::SetLinear(Agent, Value, Add, false); }
bool UProphecyRootPhysicsLibrary::SetRootMagicAngVelocity(AProphecyAgent* Agent, FVector Value, bool Add)
{ return ProphecyRootMagic::SetAngular(Agent, Value, Add, false); }
bool UProphecyRootPhysicsLibrary::SetRootMagicVelocity2(AProphecyAgent* Agent, FVector Value, bool Add)
{ return ProphecyRootMagic::SetLinear(Agent, Value, Add, true); }
bool UProphecyRootPhysicsLibrary::SetRootMagicAngVelocity2(AProphecyAgent* Agent, FVector Value, bool Add)
{ return ProphecyRootMagic::SetAngular(Agent, Value, Add, true); }

bool UProphecyRootPhysicsLibrary::SetLocomotionRootWindowLocation(AProphecyAgent* Agent, FVector WorldLocation)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || WorldLocation.ContainsNaN() || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return false;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld()); It; ++It)
        if (It->ResolveAgent(Agent->GetAgentHandle()) == Agent)
            return It->SetAgentLocomotionRootWindowLocation(Agent->GetAgentHandle(), WorldLocation);
    return false;
}

FVector UProphecyRootPhysicsLibrary::GetRootMagicVelocity(AProphecyAgent* Agent)
{
    const auto* Value = IsInGameThread() && IsValid(Agent) ? ProphecyRootMagic::FindChannel(Agent, false) : nullptr;
    return Value ? FVector(Value->Linear.X, Value->Linear.Z, Value->Linear.Y) * 100. : FVector::ZeroVector;
}

FVector UProphecyRootPhysicsLibrary::GetRootMagicAngVelocity(AProphecyAgent* Agent)
{
    const auto* Value = IsInGameThread() && IsValid(Agent) ? ProphecyRootMagic::FindChannel(Agent, false) : nullptr;
    return Value ? FVector(0, 0, -FMath::RadiansToDegrees(Value->Yaw)) : FVector::ZeroVector;
}

FVector UProphecyRootPhysicsLibrary::GetRootMagicVelocity2(AProphecyAgent* Agent)
{
    const auto* Value = IsInGameThread() && IsValid(Agent) ? ProphecyRootMagic::FindChannel(Agent, true) : nullptr;
    return Value ? FVector(Value->Linear.X, Value->Linear.Z, Value->Linear.Y) * 100. : FVector::ZeroVector;
}
FVector UProphecyRootPhysicsLibrary::GetRootMagicAngVelocity2(AProphecyAgent* Agent)
{
    const auto* Value = IsInGameThread() && IsValid(Agent) ? ProphecyRootMagic::FindChannel(Agent, true) : nullptr;
    return Value ? FVector(0, 0, -FMath::RadiansToDegrees(Value->Yaw)) : FVector::ZeroVector;
}

bool UProphecyRootPhysicsLibrary::GetContinuousLocomotionRootWindow(AProphecyAgent* Agent,
    TArray<FTransform>& WorldRoots, TArray<float>& TimeOffsetsSeconds)
{
    WorldRoots.Reset(); TimeOffsetsSeconds.Reset();
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return false;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld()); It; ++It)
        if (It->ResolveAgent(Agent->GetAgentHandle()) == Agent)
            return It->GetAgentContinuousLocomotionRootWindow(Agent->GetAgentHandle(), WorldRoots, TimeOffsetsSeconds);
    return false;
}

namespace ProphecyRootBalance
{
struct FKickDurations
{
    double Hold=0.,Fade=1.;
    double End() const { return Hold+Fade; }
    double Weight(double Elapsed) const
    {
        if (Elapsed+1.e-8>=End()) return 0.;
        if (Elapsed<=Hold) return 1.;
        const double Alpha=FMath::Clamp((Elapsed-Hold)/Fade,0.,1.);
        return 1.-Alpha*Alpha*(3.-2.*Alpha);
    }
};
struct FKickReturn { FKickDurations Duration;double Elapsed=0.; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FKickDurations> KickSettings;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FKickReturn> KickReturns;
static FDelegateHandle KickCleanup;
static void RefreshKickCleanup()
{
    if (KickSettings.IsEmpty() && KickReturns.IsEmpty())
    { FWorldDelegates::OnWorldCleanup.Remove(KickCleanup);KickCleanup.Reset(); }
    else if (!KickCleanup.IsValid()) KickCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=KickSettings.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto It=KickReturns.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        RefreshKickCleanup();
    });
}
void CancelKickException(const AProphecyAgent* Agent)
{
    if (!KickReturns.IsEmpty()) KickReturns.Remove(Agent);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::KickBalance);
    RefreshKickCleanup();
}
void BeginKickException(const AProphecyAgent* Agent,FName Attack,bool ReturningToLocomotion)
{
    CancelKickException(Agent);
    if (!ReturningToLocomotion || (Attack!=TEXT("kickl") && Attack!=TEXT("kickr"))) return;
    const FKickDurations* Config=KickSettings.IsEmpty() ? nullptr : KickSettings.Find(Agent);
    if (!Config || Config->End()<=0.) return;
    KickReturns.Add(Agent,FKickReturn{*Config});
    ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::KickBalance,Config->End());
    RefreshKickCleanup();
}
static double KickWeight(const AProphecyAgent* Agent)
{
    auto* State=KickReturns.IsEmpty() ? nullptr : KickReturns.Find(Agent);
    if (!State) return 0.;
    State->Elapsed+=ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::KickBalance);
    const double Weight=State->Duration.Weight(State->Elapsed);
    if (Weight<=0.) CancelKickException(Agent);
    return Weight;
}
static bool GetFlatPelvisTarget(const AProphecyAgent* Agent,FVector& Target)
{
    static const FName PelvisBone(TEXT("pelvis"));
    FTransform Body;FVector Linear,Angular;bool Simulating=false;
    if (Agent->GetPhysicalBodyState(PelvisBone,Body,Linear,Angular,Simulating) && Simulating)
        Target=Body.GetLocation();
    else
    {
        const auto* Mesh=Agent->GetPoseReferenceMesh();
        if (!Mesh || Mesh->GetBoneIndex(PelvisBone)==INDEX_NONE) return false;
        Target=Mesh->GetSocketLocation(PelvisBone);
    }
    if (Target.ContainsNaN()) return false;
    Target.Z=Agent->GetRootLowPoint().Z;return true;
}
bool GetTarget(const AProphecyAgent* Agent,FVector& Target)
{
    if (!IsValid(Agent)) return false;
    const double Weight=KickWeight(Agent);
    if (Weight<=0.) return GetFlatFeetTarget(Agent,Target);
    FVector Pelvis;
    if (!GetFlatPelvisTarget(Agent,Pelvis)) return GetFlatFeetTarget(Agent,Target);
    if (Weight>=1.) { Target=Pelvis;return true; }
    FVector Feet;
    if (!GetFlatFeetTarget(Agent,Feet)) { Target=Pelvis;return true; }
    Target=FMath::Lerp(Feet,Pelvis,Weight);return true;
}
// New native storage identity: Live Coding cannot resize retained TMap elements.
// If this layout changes again, migrate/version its storage or load a normal build.
struct FStateWithMagicLimits
{
    prophecy::sim::RootBalanceSpring Spring;
    FVector FlatMidpoint = FVector::ZeroVector;
    double MagicLinearSpeedSquared = 10000.; // (10000 cm/s in metres/s)^2
    double MagicAngularSpeed = FMath::DegreesToRadians(10000.);
    bool bActive = false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>, FStateWithMagicLimits> StatesWithMagicLimits;
void Remove(const AProphecyAgent* Agent)
{
    StatesWithMagicLimits.Remove(Agent);KickSettings.Remove(Agent);CancelKickException(Agent);
}
void ResetMotion(const AProphecyAgent* Agent)
{
    CancelKickException(Agent);
    if (auto* S = StatesWithMagicLimits.Find(Agent))
    { S->bActive = false; S->FlatMidpoint = FVector::ZeroVector; S->Spring.target = {}; }
}
const prophecy::sim::RootBalanceSpring* GetPrepared(const AProphecyAgent* Agent)
{
    const auto* State = StatesWithMagicLimits.IsEmpty() ? nullptr : StatesWithMagicLimits.Find(Agent);
    return State && State->bActive ? &State->Spring : nullptr;
}
const prophecy::sim::RootBalanceSpring* Prepare(const AProphecyAgent* Agent, const prophecy::sim::LocomotionState& Mover,
    const prophecy::sim::LocomotionIntent& Intent, bool bAllowed)
{
    auto* State = StatesWithMagicLimits.IsEmpty() ? nullptr : StatesWithMagicLimits.Find(Agent);
    if (!State) return nullptr;
    State->bActive = false;
    if (!bAllowed || !IsValid(Agent) || !Agent->bNNInferenceEnabled ||
        !prophecy::sim::IsRootBalanceActive(Mover, Intent, State->Spring)) return nullptr;
    // Gate before sampling either foot; disabled balancing never reaches this lookup.
    if (const auto* Magic = ProphecyRootMagic::Find(Agent))
        if (Magic->Linear.SizeSquared() > State->MagicLinearSpeedSquared
            || FMath::Abs(Magic->Yaw) > State->MagicAngularSpeed) return nullptr;
    if (!GetTarget(Agent,State->FlatMidpoint)) return nullptr;
    State->Spring.target = { State->FlatMidpoint.X * .01, State->FlatMidpoint.Y * .01 };
    State->bActive = true;
    return &State->Spring;
}
bool GetFlatFeetTarget(const AProphecyAgent* Agent,FVector& Target)
{
    if (!IsValid(Agent)) return false;
    const auto* Mesh = Agent->GetPoseReferenceMesh();
    if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return false;
    const FName Feet[] = { TEXT("foot_l"), TEXT("foot_r") };
    FVector Positions[2];
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FTransform Body;
        FVector Linear, Angular;
        bool bSimulating = false;
        if (Agent->GetPhysicalBodyState(Feet[Index], Body, Linear, Angular, bSimulating) && bSimulating)
            Positions[Index] = Body.GetLocation();
        else
        {
            if (Mesh->GetBoneIndex(Feet[Index]) == INDEX_NONE) return false;
            Positions[Index] = Mesh->GetSocketLocation(Feet[Index]);
        }
        if (Positions[Index].ContainsNaN()) return false;
    }
    Target = (Positions[0] + Positions[1]) * 0.5;
    Target.Z = Agent->GetRootLowPoint().Z;
    return true;
}
}

bool UProphecyRootPhysicsLibrary::SetKickSelfBalancingExceptionDurations(AProphecyAgent* Agent,
    float HoldDurationSeconds,float FadeDurationSeconds)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(HoldDurationSeconds) || HoldDurationSeconds<0.f
        || !FMath::IsFinite(FadeDurationSeconds) || FadeDurationSeconds<0.f) return false;
    using namespace ProphecyRootBalance;
    const FKickDurations Config{HoldDurationSeconds,FadeDurationSeconds};
    if (Config.End()<=0.) { KickSettings.Remove(Agent);CancelKickException(Agent); }
    else { KickSettings.Add(Agent,Config);RefreshKickCleanup(); }
    return true;
}

bool UProphecyRootPhysicsLibrary::AddRootAngularImpulse(AProphecyAgent* Agent,
    FVector WorldAngularImpulseRadians, bool bVelocityChange)
{
    return IsInGameThread() && IsValid(Agent) && !Agent->IsActorBeingDestroyed()
        && Agent->AddRootImpulse(FVector::ZeroVector, WorldAngularImpulseRadians, bVelocityChange);
}

bool UProphecyRootPhysicsLibrary::AddRootForceAndTorque(AProphecyAgent* Agent,
    FVector WorldForce, FVector WorldTorqueRadians, float DeltaSeconds, bool bAccelerationChange)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(DeltaSeconds) || DeltaSeconds < 0.f
        || WorldForce.ContainsNaN() || WorldTorqueRadians.ContainsNaN()) return false;
    return Agent->AddRootImpulse(WorldForce * double(DeltaSeconds),
        WorldTorqueRadians * double(DeltaSeconds), bAccelerationChange);
}

bool UProphecyRootPhysicsLibrary::SetRootSelfBalancing(AProphecyAgent* Agent, bool bEnabled,
    float SpeedThresholdCmPerSecond, float MoveInputThreshold, float SpringFrequencyHz,
    float DampingRatio, float MaxBalanceSpeedCmPerSecond, float ToleranceCm,
    float MagicVelocityThresholdCmPerSecond, float MagicAngVelocityThresholdDegreesPerSecond)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    using namespace ProphecyRootBalance;
    if (!bEnabled) { StatesWithMagicLimits.Remove(Agent); return true; }
    for (float Value : {SpeedThresholdCmPerSecond, MoveInputThreshold, SpringFrequencyHz,
        DampingRatio, MaxBalanceSpeedCmPerSecond, ToleranceCm,
        MagicVelocityThresholdCmPerSecond, MagicAngVelocityThresholdDegreesPerSecond})
        if (!FMath::IsFinite(Value) || Value < 0.f) return false;
    if (MoveInputThreshold > 1.f || SpringFrequencyHz <= 0.f) return false;
    for (auto It = StatesWithMagicLimits.CreateIterator(); It; ++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    auto& State = StatesWithMagicLimits.FindOrAdd(Agent);
    State.Spring.speed_threshold = SpeedThresholdCmPerSecond * .01;
    State.Spring.input_threshold = MoveInputThreshold;
    State.Spring.frequency_hz = SpringFrequencyHz;
    State.Spring.damping_ratio = DampingRatio;
    State.Spring.maximum_speed = MaxBalanceSpeedCmPerSecond * .01;
    State.Spring.tolerance = ToleranceCm * .01;
    State.MagicLinearSpeedSquared = FMath::Square(double(MagicVelocityThresholdCmPerSecond) * .01);
    State.MagicAngularSpeed = FMath::DegreesToRadians(double(MagicAngVelocityThresholdDegreesPerSecond));
    State.bActive = false;
    return true;
}

void UProphecyRootPhysicsLibrary::GetRootSelfBalancingState(AProphecyAgent* Agent,
    bool& bEnabled, bool& bActive, FVector& FlatFeetMidpoint)
{
    const auto* State = IsValid(Agent) ? ProphecyRootBalance::StatesWithMagicLimits.Find(Agent) : nullptr;
    bEnabled = State != nullptr;
    bActive = State && State->bActive && Agent->bNNInferenceEnabled;
    FlatFeetMidpoint = State ? State->FlatMidpoint : FVector::ZeroVector;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyKickBalanceTest,"Prophecy.Root.KickSelfBalancingException",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyKickBalanceTest::RunTest(const FString&)
{
    using namespace ProphecyRootBalance;
    const FKickDurations Schedule{.5,1.};
    TestEqual(TEXT("Starts below pelvis"),Schedule.Weight(0),1.);
    TestEqual(TEXT("Holds below pelvis through 30 ticks"),Schedule.Weight(.5),1.);
    TestNearlyEqual(TEXT("Halfway back after 30 hold plus 30 fade ticks"),Schedule.Weight(1.),.5,1.e-8);
    TestEqual(TEXT("Normal feet target after 90 ticks"),Schedule.Weight(1.5),0.);
    TestEqual(TEXT("Zero fade holds then restores immediately"),FKickDurations{1.,0.}.Weight(1.),0.);
    TestEqual(TEXT("Zero hold starts at pelvis"),FKickDurations{0.,1.}.Weight(0),1.);
    TestEqual(TEXT("Zero durations bypass entirely"),FKickDurations{0.,0.}.Weight(0),0.);
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    AProphecyAgent* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) { if (World) World->DestroyWorld(false);return false; }
    BeginKickException(Agent,TEXT("kickl"),true);
    TestFalse(TEXT("Unconfigured agent stays on normal rule"),KickReturns.Contains(Agent));
    TestTrue(TEXT("Configure durations"),UProphecyRootPhysicsLibrary::SetKickSelfBalancingExceptionDurations(Agent,.5f,1.f));
    for (FName Attack:{FName(TEXT("kickl")),FName(TEXT("kickr"))})
    {
        BeginKickException(Agent,Attack,true);
        TestEqual(TEXT("Either kick starts at pelvis weight 1"),KickWeight(Agent),1.);
        TestEqual(TEXT("Repeated target read does not advance"),KickWeight(Agent),1.);
        KickReturns.FindChecked(Agent).Elapsed=1.;
        TestNearlyEqual(TEXT("Active fade blends toward normal"),KickWeight(Agent),.5,1.e-8);
        KickReturns.FindChecked(Agent).Elapsed=1.5;
        TestEqual(TEXT("Expired return uses normal target"),KickWeight(Agent),0.);
        TestFalse(TEXT("Completed return retires state"),KickReturns.Contains(Agent));
    }
    BeginKickException(Agent,TEXT("hookl"),true);
    TestFalse(TEXT("Other attacks do not activate exception"),KickReturns.Contains(Agent));
    BeginKickException(Agent,TEXT("kickl"),false);
    TestFalse(TEXT("Replacement without locomotion does not activate"),KickReturns.Contains(Agent));
    UProphecyRootPhysicsLibrary::SetRootSelfBalancing(Agent,false);
    TestTrue(TEXT("Disabling spring preserves separate return configuration"),KickSettings.Contains(Agent));
    BeginKickException(Agent,TEXT("kickr"),true);ResetMotion(Agent);
    TestFalse(TEXT("Reset cancels active kick return"),KickReturns.Contains(Agent));
    TestTrue(TEXT("Reset preserves configured durations"),KickSettings.Contains(Agent));
    BeginKickException(Agent,TEXT("kickr"),true);
    UProphecyRootPhysicsLibrary::SetKickSelfBalancingExceptionDurations(Agent,0,0);
    TestFalse(TEXT("Zero durations remove settings"),KickSettings.Contains(Agent));
    TestFalse(TEXT("Zero durations cancel current return"),KickReturns.Contains(Agent));
    TestFalse(TEXT("Reject negative duration"),UProphecyRootPhysicsLibrary::SetKickSelfBalancingExceptionDurations(Agent,-1,1));
    Remove(Agent);World->DestroyWorld(false);
    return !HasAnyErrors();
}

#include "Misc/AutomationTest.h"
#include "ProphecyContinuousRootWindow.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyContinuousRootWindowTest,
    "Prophecy.NN.RootWindow.Continuous", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyContinuousRootWindowTest::RunTest(const FString&)
{
    auto Trajectory = [](int32 Start)
    {
        TArray<FTransform> Roots;
        for (int32 I=0; I<10; ++I)
        {
            const double T = I + Start;
            Roots.Emplace(FRotator(0, 170. + 20.*T, 0), FVector(10.*T, T*T, 0));
        }
        return Roots;
    };
    TArray<float> Times;
    auto Half = Trajectory(0);
    const FTransform Mid(FRotator(0, 180, 0), FVector(5, .5, 0));
    ProphecyContinuousRootWindow::Resample(Half, Times, .5f, 1.f/30.f, Mid);
    TestEqual(TEXT("Current plus eight future samples"), Half.Num(), 9);
    TestTrue(TEXT("Current exactly follows applied presentation root"), Half[0].Equals(Mid));
    TestTrue(TEXT("Half-step positions advance along the curved trajectory"), Half[4].GetLocation().Equals(FVector(45,20.5,0), .001));
    TestTrue(TEXT("Rotation interpolates through 180 without a wrap jump"), Half[1].GetRotation().Equals(FRotator(0,200,0).Quaternion(), .00001));
    TestEqual(TEXT("Times start at displayed now"), Times[0], 0.f);
    TestTrue(TEXT("Horizon stays eight policy intervals"), FMath::IsNearlyEqual(Times[8],8.f/30.f));
    auto Before = Trajectory(0), After = Trajectory(1);
    const FTransform Boundary = After[0];
    ProphecyContinuousRootWindow::Resample(Before, Times, 1, 1.f/30.f, Boundary);
    ProphecyContinuousRootWindow::Resample(After, Times, 0, 1.f/30.f, Boundary);
    for (int32 I=0; I<9; ++I)
        TestTrue(TEXT("Consistent rolling predictions agree at policy boundary"), Before[I].Equals(After[I], .0001));
    auto Corrected = Trajectory(0);
    const FTransform Applied(FRotator(0,180,0), FVector(2,.5,4));
    ProphecyContinuousRootWindow::Resample(Corrected, Times, .5f, 1.f/30.f, Applied);
    TestTrue(TEXT("Collision/floor translation carried through future samples"),
        Corrected[4].GetLocation().Equals(Half[4].GetLocation()+FVector(-3,0,4), .001));
    return true;
}
#endif
