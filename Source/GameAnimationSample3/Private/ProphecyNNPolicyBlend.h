#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
// Physical-profile selection follows the checkpoint driving that physical limb.
inline float ProphecyBodyPolicyWalkWeight(FName Bone,float Pelvis,const FVector2f& Legs)
{
    if (Legs.X==Pelvis && Legs.Y==Pelvis) return Pelvis;
    static const FName Left[]={TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l")};
    static const FName Right[]={TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
    for (const auto Name:Left) if (Bone==Name) return Legs.X;
    for (const auto Name:Right) if (Bone==Name) return Legs.Y;
    return Pelvis;
}
namespace ProphecyAutoRun
{
float Threshold(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
inline bool Above(double RootSpeedSquaredM, float ThresholdCm)
{
    return RootSpeedSquaredM > FMath::Square(double(ThresholdCm) * .01);
}
}

inline bool ProphecySelectWalkCheckpoint(bool bRun, double VelocityX, double VelocityZ, float ThresholdCmPerSecond)
{
    if (!bRun) return true;
    if (ThresholdCmPerSecond < 0.f) return false;
    const double ThresholdM = double(ThresholdCmPerSecond) * .01;
    return VelocityX * VelocityX + VelocityZ * VelocityZ < ThresholdM * ThresholdM;
}

// Dt is supplied by the active 60-tick blend clock (not NN or world delta time).
// Reversals start at the current mixture instead of jumping endpoints.
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
        if (Elapsed + 1.e-6f >= Duration) { Reset(bWalk); return; }
        const float T = FMath::Clamp(Elapsed / Duration, 0.f, 1.f);
        WalkWeight = FMath::Lerp(StartWeight, bWalk ? 1.f : 0.f, T * T * (3.f - 2.f * T));
    }
};
