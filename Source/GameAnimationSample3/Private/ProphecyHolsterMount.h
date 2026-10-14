#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class UPrimitiveComponent;
namespace ProphecyHolsterMount
{
void Capture(AProphecyAgent* Agent,UPrimitiveComponent* Holster,const FTransform& Rest,bool Simulated);
bool SetSimulated(AProphecyAgent* Agent,bool Simulated,float ReturnDuration);
bool BeginGrip(AProphecyAgent* Agent,float ReturnDuration);
void EndGrip(AProphecyAgent* Agent);
void BeforeAgentModeChange(AProphecyAgent* Agent,bool Kinematic,float ReturnDuration);
void AfterAgentModeChange(AProphecyAgent* Agent);
bool OwnsReturn(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
