#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class UWorld;
class UPrimitiveComponent;
struct FProphecyJoltBodyHandle;
namespace ProphecySwordHolster
{
bool InHolster(const AProphecyAgent* Agent);
bool FollowsAttachment(const UPrimitiveComponent* Source);
bool HasKinematicArm(const AProphecyAgent* Agent);
bool CompleteAttachedArms(UWorld* World,float DeltaSeconds,FString& Error);
void Remove(const AProphecyAgent* Agent);
bool BeforeModeChange(AProphecyAgent* Agent,bool Kinematic);
void AfterModeChange(AProphecyAgent* Agent);
}
