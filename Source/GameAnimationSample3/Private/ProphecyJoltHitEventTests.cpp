#include "ProphecyHitEventTestSink.h"

#if WITH_DEV_AUTOMATION_TESTS
#include <limits>
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltHitImpactLibrary.h"
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
    struct FMotion
    {
        const UObject* Receiver=nullptr;
        double TipDistance=40.;
        FVector Velocity=FVector::ZeroVector,TipVelocity=FVector::ZeroVector;
        FVector AngularVelocityRad=FVector::ZeroVector,Location=FVector::ZeroVector;
        FRotator Rotation=FRotator::ZeroRotator;
        bool Valid=false;
    };
    static FMotion GetHitPreImpactState(const UObject* Receiver,double TipDistance=40.)
    {
        FMotion Params;Params.Receiver=Receiver;Params.TipDistance=TipDistance;
        UClass* Class=FindObject<UClass>(nullptr,TEXT("/Script/ProphecyJolt.ProphecyJoltHitImpactLibrary"));
        UFunction* Function=Class ? Class->FindFunctionByName(TEXT("GetHitPreImpactState")) : nullptr;
        if (Function) Class->GetDefaultObject()->ProcessEvent(Function,&Params);
        return Params;
    }
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
    HitImpactTest::FLibrary::FMotion IncomingMotion;
    Sink->OnReceived=[&] {
        IncomingValid=HitImpactTest::FLibrary::GetHitImpactSpeed(BallActor,IncomingSpeed,IncomingVelocity);
        IncomingMotion=HitImpactTest::FLibrary::GetHitPreImpactState(BallActor);
        TestTrue(TEXT("Pre-impact component receiver accepted"),HitImpactTest::FLibrary::GetHitPreImpactState(BallComponent).Valid);
        const auto Wrong=HitImpactTest::FLibrary::GetHitPreImpactState(FloorActor);
        TestTrue(TEXT("Wrong pre-impact receiver returns false/zeros"),!Wrong.Valid && Wrong.Velocity.IsZero()
            && Wrong.TipVelocity.IsZero() && Wrong.AngularVelocityRad.IsZero() && Wrong.Location.IsZero() && Wrong.Rotation.IsZero());
        TestFalse(TEXT("Invalid tip distance rejected"),HitImpactTest::FLibrary::GetHitPreImpactState(BallActor,std::numeric_limits<double>::infinity()).Valid);
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
    TestTrue(TEXT("All five incoming values available"),IncomingMotion.Valid);
    TestTrue(TEXT("Rewind keeps incoming velocity before collision response"),FMath::Abs(IncomingMotion.Velocity.Z+IncomingSpeed)<0.1);
    TestTrue(TEXT("First hit rewinds one full tick without requiring history"),
        IncomingMotion.Location.Equals(Ball.PositionCm-FVector(0,0,-IncomingSpeed)*Dt,.01) && IncomingMotion.Rotation.IsNearlyZero());
    TestTrue(TEXT("No angular motion means tip speed equals origin speed"),IncomingMotion.AngularVelocityRad.IsNearlyZero()
        && IncomingMotion.TipVelocity.Equals(IncomingMotion.Velocity,.001));
    TestFalse(TEXT("No stale five-value snapshot outside event"),HitImpactTest::FLibrary::GetHitPreImpactState(BallActor).Valid);
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
    TestTrue(TEXT("World radians preserved"),IncomingMotion.Valid && FMath::Abs(IncomingMotion.AngularVelocityRad.Y-2.)<.02);
    TestTrue(TEXT("Tip rotation contributes expected 80 cm/s"),FMath::Abs((IncomingMotion.TipVelocity-IncomingMotion.Velocity).X-80.)<1.);
    TestTrue(TEXT("World angular velocity rewinds orientation"),
        IncomingMotion.Rotation.Quaternion().Equals(FQuat(FVector::RightVector,-2.*Dt),.0001));
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
    HitImpactTest::FLibrary::FMotion OtherMotion;
    OtherSink->OnReceived=[&] {
        OtherValid=HitImpactTest::FLibrary::GetHitImpactSpeed(FloorActor,OtherSpeed,OtherVelocity);
        OtherMotion=HitImpactTest::FLibrary::GetHitPreImpactState(FloorActor);
    };
    IncomingValid=false;
    if(!Step())return false;
    Owner->DispatchPendingHitEvents();
    TestTrue(TEXT("Moving target subtracted"),IncomingValid && FMath::Abs(IncomingSpeed-100.)<0.1);
    TestTrue(TEXT("Both receivers share speed and opposite relative velocities"),OtherValid && FMath::Abs(OtherSpeed-IncomingSpeed)<0.001 && (OtherVelocity+IncomingVelocity).Size()<0.001);
    TestTrue(TEXT("Each side gets its own absolute motion"),IncomingMotion.Valid && OtherMotion.Valid
        && FMath::Abs(IncomingMotion.Velocity.Z-OtherMotion.Velocity.Z+100.)<.1
        && IncomingMotion.Location.Equals(Ball.PositionCm-IncomingMotion.Velocity*Dt,.01)
        && OtherMotion.Location.Equals(Floor.PositionCm-OtherMotion.Velocity*Dt,.01));
    Owner->DestroyBody(BallHandle);Owner->DestroyBody(FloorHandle);

    // Kinematic swords still carry their requested incoming motion, not a zero/static read.
    if(!Owner->CreateSphere(10,Floor,FloorHandle).IsSuccess()
        || !Owner->CreateSphere(10,Ball,BallHandle).IsSuccess())return false;
    if(!Owner->SetBodyKinematic(BallHandle).IsSuccess()
        || !Owner->MoveKinematicBody(BallHandle,FTransform(FQuat::Identity,Ball.PositionCm-FVector(0,0,2)),Dt).IsSuccess())return false;
    Owner->SetBodyHitEvents(BallHandle,true);
    IncomingMotion={};
    if(!Step())return false;
    Owner->DispatchPendingHitEvents();
    TestTrue(TEXT("Kinematic incoming motion retained"),IncomingMotion.Valid && FMath::Abs(IncomingMotion.Velocity.Z+120.)<.1);
    Owner->DestroyBody(BallHandle);Owner->DestroyBody(FloorHandle);
    Floor.bDynamic=false;Floor.PositionCm.Z=-5;
    if(!Owner->CreateBox(FVector(500,500,5),0,Floor,FloorHandle).IsSuccess())return false;
    Sink->OnReceived=nullptr;OtherSink->OnReceived=nullptr;

    // A welded sword reports its own component origin/orientation, not the carrier hand.
    for (bool Reverse : {false,true})
    {
        Owner->DestroyBody(FloorHandle);
        FProphecyJoltFixtureBodySettings Hand=Ball,Sword=Ball;
        Hand.PositionCm=FVector(0,0,31);Hand.MassKg=2.;
        Sword.PositionCm=FVector(30,0,11);Sword.AssociatedObject=BallComponent;
        Hand.AssociatedObject=nullptr;
        FProphecyJoltBodyHandle HandHandle;
        const FTransform Offset(FQuat(FVector::RightVector,UE_HALF_PI),FVector(30,0,-20));
        auto MakeFloor=[&] { return Owner->CreateBox(FVector(500,500,5),0,Floor,FloorHandle).IsSuccess(); };
        if (Reverse && !MakeFloor()) return false;
        if (!Owner->CreateSphere(2,Hand,HandHandle).IsSuccess()
            || !Owner->CreateBox(FVector(10),0,Sword,BallHandle).IsSuccess()
            || !Owner->WeldBodyShape(HandHandle,BallHandle,Offset).IsSuccess()) return false;
        if (!Reverse && !MakeFloor()) return false;
        Owner->SetBodyVelocity(HandHandle,FVector(0,0,-100),FVector(0,2,0),true);
        Owner->SetBodyHitEvents(BallHandle,true);
        FProphecyJoltBodyState WeldedBefore;
        Owner->ReadBody(HandHandle,WeldedBefore);
        IncomingMotion={};
        Sink->OnReceived=[&] { IncomingMotion=HitImpactTest::FLibrary::GetHitPreImpactState(BallComponent); };
        if (!Step()) return false;
        Owner->DispatchPendingHitEvents();
        const FQuat Rewind(FVector::RightVector,-2.*Dt);
        const FVector InitialCenter=WeldedBefore.CenterOfMassPositionCm;
        const FVector RewoundCenter=InitialCenter-FVector(0,0,-100.-981.*Dt)*Dt;
        const FVector ExpectedOrigin=RewoundCenter+Rewind.RotateVector(Sword.PositionCm-InitialCenter);
        TestTrue(TEXT("Welded rewind rotates sword lever arm around carrier COM"),IncomingMotion.Valid
            && IncomingMotion.Location.Equals(ExpectedOrigin,.02)
            && IncomingMotion.Rotation.Quaternion().Equals(Rewind*Offset.GetRotation(),.001));
        TestTrue(TEXT("Rotated welded tip includes angular lever arm"),
            FMath::Abs((IncomingMotion.TipVelocity-IncomingMotion.Velocity).Z+80.)<1.);
        Owner->DestroyBody(BallHandle);Owner->DestroyBody(HandHandle);
    }
    Sink->OnReceived=nullptr;

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
    Sink->OnReceived=[&] {
        IncomingValid=HitImpactTest::FLibrary::GetHitImpactSpeed(Cube,IncomingSpeed,IncomingVelocity);
        IncomingMotion=HitImpactTest::FLibrary::GetHitPreImpactState(Cube);
    };
    IncomingValid=false;
    if (!Step()) return false;
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("CCD crossing emits a solved hit"), Sink->ComponentHits, BeforeCCD + 1);
    TestTrue(TEXT("CCD impulse opposes incoming motion"), Sink->LastImpulse.Z > 0 && Sink->LastHit.ImpactNormal.Z > 0.99);
    TestTrue(TEXT("CCD pre-impact speed available"),IncomingValid && IncomingSpeed>11900. && IncomingSpeed<12100.);
    TestTrue(TEXT("CCD absolute pre-impact motion available"),IncomingMotion.Valid && IncomingMotion.Velocity.Z<-11900.
        && IncomingMotion.TipVelocity.Equals(IncomingMotion.Velocity,.01));
    Owner->DestroyBody(BallHandle);
    // Establish a slow tick, then hit at a new speed/spin during later substeps.
    // The estimate must use this contact's incoming motion, never stale history.
    Snapshot.CaptureId=FGuid::NewGuid();
    Snapshot.Body.CenterOfMassVelocityCmPerSecond=FVector(0,0,-600);
    Snapshot.Body.AngularVelocityRadiansPerSecond=FVector::ZeroVector;
    if (!Prepared.Build(Snapshot,Error)
        || !Owner->CreateBody(Snapshot,Prepared,BallHandle,Notes).IsSuccess()) return false;
    Owner->SetBodyHitEvents(BallHandle,true);
    const int64 BeforeRewind=Sink->ComponentHits;
    if (!Step()) return false;
    Owner->DispatchPendingHitEvents();
    TestEqual(TEXT("Slow tick is clear of the floor"),Sink->ComponentHits,BeforeRewind);
    FProphecyJoltBodyState PreviousTick;
    Owner->ReadBody(BallHandle,PreviousTick);
    Owner->SetBodyVelocity(BallHandle,FVector(0,0,-12000),FVector(0,1,0),true);
    IncomingMotion={};IncomingValid=false;
    if (!Owner->Step(Dt,4).IsSuccess()) return false;
    Owner->DispatchPendingHitEvents();
    TestTrue(TEXT("Next tick crosses floor during substeps"),Sink->ComponentHits>BeforeRewind);
    TestTrue(TEXT("Impact speed remains collision-time"),IncomingValid && IncomingSpeed>11000.);
    TestTrue(TEXT("CCD rewind uses full tick interval, not just last substep"),IncomingMotion.Valid
        && IncomingMotion.Location.Z>PreviousTick.PositionCm.Z+50.);
    TestTrue(TEXT("Rewind velocity responds to new incoming speed"),IncomingMotion.Velocity.Z<-11000.);
    TestTrue(TEXT("Rewind angular velocity responds to new spin"),FMath::Abs(IncomingMotion.AngularVelocityRad.Y-1.)<.02);
    TestTrue(TEXT("Rewound tip velocity uses rewound orientation"),
        IncomingMotion.TipVelocity.Equals(IncomingMotion.Velocity+FVector::CrossProduct(
            IncomingMotion.AngularVelocityRad,IncomingMotion.Rotation.Quaternion().GetAxisZ()*40.),.001));
    Sink->OnReceived=nullptr;
    Owner->DestroyBody(BallHandle); Owner->DestroyBody(FloorHandle);
    Owner->ShutdownSimulation();
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCleanPikeTest,
    "Prophecy.Jolt.HitEvents.CleanPike", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyCleanPikeTest::RunTest(const FString&)
{
    using L=UProphecyJoltHitImpactLibrary;
    for(int Mode=0;Mode<6;++Mode)
    {
        const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
            .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
            .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
        auto* W=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(W);
        ON_SCOPE_EXIT {W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();};
        auto* S=W->GetSubsystem<UProphecyJoltWorldSubsystem>();
        FProphecyJoltWorldSettings Settings;Settings.WorkerThreads=2;
        if(!S->InitializeSimulation(Settings).IsSuccess())return false;
        auto Component=[&](){auto* A=W->SpawnActor<AActor>();auto* C=NewObject<UBoxComponent>(A);
            A->AddInstanceComponent(C);A->SetRootComponent(C);C->RegisterComponent();return C;};
        auto* C=Component();auto* FloorC=Component();auto* OtherC=Component();
        FProphecyJoltFixtureBodySettings Body,Floor;
        Body.PositionCm=FVector(0,0,Mode==1?40:9);Body.AssociatedObject=C;
        Floor.bDynamic=false;Floor.PositionCm=FVector(0,0,-5);Floor.AssociatedObject=FloorC;
        FProphecyJoltBodyHandle B,F,Reference,Wall;
        if(!S->CreateSphere(10,Body,B).IsSuccess()||!S->CreateBox(FVector(100,100,5),0,Floor,F).IsSuccess())return false;
        Body.PositionCm.X=1000;Body.AssociatedObject=nullptr;
        if(!S->CreateSphere(10,Body,Reference).IsSuccess())return false;
        const FVector V(Mode==4?-200:0,0,Mode==1?-4000:-600),Omega(0,2,0);
        S->SetBodyVelocity(B,V,Omega,true);S->SetBodyVelocity(Reference,V,Omega,true);
        if(Mode==1)S->SetBodyRuntimeSettings(B,true,0,0,true);
        if(Mode==4){Floor.PositionCm=FVector(-10,0,20);Floor.AssociatedObject=OtherC;
            S->CreateBox(FVector(5,100,100),0,Floor,Wall);}
        S->SetBodyHitEvents(B,true);
        if(Mode!=2)L::EnableCleanHitContinuation(C,true);
        FString Reason;TestFalse(TEXT("Outside Hit refuses"),L::AcceptPikeHit(C,Reason));
        TStrongObjectPtr<UProphecyHitEventTestSink> Sink(NewObject<UProphecyHitEventTestSink>());
        C->OnComponentHit.AddDynamic(Sink.Get(),&UProphecyHitEventTestSink::ComponentHit);
        bool Accepted=false;
        Sink->OnReceived=[&]{
            TestFalse(TEXT("Wrong receiver refuses"),L::AcceptPikeHit(OtherC,Reason));
            if(Mode!=3)Accepted=L::AcceptPikeHit(C,Reason);
            if(Accepted)TestTrue(TEXT("Duplicate call is idempotent"),L::AcceptPikeHit(C,Reason));
        };
        if(!S->Step(1.f/60,Mode==5?2:1).IsSuccess())return false;
        FProphecyJoltBodyState Solved,After,Free;S->ReadBody(B,Solved);
        S->DispatchPendingHitEvents();S->ReadBody(B,After);S->ReadBody(Reference,Free);
        TestTrue(TEXT("Fixture emits a hit"),Sink->ComponentHits>0);
        if(Mode<2)
        {
            TestTrue(*FString::Printf(TEXT("Accepted mode%d: %s"),Mode,*Reason),Accepted);
            TestTrue(TEXT("Continues at free-flight position"),After.PositionCm.Equals(Free.PositionCm-FVector(1000,0,0),.01));
            TestTrue(TEXT("Restores incoming velocity without adding"),After.CenterOfMassVelocityCmPerSecond.Equals(Free.CenterOfMassVelocityCmPerSecond,.01));
            TestTrue(TEXT("Spin uses radians and integrates once"),After.Rotation.Equals(Free.Rotation,1.e-5)
                &&After.AngularVelocityRadiansPerSecond.Equals(Free.AngularVelocityRadiansPerSecond,.001));
            TestTrue(TEXT("Visual component updated in callback"),C->GetComponentLocation().Equals(After.PositionCm,.01));
        }
        else
        {
            TestFalse(TEXT("Disabled/rejected/ambiguous/substepped hit remains normal"),Accepted);
            TestTrue(TEXT("Rejected continuation leaves native state intact"),After.PositionCm.Equals(Solved.PositionCm,1.e-6)
                &&After.CenterOfMassVelocityCmPerSecond.Equals(Solved.CenterOfMassVelocityCmPerSecond,1.e-6));
        }
        L::EnableCleanHitContinuation(C,false);Sink->OnReceived=nullptr;S->ShutdownSimulation();
    }
    return true;
}
#endif
