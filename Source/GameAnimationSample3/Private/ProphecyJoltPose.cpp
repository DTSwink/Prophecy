#include "ProphecyJoltPose.h"

namespace ProphecyJolt::Pose
{
namespace
{
bool PositiveScale(const FVector& Scale)
{
    return !Scale.ContainsNaN() && Scale.X > 0.0 && Scale.Y > 0.0 && Scale.Z > 0.0;
}

bool ValidTransform(const FTransform& Transform)
{
    return !Transform.ContainsNaN() && Transform.GetRotation().IsNormalized()
        && PositiveScale(Transform.GetScale3D());
}

bool RigidTransform(const FTransform& Transform)
{
    return ValidTransform(Transform) && Transform.GetScale3D().Equals(FVector::OneVector, 1.0e-6);
}

bool Fail(FString& OutError, const FString& Message)
{
    OutError = Message;
    return false;
}
}

bool ValidateLocalPose(TConstArrayView<FTransform> LocalPose, FString& OutError)
{
    OutError.Reset();
    if (LocalPose.IsEmpty()) return Fail(OutError, TEXT("Completed local pose must contain at least the root bone."));
    for (int32 Index = 0; Index < LocalPose.Num(); ++Index)
        if (!ValidTransform(LocalPose[Index]))
            return Fail(OutError, FString::Printf(TEXT("Local bone %d has a non-finite transform, unnormalized rotation or nonpositive scale."), Index));
    return true;
}

void FPreparedLayout::Reset()
{
    bPrepared = false;
    Parents.Reset(); MappingForBone.Reset(); BodyFrames.Reset();
}

bool FPreparedLayout::Build(int32 NumBones, TConstArrayView<int32> ParentIndices,
    TConstArrayView<FProphecyJoltPoseBodyMapping> BodyMappings, FString& OutError)
{
    Reset();
    OutError.Reset();
    if (NumBones <= 0)
        return Fail(OutError, TEXT("Completed local pose must contain at least the root bone."));
    if (ParentIndices.Num() != NumBones)
        return Fail(OutError, TEXT("Pose/parent counts and body mapping/state counts must match."));
    for (int32 Index = 0; Index < ParentIndices.Num(); ++Index)
        if ((Index == 0 && ParentIndices[Index] != INDEX_NONE)
            || (Index > 0 && (ParentIndices[Index] < 0 || ParentIndices[Index] >= Index)))
            return Fail(OutError, FString::Printf(TEXT("Bone %d violates the single-root, parent-before-child skeleton order."), Index));

    TArray<int32> PreparedMapping;
    PreparedMapping.Init(INDEX_NONE, NumBones);
    TArray<FBodyFrame> PreparedBodies;
    PreparedBodies.Reserve(BodyMappings.Num());
    for (int32 Index = 0; Index < BodyMappings.Num(); ++Index)
    {
        const FProphecyJoltPoseBodyMapping& Mapping = BodyMappings[Index];
        if (!PreparedMapping.IsValidIndex(Mapping.BoneIndex) || PreparedMapping[Mapping.BoneIndex] != INDEX_NONE)
            return Fail(OutError, FString::Printf(TEXT("Body mapping %d names an invalid or duplicate bone."), Index));
        if (!RigidTransform(Mapping.BodyFromBoneRigid) || !PositiveScale(Mapping.VisualScale))
            return Fail(OutError, FString::Printf(TEXT("Body mapping %d requires rigid finite body/offset frames and positive visual scale."), Index));
        PreparedMapping[Mapping.BoneIndex] = Index;
        FBodyFrame& Frame = PreparedBodies.AddDefaulted_GetRef();
        // Cache the literal original inverse operation; do not replace GetRelativeTransform with
        // multiplication by an inverse, or regroup any per-frame hierarchy operations.
        Frame.BoneFromBodyRigid = Mapping.BodyFromBoneRigid.Inverse();
        Frame.VisualScale = Mapping.VisualScale;
    }
    Parents.Append(ParentIndices.GetData(), ParentIndices.Num());
    MappingForBone = MoveTemp(PreparedMapping);
    BodyFrames = MoveTemp(PreparedBodies);
    bPrepared = true;
    return true;
}

bool FPreparedLayout::Compose(TConstArrayView<FTransform> BaseLocalPose,
    TConstArrayView<FTransform> CompletedBodyWorldTransforms, const FTransform& ComponentWorldTransform,
    FProphecyJoltComposedPose& OutPose, FString& OutError) const
{
    auto ClearOutput = [&]()
    {
        OutPose.LocalTransforms.Reset();
        OutPose.ComponentTransforms.Reset();
        OutPose.WorldTransforms.Reset();
    };
    ClearOutput();
    if (!ValidateLocalPose(BaseLocalPose, OutError)) return false;
    if (!bPrepared) return Fail(OutError, TEXT("A validated completed-pose layout must be prepared before composition."));
    if (Parents.Num() != BaseLocalPose.Num() || BodyFrames.Num() != CompletedBodyWorldTransforms.Num())
        return Fail(OutError, TEXT("Pose/parent counts and body mapping/state counts must match."));
    if (!ValidTransform(ComponentWorldTransform))
        return Fail(OutError, TEXT("Component-to-world must be finite, normalized and have positive scale."));
    for (int32 Index = 0; Index < CompletedBodyWorldTransforms.Num(); ++Index)
        if (!RigidTransform(CompletedBodyWorldTransforms[Index]))
            return Fail(OutError, FString::Printf(TEXT("Body mapping %d requires rigid finite body/offset frames and positive visual scale."), Index));

    OutPose.LocalTransforms.SetNumUninitialized(BaseLocalPose.Num());
    OutPose.ComponentTransforms.SetNumUninitialized(BaseLocalPose.Num());
    OutPose.WorldTransforms.SetNumUninitialized(BaseLocalPose.Num());
    for (int32 BoneIndex = 0; BoneIndex < BaseLocalPose.Num(); ++BoneIndex)
    {
        const int32 Parent = Parents[BoneIndex];
        const int32 MappingIndex = MappingForBone[BoneIndex];
        if (MappingIndex != INDEX_NONE)
        {
            const FBodyFrame& Mapping = BodyFrames[MappingIndex];
            FTransform BoneWorld = Mapping.BoneFromBodyRigid * CompletedBodyWorldTransforms[MappingIndex];
            BoneWorld.SetScale3D(Mapping.VisualScale);
            BoneWorld.NormalizeRotation();
            FTransform BoneComponent = BoneWorld.GetRelativeTransform(ComponentWorldTransform);
            BoneComponent.NormalizeRotation();
            FTransform BoneLocal = Parent == INDEX_NONE ? BoneComponent
                : BoneComponent.GetRelativeTransform(OutPose.ComponentTransforms[Parent]);
            BoneLocal.NormalizeRotation();
            OutPose.LocalTransforms[BoneIndex] = BoneLocal;
            OutPose.ComponentTransforms[BoneIndex] = BoneComponent;
            OutPose.WorldTransforms[BoneIndex] = BoneWorld;
        }
        else
        {
            OutPose.LocalTransforms[BoneIndex] = BaseLocalPose[BoneIndex];
            OutPose.ComponentTransforms[BoneIndex] = Parent == INDEX_NONE ? BaseLocalPose[BoneIndex]
                : BaseLocalPose[BoneIndex] * OutPose.ComponentTransforms[Parent];
            OutPose.ComponentTransforms[BoneIndex].NormalizeRotation();
            OutPose.WorldTransforms[BoneIndex] = OutPose.ComponentTransforms[BoneIndex] * ComponentWorldTransform;
            OutPose.WorldTransforms[BoneIndex].NormalizeRotation();
        }
        if (!ValidTransform(OutPose.LocalTransforms[BoneIndex]) || !ValidTransform(OutPose.ComponentTransforms[BoneIndex])
            || !ValidTransform(OutPose.WorldTransforms[BoneIndex]))
        {
            ClearOutput();
            return Fail(OutError, FString::Printf(TEXT("Composing bone %d overflowed or produced an invalid transform."), BoneIndex));
        }
    }
    return true;
}

bool ComposeCompletedPose(TConstArrayView<FTransform> BaseLocalPose, TConstArrayView<int32> ParentIndices,
    TConstArrayView<FProphecyJoltPoseBodyMapping> BodyMappings, TConstArrayView<FTransform> CompletedBodyWorldTransforms,
    const FTransform& ComponentWorldTransform, FProphecyJoltComposedPose& OutPose, FString& OutError)
{
    OutPose = {};
    if (!ValidateLocalPose(BaseLocalPose, OutError)) return false;
    if (ParentIndices.Num() != BaseLocalPose.Num() || BodyMappings.Num() != CompletedBodyWorldTransforms.Num())
        return Fail(OutError, TEXT("Pose/parent counts and body mapping/state counts must match."));
    if (!ValidTransform(ComponentWorldTransform))
        return Fail(OutError, TEXT("Component-to-world must be finite, normalized and have positive scale."));
    for (int32 Index = 0; Index < ParentIndices.Num(); ++Index)
        if ((Index == 0 && ParentIndices[Index] != INDEX_NONE)
            || (Index > 0 && (ParentIndices[Index] < 0 || ParentIndices[Index] >= Index)))
            return Fail(OutError, FString::Printf(TEXT("Bone %d violates the single-root, parent-before-child skeleton order."), Index));

    TArray<int32> MappingForBone;
    MappingForBone.Init(INDEX_NONE, BaseLocalPose.Num());
    for (int32 Index = 0; Index < BodyMappings.Num(); ++Index)
    {
        const FProphecyJoltPoseBodyMapping& Mapping = BodyMappings[Index];
        if (!MappingForBone.IsValidIndex(Mapping.BoneIndex) || MappingForBone[Mapping.BoneIndex] != INDEX_NONE)
            return Fail(OutError, FString::Printf(TEXT("Body mapping %d names an invalid or duplicate bone."), Index));
        if (!RigidTransform(Mapping.BodyFromBoneRigid) || !RigidTransform(CompletedBodyWorldTransforms[Index])
            || !PositiveScale(Mapping.VisualScale))
            return Fail(OutError, FString::Printf(TEXT("Body mapping %d requires rigid finite body/offset frames and positive visual scale."), Index));
        MappingForBone[Mapping.BoneIndex] = Index;
    }

    FProphecyJoltComposedPose Completed;
    Completed.LocalTransforms.SetNumUninitialized(BaseLocalPose.Num());
    Completed.ComponentTransforms.SetNumUninitialized(BaseLocalPose.Num());
    Completed.WorldTransforms.SetNumUninitialized(BaseLocalPose.Num());
    for (int32 BoneIndex = 0; BoneIndex < BaseLocalPose.Num(); ++BoneIndex)
    {
        const int32 Parent = ParentIndices[BoneIndex];
        const int32 MappingIndex = MappingForBone[BoneIndex];
        if (MappingIndex != INDEX_NONE)
        {
            const FProphecyJoltPoseBodyMapping& Mapping = BodyMappings[MappingIndex];
            // UE A*B applies A then B: remove body-from-bone before applying completed body-to-world.
            FTransform BoneWorld = Mapping.BodyFromBoneRigid.Inverse() * CompletedBodyWorldTransforms[MappingIndex];
            BoneWorld.SetScale3D(Mapping.VisualScale);
            BoneWorld.NormalizeRotation();
            FTransform BoneComponent = BoneWorld.GetRelativeTransform(ComponentWorldTransform);
            BoneComponent.NormalizeRotation();
            FTransform BoneLocal = Parent == INDEX_NONE ? BoneComponent
                : BoneComponent.GetRelativeTransform(Completed.ComponentTransforms[Parent]);
            BoneLocal.NormalizeRotation();
            Completed.LocalTransforms[BoneIndex] = BoneLocal;
            Completed.ComponentTransforms[BoneIndex] = BoneComponent;
            Completed.WorldTransforms[BoneIndex] = BoneWorld;
        }
        else
        {
            Completed.LocalTransforms[BoneIndex] = BaseLocalPose[BoneIndex];
            Completed.ComponentTransforms[BoneIndex] = Parent == INDEX_NONE ? BaseLocalPose[BoneIndex]
                : BaseLocalPose[BoneIndex] * Completed.ComponentTransforms[Parent];
            Completed.ComponentTransforms[BoneIndex].NormalizeRotation();
            Completed.WorldTransforms[BoneIndex] = Completed.ComponentTransforms[BoneIndex] * ComponentWorldTransform;
            Completed.WorldTransforms[BoneIndex].NormalizeRotation();
        }
        if (!ValidTransform(Completed.LocalTransforms[BoneIndex]) || !ValidTransform(Completed.ComponentTransforms[BoneIndex])
            || !ValidTransform(Completed.WorldTransforms[BoneIndex]))
            return Fail(OutError, FString::Printf(TEXT("Composing bone %d overflowed or produced an invalid transform."), BoneIndex));
    }
    OutPose = MoveTemp(Completed);
    return true;
}
}
