#include "ProphecyDefenseArmedGate.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecySwordAttackCollision.h"

namespace ProphecyDefenseArmedGate
{
namespace
{
struct FRequest
{
    TWeakObjectPtr<AProphecyNNLocomotionManager> Manager;
    TWeakObjectPtr<AProphecyAgent> Attacker;
    bool bDodge;
    float MaximumSeconds;
    TSharedPtr<FHistory> History;
};
TMap<TWeakObjectPtr<const AProphecyAgent>, FRequest> Waiting;
TMap<TWeakObjectPtr<const AProphecyAgent>,TWeakObjectPtr<AProphecyAgent>> Victims;
const FHistory* Activating=nullptr;
struct FDelays { int32 Mode[2][16]={}; };
TMap<TWeakObjectPtr<const AProphecyAgent>,FDelays> Delays;
const FName Families[]={TEXT("headbutt"),TEXT("hookL"),TEXT("hookR"),TEXT("jabL"),TEXT("jabR"),
    TEXT("kickL"),TEXT("kickR"),TEXT("overL"),TEXT("overR"),TEXT("pike"),
    TEXT("slashL"),TEXT("slashLD"),TEXT("slashLU"),TEXT("slashR"),TEXT("slashRD"),TEXT("slashRU")};
}

bool SetStartDelays(AProphecyAgent* Defender,bool Dodge,TConstArrayView<int32> Values)
{
    if(!IsInGameThread() || !IsValid(Defender) || Values.Num()!=16)return false;
    for(int32 V:Values)if(V<0)return false;
    auto& Profile=Delays.FindOrAdd(Defender);
    FMemory::Memcpy(Profile.Mode[Dodge?1:0],Values.GetData(),16*sizeof(int32));
    bool Any=false;
    for(const auto& Mode:Profile.Mode)for(int32 V:Mode)Any|=V>0;
    if(!Any)Delays.Remove(Defender);
    return true;
}
void RemoveStartDelays(const AProphecyAgent* Agent) { Delays.Remove(Agent); }
bool CanStart(const AProphecyAgent* Defender,FName Family,bool Armed,bool Dodge,int64 TicksSinceArmed)
{
    if(!Armed)return false;
    if(Delays.IsEmpty())return true;
    const auto* Profile=Delays.Find(Defender);
    if(!Profile)return true;
    for(int32 I=0;I<UE_ARRAY_COUNT(Families);++I)if(Family==Families[I])
    {
        const int32 Delay=Profile->Mode[Dodge?1:0][I];
        return Delay==0 || TicksSinceArmed>=Delay;
    }
    return true; // Synthetic spear and other non-bank attacks retain their timing.
}

const FHistory* ActivationHistory(const AProphecyAgent* Defender)
{ return Activating && Activating->bValid && Activating->Owner.Get()==Defender?Activating:nullptr; }
void Capture(AProphecyNNLocomotionManager* Manager,TFunctionRef<void(AProphecyAgent*,FHistory&)> Read)
{
    if (Waiting.IsEmpty()) return;
    for (auto& Pair:Waiting) if (Pair.Value.Manager.Get()==Manager && Pair.Key.IsValid())
    {
        auto& History=*Pair.Value.History;History.bValid=false;History.Owner=Pair.Key;
        Read(const_cast<AProphecyAgent*>(Pair.Key.Get()),History);
    }
}

void SetVictim(const AProphecyAgent* Attacker,AProphecyAgent* Victim)
{
    if (Victim) Victims.Add(Attacker,Victim);else Victims.Remove(Attacker);
    ProphecySwordNoReaction::VictimChanged(const_cast<AProphecyAgent*>(Attacker));
}
AProphecyAgent* GetVictim(const AProphecyAgent* Attacker)
{ const auto* Victim=Victims.Find(Attacker);return Victim?Victim->Get():nullptr; }
void WaitingResponses(const AProphecyAgent* Attacker,const AProphecyAgent* Victim,bool& bParry,bool& bDodge)
{
    for (const auto& Pair:Waiting)
        if (Pair.Key.IsValid() && Pair.Value.Attacker.Get()==Attacker && (!Victim || Pair.Key.Get()==Victim))
        { if (Pair.Value.bDodge) bDodge=true;else bParry=true; }
}
void RemoveAgent(const AProphecyAgent* Agent) { Cancel(Agent);AttackEnded(Agent); }

void Queue(AProphecyNNLocomotionManager* Manager, AProphecyAgent* Defender,
    AProphecyAgent* Attacker, bool bDodge,  float MaximumSeconds)
{
    Waiting.Add(Defender, {Manager, Attacker, bDodge, MaximumSeconds,MakeShared<FHistory>()});
}
bool IsWaiting(const AProphecyAgent* Defender) { return Waiting.Contains(Defender); }
bool Cancel(const AProphecyAgent* Defender) { return Waiting.Remove(Defender) != 0; }
void AttackEnded(const AProphecyAgent* Attacker)
{
    Victims.Remove(Attacker);
    for (auto It = Waiting.CreateIterator(); It; ++It)
        if (It.Value().Attacker.Get() == Attacker) It.RemoveCurrent();
}
void RemoveManager(const AProphecyNNLocomotionManager* Manager)
{
    for (auto It = Waiting.CreateIterator(); It; ++It)
        if (!It.Value().Manager.IsValid() || It.Value().Manager.Get() == Manager) It.RemoveCurrent();
}
void Advance(AProphecyNNLocomotionManager* Manager)
{
    // Empty in normal gameplay: no actor scans, pose reads, allocations or NN calls.
    if (Waiting.IsEmpty()) return;
    TArray<TPair<TWeakObjectPtr<const AProphecyAgent>, FRequest>, TInlineAllocator<8>> Ready;
    for (auto It = Waiting.CreateIterator(); It; ++It)
    {
        if (!It.Key().IsValid() || !It.Value().Attacker.IsValid() || !It.Value().Manager.IsValid())
        { It.RemoveCurrent(); continue; }
        const auto& Request = It.Value();
        if (Request.Manager.Get() != Manager) continue;
        const AProphecyAgent* Defender = It.Key().Get();
        AProphecyAgent* Attacker = Request.Attacker.Get();
        if (Manager->ResolveAgent(Defender->GetAgentHandle()) != Defender ||
            Manager->ResolveAgent(Attacker->GetAgentHandle()) != Attacker)
        { It.RemoveCurrent(); continue; }
        FName Family; bool bHalf, bArmed, bHit; int32 Frame;int64 ArmedTicks;
        if (!Manager->GetAgentNNAttackState(Attacker->GetAgentHandle(), Family, bHalf, bArmed, bHit, Frame,&ArmedTicks))
        { It.RemoveCurrent(); continue; }
        if (!Defender->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled ||
            !CanStart(Defender,Family,bArmed,Request.bDodge,ArmedTicks)) continue;
        Ready.Emplace(It.Key(), Request);
        It.RemoveCurrent();
    }
    // Start methods and attack interruption may cancel other requests; never do
    // that while iterating the map. Capture fresh defender history only now.
    for (const auto& Pair : Ready)
    {
        AProphecyAgent* Defender = const_cast<AProphecyAgent*>(Pair.Key.Get());
        AProphecyAgent* Attacker = Pair.Value.Attacker.Get();
        if (!IsValid(Defender) || !IsValid(Attacker)) continue;
        FName Family; bool bHalf, bArmed, bHit; int32 Frame;int64 ArmedTicks;
        if (!Manager->GetAgentNNAttackState(Attacker->GetAgentHandle(), Family, bHalf, bArmed, bHit, Frame,&ArmedTicks) ||
            !CanStart(Defender,Family,bArmed,Pair.Value.bDodge,ArmedTicks)) continue;
        FString Error;
        TGuardValue<const FHistory*> Scope(Activating,Pair.Value.History.Get());
        const bool Started = Pair.Value.bDodge
            ? Manager->StartAgentNNDodge(Defender->GetAgentHandle(), Attacker, Pair.Value.MaximumSeconds, Error)
            : Manager->StartAgentNNParry(Defender->GetAgentHandle(), Attacker, Pair.Value.MaximumSeconds, Error);
        if (!Started) UE_LOG(LogTemp, Warning, TEXT("Armed defense for %s could not start: %s"), *GetNameSafe(Defender), *Error);
    }
}
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "ProphecyBlendClock.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseStartDelayTest,"Prophecy.NN.Defense.StartTickDelays",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseStartDelayTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseArmedGate;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    auto* B=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A||!B)return false;
    const int Original=Delays.Num();int32 V[16]={};
    for(FName F:Families)
    {
        TestTrue(TEXT("Zero starts at Armed"),CanStart(A,F,true,false,0));
        TestFalse(TEXT("Cannot start before Armed"),CanStart(A,F,false,false,100));
    }
    for(int I=0;I<16;++I)
    {
        FMemory::Memzero(V);V[I]=3;SetStartDelays(A,false,V);
        for(int J=0;J<16;++J)TestEqual(TEXT("Family slots independent"),CanStart(A,Families[J],true,false,2),I!=J);
        TestTrue(TEXT("Exact deadline opens"),CanStart(A,Families[I],true,false,3));
        TestTrue(TEXT("Late request counts from Armed, not request"),CanStart(A,Families[I],true,false,100));
        TestFalse(TEXT("Missing Armed stamp cannot open delayed gate"),CanStart(A,Families[I],true,false,-1));
        TestTrue(TEXT("Dodge independent"),CanStart(A,Families[I],true,true,0));
        TestTrue(TEXT("Defenders independent"),CanStart(B,Families[I],true,false,0));
        TestTrue(TEXT("Spear bypass"),CanStart(A,TEXT("spear"),true,false,0));
    }
    UProphecyNNDefenseLibrary::SetParryStartHitThresholds(A,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16);
    for(int I=0;I<16;++I)
    {
        TestFalse(TEXT("Integer pin mapping before deadline"),CanStart(A,Families[I],true,false,I));
        TestTrue(TEXT("Integer pin mapping at deadline"),CanStart(A,Families[I],true,false,I+1));
    }
    UProphecyNNDefenseLibrary::SetDodgeStartHitThresholds(A,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1);
    TestFalse(TEXT("One waits at Armed"),CanStart(A,TEXT("jabR"),true,true,0));
    TestTrue(TEXT("One opens next game tick"),CanStart(A,TEXT("jabR"),true,true,1));
    V[0]=-1;TestFalse(TEXT("Negative rejected atomically"),SetStartDelays(A,true,V));
    TestFalse(TEXT("Invalid write preserves delay"),CanStart(A,TEXT("headbutt"),true,true,0));
    UProphecyNNDefenseLibrary::SetParryStartHitThresholds(A);
    TestTrue(TEXT("Reset only Parry"),CanStart(A,TEXT("jabR"),true,false,0));
    TestFalse(TEXT("Dodge retained"),CanStart(A,TEXT("jabR"),true,true,0));
    for(float FPS:{30.f,60.f,120.f})
    {
        int64 Tick=100,Armed=100;
        for(int I=0;I<3;++I)if(ProphecyBlendClock::TickBudget(false,1.f/FPS)>0)++Tick;
        TestEqual(TEXT("Game ticks independent of FPS"),ArmedElapsed(Tick,Armed),int64(3));
        if(ProphecyBlendClock::TickBudget(true,1.f/FPS)>0)++Tick;
        if(ProphecyBlendClock::TickBudget(false,0)>0)++Tick;
        TestEqual(TEXT("Pause/zero budget do not advance"),ArmedElapsed(Tick,Armed),int64(3));
        TestEqual(TEXT("New attack has no Armed time"),ArmedElapsed(Tick,-1),int64(-1));
    }
    Queue(nullptr,A,B,true,3);
    for(int I=0;I<5;++I)
    {
        Capture(nullptr,[&](AProphecyAgent*,FHistory& H){H.bValid=true;H.Root[1].X=I;});
        TestEqual(TEXT("Delayed request keeps fresh history"),Waiting.FindChecked(A).History->Root[1].X,float(I));
    }
    AttackEnded(B);TestFalse(TEXT("Attack end cancels pending delay"),IsWaiting(A));
    Queue(nullptr,A,B,true,3);TestTrue(TEXT("Manual stop cancels delay"),Cancel(A));
    RemoveStartDelays(A);RemoveStartDelays(B);
    TestEqual(TEXT("Profiles cleaned up"),Delays.Num(),Original);
    W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
