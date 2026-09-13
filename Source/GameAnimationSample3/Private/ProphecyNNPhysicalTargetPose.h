#pragma once

#include "CoreMinimal.h"

class UPhysicsAsset;
class USkeletalMesh;
struct FReferenceSkeleton;
struct FProphecyNNPoseSnapshot;

namespace ProphecyNNPhysicalTargets
{
// Index data only: no cached transforms or retained assets. Exposed here for the independent oracle tests.
class FLayout
{
public:
    bool HasSourceLayout(TConstArrayView<FName> Names) const;
    // True when indices were rebuilt. Ref-pose values deliberately do not invalidate index data.
    bool Update(const FReferenceSkeleton& Reference, TConstArrayView<FName> BodyNames,
        TConstArrayView<FName> SourceNames);
    bool Evaluate(const FReferenceSkeleton& Reference, const FProphecyNNPoseSnapshot& Pose,
        TArray<FName>& OutNames, TArray<FTransform>& OutFuture, TArray<FTransform>& OutPrevious) const;
    int32 GetEvaluatedBoneCount() const { return NeededBones.Num(); }

private:
    TArray<FName> ReferenceNames, InputBodyNames, InputSourceNames, TargetNames;
    TArray<int32> Parents, SourceIndices, NeededBones, TargetIndices;
    bool bInitialized = false;
};

// Game-thread only. OutPrevious is intentionally not interpolated: the caller retains its existing
// BlendAuthoredWorldTransform and ApplyRigidForearms, including their exact arithmetic and ordering.
bool BuildWorldPoses(const USkeletalMesh& Mesh, const UPhysicsAsset& PhysicsAsset,
    const FProphecyNNPoseSnapshot& Pose, TArray<FName>& OutNames,
    TArray<FTransform>& OutFuture, TArray<FTransform>& OutPrevious);
}
