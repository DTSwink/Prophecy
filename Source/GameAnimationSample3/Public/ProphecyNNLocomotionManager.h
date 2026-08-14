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

UCLASS(BlueprintType, Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyNNLocomotionManager : public AActor
{
	GENERATED_BODY()

public:
	struct FImpl;

	AProphecyNNLocomotionManager();
	virtual ~AProphecyNNLocomotionManager() override;

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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "0.0"))
	float AgentSpeedCmPerSecond = 500.0f;

	/** Mouse-orbit sensitivity used by the one-agent /Game/locomotion PIE test. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Simple Test", meta = (ClampMin = "0.01", UIMin = "0.01", UIMax = "1.0"))
	float CameraSensitivity = 0.15f;

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

	UFUNCTION(BlueprintPure, Category = "Prophecy|NN Locomotion|Agents")
	FProphecyAgentHandle GetAgentHandle(int32 AgentIndex) const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|NN Locomotion|Agents")
	AProphecyAgent* ResolveAgent(FProphecyAgentHandle Handle) const;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion|Agents")
	bool SetAgentSimulationMode(FProphecyAgentHandle Handle, EProphecyAgentSimulationMode NewMode);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion|Agents")
	bool SetAgentMACDEnabled(FProphecyAgentHandle Handle, bool bEnabled);

	/** Runtime-only update used by the agent's Blueprint feedback setters. */
	bool SetAgentPhysicalFeedbackTolerance(
		FProphecyAgentHandle Handle,
		EProphecyPhysicalFeedbackLimb Limb,
		float LinearToleranceCm,
		float AngularToleranceDegrees);

	/** Runtime-only update used by the agent's Blueprint global feedback setter. */
	bool SetAgentAllPhysicalFeedbackTolerances(
		FProphecyAgentHandle Handle,
		float LinearToleranceCm,
		float AngularToleranceDegrees);

	/** Configures the transient manager used only by the flat /Game/locomotion test map. */
	void ConfigureSimpleLocomotionTest();

private:
	bool LoadRuntimeContract();
	bool LoadWalkRuntimeContract();
	bool InitializeNNE();
	bool InitializeWalkNNE();
	void InitializeAgents();
	void ResolveRouteEndpoints();
	void SpawnVisualComponents();
	void StepSimulation(float StepSeconds);
	void ResamplePhysicalAgents();
	bool ResamplePhysicalAgentState(int32 AgentIndex);
	void BuildInputBatch(float StepSeconds);
	bool RunModelBatch();
	void ApplyOutputBatch(float StepSeconds);
	void PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds);
	void UpdateVisualRoots();
	void DrawFutureRootDebug() const;
	void InitializeSimpleTestCamera();
	void UpdateSimpleTestInput();
	void UpdateSimpleTestCamera();
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
