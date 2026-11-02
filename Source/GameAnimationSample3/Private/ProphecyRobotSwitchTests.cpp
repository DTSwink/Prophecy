#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyRobotLocomotion.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyNNPoseTypes.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/SkeletalMesh.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "ProphecyAttackCamera.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRobotSwitch,"Prophecy.Robotics.AgentSwitch",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRobotSwitch::RunTest(const FString&)
{
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true).CreateFXSystem(false).SetTransactional(false);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if(!World)return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    struct FCleanup{UWorld* W;~FCleanup(){W->DestroyWorld(false);GEngine->DestroyWorldContext(W);W->MarkAsGarbage();}}Cleanup{World};
    World->InitializeActorsForPlay(FURL());
    auto* Owner=World->GetSubsystem<UProphecyJoltWorldSubsystem>();FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared=FVector(0,0,-981);
    if(!Owner->InitializeSimulation(Settings).IsSuccess())return false;
    FProphecyJoltFixtureBodySettings Floor;Floor.bDynamic=false;Floor.PositionCm=FVector(0,0,-5);Floor.Friction=1;
    FProphecyJoltBodyHandle Ground;if(!Owner->CreateBox(FVector(10000,10000,5),0,Floor,Ground).IsSuccess())return false;
    auto* Asset=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    auto* PHAT=LoadObject<UPhysicsAsset>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin"));
    auto* Agent=World->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(),FTransform::Identity,
        nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    Agent->bManualNNPoseApplication=true;Agent->bAutoEnsureStandaloneNNManager=false;
    Agent->bEnableAttackFists=false;Agent->bUseBlueprintLocomotionInput=true;
    Agent->AutoPossessAI=EAutoPossessAI::Disabled;Agent->AutoPossessPlayer=EAutoReceiveInput::Disabled;
    auto* Mesh=NewObject<USkeletalMeshComponent>(Agent,TEXT("PhysicalMesh"));
    Agent->AddInstanceComponent(Mesh);Mesh->SetupAttachment(Agent->GetAgentCapsule());
    Mesh->SetSkeletalMesh(Asset);Mesh->SetPhysicsAsset(PHAT);Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
    Mesh->SetCollisionResponseToAllChannels(ECR_Block);Mesh->RegisterComponent();
    Agent->GetAgentMesh()->SetSkeletalMesh(nullptr);Agent->FinishSpawning(FTransform::Identity);Agent->DispatchBeginPlay();
    Agent->SetMACDEnabled(false);
    auto* Manager=World->SpawnActorDeferred<AProphecyNNLocomotionManager>(AProphecyNNLocomotionManager::StaticClass(),FTransform::Identity);
    Manager->ConfigureSimpleLocomotionTest();Manager->PreferredRuntime=TEXT("NNERuntimeORTCpu");Manager->PlayerAgent=Agent;
    Manager->FinishSpawning(FTransform::Identity);Manager->DispatchBeginPlay();
    if(!TestTrue(TEXT("Native NN manager registered agent"),Manager->ResolveAgent(Agent->GetAgentHandle())==Agent))return false;
    auto Tick=[&](int32 Count)
    {
        for(int32 I=0;I<Count;++I){++GFrameCounter;World->Tick(LEVELTICK_All,1.f/60);}
    };
    Tick(10);Agent->ApplyNNPoseKinematically(1.f/60);
    const TArray<FName> Bones={TEXT("pelvis"),TEXT("head"),TEXT("hand_l"),TEXT("hand_r"),TEXT("foot_l"),TEXT("foot_r")};
    auto Capture=[&](){TArray<FTransform> R;for(auto B:Bones)R.Add(Mesh->GetSocketTransform(B));return R;};
    auto Compare=[&](const TCHAR* Label,const TArray<FTransform>& Before)
    {
        const auto After=Capture();double Position=0,Angle=0;
        for(int32 I=0;I<Before.Num();++I){Position=FMath::Max(Position,FVector::Distance(Before[I].GetLocation(),After[I].GetLocation()));
            Angle=FMath::Max(Angle,FMath::RadiansToDegrees(Before[I].GetRotation().AngularDistance(After[I].GetRotation())));}
        AddInfo(FString::Printf(TEXT("%s: %.6f cm / %.6f deg"),Label,Position,Angle));
        TestTrue(Label,Position<.1&&Angle<.1);
    };
    FString Error;
    TestNull(TEXT("Unpossessed NN agent has no camera follower"),Agent->FindComponentByClass<UProphecyAttackCameraComponent>());
    auto* PC=World->SpawnActor<APlayerController>();PC->Possess(Agent);
    auto* Spring=Agent->GetAgentSpringArm();
    Spring->SetRelativeLocation(FVector(30,20,29));Spring->TargetOffset=FVector(5,40,12);
    const FVector IndependentCameraOffset=Spring->TargetOffset;
    auto Pivot=[&](){return Spring->GetComponentLocation()+Spring->TargetOffset;};
    auto CheckRobotCamera=[&]()
    {
        const auto* P=ProphecyRobot::Profile(Error);FVector COM=FVector::ZeroVector;double Mass=0;
        for(const auto& Spec:P->Bodies)
        {
            FProphecyJoltBodyHandle H;FProphecyJoltBodyState B;
            if(!Agent->GetJoltCharacterComponent()->GetBodyHandle(Spec.Bone,H)||!Owner->ReadBody(H,B).IsSuccess())return false;
            COM+=B.CenterOfMassPositionCm*Spec.Mass;Mass+=Spec.Mass;
        }
        COM/=Mass;COM.Z=0;
        const FVector Expected=Spring->GetComponentLocation()+IndependentCameraOffset+COM-Agent->GetRootLowPoint();
        return TestTrue(TEXT("Robot camera follows actual mass-weighted COM at floor Z=0"),Pivot().Equals(Expected,1.e-4));
    };
    const FVector EntryPivot=Pivot();
    const auto Before=Capture();
    if(!UProphecyLocomotionTypeLibrary::SetLocomotionType(Agent,EProphecyLocomotionType::GetUp,Error)){AddError(Error);return false;}
    TestTrue(TEXT("Get Up has physical ownership"),Agent->IsJoltPhysicalAnimationEnabled()&&!Agent->bNNInferenceEnabled);
    TestTrue(TEXT("NN to Get Up keeps camera pivot continuous"),Pivot().Equals(EntryPivot,1.e-6));
    Compare(TEXT("NN to robot preserves pose"),Before);
    Tick(120);
    CheckRobotCamera();
    if(Agent->GetJoltCharacterComponent()->IsSteppingStopped()){AddError(Agent->GetJoltCharacterComponent()->GetLastError());return false;}
    auto* Component=Agent->GetJoltCharacterComponent();FProphecyJoltBodyHandle Original;Component->GetBodyHandle(TEXT("pelvis"),Original);
    const FVector RobotSwitchPivot=Pivot();
    if(!UProphecyLocomotionTypeLibrary::SetLocomotionType(Agent,EProphecyLocomotionType::Clanker,Error)){AddError(Error);return false;}
    TestTrue(TEXT("Get Up to Clanker leaves the camera transition alone"),Pivot().Equals(RobotSwitchPivot,1.e-6));
    FProphecyJoltBodyHandle Same;Component->GetBodyHandle(TEXT("pelvis"),Same);
    TestTrue(TEXT("Robot switch retains the live bodies"),Original.Slot==Same.Slot&&Original.Generation==Same.Generation&&Original.WorldLifetime==Same.WorldLifetime);
    Tick(120);const auto Exit=Capture();
    CheckRobotCamera();const FVector ExitPivot=Pivot();
    FProphecyJoltWorldDiagnostics Diagnostics;Owner->GetDiagnostics(Diagnostics);
    TestTrue(TEXT("Real shared-world physics advanced during robot ownership"),Diagnostics.CompletedSteps>=240);
    if(!UProphecyLocomotionTypeLibrary::SetLocomotionType(Agent,EProphecyLocomotionType::NN,Error)){AddError(Error);return false;}
    TestTrue(TEXT("NN restores previous ownership"),Agent->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic&&Agent->bNNInferenceEnabled);
    TestTrue(TEXT("Robot to NN keeps camera pivot continuous immediately"),Pivot().Equals(ExitPivot,1.e-6));
    Compare(TEXT("Robot to NN preserves pose"),Exit);
    Tick(1);Compare(TEXT("Waiting for the first NN step does not rewind the pose"),Exit);
    TestTrue(TEXT("Robot to NN keeps camera pivot continuous after late root movement"),Pivot().Equals(ExitPivot,1.e-6));
    Tick(89);
    TestTrue(TEXT("NN return restores independent camera offset"),Spring->TargetOffset.Equals(IndependentCameraOffset,1.e-6));
    TestFalse(TEXT("Finished NN camera return retires ticking"),Agent->FindComponentByClass<UProphecyAttackCameraComponent>()->IsComponentTickEnabled());
    for(const auto& T:Capture())TestFalse(TEXT("NN return remains finite"),T.ContainsNaN());
    // Also exercise entry/exit when the NN itself owns simulated bodies.
    if(!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))return false;
    Tick(4);const auto SimEntry=Capture();
    if(!UProphecyLocomotionTypeLibrary::SetLocomotionType(Agent,EProphecyLocomotionType::GetUp,Error)){AddError(Error);return false;}
    Compare(TEXT("Physical NN to robot preserves pose"),SimEntry);
    Tick(120);const auto SimExit=Capture();
    FProphecyJoltBodyHandle RobotPelvis;Agent->GetJoltCharacterComponent()->GetBodyHandle(TEXT("pelvis"),RobotPelvis);
    FProphecyJoltBodyState OldMotion;Owner->ReadBody(RobotPelvis,OldMotion);
    if(!UProphecyLocomotionTypeLibrary::SetLocomotionType(Agent,EProphecyLocomotionType::NN,Error)){AddError(Error);return false;}
    TestTrue(TEXT("Physical NN ownership is restored"),Agent->IsJoltPhysicalAnimationEnabled());
    Compare(TEXT("Robot to physical NN preserves pose"),SimExit);
    FProphecyJoltBodyHandle NNPelvis;Agent->GetJoltCharacterComponent()->GetBodyHandle(TEXT("pelvis"),NNPelvis);
    FProphecyJoltBodyState NewMotion;Owner->ReadBody(NNPelvis,NewMotion);
    const FVector ExpectedVelocity=OldMotion.CenterOfMassVelocityCmPerSecond+FVector::CrossProduct(OldMotion.AngularVelocityRadiansPerSecond,
        NewMotion.CenterOfMassPositionCm-OldMotion.CenterOfMassPositionCm);
    TestTrue(TEXT("Physical NN inherits current COM velocity"),NewMotion.CenterOfMassVelocityCmPerSecond.Equals(ExpectedVelocity,.01));
    TestTrue(TEXT("Physical NN inherits current angular velocity"),NewMotion.AngularVelocityRadiansPerSecond.Equals(OldMotion.AngularVelocityRadiansPerSecond,1.e-5));
    if(!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))return false;
    // Requests issued by Blueprint Tick commit on the next safe admission window.
    World->bInTick=true;
    const bool Queued=UProphecyLocomotionTypeLibrary::SetLocomotionType(Agent,EProphecyLocomotionType::Clanker,Error);
    World->bInTick=false;
    if(!Queued){AddError(Error);return false;}
    TestTrue(TEXT("Tick request has not changed ownership early"),UProphecyLocomotionTypeLibrary::GetLocomotionType(Agent)==EProphecyLocomotionType::NN);
    Tick(2);
    TestTrue(TEXT("Queued request completes"),UProphecyLocomotionTypeLibrary::GetLocomotionType(Agent)==EProphecyLocomotionType::Clanker);
    if(!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))return false;
    TestTrue(TEXT("Ordinary mode switch retires robot ownership"),UProphecyLocomotionTypeLibrary::GetLocomotionType(Agent)==EProphecyLocomotionType::NN&&Agent->bNNInferenceEnabled);
    return !HasAnyErrors();
}
#endif
