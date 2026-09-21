#include "ProphecyJointDampingLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyAngularLimits.h"
#include "Engine/World.h"
#include "ProphecyJointDampingPolicy.h"
#include "ProphecyPhysicalContext.h"
#include "ProphecyNNPolicyBlend.h"

namespace ProphecyJointDamping
{
struct FProfile
{
    float WalkSheathed=0,RunSheathed=0,WalkDrawn=0,RunDrawn=0;
    int32 SourceIndex=INDEX_NONE;
    float Applied=-1;
    float Resolve(float WalkWeight,bool Drawn,bool Attack) const
    {
        if (Attack) return 0;
        return FMath::Lerp(Drawn ? RunDrawn : RunSheathed,
            Drawn ? WalkDrawn : WalkSheathed,FMath::Clamp(WalkWeight,0.f,1.f));
    }
};
struct FState
{
    TMap<FName,FProfile> Joints;
    FProphecyJoltBodyHandle RigBody;
    float WalkWeight=0;
    FVector2f LegWeights=FVector2f::ZeroVector;
    bool Drawn=false,Attack=false,ContextValid=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
struct FValues { TMap<FName,float> Joints; FProphecyJoltBodyHandle Rig; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FValues> AppliedValues;
void Remove(const AProphecyAgent* Agent) { States.Remove(Agent); AppliedValues.Remove(Agent); }
static void RemoveJoint(const AProphecyAgent* Agent,FName Bone)
{
    if (auto* State=States.Find(Agent))
    {
        State->Joints.Remove(Bone);
        if (State->Joints.IsEmpty()) States.Remove(Agent);
    }
}
static void Context(AProphecyAgent& Agent,float& WalkWeight,bool& Drawn,bool& Attack,FVector2f& LegWeights)
{
    Attack=Agent.IsSwordAttackActive(); // Shared full/half attack lifecycle, including unarmed attacks.
    Drawn=false;
    WalkWeight=1;
    LegWeights=FVector2f(1,1);
    if (Attack) return;
    Drawn=IsValid(Agent.GetHeldSword());
    if (!Agent.GetLocomotionRegionalWeights(WalkWeight,LegWeights)) { WalkWeight=1;LegWeights=FVector2f(1,1); }
}
static bool HasJoint(const AProphecyAgent* Agent,FName Bone)
{
    const auto* Mesh=Agent ? Agent->GetPoseReferenceMesh() : nullptr;
    const auto* Asset=Mesh ? Mesh->GetPhysicsAsset() : nullptr;
    if (!Asset || Bone.IsNone() || Mesh->GetBoneIndex(Bone)==INDEX_NONE) return false;
    for (FName Parent=Mesh->GetParentBone(Bone);!Parent.IsNone();Parent=Mesh->GetParentBone(Parent))
        for (const UPhysicsConstraintTemplate* Joint:Asset->ConstraintSetup) if (Joint)
        {
            const auto& J=Joint->DefaultInstance;
            if ((J.ConstraintBone1==Bone && J.ConstraintBone2==Parent) ||
                (J.ConstraintBone2==Bone && J.ConstraintBone1==Parent)) return true;
        }
    return false;
}
bool Validate(const AProphecyAgent* Agent,FName Bone)
{
    FProphecyJoltBodyHandle Handle;
    return IsValid(Agent) && Agent->IsJoltPhysicalAnimationEnabled() && Agent->GetJoltCharacterComponent()
        && Agent->GetJoltCharacterComponent()->GetBodyHandle(Bone,Handle) && HasJoint(Agent,Bone);
}
bool Get(const AProphecyAgent* Agent,FName Bone,float& Value)
{
    Value=0;
    if (!HasJoint(Agent,Bone)) return false;
    if (const auto* State=States.Find(Agent)) if (const auto* Profile=State->Joints.Find(Bone))
    {
        float W;bool Drawn,Attack;FVector2f Legs;Context(*const_cast<AProphecyAgent*>(Agent),W,Drawn,Attack,Legs);
        Value=Profile->Resolve(ProphecyBodyPolicyWalkWeight(Bone,W,Legs),Drawn,Attack);return true;
    }
    if (const auto* Values=AppliedValues.Find(Agent)) if (const auto* Found=Values->Joints.Find(Bone)) Value=*Found;
    return true;
}
bool GetProfile(const AProphecyAgent* Agent,FName Bone,float (&Values)[4])
{
    if (const auto* State=States.Find(Agent)) if (const auto* P=State->Joints.Find(Bone))
    { Values[0]=P->WalkSheathed;Values[1]=P->RunSheathed;Values[2]=P->WalkDrawn;Values[3]=P->RunDrawn;return true; }
    float Value;if (!Get(Agent,Bone,Value)) return false;
    for (float& V:Values) V=Value;return true;
}
void ReleasePolicy(const AProphecyAgent* Agent,FName Bone) { RemoveJoint(Agent,Bone); }
static void Remember(AProphecyAgent* Agent,FName Bone,float Value)
{
    if (Value==0)
    {
        if (auto* Values=AppliedValues.Find(Agent))
        { Values->Joints.Remove(Bone);if (Values->Joints.IsEmpty()) AppliedValues.Remove(Agent); }
        return;
    }
    auto& Values=AppliedValues.FindOrAdd(Agent);Values.Joints.Add(Bone,Value);
    Values.Rig={};
    if (auto* Character=Agent->GetJoltCharacterComponent()) Character->GetRigIdentityBody(Values.Rig);
}
}

namespace
{
bool Apply(UProphecyJoltWorldSubsystem* World,const FProphecyJoltBodyHandle& Handle,
    int32 JointIndex,float Damping,FString& Error)
{
    UFunction* Function=World ? World->FindFunction(TEXT("SetRigJointDamping")) : nullptr;
    if (!Function) { Error=TEXT("The joint damping bridge is not loaded."); return false; }
    struct FParams { FGuid WorldLifetime; int32 Slot; int64 Generation; int32 SourceIndex; float Value; FString Error; bool Result=false; };
    FParams Params{Handle.WorldLifetime,Handle.Slot,int64(Handle.Generation),JointIndex,Damping,FString(),false};
    World->ProcessEvent(Function,&Params);
    Error=MoveTemp(Params.Error);
    return Params.Result;
}
bool Set(AProphecyAgent* Agent,FName Child,float Damping,bool All,FString& Error)
{
    Error.Reset();
    if (!IsInGameThread() || !IsValid(Agent) || !FMath::IsFinite(Damping) || Damping<0)
    { Error=TEXT("A live agent and finite nonnegative damping are required."); return false; }
    auto* Jolt=Agent->GetJoltCharacterComponent();
    FProphecyJoltBodyHandle Handle;
    if (!Agent->IsJoltPhysicalAnimationEnabled() || !Jolt || !Jolt->GetBodyHandle(All ? FName(TEXT("pelvis")) : Child,Handle))
    { Error=TEXT("Enable the character's Jolt rig before setting joint damping."); return false; }
    int32 JointIndex=INDEX_NONE;
    if (!All)
    {
        auto* Mesh=Agent->GetPoseReferenceMesh();
        TArray<FConstraintProfileProperties> Unused;
        if (!Mesh || !ProphecyAngularLimits::PrepareParentJoint(*Mesh,Child,Unused,JointIndex,Error)) return false;
    }
    auto* World=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    return Apply(World,Handle,JointIndex,Damping,Error);
}
}
bool UProphecyJointDampingLibrary::SetJoltJointAngularDamping(AProphecyAgent* Agent,FName Child,float Damping,FString& OutError)
{
    if (IsValid(Agent) && !ProphecyPhysicalContext::IsApplying() &&
        (Agent->IsSwordAttackActive() || ProphecyPhysicalContext::IsManaged(Agent,Child,ProphecyPhysicalContext::EKind::Damping)))
    {
        const bool Result=BlendJoltJointAngularDamping(Agent,Child,Damping,0);
        OutError=Result ? FString() : TEXT("Invalid joint damping request.");return Result;
    }
    if (!Set(Agent,Child,Damping,false,OutError)) return false;
    ProphecyJointDamping::RemoveJoint(Agent,Child);
    ProphecyJointDamping::Remember(Agent,Child,Damping);
    return true;
}
bool UProphecyJointDampingLibrary::SetJoltAllJointsAngularDamping(AProphecyAgent* Agent,float Damping,FString& OutError)
{
    if (!IsValid(Agent) || !FMath::IsFinite(Damping) || Damping<0)
    { OutError=TEXT("A live agent and finite nonnegative damping are required.");return false; }
    auto* Mesh=Agent->GetPoseReferenceMesh();
    if (!Mesh) { OutError=TEXT("No physical mesh is available.");return false; }
    TArray<FName> Bones;Mesh->GetBoneNames(Bones);
    int32 Count=0;
    for (FName Bone:Bones) if (ProphecyJointDamping::HasJoint(Agent,Bone))
    { if (!SetJoltJointAngularDamping(Agent,Bone,Damping,OutError)) return false;++Count; }
    return Count>0;
}

bool UProphecyJointDampingLibrary::SetJoltJointLocomotionDamping(AProphecyAgent* Agent,FName ChildBone,
    float WalkSheathed,float RunSheathed,float WalkDrawn,float RunDrawn,FString& OutError)
{
    using namespace ProphecyJointDamping;
    OutError.Reset();
    if (!IsInGameThread() || !IsValid(Agent))
    { OutError=TEXT("A live agent on the game thread is required."); return false; }
    for (float Value:{WalkSheathed,RunSheathed,WalkDrawn,RunDrawn})
        if (!FMath::IsFinite(Value) || Value<0)
        { OutError=TEXT("All four damping rates must be finite and nonnegative."); return false; }
    if (!Validate(Agent,ChildBone)) { OutError=TEXT("A live Jolt joint is required.");return false; }
    using L=EProphecyLocomotionSelection;using E=EProphecyEquipmentSelection;
    return BlendJoltJointAngularDamping(Agent,ChildBone,WalkSheathed,0,L::Walk,E::Sheathed)
        && BlendJoltJointAngularDamping(Agent,ChildBone,RunSheathed,0,L::Run,E::Sheathed)
        && BlendJoltJointAngularDamping(Agent,ChildBone,WalkDrawn,0,L::Walk,E::Drawn)
        && BlendJoltJointAngularDamping(Agent,ChildBone,RunDrawn,0,L::Run,E::Drawn);
}

int32 UProphecyJointDampingLibrary::SetJoltJointLocomotionDampingBelow(AProphecyAgent* Agent,FName ParentBone,
    bool IncludeParent,float WalkSheathed,float RunSheathed,float WalkDrawn,float RunDrawn,FString& OutError)
{
    using namespace ProphecyJointDamping;
    OutError.Reset();
    auto* Mesh=IsValid(Agent) ? Agent->GetPoseReferenceMesh() : nullptr;
    if (!IsInGameThread() || !Mesh || ParentBone.IsNone() || Mesh->GetBoneIndex(ParentBone)==INDEX_NONE)
    { OutError=TEXT("A live agent and valid Parent Bone are required.");return 0; }
    for (float Value:{WalkSheathed,RunSheathed,WalkDrawn,RunDrawn})
        if (!FMath::IsFinite(Value) || Value<0)
        { OutError=TEXT("All four damping rates must be finite and nonnegative.");return 0; }
    TArray<FName> Bones,Selected;Mesh->GetBoneNames(Bones);
    for (FName Bone:Bones)
        if (((Bone==ParentBone && IncludeParent) || (Bone!=ParentBone && Mesh->BoneIsChildOf(Bone,ParentBone)))
            && HasJoint(Agent,Bone))
        {
            if (!Validate(Agent,Bone))
            { OutError=TEXT("Every selected PHAT joint requires a live Jolt body.");return 0; }
            Selected.Add(Bone);
        }
    int32 Count=0;
    for (FName Bone:Selected)
    {
        if (!SetJoltJointLocomotionDamping(Agent,Bone,WalkSheathed,RunSheathed,WalkDrawn,RunDrawn,OutError)) break;
        ++Count;
    }
    return Count;
}

bool ProphecyJointDamping::ApplyValue(AProphecyAgent* Agent,FName Bone,float Value)
{
    // Reset restores profiles while the old rig is detached. Stage the value for
    // the existing admission/pre-physics path, without creating a polling task.
    if (IsValid(Agent) && !Agent->IsJoltPhysicalAnimationEnabled() && HasJoint(Agent,Bone))
    { Remember(Agent,Bone,Value);return true; }
    FString Error;
    if (!Set(Agent,Bone,Value,false,Error)) return false;
    Remember(Agent,Bone,Value);return true;
}
bool UProphecyJointDampingLibrary::GetJoltJointAngularDamping(AProphecyAgent* Agent,FName Bone,float& Value)
{ return ProphecyJointDamping::Get(Agent,Bone,Value); }
bool UProphecyJointDampingLibrary::BlendJoltJointAngularDamping(AProphecyAgent* Agent,FName Bone,float Value,
    float Duration,EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{
    return IsValid(Agent) && FMath::IsFinite(Value) && Value>=0 &&
        ProphecyPhysicalContext::Set(*Agent,Bone,ProphecyPhysicalContext::EKind::Damping,true,{Value,Value},Duration,L,E);
}
int32 UProphecyJointDampingLibrary::BlendJoltJointAngularDampingBelow(AProphecyAgent* Agent,FName Parent,bool Include,
    float Value,float Duration,EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{
    auto* Mesh=IsValid(Agent) ? Agent->GetPoseReferenceMesh() : nullptr;
    if (!Mesh || Mesh->GetBoneIndex(Parent)==INDEX_NONE) return 0;
    TArray<FName> Bones;Mesh->GetBoneNames(Bones);int32 Count=0;
    for (FName Bone:Bones) if ((Bone==Parent && Include) || (Bone!=Parent && Mesh->BoneIsChildOf(Bone,Parent)))
        Count+=BlendJoltJointAngularDamping(Agent,Bone,Value,Duration,L,E);
    return Count;
}
int32 UProphecyJointDampingLibrary::BlendJoltAllJointsAngularDamping(AProphecyAgent* Agent,float Value,float Duration,
    EProphecyLocomotionSelection L,EProphecyEquipmentSelection E)
{
    auto* Mesh=IsValid(Agent) ? Agent->GetPoseReferenceMesh() : nullptr;
    if (!Mesh) return 0;
    TArray<FName> Bones;Mesh->GetBoneNames(Bones);int32 Count=0;
    for (FName Bone:Bones) Count+=BlendJoltJointAngularDamping(Agent,Bone,Value,Duration,L,E);
    return Count;
}

bool ProphecyJointDamping::Update(AProphecyAgent* Agent,const FProphecyJoltBodyHandle& RigBody,FString& Error)
{
    if (auto* Values=AppliedValues.IsEmpty() ? nullptr : AppliedValues.Find(Agent))
        if (Values->Rig.WorldLifetime!=RigBody.WorldLifetime || Values->Rig.Slot!=RigBody.Slot || Values->Rig.Generation!=RigBody.Generation)
        {
            for (const auto& Item:Values->Joints) if (!Set(Agent,Item.Key,Item.Value,false,Error)) return false;
            Values->Rig=RigBody;
        }
    auto* State=States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!State) return true;
    float W; bool Drawn,Attack;FVector2f Legs;
    Context(*Agent,W,Drawn,Attack,Legs);
    const bool NewRig=State->RigBody.WorldLifetime!=RigBody.WorldLifetime
        || State->RigBody.Slot!=RigBody.Slot || State->RigBody.Generation!=RigBody.Generation;
    if (!NewRig && State->ContextValid && State->WalkWeight==W && State->LegWeights==Legs && State->Drawn==Drawn && State->Attack==Attack)
        return true;
    auto* World=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    for (auto& Item:State->Joints)
    {
        auto& Profile=Item.Value;
        const float Value=Profile.Resolve(ProphecyBodyPolicyWalkWeight(Item.Key,W,Legs),Drawn,Attack);
        if (NewRig || Profile.SourceIndex==INDEX_NONE)
        {
            auto* Mesh=Agent->GetPoseReferenceMesh();
            TArray<FConstraintProfileProperties> Unused;
            if (!Mesh || !ProphecyAngularLimits::PrepareParentJoint(*Mesh,Item.Key,Unused,Profile.SourceIndex,Error)) return false;
        }
        if (NewRig || Profile.Applied!=Value)
        {
            if (!Apply(World,RigBody,Profile.SourceIndex,Value,Error)) return false;
            Profile.Applied=Value;
            Remember(Agent,Item.Key,Value);
        }
    }
    State->RigBody=RigBody;
    State->WalkWeight=W; State->LegWeights=Legs; State->Drawn=Drawn; State->Attack=Attack; State->ContextValid=true;
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJointDampingPolicyTest,"Prophecy.Jolt.Joints.DampingPolicy",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJointDampingPolicyTest::RunTest(const FString&)
{
    const ProphecyJointDamping::FProfile Profile{10,30,100,300};
    TestEqual(TEXT("Walk sheathed"),Profile.Resolve(1,false,false),10.f);
    TestEqual(TEXT("Run sheathed"),Profile.Resolve(0,false,false),30.f);
    TestEqual(TEXT("Walk drawn"),Profile.Resolve(1,true,false),100.f);
    TestEqual(TEXT("Run drawn"),Profile.Resolve(0,true,false),300.f);
    TestEqual(TEXT("Actual blend sheathed"),Profile.Resolve(.25f,false,false),25.f);
    TestEqual(TEXT("Actual blend drawn"),Profile.Resolve(.25f,true,false),250.f);
    for (float W:{0.f,.25f,1.f}) for (bool Drawn:{false,true})
        TestEqual(TEXT("All attack contexts have zero added damping"),Profile.Resolve(W,Drawn,true),0.f);
    TestEqual(TEXT("Locomotion resumes its configured value"),Profile.Resolve(.25f,true,false),250.f);
    return true;
}
#endif
