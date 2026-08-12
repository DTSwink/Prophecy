#include "ProphecyNNLocomotionAnimInstance.h"

#include "ProphecyNNPoseTypes.h"

#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AnimTypes.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"

namespace
{
	FCompactPoseBoneIndex ResolveCompactBoneIndex(const FBoneContainer& RequiredBones, FName BoneName)
	{
		const int32 SkeletonIndex = RequiredBones.GetReferenceSkeleton().FindBoneIndex(BoneName);
		return SkeletonIndex == INDEX_NONE
			? FCompactPoseBoneIndex(INDEX_NONE)
			: RequiredBones.GetCompactPoseIndexFromSkeletonIndex(SkeletonIndex);
	}

	bool IsNNLegBone(FName BoneName)
	{
		return BoneName == TEXT("thigh_l") || BoneName == TEXT("calf_l") || BoneName == TEXT("foot_l") || BoneName == TEXT("ball_l") ||
			BoneName == TEXT("thigh_r") || BoneName == TEXT("calf_r") || BoneName == TEXT("foot_r") || BoneName == TEXT("ball_r");
	}

	FTransform BlendTransform(const FTransform& A, const FTransform& B, float Alpha)
	{
		FTransform Result;
		Result.Blend(A, B, Alpha);
		Result.NormalizeRotation();
		return Result;
	}

	FQuat BlendViewerRotation(const FQuat& A, const FQuat& B, float Alpha)
	{
		FQuat Start = A.GetNormalized();
		FQuat End = B.GetNormalized();
		float CosHalfAngle = Start | End;
		if (CosHalfAngle < 0.0f)
		{
			End = End * -1.0f;
			CosHalfAngle = -CosHalfAngle;
		}
		CosHalfAngle = FMath::Clamp(CosHalfAngle, 0.0f, 1.0f);
		const float Angle = 2.0f * FMath::Acos(CosHalfAngle);
		if (Angle <= 1.0e-6f)
		{
			return Start;
		}

		// Stepper Model Viewer linearly blends rotation matrices and projects the
		// result back onto SO(3) with SVD. For two rotations, the polar factor is
		// the same relative axis with this adjusted angle.
		const float WeightedAngle = FMath::Atan2(
			Alpha * FMath::Sin(Angle),
			(1.0f - Alpha) + Alpha * FMath::Cos(Angle));
		FQuat Result = FQuat::Slerp(Start, End, WeightedAngle / Angle);
		Result.Normalize();
		return Result;
	}

	FTransform BlendViewerWorldTransform(const FTransform& A, const FTransform& B, float Alpha)
	{
		return FTransform(
			BlendViewerRotation(A.GetRotation(), B.GetRotation(), Alpha),
			FMath::Lerp(A.GetLocation(), B.GetLocation(), Alpha),
			FMath::Lerp(A.GetScale3D(), B.GetScale3D(), Alpha));
	}
}

class FProphecyNNLocomotionAnimInstanceProxy final : public FAnimInstanceProxy
{
public:
	FProphecyNNLocomotionAnimInstanceProxy() = default;
	explicit FProphecyNNLocomotionAnimInstanceProxy(UAnimInstance* Instance)
		: FAnimInstanceProxy(Instance)
	{
	}

protected:
	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override
	{
		FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);

		const UProphecyNNLocomotionAnimInstance* Instance = Cast<UProphecyNNLocomotionAnimInstance>(InAnimInstance);
		if (!Instance)
		{
			return;
		}

		AgentId = Instance->AgentId;
		if (AgentId != CurrentAgentId)
		{
			PreviousPose.Reset();
			CurrentPose.Reset();
			CurrentAgentId = AgentId;
			bCompactIndexCacheValid = false;
		}
		RenderDeltaSeconds = DeltaSeconds;
		bInterpolateNNPose = Instance->bInterpolateNNPose;
		bUseViewerGlobalPoseInterpolation = Instance->bUseViewerGlobalPoseInterpolation;
		NNPoseIntervalSeconds = FMath::Max(0.001f, Instance->NNPoseIntervalSeconds);
		OverlayAnimation = Instance->OverlayAnimation;
		bLoopOverlay = Instance->bLoopOverlay;
		OverlayPlayRate = Instance->OverlayPlayRate;
		EvaluationTimeSeconds = Instance->GetWorld()
			? double(Instance->GetWorld()->GetTimeSeconds())
			: 0.0;
		if (const USkeletalMeshComponent* MeshComponent = Instance->GetSkelMeshComponent())
		{
			EvaluationComponentWorldTransform = MeshComponent->GetComponentTransform();
			EvaluationComponentWorldTransform.NormalizeRotation();
			bHasEvaluationComponentWorldTransform = true;
		}
		else
		{
			EvaluationComponentWorldTransform = FTransform::Identity;
			bHasEvaluationComponentWorldTransform = false;
		}

		const float TargetOverlayWeight = Instance->bOverlayEnabled && OverlayAnimation ? 1.0f : 0.0f;
		if (Instance->OverlayBlendSeconds <= UE_SMALL_NUMBER)
		{
			OverlayWeight = TargetOverlayWeight;
		}
		else
		{
			OverlayWeight = FMath::FInterpConstantTo(
				OverlayWeight,
				TargetOverlayWeight,
				DeltaSeconds,
				1.0f / Instance->OverlayBlendSeconds);
		}

		if (OverlayAnimation && (TargetOverlayWeight > 0.0f || OverlayWeight > 0.0f))
		{
			const double PlayLength = FMath::Max(0.0, OverlayAnimation->GetPlayLength());
			OverlayTimeSeconds += double(DeltaSeconds * OverlayPlayRate);
			if (PlayLength > UE_DOUBLE_SMALL_NUMBER)
			{
				OverlayTimeSeconds = bLoopOverlay
					? FMath::Fmod(OverlayTimeSeconds, PlayLength)
					: FMath::Clamp(OverlayTimeSeconds, 0.0, PlayLength);
			}
		}

		FProphecyNNPoseSnapshot LatestPose;
		if (FProphecyNNPoseStore::GetAgentLocalPoseIfNewer(AgentId, CurrentPose.Revision, LatestPose))
		{
			if (CurrentPose.IsValid() && CurrentPose.BoneLayoutHash == LatestPose.BoneLayoutHash)
			{
				PreviousPose = MoveTemp(CurrentPose);
			}
			else
			{
				PreviousPose = LatestPose;
				bCompactIndexCacheValid = false;
			}
			CurrentPose = MoveTemp(LatestPose);
			PoseBlendStartSeconds = CurrentPose.SourceTimeSeconds;
		}
	}

	virtual bool Evaluate(FPoseContext& Output) override
	{
		Output.ResetToRefPose();
		if (!CurrentPose.IsValid())
		{
			return true;
		}

		const FBoneContainer& PoseBones = Output.Pose.GetBoneContainer();
		if (!bCompactIndexCacheValid || CachedBoneContainerSerial != PoseBones.GetSerialNumber() ||
			CachedBoneLayoutHash != CurrentPose.BoneLayoutHash)
		{
			RebuildCompactIndexCache(PoseBones);
		}

		const bool bHasBetweenPoseRenderFrame = RenderDeltaSeconds < NNPoseIntervalSeconds;
		const float PoseAlpha = bInterpolateNNPose && bHasBetweenPoseRenderFrame
			? FMath::Clamp(float((EvaluationTimeSeconds - PoseBlendStartSeconds) / double(NNPoseIntervalSeconds)), 0.0f, 1.0f)
			: 1.0f;

		TArray<FTransform, TInlineAllocator<64>> ReferencePose;
		ReferencePose.SetNum(Output.Pose.GetNumBones());
		for (const FCompactPoseBoneIndex BoneIndex : Output.Pose.ForEachBoneIndex())
		{
			ReferencePose[BoneIndex.GetInt()] = Output.Pose[BoneIndex];
		}

		ApplyNNPose(Output, PoseAlpha, true, true);
		const FCompactPoseBoneIndex PelvisIndex = ResolveCompactBoneIndex(PoseBones, TEXT("pelvis"));
		const FTransform NNPelvis = PelvisIndex.IsValid() && Output.Pose.IsValidIndex(PelvisIndex)
			? Output.Pose[PelvisIndex]
			: FTransform::Identity;

		if (OverlayAnimation && OverlayWeight > UE_SMALL_NUMBER && OverlayAnimation->GetSkeleton())
		{
			FAnimationPoseData AnimationPoseData(Output);
			OverlayAnimation->GetAnimationPose(
				AnimationPoseData,
				FAnimExtractContext(OverlayTimeSeconds, false, FDeltaTimeRecord(), bLoopOverlay));

			const FCompactPoseBoneIndex RootIndex = ResolveCompactBoneIndex(PoseBones, TEXT("root"));
			for (const FCompactPoseBoneIndex BoneIndex : Output.Pose.ForEachBoneIndex())
			{
				const int32 CompactIndex = BoneIndex.GetInt();
				const int32 SkeletonIndex = PoseBones.GetSkeletonIndex(BoneIndex);
				const FName BoneName = PoseBones.GetReferenceSkeleton().GetBoneName(SkeletonIndex);
				if (BoneIndex == RootIndex)
				{
					Output.Pose[BoneIndex] = ReferencePose[CompactIndex];
				}
				else if (BoneIndex == PelvisIndex)
				{
					Output.Pose[BoneIndex] = BlendTransform(NNPelvis, Output.Pose[BoneIndex], OverlayWeight);
				}
				else if (!IsNNLegBone(BoneName))
				{
					Output.Pose[BoneIndex] = BlendTransform(ReferencePose[CompactIndex], Output.Pose[BoneIndex], OverlayWeight);
				}
			}

			ApplyNNPose(Output, PoseAlpha, false, true);
		}

		Output.Pose.NormalizeRotations();
		return true;
	}

private:
	void RebuildCompactIndexCache(const FBoneContainer& PoseBones)
	{
		CachedCompactIndices.Reset(CurrentPose.BoneNames.Num());
		CachedCompactIndices.AddUninitialized(CurrentPose.BoneNames.Num());
		for (int32 Index = 0; Index < CurrentPose.BoneNames.Num(); ++Index)
		{
			CachedCompactIndices[Index] = ResolveCompactBoneIndex(PoseBones, CurrentPose.BoneNames[Index]);
		}
		CachedBoneContainerSerial = PoseBones.GetSerialNumber();
		CachedBoneLayoutHash = CurrentPose.BoneLayoutHash;
		bCompactIndexCacheValid = true;
	}

	void ApplyNNPose(FPoseContext& Output, float Alpha, bool bApplyPelvis, bool bApplyLegs) const
	{
		const bool bCanUseViewerInterpolation = bUseViewerGlobalPoseInterpolation &&
			bHasEvaluationComponentWorldTransform && CurrentPose.bHasComponentWorldTransform &&
			CurrentPose.PreviousComponentTransforms.Num() == CurrentPose.ComponentTransforms.Num() &&
			CurrentPose.ComponentTransforms.Num() == CurrentPose.BoneNames.Num();
		if (bCanUseViewerInterpolation)
		{
			ApplyViewerGlobalPose(Output, Alpha, bApplyPelvis, bApplyLegs);
			return;
		}

		const bool bCanInterpolate = PreviousPose.IsValid() && PreviousPose.BoneLayoutHash == CurrentPose.BoneLayoutHash &&
			PreviousPose.LocalTransforms.Num() == CurrentPose.LocalTransforms.Num();
		for (int32 Index = 0; Index < CurrentPose.LocalTransforms.Num(); ++Index)
		{
			const FName BoneName = CurrentPose.BoneNames[Index];
			const bool bIsPelvis = BoneName == TEXT("pelvis");
			const bool bIsLeg = IsNNLegBone(BoneName);
			if ((bIsPelvis && !bApplyPelvis) || (bIsLeg && !bApplyLegs) || (!bIsPelvis && !bIsLeg))
			{
				continue;
			}

			const FCompactPoseBoneIndex CompactIndex = CachedCompactIndices.IsValidIndex(Index)
				? CachedCompactIndices[Index]
				: FCompactPoseBoneIndex(INDEX_NONE);
			if (!CompactIndex.IsValid() || !Output.Pose.IsValidIndex(CompactIndex))
			{
				continue;
			}

			Output.Pose[CompactIndex] = bCanInterpolate
				? BlendTransform(PreviousPose.LocalTransforms[Index], CurrentPose.LocalTransforms[Index], Alpha)
				: CurrentPose.LocalTransforms[Index];
		}
	}

	void ApplyViewerGlobalPose(
		FPoseContext& Output,
		float Alpha,
		bool bApplyPelvis,
		bool bApplyLegs) const
	{
		const FBoneContainer& PoseBones = Output.Pose.GetBoneContainer();
		FCSPose<FCompactPose> ExistingComponentPose;
		ExistingComponentPose.InitPose(Output.Pose);

		TArray<FTransform, TInlineAllocator<16>> DesiredComponentTransforms;
		DesiredComponentTransforms.SetNum(CurrentPose.BoneNames.Num());
		TArray<uint8, TInlineAllocator<16>> HasDesiredTransform;
		HasDesiredTransform.Init(0, CurrentPose.BoneNames.Num());
		for (int32 Index = 0; Index < CurrentPose.BoneNames.Num(); ++Index)
		{
			const FName BoneName = CurrentPose.BoneNames[Index];
			const bool bIsPelvis = BoneName == TEXT("pelvis");
			const bool bIsLeg = IsNNLegBone(BoneName);
			if ((bIsPelvis && !bApplyPelvis) || (bIsLeg && !bApplyLegs) || (!bIsPelvis && !bIsLeg))
			{
				continue;
			}
			const FCompactPoseBoneIndex CompactIndex = CachedCompactIndices.IsValidIndex(Index)
				? CachedCompactIndices[Index]
				: FCompactPoseBoneIndex(INDEX_NONE);
			if (!CompactIndex.IsValid() || !Output.Pose.IsValidIndex(CompactIndex))
			{
				continue;
			}

			const FTransform PreviousWorld = CurrentPose.PreviousComponentTransforms[Index] *
				CurrentPose.PreviousComponentWorldTransform;
			const FTransform CurrentWorld = CurrentPose.ComponentTransforms[Index] *
				CurrentPose.ComponentWorldTransform;
			DesiredComponentTransforms[Index] = BlendViewerWorldTransform(
				PreviousWorld, CurrentWorld, Alpha).GetRelativeTransform(EvaluationComponentWorldTransform);
			DesiredComponentTransforms[Index].NormalizeRotation();
			HasDesiredTransform[Index] = true;
		}

		for (int32 Index = 0; Index < CurrentPose.BoneNames.Num(); ++Index)
		{
			if (!HasDesiredTransform[Index])
			{
				continue;
			}
			const FCompactPoseBoneIndex CompactIndex = CachedCompactIndices[Index];
			const FCompactPoseBoneIndex ParentIndex = PoseBones.GetParentBoneIndex(CompactIndex);
			FTransform ParentComponentTransform = FTransform::Identity;
			if (ParentIndex.IsValid())
			{
				const int32 ParentPoseIndex = CachedCompactIndices.IndexOfByKey(ParentIndex);
				ParentComponentTransform = ParentPoseIndex != INDEX_NONE && HasDesiredTransform[ParentPoseIndex]
					? DesiredComponentTransforms[ParentPoseIndex]
					: ExistingComponentPose.GetComponentSpaceTransform(ParentIndex);
			}
			Output.Pose[CompactIndex] = DesiredComponentTransforms[Index].GetRelativeTransform(ParentComponentTransform);
			Output.Pose[CompactIndex].NormalizeRotation();
		}
	}

	int32 AgentId = 0;
	int32 CurrentAgentId = INDEX_NONE;
	bool bInterpolateNNPose = true;
	bool bUseViewerGlobalPoseInterpolation = true;
	float NNPoseIntervalSeconds = 1.0f / 30.0f;
	UAnimSequenceBase* OverlayAnimation = nullptr;
	bool bLoopOverlay = true;
	float OverlayPlayRate = 1.0f;
	float OverlayWeight = 0.0f;
	double OverlayTimeSeconds = 0.0;
	double PoseBlendStartSeconds = 0.0;
	double EvaluationTimeSeconds = 0.0;
	float RenderDeltaSeconds = 0.0f;
	FTransform EvaluationComponentWorldTransform = FTransform::Identity;
	bool bHasEvaluationComponentWorldTransform = false;

	FProphecyNNPoseSnapshot PreviousPose;
	FProphecyNNPoseSnapshot CurrentPose;
	bool bCompactIndexCacheValid = false;
	uint16 CachedBoneContainerSerial = 0;
	uint32 CachedBoneLayoutHash = 0;
	TArray<FCompactPoseBoneIndex> CachedCompactIndices;
};

UProphecyNNLocomotionAnimInstance::UProphecyNNLocomotionAnimInstance() = default;

FAnimInstanceProxy* UProphecyNNLocomotionAnimInstance::CreateAnimInstanceProxy()
{
	return new FProphecyNNLocomotionAnimInstanceProxy(this);
}

void UProphecyNNLocomotionAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete InProxy;
}
