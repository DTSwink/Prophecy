#include "ProphecyLimbCollisionLibrary.h"
#include "ProphecyLimbCollision.h"
#include "ProphecySpecialSolver.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyNNDefenseLibrary.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Engine/World.h"

namespace ProphecyLimbCollision
{
struct FBodyOverride
{
    FProphecyJoltCollisionUpdate Original;
    ECollisionChannel ObjectChannel=ECC_MAX;
    TMap<ECollisionChannel,ECollisionResponse> Responses;
};
struct FAgentOverrides
{
    TMap<FName,FBodyOverride> Bodies;
    FProphecyJoltBodyHandle RigBody;
    bool bDefense=false,bCombat=false,bDirty=true,bApplied=false;
};
// Separate optional native storage: no extension of existing live character/map layouts.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FAgentOverrides> Overrides;
void Remove(const AProphecyAgent* Agent) { Overrides.Remove(Agent); ProphecySpecialSolver::Remove(Agent); }
void Invalidate(AProphecyAgent* Agent)
{ if (auto* S=Overrides.IsEmpty() ? nullptr : Overrides.Find(Agent)) S->bDirty=true; }
void DefenseChanged(AProphecyAgent* Agent,bool Active)
{
    ProphecySpecialSolver::DefenseChanged(Agent,Active);
    // Shared committed defense lifecycle: both parry/dodge call this after activation,
    // and StopAgentNNDefense calls it on exit. Queued pre-Armed requests never call true.
    // Independent of optional limb overrides. Reflection avoids new live plugin imports.
    if (IsValid(Agent))
    {
        struct FSweepDefenseState { AActor* Agent; bool Defending; } State{Agent,Active};
        auto* Library=FindObjectChecked<UClass>(nullptr,
            TEXT("/Script/ProphecyJolt.ProphecyJoltPHATSweepLibrary"))->GetDefaultObject();
        Library->ProcessEvent(Library->FindFunctionChecked(TEXT("NotifyDefenseState")),&State);
    }
    if (auto* S=Overrides.IsEmpty() ? nullptr : Overrides.Find(Agent)) S->bDefense=Active;
}
static bool SameRig(const FProphecyJoltBodyHandle& A,const FProphecyJoltBodyHandle& B)
{ return A.WorldLifetime==B.WorldLifetime && A.Slot==B.Slot && A.Generation==B.Generation; }
static bool Read(AProphecyAgent* Agent,FName Bone,FProphecyJoltCollisionUpdate& Out,FString& Error)
{
    auto* C=IsValid(Agent) ? Agent->GetJoltCharacterComponent() : nullptr;
    FProphecyJoltBodyHandle Handle;
    if (!IsInGameThread() || !C || !Agent->IsJoltPhysicalAnimationEnabled() || C->IsSteppingStopped()
        || !C->GetBodyHandle(Bone,Handle))
    { Error=TEXT("A healthy live Jolt rig and an exact PHAT body bone are required.");return false; }
    const auto Result=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->ReadBodyCollision(Handle,Out);
    Error=Result.Message;return Result.IsSuccess();
}
static bool Select(AProphecyAgent* Agent,FName Bone,bool Children,TArray<FName>& Out,FString& Error)
{
    FProphecyJoltCollisionUpdate Body;
    if (!Read(Agent,Bone,Body,Error)) return false;
    Out.Add(Bone);
    if (!Children) return true;
    const auto* Mesh=Agent->GetPoseReferenceMesh();
    const auto* Asset=Mesh ? Mesh->GetPhysicsAsset() : nullptr;
    if (!Asset) { Error=TEXT("The bound PHAT asset is unavailable.");return false; }
    for (const USkeletalBodySetup* Setup:Asset->SkeletalBodySetups)
        if (Setup && Setup->BoneName!=Bone && Mesh->BoneIsChildOf(Setup->BoneName,Bone)) Out.Add(Setup->BoneName);
    return true;
}
static FProphecyJoltCollisionUpdate Resolve(const FBodyOverride& Body,bool Combat)
{
    auto Result=Body.Original;
    if (!Combat)
    {
        if (Body.ObjectChannel!=ECC_MAX) Result.ObjectChannel=Body.ObjectChannel;
        for (const auto& Pair:Body.Responses) Result.Responses.SetResponse(Pair.Key,Pair.Value);
    }
    return Result;
}
bool Update(AProphecyAgent* Agent,const FProphecyJoltBodyHandle& RigBody,FString& Error)
{
    auto* S=Overrides.IsEmpty() ? nullptr : Overrides.Find(Agent);
    if (!S) return true;
    const bool Combat=Agent->IsSwordAttackActive() || S->bDefense;
    const bool NewRig=!SameRig(S->RigBody,RigBody);
    if (!NewRig && !S->bDirty && S->bApplied && S->bCombat==Combat) return true;
    TArray<FProphecyJoltCollisionUpdate,TInlineAllocator<32>> Updates;
    for (auto& Pair:S->Bodies)
    {
        if (NewRig && !Read(Agent,Pair.Key,Pair.Value.Original,Error)) return false;
        Updates.Add(Resolve(Pair.Value,Combat));
    }
    const auto Result=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->UpdateBodyCollision(Updates);
    if (!Result.IsSuccess()) { Error=Result.Message;return false; }
    S->RigBody=RigBody;S->bCombat=Combat;S->bApplied=true;S->bDirty=false;return true;
}
static bool Configure(AProphecyAgent* Agent,FName Bone,bool Children,ECollisionChannel Channel,
    ECollisionResponse Response,bool ObjectType,FString& Error)
{
    Error.Reset();
    if (Channel<0 || Channel>=ECC_MAX || Response<0 || Response>=ECR_MAX)
    { Error=TEXT("Invalid collision channel or response.");return false; }
    TArray<FName> Bones;
    if (!Select(Agent,Bone,Children,Bones,Error)) return false;
    // Stage all captures/edits before touching the live override list or native filters.
    const auto* Existing=Overrides.Find(Agent);
    FAgentOverrides Next=Existing ? *Existing : FAgentOverrides{};
    FProphecyJoltBodyHandle RigBody;
    Agent->GetJoltCharacterComponent()->GetRigIdentityBody(RigBody);
    if (!SameRig(Next.RigBody,RigBody))
        for (auto& Pair:Next.Bodies) if (!Read(Agent,Pair.Key,Pair.Value.Original,Error)) return false;
    Next.RigBody=RigBody;
    if (!Existing)
    {
        FProphecyNNDefenseStatus Defense;
        Next.bDefense=UProphecyNNDefenseLibrary::GetNNDefenseStatus(Agent,Defense) && Defense.Active;
    }
    Next.bCombat=Agent->IsSwordAttackActive() || Next.bDefense;
    for (FName Name:Bones)
    {
        auto* Body=Next.Bodies.Find(Name);
        if (!Body)
        {
            FBodyOverride New;
            if (!Read(Agent,Name,New.Original,Error)) return false;
            Body=&Next.Bodies.Add(Name,MoveTemp(New));
        }
        if (ObjectType) Body->ObjectChannel=Channel;
        else Body->Responses.Add(Channel,Response);
    }
    TArray<FProphecyJoltCollisionUpdate,TInlineAllocator<32>> Updates;
    for (const auto& Pair:Next.Bodies) Updates.Add(Resolve(Pair.Value,Next.bCombat));
    const auto Result=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->UpdateBodyCollision(Updates);
    if (!Result.IsSuccess()) { Error=Result.Message;return false; }
    Next.bDirty=false;Next.bApplied=true;Overrides.Add(Agent,MoveTemp(Next));return true;
}
}

bool UProphecyLimbCollisionLibrary::SetJoltLimbCollisionChannel(AProphecyAgent* Agent,FName BoneName,
    TEnumAsByte<ECollisionChannel> ObjectChannel,FString& OutError,bool bIncludeChildren)
{ return ProphecyLimbCollision::Configure(Agent,BoneName,bIncludeChildren,ObjectChannel,ECR_Block,true,OutError); }
bool UProphecyLimbCollisionLibrary::SetJoltLimbCollisionResponse(AProphecyAgent* Agent,FName BoneName,
    TEnumAsByte<ECollisionChannel> Channel,TEnumAsByte<ECollisionResponse> Response,FString& OutError,bool bIncludeChildren)
{ return ProphecyLimbCollision::Configure(Agent,BoneName,bIncludeChildren,Channel,Response,false,OutError); }
TArray<FName> UProphecyLimbCollisionLibrary::GetModifiedLimbCollisionBones(AProphecyAgent* Agent)
{
    TArray<FName> Bones;
    if (const auto* S=ProphecyLimbCollision::Overrides.Find(Agent)) S->Bodies.GetKeys(Bones);
    Bones.Sort(FNameLexicalLess());return Bones;
}
bool UProphecyLimbCollisionLibrary::ResetJoltLimbCollision(AProphecyAgent* Agent,FName BoneName,FString& OutError,bool bIncludeChildren)
{
    using namespace ProphecyLimbCollision;
    OutError.Reset();TArray<FName> Bones;
    if (!Select(Agent,BoneName,bIncludeChildren,Bones,OutError)) return false;
    auto* S=Overrides.Find(Agent);if (!S) return true;
    FProphecyJoltBodyHandle RigBody;Agent->GetJoltCharacterComponent()->GetRigIdentityBody(RigBody);
    if (!Update(Agent,RigBody,OutError)) return false;
    TArray<FProphecyJoltCollisionUpdate,TInlineAllocator<32>> Updates;
    for (FName Name:Bones) if (const auto* Body=S->Bodies.Find(Name)) Updates.Add(Body->Original);
    if (!Updates.IsEmpty())
    {
        const auto Result=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->UpdateBodyCollision(Updates);
        if (!Result.IsSuccess()) { OutError=Result.Message;return false; }
    }
    for (FName Name:Bones) S->Bodies.Remove(Name);
    if (S->Bodies.IsEmpty()) Overrides.Remove(Agent);
    return true;
}
bool UProphecyLimbCollisionLibrary::GetJoltLimbCollisionResponse(AProphecyAgent* Agent,FName BoneName,
    TEnumAsByte<ECollisionChannel> Channel,TEnumAsByte<ECollisionChannel>& ObjectChannel,
    TEnumAsByte<ECollisionResponse>& Response,bool& bModified,bool& bLocomotionOverrideActive)
{
    using namespace ProphecyLimbCollision;
    ObjectChannel=ECC_WorldStatic;Response=ECR_Ignore;bModified=bLocomotionOverrideActive=false;
    FProphecyJoltCollisionUpdate Body;FString Error;
    if (Channel<0 || Channel>=ECC_MAX || !Read(Agent,BoneName,Body,Error)) return false;
    ObjectChannel=Body.ObjectChannel;Response=Body.Responses.GetResponse(Channel);
    if (const auto* S=Overrides.Find(Agent))
    { bModified=S->Bodies.Contains(BoneName);bLocomotionOverrideActive=bModified && S->bApplied && !S->bCombat; }
    return true;
}
