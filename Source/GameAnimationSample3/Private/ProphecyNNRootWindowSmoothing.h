#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

namespace ProphecyNNRootWindow
{
constexpr int32 Count = 8;
struct FSample
{
    double Distance = 0, Direction = 0, Orientation = 0;
    bool bInitialized = false;
    FVector Filter(FVector Offset, double& Yaw, const FVector& Factors)
    {
        const double Length = Offset.Size2D();
        const double Heading = Length > UE_SMALL_NUMBER ? FMath::Atan2(Offset.Y, Offset.X) : (bInitialized ? Direction : Yaw);
        if (!bInitialized)
        {
            Distance = Length; Direction = Heading; Orientation = Yaw; bInitialized = true;
            return Offset;
        }
        Distance = FMath::Lerp(Distance, Length, Factors.X);
        Direction += FMath::FindDeltaAngleRadians(Direction, Heading) * Factors.Y;
        Orientation += FMath::FindDeltaAngleRadians(Orientation, Yaw) * Factors.Z;
        // Preserve the incoming value exactly for unrestricted channels.
        if (Factors.Z < 1.) Yaw = Orientation;
        else Orientation = Yaw;
        if (Factors.X == 1. && Factors.Y == 1.) return Offset;
        return FVector(Distance * FMath::Cos(Direction), Distance * FMath::Sin(Direction), Offset.Z);
    }
};
struct FState
{
    FVector Factors = FVector::OneVector;
    FSample Samples[Count];
    // Filtered root1 relative to root0, in training coordinates. Both movement and pose rebasing consume it.
    FVector3f ActualNextRootLocal = FVector3f::ZeroVector;
    float ActualNextYaw = 0;
};
FState* Find(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
