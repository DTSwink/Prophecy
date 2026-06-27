#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProphecyBloodTexturePaintManager.generated.h"

class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMeshComponent;
class UTextureRenderTarget2D;

USTRUCT(BlueprintType)
struct FProphecyBloodPaintStamp
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint")
	FVector2D UV = FVector2D::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint", meta = (ClampMin = "1.0"))
	float BrushSizePixels = 32.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Intensity = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint")
	float RotationDegrees = 0.0f;
};

USTRUCT(BlueprintType)
struct FProphecyBloodMaterialPair
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint")
	TObjectPtr<UMaterialInterface> CleanMaterial = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint")
	TObjectPtr<UMaterialInterface> BloodMaterial = nullptr;
};

USTRUCT(BlueprintType)
struct FProphecyBloodPaintState
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	TObjectPtr<UStaticMeshComponent> Component = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	int32 MaterialSlot = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	TObjectPtr<UTextureRenderTarget2D> BloodRT = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	TObjectPtr<UMaterialInstanceDynamic> BloodMID = nullptr;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	int32 RTResolution = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	float LastUsedTime = 0.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	int32 NumStamps = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint")
	bool bValid = false;
};

UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyBloodTexturePaintManager : public AActor
{
	GENERATED_BODY()

public:
	AProphecyBloodTexturePaintManager();

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Paint")
	bool TryPaintFromHit(const FHitResult& Hit, float BrushRadiusWorld = 25.0f, float Intensity = 1.0f, int32 OverrideMaterialSlot = -1);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Paint")
	bool DebugPaintUV(UStaticMeshComponent* Component, FVector2D UV, float BrushSizePixels = 32.0f, float Intensity = 1.0f, int32 MaterialSlot = 0);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Paint")
	void FlushPendingBloodStamps();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Paint")
	void ClearRuntimePaintState(bool bRestoreOriginalMaterials = true);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Paint")
	void SetDebugShowMaskOnPaintedMaterials(bool bEnabled);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Paint")
	void SetDebugMode(bool bEnabled, bool bShowMask = false);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Blood Paint")
	FString GetDebugStatsString() const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Blood Paint")
	UTextureRenderTarget2D* GetFirstPaintRenderTarget() const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	TObjectPtr<UMaterialInterface> BrushMaterial = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	TObjectPtr<UMaterialInterface> DefaultBloodMaterialTemplate = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	bool bUseDefaultBloodMaterialTemplateForUnmappedMaterials = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Editor Automation")
	bool bEditorAutoCreateBloodMaterials = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Editor Automation")
	bool bEditorAutoUpdateBloodMaterials = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Editor Automation")
	bool bEditorAllowGeneratedMaterialOverwrite = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Editor Automation")
	bool bEditorSaveGeneratedBloodMaterials = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Editor Automation")
	FString EditorGeneratedBloodMaterialFolder = TEXT("/Game/Prophecy/BloodTexturePainting/Generated");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Editor Automation")
	FString EditorGeneratedBloodMaterialSuffix = TEXT("_BloodPaint");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	TArray<FProphecyBloodMaterialPair> BloodEnabledMaterialPairs;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	FName BloodMaskTextureParameter = TEXT("BloodMaskRT");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	FName BloodIntensityParameter = TEXT("BloodIntensity");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Materials")
	FName DebugShowMaskParameter = TEXT("DebugShowBloodMask");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "0"))
	int32 PaintUVChannel = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	FName PaintableComponentTag = TEXT("BloodPaintable");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bRequirePaintableTag = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bFlushEveryTick = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bFlipV = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bDebugMode = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bDebugPrintHits = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bDebugDrawHitLocations = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bDebugLogRejectedHits = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime")
	bool bDebugShowMaskOnPaintedMaterials = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1", UIMin = "1"))
	int32 DefaultRTResolutionSmall = 256;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1", UIMin = "1"))
	int32 DefaultRTResolutionMedium = 512;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1", UIMin = "1"))
	int32 DefaultRTResolutionLarge = 1024;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1", UIMin = "1"))
	int32 MaxActivePaintRTs = 128;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1", UIMin = "1"))
	int32 MaxStampsPerFrame = 128;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1", UIMin = "1"))
	int32 MaxStampsPerRTPerFrame = 64;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Paint|Runtime", meta = (ClampMin = "1.0", UIMin = "1.0"))
	float DefaultBrushSizePixels = 32.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint|Stats")
	int32 ActivePaintStates = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint|Stats")
	int32 QueuedStampCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint|Stats")
	int32 StampsFlushedLastFrame = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint|Stats")
	int32 StampsDeferredLastFrame = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint|Stats")
	int32 StampsDroppedLastFrame = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Paint|Stats")
	int32 UnsupportedHitCount = 0;

private:
	FString MakeStateKey(const UStaticMeshComponent* Component, int32 MaterialSlot) const;
	bool IsPaintableComponent(const UStaticMeshComponent* Component, UMaterialInterface* CurrentMaterial, FString& OutRejectReason) const;
	int32 ResolveMaterialSlot(UStaticMeshComponent* Component, const FHitResult& Hit, int32 OverrideMaterialSlot, FString& OutRejectReason) const;
	UMaterialInterface* ResolveBloodMaterialTemplate(UMaterialInterface* CurrentMaterial) const;
	UMaterialInterface* ResolveOrCreateBloodMaterialTemplate(UMaterialInterface* CurrentMaterial);
#if WITH_EDITOR
	UMaterialInterface* EditorEnsureBloodMaterialTemplate(UMaterialInterface* CurrentMaterial);
#endif
	FProphecyBloodPaintState* EnsurePaintState(UStaticMeshComponent* Component, int32 MaterialSlot, FString& OutRejectReason);
	int32 ChooseRTResolution(const UStaticMeshComponent* Component) const;
	void QueueStamp(const FString& StateKey, const FProphecyBloodPaintStamp& Stamp);
	void LogReject(const FString& Reason);
	void DebugMessage(const FString& Message, FColor Color = FColor::Cyan) const;

	UPROPERTY(Transient)
	TMap<FString, FProphecyBloodPaintState> PaintStatesByKey;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UMaterialInterface>> OriginalMaterialsByKey;

	TMap<FString, TArray<FProphecyBloodPaintStamp>> PendingStampsByStateKey;
};
