#pragma once
#include "CoreMinimal.h"

namespace ProphecyContinuousRootWindow
{
// Input [previous, current, future1..8]. Presentation is previous -> current,
// NOT current -> future1: using that segment would lead the displayed character.
inline void Resample(TArray<FTransform>& Roots, TArray<float>& Times,
    float Alpha, float StepSeconds, const FTransform& AppliedRoot)
{
    check(Roots.Num() == 10);
    Alpha = FMath::Clamp(Alpha, 0.f, 1.f);
    auto Sample = [Alpha](const FTransform& A, const FTransform& B)
    {
        return FTransform(FQuat::Slerp(A.GetRotation(), B.GetRotation(), Alpha),
            FMath::Lerp(A.GetLocation(), B.GetLocation(), double(Alpha)));
    };
    const FTransform Origin = Sample(Roots[0], Roots[1]);
    // All root transforms have unit scale. Compute the common rigid correction
    // once instead of an inverse/relative-transform operation for every sample.
    const FQuat Correction = AppliedRoot.GetRotation() * Origin.GetRotation().Inverse();
    Times.SetNum(9, EAllowShrinking::No);
    for (int32 I = 1; I < 9; ++I)
    {
        // Ascending writes preserve the next pair of input samples. The last
        // pair stays within the known horizon; no tail extrapolation needed.
        const FTransform Interpolated = Sample(Roots[I], Roots[I + 1]);
        Roots[I] = FTransform(Correction * Interpolated.GetRotation(), AppliedRoot.GetLocation()
            + Correction.RotateVector(Interpolated.GetLocation() - Origin.GetLocation()));
        Times[I] = I * StepSeconds;
    }
    Roots.SetNum(9, EAllowShrinking::No);
    Roots[0] = AppliedRoot;
    Times[0] = 0.f;
}
}
