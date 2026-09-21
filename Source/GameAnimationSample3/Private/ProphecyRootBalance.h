#pragma once
#include "CoreMinimal.h"
#include "prophecy/sim/locomotion.h"
class AProphecyAgent;
namespace ProphecyRootBalance
{
// Same physical/visible-foot selection as balancing, independent of its enable/speed gates.
bool GetFlatFeetTarget(const AProphecyAgent* Agent,FVector& Target);
// Effective target, including a configured post-kick pelvis hold/return.
bool GetTarget(const AProphecyAgent* Agent,FVector& Target);
void BeginKickException(const AProphecyAgent* Agent,FName Attack,bool ReturningToLocomotion);
void CancelKickException(const AProphecyAgent* Agent);
// Sample once per real policy step. The same snapshot drives prediction and movement.
const prophecy::sim::RootBalanceSpring* Prepare(const AProphecyAgent* Agent, const prophecy::sim::LocomotionState& Mover,
    const prophecy::sim::LocomotionIntent& Intent, bool bAllowed);
const prophecy::sim::RootBalanceSpring* GetPrepared(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void ResetMotion(const AProphecyAgent* Agent);
}
