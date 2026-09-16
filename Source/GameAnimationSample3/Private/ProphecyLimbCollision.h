#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
struct FProphecyJoltBodyHandle;
namespace ProphecyLimbCollision
{
bool Update(AProphecyAgent* Agent,const FProphecyJoltBodyHandle& RigBody,FString& Error);
void Invalidate(AProphecyAgent* Agent);
void DefenseChanged(AProphecyAgent* Agent,bool bActive);
void Remove(const AProphecyAgent* Agent);
}
