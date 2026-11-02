#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAgent.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "Components/BoxComponent.h"
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
const FName LiveBones[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
struct FLiveCommand {const TCHAR* Name;FVector Move,Facing;bool Run;int32 Ticks;};
// Ordinary game NN and mover remain active. The test does not supply a course,
// prerecorded pose, alternate world tick callback or authored root trajectory.
class FFootIKLiveGameExercise final:public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    UWorld* World=nullptr;
    AProphecyNNLocomotionManager* Manager=nullptr;
    AProphecyAgent* Agent=nullptr;
    const double Started=FPlatformTime::Seconds();
    double NextTickAt=0,SourceTime=-1,MaxSolveMs=0,MaxRootStep=0,MaxReadError=0,MaxUpperError=0,MaxTerrainCorrectionCm=0;
    int32 Stage=0,Ticks=0,Phase=0,PolicyUpdates=0,Published=0,PhasePublished=0,LastApplied=-1,ZeroSteps=0,PreparationTicks=0;
    int32 WorldTicks=0,LastPublicationTick=-1,FallbackTicks=0,FallbackRun=0,MaxFallbackRun=0,RenewedFrames=0;
    int32 PhaseVerifiedIdentityStart=0,PhaseCandidateStart=0;
    bool WarmReady=false;
    uint32 LastRevision=0;
    FVector PreviousRoot=FVector::ZeroVector,PhaseRoot=FVector::ZeroVector;
    TArray<TSharedPtr<FJsonValue>> Reports;
    const FLiveCommand Commands[5]={
        {TEXT("moving-walk-enable"),FVector::ForwardVector,FVector::ForwardVector,false,180},
        {TEXT("facing-turn"),FVector::ForwardVector,FVector::RightVector,false,120},
        {TEXT("reverse-run"),-FVector::ForwardVector,FVector::ForwardVector,true,180},
        {TEXT("stop"),FVector::ZeroVector,FVector::ForwardVector,true,60},
        {TEXT("resume-run"),FVector::ForwardVector,FVector::ForwardVector,true,120}};

    void Cleanup()
    {
        if(Agent){FString Error;UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error);}
        Agent=nullptr;Manager=nullptr;
        if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    void Save(bool Success,const FString& Error=FString())
    {
        auto Report=MakeShared<FJsonObject>();Report->SetBoolField(TEXT("success"),Success);Report->SetStringField(TEXT("error"),Error);
        Report->SetStringField(TEXT("source"),TEXT("real manager + actual NN history/future roots; no recorded course"));
        Report->SetNumberField(TEXT("policyUpdates"),PolicyUpdates);Report->SetNumberField(TEXT("resolvedFrames"),Published);
        Report->SetNumberField(TEXT("maxSolveMs"),MaxSolveMs);Report->SetNumberField(TEXT("maxRootStepCm"),MaxRootStep);
        Report->SetNumberField(TEXT("maxTerrainCorrectionCm"),MaxTerrainCorrectionCm);
        Report->SetNumberField(TEXT("fallbackTicks"),FallbackTicks);Report->SetNumberField(TEXT("maxConsecutiveFallbackTicks"),MaxFallbackRun);Report->SetNumberField(TEXT("renewedFrames"),RenewedFrames);
        Report->SetNumberField(TEXT("maxSingleBodyReadErrorCm"),MaxReadError);Report->SetNumberField(TEXT("maxUpperRotationErrorRad"),MaxUpperError);Report->SetArrayField(TEXT("phases"),Reports);
        if(Agent){TSharedPtr<FJsonObject> Diagnostic;if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ProphecyFootIKLive::DiagnosticSnapshot(Agent)),Diagnostic)&&Diagnostic)Report->SetObjectField(TEXT("liveDiagnostics"),Diagnostic);}
        FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));
        const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");IFileManager::Get().MakeDirectory(*Directory,true);
        FFileHelper::SaveStringToFile(Text,*(Directory/TEXT("live-game-lifecycle.json")));
    }
    bool Fail(const FString& Error)
    {Test->AddError(TEXT("Live Foot IK: ")+Error);Save(false,Error);Cleanup();return true;}
    bool CheckReads(bool ExpectDisabled,FString& Error)
    {
        TArray<FName> RawNames,VisibleNames;TArray<FTransform> RawFuture,Raw,Future,Visible;
        FProphecyNNPoseSnapshot Before,After;float RawAlpha=0,Alpha=0;
        if(!Agent->ReadNNFutureWorldPoseWithSnapshot(RawNames,RawFuture,Raw,RawAlpha,Before,false)||
           !Agent->ReadNNFutureWorldPoseWithSnapshot(VisibleNames,Future,Visible,Alpha,After,true))
        {Error=TEXT("Ordinary game NN did not publish a complete pose");return false;}
        if(RawNames!=VisibleNames||Before.Revision!=After.Revision||Before.SourceTimeSeconds!=After.SourceTimeSeconds||RawAlpha!=Alpha||RawFuture.Num()!=Future.Num())
        {Error=TEXT("Reading the terrain overlay altered NN source metadata");return false;}
        if(Before.ComponentTransforms.Num()!=After.ComponentTransforms.Num()||Before.PreviousComponentTransforms.Num()!=After.PreviousComponentTransforms.Num())
        {Error=TEXT("Terrain overlay changed the recurrent history shape");return false;}
        for(int32 I=0;I<Before.ComponentTransforms.Num();++I)
            if(!Before.ComponentTransforms[I].Equals(After.ComponentTransforms[I],0)||!Before.PreviousComponentTransforms[I].Equals(After.PreviousComponentTransforms[I],0))
            {Error=TEXT("Terrain overlay changed stored current/previous NN history");return false;}
        for(int32 I=0;I<Future.Num();++I)if(!Future[I].Equals(RawFuture[I],0))
        {Error=TEXT("Terrain publication replaced a normal future NN target");return false;}
        if(Before.SourceTimeSeconds!=SourceTime)
        {
            if(SourceTime>=0&&Before.SourceTimeSeconds<SourceTime){Error=TEXT("Normal NN source clock went backwards");return false;}
            LastRevision=Before.Revision;SourceTime=Before.SourceTimeSeconds;++PolicyUpdates;
        }
        FVector PelvisDelta=FVector::ZeroVector;
        for(int32 J=0;J<25;++J)
        {
            const int32 I=RawNames.IndexOfByKey(LiveBones[J]);if(!Raw.IsValidIndex(I)||!Visible.IsValidIndex(I)||Raw[I].ContainsNaN()||Visible[I].ContainsNaN())
            {Error=TEXT("Missing or nonfinite body: ")+LiveBones[J].ToString();return false;}
            if(J==0)PelvisDelta=Visible[I].GetLocation()-Raw[I].GetLocation();
            if(ExpectDisabled&&!Raw[I].Equals(Visible[I],1.e-10)){Error=TEXT("Disabled Foot IK still changed a published target");return false;}
            if(!ExpectDisabled&&J>=17)MaxTerrainCorrectionCm=FMath::Max(MaxTerrainCorrectionCm,FVector::Distance(Raw[I].GetLocation(),Visible[I].GetLocation()));
            if(J<=16&&!ProphecyFootIKGame::Returning(Agent))
            {
                const double Angle=Raw[I].GetRotation().AngularDistance(Visible[I].GetRotation());MaxUpperError=FMath::Max(MaxUpperError,Angle);
                if(Angle>1.e-6||!(Visible[I].GetLocation()-Raw[I].GetLocation()).Equals(PelvisDelta,.001))
                {Error=TEXT("The stair overlay replaced actual game upper-body motion");return false;}
            }
            FTransform Previous,Current,Single;float SingleAlpha=0;
            if(!Agent->GetAuthoredBodyWorldTarget(LiveBones[J],Previous,Current,Single,SingleAlpha))
            {Error=TEXT("Single-body physical target unavailable");return false;}
            const double Distance=FVector::Distance(Single.GetLocation(),Visible[I].GetLocation());MaxReadError=FMath::Max(MaxReadError,Distance);
            if(Distance>.01||Single.GetRotation().AngularDistance(Visible[I].GetRotation())>1.e-5)
            {Error=FString::Printf(TEXT("Single-body/visible target mismatch for %s: %.8g cm"),*LiveBones[J].ToString(),Distance);return false;}
        }
        return true;
    }
    bool CheckDisabled(FString& Error)
    {
        FProphecyFootIKLiveState Status;
        if(ProphecyFootIKLive::Enabled(Agent)||ProphecyFootIKLive::AnyEnabled()||ProphecyFootIKLive::HasCallbacks()||UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,Status)||!ProphecyFootIKGame::Error(Agent).IsEmpty())
        {Error=TEXT("Disable retained live owner, callbacks or game state");return false;}
        return CheckReads(true,Error);
    }
    bool CheckPublication(const FProphecyFootIKLiveState& Status,bool& Fresh,FString& Error)
    {
        Fresh=Status.AppliedFrame>LastApplied;
        if(Status.AppliedFrame<LastApplied){Error=TEXT("Accepted live frame rewound within one enable epoch");return false;}
        if(Fresh)
        {
            TSharedPtr<FJsonObject> Receipt;bool VerifiedRaw=false;
            if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Status.DiagnosticsJson),Receipt)&&Receipt&&
                Receipt->TryGetBoolField(TEXT("verifiedRawFallback"),VerifiedRaw)&&VerifiedRaw&&!CheckReads(true,Error))return false;
            // A slow worker may legitimately cause fallback. When it finally
            // publishes, it must join the CURRENT game tick, not replay its tail.
            if(LastPublicationTick>=0&&Status.AppliedFrame-LastApplied!=WorldTicks-LastPublicationTick)
            {Error=TEXT("Live publication accepted a stale frame after asynchronous planning");return false;}
            LastApplied=Status.AppliedFrame;LastPublicationTick=WorldTicks;FallbackRun=0;
        }
        else
        {
            ++FallbackTicks;MaxFallbackRun=FMath::Max(MaxFallbackRun,++FallbackRun);
            // Throughput is recorded, not assumed under paging. A missed plan
            // must expose this tick's ordinary pose, never freeze an old overlay.
            if(!CheckReads(true,Error))return false;
        }
        return true;
    }
    void NewEpoch(){LastApplied=LastPublicationTick=-1;FallbackRun=0;}
    void StartPhase()
    {
        const auto& C=Commands[Phase];Agent->SetLocomotionInput(C.Move,C.Run,C.Facing);
        Ticks=PhasePublished=ZeroSteps=0;PhaseRoot=PreviousRoot=Agent->GetRootLowPoint();
        TSharedPtr<FJsonObject> Counts;double Verified=0,Candidate=0;
        if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ProphecyFootIKLive::DiagnosticSnapshot(Agent)),Counts)&&Counts)
        {Counts->TryGetNumberField(TEXT("verifiedIdentityFrames"),Verified);Counts->TryGetNumberField(TEXT("joinedFrames"),Candidate);}
        PhaseVerifiedIdentityStart=int32(Verified);PhaseCandidateStart=int32(Candidate);
        if(Phase==1)
        {
            // A small query-only tread exercises foot placement while the root
            // retains its ordinary flat navigation route (the lab's root/feet
            // collision separation). It is copied from a real finite collider.
            auto* Shelf=World->SpawnActor<AActor>();auto* Box=NewObject<UBoxComponent>(Shelf);Shelf->SetRootComponent(Box);
            Box->SetBoxExtent(FVector(50,100,4));Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Box->SetCollisionObjectType(ECC_WorldDynamic);Box->SetCollisionResponseToAllChannels(ECR_Ignore);Box->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);Box->ComponentTags.Add(TEXT("FootIKFeet"));Box->RegisterComponent();Shelf->SetActorLocation(FVector(PhaseRoot.X+180,PhaseRoot.Y,PhaseRoot.Z+4));
        }
        Test->AddInfo(FString::Printf(TEXT("Live Foot IK phase BEGIN %s"),C.Name));
    }
    bool EndPhase(FString& Error)
    {
        const auto& C=Commands[Phase];const double Travel=FVector::Distance(PhaseRoot,Agent->GetRootLowPoint());
        auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("name"),C.Name);Row->SetNumberField(TEXT("ticks"),Ticks);Row->SetNumberField(TEXT("resolvedFrames"),PhasePublished);Row->SetNumberField(TEXT("travelCm"),Travel);Row->SetNumberField(TEXT("zeroRootSteps"),ZeroSteps);
        TSharedPtr<FJsonObject> Counts;double Verified=0,Candidate=0;
        if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ProphecyFootIKLive::DiagnosticSnapshot(Agent)),Counts)&&Counts)
        {Counts->TryGetNumberField(TEXT("verifiedIdentityFrames"),Verified);Counts->TryGetNumberField(TEXT("joinedFrames"),Candidate);}
        Row->SetNumberField(TEXT("verifiedRawFrames"),Verified-PhaseVerifiedIdentityStart);Row->SetNumberField(TEXT("candidateOrUniformFrames"),Candidate-PhaseCandidateStart);Reports.Add(MakeShared<FJsonValueObject>(Row));
        if(PhasePublished<20){Error=FString::Printf(TEXT("%s never established live publication while the controller kept moving (%d resolved frames)"),C.Name,PhasePublished);return false;}
        if(Phase==1&&MaxTerrainCorrectionCm<.2){Error=TEXT("The finite raised foot tread produced no terrain correction");return false;}
        if(!C.Move.IsNearlyZero()&&(Travel<50||ZeroSteps>Ticks/3)){Error=TEXT("Live planning froze or stopped the ordinary root controller");return false;}
        Test->AddInfo(FString::Printf(TEXT("Live Foot IK phase END %s: %d resolved frames, %.2f cm travel"),C.Name,PhasePublished,Travel));return true;
    }
public:
    explicit FFootIKLiveGameExercise(FAutomationTestBase* InTest):Test(InTest){}
    ~FFootIKLiveGameExercise(){Cleanup();}
    virtual bool Update() override
    {
        const double Now=FPlatformTime::Seconds();if(Now-Started>1800)return Fail(TEXT("Real-manager lifecycle timed out"));
        if(Stage==0)
        {
            if(ProphecyFootIKLive::AnyEnabled())return Fail(TEXT("Run this transient test without another live Foot IK agent"));
            const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
            if(!World)return Fail(TEXT("Cannot create isolated game world"));if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            auto* Floor=World->SpawnActor<AActor>();auto* Box=NewObject<UBoxComponent>(Floor);Floor->SetRootComponent(Box);Box->SetBoxExtent(FVector(1000000,1000000,20));Box->SetCollisionProfileName(TEXT("BlockAll"));Box->RegisterComponent();Floor->SetActorLocation(FVector(0,0,-20));
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();if(!Manager)return Fail(TEXT("Cannot create actual game manager"));
            Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->EndpointAFallback=FVector::ZeroVector;Manager->EndpointBFallback=FVector(10000,0,0);
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();Agent=Manager->ResolveAgent(Manager->GetAgentHandle(0));
            if(!Agent)return Fail(TEXT("Manager did not register the test agent"));Agent->SetLocomotionInput(FVector::ForwardVector,false,FVector::ForwardVector);
            Stage=1;NextTickAt=Now;return false;
        }
        // Pace this diagnostic at60Hz so background planning is measured under
        // actual game conditions; authored simulation still advances one tick.
        if(Now<NextTickAt)return false;NextTickAt=Now+1./60.;World->Tick(LEVELTICK_All,1.f/60);++WorldTicks;
        FString Error;if((Stage!=1||Ticks>=8)&&!CheckReads(Stage==1||Stage==3||Stage==5,Error))return Fail(Error);
        if(Stage==1)
        {
            if(++Ticks<30)return false;
            float Walk=0,Run=0;if(!Manager->GetAgentLocomotionCheckpointWeights(Agent->GetAgentHandle(),Walk,Run)||Walk!=1)
                return Fail(TEXT("The disabled fixture did not retain its ordinary Walk checkpoint"));
            if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"enabled\":true,\"terrain\":\"stairs\",\"gait\":\"walk\"}"),Error)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Fail(Error);
            NewEpoch();Stage=2;StartPhase();return false;
        }
        if(Stage==2)
        {
            const auto Root=Agent->GetRootLowPoint();const double Step=FVector::Distance(PreviousRoot,Root);PreviousRoot=Root;MaxRootStep=FMath::Max(MaxRootStep,Step);if(Step<.01)++ZeroSteps;if(Step>35)return Fail(TEXT("Live solver teleported the ordinary root"));
            FProphecyFootIKLiveState Status;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,Status))return Fail(TEXT("Live owner disappeared"));
            if(!Status.Error.IsEmpty())return Fail(Status.Error);MaxSolveMs=FMath::Max(MaxSolveMs,double(Status.SolveMilliseconds));
            bool Fresh=false;if(!CheckPublication(Status,Fresh,Error))return Fail(Error);
            if(!WarmReady)
            {
                ++PreparationTicks;
                if(!Status.Ready)
                {
                    if(!Status.Preparing&&PreparationTicks>8)return Fail(FString::Printf(TEXT("Cold preparation neither progressed nor reported an error: ticks=%d applied=%d preparedThrough=%d solveMs=%.3f diagnostics=%s"),PreparationTicks,Status.AppliedFrame,Status.PreparedThroughFrame,Status.SolveMilliseconds,*Status.DiagnosticsJson.Left(1200)));
                    return false;
                }
                if(PreparationTicks>30&&FVector::Distance(PhaseRoot,Root)<20)return Fail(TEXT("Ordinary root stopped during cold preparation"));
                WarmReady=true;StartPhase();
            }
            float Walk=0,Run=0;FVector2f Legs;
            if(!Manager->GetAgentLocomotionCheckpointWeights(Agent->GetAgentHandle(),Walk,Run,&Legs)||Walk!=0||Run!=1||Legs.X!=0||Legs.Y!=0)
                return Fail(TEXT("Live Foot IK and its forecast are not using the same Run checkpoint"));
            if(Fresh){++Published;++PhasePublished;}
            if(++Ticks<Commands[Phase].Ticks)return false;
            if(!EndPhase(Error))return Fail(Error);
            if(++Phase<UE_ARRAY_COUNT(Commands)){StartPhase();return false;}
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error)||!CheckDisabled(Error))return Fail(Error);
            Stage=3;Ticks=0;PhaseRoot=Agent->GetRootLowPoint();return false;
        }
        if(Stage==3)
        {
            if(!CheckDisabled(Error))return Fail(Error);if(++Ticks<30)return false;
            if(FVector::Distance(PhaseRoot,Agent->GetRootLowPoint())<50)return Fail(TEXT("Normal NN mover did not continue after disabling Foot IK"));
            // Cancel during real asynchronous initialization and immediately
            // verify that later game ticks cannot publish its stale result.
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Fail(Error);NewEpoch();Stage=4;Ticks=0;return false;
        }
        if(Stage==4)
        {
            // No prepared output can exist before the first actual source pair.
            if(++Ticks<3)return false;if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error)||!CheckDisabled(Error))return Fail(Error);Stage=5;Ticks=0;return false;
        }
        if(Stage==5)
        {
            if(!CheckDisabled(Error))return Fail(Error);if(++Ticks<30)return false;
            if(PolicyUpdates<100)return Fail(TEXT("Normal30Hz NN policy stopped advancing during live terrain correction"));
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Fail(Error);
            NewEpoch();Stage=6;Ticks=0;return false;
        }
        if(Stage==6)
        {
            FProphecyFootIKLiveState Status;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,Status)||!Status.Error.IsEmpty())return Fail(Status.Error.IsEmpty()?TEXT("Re-enabled owner disappeared"):Status.Error);
            bool Fresh=false;if(!CheckPublication(Status,Fresh,Error))return Fail(Error);
            if(Fresh){if(!Status.Ready)return Fail(TEXT("Renewed publication was not ready"));++RenewedFrames;}
            if(RenewedFrames<20)return false;
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error)||!CheckDisabled(Error))return Fail(Error);
            Save(true);Test->AddInfo(FString::Printf(TEXT("Live Foot IK: %d resolved frames; %d ordinary NN publications; max solve %.3f ms"),Published,PolicyUpdates,MaxSolveMs));Cleanup();return true;
        }
        return false;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKLiveGameLifecycleTest,"Prophecy.FootIK.Live.GameLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKLiveGameLifecycleTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FFootIKLiveGameExercise(this));return true;}
#endif
