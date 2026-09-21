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
    FLeeways Settings;
    for (int32 Index=0;Index<4;++Index) Settings.Values[Index]=float(Index+1);
    TestEqual(TEXT("Locomotion allowance"),Settings.For(EProphecyAgentState::Locomotion),1.f);
    TestEqual(TEXT("Attack allowance"),Settings.For(EProphecyAgentState::Attacking),2.f);
    TestEqual(TEXT("Parry allowance"),Settings.For(EProphecyAgentState::Parrying),3.f);
    TestEqual(TEXT("Dodge allowance"),Settings.For(EProphecyAgentState::Dodging),4.f);
    return true;
}
#endif
