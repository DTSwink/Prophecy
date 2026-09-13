#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Async/Async.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltShapeAsset.h"
#include "UObject/Package.h"

namespace ProphecyJolt::WorldTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

class FScopedWorld final
{
public:
    explicit FScopedWorld(EWorldType::Type Type = EWorldType::Game)
    {
        const UWorld::InitializationValues Values = UWorld::InitializationValues()
            .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false)
            .CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
            .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
        World = UWorld::CreateWorld(Type, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (World && GEngine) GEngine->CreateNewWorldContext(Type).SetCurrentWorld(World);
    }
    ~FScopedWorld() { Destroy(); }
    void Destroy()
    {
        if (!World) return;
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
        World->MarkAsGarbage();
        World = nullptr;
    }
    UProphecyJoltWorldSubsystem* Get() const { return World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr; }
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
    Settings.MaxBodies = 16;
    Settings.MaxBodyPairs = 128;
    Settings.MaxContactConstraints = 128;
    return Settings;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltWorldIsolationTest, "Prophecy.Jolt.WorldSubsystem.LifecycleAndExplicitStep", ProphecyJolt::WorldTests::Flags)

bool FProphecyJoltWorldIsolationTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::WorldTests;
    const int32 InitialLive = UProphecyJoltWorldSubsystem::GetLiveSimulationCount();
    {
        FScopedWorld Editor(EWorldType::Editor);
        TestNotNull(TEXT("Editor fixture created"), Editor.World);
        TestNull(TEXT("Editor worlds have no Jolt owner"), Editor.Get());
        FScopedWorld Falling;
        FScopedWorld Still;
        if (!TestNotNull(TEXT("First Game world subsystem"), Falling.Get())
            || !TestNotNull(TEXT("Second Game world subsystem"), Still.Get())) return false;
        FProphecyJoltWorldDiagnostics Before;
        Okay(*this, TEXT("Read lazy diagnostics"), Falling.Get()->GetDiagnostics(Before));
        TestFalse(TEXT("Subsystem creation does not allocate a simulation"), Before.bInitialized);
        TestEqual(TEXT("No lazy world native owners"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialLive);
        TestTrue(TEXT("Step rejects absent initialization"), Falling.Get()->Step(1.0f / 60.0f, 1).Code == EProphecyJoltWorldResult::NotInitialized);
        FProphecyJoltWorldSettings Gravity = SmallWorld();
        FProphecyJoltWorldSettings NoGravity = Gravity;
        NoGravity.GravityCmPerSecondSquared = FVector::ZeroVector;
        if (!Okay(*this, TEXT("Initialize falling world"), Falling.Get()->InitializeSimulation(Gravity))
            || !Okay(*this, TEXT("Initialize still world"), Still.Get()->InitializeSimulation(NoGravity))) return false;
        TestEqual(TEXT("Two independent native owners"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialLive + 2);
        FProphecyJoltFixtureBodySettings Body;
        Body.PositionCm = FVector(0.0, 0.0, 500.0);
        FProphecyJoltBodyHandle FallingHandle, StillHandle;
        if (!Okay(*this, TEXT("Create falling sphere"), Falling.Get()->CreateSphere(50.0, Body, FallingHandle))
            || !Okay(*this, TEXT("Create still sphere"), Still.Get()->CreateSphere(50.0, Body, StillHandle))) return false;
        TestTrue(TEXT("World lifetime IDs differ"), FallingHandle.WorldLifetime != StillHandle.WorldLifetime);
        FProphecyJoltBodyState State;
        TestTrue(TEXT("Cross-world handles rejected"), Falling.Get()->ReadBody(StillHandle, State).Code == EProphecyJoltWorldResult::InvalidHandle);
        // These are real engine world ticks. This subsystem has no tick callback and cannot advance physics.
        Falling.World->Tick(LEVELTICK_All, 1.0f / 30.0f);
        Still.World->Tick(LEVELTICK_All, 1.0f / 30.0f);
        if (!Okay(*this, TEXT("Read after ordinary world tick"), Falling.Get()->ReadBody(FallingHandle, State))) return false;
        TestNearlyEqual(TEXT("World tick leaves Jolt pose unchanged"), State.PositionCm, Body.PositionCm, 1.0e-6f);
        FProphecyJoltWorldDiagnostics NoStep;
        Okay(*this, TEXT("Read zero-step diagnostics"), Falling.Get()->GetDiagnostics(NoStep));
        TestEqual(TEXT("World tick does not count an explicit step"), NoStep.CompletedSteps, uint64(0));
        for (int32 Index = 0; Index < 12; ++Index)
        {
            if (!Okay(*this, TEXT("Explicit falling step"), Falling.Get()->Step(1.0f / 60.0f, 1))
                || !Okay(*this, TEXT("Explicit zero-gravity step"), Still.Get()->Step(1.0f / 60.0f, 1))) return false;
        }
        Okay(*this, TEXT("Read fallen body"), Falling.Get()->ReadBody(FallingHandle, State));
        TestTrue(TEXT("Explicit stepping applies gravity"), State.PositionCm.Z < 485.0);
        Okay(*this, TEXT("Read isolated body"), Still.Get()->ReadBody(StillHandle, State));
        TestNearlyEqual(TEXT("Other world retains its gravity setting"), State.PositionCm, Body.PositionCm, 1.0e-6f);
        FProphecyJoltWorldDiagnostics After;
        Okay(*this, TEXT("Read stepped diagnostics"), Falling.Get()->GetDiagnostics(After));
        TestEqual(TEXT("Exactly twelve caller steps"), After.CompletedSteps, uint64(12));
        TestNearlyEqual(TEXT("Requested time is accumulated without cadence substitution"), After.SimulatedSeconds, 12.0 * static_cast<double>(1.0f / 60.0f), 1.0e-9);
        TestTrue(TEXT("Temporary allocation peak recorded"), After.TempPeakBytes > 0);
        TestEqual(TEXT("Temporary allocations released after step"), After.TempCurrentBytes, uint64(0));
        TestEqual(TEXT("No update error bits"), After.LastUpdateErrorBits, uint32(0));
        Falling.Destroy(); // Neither test world began play; deinitialize must still clean native state.
        TestEqual(TEXT("World cleanup releases its owner without BeginPlay"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialLive + 1);
    }
    TestEqual(TEXT("All native worlds cleaned"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialLive);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltWorldHandlesTest, "Prophecy.Jolt.WorldSubsystem.HandlesCapacityAndReinitialize", ProphecyJolt::WorldTests::Flags)

bool FProphecyJoltWorldHandlesTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::WorldTests;
    const int32 InitialLive = UProphecyJoltWorldSubsystem::GetLiveSimulationCount();
    {
        FScopedWorld Scope;
        UProphecyJoltWorldSubsystem* Owner = Scope.Get();
        if (!TestNotNull(TEXT("Game subsystem"), Owner)) return false;
        FProphecyJoltWorldSettings Settings = SmallWorld();
        Settings.MaxBodies = 1;
        Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
        if (!Okay(*this, TEXT("Initialize capacity fixture"), Owner->InitializeSimulation(Settings))) return false;
        TestTrue(TEXT("Implicit reconfiguration rejected"), Owner->InitializeSimulation(Settings).Code == EProphecyJoltWorldResult::AlreadyInitialized);
        TestTrue(TEXT("Zero interval rejected"), Owner->Step(0.0f, 1).Code == EProphecyJoltWorldResult::InvalidArgument);
        TestTrue(TEXT("Zero collision steps rejected"), Owner->Step(1.0f / 60.0f, 0).Code == EProphecyJoltWorldResult::InvalidArgument);
        FProphecyJoltFixtureBodySettings Body;
        Body.AssociatedObject = NewObject<UProphecyJoltShapeAsset>(Scope.World);
        FProphecyJoltBodyHandle First, Second;
        TestTrue(TEXT("Nonpositive sphere rejected"), Owner->CreateSphere(0.0, Body, First).Code == EProphecyJoltWorldResult::InvalidArgument);
        TestFalse(TEXT("Rejected creation leaves no handle"), First.IsSet());
        if (!Okay(*this, TEXT("Create associated body"), Owner->CreateSphere(50.0, Body, First))) return false;
        UObject* Association = nullptr;
        Okay(*this, TEXT("Resolve associated object"), Owner->ResolveAssociatedObject(First, Association));
        TestTrue(TEXT("Registry association preserves identity"), Association == Body.AssociatedObject);
        TestTrue(TEXT("Capacity rejected before extra Jolt body"), Owner->CreateSphere(50.0, Body, Second).Code == EProphecyJoltWorldResult::CapacityExceeded);
        TestFalse(TEXT("Capacity failure has no body handle"), Second.IsSet());
        FProphecyJoltWorldDiagnostics Capacity;
        Okay(*this, TEXT("Capacity diagnostics"), Owner->GetDiagnostics(Capacity));
        TestEqual(TEXT("Failed creation counted"), Capacity.BodyCreationFailures, uint64(1));
        TestEqual(TEXT("Existing body retained after capacity failure"), Capacity.BodyCount, uint32(1));
        if (!Okay(*this, TEXT("Remove first body"), Owner->DestroyBody(First))
            || !Okay(*this, TEXT("Reuse freed capacity"), Owner->CreateSphere(50.0, Body, Second))) return false;
        TestEqual(TEXT("Adapter slot reused"), First.Slot, Second.Slot);
        TestTrue(TEXT("Adapter generation advances"), Second.Generation > First.Generation);
        FProphecyJoltBodyState State;
        TestTrue(TEXT("Removed handle is stale after slot reuse"), Owner->ReadBody(First, State).Code == EProphecyJoltWorldResult::InvalidHandle);
        Body.AssociatedObject->MarkAsGarbage();
        TestTrue(TEXT("Weak association expires"), Owner->ResolveAssociatedObject(Second, Association).Code == EProphecyJoltWorldResult::AssociationUnavailable);
        TestNull(TEXT("Expired association has no raw output"), Association);
        Body.AssociatedObject = nullptr;
        if (!Okay(*this, TEXT("Explicit shutdown"), Owner->ShutdownSimulation())
            || !Okay(*this, TEXT("Repeated shutdown"), Owner->ShutdownSimulation())
            || !Okay(*this, TEXT("Reinitialize stopped fixture"), Owner->InitializeSimulation(Settings))) return false;
        FProphecyJoltBodyHandle Third;
        if (!Okay(*this, TEXT("Body in new lifetime"), Owner->CreateSphere(50.0, Body, Third))) return false;
        TestTrue(TEXT("Reinitialization changes lifetime identity"), Third.WorldLifetime != Second.WorldLifetime);
        TestTrue(TEXT("Prior-lifetime handle rejected"), Owner->ReadBody(Second, State).Code == EProphecyJoltWorldResult::InvalidHandle);
        const EProphecyJoltWorldResult WorkerResult = Async(EAsyncExecution::ThreadPool, [Owner, Third]()
        {
            UObject* Object = nullptr;
            return Owner->ResolveAssociatedObject(Third, Object).Code;
        }).Get();
        TestTrue(TEXT("Worker thread cannot resolve a UObject association"), WorkerResult == EProphecyJoltWorldResult::WrongThread);
        Owner->OnWorldEndPlay(*Scope.World);
        TestTrue(TEXT("End play prevents reinitialization"), Owner->InitializeSimulation(Settings).Code == EProphecyJoltWorldResult::WorldEnding);
        Owner->OnWorldEndPlay(*Scope.World); // Idempotent; world cleanup also invokes PreDeinitialize/Deinitialize.
        TestEqual(TEXT("End play has already released native owner"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialLive);
    }
    TestEqual(TEXT("Teardown after explicit end play is clean"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialLive);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltWorldBodyFixtureTest, "Prophecy.Jolt.WorldSubsystem.BoxCollisionAndPointImpulse", ProphecyJolt::WorldTests::Flags)

bool FProphecyJoltWorldBodyFixtureTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::WorldTests;
    FScopedWorld Scope;
    UProphecyJoltWorldSubsystem* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Game subsystem"), Owner)
        || !Okay(*this, TEXT("Initialize body fixture"), Owner->InitializeSimulation(SmallWorld()))) return false;
    FProphecyJoltFixtureBodySettings Floor;
    Floor.bDynamic = false;
    Floor.PositionCm = FVector(0.0, 0.0, -25.0);
    FProphecyJoltBodyHandle FloorHandle, SphereHandle;
    TestTrue(TEXT("Oversized convex radius rejected without clamping"), Owner->CreateBox(FVector(25.0), 30.0, Floor, FloorHandle).Code == EProphecyJoltWorldResult::InvalidArgument);
    if (!Okay(*this, TEXT("Create floor box"), Owner->CreateBox(FVector(500.0, 500.0, 25.0), 0.0, Floor, FloorHandle))) return false;
    TestTrue(TEXT("Static point impulse rejected"), Owner->AddPointImpulse(FloorHandle, FVector(0.0, 100.0, 0.0), FVector::ZeroVector).Code == EProphecyJoltWorldResult::InvalidArgument);
    FProphecyJoltFixtureBodySettings Sphere;
    Sphere.MassKg = 2.0;
    Sphere.PositionCm = FVector(0.0, 0.0, 300.0);
    if (!Okay(*this, TEXT("Create dynamic sphere"), Owner->CreateSphere(50.0, Sphere, SphereHandle))
        || !Okay(*this, TEXT("Point impulse"), Owner->AddPointImpulse(SphereHandle, FVector(0.0, 200.0, 0.0), FVector(100.0, 0.0, 300.0)))) return false;
    FProphecyJoltBodyState State;
    Okay(*this, TEXT("Read impulsed sphere"), Owner->ReadBody(SphereHandle, State));
    TestNearlyEqual(TEXT("Point impulse preserves J/m linear units"), State.CenterOfMassVelocityCmPerSecond, FVector(0.0, 100.0, 0.0), 1.0e-3f);
    TestNearlyEqual(TEXT("Point impulse creates correct angular velocity"), State.AngularVelocityRadiansPerSecond, FVector(0.0, 0.0, 10.0), 1.0e-4f);
    for (int32 Index = 0; Index < 180; ++Index)
        if (!Okay(*this, TEXT("Advance collision fixture"), Owner->Step(1.0f / 60.0f, 1))) return false;
    Okay(*this, TEXT("Read supported sphere"), Owner->ReadBody(SphereHandle, State));
    AddInfo(FString::Printf(TEXT("Supported sphere final position cm=%s, velocity cm/s=%s"),
        *State.PositionCm.ToString(), *State.CenterOfMassVelocityCmPerSecond.ToString()));
    // Pinned Jolt allows 2 cm penetration slop. The measured resting center is
    // 47.986 cm, so retain that setting and allow 1 cm of numerical margin.
    TestTrue(TEXT("Sphere supported within Jolt penetration slop plus margin"), FMath::Abs(State.PositionCm.Z - 50.0) < 3.0);
    TestTrue(TEXT("Supported sphere has settled vertically"), FMath::Abs(State.CenterOfMassVelocityCmPerSecond.Z) < 1.0);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
