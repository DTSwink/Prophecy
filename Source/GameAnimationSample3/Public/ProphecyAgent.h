#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "GameFramework/Pawn.h"
#include "PhysicsEngine/PhysicalAnimationComponent.h"
#include "ProphecyAgent.generated.h"

class UCapsuleComponent;
class UPrimitiveComponent;
class USkeletalMeshComponent;

USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyAgentHandle
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent")
	int32 Index = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent")
	int32 Generation = 0;

	bool IsValid() const
	{
		return Index != INDEX_NONE && Generation > 0;
	}

	friend bool operator==(const FProphecyAgentHandle& A, const FProphecyAgentHandle& B)
	{
		return A.Index == B.Index && A.Generation == B.Generation;
	}

	friend bool operator!=(const FProphecyAgentHandle& A, const FProphecyAgentHandle& B)
	{
		return !(A == B);
	}
};

FORCEINLINE uint32 GetTypeHash(const FProphecyAgentHandle& Handle)
{
	return HashCombineFast(GetTypeHash(Handle.Index), GetTypeHash(Handle.Generation));
}

UENUM(BlueprintType)
enum class EProphecyAgentSimulationMode : uint8
{
	Kinematic,
	Physical
};

/** Selects how a Physical agent follows the animated pose. */
UENUM(BlueprintType)
enum class EProphecyAgentPhysicalDriveMode : uint8
{
	/** One PhysicalAnimation world-space target and constraint per simulated body. */
	PerBodyWorld,

	/** Absolute world-space force and torque magnetization for every simulated lower-body rigid body. */
	RootAndJointTorque UMETA(DisplayName = "Absolute World Magnetization")
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FiveParams(
	FProphecyAgentPhysicalHitSignature,
	AProphecyAgent*, Agent,
	AActor*, OtherActor,
	UPrimitiveComponent*, OtherComponent,
	FVector, NormalImpulse,
	const FHitResult&, Hit);

/**
 * Lightweight runtime shell for one batched Prophecy agent.
 *
 * The pawn itself never ticks. The manager owns intent, NN inference, and root
 * updates. Only the skeletal mesh and physical-animation component do per-frame
 * work, and the physical-animation component is disabled outside Physical mode.
 */
UCLASS(BlueprintType, Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyAgent : public APawn
{
	GENERATED_BODY()

public:
	AProphecyAgent();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** True only for the possessed player shell; exposed for Blueprint event logic. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent", meta = (DisplayName = "Is Player"))
	bool bIsPlayer = false;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	FProphecyAgentHandle GetAgentHandle() const { return AgentHandle; }

	void SetAgentHandle(FProphecyAgentHandle InHandle) { AgentHandle = InHandle; }

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	EProphecyAgentSimulationMode GetSimulationMode() const { return SimulationMode; }

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent")
	bool SetSimulationMode(EProphecyAgentSimulationMode NewMode);

	/** Enable MACD on every Chaos body owned by this agent. Safe to change at runtime. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	void SetMACDEnabled(bool bEnabled);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Physical")
	bool IsMACDEnabled() const { return bMACDEnabled; }

	/** Must be selected while kinematic, before the physical drive has been configured. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	bool SetPhysicalDriveMode(EProphecyAgentPhysicalDriveMode NewMode);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Physical")
	EProphecyAgentPhysicalDriveMode GetPhysicalDriveMode() const { return PhysicalDriveMode; }

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	FVector GetRootLowPoint() const;

	/** Applies the manager root through the capsule sweep and reports its actual low point. */
	bool SetManagedRootLowPoint(
		const FVector& LowPoint,
		float YawDegrees,
		FVector& OutAppliedLowPoint,
		FVector& OutBlockingNormal,
		bool& bOutWorldStaticBlocked);
	/** One-time placement used before a bridge-spawned shell is made visible. */
	void TeleportManagedRootLowPoint(const FVector& LowPoint, float YawDegrees);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	UCapsuleComponent* GetAgentCapsule() const { return Capsule; }

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	USkeletalMeshComponent* GetAgentMesh() const { return Mesh; }

	/**
	 * Copies the already-published NN pose for Blueprint controllers.
	 * FutureWorldTransforms are the exact next 30 Hz targets; InterpolatedWorldTransforms
	 * are what the current Kinematic renderer would display on this game frame.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Manual NN Pose", meta = (DisplayName = "Read NN Future World Pose"))
	bool ReadNNFutureWorldPose(
		TArray<FName>& BoneNames,
		TArray<FTransform>& FutureWorldTransforms,
		TArray<FTransform>& InterpolatedWorldTransforms,
		float& InterpolationAlpha) const;

	/** Manually evaluates the existing viewer-matched Kinematic NN pose once. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Manual NN Pose", meta = (DisplayName = "Apply NN Pose Kinematically"))
	bool ApplyNNPoseKinematically(float DeltaSeconds);

	/** Disable automatic skeletal evaluation so Blueprint decides when the NN pose is applied. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Prophecy|Agent|Manual NN Pose")
	bool bManualNNPoseApplication = false;

	/** Stable authored mesh-to-capsule transform; Chaos overwrites the live relative transform while ragdolling. */
	FTransform GetAuthoredMeshRelativeTransform() const
	{
		return SimulationMode == EProphecyAgentSimulationMode::Physical
			? PhysicalTargetComponentRelativeTransform
			: Mesh->GetRelativeTransform();
	}

	/** Copies the finalized component-space bone transforms without allocating. */
	bool SampleActualComponentPose(
		TConstArrayView<FName> BoneNames,
		TArrayView<FTransform> OutComponentTransforms) const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical")
	FName PhysicalRootBodyName = TEXT("pelvis");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical")
	FPhysicalAnimationData PhysicalDriveSettings;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical", meta = (ClampMin = "0.0"))
	float PhysicalDriveStrengthMultiplier = 1.0f;

	/** Production default: one pelvis world target plus joint torque for the articulated limbs. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical")
	EProphecyAgentPhysicalDriveMode PhysicalDriveMode = EProphecyAgentPhysicalDriveMode::RootAndJointTorque;

	/** Keep this off for crowds; enable it only on agents whose hit events are needed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical")
	bool bGeneratePhysicalHitEvents = false;

	UPROPERTY(BlueprintAssignable, Category = "Prophecy|Agent|Physical")
	FProphecyAgentPhysicalHitSignature OnPhysicalHit;

private:
	void ApplyCollisionMode(EProphecyAgentSimulationMode Mode);
	void ApplyAbsoluteWorldMagnetization(float DeltaSeconds);

	UFUNCTION()
	void HandleMeshHit(
		UPrimitiveComponent* HitComponent,
		AActor* OtherActor,
		UPrimitiveComponent* OtherComponent,
		FVector NormalImpulse,
		const FHitResult& Hit);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UCapsuleComponent> Capsule;

	/** Blueprint subclasses may replace this component's mesh with any mesh using the same skeleton. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<USkeletalMeshComponent> Mesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UPhysicalAnimationComponent> PhysicalAnimation;

	UPROPERTY(VisibleAnywhere, Category = "Prophecy|Agent")
	FProphecyAgentHandle AgentHandle;

	UPROPERTY(VisibleAnywhere, Category = "Prophecy|Agent")
	EProphecyAgentSimulationMode SimulationMode = EProphecyAgentSimulationMode::Kinematic;

	bool bMACDEnabled = true;
	bool bPhysicalDriveConfigured = false;
	bool bHasPreviousPhysicalRootTarget = false;
	bool bSavedUpdateRateOptimizations = false;
	EVisibilityBasedAnimTickOption SavedVisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	FTransform PhysicalTargetComponentRelativeTransform = FTransform::Identity;
	FTransform PreviousPhysicalRootTarget = FTransform::Identity;
};
