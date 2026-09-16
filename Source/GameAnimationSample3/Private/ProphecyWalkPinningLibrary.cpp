#include "ProphecyWalkPinningLibrary.h"
#include "ProphecyWalkPinning.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyWalkPinning
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;
static FDelegateHandle CleanupHandle;
static void RefreshCleanup()
{
    if (Settings.IsEmpty())
    {
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);
        CleanupHandle.Reset();
    }
    else if (!CleanupHandle.IsValid())
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Settings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            RefreshCleanup();
        });
}
bool Apply(const AProphecyAgent* Agent,float Left,float Right,float PinScale,float& LeftPin,float& RightPin)
{
    const auto* Config=Settings.IsEmpty() ? nullptr : Settings.Find(Agent);
    return Config && Config->Apply(Left,Right,PinScale,LeftPin,RightPin);
}
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
