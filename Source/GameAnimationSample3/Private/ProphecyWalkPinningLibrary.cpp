#include "ProphecyWalkPinningLibrary.h"
#include "ProphecyWalkPinning.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyWalkPinning
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;
// Separate storage preserves the layout of settings retained across Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Limits;
static FDelegateHandle CleanupHandle;
static void RefreshCleanup()
{
    if (Settings.IsEmpty() && Limits.IsEmpty())
    {
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);
        CleanupHandle.Reset();
    }
    else if (!CleanupHandle.IsValid())
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Settings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=Limits.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            RefreshCleanup();
        });
}
bool Apply(const AProphecyAgent* Agent,float Left,float Right,float PinScale,float& LeftPin,float& RightPin)
{
    const auto* Config=Settings.IsEmpty() ? nullptr : Settings.Find(Agent);
    return Config && Config->Apply(Left,Right,PinScale,LeftPin,RightPin);
}
void ApplyLimit(const AProphecyAgent* Agent,float Left,float Right,float& LeftPin,float& RightPin)
{
    const float* Limit=Limits.IsEmpty() ? nullptr : Limits.Find(Agent);
    LimitRawValues(Limit ? *Limit : 2.f,Left,Right,LeftPin,RightPin);
}
}
bool UProphecyWalkPinningLibrary::SetWalkPinningLimit(AProphecyAgent* Agent,float Limit)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !FMath::IsFinite(Limit)) return false;
    if (Limit==2.f) Limits.Remove(Agent);
    else Limits.Add(Agent,Limit);
    RefreshCleanup();
    return true;
}
float UProphecyWalkPinningLibrary::GetWalkPinningLimit(AProphecyAgent* Agent)
{
    if (const float* Limit=ProphecyWalkPinning::Limits.Find(Agent)) return *Limit;
    return 2.f;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningTolerance(AProphecyAgent* Agent,float Tolerance,float ToleranceFallback)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(Tolerance) || Tolerance<0 || !FMath::IsFinite(ToleranceFallback)
        || ToleranceFallback<0 || ToleranceFallback>1) return false;
    if (Tolerance==0) Settings.Remove(Agent);
    else Settings.Add(Agent,FSettings{Tolerance,ToleranceFallback});
    RefreshCleanup();
    return true;
}
bool UProphecyWalkPinningLibrary::GetWalkPinningTolerance(AProphecyAgent* Agent,float& Tolerance,float& ToleranceFallback)
{
    Tolerance=ToleranceFallback=0;
    if (!IsValid(Agent)) return false;
    if (const auto* Config=ProphecyWalkPinning::Settings.Find(Agent))
    { Tolerance=Config->Tolerance; ToleranceFallback=Config->Fallback; }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningLimitTest,"Prophecy.NN.WalkPinning.Limit",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningLimitTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    float L=1,R=0;
    ApplyLimit(nullptr,2.5f,3.f,L,R);
    TestEqual(TEXT("Default limit vetoes the selected foot"),L,0.f);
    TestEqual(TEXT("Veto never transfers a pin to the other foot"),R,0.f);
    L=1;R=0;LimitRawValues(2.f,2.f,3.f,L,R);
    TestEqual(TEXT("Exactly equal to the limit stays pinned"),L,1.f);
    L=0;R=1;LimitRawValues(2.f,3.f,2.5f,L,R);
    TestEqual(TEXT("Right winner can also be vetoed"),R,0.f);
    TestEqual(TEXT("Right veto does not select left"),L,0.f);
    L=R=1;LimitRawValues(2.f,-.1f,-.2f,L,R);
    TestEqual(TEXT("Default preserves both-negative pinning"),L+R,2.f);
    L=R=1;LimitRawValues(-.15f,-.1f,-.2f,L,R);
    TestEqual(TEXT("Signed threshold independently clears left"),L,0.f);
    TestEqual(TEXT("Signed threshold preserves eligible right"),R,1.f);
    FSettings Tolerance{1.f,1.f};
    L=1;R=0;Tolerance.Apply(1.75f,2.25f,1.f,L,R);
    const float Before=L;LimitRawValues(2.f,1.75f,2.25f,L,R);
    TestEqual(TEXT("Eligible soft fallback is unchanged"),L,Before);
    TestEqual(TEXT("Over-limit soft fallback is also vetoed"),R,0.f);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningToleranceTest,"Prophecy.NN.WalkPinning.Tolerance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningToleranceTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    float L=1,R=0;
    TestFalse(TEXT("Default preserves even positive ties"),FSettings{}.Apply(.125f,.125f,8,L,R));
    TestEqual(TEXT("Bypass leaves legacy result untouched"),L,1.f);
    FSettings Config{.125f,0};
    TestTrue(TEXT("Inclusive tolerance boundary"),Config.Apply(.125f,.25f,8,L,R));
    TestEqual(TEXT("Zero fallback left"),L,0.f);
    TestEqual(TEXT("Zero fallback right"),R,0.f);
    Config.Fallback=1;
    TestTrue(TEXT("Raw fallback applies"),Config.Apply(.125f,.25f,8,L,R));
    TestNearlyEqual(TEXT("Left decoded soft probability"),L,.26894142f,1.e-6f);
    TestNearlyEqual(TEXT("Right decoded soft probability"),R,.11920292f,1.e-6f);
    Config.Fallback=.5f;
    Config.Apply(.125f,.25f,8,L,R);
    TestNearlyEqual(TEXT("Intermediate fallback scales soft weights"),L,.13447071f,1.e-6f);
    TestFalse(TEXT("Outside tolerance retains hard selection"),Config.Apply(.125f,.375f,8,L,R));
    TestFalse(TEXT("Two negative values retain both-pinned rule"),Config.Apply(-.125f,-.25f,8,L,R));
    TestFalse(TEXT("Mixed signs retain hard selection"),Config.Apply(-.125f,.125f,8,L,R));
    TestFalse(TEXT("Zero is not strictly positive"),Config.Apply(0,.125f,8,L,R));
    return true;
}
#endif
