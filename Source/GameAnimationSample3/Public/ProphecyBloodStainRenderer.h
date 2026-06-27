#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "NiagaraDataInterfaceExport.h"
#include "ProceduralMeshComponent.h"
#include "GameFramework/Actor.h"
#include "ProphecyBloodStainRenderer.generated.h"

class UMaterialInterface;
class UNiagaraComponent;
class UNiagaraSystem;

UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyBloodStainRenderer : public AActor, public INiagaraParticleCallbackHandler
{
	GENERATED_BODY()

public:
	AProphecyBloodStainRenderer();

	virtual void BeginPlay() override;
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void ReceiveParticleData_Implementation(const TArray<FBasicParticleData>& Data, UNiagaraSystem* NiagaraSystem, const FVector& SimulationPositionOffset) override;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood")
	void AddBloodHit(const FVector& WorldPosition, const FVector& WorldNormal, float RadiusCm = 0.0f, FLinearColor Color = FLinearColor(0.11f, 0.0f, 0.0f, 1.0f));

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood")
	void AddBloodParticleData(const TArray<FBasicParticleData>& Data, const FVector& SimulationPositionOffset);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood")
	void FlushPendingStains();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood")
	void ClearBloodStains();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood")
	void BindAsNiagaraExportCallback(UNiagaraComponent* NiagaraComponent, FName CallbackUserParameterName = TEXT("User.CallbackHandler"));

	void EnsureMeshInitialized();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood")
	TObjectPtr<UProceduralMeshComponent> MeshComponent;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood", meta = (ClampMin = "1", UIMin = "1"))
	int32 MaxStains = 30000;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood", meta = (ClampMin = "0.1", UIMin = "0.1"))
	float DefaultRadiusCm = 7.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood", meta = (ClampMin = "0.0", UIMin = "0.0"))
	float ParticleSizeToRadius = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood", meta = (ClampMin = "0.0", UIMin = "0.0"))
	float RadiusJitter = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood")
	float SurfaceOffsetCm = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood")
	FLinearColor DefaultColor = FLinearColor(0.11f, 0.0f, 0.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood")
	TObjectPtr<UMaterialInterface> StainMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood")
	bool bFlushEveryTick = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood")
	int32 ActiveStainCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood")
	int32 TotalStainsAccepted = 0;

private:
	void WriteTriangle(int32 StainIndex, const FVector& WorldPosition, const FVector& WorldNormal, float RadiusCm, const FLinearColor& Color);
	void WriteHiddenTriangle(int32 StainIndex);
	FVector MakeStableFallbackNormal(const FVector& Normal) const;

	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FLinearColor> VertexColors;
	TArray<struct FProcMeshTangent> Tangents;

	int32 NextStainIndex = 0;
	uint32 StainSerial = 0;
	bool bMeshInitialized = false;
	bool bMeshDirty = false;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyBloodStainBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood", meta = (WorldContext = "WorldContextObject"))
	static AProphecyBloodStainRenderer* GetOrSpawnBloodStainRenderer(const UObject* WorldContextObject);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood", meta = (WorldContext = "WorldContextObject"))
	static AProphecyBloodStainRenderer* AddBloodHitToWorld(const UObject* WorldContextObject, FVector WorldPosition, FVector WorldNormal, float RadiusCm = 0.0f, FLinearColor Color = FLinearColor(0.11f, 0.0f, 0.0f, 1.0f));

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood", meta = (WorldContext = "WorldContextObject"))
	static AProphecyBloodStainRenderer* AddBloodParticleDataToWorld(const UObject* WorldContextObject, const TArray<FBasicParticleData>& Data, FVector SimulationPositionOffset);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood", meta = (WorldContext = "WorldContextObject"))
	static AProphecyBloodStainRenderer* BindBloodRendererAsNiagaraExportCallback(const UObject* WorldContextObject, UNiagaraComponent* NiagaraComponent, FName CallbackUserParameterName = TEXT("User.CallbackHandler"));
};
