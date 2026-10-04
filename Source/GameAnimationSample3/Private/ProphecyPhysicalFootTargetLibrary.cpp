#include "ProphecyPhysicalFootTargetLibrary.h"
#include "ProphecyNNModifierDebug.h"
#include "ProphecyPhysicalFootTarget.h"
#include "ProphecyAgent.h"
#include "ProphecyNNDefenseLibrary.h"
#include "Engine/World.h"
#include "ProphecyClampEase.inl"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"

namespace ProphecyPhysicalFootTarget
{
struct FLeeways
{
    float Values[4]={0,0,0,0}; // Locomotion, attack, parry, dodge.
    float For(EProphecyAgentState State) const
    {
        switch (State)
        {
        case EProphecyAgentState::Attacking: return Values[1];
        case EProphecyAgentState::Parrying: return Values[2];
        case EProphecyAgentState::Dodging: return Values[3];
        default: return Values[0];
        }
    }
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FLeeways> Overrides;
static FDelegateHandle Cleanup;
static EProphecyAgentState LowerState(EProphecyAgentState State,bool Half)
{
    return State==EProphecyAgentState::Attacking && Half ? EProphecyAgentState::Locomotion : State;
}
static EProphecyAgentState LowerState(const AProphecyAgent* Agent)
{
    const auto State=UProphecyNNDefenseLibrary::GetAgentState(const_cast<AProphecyAgent*>(Agent));
    if (Agent && State==EProphecyAgentState::Attacking)
    {
        FName Attack;bool Half=false,Armed=false,Hit=false;int32 Frame=0;
        if (Agent->GetNNAttackState(Attack,Half,Armed,Hit,Frame)) return LowerState(State,Half);
    }
    return State;
}
static float CalfLeewayFor(const AProphecyAgent* Agent,EProphecyAgentState State)
{
    if (!Agent) return 0.f;
    if (State==EProphecyAgentState::Locomotion)
        return Agent->bOverrideLocomotionCalfClamp && Agent->bLocomotionCalfClamp
            ? FMath::Max(0.f,Agent->LocomotionCalfClampLeewayCm) : 0.f;
    if (State==EProphecyAgentState::Attacking)
        return Agent->bOverrideAttackCalfClamp && Agent->bAttackCalfClamp
            ? FMath::Max(0.f,Agent->AttackCalfClampLeewayCm) : 0.f;
    // Defense retains its existing physical range policy.
    return 0.f;
}
float LocomotionCalfLeeway(const AProphecyAgent* Agent)
{
    return LowerState(Agent)==EProphecyAgentState::Locomotion
        ? CalfLeewayFor(Agent,EProphecyAgentState::Locomotion) : 0.f;
}
float CalfLeeway(const AProphecyAgent* Agent)
{
    // This effective value is shared by the ankle joint and physical foot drive.
    return ProphecyClampEase::Resolve(Agent,ProphecyClampEase::EChannel::PhysicalCalf,
        CalfLeewayFor(Agent,LowerState(Agent)));
}
static float ObservedFootOffset(const AProphecyAgent* Agent)
{
    const auto* Mesh=Agent?Agent->GetPoseReferenceMesh():nullptr;
    const auto* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;
    if(!Asset)return -1;
    float Result=0;
    for(int32 Side=0;Side<2;++Side)
    {
        const FName Foot=Side==0?TEXT("foot_l"):TEXT("foot_r"),Calf=Side==0?TEXT("calf_l"):TEXT("calf_r");
        const int32 Index=Asset->GetRefSkeleton().FindBoneIndex(Foot);if(Index==INDEX_NONE)continue;
        FTransform F,C;FVector Linear,Angular;bool Sim=false;
        if(!Agent->GetPhysicalBodyState(Foot,F,Linear,Angular,Sim) || !Agent->GetPhysicalBodyState(Calf,C,Linear,Angular,Sim))continue;
        Result=FMath::Max(Result,float(FVector::Distance(F.GetLocation(),C.TransformPosition(Asset->GetRefSkeleton().GetRefBonePose()[Index].GetLocation()))));
    }
    return Result;
}
float Leeway(const AProphecyAgent* Agent)
{
    const auto* Settings=Overrides.IsEmpty() ? nullptr : Overrides.Find(Agent);
    if (!Settings)
    {
        if(ProphecyClampEase::Current(Agent,ProphecyClampEase::EChannel::PhysicalFoot,0)<=0)return 0;
        const float Observed=ProphecyClampEase::NeedsObservation(Agent,ProphecyClampEase::EChannel::PhysicalFoot,0)?ObservedFootOffset(Agent):-1;
        return ProphecyClampEase::Resolve(Agent,ProphecyClampEase::EChannel::PhysicalFoot,0,Observed);
    }
    // All-mode settings avoid even the activity-state lookup.
    const auto& V=Settings->Values;
    const float Target=V[0]==V[1] && V[0]==V[2] && V[0]==V[3]?V[0]:Settings->For(LowerState(Agent));
    const float Observed=ProphecyClampEase::NeedsObservation(Agent,ProphecyClampEase::EChannel::PhysicalFoot,Target)
        ? ObservedFootOffset(Agent):-1;
    return ProphecyClampEase::Resolve(Agent,ProphecyClampEase::EChannel::PhysicalFoot,Target,Observed);
}
}

bool UProphecyPhysicalFootTargetLibrary::SetPhysicalFootTargetClampLeeway(
    AProphecyAgent* Agent,float LeewayCm,EProphecyClampProfileMode Mode)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown || !FMath::IsFinite(LeewayCm)
        || LeewayCm<0.f || uint8(Mode)>uint8(EProphecyClampProfileMode::Dodge)) return false;
    using namespace ProphecyPhysicalFootTarget;
    if (Mode==EProphecyClampProfileMode::All && LeewayCm==0.f) { Overrides.Remove(Agent);return true; }
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=Overrides.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
    auto& Settings=Overrides.FindOrAdd(Agent);
    if (Mode==EProphecyClampProfileMode::All) for (float& Value:Settings.Values) Value=LeewayCm;
    else Settings.Values[uint8(Mode)-1]=LeewayCm;
    bool Default=true;
    for (float Value:Settings.Values) Default &= Value==0.f;
    if (Default) Overrides.Remove(Agent);
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyClampEaseTest,"Prophecy.NN.ClampEase.Transitions",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyClampEaseTest::RunTest(const FString&)
{
    using namespace ProphecyClampEase;
    FReduction R;R.Request(2);R.Request(10);
    TestEqual(TEXT("Opening is immediate"),R.Value,10.f);
    R.Request(0);float Previous=R.Value;
    for(int32 I=0;I<15;++I)
    {
        R.Request(0);R.Advance(1./60.);
        TestTrue(TEXT("Repeated requests cannot restart tightening"),R.Value<Previous);
        if(I<14)TestTrue(TEXT("Does not close before the blend ends"),R.Value>0);
        Previous=R.Value;
    }
    TestTrue(TEXT("Exact target and no active work at completion"),R.Value==0 && !R.Active);
    R.Request(-1);R.Request(2,7);
    TestEqual(TEXT("Re-enabling preserves actual outgoing slack"),R.Value,7.f);
    R.Advance(.1);const float Mid=R.Value;R.Request(1);
    TestEqual(TEXT("Interrupted reduction starts continuously"),R.Value,Mid);
    TestEqual(TEXT("Continuous target updates retain the closing deadline"),R.Elapsed,.1);
    R.Request(20);TestEqual(TEXT("Opening interrupts a closing blend immediately"),R.Value,20.f);
    R.Request(0,3);TestEqual(TEXT("Large allowance closes from used slack"),R.Value,3.f);
    R.Request(-1);TestTrue(TEXT("Disable cancels and leaves no active blend"),R.Value<0 && !R.Active);
    R.Request(20);R.Request(19);
    for(int32 I=0;I<15;++I){R.Request(19.f-I);R.Advance(1./60.);}
    TestTrue(TEXT("Per-tick Blueprint reductions cannot stall closing"),R.Value==5 && !R.Active);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyPhysicalFootLeewayTest,"Prophecy.Physics.FootTargetLeeway",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyPhysicalFootLeewayTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalFootTarget;
    auto* Agent=NewObject<AProphecyAgent>();
    TestEqual(TEXT("Unconfigured calf keeps old physical range"),LocomotionCalfLeeway(Agent),0.f);
    Agent->SetLocomotionCalfClamp(true,2);
    TestEqual(TEXT("Enabled calf leeway is inherited"),LocomotionCalfLeeway(Agent),2.f);
    Agent->SetLocomotionCalfClamp(true,.5f);
    TestEqual(TEXT("Current value is read rather than latched"),LocomotionCalfLeeway(Agent),.5f);
    Agent->SetLocomotionCalfClamp(false,2);
    TestEqual(TEXT("Disabled clamp does not invent unlimited joint freedom"),LocomotionCalfLeeway(Agent),0.f);
    Agent->SetLocomotionCalfClamp(true,0);
    TestEqual(TEXT("Zero clamp restores locked ankle"),LocomotionCalfLeeway(Agent),0.f);
    Agent->SetLocomotionCalfClamp(true,2);
    Agent->SetAttackCalfClamp(true,5);
    for (const bool Half:{false,true})
    {
        const auto State=LowerState(EProphecyAgentState::Attacking,Half);
        TestEqual(TEXT("Physical ankle follows the owner of the legs"),CalfLeewayFor(Agent,State),Half?2.f:5.f);
        FLeeways Profiles;Profiles.Values[0]=3;Profiles.Values[1]=1000;
        TestEqual(TEXT("Foot drive profile follows the same lower owner"),Profiles.For(State),Half?3.f:1000.f);
    }
    Agent->SetAttackCalfClamp(true,0);
    TestEqual(TEXT("Explicit zero attack allowance locks the ankle"),CalfLeewayFor(Agent,EProphecyAgentState::Attacking),0.f);
    Agent->SetAttackCalfClamp(false,5);
    TestEqual(TEXT("Disabled attack clamp does not invent unlimited joint freedom"),CalfLeewayFor(Agent,EProphecyAgentState::Attacking),0.f);
    TestEqual(TEXT("Attack settings do not overwrite half/locomotion allowance"),CalfLeeway(Agent),2.f);
    Agent->SetAttackCalfClamp(true,7);
    TestEqual(TEXT("Full attack reads current values without latching"),CalfLeewayFor(Agent,EProphecyAgentState::Attacking),7.f);
    TestEqual(TEXT("Defense keeps its previous joint policy"),CalfLeewayFor(Agent,EProphecyAgentState::Parrying),0.f);
    const FVector End(12,-8,40), Target=End+FVector(3,4,0);
    TestTrue(TEXT("Default exactly retains calf endpoint"),Clamp(Target,End,0)==End);
    TestTrue(TEXT("Inside allowance keeps original target"),Clamp(Target,End,6)==Target);
    TestTrue(TEXT("Boundary keeps original target"),Clamp(Target,End,5)==Target);
    TestTrue(TEXT("Outside allowance projects toward original foot"),Clamp(Target,End,2).Equals(End+FVector(1.2,1.6,0),1.e-8));
    TestTrue(TEXT("Coincident target is stable"),Clamp(End,End,2)==End);
    const FTransform Frame(FRotator(19,83,-12),FVector(100,-250,30));
    TestTrue(TEXT("World-space rotation preserves allowance"),
        Clamp(Frame.TransformPosition(Target),Frame.TransformPosition(End),2).Equals(
            Frame.TransformPosition(End+FVector(1.2,1.6,0)),1.e-8));
    const FTransform Calf(FRotator(11,37,-8),FVector(12,-5,43));
    const FVector Offset(-42.56,.11,.43);
    const FVector Rest=Calf.TransformPosition(Offset),Axis=(Rest-Calf.GetLocation()).GetSafeNormal();
    TestTrue(TEXT("No return exactly retains original endpoint"),CalfEnd(Calf,Offset,0)==Rest);
    for(float Delta:{-5.f,2.f,5.f})
    {
        const FVector Authored=Rest+Axis*Delta;
        TestTrue(TEXT("Physical drive follows the presented signed length, not a newer return tick"),PresentedCalfEnd(Calf,Offset,Authored).Equals(Authored,1.e-8));
        TestTrue(TEXT("Presented recovery endpoint is covariant under world rotation"),PresentedCalfEnd(Calf*Frame,Offset,Frame.TransformPosition(Authored)).Equals(Frame.TransformPosition(Authored),1.e-7));
        TestTrue(TEXT("First return follows outgoing signed target without snapping to rest"),Clamp(Authored,CalfEnd(Calf,Offset,Delta),0).Equals(Authored,1.e-8));
        TestTrue(TEXT("Physical leeway is still applied around returning endpoint"),Clamp(Authored+FVector(3,4,0),CalfEnd(Calf,Offset,Delta),2).Equals(Authored+FVector(1.2,1.6,0),1.e-8));
        FVector Previous=Authored;
        for(int32 Tick=1;Tick<=60;++Tick)
        {
            const double A=double(Tick)/60.;const float Remaining=Delta*float(1-A*A*(3-2*A));
            const FVector ReturningTarget=CalfEnd(Calf,Offset,Remaining);
            TestTrue(TEXT("Both signs return continuously on existing clock"),FVector::Distance(ReturningTarget,Previous)<.126);
            Previous=ReturningTarget;
        }
        TestTrue(TEXT("Completion exactly restores rest endpoint"),Previous==Rest);
        TestTrue(TEXT("World frame does not change signed allowance"),CalfEnd(Calf*Frame,Offset,Delta).Equals(Frame.TransformPosition(Authored),1.e-7));
    }
    FLeeways Settings;
    for (int32 Index=0;Index<4;++Index) Settings.Values[Index]=float(Index+1);
    TestEqual(TEXT("Locomotion allowance"),Settings.For(EProphecyAgentState::Locomotion),1.f);
    TestEqual(TEXT("Attack allowance"),Settings.For(EProphecyAgentState::Attacking),2.f);
    TestEqual(TEXT("Parry allowance"),Settings.For(EProphecyAgentState::Parrying),3.f);
    TestEqual(TEXT("Dodge allowance"),Settings.For(EProphecyAgentState::Dodging),4.f);
    return true;
}
#endif


void ProphecyNNModifierDebug::ClampBlends(FReport& R)
{
    using namespace ProphecyClampEase;
    const auto* S=States.Find(R.Agent);
    const bool Physical=R.Agent->GetSimulationMode()!=EProphecyAgentSimulationMode::Kinematic;
    static const TCHAR* Names[]={TEXT("Foot reach"),TEXT("Calf length"),TEXT("Physical calf"),TEXT("Physical foot target"),TEXT("Left wrist")};
    if(S)for(int32 I=0;I<int32(EChannel::Count);++I)
    {
        const auto& C=S->Values[I];if(!C.Active || ((I==2 || I==3) && !Physical))continue;
        const FString Key=FString::Printf(TEXT("ClampTighten%d"),I);
        R.Add(*Key,TEXT("CONSTRAINT"),*FString::Printf(TEXT("%s tightening"),Names[I]),FString::Printf(TEXT("%.3f -> %.3f | %.3f / %.3f"),C.Value,C.Target,C.Elapsed,Duration));
    }
    if(Physical)
    {
        const auto Mode=R.Defense?(R.Dodge?EProphecyAgentState::Dodging:EProphecyAgentState::Parrying):R.Attack&&!R.Half?EProphecyAgentState::Attacking:EProphecyAgentState::Locomotion;
        const auto* C=ProphecyPhysicalFootTarget::Overrides.Find(R.Agent);
        const float Foot=Current(R.Agent,EChannel::PhysicalFoot,C?C->For(Mode):0);
        const float Calf=Current(R.Agent,EChannel::PhysicalCalf,ProphecyPhysicalFootTarget::CalfLeewayFor(R.Agent,Mode));
        R.Add(TEXT("PhysicalFootTarget"),TEXT("PHYSICS"),TEXT("Physical foot target / calf joint limits"),FString::Printf(TEXT("foot offset %.3f cm | calf allowance %.3f cm"),Foot,Calf));
    }
}
