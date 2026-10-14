#pragma once
#include "CoreMinimal.h"
class UWorld;
class UPhysicsConstraintComponent;
struct FProphecyJoltJointHandle;
namespace ProphecyJolt::Constraints
{
void Enable(UWorld* World);
void Disable(UWorld* World);
void Prepare(UWorld* World);
void Finish(UWorld* World);
// Temporarily retire a joint without redefining its authored frames or drives.
void SetSuspended(UPhysicsConstraintComponent* Component,bool Suspended);
bool GetJoint(UPhysicsConstraintComponent* Component, FProphecyJoltJointHandle& Joint, FString& Error);
bool ReadReaction(UPhysicsConstraintComponent* Component, FVector& Force, FVector& Torque);
bool ReadRotation(UPhysicsConstraintComponent* Component, FQuat& Relative);
}
