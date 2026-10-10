#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecySwordHolster
{
bool InHolster(const AProphecyAgent* Agent);
bool HandTarget(const AProphecyAgent* Agent,FTransform& World);
void Remove(const AProphecyAgent* Agent);
void BeforeModeChange(AProphecyAgent* Agent,bool Kinematic);
void AfterModeChange(AProphecyAgent* Agent);
}
