#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyBodyflip
{
bool AnyActive();
bool Active(const AProphecyAgent* Agent);
bool Apply(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,
    const FTransform& ComponentWorld,double SourceTime);
// The posed-body carrier owns contact; the upright locomotion capsule must not
// create an earlier airborne landing. The manager applies this root without sweep.
bool Root(AProphecyAgent* Agent,FVector& WorldLowPoint,float& WorldYaw,FVector* Velocity=nullptr);
// Exact carrier history at t - 1/30 s, matching Apply's previous pose.
bool History(AProphecyAgent* Agent,FVector& PreviousWorldLowPoint,float& PreviousWorldYaw);
}
