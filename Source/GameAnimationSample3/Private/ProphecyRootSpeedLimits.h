#pragma once
#include "CoreMinimal.h"
#include "ProphecyRootMagic.h"
class AProphecyAgent;
namespace ProphecyRootSpeedLimits
{
struct FSettings
{
    double Linear = 10000.; // training metres/s
    double Angular = FMath::DegreesToRadians(1000000.);
    bool bClamped = false;
    double NextYawDelta = 0.;
    ProphecyRootMagic::FVelocity AppliedMagic;
};
FSettings* Find(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
// One scale for each channel preserves the predicted path's shape and vertical time convention.
// Every adjacent sample, including root0 -> root1, must satisfy the configured speeds.
void LimitWindow(FSettings& Settings, float* EncodedWindow, const double* UnwrappedYaw,
    int32 Count, float PositionScale, float StepSeconds, const ProphecyRootMagic::FVelocity* Magic,
    float& VerticalVelocity);
}
