#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
struct FProphecyJoltBodyHandle;

namespace ProphecyJointDamping
{
// Called by the existing pre-physics coordinator; no additional tick or subsystem.
bool Update(AProphecyAgent* Agent,const FProphecyJoltBodyHandle& RigBody,FString& Error);
void Remove(const AProphecyAgent* Agent);
}
