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

namespace HitImpactTest
{
// Exercise the actual Blueprint call path, also avoiding a new cross-module
// import that Live Coding cannot resolve until a normal editor relink.
struct FLibrary
{
    static bool GetHitImpactSpeed(const UObject* Receiver,double& Speed,FVector& Velocity)
    {
        struct FParams { const UObject* Receiver; double Speed=0.; FVector Velocity=FVector::ZeroVector; bool Valid=false; } Params{Receiver};
        UClass* Class=FindObject<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltHitImpactLibrary"));
        UFunction* Function=Class ? Class->FindFunctionByName(TEXT("GetHitImpactSpeed")) : nullptr;
        if (Function) Class->GetDefaultObject()->ProcessEvent(Function,&Params);
        Speed=Params.Speed;Velocity=Params.Velocity;return Params.Valid;
    }
};
}

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

    if (!Owner->CreateBox(FVector(500,500,5), 0, Floor, FloorHandle).IsSuccess()) return false;
    // A normal solver impulse must notify gameplay even at a speculative gap:
    // otherwise a strike can be physically stopped without a Hit event.
    Ball.PositionCm.Z=11;
    double IncomingSpeed=-1.;FVector IncomingVelocity;bool IncomingValid=false;
    Sink->OnReceived=[&] {
        IncomingValid=HitImpactTest::FLibrary::GetHitImpactSpeed(BallActor,IncomingSpeed,IncomingVelocity);
        double Speed=0.;FVector Velocity;
        TestTrue(TEXT("Receiver component also accepted"),HitImpactTest::FLibrary::GetHitImpactSpeed(BallComponent,Speed,Velocity));
        TestFalse(TEXT("Wrong receiver rejected"),HitImpactTest::FLibrary::GetHitImpactSpeed(FloorActor,Speed,Velocity));
        TestEqual(TEXT("Invalid output cleared"),Speed,0.);
    };
    if(!Owner->CreateSphere(10,Ball,BallHandle).IsSuccess())return false;
    Owner->SetBodyVelocity(BallHandle,FVector(0,0,-100),FVector::ZeroVector,true);
    Owner->SetBodyHitEvents(BallHandle,true);
    const int64 BeforeSpeculative=Sink->ComponentHits;
    if(!Step())return false;
    Owner->ReadBody(BallHandle,After);
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Solved speculative blocking impulse emits a gameplay hit"),Sink->ComponentHits,BeforeSpeculative+1);
    TestTrue(TEXT("Speculative hit carries actual outward impulse"),Sink->LastImpulse.Z>0. && Sink->LastHit.bBlockingHit);
    TestTrue(TEXT("Speculative prevention still changes velocity"),After.CenterOfMassVelocityCmPerSecond.Z>-100.);
    TestTrue(TEXT("Incoming sample available"),IncomingValid);
    TestTrue(TEXT("Captured before solver response, including gravity"),FMath::Abs(IncomingSpeed-(100.+981.*Dt))<0.1);
    TestTrue(TEXT("Incoming relative point velocity orientation"),FMath::Abs(IncomingVelocity.Z+IncomingSpeed)<0.1);
    double OutsideSpeed=123.;FVector OutsideVelocity(123.);
    TestFalse(TEXT("No stale sample outside event"),HitImpactTest::FLibrary::GetHitImpactSpeed(BallActor,OutsideSpeed,OutsideVelocity));
    TestTrue(TEXT("Outside outputs cleared"),OutsideSpeed==0. && OutsideVelocity.IsZero());
    const int64 AfterSpeculative=Sink->ComponentHits;
    for(int32 I=0;I<3 && Sink->ComponentHits==AfterSpeculative;++I)
    { if(!Step())return false;Owner->DispatchPendingHitEvents(); }
    TestTrue(TEXT("Subsequent touching contact still emits"),Sink->ComponentHits>AfterSpeculative);
    Owner->DestroyBody(BallHandle);

    // Rotation contributes at an off-centre contact even with zero COM velocity.
    Ball.PositionCm.Z=10;
    if(!Owner->CreateBox(FVector(10),0,Ball,BallHandle).IsSuccess())return false;
    Owner->SetBodyVelocity(BallHandle,FVector::ZeroVector,FVector(0,2,0),true);
    Owner->SetBodyHitEvents(BallHandle,true);
    IncomingValid=false;
    if(!Step())return false;
    Owner->DispatchPendingHitEvents();
    TestTrue(TEXT("Angular contact speed captured"),IncomingValid && IncomingSpeed>30. && IncomingSpeed<40.);
    Owner->DestroyBody(BallHandle);

    // Both bodies move: use closing speed, not attacker's absolute speed.
    Owner->DestroyBody(FloorHandle);
    Floor.bDynamic=true;Floor.MassKg=2;Floor.PositionCm.Z=0;
    Ball.PositionCm.Z=21;
    if(!Owner->CreateSphere(10,Floor,FloorHandle).IsSuccess() || !Owner->CreateSphere(10,Ball,BallHandle).IsSuccess())return false;
    Owner->SetBodyVelocity(FloorHandle,FVector(0,0,-100),FVector::ZeroVector,true);
    Owner->SetBodyVelocity(BallHandle,FVector(0,0,-200),FVector::ZeroVector,true);
    Owner->SetBodyHitEvents(BallHandle,true);Owner->SetBodyHitEvents(FloorHandle,true);
    TStrongObjectPtr<UProphecyHitEventTestSink> OtherSink(NewObject<UProphecyHitEventTestSink>());
    FloorComponent->OnComponentHit.AddDynamic(OtherSink.Get(),&UProphecyHitEventTestSink::ComponentHit);
    double OtherSpeed=-1.;FVector OtherVelocity;bool OtherValid=false;
    OtherSink->OnReceived=[&] { OtherValid=HitImpactTest::FLibrary::GetHitImpactSpeed(FloorActor,OtherSpeed,OtherVelocity); };
    IncomingValid=false;
    if(!Step())return false;
    Owner->DispatchPendingHitEvents();
    TestTrue(TEXT("Moving target subtracted"),IncomingValid && FMath::Abs(IncomingSpeed-100.)<0.1);
    TestTrue(TEXT("Both receivers share speed and opposite relative velocities"),OtherValid && FMath::Abs(OtherSpeed-IncomingSpeed)<0.001 && (OtherVelocity+IncomingVelocity).Size()<0.001);
    Owner->DestroyBody(BallHandle);Owner->DestroyBody(FloorHandle);
    Floor.bDynamic=false;Floor.PositionCm.Z=-5;
    if(!Owner->CreateBox(FVector(500,500,5),0,Floor,FloorHandle).IsSuccess())return false;
    Sink->OnReceived=nullptr;OtherSink->OnReceived=nullptr;

    // CCD-only impact: a 1 m box crosses the entire floor in one step without CCD.
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
    Sink->OnReceived=[&] { IncomingValid=HitImpactTest::FLibrary::GetHitImpactSpeed(Cube,IncomingSpeed,IncomingVelocity); };
    IncomingValid=false;
    if (!Step()) return false;
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("CCD crossing emits a solved hit"), Sink->ComponentHits, BeforeCCD + 1);
    TestTrue(TEXT("CCD impulse opposes incoming motion"), Sink->LastImpulse.Z > 0 && Sink->LastHit.ImpactNormal.Z > 0.99);
    TestTrue(TEXT("CCD pre-impact speed available"),IncomingValid && IncomingSpeed>11900. && IncomingSpeed<12100.);
    Sink->OnReceived=nullptr;
    Owner->DestroyBody(BallHandle); Owner->DestroyBody(FloorHandle);
    Owner->ShutdownSimulation();
    return true;
}
#endif
