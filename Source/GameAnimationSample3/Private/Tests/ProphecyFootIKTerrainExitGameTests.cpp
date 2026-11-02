#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAgent.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace
{
class FFootIKTerrainExitGameExercise final : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    UWorld* World=nullptr;AProphecyNNLocomotionManager* Manager=nullptr;AProphecyAgent* Agent=nullptr;
    const FTransform Course{FRotator(0,37,0)};
    const double Started=FPlatformTime::Seconds();
    double NextTickAt=0,ExitSourceTime=-1,MaxCorrection=0,MaxRootStep=0,MaxPreviousEndpointError=0;
    double EpisodeCorrection=0;
    FString PeakDiagnostics;
    int32 Stage=0,Ticks=0,ReadyTicks=0,ExitTick=-1,FreshPolicies=0,LastExits=0;
    bool ConsumedSeed=false,SawReturn=false,ReturnRetired=false;
    FVector LastRoot=FVector::ZeroVector;
    TArray<FName> SeedNames;TArray<FTransform> Seed;
    FTransform SeedCarrier;
    TArray<double> RecentCorrections;
    TArray<TSharedPtr<FJsonValue>> Trace;
    void Box(FVector Center,FVector Extent,FQuat Rotation,FName Tag,bool FeetOnly=false)
    {
        auto* Actor=World->SpawnActor<AActor>();auto* Shape=NewObject<UBoxComponent>(Actor);Actor->SetRootComponent(Shape);
        Shape->SetBoxExtent(Extent);Shape->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Shape->SetCollisionObjectType(ECC_WorldStatic);
        Shape->SetCollisionResponseToAllChannels(ECR_Block);
        if(FeetOnly){Shape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);Shape->SetCollisionResponseToChannel(ECC_GameTraceChannel8,ECR_Ignore);}
        if(!Tag.IsNone())Shape->ComponentTags.Add(Tag);Shape->RegisterComponent();Actor->SetActorTransform(FTransform(Rotation,Center)*Course);
    }
    void Cleanup()
    {
        if(Agent){FString E;UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,E);}Agent=nullptr;Manager=nullptr;
        if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    bool Finish(bool Success,const FString& Why=FString())
    {
        auto O=MakeShared<FJsonObject>();O->SetBoolField(TEXT("success"),Success);O->SetStringField(TEXT("error"),Why);
        O->SetNumberField(TEXT("activeTicks"),Ticks);O->SetNumberField(TEXT("exitTick"),ExitTick);O->SetNumberField(TEXT("exits"),LastExits);
        O->SetNumberField(TEXT("correctedSeedCm"),MaxCorrection);O->SetNumberField(TEXT("maxRootStepCm"),MaxRootStep);
        O->SetNumberField(TEXT("episodeCorrectionCm"),EpisodeCorrection);O->SetStringField(TEXT("peakDiagnostics"),PeakDiagnostics);
        O->SetNumberField(TEXT("previousEndpointErrorCm"),MaxPreviousEndpointError);O->SetNumberField(TEXT("newPolicyPublications"),FreshPolicies);
        O->SetBoolField(TEXT("consumedCorrectedSeed"),ConsumedSeed);O->SetBoolField(TEXT("sawReturn"),SawReturn);O->SetBoolField(TEXT("returnRetired"),ReturnRetired);
        O->SetArrayField(TEXT("trace"),Trace);
        if(Agent){O->SetStringField(TEXT("liveDiagnostics"),ProphecyFootIKLive::DiagnosticSnapshot(Agent));O->SetNumberField(TEXT("localRootX"),Course.InverseTransformPosition(Agent->GetRootLowPoint()).X);}
        FString Json;FJsonSerializer::Serialize(O,TJsonWriterFactory<>::Create(&Json));const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");
        IFileManager::Get().MakeDirectory(*Dir,true);FFileHelper::SaveStringToFile(Json,*(Dir/TEXT("live-terrain-exit.json")));
        if(!Success)Test->AddError(TEXT("Live terrain exit: ")+Why);Cleanup();return true;
    }
public:
    explicit FFootIKTerrainExitGameExercise(FAutomationTestBase* T):Test(T){}
    ~FFootIKTerrainExitGameExercise(){Cleanup();}
    bool Update() override
    {
        const double Now=FPlatformTime::Seconds();if(Now-Started>900)return Finish(false,TEXT("Cold preparation watchdog expired"));
        if(Stage==0)
        {
            if(ProphecyFootIKLive::AnyEnabled())return Finish(false,TEXT("Requires isolated transient host"));
            const auto V=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&V);if(!World)return Finish(false,TEXT("Cannot create test world"));
            if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            Box(FVector(-150,0,-20),FVector(350,180,20),FQuat::Identity,NAME_None);
            Box(FVector(835,0,12),FVector(565,180,20),FQuat::Identity,NAME_None);
            const FQuat Q=FRotator(FMath::RadiansToDegrees(FMath::Atan(32./70)),0,0).Quaternion();
            Box(FVector(235,0,16)-Q.GetAxisZ()*5,FVector(FMath::Sqrt(70.*70+32.*32)/2,180,5),Q,TEXT("FootIKRoot"));
            for(int32 I=0;I<2;++I)Box(FVector(217.5+35*I,0,16*(I+1)-3),FVector(17.5,180,3),FQuat::Identity,TEXT("FootIKFeet"),true);
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();if(!Manager)return Finish(false,TEXT("Cannot spawn manager"));
            Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->EndpointAFallback=Course.TransformPosition(FVector(0,0,.1));Manager->EndpointBFallback=Course.TransformPosition(FVector(10000,0,.1));
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();Agent=Manager->ResolveAgent(Manager->GetAgentHandle(0));if(!Agent)return Finish(false,TEXT("No actual ordinary agent"));
            Agent->SetLocomotionInput(FVector::ZeroVector,false,Course.GetRotation().GetForwardVector());Stage=1;NextTickAt=Now;return false;
        }
        if(Now<NextTickAt)return false;NextTickAt=Now+1./60.;World->Tick(LEVELTICK_All,1.f/60);
        if(Stage==1)
        {
            if(++ReadyTicks<30)return false;FString E;
            if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"enabled\":true,\"terrain\":\"stairs\",\"gait\":\"walk\"}"),E)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,E))return Finish(false,E);
            Stage=2;return false;
        }
        FProphecyFootIKLiveState Status;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,Status))return Finish(false,TEXT("Live owner disappeared"));
        if(!Status.Error.IsEmpty())return Finish(false,Status.Error);
        if(Stage==2)
        {
            if(!Status.Ready)return false;
            Agent->SetLocomotionInput(Course.GetRotation().GetForwardVector(),false,Course.GetRotation().GetForwardVector());
            LastRoot=Agent->GetRootLowPoint();Stage=3;return false;
        }
        ++Ticks;const FVector Root=Agent->GetRootLowPoint();MaxRootStep=FMath::Max(MaxRootStep,FVector::Distance(Root,LastRoot));LastRoot=Root;
        if(Root.ContainsNaN()||MaxRootStep>12)return Finish(false,TEXT("Controller root teleported at terrain exit"));
        TArray<FName> Names,RawNames;TArray<FTransform> Future,Visible,RawFuture,Raw;float Alpha=0,RawAlpha=0;FProphecyNNPoseSnapshot Snapshot,RawSnapshot;
        if(!Agent->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Visible,Alpha,Snapshot,true)||!Agent->ReadNNFutureWorldPoseWithSnapshot(RawNames,RawFuture,Raw,RawAlpha,RawSnapshot,false)||Names!=RawNames)return Finish(false,TEXT("Missing actual pose publication"));
        double CurrentCorrection=0;
        for(FName Bone:{FName(TEXT("foot_l")),FName(TEXT("foot_r")),FName(TEXT("pelvis"))})
        {const int32 I=Names.IndexOfByKey(Bone);if(I==INDEX_NONE)return Finish(false,TEXT("Incomplete seed pose"));CurrentCorrection=FMath::Max(CurrentCorrection,FVector::Distance(Visible[I].GetLocation(),Raw[I].GetLocation()));}
        RecentCorrections.Add(CurrentCorrection);if(RecentCorrections.Num()>3)RecentCorrections.RemoveAt(0);
        if(CurrentCorrection>EpisodeCorrection){EpisodeCorrection=CurrentCorrection;PeakDiagnostics=Status.DiagnosticsJson;}
        auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("tick"),Ticks);Row->SetNumberField(TEXT("correctionCm"),CurrentCorrection);
        Row->SetNumberField(TEXT("applied"),Status.AppliedFrame);Row->SetNumberField(TEXT("through"),Status.PreparedThroughFrame);
        Row->SetNumberField(TEXT("rootX"),Course.InverseTransformPosition(Root).X);Trace.Add(MakeShared<FJsonValueObject>(Row));
        const int32 Exits=ProphecyFootIKGame::TerrainExits(Agent);
        if(Exits>LastExits)
        {
            if(Exits!=1||LastExits!=0)return Finish(false,TEXT("One finite stair exit reseeded repeatedly"));
            LastExits=Exits;ExitTick=Ticks;ExitSourceTime=RawSnapshot.SourceTimeSeconds;SeedNames=Names;Seed=Visible;SeedCarrier=RawSnapshot.ComponentWorldTransform;
            MaxCorrection=FMath::Max(CurrentCorrection,RecentCorrections.Num()==3?RecentCorrections[0]:0.);
            // Contact/whole-shoe clearance, not a minimum remaining correction,
            // decides the canonical exit. The terrain influence may already
            // have faded to zero. Still require a real corrected episode, then
            // compare the exact actual seed with the next policy predecessor.
            if(EpisodeCorrection<.01)return Finish(false,TEXT("No real terrain correction preceded the exit"));
        }
        SawReturn|=ProphecyFootIKGame::Returning(Agent);
        if(ExitTick>=0)
        {
            if(RawSnapshot.SourceTimeSeconds>ExitSourceTime+1.e-8)
            {
                ++FreshPolicies;ExitSourceTime=RawSnapshot.SourceTimeSeconds;
                if(!ConsumedSeed)
                {
                    if(RawSnapshot.PreviousComponentTransforms.Num()!=RawSnapshot.BoneNames.Num()||!RawSnapshot.bHasComponentWorldTransform)return Finish(false,TEXT("Next NN publication lost its predecessor"));
                    FString EndpointErrors;
                    for(FName Bone:{FName(TEXT("pelvis")),FName(TEXT("foot_l")),FName(TEXT("foot_r"))})
                    {
                        const int32 I=SeedNames.IndexOfByKey(Bone),J=RawSnapshot.BoneNames.IndexOfByKey(Bone);
                        if(I==INDEX_NONE||!RawSnapshot.PreviousComponentTransforms.IsValidIndex(J))return Finish(false,TEXT("Missing reseeded publication bone"));
                        const FTransform Previous=RawSnapshot.PreviousComponentTransforms[J]*RawSnapshot.PreviousComponentWorldTransform;
                        const FVector Delta=Previous.GetLocation()-Seed[I].GetLocation();
                        MaxPreviousEndpointError=FMath::Max(MaxPreviousEndpointError,Delta.Size());
                        EndpointErrors+=FString::Printf(TEXT(" %s=(%.9g,%.9g,%.9g)cm"),*Bone.ToString(),Delta.X,Delta.Y,Delta.Z);
                    }
                    const FVector CarrierDelta=RawSnapshot.PreviousComponentWorldTransform.GetLocation()-SeedCarrier.GetLocation();
                    EndpointErrors+=FString::Printf(TEXT(" carrier=(%.9g,%.9g,%.9g)cm"),CarrierDelta.X,CarrierDelta.Y,CarrierDelta.Z);
                    Test->AddInfo(TEXT("Terrain exit first publication:")+EndpointErrors);
                    if(MaxPreviousEndpointError>.05)return Finish(false,TEXT("Next real NN publication copied an uncorrected previous endpoint:")+EndpointErrors);ConsumedSeed=true;
                }
            }
            if(Ticks-ExitTick>=6)ReturnRetired=!ProphecyFootIKGame::Returning(Agent);
            if(Ticks-ExitTick>8&&!ReturnRetired)return Finish(false,TEXT("Velocity carry survived its0.10s transition"));
            if(Ticks-ExitTick>=20)
            {
                if(!SawReturn||!ReturnRetired||!ConsumedSeed||FreshPolicies<3)return Finish(false,TEXT("No complete real NN handoff/return lifecycle"));
                for(int32 I=0;I<Visible.Num();++I)if(!Visible[I].Equals(Raw[I],.01))return Finish(false,TEXT("Flat landing retained a terrain correction after NN return"));
                return Finish(true);
            }
        }
        if(Ticks>=360)return Finish(false,TEXT("No actual corrected terrain exit within six seconds of ordinary movement"));
        return false;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKTerrainExitGameTest,"Prophecy.FootIK.Live.TerrainExitGame",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKTerrainExitGameTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FFootIKTerrainExitGameExercise(this));return true;}
#endif
