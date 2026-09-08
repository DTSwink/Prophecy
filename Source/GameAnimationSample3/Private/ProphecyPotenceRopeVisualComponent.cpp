#include "ProphecyPotenceRopeVisualComponent.h"

#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/Actor.h"
#include "ReferenceSkeleton.h"

namespace
{
constexpr int32 PotenceRopeSegmentCount = 27;
const FName PotenceRopeRootBone(TEXT("joint"));

// Keep the reflected component layout unchanged while Live Coding is active. The
// procedural component is now only a post-physics updater; this transient poseable
// component is the actual rendered copy of SKM_RopeHang.
TMap<TWeakObjectPtr<UProphecyPotenceRopeVisualComponent>, TWeakObjectPtr<UPoseableMeshComponent>>
	PotenceRopeSkinnedVisuals;

FName MakePotenceRopeVisualBoneName(const int32 SegmentIndex)
{
	return FName(*FString::Printf(TEXT("joint%d"), SegmentIndex + 1));
}

bool GetReferenceBoneComponentTransform(
	const USkeletalMesh* SkeletalMesh,
	const FName BoneName,
	FTransform& OutTransform)
{
	if (!SkeletalMesh)
	{
		return false;
	}

	const FReferenceSkeleton& ReferenceSkeleton = SkeletalMesh->GetRefSkeleton();
	const int32 BoneIndex = ReferenceSkeleton.FindBoneIndex(BoneName);
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

UProphecyPotenceRopeVisualComponent::UProphecyPotenceRopeVisualComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
	SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SetGenerateOverlapEvents(false);
	bUseComplexAsSimpleCollision = false;
}

void UProphecyPotenceRopeVisualComponent::Initialize(USkeletalMeshComponent* InTarget)
{
	if (!InTarget)
	{
		return;
	}
	if (Target.Get() == InTarget)
	{
		const TWeakObjectPtr<UPoseableMeshComponent>* ExistingVisual = PotenceRopeSkinnedVisuals.Find(this);
		if (ExistingVisual && ExistingVisual->IsValid())
		{
			return;
		}
	}

	Target = InTarget;
	bOriginalTargetVisible = InTarget->GetVisibleFlag();
	OriginalVisibilityTickOption = InTarget->VisibilityBasedAnimTickOption;
	InTarget->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

	AttachToComponent(InTarget, FAttachmentTransformRules::SnapToTargetNotIncludingScale);
	SetRelativeTransform(FTransform::Identity);
	AddTickPrerequisiteComponent(InTarget);

	// This class remains a procedural component solely to make the change safe for
	// an already-running editor. It never creates or renders procedural geometry.
	ClearAllMeshSections();
	bSectionCreated = false;
	SetCastShadow(false);
	SetVisibility(false, false);

	AActor* Owner = InTarget->GetOwner();
	if (!Owner || !InTarget->GetSkinnedAsset())
	{
		return;
	}

	UPoseableMeshComponent* SkinnedVisual = NewObject<UPoseableMeshComponent>(
		Owner,
		*FString::Printf(TEXT("ProphecyRopeSkinnedVisual_%s"), *InTarget->GetName()),
		RF_Transient);
	Owner->AddInstanceComponent(SkinnedVisual);
	SkinnedVisual->SetupAttachment(InTarget);
	SkinnedVisual->SetRelativeTransform(FTransform::Identity);
	SkinnedVisual->SetSkinnedAssetAndUpdate(InTarget->GetSkinnedAsset());
	SkinnedVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SkinnedVisual->SetGenerateOverlapEvents(false);
	SkinnedVisual->SetCastShadow(InTarget->CastShadow);
	SkinnedVisual->SetVisibility(true, false);
	SkinnedVisual->SetHiddenInGame(false, false);
	for (int32 MaterialIndex = 0; MaterialIndex < InTarget->GetNumMaterials(); ++MaterialIndex)
	{
		SkinnedVisual->SetMaterial(MaterialIndex, InTarget->GetMaterial(MaterialIndex));
	}
	SkinnedVisual->RegisterComponent();
	PotenceRopeSkinnedVisuals.Add(this, SkinnedVisual);

	UpdateRopeMesh();
	InTarget->SetVisibility(false, false);
}

void UProphecyPotenceRopeVisualComponent::SetRetractionAmount(const float InAmount)
{
	RetractionAmount = FMath::Clamp(InAmount, 0.0f, 1.0f);
}

void UProphecyPotenceRopeVisualComponent::TickComponent(
	const float DeltaTime,
	const ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UpdateRopeMesh();
}

void UProphecyPotenceRopeVisualComponent::OnComponentDestroyed(const bool bDestroyingHierarchy)
{
	if (TWeakObjectPtr<UPoseableMeshComponent>* VisualEntry = PotenceRopeSkinnedVisuals.Find(this))
	{
		if (UPoseableMeshComponent* SkinnedVisual = VisualEntry->Get())
		{
			SkinnedVisual->DestroyComponent();
		}
		PotenceRopeSkinnedVisuals.Remove(this);
	}

	if (USkeletalMeshComponent* TargetComponent = Target.Get())
	{
		TargetComponent->SetVisibility(bOriginalTargetVisible, false);
		TargetComponent->VisibilityBasedAnimTickOption = OriginalVisibilityTickOption;
	}
	Target.Reset();
	Super::OnComponentDestroyed(bDestroyingHierarchy);
}

void UProphecyPotenceRopeVisualComponent::UpdateRopeMesh()
{
	USkeletalMeshComponent* TargetComponent = Target.Get();
	const TWeakObjectPtr<UPoseableMeshComponent>* VisualEntry = PotenceRopeSkinnedVisuals.Find(this);
	UPoseableMeshComponent* SkinnedVisual = VisualEntry ? VisualEntry->Get() : nullptr;
	if (!TargetComponent || !SkinnedVisual || !TargetComponent->GetSkeletalMeshAsset())
	{
		return;
	}

	// First copy the exact simulated pose, including every collision-induced rotation.
	// The overrides below affect only the portion already reeled into the wood.
	SkinnedVisual->CopyPoseFromSkeletalComponent(TargetComponent);

	FTransform RootReferenceTransform;
	const bool bHasReferenceAnchor = GetReferenceBoneComponentTransform(
		TargetComponent->GetSkeletalMeshAsset(), PotenceRopeRootBone, RootReferenceTransform);
	const FTransform SimulatedRootTransform = TargetComponent->GetBoneTransform(PotenceRopeRootBone, RTS_Component);
	const FVector Anchor = bHasReferenceAnchor ? RootReferenceTransform.GetLocation() : SimulatedRootTransform.GetLocation();
	FVector RetractionDirection = FVector::UpVector;
	FTransform FirstSegmentReferenceTransform;
	if (bHasReferenceAnchor && GetReferenceBoneComponentTransform(
		TargetComponent->GetSkeletalMeshAsset(), MakePotenceRopeVisualBoneName(0), FirstSegmentReferenceTransform))
	{
		RetractionDirection = (Anchor - FirstSegmentReferenceTransform.GetLocation()).GetSafeNormal(
			SMALL_NUMBER, FVector::UpVector);
	}

	FTransform VisualRootTransform = SimulatedRootTransform;
	VisualRootTransform.SetLocation(Anchor);
	VisualRootTransform.SetScale3D(FVector::OneVector);
	SkinnedVisual->SetBoneTransformByName(PotenceRopeRootBone, VisualRootTransform, EBoneSpaces::ComponentSpace);

	const float SegmentProgress = RetractionAmount * static_cast<float>(PotenceRopeSegmentCount);
	for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
	{
		const FName BoneName = MakePotenceRopeVisualBoneName(SegmentIndex);
		FTransform VisualBoneTransform = TargetComponent->GetBoneTransform(BoneName, RTS_Component);
		const bool bConsumed = SegmentProgress - static_cast<float>(SegmentIndex) >= 1.0f;
		const bool bAboveAnchor = FVector::DotProduct(
			VisualBoneTransform.GetLocation() - Anchor, RetractionDirection) > 0.0f;
		if (bConsumed || bAboveAnchor)
		{
			// Do not scale the bone. Keeping the authored diameter eliminates the base
			// pinch; the collapsed full-size rings overlap inside the wood attachment.
			VisualBoneTransform.SetLocation(Anchor);
		}
		VisualBoneTransform.SetScale3D(FVector::OneVector);
		SkinnedVisual->SetBoneTransformByName(BoneName, VisualBoneTransform, EBoneSpaces::ComponentSpace);
	}
}
