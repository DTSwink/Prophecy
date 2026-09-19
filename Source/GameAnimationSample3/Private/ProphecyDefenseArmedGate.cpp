#include "ProphecyDefenseArmedGate.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNDefenseLibrary.h"

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
{ if (Victim) Victims.Add(Attacker,Victim);else Victims.Remove(Attacker); }
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
        FName Family; bool bHalf, bArmed, bHit; int32 Frame;
        if (!Manager->GetAgentNNAttackState(Attacker->GetAgentHandle(), Family, bHalf, bArmed, bHit, Frame))
        { It.RemoveCurrent(); continue; }
        if (bHit && !Request.bDodge) { It.RemoveCurrent();continue; }
        if (!bArmed || !Defender->bNNInferenceEnabled || !Attacker->bNNInferenceEnabled) continue;
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
        FName Family; bool bHalf, bArmed, bHit; int32 Frame;
        if (!Manager->GetAgentNNAttackState(Attacker->GetAgentHandle(), Family, bHalf, bArmed, bHit, Frame) || !bArmed) continue;
        if (bHit && !Pair.Value.bDodge) continue;
        FString Error;
        TGuardValue<const FHistory*> Scope(Activating,Pair.Value.History.Get());
        const bool Started = Pair.Value.bDodge
            ? Manager->StartAgentNNDodge(Defender->GetAgentHandle(), Attacker, Pair.Value.MaximumSeconds, Error)
            : Manager->StartAgentNNParry(Defender->GetAgentHandle(), Attacker, Pair.Value.MaximumSeconds, Error);
        if (!Started) UE_LOG(LogTemp, Warning, TEXT("Armed defense for %s could not start: %s"), *GetNameSafe(Defender), *Error);
    }
}
}
