#pragma once

#include "ProphecyJoltPose.h"

namespace ProphecyJolt::Pose
{
// Plain data only. The GT owner keeps all input views, layouts and distinct output buffers alive and
// immutable for the duration of ComposeBatch. The function joins every worker before returning.
struct FComposeBatchItem
{
    const FPreparedLayout* Layout = nullptr;
    TConstArrayView<FTransform> BaseLocal;
    TConstArrayView<FTransform> BodyWorld;
    FTransform ComponentWorld = FTransform::Identity;
    FProphecyJoltComposedPose* Output = nullptr;
    FString Error;
    bool bSucceeded = false;
};

// Never accesses UObjects, physics, delegates, or the GT-only character profiler.
// The force-single option is an oracle/test path, not a gameplay quality or cadence setting.
void ComposeBatch(TArrayView<FComposeBatchItem> Items, bool bForceSingleThread = false);
}
