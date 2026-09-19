#include "ProphecyAttackRecoveryLibrary.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "ProphecyBlendClock.h"

namespace ProphecyAttackRecovery
{
struct FRecovery
{
    float Duration = 1.f;
    bool bFirst = true;
    bool Step(FProphecyNNPolicyBlend& Blend, bool& bWalk, float Dt)
    { float Hold=0;return Step(Blend,bWalk,Dt,Hold); }
    bool Step(FProphecyNNPolicyBlend& Blend, bool& bWalk, float Dt,float& HoldRemaining)
    {
        if (Duration <= 0.f) { Blend.Reset(bWalk); return false; }
        if (bFirst)
        {
            bFirst = false;
            bWalk = false;
            Blend.Reset(bWalk);
            return !bWalk;
        }
        if (HoldRemaining>0.f)
        {
            const float Consumed=FMath::Min(FMath::Max(Dt,0.f),HoldRemaining);
            HoldRemaining-=Consumed;Dt-=Consumed;
            if (HoldRemaining<1.e-6f) HoldRemaining=0;
            if (Dt<=UE_SMALL_NUMBER)
            { bWalk=false;Blend.Reset(false);return true; }
        }
        bWalk = true;
        Blend.Step(true, 0.f, Duration, Dt);
        return Blend.IsActive();
    }
};
static TMap<TWeakObjectPtr<const AProphecyAgent>, float> Durations;
static TMap<TWeakObjectPtr<const AProphecyAgent>, FRecovery> Active;
// Keep existing live FRecovery/map layouts intact.
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Holds,ActiveHolds;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool)
    {
        for (auto It = Durations.CreateIterator(); It; ++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
        for (auto It = Active.CreateIterator(); It; ++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
        for (auto It = Holds.CreateIterator(); It; ++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
        for (auto It = ActiveHolds.CreateIterator(); It; ++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
    });
}
void Begin(const AProphecyAgent* Agent)
{
    if (!IsValid(Agent)) return;
    EnsureCleanup();
    const float* Duration = Durations.Find(Agent);
    Cancel(Agent);
    ActiveHolds.Remove(Agent);
    if (Duration && *Duration == 0.f) { Active.Remove(Agent); return; }
    if (const auto* Hold=Holds.Find(Agent)) ActiveHolds.Add(Agent,*Hold);
    Active.Add(Agent, FRecovery{Duration ? *Duration : 1.f, true});
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Policy);
}
void Cancel(const AProphecyAgent* Agent)
{
    if (!Active.IsEmpty()) Active.Remove(Agent);if (!ActiveHolds.IsEmpty()) ActiveHolds.Remove(Agent);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Recovery);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Policy);
}
void Remove(const AProphecyAgent* Agent) { Cancel(Agent); Durations.Remove(Agent); Holds.Remove(Agent); }
bool Step(const AProphecyAgent* Agent, FProphecyNNPolicyBlend& Blend, bool& bWalk, float Dt)
{
    if (Active.IsEmpty()) return false;
    auto* Recovery = Active.Find(Agent);
    if (!Recovery) return false;
    const bool bOverride = Recovery->Duration > 0.f;
    float Remaining=0;
    if (const auto* Hold=ActiveHolds.IsEmpty() ? nullptr : ActiveHolds.Find(Agent)) Remaining=*Hold;
    if (Recovery->bFirst && bOverride) ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::Recovery,double(Recovery->Duration)+Remaining);
    Dt=float(ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::Recovery));
    if (!Recovery->Step(Blend, bWalk, Dt, Remaining)) Cancel(Agent);
    else if (Remaining>0.f) ActiveHolds.Add(Agent,Remaining);
    else ActiveHolds.Remove(Agent);
    return bOverride;
}
}

bool UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(AProphecyAgent* Agent, float DurationSeconds,float HoldDurationSeconds)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || !FMath::IsFinite(DurationSeconds) || DurationSeconds < 0.f
        || !FMath::IsFinite(HoldDurationSeconds) || HoldDurationSeconds < 0.f) return false;
    using namespace ProphecyAttackRecovery;
    EnsureCleanup();
    if (DurationSeconds == 1.f) Durations.Remove(Agent);
    else Durations.Add(Agent, DurationSeconds);
    if (HoldDurationSeconds==0.f) Holds.Remove(Agent);
    else Holds.Add(Agent,HoldDurationSeconds);
    // Clear an already-running mixture on its next policy step without forcing
    // either checkpoint. No recovery entry is created for future zero-duration exits.
    if (DurationSeconds == 0.f)
        if (auto* Recovery = Active.Find(Agent)) Recovery->Duration = 0.f;
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackRecoveryTest, "Prophecy.NN.PolicyBlend.AttackRecovery",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyAttackRecoveryTest::RunTest(const FString&)
{
    using namespace ProphecyAttackRecovery;
    FProphecyNNPolicyBlend Blend;
    bool Walk = true;
    FRecovery Recovery;
    TestTrue(TEXT("Default recovery begins"), Recovery.Step(Blend, Walk, 1.f / 30.f));
    TestTrue(TEXT("First returned prediction is pure run, despite walk selection"), !Walk && Blend.WalkWeight == 0.f && !Blend.IsActive());
    for (int32 I = 0; I < 15; ++I)
    {
        Walk = false; // Normal run rules cannot interrupt this fade.
        Recovery.Step(Blend, Walk, 1.f / 30.f);
    }
    TestTrue(TEXT("Half second is equal checkpoint mix"), Walk && FMath::IsNearlyEqual(Blend.WalkWeight, .5f, 1.e-5f));
    bool ActiveNow = true;
    for (int32 I = 0; I < 15; ++I) ActiveNow = Recovery.Step(Blend, Walk, 1.f / 30.f);
    TestTrue(TEXT("One second ends on walk and stops dual inference"), !ActiveNow && Walk && Blend.WalkWeight == 1.f && !Blend.IsActive());
    FRecovery Slow{2.f, true};
    Slow.Step(Blend, Walk, 1.f / 30.f);
    for (int32 I = 0; I < 30; ++I) Slow.Step(Blend, Walk, 1.f / 30.f);
    TestTrue(TEXT("Custom two-second duration"), FMath::IsNearlyEqual(Blend.WalkWeight, .5f, 1.e-5f));
    FRecovery Instant{0.f, true};
    Walk = false;
    TestFalse(TEXT("Zero duration completes immediately"), Instant.Step(Blend, Walk, 1.f / 30.f));
    TestTrue(TEXT("Zero preserves ordinary run selection without dual inference"), !Walk && Blend.WalkWeight == 0.f && !Blend.IsActive());
    FRecovery Held{1.f,true};float Remaining=.2f;
    Held.Step(Blend,Walk,.1f,Remaining);
    Held.Step(Blend,Walk,.1f,Remaining);
    Held.Step(Blend,Walk,.1f,Remaining);
    TestTrue(TEXT("Hold uses pure run without dual inference"),!Walk && Blend.WalkWeight==0 && !Blend.IsActive());
    Held.Step(Blend,Walk,.5f,Remaining);
    TestTrue(TEXT("Blend duration begins after hold"),FMath::IsNearlyEqual(Blend.WalkWeight,.5f,1.e-5f));
    TestFalse(TEXT("Held recovery completes"),Held.Step(Blend,Walk,.5f,Remaining));
    FRecovery Crossing{1.f,true};Remaining=.1f;
    Crossing.Step(Blend,Walk,.25f,Remaining);
    Crossing.Step(Blend,Walk,.25f,Remaining);
    TestTrue(TEXT("Hold boundary uses remainder of step"),FMath::IsNearlyEqual(Blend.Elapsed,.15f,1.e-5f));
    return true;
}
#endif
