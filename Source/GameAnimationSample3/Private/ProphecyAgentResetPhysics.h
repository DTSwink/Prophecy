#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAgentResetPhysics
{
bool Capture(AProphecyAgent* Agent,FString& Error);
bool Has(const AProphecyAgent* Agent);
void CancelBlends(AProphecyAgent* Agent);
bool Restore(AProphecyAgent* Agent,FString& Error);
bool RestoreLimits(AProphecyAgent* Agent,FString& Error);
bool RestoreEquipment(AProphecyAgent* Agent,FString& Error);
void Remove(const AProphecyAgent* Agent);
}
