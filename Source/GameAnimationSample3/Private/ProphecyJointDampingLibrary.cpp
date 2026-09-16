#include "ProphecyJointDampingLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyAngularLimits.h"
#include "Engine/World.h"
#include "ProphecyJointDampingPolicy.h"

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
    bool Drawn=false,Attack=false,ContextValid=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FState> States;
void Remove(const AProphecyAgent* Agent) { States.Remove(Agent); }
static void RemoveJoint(const AProphecyAgent* Agent,FName Bone)
{
    if (auto* State=States.Find(Agent))
    {
        State->Joints.Remove(Bone);
        if (State->Joints.IsEmpty()) States.Remove(Agent);
    }
}
static void Context(AProphecyAgent& Agent,float& WalkWeight,bool& Drawn,bool& Attack)
{
    Attack=Agent.IsSwordAttackActive(); // Shared full/half attack lifecycle, including unarmed attacks.
    Drawn=false;
    WalkWeight=1;
    if (Attack) return;
    Drawn=IsValid(Agent.GetHeldSword());
    float RunWeight;
    if (!Agent.GetLocomotionCheckpointWeights(WalkWeight,RunWeight)) WalkWeight=1;
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
    if (!Set(Agent,Child,Damping,false,OutError)) return false;
    ProphecyJointDamping::RemoveJoint(Agent,Child);
    return true;
}
bool UProphecyJointDampingLibrary::SetJoltAllJointsAngularDamping(AProphecyAgent* Agent,float Damping,FString& OutError)
{
    if (!Set(Agent,NAME_None,Damping,true,OutError)) return false;
    ProphecyJointDamping::Remove(Agent);
    return true;
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
    FProfile Profile{WalkSheathed,RunSheathed,WalkDrawn,RunDrawn};
    float W; bool Drawn,Attack;
    Context(*Agent,W,Drawn,Attack);
    if (!Set(Agent,ChildBone,Profile.Resolve(W,Drawn,Attack),false,OutError)) return false;
    if (WalkSheathed==0 && RunSheathed==0 && WalkDrawn==0 && RunDrawn==0)
    { RemoveJoint(Agent,ChildBone); return true; }
    auto& State=States.FindOrAdd(Agent);
    State.Joints.Add(ChildBone,Profile);
    State.ContextValid=false;
    return true;
}

bool ProphecyJointDamping::Update(AProphecyAgent* Agent,const FProphecyJoltBodyHandle& RigBody,FString& Error)
{
    auto* State=States.IsEmpty() ? nullptr : States.Find(Agent);
    if (!State) return true;
    float W; bool Drawn,Attack;
    Context(*Agent,W,Drawn,Attack);
    const bool NewRig=State->RigBody.WorldLifetime!=RigBody.WorldLifetime
        || State->RigBody.Slot!=RigBody.Slot || State->RigBody.Generation!=RigBody.Generation;
    if (!NewRig && State->ContextValid && State->WalkWeight==W && State->Drawn==Drawn && State->Attack==Attack)
        return true;
    auto* World=Agent->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    for (auto& Item:State->Joints)
    {
        auto& Profile=Item.Value;
        const float Value=Profile.Resolve(W,Drawn,Attack);
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
        }
    }
    State->RigBody=RigBody;
    State->WalkWeight=W; State->Drawn=Drawn; State->Attack=Attack; State->ContextValid=true;
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
