#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyFootIKNavigation.h"
#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyBodyflipLibrary.h"
#include "ProphecyBodyflipRuntime.h"
#include "Components/BoxComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyFootIKActionHandoffTests
{
const FName Bones[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
const int32 Parents[]={-1,0,1,2,3,4,5,6,7,8,5,10,11,12,5,14,15,0,17,18,19,0,21,22,23};

// Two real-controller cases in separate transient worlds. No recorded rollout,
// direct root teleport, private Suspend call, or synthetic action ownership.
class FExercise final : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    UWorld* World=nullptr;
    AProphecyNNLocomotionManager* Manager=nullptr;
    AProphecyAgent* Agent=nullptr;
    AActor* Wall=nullptr;
    int32 Scenario=0,Stage=0,Ticks=0,SolvedTicks=0,SlideTicks=0,PoseId=-1,OverlayTicks=0;
    const double Began=FPlatformTime::Seconds();
    double NextTick=0,OldLift=0,MaxActionRootError=0,MaxActionPoseError=0;
    FVector ActionStart=FVector::ZeroVector,ResumeStart=FVector::ZeroVector,LastRoot=FVector::ZeroVector;
    bool SawOverlay=false;
    TArray<TSharedPtr<FJsonValue>> Samples;

    FString Record(const TCHAR* Label,bool Detailed=false)
    {
        if(!Agent)return TEXT("No active fixture agent");
        const FVector Root=Agent->GetRootLowPoint();const double Lift=ProphecyFootIKNavigation::Lift(Agent);
        FProphecyFootIKLiveState S;UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,S);
        const bool Overlay=HasOverlay(),Navigation=ProphecyFootIKNavigation::Active(Agent),Surface=ProphecyFootIKSurface::Active(Agent);
        auto Row=MakeShared<FJsonObject>();Row->SetStringField(TEXT("event"),Label);Row->SetNumberField(TEXT("scenario"),Scenario);Row->SetNumberField(TEXT("stage"),Stage);Row->SetNumberField(TEXT("tick"),Ticks);
        Row->SetArrayField(TEXT("actualRootCm"),{MakeShared<FJsonValueNumber>(Root.X),MakeShared<FJsonValueNumber>(Root.Y),MakeShared<FJsonValueNumber>(Root.Z)});
        Row->SetNumberField(TEXT("liftCm"),Lift);Row->SetNumberField(TEXT("virtualRootHeightCm"),Root.Z-Lift);Row->SetBoolField(TEXT("navigationActive"),Navigation);Row->SetBoolField(TEXT("surfaceActive"),Surface);
        Row->SetBoolField(TEXT("overlayNow"),Overlay);Row->SetBoolField(TEXT("sawOverlay"),SawOverlay);Row->SetNumberField(TEXT("overlayTicks"),OverlayTicks);Row->SetNumberField(TEXT("poseId"),PoseId);
        Row->SetBoolField(TEXT("ready"),S.Ready);Row->SetBoolField(TEXT("preparing"),S.Preparing);Row->SetNumberField(TEXT("appliedFrame"),S.AppliedFrame);Row->SetNumberField(TEXT("preparedThroughFrame"),S.PreparedThroughFrame);Row->SetNumberField(TEXT("solveMilliseconds"),S.SolveMilliseconds);Row->SetStringField(TEXT("liveError"),S.Error);
        if(Detailed)Row->SetStringField(TEXT("liveDiagnostics"),S.DiagnosticsJson);Samples.Add(MakeShared<FJsonValueObject>(Row));
        return FString::Printf(TEXT("root=%s lift=%.3fcm nav=%d surface=%d overlayNow=%d sawOverlay=%d overlayTicks=%d ready=%d preparing=%d applied=%d preparedThrough=%d solve=%.1fms error=%s"),*Root.ToString(),Lift,Navigation,Surface,Overlay,SawOverlay,OverlayTicks,S.Ready,S.Preparing,S.AppliedFrame,S.PreparedThroughFrame,S.SolveMilliseconds,*S.Error);
    }
    void Save(bool Success,const FString& Error)
    {
        auto Report=MakeShared<FJsonObject>();Report->SetBoolField(TEXT("success"),Success);Report->SetStringField(TEXT("error"),Error);Report->SetNumberField(TEXT("completedScenarios"),Scenario);Report->SetNumberField(TEXT("maxActionRootErrorCm"),MaxActionRootError);Report->SetNumberField(TEXT("maxActionBodyTargetErrorCm"),MaxActionPoseError);Report->SetArrayField(TEXT("samples"),Samples);
        FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));const FString Folder=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");
        IFileManager::Get().MakeDirectory(*Folder,true);FFileHelper::SaveStringToFile(Text,*(Folder/TEXT("live-action-handoff.json")));
    }

    AActor* Box(const FVector& Center,const FVector& Extent,const FQuat& Rotation=FQuat::Identity,FName Tag=NAME_None,bool FeetOnly=false)
    {
        auto* A=World->SpawnActor<AActor>();auto* C=NewObject<UBoxComponent>(A);
        A->SetRootComponent(C);C->SetBoxExtent(Extent);C->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        C->SetCollisionObjectType(ECC_WorldStatic);C->SetCollisionResponseToAllChannels(ECR_Block);
        if(FeetOnly){C->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);C->SetCollisionResponseToChannel(ECC_GameTraceChannel8,ECR_Ignore);}
        if(!Tag.IsNone())C->ComponentTags.Add(Tag);
        C->RegisterComponent();A->SetActorTransform(FTransform(Rotation,Center));return A;
    }
    void Cleanup()
    {
        if(Agent)
        {
            FString Error;
            UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error);
            UProphecyBodyflipLibrary::StopBodyflip(Agent);
        }
        Agent=nullptr;Manager=nullptr;Wall=nullptr;
        if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    bool Fail(const FString& Error)
    {
        const FString Detail=Record(TEXT("failure"),true);Save(false,Error);
        Test->AddError(FString::Printf(TEXT("Foot IK action handoff scenario%d stage%d tick%d: %s; %s"),Scenario,Stage,Ticks,*Error,*Detail));Cleanup();return true;
    }
    bool HasOverlay() const
    {
        FTransform Probe[25];for(int32 I=0;I<25;++I)Probe[I]=FTransform(FVector(100000+I,200000,300000));
        ProphecyFootIKGame::Apply(PoseId,MakeArrayView(Bones),MakeArrayView(Probe));
        for(int32 I=0;I<25;++I)if(!Probe[I].GetLocation().Equals(FVector(100000+I,200000,300000),0))return true;
        return false;
    }
    bool StartAction(FString& Error)
    {
        ActionStart=Agent->GetRootLowPoint();OldLift=ProphecyFootIKNavigation::Lift(Agent);
        Record(TEXT("before-action"),true);
        if(Scenario==0&&!SawOverlay)
        {Error=TEXT("Actual ramp climb completed, but no live terrain overlay was ever applied");return false;}
        if(Scenario==0&&(!ProphecyFootIKNavigation::Active(Agent)||OldLift<100))
        {Error=TEXT("Elevated navigation carrier was absent or lost its retained lift before the action");return false;}
        // Space Gym is a real Bodyflip action with a complete pose/carrier. It
        // avoids an unrelated jump/attack asset dependency in this handoff test.
        if(!UProphecyBodyflipLibrary::StartBodyflip(Agent,TEXT("{\"mode\":\"spaceGym\",\"trimOut\":0.5,\"aim\":false,\"flip\":0,\"twist\":0,\"jumpEvents\":[]}"),TEXT(""),Error))return false;
        FProphecyBodyflipState S;
        if(!UProphecyBodyflipLibrary::GetBodyflipState(Agent,S)||!S.Root.Equals(ActionStart,.02))
        {Error=TEXT("Action admission changed the existing actual root");return false;}
        if(ProphecyFootIKNavigation::Active(Agent)||ProphecyFootIKSurface::Active(Agent)||HasOverlay())
        {Error=TEXT("Successful action admission did not immediately suspend the live terrain owner");return false;}
        Record(TEXT("action-admitted"),true);
        Stage=4;Ticks=0;SolvedTicks=0;return true;
    }
    bool CheckAction(FString& Error)
    {
        // Check even while Bodyflip is preparing: ordinary terrain must cease
        // before the first action root/pose is published, not one frame later.
        if(ProphecyFootIKNavigation::Active(Agent)||ProphecyFootIKSurface::Active(Agent)||HasOverlay())
        {Error=TEXT("Old terrain carrier or pose overlay survived action ownership");return false;}
        FProphecyBodyflipState S;if(!UProphecyBodyflipLibrary::GetBodyflipState(Agent,S)){Error=TEXT("Action disappeared");return false;}
        if(!S.Error.IsEmpty()){Error=S.Error;return false;}
        if(S.Phase==TEXT("PREPARING"))return true;
        if(SolvedTicks==0&&(!S.Root.Equals(ActionStart,.02)||!Agent->GetRootLowPoint().Equals(ActionStart,.02)))
        {Error=TEXT("First action frame added or lost the prior navigation elevation");return false;}
        MaxActionRootError=FMath::Max(MaxActionRootError,FVector::Distance(S.Root,Agent->GetRootLowPoint()));
        FTransform P[25],C[25],L[25];
        if(!ProphecyBodyflip::Apply(Agent,MakeArrayView(Bones),MakeArrayView(Parents),MakeArrayView(P),MakeArrayView(C),MakeArrayView(L),FTransform::Identity,S.Time))
        {Error=TEXT("Action lacks its complete pose");return false;}
        for(int32 I=0;I<25;++I)
        {
            FTransform Previous,Current,Visible;float Alpha=0;
            if(!Agent->GetAuthoredBodyWorldTarget(Bones[I],Previous,Current,Visible,Alpha)||Current.ContainsNaN())
            {Error=TEXT("Action body target unavailable or nonfinite");return false;}
            MaxActionPoseError=FMath::Max(MaxActionPoseError,FVector::Distance(Current.GetLocation(),C[I].GetLocation()));
            if(Current.GetRotation().AngularDistance(C[I].GetRotation())>1.e-5)
            {Error=TEXT("An old pose layer changed the action target rotation");return false;}
        }
        if(MaxActionRootError>.02||MaxActionPoseError>.02)
        {Error=TEXT("Published action root/pose received an extra terrain transform");return false;}
        ++SolvedTicks;return true;
    }
public:
    explicit FExercise(FAutomationTestBase* In):Test(In){}
    ~FExercise(){Cleanup();}
    bool Update() override
    {
        const double Now=FPlatformTime::Seconds();
        // Wall time is only a cold asset/worker watchdog; all motion phases and
        // continuity checks use authored60Hz world ticks.
        if(Now-Began>900)return Fail(TEXT("Cold preparation or action watchdog expired"));
        if(Stage==0)
        {
            if(ProphecyFootIKLive::AnyEnabled()||ProphecyBodyflip::AnyActive())return Fail(TEXT("Requires an isolated automation host"));
            const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
            if(!World)return Fail(TEXT("Cannot create transient world"));if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            if(Scenario==0)
            {
                Box(FVector(-150,0,-20),FVector(350,180,20));Box(FVector(1310,0,148),FVector(690,180,20));
                const FQuat Q=FRotator(FMath::RadiansToDegrees(FMath::Atan(.4)),0,0).Quaternion();
                Box(FVector(410,0,84)-Q.GetAxisZ()*5,FVector(FMath::Sqrt(420.*420+168.*168)/2,180,5),Q,TEXT("FootIKRoot"));
                for(int32 I=0;I<12;++I)Box(FVector(217.5+35*I,0,14*(I+1)-3),FVector(17.5,180,3),FQuat::Identity,TEXT("FootIKFeet"),true);
            }
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();if(!Manager)return Fail(TEXT("Cannot create manager"));
            Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->EndpointAFallback=FVector::ZeroVector;Manager->EndpointBFallback=FVector(10000,0,0);
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();Agent=Manager->ResolveAgent(Manager->GetAgentHandle(0));
            if(!Agent)return Fail(TEXT("Manager did not register its agent"));Agent->SetUpperNNInputs(false,0,0);
            Agent->SetLocomotionInput(FVector::ZeroVector,false,FVector::ForwardVector);
            Stage=1;Ticks=0;NextTick=Now;return false;
        }
        if(Now<NextTick)return false;NextTick=Now+1./60.;World->Tick(LEVELTICK_All,1.f/60);FString Error;
        if(Stage==1)
        {
            if(++Ticks<30)return false;float Interval=0;bool Interpolate=false;
            if(!Agent->GetNNPoseDataSource(PoseId,Interval,Interpolate))return Fail(TEXT("Missing actual pose store id"));
            if(Scenario==1)
            {
                const FVector R=Agent->GetRootLowPoint();Box(R-FVector(0,0,10),FVector(200000,4000,10));Wall=Box(R+FVector(150,0,0),FVector(10,1500,8000));
                Agent->SetLocomotionInput(FVector::ForwardVector,true,FVector::ForwardVector);
            }
            const FString Settings=Scenario==0?TEXT("{\"terrain\":\"stairs\",\"gait\":\"walk\"}"):TEXT("{\"terrain\":\"incline\",\"gait\":\"run\",\"inclineGravity\":true,\"minGravityIncline\":80,\"fullGravity\":100,\"energyConservation\":100,\"slideEnabled\":true,\"slideSpeed\":0.2}");
            if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,Settings,Error)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Fail(Error);
            Stage=2;Ticks=0;return false;
        }
        if(Stage==2||Stage==3)
        {
            FProphecyFootIKLiveState S;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,S)||!S.Error.IsEmpty())return Fail(S.Error.IsEmpty()?TEXT("Missing live state"):S.Error);
            if(HasOverlay()){SawOverlay=true;++OverlayTicks;}
            if(Scenario==1&&!ProphecyFootIKSurface::Active(Agent)){Wall->SetActorLocation(Agent->GetRootLowPoint()+FVector(150,0,0));return false;}
            if(Stage==2)
            {
                if(Scenario==0&&!S.Ready)return false;
                Agent->SetLocomotionInput(FVector::ForwardVector,Scenario==1,FVector::ForwardVector);Stage=3;Ticks=0;return false;
            }
            if(++Ticks>600)return Fail(TEXT("Actual controller never reached handoff condition"));
            if(Ticks%30==0)Record(TEXT("locomotion"));
            if(Scenario==0)
            {
                if(Agent->GetRootLowPoint().X<750)return false;
                if(FMath::Abs(Agent->GetRootLowPoint().Z-168)>2)return Fail(TEXT("Controller failed to climb the actual navigation ramp"));
            }
            else
            {
                ProphecyFootIKSurface::FPolicyHandoff H;if(!ProphecyFootIKSurface::ReadPolicyHandoff(Agent,H,Error))return Fail(Error);
                if(!H.WasSliding||++SlideTicks<4)return false;
            }
            if(!StartAction(Error))return Fail(Error);return false;
        }
        if(Stage==4)
        {
            if(!CheckAction(Error))return Fail(Error);if(SolvedTicks<12)return false;
            const FVector Before=Agent->GetRootLowPoint();
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error))return Fail(Error);
            if(ProphecyFootIKLive::Enabled(Agent)||!ProphecyBodyflip::Active(Agent)||!Agent->GetRootLowPoint().Equals(Before,.02))return Fail(TEXT("Disabling suspended Foot IK disturbed the action"));
            if(!UProphecyBodyflipLibrary::StopBodyflip(Agent)||ProphecyBodyflip::Active(Agent))return Fail(TEXT("Action failed to hand back ownership"));
            if(!Agent->GetRootLowPoint().Equals(Before,.02))return Fail(TEXT("Action stop teleported to an old virtual root"));
            ResumeStart=LastRoot=Agent->GetRootLowPoint();
            // Stay on the broad upper landing in case0; leave the wall in
            // case1. Both commands use the ordinary controller after disable.
            const FVector ResumeDirection=Scenario==0?FVector::ForwardVector:-FVector::ForwardVector;
            Agent->SetLocomotionInput(ResumeDirection,true,ResumeDirection);
            Stage=5;Ticks=0;return false;
        }
        if(Stage==5)
        {
            const FVector Root=Agent->GetRootLowPoint();const double Step=FVector::Distance(Root,LastRoot);LastRoot=Root;
            if(Root.ContainsNaN()||Step>25||ProphecyFootIKNavigation::Active(Agent)||ProphecyFootIKSurface::Active(Agent)||HasOverlay())return Fail(TEXT("Disabled terrain reappeared or ordinary resume teleported"));
            if(Scenario==0&&FMath::Abs(Root.Z-168)>2)return Fail(TEXT("Ordinary resume lost or doubled the elevated carrier"));
            if(++Ticks<30)return false;
            if(FVector::Distance(Root,ResumeStart)<5)return Fail(TEXT("Ordinary controller did not resume moving"));
            Test->AddInfo(FString::Printf(TEXT("%s -> Bodyflip -> disabled ordinary controller; prior lift %.3fcm, action root/pose errors %.6f/%.6fcm"),Scenario==0?TEXT("Elevated navigation"):TEXT("Causal Slide"),OldLift,MaxActionRootError,MaxActionPoseError));
            Record(TEXT("ordinary-resumed"),true);Cleanup();if(++Scenario==2){Save(true,TEXT(""));return true;}Stage=0;Ticks=0;SlideTicks=0;SawOverlay=false;OverlayTicks=0;return false;
        }
        return Fail(TEXT("Unknown fixture stage"));
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKActionHandoffTest,"Prophecy.FootIK.Live.ActionHandoff",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKActionHandoffTest::RunTest(const FString&)
{ADD_LATENT_AUTOMATION_COMMAND(ProphecyFootIKActionHandoffTests::FExercise(this));return true;}
#endif
