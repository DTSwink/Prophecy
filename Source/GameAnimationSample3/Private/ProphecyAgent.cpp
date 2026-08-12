#include "ProphecyAgent.h"

#include "Chaos/ChaosConstraintSettings.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "GameFramework/Volume.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// These object channels are declared by name in DefaultEngine.ini.
	constexpr ECollisionChannel ProphecyAgentCapsuleChannel = ECC_GameTraceChannel8;
	constexpr ECollisionChannel ProphecyAgentLimbChannel = ECC_GameTraceChannel9;

	bool IsIgnoredNavigationBlocker(const AActor* Actor)
	{
		if (!Actor)
		{
			return false;
		}

		const FString ClassName = Actor->GetClass()->GetName();
		if (ClassName.StartsWith(TEXT("BP_Door")) ||
			ClassName.StartsWith(TEXT("BP_LogCabins_Shutter")) ||
			ClassName.StartsWith(TEXT("BP_StickHolder")))
		{
			return true;
		}

		const AStaticMeshActor* StaticMeshActor = Cast<AStaticMeshActor>(Actor);
		const UStaticMeshComponent* StaticMeshComponent = StaticMeshActor
			? StaticMeshActor->GetStaticMeshComponent()
			: nullptr;
		const UStaticMesh* StaticMesh = StaticMeshComponent
			? StaticMeshComponent->GetStaticMesh()
			: nullptr;
		if (!StaticMesh)
		{
			return false;
		}

		const FString MeshName = StaticMesh->GetName();
		return MeshName.StartsWith(TEXT("SM_Bench")) || MeshName.StartsWith(TEXT("SM_Barrel"));
	}
}

AProphecyAgent::AProphecyAgent()
{
	PrimaryActorTick.bCanEverTick = false;
	PrimaryActorTick.bStartWithTickEnabled = false;
	AutoPossessAI = EAutoPossessAI::Disabled;
	AutoPossessPlayer = EAutoReceiveInput::Disabled;

	Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
	Capsule->InitCapsuleSize(30.0f, 86.0f);
	Capsule->SetCollisionObjectType(ProphecyAgentCapsuleChannel);
	Capsule->SetGenerateOverlapEvents(false);
	Capsule->SetCanEverAffectNavigation(false);
	SetRootComponent(Capsule);

	Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Capsule);
	Mesh->SetRelativeLocation(FVector(0.0, 0.0, -86.0));
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->SetNotifyRigidBodyCollision(false);
	Mesh->OnComponentHit.AddDynamic(this, &AProphecyAgent::HandleMeshHit);
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> DefaultMesh(
		TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	if (DefaultMesh.Succeeded())
	{
		Mesh->SetSkeletalMesh(DefaultMesh.Object);
	}

	PhysicalAnimation = CreateDefaultSubobject<UPhysicalAnimationComponent>(TEXT("PhysicalAnimation"));
	PhysicalAnimation->SetComponentTickEnabled(false);

	PhysicalDriveSettings.bIsLocalSimulation = false;
	PhysicalDriveSettings.OrientationStrength = 1000.0f;
	PhysicalDriveSettings.AngularVelocityStrength = 100.0f;
	PhysicalDriveSettings.PositionStrength = 1000.0f;
	PhysicalDriveSettings.VelocityStrength = 100.0f;
	PhysicalDriveSettings.MaxLinearForce = 0.0f;
	PhysicalDriveSettings.MaxAngularForce = 0.0f;

	ApplyCollisionMode(EProphecyAgentSimulationMode::Kinematic);
}

void AProphecyAgent::BeginPlay()
{
	Super::BeginPlay();
	// Editor/gameplay volumes describe regions; they are not physical walls.
	// The project's custom capsule channel defaults to Block, so explicitly
	// exclude every AVolume from swept agent movement.
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->IsA<AVolume>() || IsIgnoredNavigationBlocker(*It))
		{
			Capsule->IgnoreActorWhenMoving(*It, true);
		}
	}
	PhysicalAnimation->SetSkeletalMeshComponent(Mesh);
	PhysicalAnimation->SetStrengthMultiplyer(0.0f);
	PhysicalAnimation->SetComponentTickEnabled(false);
	ApplyCollisionMode(SimulationMode);
}

bool AProphecyAgent::SetSimulationMode(EProphecyAgentSimulationMode NewMode)
{
	if (NewMode == SimulationMode)
	{
		return true;
	}

	if (NewMode == EProphecyAgentSimulationMode::Physical)
	{
		UPhysicsAsset* PhysicsAsset = Mesh->GetPhysicsAsset();
		if (!Mesh->GetSkeletalMeshAsset() || !PhysicsAsset || PhysicsAsset->FindBodyIndex(PhysicalRootBodyName) == INDEX_NONE)
		{
			return false;
		}

		if (PhysicalAnimation->GetSkeletalMesh() != Mesh)
		{
			PhysicalAnimation->SetSkeletalMeshComponent(Mesh);
		}

		// Named body iteration requires a created physics state in UE 5.7.
		ApplyCollisionMode(EProphecyAgentSimulationMode::Physical);
		Mesh->SetNotifyRigidBodyCollision(bGeneratePhysicalHitEvents);
		SetMACDEnabled(bMACDEnabled);

		if (!bPhysicalDriveConfigured)
		{
			if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
			{
				// Anchor only the pelvis in world space. Child bodies remain linked by the
				// PhysicsAsset constraints and are angularly driven toward the anim pose.
				PhysicalAnimation->ApplyPhysicalAnimationSettings(
					PhysicalRootBodyName,
					PhysicalDriveSettings);
			}
			else
			{
				PhysicalAnimation->ApplyPhysicalAnimationSettingsBelow(
					PhysicalRootBodyName,
					PhysicalDriveSettings,
					true);
			}
			bPhysicalDriveConfigured = true;
		}

		Mesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, true, true);
		Mesh->SetAllBodiesBelowPhysicsBlendWeight(PhysicalRootBodyName, 1.0f, false, true);
		if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
		{
			for (FConstraintInstance* Constraint : Mesh->Constraints)
			{
				if (Constraint)
				{
					Constraint->SetAngularDriveMode(EAngularDriveMode::TwistAndSwing);
				}
			}
			Mesh->SetAllMotorsAngularDriveParams(
				PhysicalDriveSettings.OrientationStrength * PhysicalDriveStrengthMultiplier * Chaos::ConstraintSettings::AngularDriveStiffnessScale(),
				PhysicalDriveSettings.AngularVelocityStrength * PhysicalDriveStrengthMultiplier * Chaos::ConstraintSettings::AngularDriveDampingScale(),
				PhysicalDriveSettings.MaxAngularForce * PhysicalDriveStrengthMultiplier,
				false);
			Mesh->SetAllMotorsAngularPositionDrive(true, true, false);
			Mesh->SetAllMotorsAngularVelocityDrive(true, true, false);
			Mesh->bUpdateJointsFromAnimation = true;
		}
		else
		{
			Mesh->bUpdateJointsFromAnimation = false;
		}
		PhysicalAnimation->SetStrengthMultiplyer(PhysicalDriveStrengthMultiplier);
		PhysicalAnimation->SetComponentTickEnabled(true);
		Mesh->WakeAllRigidBodies();
		SimulationMode = NewMode;
		return true;
	}

	PhysicalAnimation->SetStrengthMultiplyer(0.0f);
	if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
	{
		Mesh->bUpdateJointsFromAnimation = false;
		Mesh->SetAllMotorsAngularPositionDrive(false, false, false);
		Mesh->SetAllMotorsAngularVelocityDrive(false, false, false);
	}
	Mesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, false, true);
	Mesh->SetAllBodiesBelowPhysicsBlendWeight(PhysicalRootBodyName, 0.0f, false, true);
	Mesh->SetNotifyRigidBodyCollision(false);
	ApplyCollisionMode(EProphecyAgentSimulationMode::Kinematic);
	PhysicalAnimation->SetComponentTickEnabled(false);
	SimulationMode = NewMode;
	return true;
}

void AProphecyAgent::ApplyCollisionMode(EProphecyAgentSimulationMode Mode)
{
	Capsule->SetCollisionObjectType(ProphecyAgentCapsuleChannel);
	Capsule->SetGenerateOverlapEvents(false);
	Mesh->SetCollisionObjectType(ProphecyAgentLimbChannel);
	Mesh->SetGenerateOverlapEvents(false);

	if (Mode == EProphecyAgentSimulationMode::Physical)
	{
		// The managed root capsule supports the agent on static ground, but never
		// participates in agent-agent collision. The actual limbs own those contacts.
		Capsule->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Capsule->SetCollisionResponseToAllChannels(ECR_Ignore);
		Capsule->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);

		Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Mesh->SetCollisionResponseToAllChannels(ECR_Block);
		Mesh->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
		Mesh->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
		return;
	}

	// Kinematic agents use one cheap capsule. It blocks other kinematic capsules
	// and Physical limbs. A Physical capsule ignores this channel from its side.
	Capsule->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Capsule->SetCollisionResponseToAllChannels(ECR_Block);
	Capsule->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
	Capsule->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetCollisionResponseToAllChannels(ECR_Block);
}

bool AProphecyAgent::SetPhysicalDriveMode(EProphecyAgentPhysicalDriveMode NewMode)
{
	if (SimulationMode != EProphecyAgentSimulationMode::Kinematic || bPhysicalDriveConfigured)
	{
		return false;
	}

	PhysicalDriveMode = NewMode;
	return true;
}

void AProphecyAgent::SetMACDEnabled(bool bEnabled)
{
	bMACDEnabled = bEnabled;

	// UPrimitiveComponent::SetAllUseMACD does not iterate USkeletalMeshComponent::Bodies
	// in UE 5.7, so apply the runtime flag to every rigid body explicitly.
	for (FBodyInstance* BodyInstance : Mesh->Bodies)
	{
		if (BodyInstance)
		{
			BodyInstance->SetUseMACD(bEnabled);
		}
	}
}

FVector AProphecyAgent::GetRootLowPoint() const
{
	return Capsule->GetComponentLocation() - Capsule->GetUpVector() * Capsule->GetScaledCapsuleHalfHeight();
}

bool AProphecyAgent::SetManagedRootLowPoint(
	const FVector& LowPoint,
	float YawDegrees,
	FVector& OutAppliedLowPoint,
	FVector& OutBlockingNormal,
	bool& bOutWorldStaticBlocked)
{
	SetActorRotation(FRotator(0.0, YawDegrees, 0.0), ETeleportType::None);
	const FVector TargetLocation = LowPoint + FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight();
	FHitResult Hit;
	SetActorLocation(
		TargetLocation,
		true,
		&Hit,
		ETeleportType::None);
	OutBlockingNormal = FVector::ZeroVector;
	bOutWorldStaticBlocked = false;
	if (Hit.bBlockingHit)
	{
		bOutWorldStaticBlocked = Hit.Component.IsValid() &&
			Hit.Component->GetCollisionObjectType() == ECC_WorldStatic;
		OutBlockingNormal = Hit.Normal.GetSafeNormal2D();
		if (Hit.bStartPenetrating && !OutBlockingNormal.IsNearlyZero())
		{
			// Standard minimal-translation depenetration: move only far enough to
			// leave the blocking surface, then preserve the tangential intent.
			SetActorLocation(
				GetActorLocation() + OutBlockingNormal * (Hit.PenetrationDepth + 0.5f),
				false,
				nullptr,
				ETeleportType::None);
		}

		const FVector RemainingDelta = TargetLocation - GetActorLocation();
		const FVector SlideDelta = FVector::VectorPlaneProject(RemainingDelta, OutBlockingNormal);
		if (!SlideDelta.IsNearlyZero())
		{
			FHitResult SlideHit;
			SetActorLocation(GetActorLocation() + SlideDelta, true, &SlideHit, ETeleportType::None);
			if (SlideHit.bBlockingHit)
			{
				const FVector SlideNormal = SlideHit.Normal.GetSafeNormal2D();
				if (!SlideNormal.IsNearlyZero()) OutBlockingNormal = SlideNormal;
			}
		}
	}
	OutAppliedLowPoint = GetRootLowPoint();
	return Hit.bBlockingHit;
}

void AProphecyAgent::TeleportManagedRootLowPoint(const FVector& LowPoint, float YawDegrees)
{
	SetActorRotation(FRotator(0.0, YawDegrees, 0.0), ETeleportType::TeleportPhysics);
	SetActorLocation(
		LowPoint + FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight(),
		false,
		nullptr,
		ETeleportType::TeleportPhysics);
}

bool AProphecyAgent::SampleActualComponentPose(
	TConstArrayView<FName> BoneNames,
	TArrayView<FTransform> OutComponentTransforms) const
{
	if (BoneNames.Num() != OutComponentTransforms.Num() || !Mesh->IsRegistered())
	{
		return false;
	}

	const TArray<FTransform>& ComponentSpaceTransforms = Mesh->GetComponentSpaceTransforms();
	for (int32 Index = 0; Index < BoneNames.Num(); ++Index)
	{
		const int32 BoneIndex = Mesh->GetBoneIndex(BoneNames[Index]);
		if (!ComponentSpaceTransforms.IsValidIndex(BoneIndex))
		{
			return false;
		}
		OutComponentTransforms[Index] = ComponentSpaceTransforms[BoneIndex];
	}
	return true;
}

void AProphecyAgent::HandleMeshHit(
	UPrimitiveComponent* HitComponent,
	AActor* OtherActor,
	UPrimitiveComponent* OtherComponent,
	FVector NormalImpulse,
	const FHitResult& Hit)
{
	if (SimulationMode == EProphecyAgentSimulationMode::Physical && bGeneratePhysicalHitEvents)
	{
		OnPhysicalHit.Broadcast(this, OtherActor, OtherComponent, NormalImpulse, Hit);
	}
}
