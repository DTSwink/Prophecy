#include "CoreMinimal.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKLiveLibrary.h"
#include "ProphecyFootIKOwner.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyPhysicalFootTarget.h"
#include "ProphecyFootIKJoltFixture.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace FootIKLiveJoltTest
{
// Same complete name set as the manager's feedback capture: requesting a
// different subset would rebind the cache every time the manager samples it.
const FName Names[]={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
const int32 DrivenLower[]={0,17,18,19,21,22,23};
class FExercise final:public IAutomationLatentCommand
{
    FAutomationTestBase* Test;UWorld* World=nullptr;AProphecyNNLocomotionManager* Manager=nullptr;AProphecyAgent* Agent=nullptr;AActor* JoltFloor=nullptr;
    UProphecyJoltCharacterComponent* Character=nullptr;
    int32 Stage=0,Ticks=0,Checks=0,DisabledChecks=0,CorrectedSteps=0,LastApplied=-1,Joined=0;
    double Started=FPlatformTime::Seconds(),NextTick=0,MaxTargetCm=0,MaxTargetAngle=0,MaxPhysicalCm=0,MaxCorrectionCm=0,MaxFeedbackReadCm=0,MaxFeedbackReadAngle=0;
    void Cleanup()
    {
        if(Agent){FString E;UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,E);Agent->DisableJoltPhysicalAnimation();}
        Character=nullptr;Agent=nullptr;Manager=nullptr;
        if(World){World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);World->MarkAsGarbage();World=nullptr;}
    }
    bool Finish(bool Good,const FString& Error=FString())
    {
        auto R=MakeShared<FJsonObject>();R->SetBoolField(TEXT("success"),Good);R->SetStringField(TEXT("error"),Error);
        R->SetStringField(TEXT("source"),TEXT("ordinary manager/controller + live terrain overlay; production target publication and explicit completed Jolt step"));
        R->SetNumberField(TEXT("checkedSteps"),Checks);R->SetNumberField(TEXT("disabledSteps"),DisabledChecks);R->SetNumberField(TEXT("correctedSteps"),CorrectedSteps);R->SetNumberField(TEXT("joinedFrames"),Joined);
        R->SetNumberField(TEXT("maxAuthoredTargetErrorCm"),MaxTargetCm);R->SetNumberField(TEXT("maxAuthoredTargetAngleRad"),MaxTargetAngle);R->SetNumberField(TEXT("maxTerrainCorrectionCm"),MaxCorrectionCm);
        R->SetNumberField(TEXT("maxPhysicalDistanceCm"),MaxPhysicalCm);R->SetNumberField(TEXT("maxFeedbackReaderErrorCm"),MaxFeedbackReadCm);R->SetNumberField(TEXT("maxFeedbackReaderErrorRad"),MaxFeedbackReadAngle);
        FString Text;FJsonSerializer::Serialize(R,TJsonWriterFactory<>::Create(&Text));FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/live-jolt-target-feedback.json")));
        if(!Good)Test->AddError(TEXT("Live Foot IK Jolt targets: ")+Error);Cleanup();return true;
    }
    bool Step(bool Disabled,FString& Error)
    {
        TArray<FName> RawNames,VisibleNames;TArray<FTransform> RawFuture,Raw,Future,Visible;FProphecyNNPoseSnapshot RawSnapshot,Snapshot;float A=0,B=0;
        if(!Agent->ReadNNFutureWorldPoseWithSnapshot(RawNames,RawFuture,Raw,A,RawSnapshot,false)||!Agent->ReadNNFutureWorldPoseWithSnapshot(VisibleNames,Future,Visible,B,Snapshot,true)||RawNames!=VisibleNames)
        {Error=TEXT("Missing ordinary/final target pair");return false;}
        TArray<FTransform> Expected;Expected.SetNum(25);double Correction=0;
        for(int32 I=0;I<25;++I)
        {
            const int32 J=VisibleNames.IndexOfByKey(Names[I]);if(!Visible.IsValidIndex(J)||!Raw.IsValidIndex(J)){Error=TEXT("Missing target bone");return false;}
            Expected[I]=Visible[J];if(Disabled&&!Raw[J].Equals(Visible[J],1.e-10)){Error=TEXT("Disabled live layer still changes targets");return false;}
            if(I>=17)Correction=FMath::Max(Correction,FVector::Distance(Raw[J].GetLocation(),Visible[J].GetLocation()));
        }
        MaxCorrectionCm=FMath::Max(MaxCorrectionCm,Correction);
        // Jolt's existing physical ankle target follows the calibrated calf
        // endpoint, within the configured allowance. It is deliberately not
        // identical to an unconstrained rendered NN ankle translation.
        const auto* Mesh=Agent->GetPoseReferenceMesh();if(!Mesh||!Mesh->GetSkeletalMeshAsset()){Error=TEXT("Missing physical rig calibration");return false;}
        const auto& Skeleton=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
        const double Leeway=FMath::Max(ProphecyPhysicalFootTarget::Leeway(Agent),ProphecyPhysicalFootTarget::CalfLeeway(Agent));
        for(const int32 Foot:{19,23})
        {
            const int32 Bone=Skeleton.FindBoneIndex(Names[Foot]);if(Bone<0){Error=TEXT("Missing foot calibration");return false;}
            const FVector End=Expected[Foot-1].TransformPosition(Skeleton.GetRefBonePose()[Bone].GetTranslation());
            Expected[Foot].SetLocation(ProphecyPhysicalFootTarget::Clamp(Expected[Foot].GetLocation(),End,float(Leeway)));
        }
        FTransform Actual[25],Authored[25];
        Character->SampleCompletedLowerFeedbackPose(MakeArrayView(Names),FTransform::Identity,MakeArrayView(Actual),MakeArrayView(Authored));
        const uint64 Before=Character->GetRevision();
        if(!Character->PublishAuthoredTargets(1.f/60,Error)||!Character->StepAndPublish(1.f/60,Error))return false;
        if(Character->GetRevision()!=Before+1||!Character->SampleCompletedLowerFeedbackPose(MakeArrayView(Names),FTransform::Identity,MakeArrayView(Actual),MakeArrayView(Authored)))
        {Error=TEXT("Completed feedback did not match the just-completed servo step");return false;}
        FTransform Component[25],RelativeActual[25],RelativeAuthored[25];
        const FTransform Reference(FRotator(11,29,-7),FVector(83,-51,142));
        if(!Character->SampleCompletedComponentPose(MakeArrayView(Names),MakeArrayView(Component))||!Character->SampleCompletedLowerFeedbackPose(MakeArrayView(Names),Reference,MakeArrayView(RelativeActual),MakeArrayView(RelativeAuthored)))
        {Error=TEXT("Completed physical-feedback readers disagree on availability");return false;}
        for(const int32 I:DrivenLower)
        {
            if(Actual[I].ContainsNaN()||Authored[I].ContainsNaN()){Error=TEXT("Nonfinite completed lower-body sample");return false;}
            const double D=FVector::Distance(Expected[I].GetLocation(),Authored[I].GetLocation()),Q=Expected[I].GetRotation().AngularDistance(Authored[I].GetRotation());
            MaxTargetCm=FMath::Max(MaxTargetCm,D);MaxTargetAngle=FMath::Max(MaxTargetAngle,Q);MaxPhysicalCm=FMath::Max(MaxPhysicalCm,FVector::Distance(Actual[I].GetLocation(),Authored[I].GetLocation()));
            const FTransform FromComponent=Component[I]*Agent->GetAgentMesh()->GetComponentTransform(),RA=RelativeActual[I]*Reference,RT=RelativeAuthored[I]*Reference;
            const double ReaderError=FMath::Max(FVector::Distance(Actual[I].GetLocation(),FromComponent.GetLocation()),FMath::Max(FVector::Distance(Actual[I].GetLocation(),RA.GetLocation()),FVector::Distance(Authored[I].GetLocation(),RT.GetLocation())));
            const double ReaderAngle=FMath::Max(Actual[I].GetRotation().AngularDistance(FromComponent.GetRotation()),FMath::Max(Actual[I].GetRotation().AngularDistance(RA.GetRotation()),Authored[I].GetRotation().AngularDistance(RT.GetRotation())));
            MaxFeedbackReadCm=FMath::Max(MaxFeedbackReadCm,ReaderError);MaxFeedbackReadAngle=FMath::Max(MaxFeedbackReadAngle,ReaderAngle);
            if(D>.01||Q>1.e-5||ReaderError>.001||ReaderAngle>1.e-5){Error=FString::Printf(TEXT("%s completed target/feedback mismatch: %.8gcm, %.8grad, reader %.8gcm/%.8grad"),*Names[I].ToString(),D,Q,ReaderError,ReaderAngle);return false;}
        }
        if(Disabled)++DisabledChecks;else{++Checks;if(Correction>.2)++CorrectedSteps;}return true;
    }
public:
    explicit FExercise(FAutomationTestBase* T):Test(T){}
    ~FExercise(){Cleanup();}
    bool Update() override
    {
        const double Now=FPlatformTime::Seconds();if(Now-Started>3600)return Finish(false,TEXT("Cold/live physical test watchdog expired"));
        if(Stage==0)
        {
            if(ProphecyFootIKLive::AnyEnabled()||ProphecyFootIK::AnyActive())return Finish(false,TEXT("Use an isolated test host"));
            const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true).EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);if(!World)return Finish(false,TEXT("No transient world"));if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            const FTransform FloorTransform(FQuat::Identity,FVector(0,0,-20),FVector(2000,2000,.4));auto* Floor=World->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(),FloorTransform);
            if(!Floor)return Finish(false,TEXT("No physical floor"));Floor->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));Floor->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));Floor->GetStaticMeshComponent()->SetMobility(EComponentMobility::Static);Floor->FinishSpawning(FloorTransform);JoltFloor=Floor;
            Manager=World->SpawnActor<AProphecyNNLocomotionManager>();if(!Manager)return Finish(false,TEXT("No NN manager"));Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->EndpointAFallback=FVector::ZeroVector;Manager->EndpointBFallback=FVector(10000,0,0);
            FString Error;Agent=ProphecyFootIKJoltFixture::Spawn(World,Manager,Error);if(!Agent)return Finish(false,Error);
            World->InitializeActorsForPlay(FURL());World->SetBegunPlay(true);Manager->DispatchBeginPlay();if(Manager->ResolveAgent(Manager->GetAgentHandle(0))!=Agent||!ProphecyFootIKJoltFixture::Bind(Agent,Error))return Finish(false,Error.IsEmpty()?TEXT("Manual agent registration mismatch"):Error);Agent->SetUpperNNInputs(false,0,0);Agent->SetLocomotionInput(FVector::ZeroVector,false,FVector::ForwardVector);Stage=1;return false;
        }
        if(Now<NextTick)return false;NextTick=Now+1./60.;World->Tick(LEVELTICK_All,1.f/60);FString Error;
        if(Stage==1)
        {
            if(++Ticks<16)return false;if(!UProphecyFootIKLiveLibrary::ConfigureLiveFootIK(Agent,TEXT("{\"terrain\":\"stairs\",\"gait\":\"walk\"}"),Error)||!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,true,Error))return Finish(false,Error);Stage=2;return false;
        }
        if(Stage==2)
        {
            FProphecyFootIKLiveState State;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State)||!State.Error.IsEmpty())return Finish(false,State.Error);if(!State.Ready)return false;
            auto* Shelf=World->SpawnActor<AActor>();auto* Box=NewObject<UBoxComponent>(Shelf);Shelf->SetRootComponent(Box);Box->SetBoxExtent(FVector(150,200,4));Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Box->SetCollisionResponseToAllChannels(ECR_Ignore);Box->ComponentTags.Add(TEXT("FootIKFeet"));Box->RegisterComponent();Shelf->SetActorLocation(Agent->GetRootLowPoint()+FVector(250,0,4));
            if(!ProphecyFootIKJoltFixture::InitializeWorld(World,JoltFloor,Agent,false,Error)||!ProphecyFootIKJoltFixture::Enable(Agent,Error))return Finish(false,Error);Character=Agent->GetJoltCharacterComponent();if(!Character)return Finish(false,TEXT("Missing Jolt component"));Character->bAutomaticStep=false;Agent->SetLocomotionInput(FVector::ForwardVector,false,FVector::ForwardVector);Stage=3;Ticks=0;return false;
        }
        if(Stage==3||Stage==4)
        {
            if(!Character->IsJoltPhysical()){if(Character->IsEnablePending())return false;return Finish(false,Character->GetLastError());}
            if(Stage==3)
            {
                FProphecyFootIKLiveState State;if(!UProphecyFootIKLiveLibrary::GetLiveFootIKState(Agent,State)||!State.Error.IsEmpty())return Finish(false,State.Error);if(State.AppliedFrame>LastApplied){LastApplied=State.AppliedFrame;++Joined;}
            }
            if(!Step(Stage==4,Error))return Finish(false,Error);
            if(Stage==3&&++Ticks>=240)
            {
                if(Joined<20||CorrectedSteps<4||MaxCorrectionCm<=.2)return Finish(false,TEXT("No sustained live terrain correction reached the physical test"));
                if(!UProphecyFootIKLiveLibrary::SetFootIKEnabled(Agent,false,Error))return Finish(false,Error);Stage=4;Ticks=0;return false;
            }
            if(Stage==4&&++Ticks>=30)
            {
                if(ProphecyFootIKLive::Enabled(Agent)||ProphecyFootIKLive::HasCallbacks())return Finish(false,TEXT("Disable retained live ownership/callbacks"));return Finish(true);
            }
        }
        return false;
    }
};
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFootIKLiveJoltTargets,"Prophecy.FootIK.Live.JoltTargetAndFeedback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFootIKLiveJoltTargets::RunTest(const FString&){ADD_LATENT_AUTOMATION_COMMAND(FootIKLiveJoltTest::FExercise(this));return true;}
#endif
