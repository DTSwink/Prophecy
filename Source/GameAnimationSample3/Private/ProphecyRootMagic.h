#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

namespace ProphecyRootMagic
{
struct FVelocity
{
    // Training coordinates: metres/second, Y up. Training yaw opposes UE Z yaw.
    FVector3f Linear = FVector3f::ZeroVector;
    double Yaw = 0;
};
// Cached sum of both independently configured sets. No per-step summation or extra lookup.
const FVelocity* Find(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
