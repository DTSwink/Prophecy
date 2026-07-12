#include "ProphecyDoubleReachCharacter.h"

#include "Animation/AnimSequenceBase.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProphecyDoubleReachAnimInstance.h"
#include "UObject/ConstructorHelpers.h"

AProphecyDoubleReachCharacter::AProphecyDoubleReachCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(42.0f, 88.0f);
	GetMesh()->SetRelativeLocation(FVector(0.0, 0.0, -88.0));
	GetMesh()->SetRelativeRotation(FRotator(0.0, -90.0, 0.0));
	GetMesh()->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	GetMesh()->SetAnimInstanceClass(UProphecyDoubleReachAnimInstance::StaticClass());

	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MannequinMesh(
		TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	if (MannequinMesh.Succeeded())
	{
		GetMesh()->SetSkeletalMeshAsset(MannequinMesh.Object);
	}

	static ConstructorHelpers::FObjectFinder<UAnimSequenceBase> IdleAnimation(
		TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop.M_Neutral_Stand_Idle_Loop"));
	if (IdleAnimation.Succeeded())
	{
		BaseAnimation = IdleAnimation.Object;
	}

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));

	LeftReachTarget = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("LeftReachTarget"));
	LeftReachTarget->SetupAttachment(GetCapsuleComponent());
	LeftReachTarget->SetRelativeLocation(FVector(75.0, -30.0, 37.0));
	LeftReachTarget->SetRelativeScale3D(FVector(0.12));
	LeftReachTarget->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	LeftReachTarget->SetGenerateOverlapEvents(false);
	LeftReachTarget->SetCastShadow(false);

	RightReachTarget = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("RightReachTarget"));
	RightReachTarget->SetupAttachment(GetCapsuleComponent());
	RightReachTarget->SetRelativeLocation(FVector(75.0, 30.0, 37.0));
	RightReachTarget->SetRelativeScale3D(FVector(0.12));
	RightReachTarget->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	RightReachTarget->SetGenerateOverlapEvents(false);
	RightReachTarget->SetCastShadow(false);

	if (CubeMesh.Succeeded())
	{
		LeftReachTarget->SetStaticMesh(CubeMesh.Object);
		RightReachTarget->SetStaticMesh(CubeMesh.Object);
	}
}

void AProphecyDoubleReachCharacter::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	UpdateTargetMarkerVisibility();
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::BeginPlay()
{
	Super::BeginPlay();

	if (UMaterialInstanceDynamic* LeftMaterial = LeftReachTarget->CreateAndSetMaterialInstanceDynamic(0))
	{
		LeftMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.12f, 0.82f, 0.78f, 1.0f));
	}
	if (UMaterialInstanceDynamic* RightMaterial = RightReachTarget->CreateAndSetMaterialInstanceDynamic(0))
	{
		RightMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.95f, 0.55f, 0.12f, 1.0f));
	}

	UpdateTargetMarkerVisibility();
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::SetReachMode(const EProphecyDoubleReachMode NewMode)
{
	ReachMode = NewMode;
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::SetReachTargetsWorld(
	const FVector LeftWorldLocation,
	const FVector RightWorldLocation)
{
	SetLeftReachTargetWorld(LeftWorldLocation);
	SetRightReachTargetWorld(RightWorldLocation);
}

void AProphecyDoubleReachCharacter::SetLeftReachTargetWorld(const FVector WorldLocation)
{
	if (LeftReachTarget)
	{
		LeftReachTarget->SetWorldLocation(WorldLocation);
	}
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::SetRightReachTargetWorld(const FVector WorldLocation)
{
	if (RightReachTarget)
	{
		RightReachTarget->SetWorldLocation(WorldLocation);
	}
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::SetBaseAnimation(UAnimSequenceBase* NewAnimation)
{
	BaseAnimation = NewAnimation;
	SyncAnimInstance();
}

void AProphecyDoubleReachCharacter::SyncAnimInstance()
{
	USkeletalMeshComponent* CharacterMesh = GetMesh();
	if (!CharacterMesh || !LeftReachTarget || !RightReachTarget)
	{
		return;
	}

	UProphecyDoubleReachAnimInstance* ReachAnim =
		Cast<UProphecyDoubleReachAnimInstance>(CharacterMesh->GetAnimInstance());
	if (!ReachAnim)
	{
		return;
	}

	ReachAnim->BaseAnimation = BaseAnimation;
	ReachAnim->AnimationPlayRate = AnimationPlayRate;
	ReachAnim->bLoopAnimation = bLoopAnimation;
	ReachAnim->TransitionDuration = TransitionDuration;
	ReachAnim->bEnableUpperBodyMotionLimit = bEnableUpperBodyMotionLimit;
	ReachAnim->UpperBodySmoothingHalfLife = UpperBodySmoothingHalfLife;
	ReachAnim->MaxPelvisTranslationSpeedCmPerSecond = MaxPelvisTranslationSpeedCmPerSecond;
	ReachAnim->MaxSpineAngularSpeedDegreesPerSecond = MaxSpineAngularSpeedDegreesPerSecond;
	ReachAnim->MaxHandVelocityCmPerSecond = MaxHandVelocityCmPerSecond;
	ReachAnim->MaxElbowVelocityCmPerSecond = MaxElbowVelocityCmPerSecond;
	ReachAnim->ReachMode = ReachMode;

	const FTransform MeshToWorld = CharacterMesh->GetComponentTransform();
	ReachAnim->LeftTargetComponentSpace = MeshToWorld.InverseTransformPosition(LeftReachTarget->GetComponentLocation());
	ReachAnim->RightTargetComponentSpace = MeshToWorld.InverseTransformPosition(RightReachTarget->GetComponentLocation());
}

void AProphecyDoubleReachCharacter::UpdateTargetMarkerVisibility()
{
	if (LeftReachTarget)
	{
		LeftReachTarget->SetVisibility(bShowTargetMarkers, true);
		LeftReachTarget->SetHiddenInGame(!bShowTargetMarkers, true);
	}
	if (RightReachTarget)
	{
		RightReachTarget->SetVisibility(bShowTargetMarkers, true);
		RightReachTarget->SetHiddenInGame(!bShowTargetMarkers, true);
	}
}
