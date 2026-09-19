#pragma once

#include "CoreMinimal.h"
#include "PhysicsEngine/PhysicsSettings.h"
class UWorld;

namespace ProphecyJolt::StepTiming
{
int32 MinimumSubsteps(const UWorld* World);
void RemoveOverride(const UWorld* World);
// Jolt divides the frame evenly. The configured maximum is not the duration
// of each step (a frame just over the maximum is split into two half steps).
inline int32 Count(float FrameSeconds, bool bSubstepping, float MaximumSeconds, int32 MaximumSteps)
{
    if (!bSubstepping || MaximumSeconds <= 0.0f) return 1;
    return int32(FMath::Clamp(FMath::CeilToDouble(double(FrameSeconds) / double(MaximumSeconds)),
        1.0, double(FMath::Max(1, MaximumSteps))));
}

inline int32 Count(float FrameSeconds, const UPhysicsSettings* Settings, const UWorld* World = nullptr)
{
    const int32 Base = Settings ? Count(FrameSeconds, Settings->bSubstepping, Settings->MaxSubstepDeltaTime,
        Settings->MaxSubsteps) : 1;
    return World ? FMath::Max(Base, MinimumSubsteps(World)) : Base;
}

inline float Duration(float FrameSeconds, const UPhysicsSettings* Settings, const UWorld* World = nullptr)
{
    return FMath::Max(UE_SMALL_NUMBER, FrameSeconds / float(Count(FrameSeconds, Settings, World)));
}
}
