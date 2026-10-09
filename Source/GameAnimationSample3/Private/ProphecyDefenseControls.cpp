#include "ProphecyDefenseControls.h"
#include "ProphecyAgent.h"
#include "ProphecyClampProfiles.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyDefenseFeatures.h"
#include "ProphecyDefenseCollision.h"
#include "ProphecyDefenseArmedGate.h"
namespace ProphecyDefenseControls
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,bool> RemoveHorizontalVelocity;
bool SetRemoveHorizontalVelocity(AProphecyAgent* Agent,bool Enabled,bool UseRoot)
{
    if(!IsInGameThread() || !IsValid(Agent))return false;
    if(Enabled)RemoveHorizontalVelocity.Add(Agent,UseRoot);else RemoveHorizontalVelocity.Remove(Agent);
    return true;
}
void FilterHalfAttack(const AProphecyAgent* Agent,bool Half,ProphecyDefenseFeatures::FContext& C,
    const FVector3f& PreviousRoot,const FVector3f& CurrentRoot)
{
    if(!Half || RemoveHorizontalVelocity.IsEmpty())return;
    const auto* UseRoot=RemoveHorizontalVelocity.Find(Agent);if(!UseRoot)return;
    if(*UseRoot)ProphecyDefenseFeatures::RemoveAttackerRootHorizontalVelocity(C,CurrentRoot-PreviousRoot);
    else ProphecyDefenseFeatures::RemoveAttackerHorizontalVelocity(C);
}
namespace { struct FPair { FSettings Modes[2]; }; TMap<TWeakObjectPtr<const AProphecyAgent>,FPair> Settings; }
namespace { struct FHitDelays { int32 Parry=3,Dodge=3; }; TMap<TWeakObjectPtr<const AProphecyAgent>,FHitDelays> HitDelays; }
namespace
{
struct FRelativeTarget { FVector Local; const FProphecyNNDefenseStatus* Status; };
TMap<TWeakObjectPtr<const AProphecyAgent>,FRelativeTarget> RelativeTargets;
}
void CaptureRelativeTarget(AProphecyAgent* Agent,const FVector& WorldTarget,const FProphecyNNDefenseStatus& Status)
{
    RelativeTargets.Add(Agent,{Agent->GetActorTransform().InverseTransformPositionNoScale(WorldTarget),&Status});
}
void ClearRelativeTarget(const AProphecyAgent* Agent) { RelativeTargets.Remove(Agent); }
bool GetRelativeTarget(const AProphecyAgent* Agent,FVector& WorldTarget,FVector& RootLocalTarget)
{
    WorldTarget=RootLocalTarget=FVector::ZeroVector;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed())return false;
    const auto* Target=RelativeTargets.Find(Agent);
    // Status belongs to the defense pose. Stop clears this entry before pose
    // replacement; agent/manager teardown also removes it through Remove().
    if(!Target || !Target->Status->Active)return false;
    RootLocalTarget=Target->Local;
    WorldTarget=Agent->GetActorTransform().TransformPositionNoScale(RootLocalTarget);
    return true;
}
const FSettings* Find(const AProphecyAgent* Agent,bool bDodge)
{ const auto* Pair=Settings.Find(Agent);return Pair?&Pair->Modes[bDodge?1:0]:nullptr; }
bool Set(AProphecyAgent* Agent,bool bDodge,ELimb Limb,bool bEnabled,float LeewayCm)
{
    if (!IsInGameThread() || !IsValid(Agent) || !FMath::IsFinite(LeewayCm) || LeewayCm<0) return false;
    ProphecyClampProfiles::Cancel(Agent,bDodge?ProphecyClampProfiles::EMode::Dodge:ProphecyClampProfiles::EMode::Parry,int32(Limb));
    RestoreClamp(Agent,bDodge,Limb,{true,bEnabled,LeewayCm});return true;
}
void RestoreClamp(AProphecyAgent* Agent,bool bDodge,ELimb Limb,FClamp Value)
{
    auto& Mode=Settings.FindOrAdd(Agent).Modes[bDodge?1:0];
    auto& Clamp=Limb==ELimb::Foot?Mode.Foot:Mode.Calf;
    Clamp=Value;
}
bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{
    if (!IsInGameThread() || !IsValid(Agent) || Frames<0) return false;
    HitDelays.FindOrAdd(Agent).Dodge=Frames;
    return true;
}
int32 GetDodgeFramesAfterHit(const AProphecyAgent* Agent)
{ return GetFramesAfterHit(Agent,true); }
bool SetDefenseFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{
    if (!IsInGameThread() || !IsValid(Agent) || Frames<0) return false;
    if (Frames==3) HitDelays.Remove(Agent);else HitDelays.Add(Agent,{Frames,Frames});
    return true;
}
int32 GetFramesAfterHit(const AProphecyAgent* Agent,bool bDodge)
{ const auto* Delay=HitDelays.Find(Agent);return Delay?(bDodge?Delay->Dodge:Delay->Parry):3; }
void Remove(const AProphecyAgent* Agent) { ProphecyDefenseArmedGate::RemoveStartDelays(Agent);ProphecyDefenseCollision::Remove(Agent);RemoveHorizontalVelocity.Remove(Agent);Settings.Remove(Agent);HitDelays.Remove(Agent);ClearRelativeTarget(Agent); }
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/World.h"
#include "ProphecyNNDefenseLibrary.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseHitDelayTest,"Prophecy.NN.Defense.HitDelayControls",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseHitDelayTest::RunTest(const FString&)
{
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A || !B) { if(W) W->DestroyWorld(false);return false; }
    auto Check=[&](AProphecyAgent* Agent,int32 Dodge,int32 Parry)
    {
        int32 D,P;UProphecyNNDefenseLibrary::GetDefenseFramesAfterHit(Agent,D,P);
        TestEqual(TEXT("Dodge delay"),D,Dodge);TestEqual(TEXT("Parry delay"),P,Parry);
    };
    Check(A,3,3);
    TestTrue(TEXT("Shared zero is accepted"),UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,0));Check(A,0,0);
    TestFalse(TEXT("Negative does not replace existing values"),UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,-1));Check(A,0,0);
    Check(B,3,3);
    UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,7);Check(A,7,7);
    UProphecyNNDefenseLibrary::SetDodgeFramesAfterHit(A,1);Check(A,1,7);
    UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,3);Check(A,3,3);
    UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(A,9);
    ProphecyDefenseControls::Remove(A);Check(A,3,3);
    ProphecyDefenseControls::Remove(B);W->DestroyWorld(false);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseRelativeTargetTest,"Prophecy.NN.Defense.RelativeTarget",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseRelativeTargetTest::RunTest(const FString&)
{
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A || !B){if(W)W->DestroyWorld(false);return false;}
    FProphecyNNDefenseStatus Status;Status.Active=true;
    FVector World,Local;
    auto Read=[&](AProphecyAgent* Actor){return UProphecyNNDefenseLibrary::GetNNDefenseRelativeTarget(Actor,World,Local);};
    TestFalse(TEXT("Inactive has no target"),Read(A));
    const FVector HeadLocal(14,-8,75);
    A->SetActorLocationAndRotation(FVector(1000,-500,90),FRotator(0,35,0));
    const FVector Aim=A->GetActorTransform().TransformPositionNoScale(HeadLocal);
    ProphecyDefenseControls::CaptureRelativeTarget(A,Aim,Status);
    TestTrue(TEXT("Active target available"),Read(A));
    TestTrue(TEXT("Initial target unchanged"),World.Equals(Aim,1.e-8));
    TestTrue(TEXT("Captured local target"),Local.Equals(HeadLocal,1.e-8));
    for(const FRotator Rotation:{FRotator(0,35,0),FRotator(0,120,0),FRotator(20,-80,10)})
    {
        A->SetActorLocationAndRotation(FVector(-234,987,150),Rotation);
        A->SetLocomotionInput(FVector(1,0,0),true,FVector(0,1,0),1,1);
        TestTrue(TEXT("Motion input preserves target"),Read(A));
        TestTrue(TEXT("Target follows translated/rotated root"),World.Equals(A->GetActorTransform().TransformPositionNoScale(HeadLocal),1.e-8));
        TestTrue(TEXT("Root-local point unchanged"),Local.Equals(HeadLocal,1.e-8));
    }
    TestFalse(TEXT("Agent isolation"),Read(B));
    TestTrue(TEXT("Invalid outputs zero"),World.IsZero() && Local.IsZero());
    Status.Active=false;
    TestFalse(TEXT("Inactive status immediately invalidates getter"),Read(A));
    Status.Active=true;
    ProphecyDefenseControls::ClearRelativeTarget(A);
    TestFalse(TEXT("Stop clears target"),Read(A));
    ProphecyDefenseControls::CaptureRelativeTarget(A,Aim,Status);
    ProphecyDefenseControls::Remove(A);
    TestFalse(TEXT("Lifecycle cleanup clears target"),Read(A));
    TestFalse(TEXT("Null rejected"),Read(nullptr));
    ProphecyDefenseControls::Remove(B);W->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
