#include "ProphecyHolsterMount.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltConstraintRuntime.h"
#include "ProphecyJoltStandardPhysicsLibrary.h"
#include "ProphecySwordHolsterPose.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace ProphecyHolsterMount
{
namespace
{
struct FMount
{
    TWeakObjectPtr<UPrimitiveComponent> Holster;
    TArray<TWeakObjectPtr<UPhysicsConstraintComponent>> Joints;
    FTransform Rest,From,BeforeMode;
    bool Requested=false,Physical=false,Returning=false,PendingMode=false,Rebase=false;
    bool Gripped=false,GripReturn=false;
    int32 Elapsed=0,Duration=0;
};
TMap<TWeakObjectPtr<const AProphecyAgent>,FMount> Mounts;
TSet<TWeakObjectPtr<const AProphecyAgent>> Moving;
FDelegateHandle TickHandle,CleanupHandle;

UProphecyJoltBodyComponent* BodyFor(UPrimitiveComponent* H)
{
    TInlineComponentArray<UProphecyJoltBodyComponent*> Bodies(H->GetOwner());
    for(auto* B:Bodies)if(B->GetSourceComponent()==H)return B;
    return nullptr;
}
void CollectJoints(AProphecyAgent* A,FMount& S)
{
    TInlineComponentArray<UPhysicsConstraintComponent*> Joints(A);
    for(auto* C:Joints){
        UPrimitiveComponent* First=nullptr;UPrimitiveComponent* Second=nullptr;FName Bone1,Bone2;
        C->GetConstrainedComponents(First,Bone1,Second,Bone2);
        if((First==S.Holster&&Second==A->GetPoseReferenceMesh()&&Bone2==TEXT("pelvis"))
            ||(Second==S.Holster&&First==A->GetPoseReferenceMesh()&&Bone1==TEXT("pelvis")))S.Joints.AddUnique(C);
    }
}
void Suspend(FMount& S,bool Value)
{
    for(auto& Joint:S.Joints)if(auto* C=Joint.Get())ProphecyJolt::Constraints::SetSuspended(C,Value);
}
bool SetBodySimulation(FMount& S,bool Value)
{
    auto* H=S.Holster.Get();if(!H)return false;
    if(auto* Body=BodyFor(H);Body&&Body->IsJoltBody()){
        FString Error;
        if(!Body->SetSimulationEnabled(Value,Error)){
            UE_LOG(LogTemp,Warning,TEXT("Holster mode: %s"),*Error);return false;
        }
    }else H->SetSimulatePhysics(Value);
    return UProphecyJoltStandardPhysicsLibrary::IsSimulatingPhysics(H,NAME_None)==Value;
}
bool Kinematic(AProphecyAgent* A,FMount& S,bool Rebase=false,bool KeepPose=false)
{
    auto* H=S.Holster.Get();auto* Mesh=A->GetPoseReferenceMesh();
    if(!H||!Mesh||!Mesh->DoesSocketExist(TEXT("pelvis")))return false;
    if(!S.Physical&&!Rebase)return true;
    const FTransform World=Rebase?S.BeforeMode:H->GetComponentTransform();
    CollectJoints(A,S);Suspend(S,true);
    if(!SetBodySimulation(S,false)){Suspend(S,false);return false;}
    ProphecySwordHolsterPose::ReleaseHolsterMount(A);
    H->SetUsingAbsoluteRotation(false);
    H->AttachToComponent(Mesh,FAttachmentTransformRules::KeepWorldTransform,TEXT("pelvis"));
    H->SetWorldTransform(World,false,nullptr,ETeleportType::TeleportPhysics);
    S.From=H->GetRelativeTransform();S.Elapsed=0;S.Physical=false;
    S.Returning=!KeepPose&&S.Duration>0&&!S.From.Equals(S.Rest,1.e-6);
    if(!KeepPose&&!S.Returning)H->SetRelativeTransform(S.Rest);
    return true;
}
bool Physical(AProphecyAgent* A,FMount& S)
{
    if(S.Physical)return true;
    if(!A->IsJoltPhysicalAnimationEnabled())return false;
    CollectJoints(A,S);
    if(S.Joints.IsEmpty()){
        UE_LOG(LogTemp,Warning,TEXT("Holster mode: no authored holster/pelvis constraint on %s."),*A->GetName());return false;
    }
    const auto* H=S.Holster.Get();if(!H)return false;
    const FTransform World=H->GetComponentTransform();
    ProphecySwordHolsterPose::ReleaseHolsterMount(A);
    S.Holster->SetWorldTransform(World,false,nullptr,ETeleportType::TeleportPhysics);
    if(!SetBodySimulation(S,true))return false;
    // Resume the existing authored frames and drives. Reinitializing the UE
    // constraint here would redefine its rest pose from the current deflection.
    Suspend(S,false);S.Physical=true;S.Returning=false;return true;
}
bool BackendPending(const AProphecyAgent* A)
{
    const auto* C=A->GetJoltCharacterComponent();
    return C&&(C->IsEnablePending()||C->IsKinematicRestorePending());
}
void StopIdleTick()
{
    if(Moving.IsEmpty()&&TickHandle.IsValid()){
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();
    }
}
void Tick(UWorld* World,ELevelTick Type,float)
{
    if(!World||World->IsPaused()||Type==LEVELTICK_PauseTick)return;
    for(auto It=Moving.CreateIterator();It;++It){
        auto* A=const_cast<AProphecyAgent*>(It->Get());auto* S=Mounts.Find(*It);
        if(!A||!S||!S->Holster.IsValid()){It.RemoveCurrent();continue;}
        if(A->GetWorld()!=World)continue;
        if(S->PendingMode){
            if(BackendPending(A))continue;
            S->PendingMode=false;
            if(S->Rebase){Kinematic(A,*S,true,S->Gripped);S->Rebase=false;}
            if(!S->Gripped&&!S->Returning&&A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic&&S->Requested)Physical(A,*S);
        }
        if(S->Returning){
            const float Alpha=FMath::Clamp(float(++S->Elapsed)/S->Duration,0.f,1.f);
            FTransform Local;Local.Blend(S->From,S->Rest,Alpha);
            S->Holster->SetRelativeTransform(Local);
            if(Alpha>=1){
                S->Returning=false;
                if(!S->Gripped&&S->Requested&&A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)Physical(A,*S);
            }
        }
        if(!S->Returning&&!S->PendingMode)It.RemoveCurrent();
    }
    StopIdleTick();
}
void Schedule(const AProphecyAgent* A)
{
    Moving.Add(A);
    if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
}
}
void Capture(AProphecyAgent* A,UPrimitiveComponent* H,const FTransform& Rest,bool Simulated)
{
    if(!A||!H||!A->GetWorld()->IsGameWorld()||Mounts.Contains(A))return;
    auto& S=Mounts.Add(A);S.Holster=H;S.Rest=Rest;S.Requested=Simulated;
    S.Physical=UProphecyJoltStandardPhysicsLibrary::IsSimulatingPhysics(H,NAME_None);
    CollectJoints(A,S);
    if(!S.Physical)Suspend(S,true);
    if(A->GetSimulationMode()==EProphecyAgentSimulationMode::Kinematic){
        S.Duration=0;Kinematic(A,S);
    }
    if(!CleanupHandle.IsValid())CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool){
        for(auto It=Mounts.CreateIterator();It;++It)if(!It.Key().IsValid()||It.Key()->GetWorld()==W){
            Suspend(It.Value(),false);Moving.Remove(It.Key());It.RemoveCurrent();
        }
        StopIdleTick();
        if(Mounts.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();}
    });
}
bool SetSimulated(AProphecyAgent* A,bool Simulated,float ReturnDuration)
{
    if(!IsInGameThread()||!IsValid(A)||!FMath::IsFinite(ReturnDuration)||ReturnDuration<0)return false;
    auto* S=Mounts.Find(A);if(!S||!S->Holster.IsValid())return false;
    S->Duration=FMath::CeilToInt(ReturnDuration*60-1.e-5f);
    // A user selection during the grip takes effect after its temporary
    // kinematic ownership ends; it must not interrupt compensation/sliding.
    if(S->Gripped){S->Requested=Simulated;return true;}
    if(S->Returning&&S->Requested==Simulated)return true;
    const bool Effective=Simulated&&A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic;
    if(Effective&&!A->IsJoltPhysicalAnimationEnabled())return false;
    if(!(Effective?Physical(A,*S):Kinematic(A,*S)))return false;
    S->Requested=Simulated;
    if(S->Returning)Schedule(A);else{Moving.Remove(A);StopIdleTick();}
    return true;
}
bool BeginGrip(AProphecyAgent* A,float ReturnDuration)
{
    auto* S=Mounts.Find(A);if(!S)return true;
    if(S->Gripped)return true;
    const bool Return=S->Physical||S->Requested||S->Returning;
    if(!Kinematic(A,*S,false,true))return false;
    S->Duration=FMath::CeilToInt(ReturnDuration*60-1.e-5f);
    S->Gripped=true;S->GripReturn=Return;S->Returning=false;
    if(!S->PendingMode){Moving.Remove(A);StopIdleTick();}
    return true;
}
void EndGrip(AProphecyAgent* A)
{
    auto* S=Mounts.Find(A);if(!S||!S->Gripped)return;
    S->Gripped=false;
    const bool Return=S->GripReturn||S->Requested;S->GripReturn=false;
    // Originally kinematic holsters retain their existing compensation fade.
    if(!Return||!S->Holster.IsValid())return;
    ProphecySwordHolsterPose::ReleaseHolsterMount(A);
    S->From=S->Holster->GetRelativeTransform();S->Elapsed=0;
    S->Returning=S->Duration>0&&!S->From.Equals(S->Rest,1.e-6);
    if(S->Returning||S->PendingMode)Schedule(A);
    else{
        S->Holster->SetRelativeTransform(S->Rest);
        if(S->Requested&&A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic)Physical(A,*S);
    }
}
void BeforeAgentModeChange(AProphecyAgent* A,bool Kin,float Duration)
{
    auto* S=Mounts.Find(A);if(!S||!S->Holster.IsValid())return;
    S->Duration=FMath::CeilToInt(Duration*60-1.e-5f);
    if(Kin){
        S->BeforeMode=S->Holster->GetComponentTransform();S->Rebase=true;
        Kinematic(A,*S,false,S->Gripped);
    }
}
void AfterAgentModeChange(AProphecyAgent* A)
{
    auto* S=Mounts.Find(A);if(!S||!S->Holster.IsValid())return;
    if(BackendPending(A)){S->PendingMode=true;Schedule(A);return;}
    if(S->Rebase){Kinematic(A,*S,true,S->Gripped);S->Rebase=false;}
    if(!S->Gripped&&!S->Returning&&A->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic&&S->Requested)Physical(A,*S);
    if(S->Returning)Schedule(A);else{Moving.Remove(A);StopIdleTick();}
}
bool OwnsReturn(const AProphecyAgent* A){const auto* S=Mounts.Find(A);return S&&(S->Returning||S->PendingMode);}
void Remove(const AProphecyAgent* A)
{
    if(auto* S=Mounts.Find(A))Suspend(*S,false);
    Mounts.Remove(A);Moving.Remove(A);StopIdleTick();
}
#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorld InspectCommand(TEXT("Prophecy.Holster.Inspect"),TEXT("Write current holster mode/return/joint state; no mutation."),FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W){
    FString Text;
    for(const auto& Pair:Mounts){auto* A=Pair.Key.Get();const auto& S=Pair.Value;auto* H=S.Holster.Get();if(!A||!H||A->GetWorld()!=W)continue;
        int32 Joints=0;FString Error;FProphecyJoltJointHandle Handle;
        for(const auto& C:S.Joints)if(ProphecyJolt::Constraints::GetJoint(C.Get(),Handle,Error))++Joints;
        const auto* Mesh=A->GetPoseReferenceMesh();const FTransform Local=H->GetComponentTransform().GetRelativeTransform(Mesh->GetSocketTransform(TEXT("pelvis")));
        Text+=FString::Printf(TEXT("%s requested=%d physical=%d returning=%d elapsed=%d duration=%d pending=%d joints=%d gripped=%d rest_cm=%.9f rest_deg=%.9f\n"),
            *A->GetName(),S.Requested,S.Physical,S.Returning,S.Elapsed,S.Duration,S.PendingMode,Joints,S.Gripped,
            FVector::Distance(Local.GetLocation(),S.Rest.GetLocation()),FMath::RadiansToDegrees(Local.GetRotation().AngularDistance(S.Rest.GetRotation())));
    }
    FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/HolsterModes.txt")));
}));
#endif
}
