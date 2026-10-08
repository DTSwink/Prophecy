#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackFootLocomotion
{
// Family edits must not carry a kick-only displacement into a punch or slash.
void RetargetGhostInertia(const AProphecyAgent* Agent,FName Attack);
}
