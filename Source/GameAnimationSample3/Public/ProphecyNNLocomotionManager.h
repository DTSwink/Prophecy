#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProphecyAgent.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyNNLocomotionManager.generated.h"

class UAnimSequenceBase;
class UNNEModelData;
class USceneComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
enum class EProphecyAgentState : uint8;
struct FProphecyNNDefenseStatus;

/** Read-only completed manager diagnostics; does not sample bodies or run inference. */
struct FProphecyNNRuntimeBenchmarkStats
{
	bool bInitialized = false;
	bool bUsingGPU = false;
	bool bSimBridgeActive = false;
	int32 RegisteredAgents = 0;
	int32 RunBatchSize = 0, WalkBatchSize = 0, UpperBatchSize = 0;
	int32 FootRollSteps = 0;
	int32 PhysicalFeedbackExecutionMode = 0;
	uint64 PreparedPhysicalSamples = 0, PreparedPhysicalBatches = 0;
	uint64 CompletedNNSteps = 0, CompletedPhysicalSamples = 0, FailedPhysicalSamples = 0;
	double BuildSeconds = 0.0, InferenceSeconds = 0.0, OutputSeconds = 0.0, StoreSeconds = 0.0;
	FString RunRuntime, WalkRuntime, UpperRuntime;
};

UCLASS(BlueprintType, Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyNNLocomotionManager : public AActor
{
	GENERATED_BODY()

public:
	struct FImpl;
	// Event-only update of a registered lane; non-reflected and not a per-frame settings lookup.
	void CacheUpperRootRotationHorizon(const AProphecyAgent* Agent, float Horizon);
	// Event-only debug checkpoints; native storage is separate from retained manager layouts.
	int32 CaptureInitialAgentResetState(FString& OutError);
	int32 RestoreInitialAgentResetState(FString& OutError);
	void ClearInitialAgentResetState();

	AProphecyNNLocomotionManager();
	virtual ~AProphecyNNLocomotionManager() override;

	/** Native opt-in before BeginPlay: 0 original, 1 prepared serial, 2 prepared parallel. */
	bool SetPhysicalFeedbackExecutionMode(int32 Mode);

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	/** Launch and synchronize the standalone simulation for this PIE session. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Bridge", meta = (DisplayName = "Sim Bridge"))
	bool bSimBridge = true;

	/** Possessed agent observed by the sim but never root-driven by it. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Prophecy|Bridge")
	TObjectPtr<AProphecyAgent> PlayerAgent;

	/** Number of simulated villagers. PlayerAgent is additional to this count. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "1", ClampMax = "100"))
	int32 CrowdSize = 100;

	/** Blueprint subclass used for every lightweight shell in this batch. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Agents")
	TSubclassOf<AProphecyAgent> AgentClass;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "1.0"))
	float NNUpdateHz = 30.0f;

	/** Foot-contact integration work per NN update. Four is the production default. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "0", ClampMax = "1024"))
	int32 FootRollIntegrationSteps = 4;

	/** Final presentation-only safeguard: keep each foot within its authored total leg length from the thigh bone. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (DisplayName = "Clamp Foot"))
	bool bClampFoot = false;

	/** Multiplies the authored upper-leg plus lower-leg reach used by Clamp Foot. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (DisplayName = "Foot Clamp Length Multiplier", ClampMin = "0.0", UIMin = "0.5", UIMax = "2.0"))
	float FootClampLengthMultiplier = 1.0f;

	/** Final presentation-only safeguard: pull the foot inward when it exceeds the authored calf length. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (DisplayName = "Clamp Calf"))
	bool bClampCalf = false;

	/** Multiplies the authored lower-leg length used by Clamp Calf. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (DisplayName = "Calf Clamp Length Multiplier", ClampMin = "0.0", UIMin = "0.5", UIMax = "2.0"))
	float CalfClampLengthMultiplier = 1.0f;

	/** Limit each locomotion hand's distance from its elbow when building the pose. Applies to all managed agents; does not change recurrent NN state or Slash attack forearm correction. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (DisplayName = "Clamp Hand"))
	bool bClampHand = true;

	/** Maximum elbow-to-hand distance as a multiple of authored forearm length. Read on each pose publication; 1 preserves the original limit. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (DisplayName = "Hand Clamp Length Multiplier", ClampMin = "0.0", UIMin = "0.5", UIMax = "2.0"))
	float HandClampLengthMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "0.0"))
	float AgentSpeedCmPerSecond = 500.0f;

	/** Draw the exact current-root frame and eight future roots encoded into the selected agent's NN input. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Debug")
	bool bShowFutureRootDebug = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Debug", meta = (ClampMin = "0", ClampMax = "99"))
	int32 FutureRootDebugAgentIndex = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "0.0"))
	float MaxTurnRateDegreesPerSecond = 360.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "1.0"))
	float ArrivalRadiusCm = 90.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	bool bSpawnVisuals = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	bool bCastShadows = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "0"))
	int32 ForcedMeshLOD = 1;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	FString PreferredRuntime = TEXT("NNERuntimeORTDml");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	FString OnnxModelPath = TEXT("Content/locomotion/NN/prophecy_lower_body_run_b100.onnx");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	FString RuntimeContractPath = TEXT("Content/locomotion/NN/prophecy_lower_body_runtime.json");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	FString WalkOnnxModelPath = TEXT("Content/locomotion/NN/prophecy_lower_body_walk_b100.onnx");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	FString WalkRuntimeContractPath = TEXT("Content/locomotion/NN/prophecy_lower_body_walk_runtime.json");

	/** Temporary upper-body checkpoint exported as a second batched data-only NNE model. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Upper Body")
	FString UpperOnnxModelPath = TEXT("Content/locomotion/NN/prophecy_upper_body_b100.onnx");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Upper Body")
	FString UpperRuntimeContractPath = TEXT("Content/locomotion/NN/prophecy_upper_body_runtime.json");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Route")
	FName EndpointAActorName = TEXT("Cube");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Route")
	FName EndpointBActorName = TEXT("Cube2");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Route")
	FVector EndpointAFallback = FVector(-1024.48, -1765.47, 0.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Route")
	FVector EndpointBFallback = FVector(-1024.48, 1373.10, 0.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	TObjectPtr<UAnimSequenceBase> OverlayAnimation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	bool bOverlayEnabled = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay", meta = (ClampMin = "0.0"))
	float OverlayBlendSeconds = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	float OverlayPlayRate = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Benchmark", meta = (ClampMin = "0.0"))
	float BenchmarkWarmupSeconds = 3.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Benchmark", meta = (ClampMin = "0.0"))
	float BenchmarkSeconds = 15.0f;

	/** Development-only startup hook. Production keeps this at zero and promotes agents explicitly. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Physical", meta = (ClampMin = "0", ClampMax = "100"))
	int32 InitialPhysicalAgentCount = 0;

	/** Development/benchmark startup hook; runtime agents can be changed individually. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Physical")
	bool bInitialPhysicalAgentsUseMACD = true;

	/** Development/benchmark startup hook. Production uses pelvis + joint torque. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Physical")
	EProphecyAgentPhysicalDriveMode InitialPhysicalDriveMode = EProphecyAgentPhysicalDriveMode::RootAndJointTorque;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion")
	void SetUpperBodyOverlayEnabled(bool bEnabled);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion")
	void SetUpperBodyOverlayAnimation(UAnimSequenceBase* Animation);

	UFUNCTION(BlueprintPure, Category = "Prophecy|NN Locomotion")
	FString GetActiveRuntimeName() const;

	/** Game-thread fixture observer of existing work. No callbacks, simulation or model work is triggered. */
	bool ReadRuntimeBenchmarkStats(FProphecyNNRuntimeBenchmarkStats& OutStats) const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|NN Locomotion|Agents")
	FProphecyAgentHandle GetAgentHandle(int32 AgentIndex) const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|NN Locomotion|Agents")
	AProphecyAgent* ResolveAgent(FProphecyAgentHandle Handle) const;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion|Agents")
	bool SetAgentSimulationMode(FProphecyAgentHandle Handle, EProphecyAgentSimulationMode NewMode);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion|Agents")
	bool SetAgentMACDEnabled(FProphecyAgentHandle Handle, bool bEnabled);

	bool GetAgentLocomotionState(FProphecyAgentHandle Handle,
		FVector& WorldVelocityCmPerSecond, FVector& FacingWorldDirection, bool& bRun) const;
	bool GetAgentLocomotionCheckpointWeights(FProphecyAgentHandle Handle, float& WalkWeight, float& RunWeight) const;
	bool GetAgentLocomotionTarget(FProphecyAgentHandle Handle, FVector& TargetWorldVelocityCmPerSecond,
		float& TargetSpeedCmPerSecond, FVector& TargetFacingWorldDirection, bool& bRun) const;
	bool AddAgentRootVelocityImpulse(FProphecyAgentHandle Handle, FVector DeltaVelocityCmPerSecond,
		double DeltaWorldYawRadiansPerSecond);
	bool GetAgentRootVelocity(FProphecyAgentHandle Handle, FVector& LinearCmPerSecond,
		FVector& AngularRadiansPerSecond) const;
	static bool SetHalfAttackTargetRadius(const UWorld* World, float RadiusCm);
	static float GetHalfAttackTargetRadius(const UWorld* World);
	bool GetAgentNNAttackTarget(FProphecyAgentHandle Handle, FVector& RequestedWorldTarget,
		FVector& EffectiveWorldTarget, FVector& GhostWorldTarget) const;

	/** Runtime-only update used by the agent's Blueprint feedback setters. */
	bool SetAgentPhysicalFeedbackTolerance(
		FProphecyAgentHandle Handle,
		FName BoneName,
		float LinearToleranceCm,
		float AngularToleranceDegrees);

	/** Runtime-only update used by the agent's Blueprint global feedback setter. */
	bool SetAgentAllPhysicalFeedbackTolerances(
		FProphecyAgentHandle Handle,
		float LinearToleranceCm,
		float AngularToleranceDegrees);

	/** Event-driven entry point used by AProphecyAgent's Blueprint animation-layer nodes. */
	bool PlayAgentAnimationLayer(
		FProphecyAgentHandle Handle,
		UAnimSequenceBase* Animation,
		FName FirstBlendedBone,
		float BlendInSeconds,
		float BlendOutSeconds,
		float PlayRate,
		bool bLoop);
	bool StopAgentAnimationLayer(FProphecyAgentHandle Handle, float BlendOutSeconds);
	bool TriggerAgentNNAttack(FProphecyAgentHandle Handle, FName Attack, FVector TargetWorld, bool bHalf);
	void GetAgentAttackDefenseState(FProphecyAgentHandle Handle,bool& bParry,bool& bDodge) const;
	bool SetAgentNNHalfAttack(FProphecyAgentHandle Handle, bool bHalf);
	bool SetAgentNNAttackTarget(FProphecyAgentHandle Handle, FVector TargetWorld);
	bool GetAgentLocomotionRootWindow(FProphecyAgentHandle Handle, TArray<FTransform>& WorldRoots, TArray<float>& Times) const;
	bool GetAgentContinuousLocomotionRootWindow(FProphecyAgentHandle Handle, TArray<FTransform>& WorldRoots, TArray<float>& Times) const;
	bool SetAgentLocomotionRootWindowLocation(FProphecyAgentHandle Handle, FVector WorldLocation, bool bPreserveWorldPose = false);
	UPoseableMeshComponent* SetAgentPreviousPoseDebug(FProphecyAgentHandle Handle, bool bEnabled, bool bPreferAttack);
	void UpdatePreviousPoseDebug(bool bAttack);
	void TraceNNHandoff();
	bool SetAgentFootPinningDebug(FProphecyAgentHandle Handle, bool bEnabled);
	bool GetAgentFootPinning(FProphecyAgentHandle Handle, bool bAttack, bool bFrozenStage, FProphecyFootPinningSample& Sample) const;
	bool StopAgentNNAttack(FProphecyAgentHandle Handle, bool bReturnToLocomotion = true);
	bool StartAgentNNParry(FProphecyAgentHandle Handle,AProphecyAgent* Attacker,float MaximumSeconds,FString& Error);
	bool StartAgentNNDodge(FProphecyAgentHandle Handle,AProphecyAgent* Attacker,float MaximumSeconds,FString& Error);
	bool StopAgentNNDefense(FProphecyAgentHandle Handle, bool bReturnToLocomotion = true);
	EProphecyAgentState GetAgentActivityState(FProphecyAgentHandle Handle) const;
	bool GetAgentNNDefenseStatus(FProphecyAgentHandle Handle,FProphecyNNDefenseStatus& Status) const;
	bool GetAgentNNAttackState(FProphecyAgentHandle Handle, FName& Attack, bool& bHalf, bool& bArmed, bool& bHit, int32& Frame) const;
	/** Development console audit; not part of the gameplay Blueprint surface. */
	UFUNCTION(Exec)
	bool AuditSlashReference(const FString& ReferenceDirectory);
	/** Opt-in whole-step CPU/DirectML benchmark. Never runs during gameplay. */
	UFUNCTION(Exec)
	bool BenchmarkSlashRuntime(bool bGpu, int32 AgentCount);
	bool GetAgentAnimationLayerState(
		FProphecyAgentHandle Handle,
		float& OutPlaybackTimeSeconds,
		float& OutBlendWeight) const;

	/** Configures the transient manager used only by the flat /Game/locomotion test map. */
	void ConfigureSimpleLocomotionTest();

private:
	bool LoadRuntimeContract();
	bool LoadWalkRuntimeContract();
	bool LoadUpperRuntimeContract();
	bool InitializeNNE();
	bool InitializeWalkNNE();
	bool InitializeUpperNNE();
	bool ValidateUpperNNE();
	void InitializeAgents();
	void ResolveRouteEndpoints();
	void SpawnVisualComponents();
	void StepSimulation(float StepSeconds);
	void ResamplePhysicalAgents();
	bool ResamplePhysicalAgentState(int32 AgentIndex);
	int32 PhysicalFeedbackExecutionMode = 0;
	void BuildInputBatch(float StepSeconds);
	void AdvanceAgentMover(int32 AgentIndex, float StepSeconds);
	void RebaseDefenseAfterRootCollision(int32 AgentIndex,const FVector3f& PreviousRoot,float PreviousYaw,const FVector3f& Root,float Yaw);
	bool RunModelBatch();
	void ApplyOutputBatch(float StepSeconds);
	void BuildUpperInputBatch();
	bool RunUpperModelBatch();
	void ApplyUpperOutputBatch();
	void ApplyAnimationLayers(float StepSeconds);
	bool InitializeSlashNNE();
	void AdvanceSlashAttacks();
	void AdvanceNNDefenses();
	void AdvanceNNDodges();
	void ApplySlashPose(int32 AgentIndex, TArrayView<FTransform> PreviousPose, TArrayView<FTransform> Pose);
	void PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds);
	void UpdateVisualRoots();
	void DrawFutureRootDebug() const;
	void InitializeSimpleTestPlayerView();
	void CaptureAbsoluteMotionAuditFrame();
	void UpdateAbsoluteMotionAuditPhase();
	void UpdateOverlaySettings();
	void LogBenchmark(float DeltaSeconds);
	bool StartSimBridge();
	void StopSimBridge();
	bool ConsumeSimBridgeFrame();
	void PublishUnrealBridgeFrame();
	bool IsSimBridgeActive() const;

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(Transient)
	TObjectPtr<UNNEModelData> ModelData;

	UPROPERTY(Transient)
	TObjectPtr<UNNEModelData> WalkModelData;

	UPROPERTY(Transient)
	TObjectPtr<UNNEModelData> UpperModelData;

	UPROPERTY(Transient)
	TObjectPtr<UNNEModelData> SlashModelData;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USkeletalMeshComponent>> MeshComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<AProphecyAgent>> AgentActors;

	FImpl* Impl = nullptr;
};

UCLASS(BlueprintType)
class GAMEANIMATIONSAMPLE3_API UProphecyNNLocomotionWorldSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

	UFUNCTION(BlueprintPure, Category = "Prophecy|NN Locomotion")
	AProphecyNNLocomotionManager* GetManager() const { return Manager; }

private:
	UPROPERTY(Transient)
	TObjectPtr<AProphecyNNLocomotionManager> Manager;
};
