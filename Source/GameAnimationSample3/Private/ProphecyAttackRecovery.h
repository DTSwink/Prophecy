#pragma once
#include "ProphecyNNPolicyBlend.h"

namespace ProphecyAttackRecovery
{
void Begin(const AProphecyAgent* Agent);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
// True owns selection for this policy step, including the exact walk endpoint.
bool Step(const AProphecyAgent* Agent, FProphecyNNPolicyBlend& Blend, bool& bWalk, float Dt);
}
