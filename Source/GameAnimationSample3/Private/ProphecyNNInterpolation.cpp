#include "ProphecyNNInterpolation.h"

namespace ProphecyNNInterpolation
{
namespace
{
void LimitTangents(const FVector& Delta, FVector& Start, FVector& End)
{
    for (int32 Axis = 0; Axis < 3; ++Axis)
    {
        const double D = Delta[Axis];
        if (FMath::Abs(D) < 1.e-8) { Start[Axis] = End[Axis] = 0; continue; }
        double A = FMath::IsFinite(Start[Axis]) ? FMath::Max(0., Start[Axis] / D) : 1.;
        double B = FMath::IsFinite(End[Axis]) ? FMath::Max(0., End[Axis] / D) : 1.;
        // Ordered Bezier control points: each coordinate stays within its endpoint range.
        const double Scale = A + B > 3. ? 3. / (A + B) : 1.;
        Start[Axis] = A * Scale * D;
        End[Axis] = B * Scale * D;
    }
}
}

void Prepare(FProphecyNNPoseSnapshot& Previous, EProphecyNNInterpolationMode Mode,
    TConstArrayView<FName> Names, TConstArrayView<FTransform> A, TConstArrayView<FTransform> B,
    const FTransform& FrameA, const FTransform& FrameB, double SourceTime)
{
    if (Mode != EProphecyNNInterpolationMode::HermiteSlerp)
    {
        Previous.InterpolationMode = EProphecyNNInterpolationMode::Current;
        Previous.InterpolationStartTangents.Empty();
        Previous.InterpolationEndTangents.Empty();
        Previous.InterpolationIntervalSeconds = 0;
        return;
    }
    bool bLayoutMatches = Names.Num() == Previous.BoneNames.Num();
    for (int32 I = 0; bLayoutMatches && I < Names.Num(); ++I) bLayoutMatches = Names[I] == Previous.BoneNames[I];
    const bool bHadCurves = Previous.InterpolationMode == Mode && bLayoutMatches
        && Previous.InterpolationEndTangents.Num() == Names.Num()
        && Previous.ComponentTransforms.Num() == Names.Num()
        && Previous.PreviousComponentTransforms.Num() == Names.Num();
    const double Dt = SourceTime - Previous.SourceTimeSeconds;
    if (bHadCurves && Dt == 0)
    {
        // Root handoff can republish the same world endpoints in different carrier coordinates.
        bool bSameWorld = true;
        for (int32 I = 0; bSameWorld && I < Names.Num(); ++I)
            bSameWorld = (A[I] * FrameA).GetLocation().Equals(
                (Previous.PreviousComponentTransforms[I] * Previous.PreviousComponentWorldTransform).GetLocation(), .001)
                && (B[I] * FrameB).GetLocation().Equals(
                (Previous.ComponentTransforms[I] * Previous.ComponentWorldTransform).GetLocation(), .001);
        if (bSameWorld) return;
    }
    const bool bHasHistory = bHadCurves && Dt > 0 && Previous.InterpolationIntervalSeconds > 0
        && Dt <= 4 * Previous.InterpolationIntervalSeconds;
    Previous.InterpolationStartTangents.SetNum(Names.Num());
    Previous.InterpolationEndTangents.SetNum(Names.Num());
    for (int32 I = 0; I < Names.Num(); ++I)
    {
        const FVector StartPosition = (A[I] * FrameA).GetLocation();
        const FVector Delta = (B[I] * FrameB).GetLocation() - StartPosition;
        FVector Start = Delta, End = Delta; // New mode/layout/discontinuity starts with a straight segment.
        if (bHasHistory && StartPosition.Equals(
            (Previous.ComponentTransforms[I] * Previous.ComponentWorldTransform).GetLocation(), .001))
        {
            const double Ratio = Dt / Previous.InterpolationIntervalSeconds;
            Start = Previous.InterpolationEndTangents[I] * Ratio;
            const FVector PreviousDelta = (Previous.ComponentTransforms[I] * Previous.ComponentWorldTransform).GetLocation()
                - (Previous.PreviousComponentTransforms[I] * Previous.PreviousComponentWorldTransform).GetLocation();
            End = .5 * (Delta + PreviousDelta * Ratio);
        }
        LimitTangents(Delta, Start, End);
        Previous.InterpolationStartTangents[I] = Start;
        Previous.InterpolationEndTangents[I] = End;
    }
    Previous.InterpolationMode = Mode;
    Previous.InterpolationIntervalSeconds = Dt > 0 ? Dt : 0;
}

FTransform Sample(const FProphecyNNPoseSnapshot& Pose, int32 BoneIndex,
    const FTransform& A, const FTransform& B, float Alpha)
{
    if (Alpha <= 0) return A;
    if (Alpha >= 1) return B;
    FVector Position = FMath::Lerp(A.GetLocation(), B.GetLocation(), Alpha);
    if (Pose.InterpolationStartTangents.IsValidIndex(BoneIndex) && Pose.InterpolationEndTangents.IsValidIndex(BoneIndex))
        Position = FMath::CubicInterp(A.GetLocation(), Pose.InterpolationStartTangents[BoneIndex],
            B.GetLocation(), Pose.InterpolationEndTangents[BoneIndex], double(Alpha));
    return FTransform(FQuat::Slerp(A.GetRotation(), B.GetRotation(), Alpha).GetNormalized(),
        Position, FMath::Lerp(A.GetScale3D(), B.GetScale3D(), Alpha));
}
}
