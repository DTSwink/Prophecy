#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyDefenseCollision
{
void Start(AProphecyAgent* Defender,AProphecyAgent* Attacker,FName Family,bool Dodge);
void Stop(const AProphecyAgent* Defender);
void Remove(const AProphecyAgent* Agent);
void Refresh(AProphecyAgent* Agent);
bool BlocksSlashSwordNoReaction(const AProphecyAgent* Attacker);
}
