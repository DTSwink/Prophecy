#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class AProphecyNNLocomotionManager;

// Waiting requests have no model state or locomotion ownership. A copy of the
// last two completed poses lets defense predict Armed itself without consuming
// the free-motion prediction for that same frame.
// Kept outside retained manager allocations so this fix can be live patched.
namespace ProphecyDefenseArmedGate
{
// Pin order: headbutt, hooks, jabs, kicks, overs, pike, left slashes, right slashes.
bool SetStartDelays(AProphecyAgent* Defender,bool Dodge,TConstArrayView<int32> Values);
void RemoveStartDelays(const AProphecyAgent* Agent);
inline int64 ArmedElapsed(int64 Tick,int64 ArmedTick) { return ArmedTick<0 ? -1 : FMath::Max<int64>(0,Tick-ArmedTick); }
bool CanStart(const AProphecyAgent* Defender,FName Family,bool Armed,bool Dodge,int64 TicksSinceArmed);
struct FHistory
{
    FTransform Pose[2][25];
    FVector3f Root[2];
    float Yaw[2]={};
    TWeakObjectPtr<const AProphecyAgent> Owner;
    bool bValid=false;
};
void Capture(AProphecyNNLocomotionManager* Manager,TFunctionRef<void(AProphecyAgent*,FHistory&)> Read);
const FHistory* ActivationHistory(const AProphecyAgent* Defender);
void Queue(AProphecyNNLocomotionManager* Manager, AProphecyAgent* Defender,
    AProphecyAgent* Attacker, bool bDodge,  float MaximumSeconds);
bool IsWaiting(const AProphecyAgent* Defender);
bool Cancel(const AProphecyAgent* Defender);
void AttackEnded(const AProphecyAgent* Attacker);
void RemoveManager(const AProphecyNNLocomotionManager* Manager);
void Advance(AProphecyNNLocomotionManager* Manager);
void SetVictim(const AProphecyAgent* Attacker,AProphecyAgent* Victim);
AProphecyAgent* GetVictim(const AProphecyAgent* Attacker);
void WaitingResponses(const AProphecyAgent* Attacker,const AProphecyAgent* Victim,bool& bParry,bool& bDodge);
void RemoveAgent(const AProphecyAgent* Agent);
}
