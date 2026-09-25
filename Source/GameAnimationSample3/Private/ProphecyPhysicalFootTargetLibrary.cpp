#include "ProphecyPhysicalFootTargetLibrary.h"
#include "ProphecyPhysicalFootTarget.h"
#include "ProphecyAgent.h"
#include "ProphecyNNDefenseLibrary.h"
#include "Engine/World.h"

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
float LocomotionCalfLeeway(const AProphecyAgent* Agent)
{
    if (!Agent || !Agent->bOverrideLocomotionCalfClamp || !Agent->bLocomotionCalfClamp
        || Agent->LocomotionCalfClampLeewayCm<=0.f) return 0.f;
    return UProphecyNNDefenseLibrary::GetAgentState(const_cast<AProphecyAgent*>(Agent))==EProphecyAgentState::Locomotion
        ? Agent->LocomotionCalfClampLeewayCm : 0.f;
}
float Leeway(const AProphecyAgent* Agent)
{
    const auto* Settings=Overrides.IsEmpty() ? nullptr : Overrides.Find(Agent);
    if (!Settings) return 0.f;
    // All-mode settings avoid even the activity-state lookup.
    const auto& V=Settings->Values;
    if (V[0]==V[1] && V[0]==V[2] && V[0]==V[3]) return V[0];
    return Settings->For(UProphecyNNDefenseLibrary::GetAgentState(const_cast<AProphecyAgent*>(Agent)));
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
