#pragma once
#include "CoreMinimal.h"

inline bool ProphecySelectWalkCheckpoint(bool bRun, double VelocityX, double VelocityZ, float ThresholdCmPerSecond)
{
    if (!bRun) return true;
    if (ThresholdCmPerSecond < 0.f) return false;
    const double ThresholdM = double(ThresholdCmPerSecond) * .01;
    return VelocityX * VelocityX + VelocityZ * VelocityZ < ThresholdM * ThresholdM;
}

// NN-step clock. Reversals start at the current mixture instead of jumping endpoints.
struct FProphecyNNPolicyBlend
{
    float WalkWeight = 1.f;
    float StartWeight = 1.f;
    float Elapsed = 0.f;
    float Duration = 0.f;
    bool bTargetWalk = true;

    bool IsActive() const { return Duration > 0.f; }
    void Reset(bool bWalk)
    {
        WalkWeight = StartWeight = bWalk ? 1.f : 0.f;
        bTargetWalk = bWalk;
        Elapsed = Duration = 0.f;
    }
    void Step(bool bWalk, float WalkToRun, float RunToWalk, float Dt)
    {
        const float Requested = bWalk ? RunToWalk : WalkToRun;
        if (Requested <= 0.f) { Reset(bWalk); return; }
        if (bWalk != bTargetWalk)
        {
            bTargetWalk = bWalk;
            StartWeight = WalkWeight;
            Elapsed = 0.f;
            Duration = Requested;
        }
        if (!IsActive()) return;
        Elapsed += Dt;
        if (Elapsed + UE_SMALL_NUMBER >= Duration) { Reset(bWalk); return; }
        const float T = FMath::Clamp(Elapsed / Duration, 0.f, 1.f);
        WalkWeight = FMath::Lerp(StartWeight, bWalk ? 1.f : 0.f, T * T * (3.f - 2.f * T));
    }
};
