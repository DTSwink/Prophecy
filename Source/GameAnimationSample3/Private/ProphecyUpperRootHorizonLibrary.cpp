#include "ProphecyUpperRootHorizonLibrary.h"
#include "ProphecyUpperRootHorizon.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "Engine/World.h"
#include "EngineUtils.h"

namespace ProphecyUpperRootHorizon
{
static TMap<TWeakObjectPtr<const AProphecyAgent>, float> Settings;
static FDelegateHandle CleanupHandle;
static void RefreshCleanup()
{
    if (Settings.IsEmpty())
    {
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);
        CleanupHandle.Reset();
    }
    else if (!CleanupHandle.IsValid())
        CleanupHandle = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool)
        {
            for (auto It = Settings.CreateIterator(); It; ++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
            RefreshCleanup();
        });
}
float Configured(const AProphecyAgent* Agent)
{
    const float* Value = Settings.IsEmpty() ? nullptr : Settings.Find(Agent);
    return Value ? *Value : 1.0f;
}
void Remove(const AProphecyAgent* Agent) { Settings.Remove(Agent); RefreshCleanup(); }
}

bool UProphecyUpperRootHorizonLibrary::SetUpperRootRotationHorizon(AProphecyAgent* Agent, float Horizon)
{
    using namespace ProphecyUpperRootHorizon;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(Horizon) || Horizon < 0.0f || Horizon > 1.0f) return false;
    if (Configured(Agent) == Horizon) return true;
    if (Horizon == 1.0f) Settings.Remove(Agent);
    else Settings.Add(Agent, Horizon);
    RefreshCleanup();
    if (UWorld* World = Agent->GetWorld())
        for (TActorIterator<AProphecyNNLocomotionManager> It(World); It; ++It)
            It->CacheUpperRootRotationHorizon(Agent, Horizon);
    return true;
}

bool UProphecyUpperRootHorizonLibrary::GetUpperRootRotationHorizon(AProphecyAgent* Agent, float& Horizon)
{
    Horizon = 1.0f;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    Horizon = ProphecyUpperRootHorizon::Configured(Agent);
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyUpperRootHorizonTest, "Prophecy.NN.UpperRootHorizon.Resampling",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyUpperRootHorizonTest::RunTest(const FString&)
{
    float Original[35], Values[35];
    for (int32 I=0; I<35; ++I) Original[I] = float(I) + 0.125f;
    FMemory::Memcpy(Values, Original, sizeof(Values));
    ProphecyUpperRootHorizon::Resample(Values, 1.0f);
    TestTrue(TEXT("Default is bit-identical, even for nonunit pairs"), FMemory::Memcmp(Original, Values, sizeof(Values)) == 0);
    const double Degrees[8] = {15,30,70,110,175,-160,-100,-60};
    const double ExpectedHalf[8] = {7.5,15,22.5,30,50,70,90,110};
    const double ExpectedThreeQuarters[8] = {11.25,22.5,40,70,100,142.5,181.25,200};
    for (int32 I=0; I<8; ++I)
    {
        Original[5+4*I] = float(FMath::Cos(FMath::DegreesToRadians(Degrees[I])));
        Original[6+4*I] = float(FMath::Sin(FMath::DegreesToRadians(Degrees[I])));
    }
    for (float Horizon : {0.0f, 0.5f, 0.75f})
    {
        FMemory::Memcpy(Values, Original, sizeof(Values));
        ProphecyUpperRootHorizon::Resample(Values, Horizon);
        for (int32 I=0; I<35; ++I)
            if (I<3 || ((I-3)%4)<2)
                TestEqual(TEXT("Velocities and positions unchanged"), Values[I], Original[I]);
        for (int32 I=0; I<8; ++I)
        {
            const double Expected = Horizon==0 ? 0 : Horizon==0.5f ? ExpectedHalf[I] : ExpectedThreeQuarters[I];
            TestNearlyEqual(TEXT("Resampled cosine across wrapped angles"), Values[5+4*I], float(FMath::Cos(FMath::DegreesToRadians(Expected))), 1.e-6f);
            TestNearlyEqual(TEXT("Resampled sine across wrapped angles"), Values[6+4*I], float(FMath::Sin(FMath::DegreesToRadians(Expected))), 1.e-6f);
        }
    }
    return true;
}
#endif
