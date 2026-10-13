#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class UPrimitiveComponent;
struct FProphecyJoltBodyHandle;
namespace ProphecySwordHolster
{
bool InHolster(const AProphecyAgent* Agent);
bool IsPhysicsDriven(const UPrimitiveComponent* Source,const FProphecyJoltBodyHandle& Body);
bool FollowsAttachment(const UPrimitiveComponent* Source);
bool PhysicsTarget(const UPrimitiveComponent* Source,const FProphecyJoltBodyHandle& Body,FTransform& World);
void Remove(const AProphecyAgent* Agent);
void BeforeModeChange(AProphecyAgent* Agent,bool Kinematic);
void AfterModeChange(AProphecyAgent* Agent);
}
