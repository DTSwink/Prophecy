#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/HitResult.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "TimerManager.h"
#include "ProphecyFoliageDecalGridComponent.generated.h"

class AActor;
class UDecalComponent;
class UMaterialInterface;

USTRUCT()
struct FProphecyFoliageDecalGridTile
{
	GENERATED_BODY()

	UPROPERTY(Transient)
	FIntVector Key = FIntVector::ZeroValue;

	UPROPERTY(Transient)
	TObjectPtr<UDecalComponent> Decal = nullptr;

	UPROPERTY(Transient)
	FVector CenterLocation = FVector::ZeroVector;

	UPROPERTY(Transient)
	FVector ProjectionNormal = FVector::UpVector;

	UPROPERTY(Transient)
	float LastTouchedTime = 0.0f;
};

UCLASS(ClassGroup = (Prophecy), meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyFoliageDecalGridComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UProphecyFoliageDecalGridComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Add Floor Hit To Grid", Keywords = "foliage decal floor stain blood grid"))
	int32 AddFloorHitToGrid(const FHitResult& Hit, float RadiusCm = 35.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Add Floor Stain To Grid", Keywords = "foliage decal floor stain blood grid"))
	int32 AddFloorStainToGrid(FVector WorldLocation, FVector WorldNormal, float RadiusCm = 35.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Process Foliage Grid Merges", Keywords = "foliage decal grid merge remesh"))
	void ProcessPendingMerges();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (Keywords = "foliage decal grid merge remesh"))
	void SetMergeProcessingEnabled(bool bEnabled);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (Keywords = "foliage decal grid merge remesh"))
	void StartMergeProcessing();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (Keywords = "foliage decal grid merge remesh"))
	void StopMergeProcessing();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Foliage Decal Grid")
	bool IsMergeProcessingEnabled() const;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid")
	void ClearFoliageDecalGrid();

	UFUNCTION(BlueprintPure, Category = "Prophecy|Foliage Decal Grid")
	FString GetFoliageDecalGridStatsString() const;

	UFUNCTION(BlueprintPure, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Get Active Foliage Grid Decals", Keywords = "foliage decal grid active list current"))
	TArray<UDecalComponent*> GetActiveFoliageGridDecals() const;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid|Debug", meta = (DevelopmentOnly, DisplayName = "Draw Active Foliage Grid Decal Bounds", Keywords = "foliage decal grid debug bounds merge remesh"))
	void DrawActiveFoliageGridDecalBounds(float DurationSeconds = 0.1f, float LineThickness = 2.0f, float BoundsHeightCm = 8.0f, FLinearColor LineColor = FLinearColor(0.0f, 1.0f, 0.0f, 1.0f), bool bColorByMergeLevel = true, bool bDrawLabels = true) const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal")
	TObjectPtr<UMaterialInterface> DecalMaterial = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal")
	FLinearColor DecalColor = FLinearColor(0.11f, 0.0f, 0.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal", meta = (ClampMin = "1.0", UIMin = "1.0"))
	float ProjectionDepthCm = 120.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal", meta = (ClampMin = "0.0", UIMin = "0.0"))
	float ProjectionSurfaceOffsetCm = 2.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal", meta = (ClampMin = "1.0", UIMin = "1.0"))
	float DecalPadding = 1.02f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal")
	float FadeScreenSize = 0.001f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Decal")
	int32 SortOrder = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid", meta = (ClampMin = "1.0", UIMin = "1.0"))
	float CellSizeCm = 12.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid")
	FVector2D GridOrigin = FVector2D::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid")
	bool bLimitGridSize = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid", meta = (ClampMin = "1", UIMin = "1", EditCondition = "bLimitGridSize"))
	FIntPoint GridSizeCells = FIntPoint(256, 256);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid", meta = (ClampMin = "1", UIMin = "1"))
	int32 MaxCellsPerHit = 128;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid", meta = (ClampMin = "1", UIMin = "1"))
	int32 MaxActiveDecals = 4096;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Grid", meta = (ClampMin = "0", UIMin = "0"))
	int32 MaxMergeLevel = 8;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Floor")
	bool bRequireFloorNormal = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Floor", meta = (ClampMin = "-1.0", ClampMax = "1.0"))
	float FloorNormalMinZ = 0.55f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Merge")
	bool bAutoProcessMerges = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Merge", meta = (ClampMin = "0.01", UIMin = "0.01", EditCondition = "bAutoProcessMerges"))
	float MergeProcessIntervalSeconds = 0.05f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Merge", meta = (ClampMin = "0", UIMin = "0"))
	int32 MaxStainedPointsScannedPerPass = 128;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Merge", meta = (ClampMin = "0", UIMin = "0"))
	int32 MaxMergeChecksPerPass = 32;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Merge", meta = (ClampMin = "0", UIMin = "0"))
	int32 MaxMergesPerPass = 4;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Foliage Decal Grid|Merge", meta = (ClampMin = "0.0", UIMin = "0.0"))
	float MergeBudgetMs = 0.25f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Stats")
	int32 ActiveDecalCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Stats")
	int32 PendingMergeCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Stats")
	int32 TotalCellsSpawned = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Stats")
	int32 TotalMerges = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Stats")
	int32 TotalStainedPointsScanned = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Stats")
	int32 TotalPruned = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Foliage Decal Grid|Runtime")
	TArray<TObjectPtr<UDecalComponent>> ActiveDecalComponents;

private:
	FIntVector MakeKeyForWorldLocation(const FVector& WorldLocation, int32 Level) const;
	FVector MakeTileCenterLocation(const FIntVector& Key, float FloorZ) const;
	FVector MakeDecalLocation(const FVector& CenterLocation, const FVector& ProjectionNormal) const;
	FRotator MakeDecalRotation(const FVector& ProjectionNormal) const;
	float GetTileSizeCm(int32 Level) const;
	int32 GetTileSizeCells(int32 Level) const;
	bool IsKeyInsideGridBounds(const FIntVector& Key) const;
	FIntVector GetChildKey(const FIntVector& ParentKey, int32 ChildOffsetX, int32 ChildOffsetY) const;
	bool TryAddTile(const FIntVector& Key, FVector CenterLocation, FVector ProjectionNormal);
	void ScanActiveStainedTilesForMergeCandidates(double StartSeconds, double BudgetSeconds);
	void AdvanceScanCursor();
	void TrackActiveTileKey(const FIntVector& Key);
	void UntrackActiveTileKey(const FIntVector& Key);
	void RefreshMergeTimer();
	bool TryEnqueueParentMerge(const FIntVector& ChildKey);
	bool CanMergeParent(const FIntVector& ParentKey, TArray<FIntVector>& OutChildKeys) const;
	bool MergeParent(const FIntVector& ParentKey, const TArray<FIntVector>& ChildKeys);
	UDecalComponent* SpawnTileDecal(const FProphecyFoliageDecalGridTile& Tile);
	void UpdateTileDecal(FProphecyFoliageDecalGridTile& Tile) const;
	void DestroyTileDecal(FProphecyFoliageDecalGridTile& Tile);
	void RemoveOccupiedLeavesForTile(const FProphecyFoliageDecalGridTile& Tile);
	void RegisterActiveDecal(UDecalComponent* Decal);
	void UnregisterActiveDecal(UDecalComponent* Decal);
	void CompactActiveDecalList();
	void PruneOldestTileIfNeeded();
	void RefreshStats();

	UPROPERTY(Transient)
	TMap<FIntVector, FProphecyFoliageDecalGridTile> ActiveTiles;

	UPROPERTY(Transient)
	TArray<FIntVector> MergeQueue;

	UPROPERTY(Transient)
	TArray<FIntVector> ActiveScanKeys;

	TSet<FIntVector> QueuedMergeKeys;
	TSet<FIntVector> ActiveScanKeySet;
	TSet<FIntPoint> OccupiedLeafKeys;
	FTimerHandle MergeTimerHandle;
	int32 ActiveScanCursor = 0;
	bool bScanForward = true;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyFoliageDecalGridBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Add Floor Hit To Foliage Decal Grid", Keywords = "foliage decal floor stain blood grid"))
	static int32 AddFloorHitToFoliageDecalGrid(UProphecyFoliageDecalGridComponent* DecalGrid, const FHitResult& Hit, float RadiusCm = 35.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Add Floor Hit To Foliage Decal Grid Ref", Keywords = "foliage decal floor stain blood grid livecoding ref object"))
	static int32 AddFloorHitToFoliageDecalGridRef(UObject* DecalGridRef, const FHitResult& Hit, float RadiusCm = 35.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Set Foliage Grid Merge Processing Enabled", Keywords = "foliage decal grid merge remesh"))
	static void SetFoliageGridMergeProcessingEnabled(UProphecyFoliageDecalGridComponent* DecalGrid, bool bEnabled);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Set Foliage Grid Merge Processing Enabled Ref", Keywords = "foliage decal grid merge remesh livecoding ref object"))
	static void SetFoliageGridMergeProcessingEnabledRef(UObject* DecalGridRef, bool bEnabled);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Get Active Foliage Grid Decals", Keywords = "foliage decal grid active list current"))
	static TArray<UDecalComponent*> GetActiveFoliageGridDecals(UProphecyFoliageDecalGridComponent* DecalGrid);

	UFUNCTION(BlueprintPure, Category = "Prophecy|Foliage Decal Grid", meta = (DisplayName = "Get Active Foliage Grid Decals Ref", Keywords = "foliage decal grid active list current livecoding ref object"))
	static TArray<UDecalComponent*> GetActiveFoliageGridDecalsRef(UObject* DecalGridRef);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid|Debug", meta = (DevelopmentOnly, DisplayName = "Draw Foliage Grid Decal Bounds", Keywords = "foliage decal grid debug bounds merge remesh"))
	static void DrawFoliageGridDecalBounds(UProphecyFoliageDecalGridComponent* DecalGrid, float DurationSeconds = 0.1f, float LineThickness = 2.0f, float BoundsHeightCm = 8.0f, FLinearColor LineColor = FLinearColor(0.0f, 1.0f, 0.0f, 1.0f), bool bColorByMergeLevel = true, bool bDrawLabels = true);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Foliage Decal Grid|Debug", meta = (DevelopmentOnly, DisplayName = "Draw Foliage Grid Decal Bounds Ref", Keywords = "foliage decal grid debug bounds merge remesh livecoding ref object"))
	static void DrawFoliageGridDecalBoundsRef(UObject* DecalGridRef, float DurationSeconds = 0.1f, float LineThickness = 2.0f, float BoundsHeightCm = 8.0f, FLinearColor LineColor = FLinearColor(0.0f, 1.0f, 0.0f, 1.0f), bool bColorByMergeLevel = true, bool bDrawLabels = true);
};
