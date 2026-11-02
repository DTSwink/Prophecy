#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltPhysicsCommand.h"
#include "ProphecyJoltWorldSubsystem.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltReleaseScheduleTest,"Prophecy.Jolt.Bodyflip.FractionalRelease",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyJoltReleaseScheduleTest::RunTest(const FString&)
{
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);if(!TestNotNull(TEXT("world"),World))return false;if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* P=World->GetSubsystem<UProphecyJoltWorldSubsystem>();bool Okay=true;auto Check=[&](const FProphecyJoltWorldStatus& S){if(!S.IsSuccess()){AddError(S.Message);Okay=false;}return S.IsSuccess();};
    FProphecyJoltWorldSettings Config;Config.GravityCmPerSecondSquared=FVector::ZeroVector;Config.MaxBodies=8;Config.MaxBodyPairs=Config.MaxContactConstraints=64;Config.WorkerThreads=1;
    if(P&&Check(P->InitializeSimulation(Config)))
    {
        FProphecyJoltBodyHandle Existing,Released;FProphecyJoltFixtureBodySettings Body;Body.MassKg=2;Body.PositionCm=FVector(0,0,1000);Check(P->CreateSphere(1,Body,Existing));FProphecyJoltPhysicsCommand Force;Force.Operation=EProphecyJoltPhysicsCommand::Force;Force.Value=FVector(1000,0,0);Check(P->ExecutePhysicsCommand(Existing,Force));
        FProphecyJoltStepSchedule Schedule;Schedule.Fractions={.37};double ReleasedAt=-1;int Calls=0;Schedule.Before=[&](double Fraction,double){Calls++;if(Fraction>=.37-1.e-9&&!Released.IsSet()){ReleasedAt=Fraction;FProphecyJoltFixtureBodySettings Spawn;auto S=P->CreateSphere(1,Spawn,Released);if(!S.IsSuccess())return S;return P->SetBodyVelocity(Released,FVector(100,0,0),FVector::ZeroVector,true);}return FProphecyJoltWorldStatus{};};
        Check(P->Step(.1f,4,&Schedule));FProphecyJoltBodyState A,B;Check(P->ReadBody(Existing,A));Check(P->ReadBody(Released,B));TestTrue(TEXT("fractional release exactly at cut"),FMath::Abs(ReleasedAt-.37)<1.e-9);TestTrue(TEXT("only remainder advances projectile"),FMath::Abs(B.PositionCm.X-6.3)<.001);TestTrue(TEXT("other client's force lasts full step"),FMath::Abs(A.CenterOfMassVelocityCmPerSecond.X-50)<.001);
        FProphecyJoltWorldDiagnostics D;Check(P->GetDiagnostics(D));TestEqual(TEXT("one shared publication"),D.CompletedSteps,uint64(1));TestEqual(TEXT("one callback per native interval plus endpoint"),Calls,6);
        Check(P->Step(.1f,4));Check(P->GetDiagnostics(D));TestEqual(TEXT("ordinary step still one publication"),D.CompletedSteps,uint64(2));
        FProphecyJoltBodyState Saved,Paused,Resumed;Check(P->ReadBody(Released,Saved));Force.Value=FVector(10000,0,0);Check(P->ExecutePhysicsCommand(Released,Force));
        Check(P->RestoreBodyState(Released,Saved,true));Check(P->Step(.1f,4));Check(P->ReadBody(Released,Paused));TestTrue(TEXT("paused body stays at recorded pose"),Paused.PositionCm.Equals(Saved.PositionCm,1.e-5));
        Check(P->RestoreBodyState(Released,Saved,false));Check(P->Step(.1f,4));Check(P->ReadBody(Released,Resumed));TestTrue(TEXT("resume restores velocity without stale queued force"),Resumed.CenterOfMassVelocityCmPerSecond.Equals(Saved.CenterOfMassVelocityCmPerSecond,1.e-4));
        Saved.bActive=false;Saved.CenterOfMassVelocityCmPerSecond=Saved.AngularVelocityRadiansPerSecond=FVector::ZeroVector;Check(P->RestoreBodyState(Released,Saved,false));Check(P->ReadBody(Released,Resumed));TestFalse(TEXT("recorded sleeping state restored"),Resumed.bActive);
        Check(P->SetBodyGyroscopic(Released,true));
        // Small Throw releases just after a regular 240 Hz boundary. Inserting
        // that cut into the old uniform grid made a roughly 10 microsecond step.
        // The exact release must survive without creating that accidental sliver.
        constexpr double NearGrid=.250596693937478;
        FProphecyJoltStepSchedule Near;Near.Fractions={NearGrid};
        FProphecyJoltBodyHandle NearBody;double NearReleasedAt=-1,MinDt=1,MaxDt=0,TotalDt=0;
        Near.Before=[&](double Fraction,double Dt)
        {
            if(Dt>0){MinDt=FMath::Min(MinDt,Dt);MaxDt=FMath::Max(MaxDt,Dt);TotalDt+=Dt;}
            if(Fraction>=NearGrid-1.e-9&&!NearBody.IsSet())
            {
                NearReleasedAt=Fraction;FProphecyJoltFixtureBodySettings Spawn;Spawn.PositionCm=FVector(0,100,0);
                auto S=P->CreateSphere(1,Spawn,NearBody);if(!S.IsSuccess())return S;
                return P->SetBodyVelocity(NearBody,FVector(100,0,0),FVector::ZeroVector,true);
            }
            return FProphecyJoltWorldStatus{};
        };
        constexpr float Frame=1.f/60.f;Check(P->Step(Frame,4,&Near));Check(P->ReadBody(NearBody,B));
        TestTrue(TEXT("near-grid release remains exact"),FMath::Abs(NearReleasedAt-NearGrid)<1.e-12);
        TestTrue(TEXT("near-grid cut has no accidental tiny interval"),MinDt>=double(Frame)/8.);
        TestTrue(TEXT("release intervals respect maximum collision step"),MaxDt<=double(Frame)/4.+1.e-9);
        TestTrue(TEXT("release intervals cover the full frame"),FMath::Abs(TotalDt-Frame)<1.e-8);
        TestTrue(TEXT("near-grid projectile advances only after release"),FMath::Abs(B.PositionCm.X-100.*Frame*(1.-NearGrid))<.001);
        Check(P->ShutdownSimulation());
    }else Okay=false;
    World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();return Okay;
}
#endif
