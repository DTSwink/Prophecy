#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKSurfaceOwner.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKGame.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"
#include "Components/BoxComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyFootIKSurfaceTests
{
const FName Bones[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
const int32 Parents[]={-1,0,1,2,3,4,5,6,7,8,5,10,11,12,5,14,15,0,17,18,19,0,21,22,23};
class FExercise final:public IAutomationLatentCommand
{
    FAutomationTestBase* Test;
    UWorld* World=nullptr;AProphecyNNLocomotionManager* Manager=nullptr;AProphecyAgent* Agent=nullptr;AActor* Wall=nullptr;
    int32 Stage=0,Ticks=0,Checked=0,LastFrame=-1,PreparationTicks=0;bool SawSlide=false,SawTurn=false,Reconfigured=false;
    int32 WorldTicks=0,LastPublicationTick=-1,RenewedFrames=0,RenewedReadyTicks=0,ReconfigureFallbackTicks=0,MaxFallbackRun=0,FallbackRun=0;
    double Started=FPlatformTime::Seconds(),MaxRootError=0,MaxTargetError=0,MaxRotationError=0,MaxSolveMs=0;
    FVector DisabledRoot=FVector::ZeroVector,PreparationRoot=FVector::ZeroVector;double PreparationTravel=0;float InitialYaw=0;
    FVector LastDisabledRoot=FVector::ZeroVector;double DisabledStepLimit=100,MaxDisabledStep=0;
    void Save(bool Good,const FString& Error)
    {
        auto R=MakeShared<FJsonObject>();R->SetBoolField(TEXT("success"),Good);R->SetStringField(TEXT("error"),Error);R->SetStringField(TEXT("source"),TEXT("real manager history + finite world box colliders + live controller; no course initialization"));
        R->SetNumberField(TEXT("preparationTicks"),PreparationTicks);R->SetNumberField(TEXT("ordinaryTravelDuringPreparationCm"),PreparationTravel);
        R->SetNumberField(TEXT("framesChecked"),Checked);R->SetBoolField(TEXT("sawSlide"),SawSlide);R->SetBoolField(TEXT("sawLiveFacingTurn"),SawTurn);R->SetBoolField(TEXT("activeConfigureReset"),Reconfigured);
        R->SetNumberField(TEXT("renewedFramesAfterConfigure"),RenewedFrames);R->SetNumberField(TEXT("reconfigureFallbackTicks"),ReconfigureFallbackTicks);R->SetNumberField(TEXT("maxConsecutiveFallbackTicks"),MaxFallbackRun);R->SetNumberField(TEXT("maxDisabledRootStepCm"),MaxDisabledStep);
        R->SetNumberField(TEXT("maxRootErrorCm"),MaxRootError);R->SetNumberField(TEXT("maxTargetErrorCm"),MaxTargetError);R->SetNumberField(TEXT("maxRotationErrorRad"),MaxRotationError);R->SetNumberField(TEXT("maxSolveMilliseconds"),MaxSolveMs);
        R->SetNumberField(TEXT("renewedReadyTicks"),RenewedReadyTicks);
        if(!Good&&Agent)
        {
            TSharedPtr<FJsonObject> Diagnostic;
            if(FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ProphecyFootIKLive::DiagnosticSnapshot(Agent)),Diagnostic)&&Diagnostic)R->SetObjectField(TEXT("liveDiagnostics"),Diagnostic);
        }
        FString Text;FJsonSerializer::Serialize(R,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/surface-live-game.json")));
    }
    void Cleanup()
    {
        if(Agent){FString Error;UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error);}Agent=nullptr;Manager=nullptr;
        if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    bool Fail(const FString& Error){Test->AddError(TEXT("Causal surface owner: ")+Error);Save(false,Error);Cleanup();return true;}
    AActor* Box(const FVector& Center,const FVector& Extents)
    {
        auto* Actor=World->SpawnActor<AActor>();auto* C=NewObject<UBoxComponent>(Actor);Actor->SetRootComponent(C);C->SetBoxExtent(Extents);C->SetCollisionProfileName(TEXT("BlockAll"));C->RegisterComponent();Actor->SetActorLocation(Center);return Actor;
    }
    bool Check(FString& Error)
    {
        FProphecyFootIKLiveState State;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State)){Error=TEXT("Public live state disappeared");return false;}
        if(!State.Error.IsEmpty()){Error=State.Error;return false;}if(!ProphecyFootIKSurface::Active(Agent))return true;
        if(!State.Ready){Error=TEXT("Active causal surface owner is not ready");return false;}
        // Once active this owner is synchronous: every authored world tick must
        // advance its coupled root, policy and target exactly one display frame.
        if(LastPublicationTick>=0&&State.AppliedFrame-LastFrame!=WorldTicks-LastPublicationTick)
        {Error=TEXT("Active causal surface skipped/replayed a display frame");return false;}
        LastFrame=State.AppliedFrame;LastPublicationTick=WorldTicks;MaxSolveMs=FMath::Max(MaxSolveMs,double(State.SolveMilliseconds));
        FVector Root,Velocity,PreviousRoot;float Yaw=0,PreviousYaw=0;
        if(!ProphecyFootIKSurface::Root(Agent,Root,Yaw,&Velocity)||!ProphecyFootIKSurface::History(Agent,PreviousRoot,PreviousYaw)){Error=TEXT("Missing coupled carrier/history");return false;}
        MaxRootError=FMath::Max(MaxRootError,FVector::Distance(Root,Agent->GetRootLowPoint()));if(MaxRootError>.02){Error=TEXT("The manager advanced a different root than the causal solver");return false;}
        if(FMath::Abs(FMath::FindDeltaAngleDegrees(InitialYaw,Yaw))>30)SawTurn=true;
        FTransform Prior[25],Current[25],Local[25];if(!ProphecyFootIKSurface::Apply(Agent,MakeArrayView(Bones),MakeArrayView(Parents),MakeArrayView(Prior),MakeArrayView(Current),MakeArrayView(Local),FTransform::Identity)){Error=TEXT("Missing complete published pose");return false;}
        FString Mismatch;
        for(int32 I=0;I<25;++I)
        {
            FTransform A,B,Visible;float Alpha=0;if(!Agent->GetAuthoredBodyWorldTarget(Bones[I],A,B,Visible,Alpha)){Error=TEXT("Missing authored body target");return false;}
            if(Current[I].ContainsNaN()||Prior[I].ContainsNaN()||Visible.ContainsNaN()){Error=TEXT("Nonfinite body during surface ownership");return false;}
            const double Endpoint=FVector::Distance(Current[I].GetLocation(),B.GetLocation()),Presented=FVector::Distance(Current[I].GetLocation(),Visible.GetLocation()),Angle=Current[I].GetRotation().AngularDistance(Visible.GetRotation());
            MaxTargetError=FMath::Max(MaxTargetError,FMath::Max(Endpoint,Presented));MaxRotationError=FMath::Max(MaxRotationError,Angle);
            if(Mismatch.IsEmpty()&&(Endpoint>.02||Presented>.02||Angle>1.e-5))
            {
                const FQuat WantedQ=Current[I].GetRotation(),EndQ=B.GetRotation(),VisibleQ=Visible.GetRotation(),OldQ=A.GetRotation();
                Mismatch=FString::Printf(TEXT("frame %d, %s: endpoint %.8gcm, presented %.8gcm / %.8grad, alpha %.8g; normalized end/presented/old-visible %.9g/%.9g/%.9grad; norm2 wanted/end/visible/old %.17g/%.17g/%.17g/%.17g; old-end dot %.17g"),State.AppliedFrame,*Bones[I].ToString(),Endpoint,Presented,Angle,double(Alpha),WantedQ.GetNormalized().AngularDistance(EndQ.GetNormalized()),WantedQ.GetNormalized().AngularDistance(VisibleQ.GetNormalized()),OldQ.GetNormalized().AngularDistance(VisibleQ.GetNormalized()),WantedQ.SizeSquared(),EndQ.SizeSquared(),VisibleQ.SizeSquared(),OldQ.SizeSquared(),OldQ.GetNormalized()|EndQ.GetNormalized());
            }
        }
        if(!Mismatch.IsEmpty()){Error=TEXT("The published pose has extra interpolation or a different carrier: ")+Mismatch;return false;}
        ProphecyFootIKSurface::FPolicyHandoff H;if(!ProphecyFootIKSurface::ReadPolicyHandoff(Agent,H,Error))return false;
        if(H.Current.BodiesWorld.Num()!=25||H.Previous.BodiesWorld.Num()!=25||!H.Current.RootWorld.Equals(Root,.001)){Error=TEXT("Raw policy handoff does not match accepted root history");return false;}
        SawSlide|=H.WasSliding;++Checked;return true;
    }
    bool CheckOrdinaryTargets(bool MustBeRaw,FString& Error)
    {
        TArray<FName> Names,RawNames;TArray<FTransform> Future,Visible,RawFuture,Raw;FProphecyNNPoseSnapshot Snapshot,RawSnapshot;float Alpha=0,RawAlpha=0;
        if(!Agent->ReadNNFutureWorldPoseWithSnapshot(Names,Future,Visible,Alpha,Snapshot,true)||!Agent->ReadNNFutureWorldPoseWithSnapshot(RawNames,RawFuture,Raw,RawAlpha,RawSnapshot,false)||Names!=RawNames)
        {Error=TEXT("Resumed ordinary NN did not publish a complete current/history pair");return false;}
        for(const FName Name:Bones)
        {
            const int32 I=Names.IndexOfByKey(Name);FTransform Previous,Current,Single;float A=0;
            if(!Raw.IsValidIndex(I)||!Visible.IsValidIndex(I)||Raw[I].ContainsNaN()||Visible[I].ContainsNaN()||!Agent->GetAuthoredBodyWorldTarget(Name,Previous,Current,Single,A)||Previous.ContainsNaN()||Current.ContainsNaN())
            {Error=TEXT("Missing/nonfinite resumed body target");return false;}
            if(!Single.GetLocation().Equals(Visible[I].GetLocation(),.02)||Single.GetRotation().AngularDistance(Visible[I].GetRotation())>1.e-5)
            {Error=TEXT("Resumed whole-pose and single-body targets disagree");return false;}
            if(MustBeRaw&&!Visible[I].Equals(Raw[I],1.e-8)){Error=TEXT("Disabled/fallback owner retained a stale terrain target");return false;}
        }
        return true;
    }
public:
    explicit FExercise(FAutomationTestBase* In):Test(In){}
    ~FExercise(){Cleanup();}
    bool Update() override
    {
        if(FPlatformTime::Seconds()-Started>600)return Fail(TEXT("Timed out"));
        if(Stage==0)
        {
            if(ProphecyFootIKSurface::AnyActive()||ProphecyFootIKLive::AnyEnabled())return Fail(TEXT("Use an isolated automation host"));
            const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);if(!World)return Fail(TEXT("Could not create transient world"));if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();if(!Manager)return Fail(TEXT("Could not create actual NN manager"));Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->EndpointAFallback=FVector::ZeroVector;Manager->EndpointBFallback=FVector(2000,0,0);
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();Agent=Manager->ResolveAgent(Manager->GetAgentHandle(0));if(!Agent)return Fail(TEXT("Manager did not register its agent"));
            Agent->SetUpperNNInputs(false,0,0);Agent->SetLocomotionInput(FVector::ForwardVector,true,FVector::ForwardVector);Stage=1;return false;
        }
        World->Tick(LEVELTICK_All,1.f/60);++WorldTicks;FString Error;
        if(Stage==1)
        {
            if(++Ticks<12)return false;const FVector Root=Agent->GetRootLowPoint();InitialYaw=Agent->GetActorRotation().Yaw;
            // A newly spawned blocking floor needs the same 1mm sweep skin as
            // ordinary navigation; exact tangency can block at sweep time0.
            Box(Root-FVector(0,0,10.1),FVector(200000,4000,10));Wall=Box(Root+FVector(150,0,0),FVector(10,1500,8000));PreparationRoot=Root;
            if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"terrain\":\"incline\",\"gait\":\"run\",\"inclineGravity\":true,\"minGravityIncline\":80,\"fullGravity\":100,\"energyConservation\":100,\"slideEnabled\":true,\"slideSpeed\":0.2}"),Error)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Fail(Error);
            Stage=2;Ticks=0;return false;
        }
        if(Stage==2)
        {
            if(!Check(Error))return Fail(Error);
            if(!ProphecyFootIKSurface::Active(Agent))
            {
                FProphecyFootIKLiveState State;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State))return Fail(TEXT("Missing preparing state"));
                if(++PreparationTicks>3&&!State.Preparing)return Fail(TEXT("Cold preparation was not reported without an error"));
                PreparationTravel=FVector::Distance(PreparationRoot,Agent->GetRootLowPoint());
                // Keep the finite collider ahead while the ordinary controller
                // moves. Freeze it on activation; never author root or pose.
                Wall->SetActorLocation(Agent->GetRootLowPoint()+FVector(150,0,0));return false;
            }
            if(PreparationTicks>4&&PreparationTravel<5)return Fail(TEXT("Ordinary movement froze during background preparation"));
            ++Ticks;
            if(Ticks==70)Agent->SetLocomotionInput(FVector::ForwardVector,true,FVector::RightVector);
            if(Ticks==120)Agent->SetLocomotionInput(FVector::ForwardVector,true,-FVector::ForwardVector);
            if(Ticks<180)return false;if(Checked<120||!SawSlide||!SawTurn)return Fail(TEXT("The exercise did not reach slide and live facing changes"));
            FVector Root,Velocity;float Yaw=0;if(!ProphecyFootIKSurface::Root(Agent,Root,Yaw,&Velocity))return Fail(TEXT("Missing surface root before disable"));
            DisabledRoot=Agent->GetRootLowPoint();DisabledStepLimit=FMath::Max(25.,Velocity.Size()/60.+10.);
            if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error))return Fail(Error);
            if(ProphecyFootIKSurface::Active(Agent)||ProphecyFootIKSurface::AnyActive()||ProphecyFootIKLive::Enabled(Agent)||ProphecyFootIKLive::HasCallbacks())return Fail(TEXT("Disable retained surface/live ownership"));
            if(!Agent->GetRootLowPoint().Equals(DisabledRoot,.02))return Fail(TEXT("Disabling slide teleported the accepted root"));
            if(!CheckOrdinaryTargets(true,Error))return Fail(Error);
            LastDisabledRoot=DisabledRoot;Agent->SetLocomotionInput(-FVector::ForwardVector,true,-FVector::ForwardVector);Stage=3;Ticks=0;return false;
        }
        if(Stage==3)
        {
            if(ProphecyFootIKSurface::Active(Agent)||ProphecyFootIKLive::Enabled(Agent)||ProphecyFootIKLive::HasCallbacks())return Fail(TEXT("Disabled owner resumed itself"));
            if(!CheckOrdinaryTargets(true,Error))return Fail(Error);
            const double Step=FVector::Distance(LastDisabledRoot,Agent->GetRootLowPoint());LastDisabledRoot=Agent->GetRootLowPoint();MaxDisabledStep=FMath::Max(MaxDisabledStep,Step);
            if(Step>DisabledStepLimit)return Fail(TEXT("First ordinary NN/controller steps snapped to an obsolete surface root"));if(++Ticks<30)return false;
            if(FVector::Distance(DisabledRoot,Agent->GetRootLowPoint())<5)return Fail(TEXT("Ordinary mover did not resume"));
            if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"terrain\":\"flat\",\"gait\":\"run\"}"),Error)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Fail(Error);Stage=4;Ticks=0;LastFrame=LastPublicationTick=-1;return false;
        }
        if(Stage==4)
        {
            if(++Ticks==5)
            {
                if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"terrain\":\"flat\",\"gait\":\"walk\",\"clearance\":0.02}"),Error))return Fail(Error);
                Reconfigured=true;LastFrame=LastPublicationTick=-1;RenewedFrames=RenewedReadyTicks=0;FallbackRun=0;
            }
            FProphecyFootIKLiveState State;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State)||!State.Error.IsEmpty())return Fail(State.Error.IsEmpty()?TEXT("Reconfigured state disappeared"):State.Error);
            const bool Fresh=State.AppliedFrame>LastFrame;
            if(State.AppliedFrame<LastFrame)return Fail(TEXT("Reconfigured live epoch rewound"));
            if(Fresh)
            {
                if(!State.Ready)return Fail(TEXT("Reconfigured owner published an unprepared frame"));
                if(LastPublicationTick>=0&&State.AppliedFrame-LastFrame!=WorldTicks-LastPublicationTick)return Fail(TEXT("Reconfigured owner replayed a stale asynchronous frame"));
                LastFrame=State.AppliedFrame;LastPublicationTick=WorldTicks;FallbackRun=0;if(Reconfigured)++RenewedFrames;
            }
            else {++ReconfigureFallbackTicks;MaxFallbackRun=FMath::Max(MaxFallbackRun,++FallbackRun);}
            if(!CheckOrdinaryTargets(!Fresh,Error))return Fail(Error);
            if(Reconfigured&&State.Ready&&++RenewedReadyTicks>=180&&RenewedFrames<20)
                return Fail(FString::Printf(TEXT("Reconfigured surface handoff produced only %d fresh frames in %d ready game ticks"),RenewedFrames,RenewedReadyTicks));
            if(Ticks<12||!Reconfigured||RenewedFrames<20)return false;
            Save(true,FString());Test->AddInfo(FString::Printf(TEXT("%d live surface frames checked; %d renewed frames; max root %.6gcm, target %.6gcm; max solve %.3fms"),Checked,RenewedFrames,MaxRootError,MaxTargetError,MaxSolveMs));Cleanup();return true;
        }
        return false;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKSurfaceOwnerLifecycle,"Prophecy.FootIK.Live.SurfaceOwnerLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKSurfaceOwnerLifecycle::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(ProphecyFootIKSurfaceTests::FExercise(this));return true;}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKTinyRotationEndpoints,"Prophecy.FootIK.Presentation.TinyRotationEndpoints",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKTinyRotationEndpoints::RunTest(const FString&)
{
    constexpr int32 Id=912460;constexpr double Source=4.;
    // Exercise the real whole-pose, single-body and shared presentation readers.
    // No world tick, neural policy, terrain solver or physical rig is required.
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if(!TestNotNull(TEXT("Tiny-rotation fixture world"),World))return false;
    AProphecyAgent* Agent=World->SpawnActor<AProphecyAgent>();
    if(!Agent){World->DestroyWorld(false);World->MarkAsGarbage();AddError(TEXT("Tiny-rotation fixture agent"));return false;}
    Agent->bManualNNPoseApplication=false;Agent->ConfigureNNPoseDataSource(Id,1.f/30,true);Agent->SetNNInterpolationMode(EProphecyNNInterpolationMode::Current);
    const TArray<FName> Names{TEXT("foot_l")};const FVector Axis=FVector(1,2,3).GetSafeNormal();const FQuat Start=FRotator(11,29,-7).Quaternion();
    const FTransform Carrier(FRotator(-3,81,5),FVector(31,-27,44));
    for(double Angle:{1.e-8,1.e-6,1.e-4,.00047466125,.0009})
    {
        const TArray<FTransform> Previous{FTransform(Start,FVector(1,2,3))},Current{FTransform(FQuat(Axis,Angle)*Start,FVector(4,6,8))};
        FProphecyNNPoseStore::SetAgentLocalPose(Id,Names,Current,Previous,Current,Carrier,Carrier,Source);
        for(float Alpha:{0.f,.5f,1.f})
        {
            if(Alpha==.5f&&Angle<1.e-5)continue; // Existing sub-microradian interior deadband is unchanged.
            ProphecyNNPresentation::Publish(Id,Source,Alpha);
            const FTransform A=Previous[0]*Carrier,B=Current[0]*Carrier;
            const FTransform Expected(Alpha==0?A.GetRotation():(Alpha==1?B.GetRotation():FQuat::Slerp(A.GetRotation(),B.GetRotation(),.5).GetNormalized()),FMath::Lerp(A.GetLocation(),B.GetLocation(),Alpha));
            FTransform Old,End,Single,Shared;float SingleAlpha=-1,WholeAlpha=-1;TArray<FName> OutNames;TArray<FTransform> Future,Whole;FProphecyNNPoseSnapshot Snapshot;
            const bool Read=Agent->GetAuthoredBodyWorldTarget(Names[0],Old,End,Single,SingleAlpha)
                &&Agent->ReadNNFutureWorldPoseWithSnapshot(OutNames,Future,Whole,WholeAlpha,Snapshot,false)
                &&ProphecyNNPresentation::ReadBoneWorld(Id,Names[0],Shared);
            if(!TestTrue(TEXT("All actual presentation readers returned the tiny rotation"),Read)||Whole.Num()!=1)continue;
            TestEqual(TEXT("Single-body reader uses the requested progress"),SingleAlpha,Alpha);TestEqual(TEXT("Whole-pose reader uses the requested progress"),WholeAlpha,Alpha);
            for(const FTransform& Observed:{Single,Whole[0],Shared})
            {
                // Compare normalized quaternion components, avoiding acos's
                // conditioning near zero while retaining a much tighter bound.
                TestTrue(FString::Printf(TEXT("Angle %.9g alpha %.1f keeps exact orientation"),Angle,double(Alpha)),Observed.GetRotation().GetNormalized().Equals(Expected.GetRotation().GetNormalized(),1.e-11));
                TestTrue(TEXT("The same presentation endpoint retains translation"),Observed.GetLocation().Equals(Expected.GetLocation(),1.e-10));
            }
        }
    }
    Agent->ClearNNPoseDataSource();FProphecyNNPoseStore::ClearAgentPose(Id);World->DestroyWorld(false);World->MarkAsGarbage();return true;
}
#endif
