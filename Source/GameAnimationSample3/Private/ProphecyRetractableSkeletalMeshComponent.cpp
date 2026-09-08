#include "ProphecyRetractableSkeletalMeshComponent.h"

#include "Engine/SkeletalMesh.h"
#include "ReferenceSkeleton.h"

namespace
{
constexpr int32 PotenceRopeSegmentCount = 27;
constexpr float PotenceRopeMinimumLongitudinalScale = 0.001f;
const FName PotenceRopeRootBone(TEXT("joint"));

FName MakePotenceRopeBoneName(const int32 SegmentIndex)
{
	return FName(*FString::Printf(TEXT("joint%d"), SegmentIndex + 1));
}

bool GetReferenceBoneComponentTransform(
	const FReferenceSkeleton& ReferenceSkeleton,
	const int32 BoneIndex,
	FTransform& OutTransform)
{
	if (BoneIndex == INDEX_NONE)
	{
		return false;
	}

	const TArray<FTransform>& ReferencePose = ReferenceSkeleton.GetRefBonePose();
	OutTransform = ReferencePose[BoneIndex];
	for (int32 ParentIndex = ReferenceSkeleton.GetParentIndex(BoneIndex);
		ParentIndex != INDEX_NONE;
		ParentIndex = ReferenceSkeleton.GetParentIndex(ParentIndex))
	{
		OutTransform *= ReferencePose[ParentIndex];
	}
	return true;
}
}

void UProphecyRetractableSkeletalMeshComponent::SetRetractionVisualAmount(const float InAmount)
{
	RetractionVisualAmount = FMath::Clamp(InAmount, 0.0f, 1.0f);
	bRetractionVisualActive = true;
}

void UProphecyRetractableSkeletalMeshComponent::FinalizeBoneTransform()
{
	// At this point animation and any physics blending have written the editable
	// component-space pose, but USkinnedMeshComponent has not published it to the
	// render buffer yet. Physics bodies are independent and remain untouched.
	if (bRetractionVisualActive)
	{
		ApplyRetractionVisualPose();
	}

	Super::FinalizeBoneTransform();
}

void UProphecyRetractableSkeletalMeshComponent::ApplyRetractionVisualPose()
{
	const USkeletalMesh* RopeSkeletalMesh = GetSkeletalMeshAsset();
	if (!RopeSkeletalMesh)
	{
		return;
	}

	const FReferenceSkeleton& ReferenceSkeleton = RopeSkeletalMesh->GetRefSkeleton();
	TArray<FTransform>& ComponentPose = GetEditableComponentSpaceTransforms();
	const int32 RootBoneIndex = ReferenceSkeleton.FindBoneIndex(PotenceRopeRootBone);
	FTransform RootReferenceTransform;
	if (!ComponentPose.IsValidIndex(RootBoneIndex)
		|| !GetReferenceBoneComponentTransform(ReferenceSkeleton, RootBoneIndex, RootReferenceTransform))
	{
		return;
	}

	const FVector Anchor = RootReferenceTransform.GetLocation();
	FVector RetractionDirection = FVector::UpVector;
	const int32 FirstSegmentBoneIndex = ReferenceSkeleton.FindBoneIndex(MakePotenceRopeBoneName(0));
	FTransform FirstSegmentReferenceTransform;
	if (GetReferenceBoneComponentTransform(
		ReferenceSkeleton, FirstSegmentBoneIndex, FirstSegmentReferenceTransform))
	{
		RetractionDirection = (Anchor - FirstSegmentReferenceTransform.GetLocation()).GetSafeNormal(
			SMALL_NUMBER, FVector::UpVector);
	}

	FTransform& RootVisualTransform = ComponentPose[RootBoneIndex];
	RootVisualTransform.SetLocation(Anchor);
	RootVisualTransform.SetScale3D(RootReferenceTransform.GetScale3D());

	const float SegmentProgress = RetractionVisualAmount * static_cast<float>(PotenceRopeSegmentCount);
	for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
	{
		const int32 BoneIndex = ReferenceSkeleton.FindBoneIndex(MakePotenceRopeBoneName(SegmentIndex));
		if (!ComponentPose.IsValidIndex(BoneIndex))
		{
			continue;
		}

		FTransform ReferenceTransform;
		if (!GetReferenceBoneComponentTransform(ReferenceSkeleton, BoneIndex, ReferenceTransform))
		{
			continue;
		}

		FTransform& VisualTransform = ComponentPose[BoneIndex];
		const float ConsumedFraction = FMath::Clamp(
			SegmentProgress - static_cast<float>(SegmentIndex), 0.0f, 1.0f);
		const bool bAboveAnchor = FVector::DotProduct(
			VisualTransform.GetLocation() - Anchor, RetractionDirection) > 0.0f;
		if (ConsumedFraction >= 1.0f || bAboveAnchor)
		{
			VisualTransform.SetLocation(Anchor);
		}

		// The rope was authored along each bone's local Z axis. Only that axis is
		// shortened; the two radial axes retain their authored scale.
		FVector VisualScale = ReferenceTransform.GetScale3D();
		VisualScale.Z *= FMath::Max(1.0f - ConsumedFraction, PotenceRopeMinimumLongitudinalScale);
		VisualTransform.SetScale3D(VisualScale);
	}
}
