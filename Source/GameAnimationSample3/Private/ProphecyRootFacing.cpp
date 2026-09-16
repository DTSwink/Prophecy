#include "ProphecyRootFacing.h"
#include "ProphecyAgent.h"

namespace ProphecyRootFacing
{
// Optional, separate storage: no changes to retained live UObject/FImpl layouts.
static TSet<TWeakObjectPtr<const AProphecyAgent>> ImpulseOwners;
void Impulse(const AProphecyAgent* Agent) { ImpulseOwners.Add(Agent); }
void Explicit(const AProphecyAgent* Agent)
{ if (!ImpulseOwners.IsEmpty()) ImpulseOwners.Remove(Agent); }
bool IsImpulseOwned(const AProphecyAgent* Agent)
{ return !ImpulseOwners.IsEmpty() && ImpulseOwners.Contains(Agent); }
}
