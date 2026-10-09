#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

// Event-driven attack collision phase: held sword channels/owner pairs and Jolt
// body self-collision until first Hit. Does not alter NN conditioning geometry.
namespace ProphecySwordAttackCollision
{
void Begin(AProphecyAgent* Agent,FName Family,int64 EntryTicks=-1);
void RetargetFamily(AProphecyAgent* Agent,FName Family,bool bArmed,bool bHit);
void Armed(AProphecyAgent* Agent);
void Hit(AProphecyAgent* Agent);
void End(AProphecyAgent* Agent);
void Refresh(AProphecyAgent* Agent);
void ReleaseSword(AProphecyAgent* Agent);
void CancelCooldown(AProphecyAgent* Agent);
bool SuppressesOwner(const AProphecyAgent* Agent);
bool IsAllowed(const AProphecyAgent* Agent);
}

namespace ProphecySwordNoReaction
{
// Existing attack/defense transitions call these; no new tick subscription.
void DefenseChanged();
void VictimChanged(AProphecyAgent* Agent);
}
