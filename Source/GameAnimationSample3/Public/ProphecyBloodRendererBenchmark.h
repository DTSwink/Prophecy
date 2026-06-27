#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyBloodRendererBenchmark.generated.h"

class ACameraActor;
class AProphecyBloodStainRenderer;
class UDecalComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UProceduralMeshComponent;
class UStaticMesh;
class UStaticMeshComponent;

UENUM()
enum class EProphecyBloodRendererBenchmarkMethod : uint8
{
	DecalComponents,
	InstancedStaticMesh,
	HierarchicalInstancedStaticMesh,
	MeshDecalInstancedStaticMesh,
	ProceduralMesh
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API AProphecyBloodRendererBenchmarkActor : public AActor
{
	GENERATED_BODY()

public:
	AProphecyBloodRendererBenchmarkActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	EProphecyBloodRendererBenchmarkMethod Method = EProphecyBloodRendererBenchmarkMethod::InstancedStaticMesh;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark", meta = (ClampMin = "1"))
	int32 StainCount = 30000;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark", meta = (ClampMin = "0"))
	int32 UpdatesPerFrame = 256;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark", meta = (ClampMin = "0.1"))
	float BenchmarkSeconds = 8.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark", meta = (ClampMin = "0.0"))
	float WarmupSeconds = 2.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark", meta = (ClampMin = "0.0"))
	float ScreenshotSeconds = 1.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	float FieldHalfExtentCm = 2400.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	float MinRadiusCm = 3.5f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	float MaxRadiusCm = 8.0f;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	FString ScreenshotPath;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	FString JsonPath;

	UPROPERTY(EditAnywhere, Category = "Prophecy|Blood Benchmark")
	bool bExitWhenDone = false;

private:
	struct FStainSample
	{
		FVector Position = FVector::ZeroVector;
		FVector Normal = FVector::UpVector;
		float RadiusCm = 6.0f;
		float YawDegrees = 0.0f;
		FLinearColor Color = FLinearColor(0.12f, 0.0f, 0.0f, 1.0f);
	};

	void ApplyCommandLineOverrides();
	bool ParseMethodName(const FString& Name, EProphecyBloodRendererBenchmarkMethod& OutMethod) const;
	FString GetMethodName() const;
	void SetupScene();
	void BuildSamples();
	void PopulateBenchmark();
	void PopulateDecalComponents();
	void PopulateInstancedStaticMesh(bool bHierarchical, bool bMeshDecal);
	void PopulateProceduralMesh();
	void UpdateBenchmarkBatch();
	void UpdateDecalBatch();
	void UpdateInstancedBatch(UInstancedStaticMeshComponent* Component);
	void UpdateProceduralBatch();
	void RequestBenchmarkScreenshot();
	void LogProgressIfNeeded();
	void FinishBenchmark();
	void SaveJsonSummary() const;
	void RecordPopulateChunk(double ChunkSeconds);
	FTransform MakeStainTransform(const FStainSample& Sample, float ExtraYawDegrees = 0.0f) const;
	FStainSample MakeMovedSample(int32 SampleIndex, int32 Generation) const;
	UStaticMesh* CreateTriangleMesh();
	UMaterialInterface* CreateBloodDebugMaterial();
	UMaterialInterface* LoadDecalMaterial() const;
	UMaterialInterface* LoadFloorMaterial() const;

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> FloorComponent;

	UPROPERTY(Transient)
	TObjectPtr<ACameraActor> CameraActor;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UDecalComponent>> DecalComponents;

	UPROPERTY(Transient)
	TObjectPtr<UInstancedStaticMeshComponent> ISMComponent;

	UPROPERTY(Transient)
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> HISMComponent;

	UPROPERTY(Transient)
	TObjectPtr<AProphecyBloodStainRenderer> ProceduralRenderer;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> TriangleMesh;

	TArray<FStainSample> Samples;
	TArray<double> PopulateChunkMs;

	double PopulateTotalMs = 0.0;
	double PopulateFlushMs = 0.0;
	double WarmUpdateSeconds = 0.0;
	double WarmDeltaSeconds = 0.0;
	int64 WarmFrameCount = 0;
	int64 FrameCount = 0;
	int32 UpdateCursor = 0;
	int32 UpdateGeneration = 0;
	float ElapsedSeconds = 0.0f;
	float LastProgressSeconds = 0.0f;
	bool bScreenshotRequested = false;
	bool bFinished = false;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyBloodRendererBenchmarkSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

private:
	UPROPERTY(Transient)
	TObjectPtr<AProphecyBloodRendererBenchmarkActor> BenchmarkActor;
};
