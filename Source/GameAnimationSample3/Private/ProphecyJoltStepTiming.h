#pragma once

#include "CoreMinimal.h"
#include "PhysicsEngine/PhysicsSettings.h"

namespace ProphecyJolt::StepTiming
{
// Jolt divides the frame evenly. The configured maximum is not the duration
// of each step (a frame just over the maximum is split into two half steps).
inline int32 Count(float FrameSeconds, bool bSubstepping, float MaximumSeconds, int32 MaximumSteps)
{
    if (!bSubstepping || MaximumSeconds <= 0.0f) return 1;
    return int32(FMath::Clamp(FMath::CeilToDouble(double(FrameSeconds) / double(MaximumSeconds)),
        1.0, double(FMath::Max(1, MaximumSteps))));
}

inline int32 Count(float FrameSeconds, const UPhysicsSettings* Settings)
{
    return Settings ? Count(FrameSeconds, Settings->bSubstepping, Settings->MaxSubstepDeltaTime,
        Settings->MaxSubsteps) : 1;
}

inline float Duration(float FrameSeconds, const UPhysicsSettings* Settings)
{
    return FMath::Max(UE_SMALL_NUMBER, FrameSeconds / float(Count(FrameSeconds, Settings)));
}
}
