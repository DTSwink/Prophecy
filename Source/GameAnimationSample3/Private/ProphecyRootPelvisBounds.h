#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class AProphecyNNLocomotionManager;

namespace ProphecyRootPelvisBounds
{
// Returns the minimum planar correction only when outside the circle.
inline bool ClampLocation(const FVector& Root, const FVector& Pelvis, double RadiusCm, FVector& OutRoot)
{
    OutRoot = Root;
    if (Root.ContainsNaN() || Pelvis.ContainsNaN() || !FMath::IsFinite(RadiusCm) || RadiusCm < 0.) return false;
    const FVector Offset(Root.X - Pelvis.X, Root.Y - Pelvis.Y, 0.);
    const double DistanceSquared = Offset.SizeSquared();
    if (!FMath::IsFinite(DistanceSquared) || DistanceSquared <= FMath::Square(RadiusCm)) return false;
    const double Scale = RadiusCm / FMath::Sqrt(DistanceSquared);
    OutRoot.X = Pelvis.X + Offset.X * Scale;
    OutRoot.Y = Pelvis.Y + Offset.Y * Scale;
    return true;
}
void Apply(AProphecyNNLocomotionManager& Manager);
void Remove(const AProphecyAgent* Agent);
}
