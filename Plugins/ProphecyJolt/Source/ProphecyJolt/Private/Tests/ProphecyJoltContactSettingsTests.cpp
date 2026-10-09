#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltContactSettingsLibrary.h"
#include "ProphecyJoltBodyDriveLibrary.h"

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
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSpeculativeDistanceTest, "Prophecy.Jolt.ContactSettings.SpeculativeDistance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJoltSpeculativeDistanceTest::RunTest(const FString&)
{
    using L = UProphecyJoltBodyDriveLibrary;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    for (float Distance : {2.f, 11.f})
    {
        auto* W = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (!TestNotNull(TEXT("Transient world"), W)) return false;
        if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        auto* S = W->GetSubsystem<UProphecyJoltWorldSubsystem>();
        TestEqual(TEXT("Fresh world default"), L::GetJoltSpeculativeContactDistance(W), 2.f);
        TestFalse(TEXT("Null context rejected"), L::SetJoltSpeculativeContactDistance(nullptr, Distance));
        TestTrue(TEXT("Before physics admission"), L::SetJoltSpeculativeContactDistance(W, Distance));
        FProphecyJoltWorldSettings Settings; Settings.GravityCmPerSecondSquared = FVector::ZeroVector; Settings.WorkerThreads = 0;
        TestTrue(TEXT("Initialize"), S->InitializeSimulation(Settings).IsSuccess());
        TestNearlyEqual(TEXT("Native distance in cm"), L::GetJoltSpeculativeContactDistance(W), Distance, .00001f);
        TestFalse(TEXT("Negative rejected"), L::SetJoltSpeculativeContactDistance(W, -1.f));
        TestFalse(TEXT("NaN rejected"), L::SetJoltSpeculativeContactDistance(W, std::numeric_limits<float>::quiet_NaN()));
        TestFalse(TEXT("Infinity rejected"), L::SetJoltSpeculativeContactDistance(W, std::numeric_limits<float>::infinity()));
        TestNearlyEqual(TEXT("Invalid inputs preserve value"), L::GetJoltSpeculativeContactDistance(W), Distance, .00001f);
        TestTrue(TEXT("Independent slop setting"), UProphecyJoltContactSettingsLibrary::SetJoltPenetrationSlop(W, .25f));
        TestTrue(TEXT("Live zero accepted"), L::SetJoltSpeculativeContactDistance(W, 0.f));
        TestEqual(TEXT("Zero readback"), L::GetJoltSpeculativeContactDistance(W), 0.f);
        TestTrue(TEXT("Live distance restored"), L::SetJoltSpeculativeContactDistance(W, Distance));
        TestNearlyEqual(TEXT("Slop preserved"), UProphecyJoltContactSettingsLibrary::GetJoltPenetrationSlop(W), .25f, .00001f);
        FProphecyJoltBodyHandle Moving, Target;
        FProphecyJoltFixtureBodySettings Body; Body.PositionCm = FVector(-26, 0, 0);
        TestTrue(TEXT("Moving box"), S->CreateBox(FVector(10), .01f, Body, Moving).IsSuccess());
        Body.PositionCm = FVector::ZeroVector; Body.bDynamic = false;
        TestTrue(TEXT("Static box"), S->CreateBox(FVector(10), .01f, Body, Target).IsSuccess());
        TestTrue(TEXT("Set incoming velocity"), S->SetBodyVelocity(Moving, FVector(600, 0, 0), {}, true).IsSuccess());
        TestTrue(TEXT("Step"), S->Step(1.f / 60, 1).IsSuccess());
        FProphecyJoltBodyState State; TestTrue(TEXT("Read moving body"), S->ReadBody(Moving, State).IsSuccess());
        if (Distance == 11.f) TestTrue(TEXT("Wider search produces physical blocking this step"), State.PositionCm.X < -19.5);
        else TestTrue(TEXT("Default misses the initial six-cm gap"), State.PositionCm.X > -19.5);
        TestTrue(TEXT("Shutdown"), S->ShutdownSimulation().IsSuccess());
        TestTrue(TEXT("Reinitialize"), S->InitializeSimulation(Settings).IsSuccess());
        TestNearlyEqual(TEXT("Setting survives simulation recreation"), L::GetJoltSpeculativeContactDistance(W), Distance, .00001f);
        TestTrue(TEXT("Restore stock"), L::SetJoltSpeculativeContactDistance(W, 2.f));
        TestNearlyEqual(TEXT("Stock restored"), L::GetJoltSpeculativeContactDistance(W), 2.f, .00001f);
        W->DestroyWorld(false); if (GEngine) GEngine->DestroyWorldContext(W); W->MarkAsGarbage();
    }
    return !HasAnyErrors();
}
#endif
