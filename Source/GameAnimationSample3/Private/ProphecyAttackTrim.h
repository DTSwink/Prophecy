#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class AProphecyNNLocomotionManager;

namespace ProphecyAttackTrim
{
// Resolve only on start, family change or explicit setter; no tick or per-step lookup.
int32 TailSteps(const AProphecyAgent* Agent,FName Attack,int32 AuthoredSteps);
// Only consulted at the final policy interval, not throughout the attack.
void QueueHalfFrame(AProphecyNNLocomotionManager* Manager,AProphecyAgent* Agent,FName Attack,int32 ExpectedFrame);
void CancelHalfFrame(const AProphecyAgent* Agent);
}
