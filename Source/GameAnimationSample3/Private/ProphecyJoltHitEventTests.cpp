#include "ProphecyHitEventTestSink.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltBody.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "PhysicsEngine/BodyInstance.h"
#include "UObject/StrongObjectPtr.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltHitEventsTest,
    "Prophecy.Jolt.HitEvents.SolvedImpulseAndLifetime",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltHitEventsTest::RunTest(const FString& Parameters)
{
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("World"), World)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    ON_SCOPE_EXIT { World->DestroyWorld(false); GEngine->DestroyWorldContext(World); World->MarkAsGarbage(); };
    auto* Owner = World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.MaxBodies = 8; Settings.MaxBodyPairs = 32; Settings.MaxContactConstraints = 32;
    Settings.WorkerThreads = 2;
    if (!TestTrue(TEXT("Initialize"), Owner->InitializeSimulation(Settings).IsSuccess())) return false;
    AActor* FloorActor = World->SpawnActor<AActor>();
    auto* FloorComponent = NewObject<UBoxComponent>(FloorActor);
    FloorActor->AddInstanceComponent(FloorComponent); FloorActor->SetRootComponent(FloorComponent);
    FloorComponent->RegisterComponent();
    AActor* BallActor = World->SpawnActor<AActor>();
    auto* BallComponent = NewObject<UBoxComponent>(BallActor);
    BallActor->AddInstanceComponent(BallComponent); BallActor->SetRootComponent(BallComponent);
    BallComponent->RegisterComponent();
    TStrongObjectPtr<UProphecyHitEventTestSink> Sink(NewObject<UProphecyHitEventTestSink>());
    BallComponent->OnComponentHit.AddDynamic(Sink.Get(), &UProphecyHitEventTestSink::ComponentHit);
    FProphecyJoltFixtureBodySettings Floor, Ball;
    Floor.bDynamic = false; Floor.PositionCm.Z = -5; Floor.AssociatedObject = FloorComponent;
    Ball.PositionCm.Z = 10; Ball.AssociatedObject = BallComponent; Ball.MassKg = 2;
    FProphecyJoltBodyHandle FloorHandle, BallHandle;
    if (!Owner->CreateSphere(10, Ball, BallHandle).IsSuccess()
        || !Owner->CreateBox(FVector(500,500,5), 0, Floor, FloorHandle).IsSuccess()) return false;
    constexpr float Dt = 1.0f / 60.0f;
    const auto Step = [&] { return TestTrue(TEXT("Step"), Owner->Step(Dt, 1).IsSuccess()); };
    if (!Step()) return false;
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Default-off dispatch"), Sink->ComponentHits, int64(0));
    Owner->SetBodyHitEvents(BallHandle, true);
    FProphecyJoltBodyState Before, After;
    Owner->ReadBody(BallHandle, Before);
    if (!Step()) return false;
    TestEqual(TEXT("No worker-thread delegate"), Sink->ComponentHits, int64(0));
    Owner->ReadBody(BallHandle, After);
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Existing resting contact emits on enable"), Sink->ComponentHits, int64(1));
    TestTrue(TEXT("Game thread only"), Sink->bOnlyGameThread);
    TestTrue(TEXT("Correct hit actor and component"), Sink->LastHit.GetActor() == FloorActor && Sink->LastHit.GetComponent() == FloorComponent);
    TestTrue(TEXT("Blocking hit with outward normal"), Sink->LastHit.bBlockingHit && Sink->LastHit.ImpactNormal.Z > 0.99);
    const double ExpectedImpulse = 2.0 * (After.CenterOfMassVelocityCmPerSecond.Z - Before.CenterOfMassVelocityCmPerSecond.Z + 981.0 * Dt);
    TestTrue(TEXT("Actual kg cm/s impulse matches momentum balance"), FMath::Abs(Sink->LastImpulse.Z - ExpectedImpulse) < 0.05);
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Drained only once"), Sink->ComponentHits, int64(1));
    Owner->SetBodyHitEvents(BallHandle, false);
    if (!Step()) return false;
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Disable stops delivery"), Sink->ComponentHits, int64(1));
    Owner->SetBodyHitEvents(BallHandle, true);
    if (!Step()) return false;
    // Exercise mutation during delivery: the other side must not receive stale handles.
    Owner->SetBodyHitEvents(FloorHandle, true);
    Sink->OnReceived = [&] { Owner->DestroyBody(FloorHandle); };
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Callback can remove contact body"), Sink->ComponentHits, int64(2));
    TestFalse(TEXT("Removed body stays invalid"), Owner->OwnsBody(FloorHandle));
    Sink->OnReceived = nullptr;
    Owner->DestroyBody(BallHandle);

    // CCD-only impact: a 1 m box crosses the entire floor in one step without CCD.
    if (!Owner->CreateBox(FVector(500,500,5), 0, Floor, FloorHandle).IsSuccess()) return false;
    auto* Cube = NewObject<UStaticMeshComponent>(BallActor);
    BallActor->AddInstanceComponent(Cube);
    Cube->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
    Cube->SetWorldLocation(FVector(0,0,150));
    Cube->SetCollisionProfileName(TEXT("PhysicsActor")); Cube->SetMobility(EComponentMobility::Movable);
    Cube->RegisterComponent(); Cube->SetSimulatePhysics(true);
    Cube->BodyInstance.SetUseCCD(true);
    Cube->SetPhysicsLinearVelocity(FVector(0,0,-12000));
    FProphecyJoltBodySnapshot Snapshot; FProphecyJoltPreparedBody Prepared; FString Error; TArray<FString> Notes;
    if (!ProphecyJolt::Body::CaptureLiveBody(*Cube, Snapshot, Error) || !Prepared.Build(Snapshot, Error)
        || !Owner->CreateBody(Snapshot, Prepared, BallHandle, Notes).IsSuccess()) { AddError(Error); return false; }
    Cube->OnComponentHit.AddDynamic(Sink.Get(), &UProphecyHitEventTestSink::ComponentHit);
    Owner->SetBodyHitEvents(BallHandle, true);
    const int64 BeforeCCD = Sink->ComponentHits;
    if (!Step()) return false;
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("CCD crossing emits a solved hit"), Sink->ComponentHits, BeforeCCD + 1);
    TestTrue(TEXT("CCD impulse opposes incoming motion"), Sink->LastImpulse.Z > 0 && Sink->LastHit.ImpactNormal.Z > 0.99);
    Owner->DestroyBody(BallHandle); Owner->DestroyBody(FloorHandle);
    Owner->ShutdownSimulation();
    return true;
}
#endif
