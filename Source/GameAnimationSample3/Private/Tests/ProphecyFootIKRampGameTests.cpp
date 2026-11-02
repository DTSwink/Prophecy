#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAgent.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKNavigation.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyThrowMath.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNLocomotionManager.h"
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
const FName RampBones[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
// This fixture drives the actual ordinary controller. No root position is
// authored by the test after spawn, and no prerecorded NN course is supplied.
class FFootIKRampGameExercise final : public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    UWorld* World=nullptr;
    AProphecyNNLocomotionManager* Manager=nullptr;
    AProphecyAgent* Agent=nullptr;
    const FTransform Course{FRotator(0,37,0)};
    const double Started=FPlatformTime::Seconds();
    double NextTickAt=0,MaxStep=0,MaxHeightError=0;
    int32 Stage=0,Phase=0,Ticks=0,Joined=0,LastApplied=-1,WindowSlopeSamples=0;
    int32 WorldTicks=0,LastPublicationTick=-1,FallbackTicks=0,FallbackRun=0,MaxFallbackRun=0,TreadContacts=0,RenewedFrames=0,RenewedReadyTicks=0;
    bool HasSolverSpace=false,ElevatedDisableChecked=false;
    FTransform SolverSpace;
    TArray<UBoxComponent*> FootSurfaces;
    double MaxBodyReadError=0,MaxPinError=0;
    FVector LastRoot=FVector::ZeroVector;
    TArray<TSharedPtr<FJsonValue>> Samples;

    static double Height(double X)
    { return X<200 ? 0 : X>620 ? 168 : (X-200)*.4; }
    FVector InCourse(const FVector& WorldPoint) const
    { return Course.InverseTransformPosition(WorldPoint); }
    void Box(FVector Center,FVector Extent,FQuat Rotation,FName Tag,bool FeetOnly=false)
    {
        AActor* Actor=World->SpawnActor<AActor>();auto* Shape=NewObject<UBoxComponent>(Actor);
        Actor->SetRootComponent(Shape);Shape->SetBoxExtent(Extent);
        Shape->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Shape->SetCollisionObjectType(ECC_WorldStatic);Shape->SetCollisionResponseToAllChannels(ECR_Block);
        if(FeetOnly)
        {
            Shape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
            Shape->SetCollisionResponseToChannel(ECC_GameTraceChannel8,ECR_Ignore);
        }
        if(!Tag.IsNone())Shape->ComponentTags.Add(Tag);
        Shape->RegisterComponent();Actor->SetActorTransform(FTransform(Rotation,Center)*Course);
        if(Tag!=FName(TEXT("FootIKRoot")))FootSurfaces.Add(Shape);
    }
    void Cleanup()
    {
        if(Agent){FString Error;UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error);}
        Agent=nullptr;Manager=nullptr;
        if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    bool Finish(bool Success,const FString& Error=FString())
    {
        auto Report=MakeShared<FJsonObject>();Report->SetBoolField(TEXT("success"),Success);
        Report->SetStringField(TEXT("error"),Error);Report->SetNumberField(TEXT("maxRootStepCm"),MaxStep);
        Report->SetNumberField(TEXT("maxHeightErrorCm"),MaxHeightError);
        Report->SetNumberField(TEXT("joinedFrames"),Joined);Report->SetNumberField(TEXT("slopedFutureWindows"),WindowSlopeSamples);
        Report->SetNumberField(TEXT("fallbackTicks"),FallbackTicks);Report->SetNumberField(TEXT("maxConsecutiveFallbackTicks"),MaxFallbackRun);
        Report->SetNumberField(TEXT("treadContacts"),TreadContacts);Report->SetNumberField(TEXT("maxPinErrorCm"),MaxPinError);Report->SetNumberField(TEXT("maxBodyReadErrorCm"),MaxBodyReadError);
        Report->SetBoolField(TEXT("elevatedDisableChecked"),ElevatedDisableChecked);Report->SetNumberField(TEXT("renewedFrames"),RenewedFrames);
        Report->SetNumberField(TEXT("stage"),Stage);Report->SetNumberField(TEXT("phase"),Phase);Report->SetNumberField(TEXT("worldTicks"),WorldTicks);
        Report->SetNumberField(TEXT("renewedReadyTicks"),RenewedReadyTicks);
        if(Agent)
        {
            const FString Diagnostic=ProphecyFootIKLive::DiagnosticSnapshot(Agent);TSharedPtr<FJsonObject> Parsed;
            if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Diagnostic),Parsed)&&Parsed)Report->SetObjectField(TEXT("liveDiagnostics"),Parsed);
            else Report->SetStringField(TEXT("liveDiagnostics"),Diagnostic);
            FProphecyFootIKLiveState State;if(UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State))
            {
                Report->SetBoolField(TEXT("ready"),State.Ready);Report->SetBoolField(TEXT("preparing"),State.Preparing);
                Report->SetNumberField(TEXT("appliedFrame"),State.AppliedFrame);Report->SetNumberField(TEXT("preparedThroughFrame"),State.PreparedThroughFrame);
                Report->SetNumberField(TEXT("solveMilliseconds"),State.SolveMilliseconds);Report->SetStringField(TEXT("ownerError"),State.Error);
            }
        }
        Report->SetArrayField(TEXT("samples"),Samples);FString Text;FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Text));
        const FString Directory=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030");IFileManager::Get().MakeDirectory(*Directory,true);
        FFileHelper::SaveStringToFile(Text,*(Directory/TEXT("live-root-ramp.json")));
        if(!Success)Test->AddError(TEXT("Foot IK root ramp: ")+Error);Cleanup();return true;
    }
    void Command()
    {
        const bool Down=(Phase&1)!=0;const bool Run=Phase>=2;
        const FVector Forward=Course.TransformVectorNoScale(FVector::ForwardVector);
        Agent->SetLocomotionInput(Down?-Forward:Forward,Run,Forward);
        Ticks=0;LastRoot=Agent->GetRootLowPoint();
        Test->AddInfo(FString::Printf(TEXT("Root-ramp BEGIN %s %s"),Run?TEXT("run"):TEXT("walk"),Down?TEXT("backward down"):TEXT("forward up")));
    }
    bool ReadPose(TArray<FName>& Names,TArray<FTransform>& Pose,bool Overlay,FString& Error)
    {
        TArray<FTransform> Future;FProphecyNNPoseSnapshot Snapshot;float Alpha=0;
        if(!Agent->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Pose,Alpha,Snapshot,Overlay))
        {Error=TEXT("Missing actual published ramp pose");return false;}return true;
    }
    bool CheckPose(const FProphecyFootIKLiveState& State,bool& Fresh,FString& Error)
    {
        Fresh=State.AppliedFrame>LastApplied;
        if(State.AppliedFrame<LastApplied){Error=TEXT("Ramp accepted frame rewound within an epoch");return false;}
        if(Fresh)
        {
            if(LastPublicationTick>=0&&State.AppliedFrame-LastApplied!=WorldTicks-LastPublicationTick)
            {Error=TEXT("Ramp joined a stale asynchronous frame");return false;}
            LastApplied=State.AppliedFrame;LastPublicationTick=WorldTicks;FallbackRun=0;++Joined;
        }
        else {++FallbackTicks;MaxFallbackRun=FMath::Max(MaxFallbackRun,++FallbackRun);}
        TArray<FName> Names,RawNames;TArray<FTransform> Visible,Raw;
        if(!ReadPose(Names,Visible,true,Error)||!ReadPose(RawNames,Raw,false,Error)||Names!=RawNames)return false;
        TArray<FTransform> Bodies;Bodies.Reserve(25);FVector PelvisDelta=FVector::ZeroVector;
        for(int32 J=0;J<25;++J)
        {
            const int32 I=Names.IndexOfByKey(RampBones[J]);
            if(!Visible.IsValidIndex(I)||!Raw.IsValidIndex(I)||Visible[I].ContainsNaN()||Raw[I].ContainsNaN())
            {Error=TEXT("Missing/nonfinite final ramp body");return false;}
            Bodies.Add(Visible[I]);if(J==0)PelvisDelta=Visible[I].GetLocation()-Raw[I].GetLocation();
            if(!Fresh&&!Visible[I].Equals(Raw[I],1.e-8)){Error=TEXT("Ramp fallback retained an obsolete terrain overlay");return false;}
            if(J<=16&&!ProphecyFootIKGame::Returning(Agent)&&(Raw[I].GetRotation().AngularDistance(Visible[I].GetRotation())>1.e-6||!(Visible[I].GetLocation()-Raw[I].GetLocation()).Equals(PelvisDelta,.001)))
            {Error=TEXT("Navigation/terrain changed the actual NN upper-body pose");return false;}
            FTransform Previous,Current,Single;float Alpha=0;
            if(!Agent->GetAuthoredBodyWorldTarget(RampBones[J],Previous,Current,Single,Alpha))
            {Error=TEXT("Missing single-body ramp target");return false;}
            const double Distance=FVector::Distance(Single.GetLocation(),Visible[I].GetLocation());MaxBodyReadError=FMath::Max(MaxBodyReadError,Distance);
            if(Distance>.01||Single.GetRotation().AngularDistance(Visible[I].GetRotation())>1.e-5)
            {Error=TEXT("Final ramp whole-pose and physical-target readers disagree");return false;}
        }
        if(!Fresh)return true;
        TSharedPtr<FJsonObject> Reply;const TSharedPtr<FJsonObject> *Frame=nullptr,*Pose=nullptr;
        const TArray<TSharedPtr<FJsonValue>> *Points=nullptr,*Quats=nullptr,*Feet=nullptr,*Root=nullptr;
        if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(State.DiagnosticsJson),Reply)||!Reply)
        {Error=TEXT("Malformed ramp diagnostics");return false;}
        // Status may poll a worker just completed after the game publication.
        // Only liveJoin receipts describe the displayed pose; prospective
        // liveEvaluate diagnostics must never be mistaken for accepted contact.
        if(!Reply->HasField(TEXT("pinErrors")))return true;
        if(!Reply->TryGetObjectField(TEXT("frame"),Frame)||!(*Frame)->TryGetObjectField(TEXT("pose"),Pose)||!(*Pose)->TryGetArrayField(TEXT("points"),Points)||!(*Pose)->TryGetArrayField(TEXT("q"),Quats)||Points->Num()!=26||Quats->Num()!=26||!(*Frame)->TryGetArrayField(TEXT("feet"),Feet)||Feet->Num()!=2||!(*Frame)->TryGetArrayField(TEXT("root"),Root)||Root->Num()!=3)
        {Error=TEXT("Fresh ramp publication lacks its exact pose/contact receipt");return false;}
        auto Vector=[](const TArray<TSharedPtr<FJsonValue>>& V){return FVector(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber());};
        for(int32 J=0;J<25;++J)
        {
            const auto& P=(*Points)[J+1]->AsArray();const auto& Q=(*Quats)[J+1]->AsArray();
            if(P.Num()!=3||Q.Num()!=4){Error=TEXT("Malformed ramp pose receipt");return false;}
            const FTransform Local=ProphecyThrow::ToUnreal(FTransform(FQuat(Q[0]->AsNumber(),Q[1]->AsNumber(),Q[2]->AsNumber(),Q[3]->AsNumber()),Vector(P)));
            if(!HasSolverSpace){SolverSpace=Local.Inverse()*Bodies[J];HasSolverSpace=true;}
            const FTransform Expected=Local*SolverSpace;
            if(!Expected.GetLocation().Equals(Bodies[J].GetLocation(),.02)||Expected.GetRotation().AngularDistance(Bodies[J].GetRotation())>1.e-5)
            {Error=TEXT("Ramp final body differs from the accepted solver receipt/carrier");return false;}
        }
        if(!SolverSpace.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(*Root))).Equals(Agent->GetRootLowPoint(),.02))
        {Error=TEXT("Ramp body carrier adds navigation height more than once");return false;}
        for(int32 Side=0;Side<2;++Side)
        {
            const auto Foot=(*Feet)[Side]->AsObject();const TSharedPtr<FJsonObject>* Contact=nullptr;
            if(!Foot||!Foot->TryGetObjectField(TEXT("contact"),Contact))continue;
            const TArray<TSharedPtr<FJsonValue>> *Point=nullptr,*Local=nullptr;
            if(!(*Contact)->TryGetArrayField(TEXT("point"),Point)||Point->Num()!=3||!(*Contact)->TryGetArrayField(TEXT("localPoint"),Local)||Local->Num()!=3)
            {Error=TEXT("Pinned foot lacks its material contact point");return false;}
            const FVector ContactWorld=SolverSpace.TransformPosition(ProphecyThrow::ToUnrealPoint(Vector(*Point)));
            const FTransform FootSolver=ProphecyFootIKLive::ToSolverBody(Bodies[Side?23:19],SolverSpace);
            const FVector MaterialWorld=SolverSpace.TransformPosition(ProphecyThrow::ToUnrealPoint(FootSolver.TransformPosition(Vector(*Local))));
            const double PinError=FVector::Distance(ContactWorld,MaterialWorld);MaxPinError=FMath::Max(MaxPinError,PinError);
            if(PinError>.6){Error=TEXT("Final ramp shoe does not touch its accepted pin");return false;}
            bool OnFootSurface=false,OnTread=false;
            for(const auto* Surface:FootSurfaces)
            {
                const FVector P=Surface->GetComponentTransform().InverseTransformPosition(ContactWorld),Extent=Surface->GetUnscaledBoxExtent();
                if(FMath::Abs(P.Z-Extent.Z)<.1&&FMath::Abs(P.X)<=Extent.X+.1&&FMath::Abs(P.Y)<=Extent.Y+.1)
                {OnFootSurface=true;OnTread|=Surface->ComponentHasTag(TEXT("FootIKFeet"));}
            }
            if(!OnFootSurface){Error=TEXT("Pin is on the navigation ramp or outside every actual finite tread");return false;}
            if(OnTread)++TreadContacts;
        }
        return true;
    }
    bool DisableElevated(FString& Error)
    {
        TArray<FName> BeforeNames,AfterNames;TArray<FTransform> Before,After;
        if(!ReadPose(BeforeNames,Before,false,Error))return false;const FVector Root=Agent->GetRootLowPoint();
        if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error)||ProphecyFootIKLive::AnyEnabled()||ProphecyFootIKLive::HasCallbacks()||ProphecyFootIKNavigation::Active(Agent))
        {Error=TEXT("Elevated disable retained ownership/navigation");return false;}
        if(!ReadPose(AfterNames,After,false,Error)||BeforeNames!=AfterNames||!Agent->GetRootLowPoint().Equals(Root,.01))
        {Error=TEXT("Elevated disable moved the root or removed ordinary pose publication");return false;}
        for(int32 I=0;I<Before.Num();++I)if(!Before[I].Equals(After[I],.01))
        {Error=TEXT("Elevated disable changed the already-published NN carrier");return false;}
        ElevatedDisableChecked=true;Agent->SetLocomotionInput(FVector::ZeroVector,false,Course.TransformVectorNoScale(FVector::ForwardVector));
        Stage=4;Ticks=0;LastRoot=Root;return true;
    }
public:
    explicit FFootIKRampGameExercise(FAutomationTestBase* InTest):Test(InTest){}
    ~FFootIKRampGameExercise(){Cleanup();}
    virtual bool Update() override
    {
        const double Now=FPlatformTime::Seconds();if(Now-Started>900)return Finish(false,TEXT("Timed out"));
        if(Stage==0)
        {
            if(ProphecyFootIKLive::AnyEnabled())return Finish(false,TEXT("Requires an isolated transient test host"));
            const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
            if(!World)return Finish(false,TEXT("Cannot create world"));if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            Box(FVector(-150,0,-20),FVector(350,180,20),FQuat::Identity,NAME_None);
            Box(FVector(1310,0,148),FVector(690,180,20),FQuat::Identity,NAME_None);
            const FQuat RampQ=FRotator(FMath::RadiansToDegrees(FMath::Atan(.4)),0,0).Quaternion();
            Box(FVector(410,0,84)-RampQ.GetAxisZ()*5,FVector(FMath::Sqrt(420.*420+168.*168)/2,180,5),RampQ,TEXT("FootIKRoot"));
            for(int32 I=0;I<12;++I)
                Box(FVector(217.5+35*I,0,14*(I+1)-3),FVector(17.5,180,3),FQuat::Identity,TEXT("FootIKFeet"),true);
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();if(!Manager)return Finish(false,TEXT("Cannot create manager"));
            Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->EndpointAFallback=Course.GetLocation();Manager->EndpointBFallback=Course.TransformPosition(FVector(10000,0,0));
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();Agent=Manager->ResolveAgent(Manager->GetAgentHandle(0));
            if(!Agent)return Finish(false,TEXT("Missing real test agent"));
            Agent->SetLocomotionInput(FVector::ZeroVector,false,Course.TransformVectorNoScale(FVector::ForwardVector));Stage=1;NextTickAt=Now;return false;
        }
        if(Now<NextTickAt)return false;NextTickAt=Now+1./60.;World->Tick(LEVELTICK_All,1.f/60);++WorldTicks;
        if(Stage==1)
        {
            if(++Ticks<30)return false;FString Error;
            if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"enabled\":true,\"terrain\":\"stairs\",\"gait\":\"walk\"}"),Error)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Finish(false,Error);
            Stage=2;Ticks=0;return false;
        }
        if(Stage==2)
        {
            FProphecyFootIKLiveState Warm;FString Why;
            if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,Warm))return Finish(false,TEXT("Preparing ramp owner disappeared"));
            if(!Warm.Error.IsEmpty())return Finish(false,Warm.Error);bool Fresh=false;
            if(!CheckPose(Warm,Fresh,Why))return Finish(false,Why);
            if(!Warm.Ready)return false;Stage=3;Command();return false;
        }
        if(Stage==4)
        {
            const FVector Root=Agent->GetRootLowPoint();
            if(ProphecyFootIKLive::Enabled(Agent)||ProphecyFootIKNavigation::Active(Agent)||FVector::Distance(Root,LastRoot)>25||FMath::Abs(InCourse(Root).Z-168)>2)
                return Finish(false,TEXT("Ordinary locomotion lost elevated height after disable"));
            LastRoot=Root;if(++Ticks<30)return false;FString Why;
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Why))return Finish(false,Why);
            LastApplied=LastPublicationTick=-1;HasSolverSpace=false;FallbackRun=0;RenewedReadyTicks=0;Stage=5;return false;
        }
        if(Stage==5)
        {
            FProphecyFootIKLiveState State;FString Why;
            if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State)||!State.Error.IsEmpty())return Finish(false,State.Error.IsEmpty()?TEXT("Elevated re-enable lost its owner"):State.Error);
            bool Fresh=false;if(!CheckPose(State,Fresh,Why))return Finish(false,Why);
            if(FMath::Abs(InCourse(Agent->GetRootLowPoint()).Z-168)>2)return Finish(false,TEXT("Re-enable counted elevated navigation twice"));
            if(Fresh){if(!State.Ready)return Finish(false,TEXT("Renewed ramp frame was not ready"));++RenewedFrames;}
            if(State.Ready&&++RenewedReadyTicks>=180&&RenewedFrames<12)
                return Finish(false,FString::Printf(TEXT("Elevated re-enable produced only %d fresh frames in %d ready game ticks"),RenewedFrames,RenewedReadyTicks));
            if(RenewedFrames<12)return false;Stage=3;++Phase;Command();return false;
        }
        const FVector Root=Agent->GetRootLowPoint(),Local=InCourse(Root);const double Step=FVector::Distance(LastRoot,Root);LastRoot=Root;MaxStep=FMath::Max(MaxStep,Step);
        if(Root.ContainsNaN()||Step>25)return Finish(false,TEXT("Root became nonfinite or teleported"));
        FProphecyFootIKLiveState State;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State))return Finish(false,TEXT("Live owner disappeared"));
        if(!State.Error.IsEmpty())return Finish(false,State.Error);bool Fresh=false;FString PoseError;if(!CheckPose(State,Fresh,PoseError))return Finish(false,PoseError);
        // Allow the exact upright-capsule contact offset on an inclined plane,
        // but not a second ramp lift or an authored flat root beneath the stairs.
        const double Radius=Agent->GetAgentCapsule()->GetScaledCapsuleRadius();
        const double Allowance=Radius*(FMath::Sqrt(1.16)-1)+2;
        const double Error=Local.Z-Height(Local.X);MaxHeightError=FMath::Max(MaxHeightError,FMath::Abs(Error));
        if(Local.X>235&&Local.X<585&&(Error<-2||Error>Allowance))return Finish(false,FString::Printf(TEXT("Root does not follow actual navigation ramp: x%.3f z%.3f expected%.3f"),Local.X,Local.Z,Height(Local.X)));
        TArray<FTransform> Roots;TArray<float> Times;
        if(!Manager->GetAgentContinuousLocomotionRootWindow(Agent->GetAgentHandle(),Roots,Times)||Roots.Num()!=9)return Finish(false,TEXT("Expected present plus eight continuous future roots"));
        bool Sloped=false;
        for(int32 I=1;I<Roots.Num();++I)
        {
            const FVector Future=InCourse(Roots[I].GetLocation());
            if(Future.ContainsNaN())return Finish(false,TEXT("Future root is nonfinite"));
            if(Future.X>250&&Future.X<570)
            {
                const double Delta=Future.Z-Height(Future.X);
                if(Delta<-2||Delta>Allowance)return Finish(false,TEXT("NN future root window lacks navigation ramp elevation"));
                Sloped|=FMath::Abs(Future.Z-Local.Z)>1;
            }
        }
        if(Sloped)++WindowSlopeSamples;
        auto Row=MakeShared<FJsonObject>();Row->SetNumberField(TEXT("phase"),Phase);Row->SetNumberField(TEXT("x"),Local.X);Row->SetNumberField(TEXT("height"),Local.Z);Row->SetNumberField(TEXT("futureHeight"),InCourse(Roots.Last().GetLocation()).Z);Samples.Add(MakeShared<FJsonValueObject>(Row));
        const bool Down=(Phase&1)!=0;const bool Arrived=Down?Local.X<75:Local.X>750;
        if(!Arrived){if(++Ticks>540)return Finish(false,TEXT("Ordinary controller stalled at the ramp"));return false;}
        if(FMath::Abs(Local.Z-(Down?0:168))>2)return Finish(false,TEXT("Wrong actual root elevation on landing"));
        if(Phase==0&&!ElevatedDisableChecked){FString Why;if(!DisableElevated(Why))return Finish(false,Why);return false;}
        if(++Phase<4){Command();return false;}
        if(Joined<80||WindowSlopeSamples<30)return Finish(false,TEXT("Insufficient live terrain publication or predictive ramp samples"));
        if(TreadContacts<2||!ElevatedDisableChecked||RenewedFrames<12)return Finish(false,TEXT("Missing actual tread contact or successful elevated re-enable coverage"));
        return Finish(true);
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKRootRampGameTest,"Prophecy.FootIK.Live.RootRampGame",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKRootRampGameTest::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FFootIKRampGameExercise(this));return true;}
#endif
