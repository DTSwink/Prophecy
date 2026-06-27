#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyNNCrowdBenchmark.generated.h"

class USceneComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class UInstancedStaticMeshComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class UTexture2D;
class UNNEModelData;
class UNiagaraComponent;
class UNiagaraSystem;
class ACameraActor;
class ADirectionalLight;
class AExponentialHeightFog;
class ASkyLight;
class ASkyAtmosphere;
class AVolumetricCloud;
class FJsonObject;

UCLASS()
class GAMEANIMATIONSAMPLE3_API AProphecyNNCrowdBenchmarkActor : public AActor
{
	GENERATED_BODY()

public:
	AProphecyNNCrowdBenchmarkActor();
	virtual ~AProphecyNNCrowdBenchmarkActor() override;

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	int32 CrowdSize = 100;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float NNUpdateHz = 30.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bSpawnVisuals = true;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bCastShadows = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bSpawnBenchmarkFloor = true;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bSpawnBenchmarkLights = true;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString BenchmarkProfile;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bApplyBattleSimRenderProfile = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString ShadowMode = TEXT("None");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	int32 RealShadowBudget = 12;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bSpawnContactShadows = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString ContactShadowVariant = TEXT("Root");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bDebugShadowGeometry = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bGrassDiagnosticMode = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bGrassWind = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bGrassWindDiagnostic = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float GrassWindBendCm = 18.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float GrassWindLiftCm = 0.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float GrassWindWorldFrequency = 0.00115f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float GrassWindPatchFrequency = 0.00055f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float GrassWindSpeed = 1.35f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float GrassWindGustStrength = 1.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bSpawnTrees = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	int32 TreeInstanceCount = 420;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString TreeSource = TEXT("PolyHavenFir");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bTreeWind = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bTreeWindDiagnostic = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float TreeWindBendCm = 30.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float TreeWindLiftCm = 0.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float TreeWindWorldFrequency = 0.00034f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float TreeWindSpeed = 0.60f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float TreeWindGustStrength = 0.55f;

	bool bShadowMaskDiagnostic = false;

	bool bHideGrassForShadowInspection = false;
	bool bHideGrassBladesOnly = false;
	bool bSceneryOnly = false;
	bool bClosePreviewCamera = false;
	bool bCenterTreeDiagnostic = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bSpawnGrass = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString GrassRenderer = TEXT("HISM");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString NiagaraGrassSystemPath = TEXT("/Niagara/DefaultAssets/Templates/Systems/MinimalLightweight.MinimalLightweight");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	int32 NiagaraGrassComponentCount = 1;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString VisualMode = TEXT("Skeletal");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	int32 ForcedMeshLOD = 3;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString MetaHumanBlueprintClassPath = TEXT("/Game/MetaHumans/Kellan/BP_Kellan.BP_Kellan_C");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	int32 MetaHumanForcedLOD = -1;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bMetaHumanDriveBodyWithNNPose = true;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bMetaHumanPreserveReferenceBoneTranslations = true;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString MetaHumanTier = TEXT("Full");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bMetaHumanTierComparison = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString MetaHumanTierComparisonList = TEXT("Full,Mid,Far");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float MetaHumanTierComparisonSpacingCm = 260.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString MetaHumanClothingMode = TEXT("TierDefault");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString MetaHumanGroomMode = TEXT("TierDefault");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString MetaHumanFaceMode = TEXT("TierDefault");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bMetaHumanFreezeSkeletalTicks = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float SkeletalTickHz = 30.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString PreferredRuntime = TEXT("NNERuntimeORTDml");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float BenchmarkSeconds = 30.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float WarmupSeconds = 5.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bExitWhenDone = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString OnnxModelPath = TEXT("Content/Prophecy/NN/stepper_checkpoint_last_b100.onnx");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString RuntimeSeedPath = TEXT("Content/Prophecy/NN/stepper_runtime_seed.json");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString ScreenshotPath;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float ScreenshotSeconds = 3.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	bool bLiveVisualIteration = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	FString LiveVisualConfigPath = TEXT("Saved/ProphecyLiveVisual.json");

	UPROPERTY(EditAnywhere, Category = "Prophecy|NN Benchmark")
	float LiveVisualPollSeconds = 0.25f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood VFX")
	bool bBloodVFXPreview = false;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood VFX")
	float BloodVFXPreviewScale = 1.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood VFX")
	float BloodVFXPreviewTimeScale = 1.0f;

private:
	void ApplyCommandLineOverrides();
	void ApplyBenchmarkProfile();
	void NormalizeShadowVariantSettings();
	void ApplyBattleSimRenderProfile();
	bool InitializeSeedData();
	bool InitializeNNE();
	bool TryCreateGpuModel(const FString& RuntimeName);
	bool TryCreateCpuModel(const FString& RuntimeName);
	void InitializeAgents();
	void SpawnVisualComponents();
	void SpawnMetaHumanActors();
	void SpawnInstancedProxyComponents();
	void InitializeShadowLimbSegments();
	void SpawnContactShadowComponents();
	void SpawnGrassField();
	void SpawnDistantGrassHills();
	void SpawnNiagaraGrassField();
	void ApplyGrassWindMaterialParameters();
	void SpawnTreeField();
	bool SpawnPolyHavenFirTreeField();
	bool SpawnPCGSampleTreeField();
	bool SpawnPVETreeField();
	void ApplyTreeWindMaterialParameters();
	void BakeStaticTreeShadowMasks();
	void InitializeDistantTerrainTexture();
	void InitializeGrassShadowMask(const FVector2D& FieldCenter, float FieldHalfExtent);
	void InitializeGroundShadowMask(const FVector2D& FieldCenter, float FieldHalfExtent);
	void InitializeBloodMask(const FVector2D& FieldCenter, float FieldHalfExtent);
	void ConfigureBloodMaskMaterials();
	void ClearBloodMask();
	void StampBloodDropMask(const FVector2D& Center, float RadiusXCm, float RadiusYCm, float RotationRadians, float Strength, float CoreStrength);
	void GeneratePreviewBloodStains(float RadiusScale, float Strength);
	void GenerateCoherentBloodVFXStain(float TimeSeconds, float RadiusScale, float Strength);
	void UploadBloodMask();
	UStaticMesh* CreateBloodVFXPoolMesh();
	UStaticMesh* CreateBloodVFXRibbonMesh();
	UStaticMesh* CreateBloodVFXSheetMesh();
	void SpawnBloodVFXPreview();
	void UpdateBloodVFXPreview(float DeltaSeconds);
	UStaticMesh* CreateGrassClusterMesh();
	UStaticMesh* CreateDenseGrassClusterMesh();
	UStaticMesh* CreateOuterShellRemovedGrassClusterMesh();
	UStaticMesh* CreateGrassClusterMeshVariant(TObjectPtr<UStaticMesh>& MeshSlot, FName MeshName, int32 BladesPerTile, bool bDenseCoverage, bool bRemoveLowerBladeBand);
	UStaticMesh* CreateDistantGrassHillsMesh();
	UStaticMesh* CreateTreeMesh();
	UStaticMesh* CreateContactShadowMesh();
	UStaticMesh* CreateLimbShadowMesh();
	UMaterialInterface* CreateTintedMaterial(FName ObjectName, const FLinearColor& Color);
	void StepSimulation(float StepSeconds);
	void BuildInputBatch(float StepSeconds);
	void RunModelBatch();
	void ApplyOutputBatch(float StepSeconds);
	void PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds);
	void BuildAgentVisualBoneWorldPositions(int32 AgentIndex, float Alpha, TArray<FVector>& OutPositions) const;
	void UpdateVisualRoots();
	void UpdateMetaHumanRoots();
	void UpdateInstancedProxyVisuals();
	void UpdateContactShadowVisuals();
	void UpdateLimbShadowVisuals();
	void UpdateGrassShadowMask();
	void UpdateGroundShadowMask();
	void PublishLiveVisualReadyIfNeeded();
	void PollLiveVisualIteration();
	void ApplyLiveVisualIterationConfig(const TSharedPtr<FJsonObject>& RootObject);
	void SetupBenchmarkView();
	void LogProgressIfNeeded(float DeltaSeconds);
	void LogFinalSummary() const;

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(Transient)
	TObjectPtr<UNNEModelData> ModelData;

	UPROPERTY(Transient)
	TObjectPtr<USkeletalMesh> BenchmarkMesh;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USkeletalMeshComponent>> MeshComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<AActor>> MetaHumanActors;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USkeletalMeshComponent>> MetaHumanBodyComponents;

	TArray<int32> MetaHumanAgentIndices;
	TArray<FVector> MetaHumanWorldOffsets;
	TArray<FString> MetaHumanActorTiers;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UInstancedStaticMeshComponent>> ProxySegmentComponents;

	UPROPERTY(Transient)
	TObjectPtr<UInstancedStaticMeshComponent> ContactShadowComponent;

	UPROPERTY(Transient)
	TObjectPtr<UInstancedStaticMeshComponent> LimbShadowComponent;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> GrassComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> TreeComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<USkeletalMeshComponent>> SkeletalTreeComponents;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> GrassMaterialInstance;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> TreeMaterialInstance;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> FloorMaterialInstance;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> DistantHillsMaterialInstance;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> GrassShadowMaskTexture;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> GroundShadowMaskTexture;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> BloodMaskTexture;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BloodVFXMaterialInstance;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> BloodVFXPoolComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> BloodVFXStainComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> BloodVFXRibbonComponents;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UStaticMeshComponent>> BloodVFXDropComponents;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> BloodVFXPoolMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> BloodVFXRibbonMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> BloodVFXDropMesh;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> DistantTerrainTexture;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UNiagaraComponent>> NiagaraGrassComponents;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> GrassMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> DenseGrassMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> OuterShellRemovedGrassMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> DistantHillsMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> TreeMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> ContactShadowMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> LimbShadowMesh;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> FloorComponent;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> DistantHillsComponent;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> SkyDomeComponent;

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> BenchmarkCamera;

	UPROPERTY(Transient)
	TObjectPtr<ADirectionalLight> BenchmarkKeyLight;

	UPROPERTY(Transient)
	TObjectPtr<ASkyLight> BenchmarkSkyLight;

	UPROPERTY(Transient)
	TObjectPtr<ASkyAtmosphere> BenchmarkSkyAtmosphere;

	UPROPERTY(Transient)
	TObjectPtr<AVolumetricCloud> BenchmarkVolumetricCloud;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BenchmarkCloudMaterialInstance;

	UPROPERTY(Transient)
	TObjectPtr<AExponentialHeightFog> BenchmarkDistanceFog;

	struct FImpl;
	FImpl* Impl = nullptr;
	float BloodVFXPreviewAgeSeconds = 0.0f;
	float BloodVFXManualTimeSeconds = -1.0f;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyNNBenchmarkWorldSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

private:
	UPROPERTY(Transient)
	TObjectPtr<AProphecyNNCrowdBenchmarkActor> BenchmarkActor;
};
