#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Async/Async.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltWorldSubsystem.h"

#include <limits>

namespace ProphecyJolt::QueryTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

class FScopedWorld final
{
public:
    FScopedWorld()
    {
        const UWorld::InitializationValues Values = UWorld::InitializationValues()
            .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false)
            .CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
            .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
        World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (World && GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    }
    ~FScopedWorld()
    {
        if (!World) return;
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
        World->MarkAsGarbage();
    }
    UProphecyJoltWorldSubsystem* Get() const { return World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr; }
private:
    UWorld* World = nullptr;
};

bool Okay(FAutomationTestBase& Test, const TCHAR* Context, const FProphecyJoltWorldStatus& Status)
{
    if (Status.IsSuccess()) return true;
    Test.AddError(FString::Printf(TEXT("%s: result %u: %s"), Context, static_cast<uint32>(Status.Code), *Status.Message));
    return false;
}

FProphecyJoltWorldSettings SmallWorld()
{
    FProphecyJoltWorldSettings Settings;
    Settings.MaxBodies = 8;
    Settings.MaxBodyPairs = 64;
    Settings.MaxContactConstraints = 64;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    return Settings;
}

bool SameHandle(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltClosestQueryTest,
    "Prophecy.Jolt.Query.ClosestHitsNormalsAndArguments", ProphecyJolt::QueryTests::Flags)

bool FProphecyJoltClosestQueryTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::QueryTests;
    FScopedWorld Scope;
    UProphecyJoltWorldSubsystem* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Game world subsystem"), Owner)) return false;
    const FVector Start(-100.0, 0.0, 100.0), End(400.0, 0.0, 100.0);
    FProphecyJoltRayHit Hit;
    bool bHit = true;
    TestTrue(TEXT("Uninitialized query is rejected"), Owner->RayCast(Start, End, Hit, bHit).Code == EProphecyJoltWorldResult::NotInitialized);
    TestFalse(TEXT("Rejected query clears hit flag"), bHit);
    if (!Okay(*this, TEXT("Initialize query fixture"), Owner->InitializeSimulation(SmallWorld()))) return false;
    FProphecyJoltFixtureBodySettings SphereSettings;
    SphereSettings.PositionCm = FVector(0.0, 0.0, 100.0);
    FProphecyJoltFixtureBodySettings BoxSettings;
    BoxSettings.PositionCm = FVector(300.0, 0.0, 100.0);
    BoxSettings.Rotation = FQuat(FVector::UpVector, UE_HALF_PI);
    BoxSettings.bDynamic = false;
    FProphecyJoltBodyHandle Sphere, Box;
    if (!Okay(*this, TEXT("Create dynamic sphere"), Owner->CreateSphere(25.0, SphereSettings, Sphere))
        || !Okay(*this, TEXT("Create rotated static box"), Owner->CreateBox(FVector(20.0, 40.0, 60.0), 0.0, BoxSettings, Box))) return false;

    if (!Okay(*this, TEXT("Cast through both bodies"), Owner->RayCast(Start, End, Hit, bHit))
        || !TestTrue(TEXT("Segment hits"), bHit)) return false;
    TestTrue(TEXT("Closest body wins over farther box"), SameHandle(Hit.Handle, Sphere));
    TestNearlyEqual(TEXT("Sphere hit position in centimeters"), Hit.PositionCm, FVector(-25.0, 0.0, 100.0), 1.0e-3f);
    TestNearlyEqual(TEXT("Sphere outward world normal"), Hit.Normal, FVector(-1.0, 0.0, 0.0), 1.0e-5f);
    TestNearlyEqual(TEXT("Fraction uses full segment length"), Hit.Fraction, 0.15f, 1.0e-5f);
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Resolve ray hit as body handle"), Owner->ReadBody(Hit.Handle, State))) return false;
    TestNearlyEqual(TEXT("Query does not advance body pose"), State.PositionCm, SphereSettings.PositionCm, 1.0e-6f);

    if (!Okay(*this, TEXT("Cast along rotated box local X"), Owner->RayCast(FVector(300.0, -100.0, 100.0), FVector(300.0, 100.0, 100.0), Hit, bHit))
        || !TestTrue(TEXT("Static layer is queryable"), bHit)) return false;
    TestTrue(TEXT("Box hit resolves its adapter identity"), SameHandle(Hit.Handle, Box));
    TestNearlyEqual(TEXT("Rotated box surface position"), Hit.PositionCm, FVector(300.0, -20.0, 100.0), 1.0e-3f);
    TestNearlyEqual(TEXT("Box normal is world space"), Hit.Normal, FVector(0.0, -1.0, 0.0), 1.0e-5f);
    TestNearlyEqual(TEXT("Box segment fraction"), Hit.Fraction, 0.4f, 1.0e-5f);

    if (!Okay(*this, TEXT("Miss outside both bodies"), Owner->RayCast(Start + FVector(0.0, 500.0, 0.0), End + FVector(0.0, 500.0, 0.0), Hit, bHit))) return false;
    TestFalse(TEXT("Miss clears hit flag"), bHit);
    TestFalse(TEXT("Miss clears earlier body identity"), Hit.Handle.IsSet());
    TestNearlyEqual(TEXT("Miss clears earlier hit point"), Hit.PositionCm, FVector::ZeroVector, 1.0e-6f);
    TestTrue(TEXT("Zero-length segment is rejected"), Owner->RayCast(Start, Start, Hit, bHit).Code == EProphecyJoltWorldResult::InvalidArgument);
    const FVector Invalid(std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0);
    TestTrue(TEXT("Non-finite endpoint is rejected"), Owner->RayCast(Start, Invalid, Hit, bHit).Code == EProphecyJoltWorldResult::InvalidArgument);
    TestFalse(TEXT("Invalid input retains no hit"), bHit);
    const EProphecyJoltWorldResult WorkerResult = Async(EAsyncExecution::ThreadPool, [Owner, Start, End]()
    {
        FProphecyJoltRayHit WorkerHit;
        bool bWorkerHit = true;
        return Owner->RayCast(Start, End, WorkerHit, bWorkerHit).Code;
    }).Get();
    TestTrue(TEXT("Query rejects worker-thread access"), WorkerResult == EProphecyJoltWorldResult::WrongThread);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltMovedQueryTest,
    "Prophecy.Jolt.Query.MovedPoseAndHandleLifetime", ProphecyJolt::QueryTests::Flags)

bool FProphecyJoltMovedQueryTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::QueryTests;
    FScopedWorld Scope;
    UProphecyJoltWorldSubsystem* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Game world subsystem"), Owner)
        || !Okay(*this, TEXT("Initialize moving fixture"), Owner->InitializeSimulation(SmallWorld()))) return false;
    FProphecyJoltFixtureBodySettings Settings;
    Settings.PositionCm = FVector(0.0, 0.0, 100.0);
    FProphecyJoltBodyHandle Original;
    if (!Okay(*this, TEXT("Create moving sphere"), Owner->CreateSphere(25.0, Settings, Original))) return false;
    FProphecyJoltRayHit Hit;
    bool bHit = false;
    const FVector Start(-100.0, 0.0, 100.0), End(100.0, 0.0, 100.0);
    if (!Okay(*this, TEXT("Query initial position"), Owner->RayCast(Start, End, Hit, bHit))
        || !TestTrue(TEXT("Initial sphere hit"), bHit)) return false;
    TestTrue(TEXT("Initial hit identity"), SameHandle(Hit.Handle, Original));
    if (!Okay(*this, TEXT("Apply center impulse"), Owner->AddPointImpulse(Original, FVector(0.0, 1000.0, 0.0), Settings.PositionCm))
        || !Okay(*this, TEXT("Advance moving sphere"), Owner->Step(0.1f, 1))) return false;
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Read integrated position"), Owner->ReadBody(Original, State))) return false;
    TestNearlyEqual(TEXT("Sphere moved one meter sideways"), State.PositionCm, FVector(0.0, 100.0, 100.0), 1.0e-3f);
    if (!Okay(*this, TEXT("Query former position"), Owner->RayCast(Start, End, Hit, bHit))) return false;
    TestFalse(TEXT("Broad and narrow phase no longer hit old pose"), bHit);
    const FVector Offset(0.0, 100.0, 0.0);
    if (!Okay(*this, TEXT("Query integrated position"), Owner->RayCast(Start + Offset, End + Offset, Hit, bHit))
        || !TestTrue(TEXT("Current native position hits"), bHit)) return false;
    TestNearlyEqual(TEXT("Hit follows integrated sphere"), Hit.PositionCm, FVector(-25.0, 100.0, 100.0), 1.0e-3f);
    TestTrue(TEXT("Motion retains generation identity"), SameHandle(Hit.Handle, Original));
    const FProphecyJoltBodyHandle StaleHit = Hit.Handle;
    if (!Okay(*this, TEXT("Destroy body through ray handle"), Owner->DestroyBody(StaleHit))) return false;
    TestTrue(TEXT("Destroyed hit handle becomes invalid"), Owner->ReadBody(StaleHit, State).Code == EProphecyJoltWorldResult::InvalidHandle);
    if (!Okay(*this, TEXT("Query removed body"), Owner->RayCast(Start + Offset, End + Offset, Hit, bHit))) return false;
    TestFalse(TEXT("Removed body does not remain queryable"), bHit);
    Settings.PositionCm += Offset;
    FProphecyJoltBodyHandle Replacement;
    if (!Okay(*this, TEXT("Reuse slot for replacement box"), Owner->CreateBox(FVector(10.0), 0.0, Settings, Replacement))
        || !Okay(*this, TEXT("Query replacement"), Owner->RayCast(Start + Offset, End + Offset, Hit, bHit))
        || !TestTrue(TEXT("Replacement box hit"), bHit)) return false;
    TestEqual(TEXT("Adapter slot was reused"), Replacement.Slot, StaleHit.Slot);
    TestTrue(TEXT("Replacement has a new generation"), Replacement.Generation > StaleHit.Generation);
    TestTrue(TEXT("Ray returns current replacement identity"), SameHandle(Hit.Handle, Replacement));
    TestTrue(TEXT("Old ray identity stays stale after reuse"), Owner->ReadBody(StaleHit, State).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestNearlyEqual(TEXT("Query uses replacement geometry"), Hit.PositionCm, FVector(-10.0, 100.0, 100.0), 1.0e-3f);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
