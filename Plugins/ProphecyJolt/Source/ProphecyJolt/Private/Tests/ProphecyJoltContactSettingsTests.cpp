#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltContactSettingsLibrary.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltContactSlopTest, "Prophecy.Jolt.ContactSettings.PenetrationSlop",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJoltContactSlopTest::RunTest(const FString&)
{
    const UWorld::InitializationValues Values = UWorld::InitializationValues()
        .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false)
        .CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("Transient world"), World)) return false;
    if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    using S = UProphecyJoltContactSettingsLibrary;
    auto* Owner = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (TestNotNull(TEXT("Subsystem"), Owner))
    {
        TestEqual(TEXT("Unchanged default"), S::GetJoltPenetrationSlop(World), 2.0f);
        TestFalse(TEXT("Null rejected"), S::SetJoltPenetrationSlop(nullptr, 0.1f));
        TestTrue(TEXT("Configure before native initialization"), S::SetJoltPenetrationSlop(World, 0.1f));
        FProphecyJoltWorldSettings Settings; Settings.WorkerThreads = 0;
        TestTrue(TEXT("Initialize"), Owner->InitializeSimulation(Settings).IsSuccess());
        TestNearlyEqual(TEXT("Native initialization keeps requested cm"), S::GetJoltPenetrationSlop(World), 0.1f, 0.00001f);
        TestFalse(TEXT("Negative rejected"), S::SetJoltPenetrationSlop(World, -1.0f));
        TestFalse(TEXT("NaN rejected"), S::SetJoltPenetrationSlop(World, std::numeric_limits<float>::quiet_NaN()));
        TestNearlyEqual(TEXT("Invalid input preserves setting"), S::GetJoltPenetrationSlop(World), 0.1f, 0.00001f);
        TestTrue(TEXT("Zero accepted while live"), S::SetJoltPenetrationSlop(World, 0.0f));
        TestEqual(TEXT("Zero native readback"), S::GetJoltPenetrationSlop(World), 0.0f);
        TestTrue(TEXT("Reset to stock"), S::SetJoltPenetrationSlop(World, 2.0f));
        TestNearlyEqual(TEXT("Stock readback"), S::GetJoltPenetrationSlop(World), 2.0f, 0.00001f);
        TestTrue(TEXT("Shutdown"), Owner->ShutdownSimulation().IsSuccess());
        TestTrue(TEXT("Reinitialize"), Owner->InitializeSimulation(Settings).IsSuccess());
        TestNearlyEqual(TEXT("Reset survived reinitialization"), S::GetJoltPenetrationSlop(World), 2.0f, 0.00001f);
    }
    World->DestroyWorld(false);
    if (GEngine) GEngine->DestroyWorldContext(World);
    World->MarkAsGarbage();
    return true;
}
#endif
