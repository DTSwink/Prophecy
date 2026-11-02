#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyBodyflipProjectiles.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipProjectileTest,"Prophecy.Bodyflip.ProjectileGeometry",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipProjectileTest::RunTest(const FString&)
{
    FString Text;TSharedPtr<FJsonObject> Data;if(!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectContentDir()/TEXT("BodyflipLab/Projectiles.json")))||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data)){AddError(TEXT("Package Bodyflip Projectiles.json before running"));return false;}
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);if(!World)return false;if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);auto* Physics=World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Config;Config.GravityCmPerSecondSquared=FVector::ZeroVector;Config.MaxBodies=8;Config.MaxBodyPairs=Config.MaxContactConstraints=64;bool Okay=Physics&&Physics->InitializeSimulation(Config).IsSuccess();FString Error;
    if(Okay)for(const FString Kind:{TEXT("spear"),TEXT("bomb")})
    {
        FProphecyBodyflipProjectiles P;if(!P.Initialize(World,FTransform::Identity,Error)){AddError(Error);Okay=false;break;}
        auto Array=[](std::initializer_list<double> Values){TArray<TSharedPtr<FJsonValue>> Out;for(double V:Values)Out.Add(MakeShared<FJsonValueNumber>(V));return Out;};
        auto Launch=MakeShared<FJsonObject>();Launch->SetStringField(TEXT("id"),Kind);Launch->SetStringField(TEXT("kind"),Kind);Launch->SetArrayField(TEXT("p"),Array({0,1,0}));Launch->SetArrayField(TEXT("q"),Array({0,0,0,1}));Launch->SetArrayField(TEXT("v"),Array({1,0,0}));Launch->SetArrayField(TEXT("omega"),Array({0,0,0}));Launch->SetArrayField(TEXT("scale"),Data->GetObjectField(TEXT("physical"))->GetObjectField(Kind)->GetArrayField(TEXT("scale")));Launch->SetNumberField(TEXT("releaseTime"),.037);auto Aero=MakeShared<FJsonObject>();Aero->SetBoolField(TEXT("enabled"),false);Launch->SetObjectField(TEXT("aero"),Aero);
        auto Result=MakeShared<FJsonObject>();Result->SetBoolField(TEXT("zeroGravity"),true);Result->SetArrayField(TEXT("releases"),{MakeShared<FJsonValueObject>(Launch)});if(!P.Update(Result,.1,Error)){AddError(Error);Okay=false;break;}
        FProphecyJoltStepSchedule Schedule;TestTrue(TEXT("shared-world schedule exists"),ProphecyBodyflip::ProjectileStepSchedule(World,Schedule));const auto Status=Physics->Step(.1f,4,&Schedule);if(!Status.IsSuccess()){AddError(Status.Message);Okay=false;break;}
        AActor* Visual=nullptr;for(TActorIterator<AActor> It(World);It;++It)if(It->ActorHasTag(FName(*Kind)))Visual=*It;
        if(TestNotNull(*FString::Printf(TEXT("%s exact-geometry visual"),*Kind),Visual)){TestTrue(TEXT("fractional native flight"),FMath::Abs(Visual->GetActorLocation().X-6.3)<.01);TestTrue(TEXT("Y-up to UE Z-up placement"),FMath::Abs(Visual->GetActorLocation().Z-100)<.01);}
        if(!Visual){Okay=false;break;}
        if(!P.Update(Result,.2,Error)){AddError(Error);Okay=false;break;}Schedule={};ProphecyBodyflip::ProjectileStepSchedule(World,Schedule);Physics->Step(.1f,4,&Schedule);
        TestTrue(TEXT("second recorded frame advances from release"),FMath::Abs(Visual->GetActorLocation().X-16.3)<.01);
        FProphecyJoltBodyHandle Other;FProphecyJoltFixtureBodySettings OtherSettings;OtherSettings.PositionCm=FVector(1000,0,0);Physics->CreateSphere(1,OtherSettings,Other);Physics->SetBodyVelocity(Other,FVector(50,0,0),FVector::ZeroVector,true);
        Schedule={};ProphecyBodyflip::ProjectileStepSchedule(World,Schedule);P.SetPaused(true);Physics->Step(.1f,4,&Schedule);FProphecyJoltBodyState OtherBefore,OtherAfter;Physics->ReadBody(Other,OtherBefore);FProphecyJoltWorldDiagnostics Before,After;Physics->GetDiagnostics(Before);
        const FVector BeforeFailedSeek=Visual->GetActorLocation();TestFalse(TEXT("uncomputed future preflight fails"),P.CanSeek(Result,.3,Error));TestFalse(TEXT("uncomputed future seek fails"),P.Seek(Result,.3,Error));TestTrue(TEXT("failed seek leaves owned pose unchanged"),Visual->GetActorLocation().Equals(BeforeFailedSeek));
        auto ChangedLaunch=MakeShared<FJsonObject>(*Launch);ChangedLaunch->SetArrayField(TEXT("v"),Array({2,0,0}));auto Changed=MakeShared<FJsonObject>(*Result);Changed->SetArrayField(TEXT("releases"),{MakeShared<FJsonValueObject>(ChangedLaunch)});TestFalse(TEXT("changed launch cannot reuse cached physics"),P.Seek(Changed,.1,Error));TestTrue(TEXT("changed-launch rejection preserves pose"),Visual->GetActorLocation().Equals(BeforeFailedSeek));
        ChangedLaunch->SetArrayField(TEXT("v"),Array({1+1.e-10,0,0}));TestTrue(TEXT("floating-point recomputation noise preserves cached launch"),P.CanSeek(Changed,.1,Error));
        Error.Reset();TestTrue(TEXT("recorded rewind succeeds"),P.Seek(Result,.1,Error));TestTrue(TEXT("rewind restores actual flight, not release"),FMath::Abs(Visual->GetActorLocation().X-6.3)<.01);
        TestTrue(TEXT("recorded forward seek succeeds"),P.Seek(Result,.2,Error));TestTrue(TEXT("forward seek restores actual flight"),FMath::Abs(Visual->GetActorLocation().X-16.3)<.01);
        auto Held=MakeShared<FJsonObject>();Held->SetBoolField(TEXT("zeroGravity"),true);Held->SetArrayField(TEXT("releases"),{});Held->SetArrayField(TEXT("held"),{MakeShared<FJsonValueObject>(Launch)});
        TestTrue(TEXT("pre-release seek removes physical flight"),P.Seek(Held,.02,Error));TestTrue(TEXT("recorded state survives pre-release rewind"),P.Seek(Result,.2,Error));
        Physics->ReadBody(Other,OtherAfter);Physics->GetDiagnostics(After);TestTrue(TEXT("seeks do not move unrelated bodies"),OtherBefore.PositionCm.Equals(OtherAfter.PositionCm));TestEqual(TEXT("seeks never step shared world"),After.CompletedSteps,Before.CompletedSteps);
        P.SetPaused(false);P.Update(Result,.3,Error);Schedule={};ProphecyBodyflip::ProjectileStepSchedule(World,Schedule);Physics->Step(.1f,4,&Schedule);
        Visual=nullptr;for(TActorIterator<AActor> It(World);It;++It)if(It->ActorHasTag(FName(*Kind))&&!It->IsActorBeingDestroyed())Visual=*It;
        TestNotNull(TEXT("restored visual exists"),Visual);if(Visual)TestTrue(TEXT("resume keeps recorded velocity"),FMath::Abs(Visual->GetActorLocation().X-26.3)<.01);
        P.InvalidateHistory();TestFalse(TEXT("scene edits invalidate old collision history"),P.CanSeek(Result,.1,Error));P.Reset();Schedule={};TestFalse(TEXT("teardown removes only own projectile schedule"),ProphecyBodyflip::ProjectileStepSchedule(World,Schedule));TestTrue(TEXT("unrelated body survives reset"),Physics->OwnsBody(Other));Physics->DestroyBody(Other);
    }
    if(Physics)Physics->ShutdownSimulation();World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();return Okay;
}
#endif
