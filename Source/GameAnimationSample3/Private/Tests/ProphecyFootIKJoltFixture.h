#pragma once

#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyJoltBlueprintLibrary.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Engine/World.h"

namespace ProphecyFootIKJoltFixture
{
// The native locomotion shell is not a manual physical follower. Reproduce the
// game's separate PhysicalMesh contract without executing a user Blueprint.
inline AProphecyAgent* Spawn(UWorld* World,AProphecyNNLocomotionManager* Manager,FString& Error)
{
    auto* Agent=World->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(),FTransform::Identity,nullptr,nullptr,ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if(!Agent){Error=TEXT("Could not create manual physical agent");return nullptr;}
    Agent->bManualNNPoseApplication=true;Agent->bAutoEnsureStandaloneNNManager=false;
    Agent->bAutoPublishManualFollowerSubstepTargets=false;Agent->bEnableAttackFists=false;
    Agent->AutoPossessAI=EAutoPossessAI::Disabled;Agent->AutoPossessPlayer=EAutoReceiveInput::Disabled;
    auto* Base=Agent->GetAgentMesh();auto* Mesh=NewObject<USkeletalMeshComponent>(Agent,TEXT("PhysicalMesh"));
    Agent->AddInstanceComponent(Mesh);Mesh->SetupAttachment(Agent->GetAgentCapsule());Mesh->SetRelativeTransform(Base->GetRelativeTransform());
    Mesh->SetSkeletalMesh(Base->GetSkeletalMeshAsset());Mesh->SetPhysicsAsset(Base->GetPhysicsAsset());
    if(!Mesh->GetSkeletalMeshAsset()||!Mesh->GetPhysicsAsset()){Error=TEXT("Missing actual mannequin/PHAT calibration");Agent->Destroy();return nullptr;}
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);Mesh->SetCollisionObjectType(ECC_PhysicsBody);Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetGenerateOverlapEvents(false);Mesh->SetCanEverAffectNavigation(false);Mesh->RegisterComponent();
    Base->SetSkeletalMesh(nullptr);Agent->FinishSpawning(FTransform::Identity);Manager->PlayerAgent=Agent;return Agent;
}
inline bool Bind(AProphecyAgent* Agent,FString& Error)
{
    if(!Agent->HasActorBegunPlay())Agent->DispatchBeginPlay();
    int32 Id=INDEX_NONE;float Interval=0;bool Interpolate=false;
    if(!Agent->GetNNPoseDataSource(Id,Interval,Interpolate)){Error=TEXT("Manual physical follower was not registered with the manager");return false;}
    auto* Mesh=Agent->GetPoseReferenceMesh();Mesh->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
    auto* Anim=Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());if(!Anim){Error=TEXT("Could not bind the physical pose proxy");return false;}
    Anim->AgentId=Id;Anim->NNPoseIntervalSeconds=Interval;Anim->bInterpolateNNPose=Interpolate;Anim->bUseViewerGlobalPoseInterpolation=Interpolate;
    Mesh->TickAnimation(0,false);Mesh->RefreshBoneTransforms();return true;
}
inline bool InitializeWorld(UWorld* World,AActor* SceneOwner,AProphecyAgent* Agent,bool Automatic,FString& Error)
{
    auto* Floor=SceneOwner?SceneOwner->FindComponentByClass<UStaticMeshComponent>():nullptr;
    if(!Floor||!Floor->GetStaticMesh()||!Floor->IsRegistered()||Floor->GetCollisionEnabled()!=ECollisionEnabled::QueryAndPhysics)
    {Error=TEXT("Fixture floor must have its actual mesh, registered solid collision and completed spawn before Jolt admission");return false;}
    auto* Physics=World?World->GetSubsystem<UProphecyJoltWorldSubsystem>():nullptr;FProphecyJoltWorldDiagnostics Ready;
    if(!Physics||!Physics->GetDiagnostics(Ready).IsSuccess()){Error=TEXT("Cannot inspect the fixture's shared Jolt world");return false;}
    if(Ready.bFaulted){Error=TEXT("Fixture Jolt world is faulted: ")+Ready.Failure;return false;}
    // The normal DefaultPhysics pre-actor-tick hook can already have created the
    // world's FightSetup. Its owner and settings must survive fixture admission.
    const bool Reused=Ready.bInitialized;
    if(!Reused&&!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(World,Error,256,0))return false;
    if(!Physics->GetDiagnostics(Ready).IsSuccess()||!Ready.bInitialized||Ready.bFaulted||!Ready.WorldLifetime.IsValid())
    {Error=TEXT("Fixture shared Jolt world is not ready");return false;}
    if(!Ready.Settings.GravityCmPerSecondSquared.Equals(FVector(0,0,World->GetGravityZ()),.001))
    {Error=TEXT("Fixture shared Jolt gravity differs from its Unreal world");return false;}
    const auto* Asset=Agent&&Agent->GetPoseReferenceMesh()?Agent->GetPoseReferenceMesh()->GetPhysicsAsset():nullptr;
    if(!Asset){Error=TEXT("Missing physical rig capacity calibration");return false;}
    const uint32 Needed=uint32(Asset->SkeletalBodySetups.Num())+1;
    if(Ready.Settings.MaxBodies<Ready.BodyCount||Ready.Settings.MaxBodies-Ready.BodyCount<Needed)
    {Error=TEXT("Fixture shared Jolt world lacks capacity for the actual PHAT rig and floor");return false;}
    auto* Scene=UProphecyJoltSceneCollisionComponent::FindForWorld(World);
    if(!Scene)
    {
        Scene=NewObject<UProphecyJoltSceneCollisionComponent>(SceneOwner,NAME_None,RF_Transient);SceneOwner->AddInstanceComponent(Scene);Scene->RegisterComponent();
        if(!Scene->EnableSceneCollision(Error))return false;
    }
    // This is the test's privately created world. Manual completion tests retain
    // its real collision owner but select the explicit step protocol before rig
    // admission; automatic tracking tests retain the ordinary gameplay protocol.
    Scene->bAutomaticScenePhysics=Automatic;
    Agent->bAutoPublishManualFollowerSubstepTargets=Automatic;
    if(!Scene->IsSceneCollisionEnabled()||Scene->IsEnablePending()||!Scene->PrepareJoltWorldStep(1.f/60,false,Error))
    {if(Error.IsEmpty())Error=TEXT("Shared Jolt scene collision is not ready");return false;}
    FProphecyJoltBodyHandle Handle;UObject* Associated=nullptr;
    if(!Floor||!Scene->GetBodyHandle(*Floor,INDEX_NONE,Handle)||!Physics->OwnsBody(Handle)||!Physics->ResolveAssociatedObject(Handle,Associated).IsSuccess()||Associated!=Floor)
    {Error=TEXT("Actual physical floor did not enter the shared Jolt world");return false;}
    UE_LOG(LogTemp,Display,TEXT("Foot IK Jolt fixture %s world: bodies %u/%u, workers %d, automatic %d"),Reused?TEXT("reuses"):TEXT("initialized"),Ready.BodyCount,Ready.Settings.MaxBodies,Ready.Settings.WorkerThreads,Automatic);
    return true;
}
inline bool Enable(AProphecyAgent* Agent,FString& Error)
{
    // Match the ordinary FightSetup admission. Native agents default to Chaos
    // MACD, which SetSimulationMode(Physical) reapplies to every live body;
    // the sealed Jolt rig must enter discretely before its own CCD policy is set.
    Agent->SetMACDEnabled(false);
    if(!Agent->EnableJoltPhysicalAnimation()){Error=FString::Printf(TEXT("Jolt backend selection failed (manual=%d, begun=%d)"),Agent->bManualNNPoseApplication,Agent->HasActorBegunPlay());return false;}
    if(!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))
    {const auto* Character=Agent->GetJoltCharacterComponent();Error=TEXT("Jolt physical admission failed: ")+(Character?Character->GetLastError():TEXT("no character component"));return false;}
    return true;
}
}
