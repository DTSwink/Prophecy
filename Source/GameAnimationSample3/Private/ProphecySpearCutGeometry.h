#pragma once
#include "CoreMinimal.h"

namespace ProphecySpearCut
{
// Wound travel is measured from the blade root in the weapon's +Z frame.
// The rear must clear the target's far face, not merely the tip or blade root.
inline double ForwardExit(double RearLocalZ, double ScaleZ, double BladeRootCm, double ThicknessCm)
{
    return RearLocalZ * ScaleZ - BladeRootCm - ThicknessCm;
}
inline bool Cleared(double WoundZ, double BladeLength, bool PassThrough, double ForwardExitZ)
{
    constexpr double ClearanceCm = .05;
    return WoundZ > BladeLength + ClearanceCm
        || (PassThrough && WoundZ < ForwardExitZ - ClearanceCm);
}
}
