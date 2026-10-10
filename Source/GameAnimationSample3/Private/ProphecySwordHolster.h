#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecySwordHolster
{
bool InHolster(const AProphecyAgent* Agent);
bool HandTarget(const AProphecyAgent* Agent,FTransform& World);
void Remove(const AProphecyAgent* Agent);
}
