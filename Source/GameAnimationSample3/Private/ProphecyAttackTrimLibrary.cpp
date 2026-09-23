#include "ProphecyAttackTrimLibrary.h"
#include "ProphecyAttackTrim.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "Engine/World.h"
#include "EngineUtils.h"

namespace ProphecyAttackTrim
{
struct FSettings { int32 Frames[16] = {}; };
static TMap<TWeakObjectPtr<AProphecyAgent>,FSettings> Settings;
static FDelegateHandle Cleanup;
struct FPending
{
    TWeakObjectPtr<AProphecyNNLocomotionManager> Manager;
    TWeakObjectPtr<AProphecyAgent> Agent;
    FName Attack;
    int32 ExpectedFrame;
};
static TArray<FPending> Pending;
static FDelegateHandle HalfTick;
static void RefreshCleanup();
static void RetireHalfTick()
{
    if (Pending.IsEmpty() && HalfTick.IsValid())
    { FWorldDelegates::OnWorldPreActorTick.Remove(HalfTick);HalfTick.Reset(); }
}
void CancelHalfFrame(const AProphecyAgent* Agent)
{
    Pending.RemoveAll([Agent](const FPending& P){return !P.Agent.IsValid() || P.Agent.Get()==Agent;});
    RetireHalfTick();
}
static const FName Names[]={TEXT("slashL"),TEXT("slashR"),TEXT("slashLD"),TEXT("slashRD"),TEXT("slashLU"),TEXT("slashRU"),
    TEXT("pike"),TEXT("jabL"),TEXT("jabR"),TEXT("hookL"),TEXT("hookR"),TEXT("overL"),TEXT("overR"),TEXT("headbutt"),TEXT("kickL"),TEXT("kickR")};

static int32 Resolve(const FSettings& Value,FName Attack,int32 Authored)
{
    for (int32 I=0;I<UE_ARRAY_COUNT(Names);++I)
        if (Names[I]==Attack) return Authored-FMath::Min(FMath::Max(Authored,0),Value.Frames[I]/2);
    return Authored;
}
int32 TailSteps(const AProphecyAgent* Agent,FName Attack,int32 Authored)
{
    CancelHalfFrame(Agent);
    const FSettings* Value=Settings.IsEmpty() ? nullptr : Settings.Find(const_cast<AProphecyAgent*>(Agent));
    return Value ? Resolve(*Value,Attack,Authored) : Authored;
}
static void FinishHalfFrame(UWorld* World,ELevelTick TickType,float DeltaSeconds)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || DeltaSeconds<=0) return;
    TArray<FPending,TInlineAllocator<8>> Due;
    for (int32 I=Pending.Num()-1;I>=0;--I)
    {
        const auto* Agent=Pending[I].Agent.Get();
        if (!Agent || !Pending[I].Manager.IsValid()) { Pending.RemoveAtSwap(I);continue; }
        if (Agent->GetWorld()==World && Agent->bNNInferenceEnabled)
        { Due.Add(Pending[I]);Pending.RemoveAtSwap(I); }
    }
    RetireHalfTick(); // Remove before Blueprint Ended can start another attack.
    for (const auto& P:Due)
    {
        auto* Agent=P.Agent.Get();auto* Manager=P.Manager.Get();
        if (!IsValid(Agent) || !IsValid(Manager)) continue;
        FName Attack;bool Half,Armed,Hit;int32 Frame;
        const auto Handle=Agent->GetAgentHandle();
        if (Manager->ResolveAgent(Handle)==Agent &&
            Manager->GetAgentNNAttackState(Handle,Attack,Half,Armed,Hit,Frame) &&
            Attack==P.Attack && Hit && Frame==P.ExpectedFrame)
            Manager->StopAgentNNAttack(Handle);
    }
}
void QueueHalfFrame(AProphecyNNLocomotionManager* Manager,AProphecyAgent* Agent,FName Attack,int32 ExpectedFrame)
{
    const auto* Value=Settings.IsEmpty()?nullptr:Settings.Find(Agent);
    if (!Value) return;
    for (int32 I=0;I<UE_ARRAY_COUNT(Names);++I)
        if (Names[I]==Attack && (Value->Frames[I]&1))
        {
            CancelHalfFrame(Agent);
            Pending.Add({Manager,Agent,Attack,ExpectedFrame});
            if (!HalfTick.IsValid()) HalfTick=FWorldDelegates::OnWorldPreActorTick.AddStatic(&FinishHalfFrame);
            return;
        }
}
static void RefreshCleanup()
{
    if (!Settings.IsEmpty() && !Cleanup.IsValid())
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            Pending.RemoveAll([World](const FPending& P){return !P.Agent.IsValid() || P.Agent->GetWorld()==World;});
            RetireHalfTick();
            for (auto It=Settings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            RefreshCleanup();
        });
    else if (Settings.IsEmpty() && Cleanup.IsValid())
    { FWorldDelegates::OnWorldCleanup.Remove(Cleanup); Cleanup.Reset(); }
}
}

bool UProphecyAttackTrimLibrary::SetTrimAttack(AProphecyAgent* Agent,
    int32 SlashL,int32 SlashR,int32 SlashLD,int32 SlashRD,int32 SlashLU,int32 SlashRU,int32 Pike,
    int32 JabL,int32 JabR,int32 HookL,int32 HookR,int32 OverL,int32 OverR,int32 Headbutt,int32 KickL,int32 KickR)
{
    using namespace ProphecyAttackTrim;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    FSettings Value{{SlashL,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike,JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR}};
    bool Any=false;
    for (int32 Frames:Value.Frames) { if (Frames<0) return false; Any|=Frames>0; }
    CancelHalfFrame(Agent);
    if (Any) Settings.Add(Agent,Value); else Settings.Remove(Agent);
    RefreshCleanup();
    if (Agent->HasValidAgentHandle())
        for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
            if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
            { It->RefreshAgentAttackTrim(Agent->GetAgentHandle()); break; }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackTrimTest,"Prophecy.Attack.Trim",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyAttackTrimTest::RunTest(const FString&)
{
    using namespace ProphecyAttackTrim;
    for (int32 Selected=0;Selected<UE_ARRAY_COUNT(Names);++Selected)
    {
        FSettings Value;
        for (FName Name:Names) TestEqual(TEXT("Zero retains original finish"),Resolve(Value,Name,5),5);
        Value.Frames[Selected]=1;
        for (int32 Other=0;Other<UE_ARRAY_COUNT(Names);++Other)
            TestEqual(TEXT("Odd trim retains the bounding NN frame"),Resolve(Value,Names[Other],5),5);
        Value.Frames[Selected]=2;
        for (int32 Other=0;Other<UE_ARRAY_COUNT(Names);++Other)
            TestEqual(TEXT("Two 60 Hz frames remove one NN frame only for selected family"),Resolve(Value,Names[Other],5),Other==Selected?4:5);
        for (int32 Trim=0;Trim<=12;++Trim)
        {
            Value.Frames[Selected]=Trim;
            const int32 Tail=Resolve(Value,Names[Selected],5);
            // Existing completion is the next policy boundary after the final output.
            // Odd values hand off one game tick before that boundary.
            const int32 FinishTick=2*(Tail+1)-((Tail>0 && (Trim&1))?1:0);
            TestEqual(TEXT("Every unit advances finish by exactly one 60 Hz tick until Hit clamp"),FinishTick,12-FMath::Min(Trim,10));
        }
        Value.Frames[Selected]=MAX_int32;
        TestEqual(TEXT("Oversized trim stops at Hit without integer overflow"),Resolve(Value,Names[Selected],5),0);
        TestEqual(TEXT("Zero tail remains zero"),Resolve(Value,Names[Selected],0),0);
    }
    TestEqual(TEXT("Unknown family is unchanged"),Resolve(FSettings{},TEXT("unknown"),5),5);
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World?World->SpawnActor<AProphecyAgent>():nullptr;
    auto* Manager=World?World->SpawnActor<AProphecyNNLocomotionManager>():nullptr;
    if (!Agent || !Manager) return false;
    const int32 Before=Pending.Num();
    UProphecyAttackTrimLibrary::SetTrimAttack(Agent,1);
    QueueHalfFrame(Manager,Agent,Names[0],12);
    TestEqual(TEXT("Odd trim schedules exactly one handoff"),Pending.Num(),Before+1);
    QueueHalfFrame(Manager,Agent,Names[0],13);
    TestEqual(TEXT("Retarget replaces pending handoff"),Pending.Num(),Before+1);
    CancelHalfFrame(Agent);
    TestEqual(TEXT("Stop/reset removes handoff"),Pending.Num(),Before);
    UProphecyAttackTrimLibrary::SetTrimAttack(Agent,2);
    QueueHalfFrame(Manager,Agent,Names[0],12);
    TestEqual(TEXT("Even trim has no tick callback"),Pending.Num(),Before);
    UProphecyAttackTrimLibrary::SetTrimAttack(Agent,1);
    QueueHalfFrame(Manager,Agent,Names[0],12);
    FinishHalfFrame(World,LEVELTICK_All,1.f/60);
    TestEqual(TEXT("Stale attack cannot survive one-shot handoff"),Pending.Num(),Before);
    UProphecyAttackTrimLibrary::SetTrimAttack(Agent);
    if (Before==0) TestFalse(TEXT("No dormant half-frame callback"),HalfTick.IsValid());
    World->DestroyWorld(false);
    return true;
}
#endif
