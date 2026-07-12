#include "ProphecyDoubleReachBallTest.h"

#include "Chaos/ChaosEngineInterface.h"
#include "Components/BoxComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "ProphecyDoubleReachCharacter.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
constexpr int32 WallCount = 6;
constexpr double MinimumVelocitySquared = 1.0;
}

AProphecyDoubleReachBallTest::AProphecyDoubleReachBallTest()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	SceneRoot->SetMobility(EComponentMobility::Static);

	for (int32 Index = 0; Index < WallCount; ++Index)
	{
		UBoxComponent* Wall = CreateDefaultSubobject<UBoxComponent>(
			*FString::Printf(TEXT("BoundaryWall%d"), Index));
		Wall->SetupAttachment(SceneRoot);
		Wall->SetMobility(EComponentMobility::Static);
		Wall->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Wall->SetCollisionObjectType(ECC_WorldStatic);
		Wall->SetCollisionResponseToAllChannels(ECR_Ignore);
		Wall->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
		Wall->SetGenerateOverlapEvents(false);
		Wall->SetCanEverAffectNavigation(false);
		Wall->SetHiddenInGame(true);
		Wall->SetVisibility(false);
		BoundaryWalls.Add(Wall);
	}

	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));

	auto CreateBall = [&](const TCHAR* Name)
	{
		UStaticMeshComponent* Ball = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Ball->SetupAttachment(SceneRoot);
		Ball->SetMobility(EComponentMobility::Movable);
		Ball->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Ball->SetCollisionObjectType(ECC_PhysicsBody);
		Ball->SetCollisionResponseToAllChannels(ECR_Ignore);
		Ball->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
		Ball->SetGenerateOverlapEvents(false);
		Ball->SetCanEverAffectNavigation(false);
		Ball->SetCastShadow(true);
		if (SphereMesh.Succeeded())
		{
			Ball->SetStaticMesh(SphereMesh.Object);
		}
		return Ball;
	};

	LeftBall = CreateBall(TEXT("LeftBall"));
	RightBall = CreateBall(TEXT("RightBall"));
	TestCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("TestCamera"));
	TestCamera->SetupAttachment(SceneRoot);
	TestCamera->SetRelativeLocation(FVector(420.0, 0.0, 155.0));
	TestCamera->SetRelativeRotation(FRotator(-3.0, 180.0, 0.0));
	TestCamera->SetFieldOfView(55.0f);
	TestCamera->SetAutoActivate(true);
	ReachCharacterClass = AProphecyDoubleReachCharacter::StaticClass();
	UpdateBoundsGeometry();
}

void AProphecyDoubleReachBallTest::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	UpdateBoundsGeometry();
}

void AProphecyDoubleReachBallTest::BeginPlay()
{
	Super::BeginPlay();

	BouncePhysicalMaterial = NewObject<UPhysicalMaterial>(this, TEXT("PerpetualBouncePhysicalMaterial"));
	BouncePhysicalMaterial->Friction = 0.0f;
	BouncePhysicalMaterial->Restitution = 1.0f;
	BouncePhysicalMaterial->bOverrideFrictionCombineMode = true;
	BouncePhysicalMaterial->FrictionCombineMode = EFrictionCombineMode::Min;
	BouncePhysicalMaterial->bOverrideRestitutionCombineMode = true;
	BouncePhysicalMaterial->RestitutionCombineMode = EFrictionCombineMode::Max;

	for (UBoxComponent* Wall : BoundaryWalls)
	{
		if (Wall)
		{
			Wall->SetPhysMaterialOverride(BouncePhysicalMaterial);
		}
	}

	if (UMaterialInstanceDynamic* LeftMaterial = LeftBall->CreateAndSetMaterialInstanceDynamic(0))
	{
		LeftMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.12f, 0.82f, 0.78f, 1.0f));
	}
	if (UMaterialInstanceDynamic* RightMaterial = RightBall->CreateAndSetMaterialInstanceDynamic(0))
	{
		RightMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.95f, 0.55f, 0.12f, 1.0f));
	}

	ConfigureBall(LeftBall, LeftBallInitialDirection);
	ConfigureBall(RightBall, RightBallInitialDirection);
	SpawnOrAcquireReachCharacter();
	UpdateReachTargets();
	if (bAutoViewOnBeginPlay)
	{
		if (APlayerController* PlayerController = GetWorld()->GetFirstPlayerController())
		{
			PlayerController->SetViewTarget(this);
		}
	}
}

void AProphecyDoubleReachBallTest::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (bOwnsReachCharacter && IsValid(ActiveReachCharacter))
	{
		ActiveReachCharacter->Destroy();
	}
	ActiveReachCharacter = nullptr;
	bOwnsReachCharacter = false;
	Super::EndPlay(EndPlayReason);
}

void AProphecyDoubleReachBallTest::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	MaintainBall(LeftBall, LeftBallInitialDirection);
	MaintainBall(RightBall, RightBallInitialDirection);
	UpdateReachTargets();

	if (bDrawBounds && GetWorld())
	{
		DrawDebugBox(
			GetWorld(),
			GetActorTransform().TransformPosition(BoxCenterOffset),
			BoxHalfExtent,
			GetActorQuat(),
			FColor::White,
			false,
			0.0f,
			0,
			1.5f);
	}
}

void AProphecyDoubleReachBallTest::ResetBalls()
{
	UpdateBoundsGeometry();
	ConfigureBall(LeftBall, LeftBallInitialDirection);
	ConfigureBall(RightBall, RightBallInitialDirection);
}

void AProphecyDoubleReachBallTest::UpdateBoundsGeometry()
{
	if (BoundaryWalls.Num() != WallCount || !LeftBall || !RightBall)
	{
		return;
	}

	const FVector Half(
		FMath::Max(30.0, BoxHalfExtent.X),
		FMath::Max(30.0, BoxHalfExtent.Y),
		FMath::Max(30.0, BoxHalfExtent.Z));
	const double Thickness = FMath::Max(1.0f, WallThicknessCm);
	const double WallHalf = Thickness * 0.5;

	BoundaryWalls[0]->SetRelativeLocation(BoxCenterOffset + FVector(Half.X + WallHalf, 0.0, 0.0));
	BoundaryWalls[0]->SetBoxExtent(FVector(WallHalf, Half.Y + Thickness, Half.Z + Thickness));
	BoundaryWalls[1]->SetRelativeLocation(BoxCenterOffset - FVector(Half.X + WallHalf, 0.0, 0.0));
	BoundaryWalls[1]->SetBoxExtent(FVector(WallHalf, Half.Y + Thickness, Half.Z + Thickness));
	BoundaryWalls[2]->SetRelativeLocation(BoxCenterOffset + FVector(0.0, Half.Y + WallHalf, 0.0));
	BoundaryWalls[2]->SetBoxExtent(FVector(Half.X + Thickness, WallHalf, Half.Z + Thickness));
	BoundaryWalls[3]->SetRelativeLocation(BoxCenterOffset - FVector(0.0, Half.Y + WallHalf, 0.0));
	BoundaryWalls[3]->SetBoxExtent(FVector(Half.X + Thickness, WallHalf, Half.Z + Thickness));
	BoundaryWalls[4]->SetRelativeLocation(BoxCenterOffset + FVector(0.0, 0.0, Half.Z + WallHalf));
	BoundaryWalls[4]->SetBoxExtent(FVector(Half.X + Thickness, Half.Y + Thickness, WallHalf));
	BoundaryWalls[5]->SetRelativeLocation(BoxCenterOffset - FVector(0.0, 0.0, Half.Z + WallHalf));
	BoundaryWalls[5]->SetBoxExtent(FVector(Half.X + Thickness, Half.Y + Thickness, WallHalf));

	const double SafeRadius = FMath::Clamp<double>(BallRadiusCm, 2.0, Half.GetMin() - 2.0);
	const FVector BallScale(SafeRadius / 50.0);
	LeftBall->SetRelativeScale3D(BallScale);
	RightBall->SetRelativeScale3D(BallScale);
	if (!LeftBall->IsSimulatingPhysics())
	{
		LeftBall->SetRelativeLocation(BoxCenterOffset + LeftBallStartOffset);
	}
	if (!RightBall->IsSimulatingPhysics())
	{
		RightBall->SetRelativeLocation(BoxCenterOffset + RightBallStartOffset);
	}
}

void AProphecyDoubleReachBallTest::ConfigureBall(
	UStaticMeshComponent* Ball,
	const FVector& InitialDirection)
{
	if (!Ball)
	{
		return;
	}

	const bool bIsLeftBall = Ball == LeftBall;
	const FVector StartOffset = bIsLeftBall ? LeftBallStartOffset : RightBallStartOffset;
	const FVector StartWorld = GetActorTransform().TransformPosition(BoxCenterOffset + StartOffset);
	Ball->SetSimulatePhysics(false);
	Ball->SetWorldLocation(StartWorld, false, nullptr, ETeleportType::TeleportPhysics);
	Ball->SetWorldRotation(FQuat::Identity, false, nullptr, ETeleportType::TeleportPhysics);
	Ball->SetPhysMaterialOverride(BouncePhysicalMaterial);
	Ball->SetEnableGravity(false);
	Ball->SetLinearDamping(0.0f);
	Ball->SetAngularDamping(0.0f);
	Ball->SetUseCCD(true);
	Ball->BodyInstance.bStartAwake = true;
	Ball->BodyInstance.SleepFamily = ESleepFamily::Custom;
	Ball->BodyInstance.CustomSleepThresholdMultiplier = 0.0f;
	Ball->BodyInstance.StabilizationThresholdMultiplier = 0.0f;
	Ball->SetSimulatePhysics(true);
	Ball->SetPhysicsLinearVelocity(
		GetActorTransform().TransformVectorNoScale(InitialDirection.GetSafeNormal())
			* FMath::Max(1.0f, BallSpeedCmPerSecond));
	Ball->WakeAllRigidBodies();
}

void AProphecyDoubleReachBallTest::MaintainBall(
	UStaticMeshComponent* Ball,
	const FVector& FallbackDirection)
{
	if (!Ball || !Ball->IsSimulatingPhysics())
	{
		return;
	}

	const FTransform ActorTransform = GetActorTransform();
	const FVector LocalPosition = ActorTransform.InverseTransformPosition(Ball->GetComponentLocation()) - BoxCenterOffset;
	const double Radius = FMath::Max(2.0f, BallRadiusCm);
	const FVector Limit(
		FMath::Max(1.0, BoxHalfExtent.X - Radius),
		FMath::Max(1.0, BoxHalfExtent.Y - Radius),
		FMath::Max(1.0, BoxHalfExtent.Z - Radius));
	const FVector Clamped(
		FMath::Clamp(LocalPosition.X, -Limit.X, Limit.X),
		FMath::Clamp(LocalPosition.Y, -Limit.Y, Limit.Y),
		FMath::Clamp(LocalPosition.Z, -Limit.Z, Limit.Z));

	FVector Velocity = Ball->GetPhysicsLinearVelocity();
	if (!LocalPosition.Equals(Clamped, 2.0))
	{
		FVector LocalVelocity = ActorTransform.InverseTransformVectorNoScale(Velocity);
		if (!FMath::IsNearlyEqual(LocalPosition.X, Clamped.X))
		{
			LocalVelocity.X *= -1.0;
		}
		if (!FMath::IsNearlyEqual(LocalPosition.Y, Clamped.Y))
		{
			LocalVelocity.Y *= -1.0;
		}
		if (!FMath::IsNearlyEqual(LocalPosition.Z, Clamped.Z))
		{
			LocalVelocity.Z *= -1.0;
		}
		Velocity = ActorTransform.TransformVectorNoScale(LocalVelocity);
		Ball->SetWorldLocation(
			ActorTransform.TransformPosition(BoxCenterOffset + Clamped),
			false,
			nullptr,
			ETeleportType::TeleportPhysics);
	}

	if (bMaintainBallSpeed)
	{
		const double Speed = FMath::Max(1.0f, BallSpeedCmPerSecond);
		if (Velocity.SizeSquared() <= MinimumVelocitySquared)
		{
			Velocity = ActorTransform.TransformVectorNoScale(FallbackDirection.GetSafeNormal()) * Speed;
		}
		else
		{
			Velocity = Velocity.GetSafeNormal() * Speed;
		}
		Ball->SetPhysicsLinearVelocity(Velocity);
	}
	Ball->WakeAllRigidBodies();
}

void AProphecyDoubleReachBallTest::SpawnOrAcquireReachCharacter()
{
	ActiveReachCharacter = ReachCharacterOverride;
	bOwnsReachCharacter = false;
	if (!ActiveReachCharacter && ReachCharacterClass && GetWorld())
	{
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.Owner = this;
		SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		ActiveReachCharacter = GetWorld()->SpawnActor<AProphecyDoubleReachCharacter>(
			ReachCharacterClass,
			GetActorTransform().TransformPosition(CharacterSpawnOffset),
			GetActorRotation(),
			SpawnParameters);
		bOwnsReachCharacter = ActiveReachCharacter != nullptr;
	}

	if (ActiveReachCharacter)
	{
		ActiveReachCharacter->TransitionDuration = ReachTransitionDuration;
		ActiveReachCharacter->bShowTargetMarkers = false;
		if (ActiveReachCharacter->LeftReachTarget)
		{
			ActiveReachCharacter->LeftReachTarget->SetVisibility(false, true);
			ActiveReachCharacter->LeftReachTarget->SetHiddenInGame(true, true);
		}
		if (ActiveReachCharacter->RightReachTarget)
		{
			ActiveReachCharacter->RightReachTarget->SetVisibility(false, true);
			ActiveReachCharacter->RightReachTarget->SetHiddenInGame(true, true);
		}
		if (USkeletalMeshComponent* CharacterMesh = ActiveReachCharacter->GetMesh())
		{
			CharacterMesh->VisibilityBasedAnimTickOption =
				EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		}
		ActiveReachCharacter->SetReachMode(EProphecyDoubleReachMode::Both);
	}
}

void AProphecyDoubleReachBallTest::UpdateReachTargets()
{
	if (!IsValid(ActiveReachCharacter) || !LeftBall || !RightBall)
	{
		return;
	}
	ActiveReachCharacter->SetReachTargetsWorld(
		LeftBall->GetComponentLocation(),
		RightBall->GetComponentLocation());
}
