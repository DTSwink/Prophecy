#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "GameFramework/Pawn.h"
#include "PhysicsEngine/PhysicalAnimationComponent.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyAttackFistTypes.h"
#include "ProphecyAgent.generated.h"

class UCapsuleComponent;
class UCameraComponent;
class UPrimitiveComponent;
class USpringArmComponent;
class UAnimSequenceBase;
class UAnimSequence;
class UPhysicsAsset;
class USkeletalMeshComponent;
class UStaticMesh;

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
	Kinematic = 0,
	Physical = 1 UMETA(DisplayName = "Sim"),
	/** Native physical animation on the existing pose mesh, with real colliders. */
	HalfSim = 2 UMETA(DisplayName = "Half Sim")
};

/** Persistent input to the existing mover, not a velocity or a pose override. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyLocomotionInput
{
	GENERATED_BODY()

	/** World XY direction times stick amplitude (0..1). Z is ignored. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input")
	FVector WorldMoveInput = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input")
	bool bRun = false;

	/** World XY facing direction, independent of movement. Zero preserves the facing target. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input")
	FVector FacingWorldDirection = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input",
		meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float SpeedScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input",
		meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float TurnScale = 1.0f;
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

/** Recurrent physical-feedback deadband for one controlled skeleton bone. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyPhysicalFeedbackToleranceSettings
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical Feedback",
		meta = (ClampMin = "0.0", Units = "cm"))
	float LinearToleranceCm = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical Feedback",
		meta = (ClampMin = "0.0", Units = "deg"))
	float AngularToleranceDegrees = 0.0f;
};

/** Runtime configuration for one Physics Asset body in absolute-world magnetization mode. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyBodyMagnetizationSettings
{
	GENERATED_BODY()

	/** Include this body when Physical mode is initialized. Change while Kinematic. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization")
	bool bSimulateBody = true;

	/** Apply the native world-space magnetization force and torque to this body. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization")
	bool bMagnetizationEnabled = true;

	/** Multiplies the exact position-tracking acceleration. Zero disables position pull. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization",
		meta = (ClampMin = "0.0"))
	float LinearStrengthScale = 1.0f;

	/** Multiplies the exact rotation-tracking acceleration. Zero disables rotation pull. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization",
		meta = (ClampMin = "0.0"))
	float AngularStrengthScale = 1.0f;

	/** Cancel gravity for this body as part of its linear magnetization force. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization")
	bool bCancelGravity = true;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_FiveParams(
	FProphecyAgentPhysicalHitSignature,
	AProphecyAgent*, Agent,
	AActor*, OtherActor,
	UPrimitiveComponent*, OtherComponent,
	FVector, NormalImpulse,
	const FHitResult&, Hit);

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(
	FProphecyAgentAnimationLayerSignature,
	UAnimSequenceBase*, Animation);

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
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** Existing user Blueprint. Equip Sword spawns an instance; it never edits this asset. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Sword")
	TSoftClassPtr<AActor> SwordBlueprint = TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C")));

	/** Original sword geometry with the training transform's tiny shear baked in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Sword")
	TSoftObjectPtr<UStaticMesh> SwordTrainingMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(
		TEXT("/Game/_mygame/sword/geometry/Sword_GL01_Training.Sword_GL01_Training")));

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Sword")
	FName SwordHandSocket = TEXT("hand_r");

	/** Mesh-to-hand transform calibrated from the accepted Slash training handoff. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Sword")
	FTransform SwordGripTransform = FTransform(
		FQuat(-0.020187416964488277, -0.10610846088390578, 0.6210491947126335, 0.7762933469197968),
		FVector(-7.1119709819428465, 2.7136660691211247, -0.10802111799378267),
		FVector(0.8377267802922563, 0.7661935080608141, 1.3119414990256073));

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Sword", meta = (ClampMin = "0.01", Units = "kg"))
	float SwordMassKg = 1.0f;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Sword")
	bool EquipSword(bool bSimulated = true);

	/** False: attached child of the current hand. True: simulated body held by a fixed constraint. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Sword")
	bool SetSwordSimulated(bool bSimulated);

	/** Detaches the held instance, preserves momentum and enables free physics. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Sword")
	AActor* DropSword();

	/** Despawns only the held instance. Equip Sword makes a new one. Dropped swords are unaffected. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Sword")
	void HideSword();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Sword")
	AActor* GetHeldSword() const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Sword")
	bool IsSwordSimulated() const;

	/** True only for the possessed player shell; exposed for Blueprint event logic. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent", meta = (DisplayName = "Is Player"))
	bool bIsPlayer = false;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	FProphecyAgentHandle GetAgentHandle() const { return AgentHandle; }

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent")
	void SetAgentHandle(FProphecyAgentHandle InHandle) { AgentHandle = InHandle; }

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	bool HasValidAgentHandle() const { return AgentHandle.IsValid(); }

	/** Input setters enable this automatically. False leaves crowd/bridge intent ownership intact. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input")
	bool bUseBlueprintLocomotionInput = false;

	/** Held until changed, including between 30 Hz steps. Native code never reads keys for this input. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Locomotion Input")
	FProphecyLocomotionInput LocomotionInput;

	/** Sets intent only; the existing mover still owns acceleration, collision and future roots.
	 * WorldMoveInput length is stick amplitude, not cm/s. FacingWorldDirection zero keeps facing.
	 * Safe before manager registration. Full-body attacks temporarily suppress movement as before.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Locomotion Input")
	void SetLocomotionInput(FVector WorldMoveInput, bool bRun, FVector FacingWorldDirection,
		float SpeedScale = 1.0f, float TurnScale = 1.0f);

	/** Changes gait without replacing movement, facing or scales. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Locomotion Input")
	void SetLocomotionRunning(bool bRun);

	/** Zero stick and preserve the facing target; brakes through the mover, never zeros velocity. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Locomotion Input")
	void StopLocomotionInput();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Locomotion Input")
	FProphecyLocomotionInput GetLocomotionInput() const { return LocomotionInput; }

	/** Actual fixed-step mover velocity in world cm/s, facing direction and active gait.
	 * Returns false before this pawn is registered as a mover-controlled agent.
	 */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Locomotion Input")
	bool GetLocomotionState(FVector& WorldVelocityCmPerSecond, FVector& FacingWorldDirection, bool& bRun) const;

	/** Goal consumed by the most recent 30 Hz mover step, not its current motion.
	 * Includes stick/scales, directional gait limits, run turn boost and attack overrides.
	 * Facing is the final heading goal, not this frame's partially turned orientation.
	 * Returns false until this agent has completed its first mover step.
	 */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Locomotion Input")
	bool GetLocomotionTarget(FVector& TargetWorldVelocityCmPerSecond, float& TargetSpeedCmPerSecond,
		FVector& TargetFacingWorldDirection, bool& bRun) const;

	/** Adds world XY impulse and world Z angular impulse to the capsule mover, never teleports.
	 * Normal units: kg*cm/s and kg*cm^2/s. Velocity Change instead takes cm/s and rad/s.
	 * Z translation and X/Y rotation are unsupported by the upright ground mover and ignored.
	 * Returns false before registration, when inference/root stepping is disabled, or for invalid mass/input.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Root")
	bool AddRootImpulse(FVector WorldLinearImpulse, FVector WorldAngularImpulseRadians, bool bVelocityChange = false);

	/** Actual mover momentum readback; angular velocity is world Z in radians/second. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Root")
	bool GetRootVelocity(FVector& WorldLinearVelocityCmPerSecond, FVector& WorldAngularVelocityRadiansPerSecond) const;

	/** Capsule body's mass and inertia about upright world Z, used by Add Root Impulse. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Root")
	bool GetRootImpulseMassProperties(float& MassKg, float& YawInertiaKgCmSquared) const;

	/** Per-agent policy gate. A disabled lane freezes its last NN/root state. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|NN")
	bool bNNInferenceEnabled = true;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN")
	void SetNNInferenceEnabled(bool bEnabled) { bNNInferenceEnabled = bEnabled; }

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|NN")
	bool IsNNInferenceEnabled() const { return bNNInferenceEnabled; }

	/** Upper-controller mode input: false writes -1 (no sword), true writes +1. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|NN|Upper Body")
	bool bUpperNNHasSword = false;

	/** Normalized gaze yaw expected by the upper controller; -1..1 maps to -170..170 degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|NN|Upper Body",
		meta = (ClampMin = "-1.0", ClampMax = "1.0"))
	float UpperNNGazeYawNormalized = 0.0f;

	/** Normalized gaze pitch expected by the upper controller; -1..1 maps to -85..85 degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|NN|Upper Body",
		meta = (ClampMin = "-1.0", ClampMax = "1.0"))
	float UpperNNGazePitchNormalized = 0.0f;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN|Upper Body")
	void SetUpperNNInputs(bool bHasSword, float GazeYawNormalized, float GazePitchNormalized)
	{
		bUpperNNHasSword = bHasSword;
		SetUpperNNGaze(GazeYawNormalized, GazePitchNormalized);
	}

	/** Changes only the runtime gaze input; values are consumed on the next upper-policy step. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN|Upper Body")
	void SetUpperNNGaze(float GazeYawNormalized, float GazePitchNormalized)
	{
		UpperNNGazeYawNormalized = FMath::Clamp(GazeYawNormalized, -1.0f, 1.0f);
		UpperNNGazePitchNormalized = FMath::Clamp(GazePitchNormalized, -1.0f, 1.0f);
	}

	/** Performs the native BeginPlay component/collision initialization on demand. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Execution")
	void InitializeAgentRuntime();

	/** Creates/configures the single-agent NN manager when this pawn is auto-possessed. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Execution")
	bool EnsureStandaloneNNManager();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	EProphecyAgentSimulationMode GetSimulationMode() const;

	/** Kinematic, Half Sim (native physical animation), or Sim (existing magnetization).
	 * A Half Sim request during BeginPlay waits for the first NN pose automatically. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent")
	bool SetSimulationMode(EProphecyAgentSimulationMode NewMode);

	/**
	 * Replaces the active Physics Asset without discarding the live articulated state.
	 * Matching bodies retain transform, velocity, simulation, gravity, blend, and sleep state;
	 * native collision, solver, MACD, drive, and magnetization bindings are rebuilt.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical", meta = (DisplayName = "My Set Physics Asset"))
	bool MySetPhysicsAsset(UPhysicsAsset* NewPhysicsAsset);

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

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Physical")
	bool IsPhysicalDriveConfigured() const { return bPhysicalDriveConfigured; }

	/** Re-applies PhysicalDriveSettings and its live strength multiplier. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	bool ApplyPhysicalDriveSettingsNow();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	void SetPhysicalDriveStrengthMultiplier(float NewMultiplier);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	void SetGeneratePhysicalHitEvents(bool bEnabled);

	/** Applies the currently configured Chaos solver iteration counts to every body. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	void ApplyPhysicalSolverSettings();

	/** Applies the production collision profile for the requested agent mode. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical")
	void ApplyAgentCollisionMode(EProphecyAgentSimulationMode Mode);

	/** Direct low-level body controls for Blueprint physical experiments. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical|Body")
	bool SetPhysicalBodySimulating(FName BoneName, bool bSimulate, bool bWake = true);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical|Body")
	bool SetPhysicalBodyGravityEnabled(FName BoneName, bool bEnabled);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical|Body")
	bool WakePhysicalBody(FName BoneName);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical|Body")
	void WakeAllPhysicalBodies();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical|Body")
	bool ClearPhysicalBodyForces(FName BoneName);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Physical|Body")
	bool GetPhysicalBodyState(
		FName BoneName,
		FTransform& WorldTransform,
		FVector& LinearVelocityCmPerSecond,
		FVector& AngularVelocityRadiansPerSecond,
		bool& bIsSimulating) const;

	/** On-demand sum over unique, currently simulated PHAT bodies against the data-only
	 * presented target at the time of this call (not the future endpoint or feedback deadband).
	 * Linear = sum mass*(actual-target), kg*cm. Angular = sum mass*shortest world rotation
	 * vector from target to actual, kg*radians. Opposing vectors cancel; these are NOT averages.
	 * Includes upper body/attacks. Returns false with zero outputs if no supported simulated bodies.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical Feedback")
	bool GetMassWeightedPoseError(FVector& LinearErrorKgCm, FVector& AngularErrorKgRadians,
		float& TotalMassKg, int32& BodyCount) const;

	/** Sets the same linear and angular feedback tolerance on every feedback limb. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical Feedback",
		meta = (DisplayName = "Set All Physical Feedback Tolerances", ClampMin = "0.0"))
	bool SetAllPhysicalFeedbackTolerances(float LinearToleranceCm, float AngularToleranceDegrees);

	/** Sets the linear and angular feedback tolerance on one recurrently controlled bone. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical Feedback",
		meta = (DisplayName = "Set Physical Feedback Tolerance", ClampMin = "0.0"))
	bool SetPhysicalFeedbackTolerance(
		FName BoneName,
		float LinearToleranceCm,
		float AngularToleranceDegrees);

	/** Sets feedback tolerances on every recurrently controlled bone at or below ParentBone. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Physical Feedback",
		meta = (DisplayName = "Set Physical Feedback Tolerance Below", ClampMin = "0.0"))
	int32 SetPhysicalFeedbackToleranceBelow(
		FName ParentBone,
		bool bIncludeParent,
		float LinearToleranceCm,
		float AngularToleranceDegrees);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Physical Feedback")
	bool GetPhysicalFeedbackTolerance(
		FName BoneName,
		FProphecyPhysicalFeedbackToleranceSettings& Settings) const;

	/** Empty entries use zero tolerance. Keys are actual skeleton bone names. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical Feedback")
	TMap<FName, FProphecyPhysicalFeedbackToleranceSettings> PhysicalFeedbackTolerances;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	FVector GetRootLowPoint() const;

	/** Applies the manager root through the capsule sweep and reports its actual low point. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Root")
	bool SetManagedRootLowPoint(
		const FVector& LowPoint,
		float YawDegrees,
		FVector& OutAppliedLowPoint,
		FVector& OutBlockingNormal,
		bool& bOutWorldStaticBlocked);
	/** One-time placement used before a bridge-spawned shell is made visible. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Root")
	void TeleportManagedRootLowPoint(const FVector& LowPoint, float YawDegrees);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	UCapsuleComponent* GetAgentCapsule() const { return Capsule; }

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent")
	USkeletalMeshComponent* GetAgentMesh() const { return Mesh; }

	/** Returns this agent's inherited camera component. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Camera", meta = (DisplayName = "Get Agent Camera"))
	UCameraComponent* GetAgentCamera() const;

	/** Returns this agent's inherited camera boom for Blueprint-authored camera control. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Camera", meta = (DisplayName = "Get Agent Spring Arm"))
	USpringArmComponent* GetAgentSpringArm() const { return SpringArm; }

	/** The one rendered/simulated mesh used as this agent's skeleton reference. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Manual NN Pose")
	USkeletalMeshComponent* GetPoseReferenceMesh() const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Manual NN Pose")
	UProphecyNNLocomotionAnimInstance* GetProphecyAnimInstance() const;

	/** Plays an animation on the upper body while the NN keeps pelvis/legs, or on the full body. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Animation Overlay")
	bool PlayAnimationOverlay(
		UAnimSequenceBase* Animation,
		EProphecyAnimationOverlayMode Mode = EProphecyAnimationOverlayMode::UpperBodyOnly,
		float BlendSeconds = 0.25f,
		float PlayRate = 1.0f,
		bool bLoop = true,
		bool bRestart = true);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Animation Overlay")
	bool StopAnimationOverlay(float BlendOutSeconds = 0.25f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Animation Overlay")
	bool RestartAnimationOverlay();

	/**
	 * Plays an in-place authored sequence inside the manager's existing 30 Hz pose step.
	 * NAME_None blends the full controlled skeleton; another bone blends that bone and descendants.
	 * The finalized blended pose is also written back as the next recurrent NN state.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Animation Layer")
	bool PlayNNAnimationLayer(
		UAnimSequenceBase* Animation,
		FName FirstBlendedBone = NAME_None,
		float BlendInSeconds = 0.25f,
		float BlendOutSeconds = 0.25f,
		float PlayRate = 1.0f,
		bool bLoop = false);

	/** Blends the active authored layer back to the NN without adding a Blueprint Tick path. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Animation Layer")
	bool StopNNAnimationLayer(float BlendOutSeconds = 0.25f);

	/** Start the accepted Slash2 policy from this agent's current pose, not a recorded clip.
	 * Attack: slashL/R/LD/RD/LU/RU, pike, jabL/R, hookL/R, overL/R, headbutt, kickL/R.
	 * Target is an absolute Unreal world position in centimetres. Kicks reject half mode.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN Attack")
	bool TriggerNNAttack(FName Attack, FVector TargetWorldLocation, bool bHalfAttack = false);

	/** Both hands are sampled at time zero. Only finger/metacarpal bones are used. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Prophecy|Agent|NN Attack|Fists")
	TSoftObjectPtr<UAnimSequence> ClosedFistAnimation = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(TEXT("/Game/_mygame/closed_fist.closed_fist")));

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Prophecy|Agent|NN Attack|Fists")
	bool bEnableAttackFists = true;

	/** Used for any attack not present in Attack Fist Settings. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Prophecy|Agent|NN Attack|Fists")
	FProphecyAttackFistSettings DefaultAttackFistSettings;

	/** Keys are the same attack names accepted by Trigger NN Attack. Changes apply on the next trigger. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Prophecy|Agent|NN Attack|Fists")
	TMap<FName, FProphecyAttackFistSettings> AttackFistSettings;

	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack|Fists")
	bool SetAttackFistSettings(FName Attack, FProphecyAttackFistSettings Settings);

	UFUNCTION(BlueprintPure, Category="Prophecy|Agent|NN Attack|Fists")
	FProphecyAttackFistSettings GetAttackFistSettings(FName Attack) const;

	/** Current interpolated levels; safe to read repeatedly without advancing time. */
	UFUNCTION(BlueprintPure, Category="Prophecy|Agent|NN Attack|Fists")
	void GetFistClosedLevels(float& Left, float& Right) const;

	/** Blend to persistent manual levels (initially 0). Call once, not on Tick.
	 * Takes hand control until the next attack; attacks then return to these levels. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack|Fists", meta=(ClampMin="0"))
	bool SetFistClosedLevels(float Left = 0.0f, float Right = 0.0f, float BlendSeconds = 0.4f);

	// Native attack lifecycle; not a second Blueprint trigger path.
	void BeginAttackFists(FName Attack);
	void EndAttackFists();
	void ReleaseAttackFists();

	/** Shared by every agent in this game world. Default 125 cm. Existing half attacks
	 * consume updates on their next policy step; full attacks are unaffected. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN|Attack")
	bool SetGlobalHalfAttackTargetRadius(float RadiusCm);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|NN|Attack")
	float GetGlobalHalfAttackTargetRadius() const;

	/** Original gameplay target, clamped real-pelvis target, and actual ghost-policy target.
	 * Pure readback: no inference and no alteration of attack history. False when inactive. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|NN|Attack")
	bool GetNNAttackTarget(FVector& RequestedWorldTarget, FVector& EffectiveWorldTarget,
		FVector& GhostWorldTarget) const;

	/** Change full/upper-only ownership without restarting the attack or its ghost history. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN Attack")
	bool SetNNHalfAttackEnabled(bool bEnabled);

	/** Retarget the running attack. No Blueprint Tick is required for a stationary target. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN Attack")
	bool SetNNAttackTarget(FVector TargetWorldLocation);

	/** Return control to locomotion using the last published attack pose as recurrent history. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|NN Attack")
	bool StopNNAttack();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|NN Attack")
	bool GetNNAttackState(FName& Attack, bool& bHalfAttack, bool& bArmed, bool& bHit, int32& PolicyFrame) const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Animation Layer")
	bool IsNNAnimationLayerActive() const;

	/** Returns false when no authored layer is active. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Animation Layer")
	bool GetNNAnimationLayerState(float& PlaybackTimeSeconds, float& BlendWeight) const;

	/** Fires once when natural completion or an explicit stop begins blending out. */
	UPROPERTY(BlueprintAssignable, Category = "Prophecy|Agent|Animation Layer")
	FProphecyAgentAnimationLayerSignature OnNNAnimationLayerBlendingOut;

	/** Fires after a non-looping sequence has completed its automatic blend-out. */
	UPROPERTY(BlueprintAssignable, Category = "Prophecy|Agent|Animation Layer")
	FProphecyAgentAnimationLayerSignature OnNNAnimationLayerFinished;

	/** Fires after an explicit stop, or immediately when another sequence replaces this one. */
	UPROPERTY(BlueprintAssignable, Category = "Prophecy|Agent|Animation Layer")
	FProphecyAgentAnimationLayerSignature OnNNAnimationLayerInterrupted;

	/** Runtime setter: off destroys the extra renderer; the authored target remains data-only. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Debug")
	void SetShowKinematicDebugMesh(bool bShow) { bShowKinematicDebugMesh = bShow; }

	/** Binds this shell directly to the manager's pose-store data, without requiring an AnimInstance. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Manual NN Pose")
	void ConfigureNNPoseDataSource(int32 AgentId, float PoseIntervalSeconds, bool bInterpolatePose);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Manual NN Pose")
	void ClearNNPoseDataSource();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Manual NN Pose")
	bool GetNNPoseDataSource(
		int32& AgentId,
		float& PoseIntervalSeconds,
		bool& bInterpolatePose) const;

	/** Reads one authored target directly without copying the complete pose arrays. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Manual NN Pose")
	bool GetAuthoredBodyWorldTarget(
		FName BoneName,
		FTransform& PreviousWorldTransform,
		FTransform& CurrentWorldTransform,
		FTransform& InterpolatedWorldTransform,
		float& InterpolationAlpha) const;

	/** Publishes this frame's finalized Blueprint target to the Chaos substep callback. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Manual NN Pose")
	void PublishManualFollowerSubstepTargets(float DeltaSeconds);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Manual NN Pose")
	void ReleaseManualFollowerSubstepTargets();

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
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Manual NN Pose")
	bool bManualNNPoseApplication = false;

	/** Default true preserves the existing native Tick publication. Disable to call it from Blueprint. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Execution")
	bool bAutoPublishManualFollowerSubstepTargets = true;

	/** Default true preserves the existing native PrePhysics magnetization pass. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Execution")
	bool bAutoApplyWorldMagnetization = true;

	/** Default true preserves native BeginPlay component and collision initialization. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Execution")
	bool bAutoInitializeAgentRuntime = true;

	/** Default true preserves automatic single-agent manager creation for possessed test pawns. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Execution")
	bool bAutoEnsureStandaloneNNManager = true;

	/** Debug only: render the data-only authored pose as a second kinematic mesh. Zero cost while disabled. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Debug", meta = (DisplayName = "Show Kinematic Debug Mesh"))
	bool bShowKinematicDebugMesh = false;

	/** Stable authored mesh-to-capsule transform; Chaos overwrites the live relative transform while ragdolling. */
	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Manual NN Pose")
	FTransform GetAuthoredMeshRelativeTransform() const
	{
		return GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic
			? PhysicalTargetComponentRelativeTransform
			: GetPoseReferenceMesh()->GetRelativeTransform();
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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Solver", meta = (ClampMin = "1"))
	int32 PhysicalPositionSolverIterations = 4;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Solver", meta = (ClampMin = "1"))
	int32 PhysicalVelocitySolverIterations = 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Solver", meta = (ClampMin = "0"))
	int32 PhysicalProjectionSolverIterations = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Constraints",
		meta = (ClampMin = "0.0", ClampMax = "179.0"))
	float PhysicalAngularLimitDegrees = 179.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Constraints")
	bool bEnablePhysicalMassConditioning = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Constraints")
	bool bDisablePhysicalConstraintMotors = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Physical|Constraints")
	bool bUpdatePhysicalJointsFromAnimation = false;

	/** Global gate and multipliers; defaults reproduce the existing exact one-step tracker. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization")
	bool bWorldMagnetizationEnabled = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization",
		meta = (ClampMin = "0.0"))
	float WorldMagnetizationLinearStrengthScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization",
		meta = (ClampMin = "0.0"))
	float WorldMagnetizationAngularStrengthScale = 1.0f;

	/** Bodies omitted from this map stay animation-driven when Physical mode is initialized. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Agent|Magnetization")
	TMap<FName, FProphecyBodyMagnetizationSettings> BodyMagnetizationSettings;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Magnetization")
	void SetAllBodyMagnetization(
		bool bEnabled,
		float LinearStrengthScale = 1.0f,
		float AngularStrengthScale = 1.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Magnetization")
	void SetBodyMagnetization(
		FName BoneName,
		bool bEnabled,
		float LinearStrengthScale = 1.0f,
		float AngularStrengthScale = 1.0f);

	/** Applies settings to every Physics Asset body at or below ParentBone. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Magnetization")
	int32 SetBodyMagnetizationBelow(
		FName ParentBone,
		bool bIncludeParent,
		bool bEnabled,
		float LinearStrengthScale = 1.0f,
		float AngularStrengthScale = 1.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Magnetization")
	bool SetBodyIncludedInPhysicalSimulation(FName BoneName, bool bSimulateBody);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Agent|Magnetization")
	bool GetBodyMagnetizationSettings(
		FName BoneName,
		FProphecyBodyMagnetizationSettings& Settings) const;

	/** Executes the same configured all-body magnetization pass normally called by native Tick. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Magnetization")
	void ApplyConfiguredWorldMagnetization(float DeltaSeconds);

	/** Low-level one-body force/torque primitive for custom Blueprint targets. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Agent|Magnetization")
	bool ApplyBodyWorldMagnetization(
		FName BoneName,
		const FTransform& TargetWorldTransform,
		float DeltaSeconds,
		float LinearStrengthScale = 1.0f,
		float AngularStrengthScale = 1.0f,
		bool bCancelGravity = true);

	UPROPERTY(BlueprintAssignable, Category = "Prophecy|Agent|Physical")
	FProphecyAgentPhysicalHitSignature OnPhysicalHit;

private:
	friend class AProphecyNNLocomotionManager;
	bool EnterHalfSimulation();
	bool LeaveHalfSimulation(EProphecyAgentSimulationMode NextMode);
	void ReleaseHalfSimulationState();
	bool RefreshHalfSimulationDrives();
	void ApplyHalfSimulationBodyStrength(FName BoneName);
	UPROPERTY(Transient)
	bool bPendingHalfSimulation = false;

	void ApplyCollisionMode(EProphecyAgentSimulationMode Mode);
	void ApplyAbsoluteWorldMagnetization(float DeltaSeconds);
	void ConfigureRootAndJointTorquePhysics(USkeletalMeshComponent* PhysicalMesh, UPhysicsAsset* PhysicsAsset);
	bool IsBodyConfiguredForSimulation(FName BoneName) const;

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

	/** Camera boom owned by the agent. Native code does not apply mouse input to it. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Camera", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<USpringArmComponent> SpringArm;

	/** Camera whose flattened heading is read by the manual locomotion input. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Camera", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical", meta = (AllowPrivateAccess = "true"))
	TObjectPtr<UPhysicalAnimationComponent> PhysicalAnimation;

	UPROPERTY(VisibleAnywhere, Category = "Prophecy|Agent")
	FProphecyAgentHandle AgentHandle;

	/** Strong runtime reference; timing and blending state live in the batched manager. */
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequenceBase> ActiveNNAnimationLayerAsset;

	UPROPERTY(VisibleAnywhere, Category = "Prophecy|Agent")
	EProphecyAgentSimulationMode SimulationMode = EProphecyAgentSimulationMode::Kinematic;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical",
		meta = (AllowPrivateAccess = "true"))
	bool bMACDEnabled = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical",
		meta = (AllowPrivateAccess = "true"))
	bool bPhysicalDriveConfigured = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical",
		meta = (AllowPrivateAccess = "true"))
	bool bHasPreviousPhysicalRootTarget = false;
	bool bSavedUpdateRateOptimizations = false;
	EVisibilityBasedAnimTickOption SavedVisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical",
		meta = (AllowPrivateAccess = "true"))
	FTransform PhysicalTargetComponentRelativeTransform = FTransform::Identity;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Agent|Physical",
		meta = (AllowPrivateAccess = "true"))
	FTransform PreviousPhysicalRootTarget = FTransform::Identity;
};
