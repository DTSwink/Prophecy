#pragma once
#include "ProphecyNNPoseTypes.h"

// Pure snapshot math: publication prepares tangents once; animation workers only read them.
namespace ProphecyNNInterpolation
{
void Prepare(FProphecyNNPoseSnapshot& Previous, EProphecyNNInterpolationMode Mode,
    TConstArrayView<FName> Names, TConstArrayView<FTransform> A, TConstArrayView<FTransform> B,
    const FTransform& FrameA, const FTransform& FrameB, double SourceTime);
FTransform Sample(const FProphecyNNPoseSnapshot& Pose, int32 BoneIndex,
    const FTransform& A, const FTransform& B, float Alpha);
}
