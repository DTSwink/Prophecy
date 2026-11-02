#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyFootIK
{
bool AnyActive();
bool HasCallbacks();
bool Active(const AProphecyAgent* Agent);
void Remove(AProphecyAgent* Agent);
bool Root(AProphecyAgent* Agent,FVector& Position,float& Yaw,FVector* Velocity=nullptr);
bool History(AProphecyAgent* Agent,FVector& PreviousPosition,float& PreviousYaw);
bool Apply(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,
    const FTransform& ComponentWorld);
}
