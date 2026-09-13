#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"

/** Indices refer to the skeletal mesh's reference skeleton, not an animation USkeleton or compact LOD pose. */
struct FProphecyJoltPoseBodyMapping
{
    int32 BoneIndex = INDEX_NONE;
    // Rigid body-origin relative to the rigid bone frame. Collision scale is already baked into the rig.
    FTransform BodyFromBoneRigid = FTransform::Identity;
    // Absolute bone world/component scale. Component-to-world is rigid in this first adapter slice.
    FVector VisualScale = FVector::OneVector;
};

/** One completed frame, with all arrays in skeletal-mesh reference-skeleton order. */
struct FProphecyJoltComposedPose
{
    TArray<FTransform> LocalTransforms;
    TArray<FTransform> ComponentTransforms;
    TArray<FTransform> WorldTransforms;
};

namespace ProphecyJolt::Pose
{
    /**
     * Owns a validated immutable skeleton/body layout. Build once when binding a rig, rebuild when its
     * parent order, body mapping, offset or visual scale changes. No UObject or native physics handles.
     * Compose retains changing-input/output validation and the original FTransform arithmetic.
     * Independent calls may share this const layout if each owns its input/output arrays.
     */
    class GAMEANIMATIONSAMPLE3_API FPreparedLayout
    {
    public:
        bool Build(int32 NumBones, TConstArrayView<int32> ParentIndices,
            TConstArrayView<FProphecyJoltPoseBodyMapping> BodyMappings, FString& OutError);
        void Reset();
        bool IsValid() const { return bPrepared; }

        // Output arrays are empty on failure; their capacity is retained for reuse. No input aliases
        // may refer into OutPose, just as with the original ComposeCompletedPose output parameter.
        bool Compose(TConstArrayView<FTransform> BaseLocalPose,
            TConstArrayView<FTransform> CompletedBodyWorldTransforms, const FTransform& ComponentWorldTransform,
            FProphecyJoltComposedPose& OutPose, FString& OutError) const;

    private:
        struct FBodyFrame
        {
            FTransform BoneFromBodyRigid;
            FVector VisualScale;
        };
        TArray<int32> Parents;
        TArray<int32> MappingForBone;
        TArray<FBodyFrame> BodyFrames;
        bool bPrepared = false;
    };

    /** No UObject/physics access. Requires finite normalized transforms and positive visual scales. */
    GAMEANIMATIONSAMPLE3_API bool ValidateLocalPose(TConstArrayView<FTransform> LocalPose, FString& OutError);

    /**
     * Compose an immutable completed physical frame. BodyMappings and CompletedBodyWorldTransforms
     * correspond by array index; mappings can be in any order and cannot repeat a bone. ParentIndices
     * require one root at index zero and parent-before-child order. Unmapped bones retain their supplied
     * authored/reference local transforms (including fingers/helpers). Body/world/component frames are
     * rigid; visual scale is applied to bones only. No physics state or input array is modified.
     * All outputs are empty on failure. UE skeletal FTransform composition semantics are retained.
     */
    GAMEANIMATIONSAMPLE3_API bool ComposeCompletedPose(
        TConstArrayView<FTransform> BaseLocalPose,
        TConstArrayView<int32> ParentIndices,
        TConstArrayView<FProphecyJoltPoseBodyMapping> BodyMappings,
        TConstArrayView<FTransform> CompletedBodyWorldTransforms,
        const FTransform& ComponentWorldTransform,
        FProphecyJoltComposedPose& OutPose,
        FString& OutError);
}
