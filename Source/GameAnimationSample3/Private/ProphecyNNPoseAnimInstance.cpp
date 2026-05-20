#include "ProphecyNNPoseAnimInstance.h"

#include "ProphecyNNPoseTypes.h"

#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeBase.h"
#include "BoneContainer.h"
#include "BonePose.h"

namespace
{
	FCompactPoseBoneIndex ResolveCompactBoneIndex(const FBoneContainer& RequiredBones, FName BoneName)
	{
		if (BoneName.IsNone())
		{
			return FCompactPoseBoneIndex(INDEX_NONE);
		}

		const int32 SkeletonIndex = RequiredBones.GetReferenceSkeleton().FindBoneIndex(BoneName);
		if (SkeletonIndex == INDEX_NONE)
		{
			return FCompactPoseBoneIndex(INDEX_NONE);
		}

		return RequiredBones.GetCompactPoseIndexFromSkeletonIndex(SkeletonIndex);
	}
}

class FProphecyNNPoseAnimInstanceProxy final : public FAnimInstanceProxy
{
public:
	FProphecyNNPoseAnimInstanceProxy() = default;

	explicit FProphecyNNPoseAnimInstanceProxy(UAnimInstance* Instance)
		: FAnimInstanceProxy(Instance)
	{
	}

protected:
	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override
	{
		FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);

		const UProphecyNNPoseAnimInstance* PoseInstance = Cast<UProphecyNNPoseAnimInstance>(InAnimInstance);
		if (!PoseInstance)
		{
			return;
		}

		AgentId = PoseInstance->AgentId;
		bUseStoredPose = PoseInstance->bUseStoredPose;
		bEnableDebugMotion = PoseInstance->bEnableDebugMotion;
		DebugBoneName = PoseInstance->DebugBoneName;
		DebugMotionDegrees = PoseInstance->DebugMotionDegrees;
		DebugMotionHz = PoseInstance->DebugMotionHz;

		DebugPhase = FMath::Fmod(DebugPhase + DeltaSeconds * FMath::Max(0.0f, DebugMotionHz), 1.0f);

		bHasStoredPose = bUseStoredPose && FProphecyNNPoseStore::GetAgentLocalPose(AgentId, StoredPose);
		if (!bHasStoredPose)
		{
			StoredPose.Reset();
			bCachedCompactIndicesValid = false;
		}
	}

	virtual bool Evaluate(FPoseContext& Output) override
	{
		Output.ResetToRefPose();

		if (bHasStoredPose)
		{
			ApplyStoredPose(Output);
		}
		else if (bEnableDebugMotion)
		{
			ApplyDebugMotion(Output);
		}

		Output.Pose.NormalizeRotations();
		return true;
	}

private:
	void RebuildCompactIndexCache(const FBoneContainer& InRequiredBones)
	{
		CachedCompactIndices.Reset(StoredPose.BoneNames.Num());
		CachedCompactIndices.AddUninitialized(StoredPose.BoneNames.Num());

		for (int32 Index = 0; Index < StoredPose.BoneNames.Num(); ++Index)
		{
			CachedCompactIndices[Index] = ResolveCompactBoneIndex(InRequiredBones, StoredPose.BoneNames[Index]);
		}

		CachedBoneContainerSerial = InRequiredBones.GetSerialNumber();
		CachedPoseRevision = StoredPose.Revision;
		bCachedCompactIndicesValid = true;
	}

	void ApplyStoredPose(FPoseContext& Output)
	{
		if (!StoredPose.IsValid())
		{
			return;
		}

		const FBoneContainer& OutputRequiredBones = Output.Pose.GetBoneContainer();
		const bool bCacheStale =
			!bCachedCompactIndicesValid ||
			CachedPoseRevision != StoredPose.Revision ||
			CachedBoneContainerSerial != OutputRequiredBones.GetSerialNumber() ||
			CachedCompactIndices.Num() != StoredPose.LocalTransforms.Num();

		if (bCacheStale)
		{
			RebuildCompactIndexCache(OutputRequiredBones);
		}

		for (int32 Index = 0; Index < StoredPose.LocalTransforms.Num(); ++Index)
		{
			const FCompactPoseBoneIndex CompactIndex = CachedCompactIndices[Index];
			if (CompactIndex.IsValid() && Output.Pose.IsValidIndex(CompactIndex))
			{
				Output.Pose[CompactIndex] = StoredPose.LocalTransforms[Index];
			}
		}
	}

	void ApplyDebugMotion(FPoseContext& Output) const
	{
		const FBoneContainer& OutputRequiredBones = Output.Pose.GetBoneContainer();
		FCompactPoseBoneIndex CompactIndex = ResolveCompactBoneIndex(OutputRequiredBones, DebugBoneName);

		if (!CompactIndex.IsValid() || !Output.Pose.IsValidIndex(CompactIndex))
		{
			CompactIndex = ResolveCompactBoneIndex(OutputRequiredBones, TEXT("pelvis"));
		}

		if (!CompactIndex.IsValid() || !Output.Pose.IsValidIndex(CompactIndex))
		{
			return;
		}

		const float AngleRadians = FMath::DegreesToRadians(FMath::Sin(DebugPhase * UE_TWO_PI) * DebugMotionDegrees);
		const FQuat DebugRotation(FVector::RightVector, AngleRadians);
		FTransform& BoneTransform = Output.Pose[CompactIndex];
		BoneTransform.SetRotation((DebugRotation * BoneTransform.GetRotation()).GetNormalized());
	}

	int32 AgentId = 0;
	bool bUseStoredPose = true;
	bool bEnableDebugMotion = true;
	FName DebugBoneName = TEXT("spine_03");
	float DebugMotionDegrees = 12.0f;
	float DebugMotionHz = 1.0f;
	float DebugPhase = 0.0f;

	bool bHasStoredPose = false;
	FProphecyNNPoseSnapshot StoredPose;

	bool bCachedCompactIndicesValid = false;
	uint16 CachedBoneContainerSerial = 0;
	uint32 CachedPoseRevision = 0;
	TArray<FCompactPoseBoneIndex> CachedCompactIndices;
};

UProphecyNNPoseAnimInstance::UProphecyNNPoseAnimInstance()
	: AgentId(0)
	, bUseStoredPose(true)
	, bEnableDebugMotion(true)
	, DebugBoneName(TEXT("spine_03"))
	, DebugMotionDegrees(12.0f)
	, DebugMotionHz(1.0f)
{
}

FAnimInstanceProxy* UProphecyNNPoseAnimInstance::CreateAnimInstanceProxy()
{
	return new FProphecyNNPoseAnimInstanceProxy(this);
}

void UProphecyNNPoseAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete InProxy;
}
