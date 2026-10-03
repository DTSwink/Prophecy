#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackEndExtension
{
// Only queried at the existing end boundary, never on ordinary locomotion/attack steps.
bool Threshold(const AProphecyAgent* Agent,FName Attack,float& Degrees,bool& Sword,bool& Left);
}
