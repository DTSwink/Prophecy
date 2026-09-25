#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

// Event-driven attack collision phase: held sword channels/owner pairs and Jolt
// body self-collision until first Hit. Does not alter NN conditioning geometry.
namespace ProphecySwordAttackCollision
{
void Begin(AProphecyAgent* Agent,FName Family);
void RetargetFamily(AProphecyAgent* Agent,FName Family,bool bArmed,bool bHit);
void Armed(AProphecyAgent* Agent);
void Hit(AProphecyAgent* Agent);
void End(AProphecyAgent* Agent);
void Refresh(AProphecyAgent* Agent);
void ReleaseSword(AProphecyAgent* Agent);
bool SuppressesOwner(const AProphecyAgent* Agent);
bool IsAllowed(const AProphecyAgent* Agent);
}
