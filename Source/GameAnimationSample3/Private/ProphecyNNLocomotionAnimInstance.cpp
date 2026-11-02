#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyBodyflipRuntime.h"
#include "ProphecyFootIKGame.h"
#include "ProphecySwordHolsterPose.h"
#include "ProphecyReachRuntime.h"
#include "ProphecyAttackStartInertia.h"
#include "ProphecyNNInterpolation.h"

#include "ProphecyAgent.h"
#include "ProphecyAttackFists.h"
#include "ProphecyModeTransitions.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"

#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeBase.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AnimTypes.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"

namespace
{
	FCompactPoseBoneIndex ResolveLocomotionCompactBoneIndex(const FBoneContainer& RequiredBones, FName BoneName)
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
		// Gameplay ownership is sampled on the game thread only. Worker Evaluate
		// reads this private snapshot and never queries the active-controller map.
		bBodyflipPoseOwner = ProphecyBodyflip::Active(Cast<AProphecyAgent>(Instance->GetOwningActor()));
		ProphecyAttackFists::PreUpdate(this, Cast<AProphecyAgent>(Instance->GetOwningActor()));
		ProphecyModeTransitions::PreUpdate(this, Cast<AProphecyAgent>(Instance->GetOwningActor()));
		if (AgentId != CurrentAgentId)
		{
			PreviousPose.Reset();
			CurrentPose.Reset();
			CurrentAgentId = AgentId;
			bCompactIndexCacheValid = false;
		}
		// Carrier refreshes share the manager's presentation clock. Keep the world
		// frame duration available to readers without advancing overlay time again.
		const float FrameDeltaSeconds = DeltaSeconds > 0.0f || !Instance->GetWorld()
			? DeltaSeconds : Instance->GetWorld()->GetDeltaSeconds();
		bInterpolateNNPose = Instance->bInterpolateNNPose;
		bUseViewerGlobalPoseInterpolation = Instance->bUseViewerGlobalPoseInterpolation;
		NNPoseIntervalSeconds = FMath::Max(0.001f, Instance->NNPoseIntervalSeconds);
		UpdateOverlay(*Instance, DeltaSeconds);
		EvaluationTimeSeconds = Instance->GetWorld()
			? double(Instance->GetWorld()->GetTimeSeconds())
			: 0.0;
		if (const USkeletalMeshComponent* MeshComponent = Instance->GetSkelMeshComponent())
		{
			EvaluationComponentWorldTransform = MeshComponent->GetComponentTransform();
			EvaluationComponentWorldTransform.NormalizeRotation();
			bHasEvaluationComponentWorldTransform = true;
			const AProphecyAgent* Agent = Cast<AProphecyAgent>(MeshComponent->GetOwner());
			bPhysicalAgent = Agent && Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic;
		}
		else
		{
			EvaluationComponentWorldTransform = FTransform::Identity;
			bHasEvaluationComponentWorldTransform = false;
			bPhysicalAgent = false;
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
		// Resolve on the game thread; Evaluate only reads this cached scalar. Reuse
		// the former frame-delta slot to preserve already-allocated proxy layouts.
		PresentationAlpha = ProphecyNNPresentation::Resolve(AgentId, CurrentPose.SourceTimeSeconds,
			EvaluationTimeSeconds, FrameDeltaSeconds, NNPoseIntervalSeconds, bInterpolateNNPose);
	}

	virtual bool Evaluate(FPoseContext& Output) override
	{
		Output.ResetToRefPose();
		if (!CurrentPose.IsValid())
		{
			ProphecyAttackFists::Evaluate(this, Output);
			if (!bBodyflipPoseOwner) ProphecyModeTransitions::Evaluate(this, Output);
			return true;
		}

		const FBoneContainer& PoseBones = Output.Pose.GetBoneContainer();
		if (!bCompactIndexCacheValid || CachedBoneContainerSerial != PoseBones.GetSerialNumber() ||
			CachedBoneLayoutHash != CurrentPose.BoneLayoutHash)
		{
			RebuildCompactIndexCache(PoseBones);
		}

		const float PoseAlpha = PresentationAlpha;

		TArray<FTransform, TInlineAllocator<64>> ReferencePose;
		ReferencePose.SetNum(Output.Pose.GetNumBones());
		for (const FCompactPoseBoneIndex BoneIndex : Output.Pose.ForEachBoneIndex())
		{
			ReferencePose[BoneIndex.GetInt()] = Output.Pose[BoneIndex];
		}

		ApplyNNPose(Output, PoseAlpha, true, true, true);
		const FCompactPoseBoneIndex PelvisIndex = ResolveLocomotionCompactBoneIndex(PoseBones, TEXT("pelvis"));
		const FTransform NNPelvis = PelvisIndex.IsValid() && Output.Pose.IsValidIndex(PelvisIndex)
			? Output.Pose[PelvisIndex]
			: FTransform::Identity;

		if (CanEvaluateOverlay() && OverlayAnimation->GetSkeleton())
		{
			TArray<FTransform, TInlineAllocator<64>> NNPose;
			NNPose.SetNum(Output.Pose.GetNumBones());
			for (const FCompactPoseBoneIndex BoneIndex : Output.Pose.ForEachBoneIndex())
			{
				NNPose[BoneIndex.GetInt()] = Output.Pose[BoneIndex];
			}
			FAnimationPoseData AnimationPoseData(Output);
			OverlayAnimation->GetAnimationPose(
				AnimationPoseData,
				FAnimExtractContext(OverlayTimeSeconds, false, FDeltaTimeRecord(), bLoopOverlay));

			const FCompactPoseBoneIndex RootIndex = ResolveLocomotionCompactBoneIndex(PoseBones, TEXT("root"));
			for (const FCompactPoseBoneIndex BoneIndex : Output.Pose.ForEachBoneIndex())
			{
				const int32 CompactIndex = BoneIndex.GetInt();
				const int32 SkeletonIndex = PoseBones.GetSkeletonIndex(BoneIndex);
				const FName BoneName = PoseBones.GetReferenceSkeleton().GetBoneName(SkeletonIndex);
				if (BoneIndex == RootIndex)
				{
					Output.Pose[BoneIndex] = ReferencePose[CompactIndex];
				}
				else if (OverlayMode == EProphecyAnimationOverlayMode::FullBody)
				{
					Output.Pose[BoneIndex] = BlendTransform(
						NNPose[CompactIndex], Output.Pose[BoneIndex], OverlayWeight);
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

			if (OverlayMode == EProphecyAnimationOverlayMode::UpperBodyOnly)
			{
				ApplyNNPose(Output, PoseAlpha, false, true, false);
			}
		}

		ProphecyAttackFists::Evaluate(this, Output);
		if (!bBodyflipPoseOwner) ProphecyModeTransitions::Evaluate(this, Output);
		// Overlay and simulation-mode blends run after NN presentation. Their
		// component-space interpolation must not shorten an attached forearm.
		// Enforce the anatomical local translations at the final animation output;
		// wrist rotations and finger-local poses retain their authored values.
		for(int32 Side=0;Side<2;++Side)
		{
			if(CurrentPose.FixedArms.ForearmOffsets[Side].IsNearlyZero())continue;
			const FCompactPoseBoneIndex Index=ResolveLocomotionCompactBoneIndex(PoseBones,Side==0?FName(TEXT("hand_l")):FName(TEXT("hand_r")));
			if(Index.IsValid() && Output.Pose.IsValidIndex(Index))
				Output.Pose[Index].SetTranslation(PoseBones.GetReferenceSkeleton().GetRefBonePose()[PoseBones.GetSkeletonIndex(Index)].GetTranslation());
		}
		Output.Pose.NormalizeRotations();
		return true;
	}

private:
#if WITH_DEV_AUTOMATION_TESTS
	friend class FProphecyBodyflipOverlayOwnershipTest;
#endif
	void UpdateOverlay(const UProphecyNNLocomotionAnimInstance& Instance, float DeltaSeconds)
	{
		// Retain the private playhead, fade and pending restart while Bodyflip owns
		// the body. Instance/global settings stay editable and are read on release.
		if (bBodyflipPoseOwner) return;
		OverlayAnimation = Instance.OverlayAnimation;
		bLoopOverlay = Instance.bLoopOverlay;
		OverlayPlayRate = Instance.OverlayPlayRate;
		OverlayMode = Instance.OverlayMode;
		if (OverlayPlaybackRevision != Instance.OverlayPlaybackRevision)
		{
			OverlayPlaybackRevision = Instance.OverlayPlaybackRevision;
			OverlayTimeSeconds = 0.0;
		}
		const float TargetOverlayWeight = Instance.bOverlayEnabled && OverlayAnimation ? 1.0f : 0.0f;
		if (Instance.OverlayBlendSeconds <= UE_SMALL_NUMBER)
		{
			OverlayWeight = TargetOverlayWeight;
		}
		else
		{
			OverlayWeight = FMath::FInterpConstantTo(
				OverlayWeight,
				TargetOverlayWeight,
				DeltaSeconds,
				1.0f / Instance.OverlayBlendSeconds);
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

	}
	bool CanEvaluateOverlay() const
	{
		return !bBodyflipPoseOwner && OverlayAnimation && OverlayWeight > UE_SMALL_NUMBER;
	}

	void RebuildCompactIndexCache(const FBoneContainer& PoseBones)
	{
		CachedCompactIndices.Reset(CurrentPose.BoneNames.Num());
		CachedCompactIndices.AddUninitialized(CurrentPose.BoneNames.Num());
		for (int32 Index = 0; Index < CurrentPose.BoneNames.Num(); ++Index)
		{
			CachedCompactIndices[Index] = ResolveLocomotionCompactBoneIndex(PoseBones, CurrentPose.BoneNames[Index]);
		}
		CachedBoneContainerSerial = PoseBones.GetSerialNumber();
		CachedBoneLayoutHash = CurrentPose.BoneLayoutHash;
		bCompactIndexCacheValid = true;
	}

	void ApplyNNPose(
		FPoseContext& Output,
		float Alpha,
		bool bApplyPelvis,
		bool bApplyLegs,
		bool bApplyUpperBody) const
	{
		const bool bCanUseViewerInterpolation = (bUseViewerGlobalPoseInterpolation || CurrentPose.InterpolationMode != EProphecyNNInterpolationMode::Current) &&
			bHasEvaluationComponentWorldTransform && CurrentPose.bHasComponentWorldTransform &&
			CurrentPose.PreviousComponentTransforms.Num() == CurrentPose.ComponentTransforms.Num() &&
			CurrentPose.ComponentTransforms.Num() == CurrentPose.BoneNames.Num();
		if (bCanUseViewerInterpolation)
		{
			ApplyViewerGlobalPose(Output, Alpha, bApplyPelvis, bApplyLegs, bApplyUpperBody);
			return;
		}

		const bool bCanInterpolate = PreviousPose.IsValid() && PreviousPose.BoneLayoutHash == CurrentPose.BoneLayoutHash &&
			PreviousPose.LocalTransforms.Num() == CurrentPose.LocalTransforms.Num();
		for (int32 Index = 0; Index < CurrentPose.LocalTransforms.Num(); ++Index)
		{
			const FName BoneName = CurrentPose.BoneNames[Index];
			const bool bIsPelvis = BoneName == TEXT("pelvis");
			const bool bIsLeg = IsNNLegBone(BoneName);
			const bool bIsUpperBody = !bIsPelvis && !bIsLeg;
			if ((bIsPelvis && !bApplyPelvis) || (bIsLeg && !bApplyLegs) ||
				(bIsUpperBody && !bApplyUpperBody))
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
		bool bApplyLegs,
		bool bApplyUpperBody) const
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
			const bool bIsUpperBody = !bIsPelvis && !bIsLeg;
			if ((bIsPelvis && !bApplyPelvis) || (bIsLeg && !bApplyLegs) ||
				(bIsUpperBody && !bApplyUpperBody))
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
			DesiredComponentTransforms[Index] = (CurrentPose.InterpolationMode != EProphecyNNInterpolationMode::Current
				? ProphecyNNInterpolation::Sample(CurrentPose, Index, PreviousWorld, CurrentWorld, Alpha)
				: BlendViewerWorldTransform(PreviousWorld, CurrentWorld, Alpha)).GetRelativeTransform(EvaluationComponentWorldTransform);
			DesiredComponentTransforms[Index].NormalizeRotation();
			HasDesiredTransform[Index] = true;
		}

		if (bApplyUpperBody)
		{
			FProphecyNNPoseStore::ApplyRigidForearms(AgentId, CurrentPose,
				CurrentPose.BoneNames, DesiredComponentTransforms);
		}

		if (bApplyLegs)
			FProphecyNNPoseStore::ApplyRigidCalves(AgentId, CurrentPose,
				CurrentPose.BoneNames, DesiredComponentTransforms,Alpha);

		if (bApplyPelvis && bApplyLegs && bApplyUpperBody)
            ProphecyAttackStartInertia::Apply(AgentId,CurrentPose.BoneNames,DesiredComponentTransforms,EvaluationComponentWorldTransform);
        if (bApplyUpperBody) ProphecySwordHolsterPose::Apply(AgentId,CurrentPose.BoneNames,DesiredComponentTransforms,EvaluationComponentWorldTransform);
        ProphecyReach::Apply(AgentId,CurrentPose.BoneNames,DesiredComponentTransforms,EvaluationComponentWorldTransform);
        if(bApplyPelvis&&bApplyLegs&&bApplyUpperBody)
            ProphecyFootIKGame::Apply(AgentId,CurrentPose.BoneNames,DesiredComponentTransforms,EvaluationComponentWorldTransform);
		const bool bRecoveringCalfLength=!bPhysicalAgent && ProphecyNNPresentation::HasRecoveryCalfLengths(AgentId);
		// The model viewer draws each lower-leg segment all the way from the calf
		// point to the predicted foot point. Mirror that here: keep the predicted
		// endpoint, align the calf's actual reference-bone axis to it, and extend
		// the calf mesh to reach it. Moving only the foot bone leaves a visible gap.
		auto ExtendCalfToFoot = [&](FName CalfName, FName FootName)
		{
			const int32 CalfPoseIndex = CurrentPose.BoneNames.IndexOfByKey(CalfName);
			const int32 FootPoseIndex = CurrentPose.BoneNames.IndexOfByKey(FootName);
			if (CalfPoseIndex == INDEX_NONE || FootPoseIndex == INDEX_NONE ||
				!HasDesiredTransform[CalfPoseIndex] || !HasDesiredTransform[FootPoseIndex])
			{
				return;
			}

			const int32 FootSkeletonIndex = PoseBones.GetReferenceSkeleton().FindBoneIndex(FootName);
			if (FootSkeletonIndex == INDEX_NONE)
			{
				return;
			}

			const FVector ReferenceOffset =
				PoseBones.GetReferenceSkeleton().GetRefBonePose()[FootSkeletonIndex].GetTranslation();
			const FVector DesiredSegment =
				DesiredComponentTransforms[FootPoseIndex].GetLocation() -
				DesiredComponentTransforms[CalfPoseIndex].GetLocation();
			const double ReferenceLength = ReferenceOffset.Length();
			const double DesiredLength = DesiredSegment.Length();
			if (ReferenceLength <= UE_SMALL_NUMBER || DesiredLength <= UE_SMALL_NUMBER)
			{
				return;
			}

			FTransform& CalfTransform = DesiredComponentTransforms[CalfPoseIndex];
			const FVector CurrentAxis = CalfTransform.GetRotation().RotateVector(ReferenceOffset).GetSafeNormal();
			const FVector DesiredAxis = DesiredSegment / DesiredLength;
			CalfTransform.SetRotation(
				(FQuat::FindBetweenNormals(CurrentAxis, DesiredAxis) * CalfTransform.GetRotation()).GetNormalized());
			// Attacks retain the authored unit scale even when the ankle is farther
			// away. Growing the mesh to that distance on the first recovery frame
			// closes the gap instantly despite a smooth knee/ankle length return.
			// Keep that scale until recovery converges to rest; the existing signed
			// length curve closes the visible gap without another timer or blend.
			if (!bRecoveringCalfLength) CalfTransform.SetScale3D(FVector(DesiredLength / ReferenceLength));
		};
		// Attack playback already supplies the authored calf transform at unit
		// scale. The legacy locomotion extension would inflate all three axes.
		if (!bPhysicalAgent && !FProphecyNNPoseStore::UsesLowerSpecialPresentation(AgentId))
		{
			ExtendCalfToFoot(TEXT("calf_l"), TEXT("foot_l"));
			ExtendCalfToFoot(TEXT("calf_r"), TEXT("foot_r"));
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
	EProphecyAnimationOverlayMode OverlayMode = EProphecyAnimationOverlayMode::UpperBodyOnly;
	int32 OverlayPlaybackRevision = INDEX_NONE;
	float OverlayPlayRate = 1.0f;
	float OverlayWeight = 0.0f;
	double OverlayTimeSeconds = 0.0;
	double PoseBlendStartSeconds = 0.0;
	double EvaluationTimeSeconds = 0.0;
	float PresentationAlpha = 1.0f;
	FTransform EvaluationComponentWorldTransform = FTransform::Identity;
	bool bHasEvaluationComponentWorldTransform = false;
	bool bPhysicalAgent = false;
	bool bBodyflipPoseOwner = false;

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
	ProphecyAttackFists::ReleaseProxy(InProxy);
	ProphecyModeTransitions::ReleaseProxy(InProxy);
	delete InProxy;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Animation/AnimSequence.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipOverlayOwnershipTest,
	"Prophecy.Bodyflip.Presentation.OverlayOwnership",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipOverlayOwnershipTest::RunTest(const FString&)
{
	// Test the actual private update/evaluation decision, without an NN model,
	// animation asset, world or second controller. A zero-length transient clip
	// retains the ordinary unbounded-time behavior used by UpdateOverlay.
	auto* Mesh = NewObject<USkeletalMeshComponent>();
	auto* Instance = NewObject<UProphecyNNLocomotionAnimInstance>(Mesh);
	auto* ClipA = NewObject<UAnimSequence>();
	auto* ClipB = NewObject<UAnimSequence>();
	FProphecyNNLocomotionAnimInstanceProxy Owned, Other;
	Instance->OverlayAnimation = ClipA;
	Instance->bOverlayEnabled = true;
	Instance->OverlayBlendSeconds = 1;
	Instance->OverlayPlayRate = 2;
	Instance->bLoopOverlay = false;
	Instance->OverlayPlaybackRevision = 7;
	Owned.UpdateOverlay(*Instance, .125f);
	Other.UpdateOverlay(*Instance, .125f);
	TestEqual(TEXT("Ordinary fade is unchanged"), Owned.OverlayWeight, .125f);
	TestEqual(TEXT("Ordinary playhead is unchanged"), Owned.OverlayTimeSeconds, .25);
	TestTrue(TEXT("Ordinary overlay can evaluate"), Owned.CanEvaluateOverlay());
	Owned.bBodyflipPoseOwner = true;
	Instance->OverlayAnimation = ClipB;
	Instance->OverlayPlayRate = 3;
	Instance->OverlayBlendSeconds = .2f;
	Instance->bLoopOverlay = true;
	Instance->OverlayMode = EProphecyAnimationOverlayMode::FullBody;
	Instance->RestartOverlayPlayback();
	for(int32 Frame=0;Frame<60;++Frame)Owned.UpdateOverlay(*Instance, 1.f/60);
	TestEqual(TEXT("Bodyflip retains overlay time"), Owned.OverlayTimeSeconds, .25);
	TestEqual(TEXT("Bodyflip retains fade progress"), Owned.OverlayWeight, .125f);
	TestEqual(TEXT("Pending restart is retained"), Owned.OverlayPlaybackRevision, 7);
	TestTrue(TEXT("Pending clip does not replace cached clip"), Owned.OverlayAnimation == ClipA);
	TestFalse(TEXT("Full-weight output is suppressed by cached ownership"), Owned.CanEvaluateOverlay());
	TestTrue(TEXT("Editable clip is not overwritten"), Instance->OverlayAnimation.Get() == ClipB);
	TestTrue(TEXT("Editable enabled setting is preserved"), Instance->bOverlayEnabled);
	TestEqual(TEXT("Editable restart revision is preserved"), Instance->OverlayPlaybackRevision, 8);
	// Exact binary duration isolates ownership from float constant-folding.
	Other.UpdateOverlay(*Instance, .0625f);
	TestTrue(TEXT("Another proxy still evaluates the global overlay"), Other.CanEvaluateOverlay());
	TestTrue(TEXT("Another proxy consumes the new clip"), Other.OverlayAnimation == ClipB);
	TestEqual(TEXT("Another proxy consumes the restart"), Other.OverlayTimeSeconds, .1875);
	Owned.bBodyflipPoseOwner = false;
	Owned.UpdateOverlay(*Instance, .0625f);
	TestTrue(TEXT("Overlay resumes after ownership ends"), Owned.CanEvaluateOverlay());
	TestTrue(TEXT("Resume consumes the latest clip"), Owned.OverlayAnimation == ClipB);
	TestEqual(TEXT("Resume consumes the pending restart"), Owned.OverlayPlaybackRevision, 8);
	TestEqual(TEXT("Resume uses the new play rate"), Owned.OverlayTimeSeconds, .1875);
	TestTrue(TEXT("Resume retains ordinary fade semantics"), FMath::IsNearlyEqual(Owned.OverlayWeight, .4375f));
	TestTrue(TEXT("Resume consumes current mode and loop"), Owned.OverlayMode == EProphecyAnimationOverlayMode::FullBody && Owned.bLoopOverlay);
	const double HeldTime = Owned.OverlayTimeSeconds;
	Owned.UpdateOverlay(*Instance, 0);
	TestEqual(TEXT("Zero-delta refresh does not advance time"), Owned.OverlayTimeSeconds, HeldTime);
	Owned.bBodyflipPoseOwner = true;
	Instance->bOverlayEnabled = false;
	Owned.UpdateOverlay(*Instance, .5f);
	TestEqual(TEXT("Disable during ownership does not advance time"), Owned.OverlayTimeSeconds, HeldTime);
	TestFalse(TEXT("Disable edit remains stored on instance"), Instance->bOverlayEnabled);
	Owned.bBodyflipPoseOwner = false;
	Owned.UpdateOverlay(*Instance, .2f);
	TestFalse(TEXT("Release honors a pending disable"), Owned.CanEvaluateOverlay());
	TestEqual(TEXT("Completed fade does not advance disabled clip"), Owned.OverlayTimeSeconds, HeldTime);
	return !HasAnyErrors();
}
#endif
