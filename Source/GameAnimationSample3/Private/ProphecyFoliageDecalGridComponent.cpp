#include "ProphecyFoliageDecalGridComponent.h"

#include "Components/DecalComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
DEFINE_LOG_CATEGORY_STATIC(LogProphecyFoliageDecalGrid, Log, All);

FVector SafeNormalOrUp(const FVector& Value)
{
	return Value.GetSafeNormal(KINDA_SMALL_NUMBER, FVector::UpVector);
}

bool IsLikelyFoliageDecalGridComponent(const UObject* Object)
{
	if (!Object)
	{
		return false;
	}

	if (Object->IsA<UProphecyFoliageDecalGridComponent>())
	{
		return true;
	}

	const UClass* Class = Object->GetClass();
	return Class && Class->GetName().Contains(TEXT("ProphecyFoliageDecalGrid"));
}

int32 AddFloorHitToFoliageDecalGridObject(UObject* DecalGridObject, const FHitResult& Hit, float RadiusCm)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		return DecalGrid->AddFloorHitToGrid(Hit, RadiusCm);
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return 0;
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("AddFloorHitToGrid"));
	if (!Function)
	{
		return 0;
	}

	struct FAddFloorHitToGridParams
	{
		FHitResult Hit;
		float RadiusCm = 35.0f;
		int32 ReturnValue = 0;
	};

	FAddFloorHitToGridParams Params;
	Params.Hit = Hit;
	Params.RadiusCm = RadiusCm;
	DecalGridObject->ProcessEvent(Function, &Params);
	return Params.ReturnValue;
}

void SetFoliageGridMergeProcessingEnabledObject(UObject* DecalGridObject, bool bEnabled)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		DecalGrid->SetMergeProcessingEnabled(bEnabled);
		return;
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return;
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("SetMergeProcessingEnabled"));
	if (!Function)
	{
		return;
	}

	struct FSetMergeProcessingEnabledParams
	{
		bool bEnabled = false;
	};

	FSetMergeProcessingEnabledParams Params;
	Params.bEnabled = bEnabled;
	DecalGridObject->ProcessEvent(Function, &Params);
}

TArray<UDecalComponent*> GetActiveFoliageGridDecalsObject(UObject* DecalGridObject)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		return DecalGrid->GetActiveFoliageGridDecals();
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return TArray<UDecalComponent*>();
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("GetActiveFoliageGridDecals"));
	if (!Function)
	{
		return TArray<UDecalComponent*>();
	}

	struct FGetActiveFoliageGridDecalsParams
	{
		TArray<UDecalComponent*> ReturnValue;
	};

	FGetActiveFoliageGridDecalsParams Params;
	DecalGridObject->ProcessEvent(Function, &Params);
	return Params.ReturnValue;
}

void DrawFoliageGridDecalBoundsObject(UObject* DecalGridObject, float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		DecalGrid->DrawActiveFoliageGridDecalBounds(DurationSeconds, LineThickness, BoundsHeightCm, LineColor, bColorByMergeLevel, bDrawLabels);
		return;
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return;
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("DrawActiveFoliageGridDecalBounds"));
	if (!Function)
	{
		return;
	}

	struct FDrawActiveFoliageGridDecalBoundsParams
	{
		float DurationSeconds = 0.1f;
		float LineThickness = 2.0f;
		float BoundsHeightCm = 8.0f;
		FLinearColor LineColor = FLinearColor(0.0f, 1.0f, 0.0f, 1.0f);
		bool bColorByMergeLevel = true;
		bool bDrawLabels = true;
	};

	FDrawActiveFoliageGridDecalBoundsParams Params;
	Params.DurationSeconds = DurationSeconds;
	Params.LineThickness = LineThickness;
	Params.BoundsHeightCm = BoundsHeightCm;
	Params.LineColor = LineColor;
	Params.bColorByMergeLevel = bColorByMergeLevel;
	Params.bDrawLabels = bDrawLabels;
	DecalGridObject->ProcessEvent(Function, &Params);
}
}

UProphecyFoliageDecalGridComponent::UProphecyFoliageDecalGridComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	PrimaryComponentTick.bStartWithTickEnabled = false;

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DecalMaterialFinder(TEXT("/Game/_mygame/blood2/MI_blooddecal.MI_blooddecal"));
	if (DecalMaterialFinder.Succeeded())
	{
		DecalMaterial = DecalMaterialFinder.Object;
	}
}

void UProphecyFoliageDecalGridComponent::BeginPlay()
{
	Super::BeginPlay();
	RefreshMergeTimer();
	RefreshStats();
}

void UProphecyFoliageDecalGridComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(MergeTimerHandle);
	}
	ClearFoliageDecalGrid();
	Super::EndPlay(EndPlayReason);
}

int32 UProphecyFoliageDecalGridComponent::AddFloorHitToGrid(const FHitResult& Hit, float RadiusCm)
{
	if (!Hit.bBlockingHit)
	{
		return 0;
	}

	const FVector WorldLocation = Hit.ImpactPoint.IsNearlyZero() ? Hit.Location : Hit.ImpactPoint;
	const FVector WorldNormal = Hit.ImpactNormal.IsNearlyZero() ? Hit.Normal : Hit.ImpactNormal;
	return AddFloorStainToGrid(WorldLocation, WorldNormal, RadiusCm);
}

int32 UProphecyFoliageDecalGridComponent::AddFloorStainToGrid(FVector WorldLocation, FVector WorldNormal, float RadiusCm)
{
	if (!DecalMaterial || CellSizeCm <= KINDA_SMALL_NUMBER || MaxCellsPerHit <= 0)
	{
		return 0;
	}

	FVector Normal = WorldNormal.GetSafeNormal();
	if (Normal.IsNearlyZero())
	{
		Normal = FVector::UpVector;
	}

	if (bRequireFloorNormal && Normal.Z < FloorNormalMinZ)
	{
		return 0;
	}

	const float SafeRadiusCm = FMath::Max(0.0f, RadiusCm);
	const FIntVector CenterKey = MakeKeyForWorldLocation(WorldLocation, 0);
	const int32 SearchRadiusCells = SafeRadiusCm > KINDA_SMALL_NUMBER
		? FMath::Max(0, FMath::CeilToInt((SafeRadiusCm + CellSizeCm * 0.5f) / CellSizeCm))
		: 0;
	const float IncludeRadiusCm = SafeRadiusCm > KINDA_SMALL_NUMBER ? SafeRadiusCm + CellSizeCm * 0.7072f : 0.0f;
	const float IncludeRadiusSquared = IncludeRadiusCm * IncludeRadiusCm;

	struct FCandidateCell
	{
		FIntVector Key = FIntVector::ZeroValue;
		FVector CenterLocation = FVector::ZeroVector;
		float DistanceSquared = 0.0f;
	};

	TArray<FCandidateCell> Candidates;
	const int32 CandidateReserve = FMath::Square(SearchRadiusCells * 2 + 1);
	Candidates.Reserve(FMath::Min(CandidateReserve, MaxCellsPerHit * 2));

	for (int32 Y = CenterKey.Y - SearchRadiusCells; Y <= CenterKey.Y + SearchRadiusCells; ++Y)
	{
		for (int32 X = CenterKey.X - SearchRadiusCells; X <= CenterKey.X + SearchRadiusCells; ++X)
		{
			const FIntVector Key(X, Y, 0);
			if (!IsKeyInsideGridBounds(Key))
			{
				continue;
			}

			const FVector CenterLocation = MakeTileCenterLocation(Key, WorldLocation.Z);
			const FVector2D Delta(CenterLocation.X - WorldLocation.X, CenterLocation.Y - WorldLocation.Y);
			const float DistanceSquared = Delta.SizeSquared();
			if (SafeRadiusCm > KINDA_SMALL_NUMBER && DistanceSquared > IncludeRadiusSquared)
			{
				continue;
			}

			FCandidateCell& Candidate = Candidates.AddDefaulted_GetRef();
			Candidate.Key = Key;
			Candidate.CenterLocation = CenterLocation;
			Candidate.DistanceSquared = DistanceSquared;
		}
	}

	Candidates.Sort([](const FCandidateCell& A, const FCandidateCell& B)
	{
		return A.DistanceSquared < B.DistanceSquared;
	});

	int32 AcceptedCells = 0;
	const int32 CandidateLimit = FMath::Min(Candidates.Num(), MaxCellsPerHit);
	for (int32 CandidateIndex = 0; CandidateIndex < CandidateLimit; ++CandidateIndex)
	{
		const FCandidateCell& Candidate = Candidates[CandidateIndex];
		if (TryAddTile(Candidate.Key, Candidate.CenterLocation, Normal))
		{
			AcceptedCells += 1;
		}
	}

	RefreshStats();
	return AcceptedCells;
}

void UProphecyFoliageDecalGridComponent::ProcessPendingMerges()
{
	const double StartSeconds = FPlatformTime::Seconds();
	const double BudgetSeconds = FMath::Max(0.0f, MergeBudgetMs) / 1000.0f;
	ScanActiveStainedTilesForMergeCandidates(StartSeconds, BudgetSeconds);

	if (MergeQueue.Num() == 0 || MaxMergeChecksPerPass <= 0 || MaxMergesPerPass <= 0)
	{
		RefreshStats();
		return;
	}

	int32 Checks = 0;
	int32 Merges = 0;

	while (MergeQueue.Num() > 0 && Checks < MaxMergeChecksPerPass && Merges < MaxMergesPerPass)
	{
		if (BudgetSeconds > 0.0 && FPlatformTime::Seconds() - StartSeconds >= BudgetSeconds)
		{
			break;
		}

		const FIntVector ParentKey = MergeQueue[0];
		MergeQueue.RemoveAtSwap(0, 1, EAllowShrinking::No);
		QueuedMergeKeys.Remove(ParentKey);
		Checks += 1;

		TArray<FIntVector> ChildKeys;
		if (!CanMergeParent(ParentKey, ChildKeys))
		{
			continue;
		}

		if (MergeParent(ParentKey, ChildKeys))
		{
			Merges += 1;
			TotalMerges += 1;
			TryEnqueueParentMerge(ParentKey);
		}
	}

	RefreshStats();
}

void UProphecyFoliageDecalGridComponent::SetMergeProcessingEnabled(bool bEnabled)
{
	bAutoProcessMerges = bEnabled;
	RefreshMergeTimer();
}

void UProphecyFoliageDecalGridComponent::StartMergeProcessing()
{
	SetMergeProcessingEnabled(true);
}

void UProphecyFoliageDecalGridComponent::StopMergeProcessing()
{
	SetMergeProcessingEnabled(false);
}

bool UProphecyFoliageDecalGridComponent::IsMergeProcessingEnabled() const
{
	if (const UWorld* World = GetWorld())
	{
		return World->GetTimerManager().IsTimerActive(MergeTimerHandle);
	}

	return bAutoProcessMerges;
}

void UProphecyFoliageDecalGridComponent::ClearFoliageDecalGrid()
{
	for (TPair<FIntVector, FProphecyFoliageDecalGridTile>& TilePair : ActiveTiles)
	{
		DestroyTileDecal(TilePair.Value);
	}

	ActiveTiles.Reset();
	MergeQueue.Reset();
	ActiveScanKeys.Reset();
	QueuedMergeKeys.Reset();
	ActiveScanKeySet.Reset();
	OccupiedLeafKeys.Reset();
	ActiveScanCursor = 0;
	bScanForward = true;
	RefreshStats();
}

FString UProphecyFoliageDecalGridComponent::GetFoliageDecalGridStatsString() const
{
	return FString::Printf(TEXT("FoliageDecalGrid active=%d pendingMerges=%d spawnedCells=%d scanned=%d merges=%d pruned=%d"),
		ActiveDecalCount,
		PendingMergeCount,
		TotalCellsSpawned,
		TotalStainedPointsScanned,
		TotalMerges,
		TotalPruned);
}

TArray<UDecalComponent*> UProphecyFoliageDecalGridComponent::GetActiveFoliageGridDecals() const
{
	TArray<UDecalComponent*> Result;
	Result.Reserve(ActiveDecalComponents.Num());
	for (UDecalComponent* Decal : ActiveDecalComponents)
	{
		if (IsValid(Decal))
		{
			Result.Add(Decal);
		}
	}
	return Result;
}

void UProphecyFoliageDecalGridComponent::DrawActiveFoliageGridDecalBounds(float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels) const
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	static const FColor LevelColors[] =
	{
		FColor::Green,
		FColor::Cyan,
		FColor::Yellow,
		FColor::Orange,
		FColor::Magenta,
		FColor::Red,
		FColor::Blue,
		FColor::White
	};

	const float SafeDuration = FMath::Max(0.0f, DurationSeconds);
	const float SafeThickness = FMath::Max(0.0f, LineThickness);
	const float SafeBoundsHeightCm = FMath::Max(0.0f, BoundsHeightCm);
	const FColor DefaultColor = LineColor.ToFColor(true);

	for (const TPair<FIntVector, FProphecyFoliageDecalGridTile>& TilePair : ActiveTiles)
	{
		const FProphecyFoliageDecalGridTile& Tile = TilePair.Value;
		const UDecalComponent* Decal = Tile.Decal;
		if (!IsValid(Decal))
		{
			continue;
		}

		const int32 LevelColorIndex = FMath::Abs(Tile.Key.Z) % UE_ARRAY_COUNT(LevelColors);
		const FColor DebugColor = bColorByMergeLevel ? LevelColors[LevelColorIndex] : DefaultColor;
		FVector Extent = Decal->DecalSize * 0.5f;
		if (Extent.SizeSquared() <= UE_SMALL_NUMBER)
		{
			const float TileSize = GetTileSizeCm(Tile.Key.Z) * DecalPadding;
			Extent = FVector(ProjectionDepthCm * 0.5f, TileSize * 0.5f, TileSize * 0.5f);
		}

		FVector Center = Decal->GetComponentLocation();
		if (SafeBoundsHeightCm > KINDA_SMALL_NUMBER)
		{
			const FVector Normal = SafeNormalOrUp(Tile.ProjectionNormal);
			Extent.X = SafeBoundsHeightCm * 0.5f;
			Center = Tile.CenterLocation + Normal * (Extent.X + ProjectionSurfaceOffsetCm);
		}

		const FQuat Rotation = Decal->GetComponentQuat();
		DrawDebugBox(World, Center, Extent, Rotation, DebugColor, false, SafeDuration, 0, SafeThickness);

		if (bDrawLabels)
		{
			const FString Label = FString::Printf(TEXT("L%d %.0fcm"), Tile.Key.Z, GetTileSizeCm(Tile.Key.Z));
			DrawDebugString(World, Center + FVector(0.0, 0.0, Extent.Z + 8.0), Label, nullptr, DebugColor, SafeDuration, false, 1.0f);
		}
	}
}

FIntVector UProphecyFoliageDecalGridComponent::MakeKeyForWorldLocation(const FVector& WorldLocation, int32 Level) const
{
	const float TileSize = FMath::Max(1.0f, CellSizeCm);
	return FIntVector(
		FMath::FloorToInt((WorldLocation.X - GridOrigin.X) / TileSize),
		FMath::FloorToInt((WorldLocation.Y - GridOrigin.Y) / TileSize),
		Level);
}

FVector UProphecyFoliageDecalGridComponent::MakeTileCenterLocation(const FIntVector& Key, float FloorZ) const
{
	const int32 TileSizeCells = GetTileSizeCells(Key.Z);
	const float LeafSize = FMath::Max(1.0f, CellSizeCm);
	return FVector(
		GridOrigin.X + (static_cast<float>(Key.X) + static_cast<float>(TileSizeCells) * 0.5f) * LeafSize,
		GridOrigin.Y + (static_cast<float>(Key.Y) + static_cast<float>(TileSizeCells) * 0.5f) * LeafSize,
		FloorZ);
}

FVector UProphecyFoliageDecalGridComponent::MakeDecalLocation(const FVector& CenterLocation, const FVector& ProjectionNormal) const
{
	const FVector Normal = SafeNormalOrUp(ProjectionNormal);
	return CenterLocation + Normal * (ProjectionDepthCm * 0.5f + ProjectionSurfaceOffsetCm);
}

FRotator UProphecyFoliageDecalGridComponent::MakeDecalRotation(const FVector& ProjectionNormal) const
{
	const FVector Normal = SafeNormalOrUp(ProjectionNormal);
	return FRotationMatrix::MakeFromX(-Normal).Rotator();
}

float UProphecyFoliageDecalGridComponent::GetTileSizeCm(int32 Level) const
{
	return FMath::Max(1.0f, CellSizeCm) * static_cast<float>(GetTileSizeCells(Level));
}

int32 UProphecyFoliageDecalGridComponent::GetTileSizeCells(int32 Level) const
{
	const int32 SafeLevel = FMath::Clamp(Level, 0, 20);
	return 1 << SafeLevel;
}

bool UProphecyFoliageDecalGridComponent::IsKeyInsideGridBounds(const FIntVector& Key) const
{
	if (!bLimitGridSize)
	{
		return true;
	}

	const int32 Width = FMath::Max(1, GridSizeCells.X);
	const int32 Height = FMath::Max(1, GridSizeCells.Y);
	const int32 TileSizeCells = GetTileSizeCells(Key.Z);
	return Key.X >= 0 && Key.X + TileSizeCells <= Width && Key.Y >= 0 && Key.Y + TileSizeCells <= Height;
}

FIntVector UProphecyFoliageDecalGridComponent::GetChildKey(const FIntVector& ParentKey, int32 ChildOffsetX, int32 ChildOffsetY) const
{
	const int32 ChildLevel = FMath::Max(0, ParentKey.Z - 1);
	const int32 ChildSizeCells = GetTileSizeCells(ChildLevel);
	return FIntVector(ParentKey.X + ChildOffsetX * ChildSizeCells, ParentKey.Y + ChildOffsetY * ChildSizeCells, ChildLevel);
}

bool UProphecyFoliageDecalGridComponent::TryAddTile(const FIntVector& Key, FVector CenterLocation, FVector ProjectionNormal)
{
	const FIntPoint LeafKey(Key.X, Key.Y);
	if (OccupiedLeafKeys.Contains(LeafKey) || !IsKeyInsideGridBounds(Key))
	{
		return false;
	}

	PruneOldestTileIfNeeded();

	FProphecyFoliageDecalGridTile NewTile;
	NewTile.Key = Key;
	NewTile.CenterLocation = CenterLocation;
	NewTile.ProjectionNormal = SafeNormalOrUp(ProjectionNormal);
	NewTile.LastTouchedTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	NewTile.Decal = SpawnTileDecal(NewTile);
	if (!NewTile.Decal)
	{
		return false;
	}

	ActiveTiles.Add(Key, NewTile);
	OccupiedLeafKeys.Add(LeafKey);
	TrackActiveTileKey(Key);
	TotalCellsSpawned += 1;
	TryEnqueueParentMerge(Key);
	return true;
}

void UProphecyFoliageDecalGridComponent::ScanActiveStainedTilesForMergeCandidates(double StartSeconds, double BudgetSeconds)
{
	if (MaxStainedPointsScannedPerPass <= 0 || ActiveScanKeys.Num() == 0)
	{
		return;
	}

	int32 PointsScannedThisPass = 0;
	while (ActiveScanKeys.Num() > 0 && PointsScannedThisPass < MaxStainedPointsScannedPerPass)
	{
		if (BudgetSeconds > 0.0 && FPlatformTime::Seconds() - StartSeconds >= BudgetSeconds)
		{
			break;
		}

		ActiveScanCursor = FMath::Clamp(ActiveScanCursor, 0, ActiveScanKeys.Num() - 1);
		const FIntVector ScanKey = ActiveScanKeys[ActiveScanCursor];
		AdvanceScanCursor();

		if (ActiveTiles.Contains(ScanKey))
		{
			TryEnqueueParentMerge(ScanKey);
			PointsScannedThisPass += 1;
			TotalStainedPointsScanned += 1;
		}
		else
		{
			UntrackActiveTileKey(ScanKey);
		}
	}
}

void UProphecyFoliageDecalGridComponent::AdvanceScanCursor()
{
	if (ActiveScanKeys.Num() <= 1)
	{
		ActiveScanCursor = 0;
		bScanForward = true;
		return;
	}

	if (bScanForward)
	{
		if (ActiveScanCursor >= ActiveScanKeys.Num() - 1)
		{
			bScanForward = false;
			ActiveScanCursor = ActiveScanKeys.Num() - 2;
		}
		else
		{
			ActiveScanCursor += 1;
		}
		return;
	}

	if (ActiveScanCursor <= 0)
	{
		bScanForward = true;
		ActiveScanCursor = 1;
	}
	else
	{
		ActiveScanCursor -= 1;
	}
}

void UProphecyFoliageDecalGridComponent::TrackActiveTileKey(const FIntVector& Key)
{
	if (ActiveScanKeySet.Contains(Key))
	{
		return;
	}

	ActiveScanKeySet.Add(Key);
	ActiveScanKeys.Add(Key);
	ActiveScanCursor = FMath::Clamp(ActiveScanCursor, 0, ActiveScanKeys.Num() - 1);
}

void UProphecyFoliageDecalGridComponent::UntrackActiveTileKey(const FIntVector& Key)
{
	if (!ActiveScanKeySet.Remove(Key))
	{
		return;
	}

	const int32 RemovedIndex = ActiveScanKeys.Find(Key);
	if (RemovedIndex != INDEX_NONE)
	{
		ActiveScanKeys.RemoveAt(RemovedIndex, 1, EAllowShrinking::No);
		if (RemovedIndex < ActiveScanCursor)
		{
			ActiveScanCursor -= 1;
		}
	}

	if (ActiveScanKeys.Num() == 0)
	{
		ActiveScanCursor = 0;
		bScanForward = true;
	}
	else
	{
		ActiveScanCursor = FMath::Clamp(ActiveScanCursor, 0, ActiveScanKeys.Num() - 1);
	}
}

void UProphecyFoliageDecalGridComponent::RefreshMergeTimer()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	World->GetTimerManager().ClearTimer(MergeTimerHandle);
	if (!bAutoProcessMerges)
	{
		return;
	}

	World->GetTimerManager().SetTimer(
		MergeTimerHandle,
		this,
		&UProphecyFoliageDecalGridComponent::ProcessPendingMerges,
		FMath::Max(0.01f, MergeProcessIntervalSeconds),
		true);
}

bool UProphecyFoliageDecalGridComponent::TryEnqueueParentMerge(const FIntVector& ChildKey)
{
	if (ChildKey.Z >= MaxMergeLevel)
	{
		return false;
	}

	bool bQueuedAny = false;
	const int32 ChildSizeCells = GetTileSizeCells(ChildKey.Z);
	for (int32 ChildOffsetY = 0; ChildOffsetY < 2; ++ChildOffsetY)
	{
		for (int32 ChildOffsetX = 0; ChildOffsetX < 2; ++ChildOffsetX)
		{
			const FIntVector ParentKey(
				ChildKey.X - ChildOffsetX * ChildSizeCells,
				ChildKey.Y - ChildOffsetY * ChildSizeCells,
				ChildKey.Z + 1);
			if (!IsKeyInsideGridBounds(ParentKey) || ActiveTiles.Contains(ParentKey) || QueuedMergeKeys.Contains(ParentKey))
			{
				continue;
			}

			TArray<FIntVector> ChildKeys;
			if (!CanMergeParent(ParentKey, ChildKeys))
			{
				continue;
			}

			MergeQueue.Add(ParentKey);
			QueuedMergeKeys.Add(ParentKey);
			bQueuedAny = true;
		}
	}

	if (bQueuedAny)
	{
		RefreshStats();
	}
	return bQueuedAny;
}

bool UProphecyFoliageDecalGridComponent::CanMergeParent(const FIntVector& ParentKey, TArray<FIntVector>& OutChildKeys) const
{
	OutChildKeys.Reset();
	if (ParentKey.Z <= 0 || ParentKey.Z > MaxMergeLevel || ActiveTiles.Contains(ParentKey))
	{
		return false;
	}

	for (int32 ChildOffsetY = 0; ChildOffsetY < 2; ++ChildOffsetY)
	{
		for (int32 ChildOffsetX = 0; ChildOffsetX < 2; ++ChildOffsetX)
		{
			const FIntVector ChildKey = GetChildKey(ParentKey, ChildOffsetX, ChildOffsetY);
			if (!ActiveTiles.Contains(ChildKey))
			{
				return false;
			}
			OutChildKeys.Add(ChildKey);
		}
	}

	return OutChildKeys.Num() == 4;
}

bool UProphecyFoliageDecalGridComponent::MergeParent(const FIntVector& ParentKey, const TArray<FIntVector>& ChildKeys)
{
	if (ChildKeys.Num() != 4 || ActiveTiles.Contains(ParentKey))
	{
		return false;
	}

	FVector AverageLocation = FVector::ZeroVector;
	FVector AverageNormal = FVector::ZeroVector;
	float LastTouchedTime = 0.0f;

	for (const FIntVector& ChildKey : ChildKeys)
	{
		const FProphecyFoliageDecalGridTile* ChildTile = ActiveTiles.Find(ChildKey);
		if (!ChildTile)
		{
			return false;
		}

		AverageLocation += ChildTile->CenterLocation;
		AverageNormal += ChildTile->ProjectionNormal;
		LastTouchedTime = FMath::Max(LastTouchedTime, ChildTile->LastTouchedTime);
	}

	AverageLocation /= 4.0f;
	AverageLocation = MakeTileCenterLocation(ParentKey, AverageLocation.Z);
	AverageNormal = SafeNormalOrUp(AverageNormal);

	FProphecyFoliageDecalGridTile ParentTile;
	ParentTile.Key = ParentKey;
	ParentTile.CenterLocation = AverageLocation;
	ParentTile.ProjectionNormal = AverageNormal;
	ParentTile.LastTouchedTime = LastTouchedTime;
	ParentTile.Decal = SpawnTileDecal(ParentTile);
	if (!ParentTile.Decal)
	{
		return false;
	}

	for (const FIntVector& ChildKey : ChildKeys)
	{
		if (FProphecyFoliageDecalGridTile* ChildTile = ActiveTiles.Find(ChildKey))
		{
			DestroyTileDecal(*ChildTile);
		}
		ActiveTiles.Remove(ChildKey);
		UntrackActiveTileKey(ChildKey);
	}

	ActiveTiles.Add(ParentKey, ParentTile);
	TrackActiveTileKey(ParentKey);
	return true;
}

UDecalComponent* UProphecyFoliageDecalGridComponent::SpawnTileDecal(const FProphecyFoliageDecalGridTile& Tile)
{
	AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	if (!Owner || !World || !DecalMaterial)
	{
		return nullptr;
	}

	UDecalComponent* Decal = NewObject<UDecalComponent>(Owner);
	if (!Decal)
	{
		return nullptr;
	}

	Decal->SetMobility(EComponentMobility::Movable);
	Decal->SetDecalMaterial(DecalMaterial);
	Decal->DecalSize = FVector(ProjectionDepthCm, GetTileSizeCm(Tile.Key.Z) * DecalPadding, GetTileSizeCm(Tile.Key.Z) * DecalPadding);
	Decal->SetFadeScreenSize(FadeScreenSize);
	Decal->SetSortOrder(SortOrder);
	Decal->SetDecalColor(DecalColor);
	Decal->SetWorldLocationAndRotation(MakeDecalLocation(Tile.CenterLocation, Tile.ProjectionNormal), MakeDecalRotation(Tile.ProjectionNormal));

	if (USceneComponent* RootComponent = Owner->GetRootComponent())
	{
		Decal->AttachToComponent(RootComponent, FAttachmentTransformRules::KeepWorldTransform);
	}

	Owner->AddInstanceComponent(Decal);
	Decal->RegisterComponentWithWorld(World);
	RegisterActiveDecal(Decal);
	return Decal;
}

void UProphecyFoliageDecalGridComponent::UpdateTileDecal(FProphecyFoliageDecalGridTile& Tile) const
{
	if (!Tile.Decal)
	{
		return;
	}

	Tile.Decal->DecalSize = FVector(ProjectionDepthCm, GetTileSizeCm(Tile.Key.Z) * DecalPadding, GetTileSizeCm(Tile.Key.Z) * DecalPadding);
	Tile.Decal->SetWorldLocationAndRotation(MakeDecalLocation(Tile.CenterLocation, Tile.ProjectionNormal), MakeDecalRotation(Tile.ProjectionNormal));
	Tile.Decal->SetDecalColor(DecalColor);
}

void UProphecyFoliageDecalGridComponent::DestroyTileDecal(FProphecyFoliageDecalGridTile& Tile)
{
	if (Tile.Decal)
	{
		UnregisterActiveDecal(Tile.Decal);
		Tile.Decal->DestroyComponent();
		Tile.Decal = nullptr;
	}
}

void UProphecyFoliageDecalGridComponent::RemoveOccupiedLeavesForTile(const FProphecyFoliageDecalGridTile& Tile)
{
	const int32 TileSizeCells = GetTileSizeCells(Tile.Key.Z);
	for (int32 OffsetY = 0; OffsetY < TileSizeCells; ++OffsetY)
	{
		for (int32 OffsetX = 0; OffsetX < TileSizeCells; ++OffsetX)
		{
			OccupiedLeafKeys.Remove(FIntPoint(Tile.Key.X + OffsetX, Tile.Key.Y + OffsetY));
		}
	}
}

void UProphecyFoliageDecalGridComponent::RegisterActiveDecal(UDecalComponent* Decal)
{
	if (!IsValid(Decal))
	{
		return;
	}

	ActiveDecalComponents.AddUnique(Decal);
	RefreshStats();
}

void UProphecyFoliageDecalGridComponent::UnregisterActiveDecal(UDecalComponent* Decal)
{
	if (!Decal)
	{
		return;
	}

	ActiveDecalComponents.Remove(Decal);
	RefreshStats();
}

void UProphecyFoliageDecalGridComponent::CompactActiveDecalList()
{
	ActiveDecalComponents.RemoveAll([](const TObjectPtr<UDecalComponent>& Decal)
	{
		return !IsValid(Decal);
	});
}

void UProphecyFoliageDecalGridComponent::PruneOldestTileIfNeeded()
{
	if (MaxActiveDecals <= 0 || ActiveTiles.Num() < MaxActiveDecals)
	{
		return;
	}

	FIntVector OldestKey(INDEX_NONE, INDEX_NONE, INDEX_NONE);
	float OldestTime = TNumericLimits<float>::Max();
	for (const TPair<FIntVector, FProphecyFoliageDecalGridTile>& TilePair : ActiveTiles)
	{
		if (TilePair.Value.LastTouchedTime < OldestTime)
		{
			OldestTime = TilePair.Value.LastTouchedTime;
			OldestKey = TilePair.Key;
		}
	}

	if (OldestKey.Z != INDEX_NONE)
	{
		if (FProphecyFoliageDecalGridTile* Tile = ActiveTiles.Find(OldestKey))
		{
			RemoveOccupiedLeavesForTile(*Tile);
			DestroyTileDecal(*Tile);
		}
		ActiveTiles.Remove(OldestKey);
		UntrackActiveTileKey(OldestKey);
		TotalPruned += 1;
	}
}

void UProphecyFoliageDecalGridComponent::RefreshStats()
{
	CompactActiveDecalList();
	ActiveDecalCount = ActiveTiles.Num();
	PendingMergeCount = MergeQueue.Num();
}

int32 UProphecyFoliageDecalGridBlueprintLibrary::AddFloorHitToFoliageDecalGrid(UProphecyFoliageDecalGridComponent* DecalGrid, const FHitResult& Hit, float RadiusCm)
{
	return DecalGrid ? DecalGrid->AddFloorHitToGrid(Hit, RadiusCm) : 0;
}

int32 UProphecyFoliageDecalGridBlueprintLibrary::AddFloorHitToFoliageDecalGridRef(UObject* DecalGridRef, const FHitResult& Hit, float RadiusCm)
{
	return AddFloorHitToFoliageDecalGridObject(DecalGridRef, Hit, RadiusCm);
}

void UProphecyFoliageDecalGridBlueprintLibrary::SetFoliageGridMergeProcessingEnabled(UProphecyFoliageDecalGridComponent* DecalGrid, bool bEnabled)
{
	if (DecalGrid)
	{
		DecalGrid->SetMergeProcessingEnabled(bEnabled);
	}
}

void UProphecyFoliageDecalGridBlueprintLibrary::SetFoliageGridMergeProcessingEnabledRef(UObject* DecalGridRef, bool bEnabled)
{
	SetFoliageGridMergeProcessingEnabledObject(DecalGridRef, bEnabled);
}

TArray<UDecalComponent*> UProphecyFoliageDecalGridBlueprintLibrary::GetActiveFoliageGridDecals(UProphecyFoliageDecalGridComponent* DecalGrid)
{
	return DecalGrid ? DecalGrid->GetActiveFoliageGridDecals() : TArray<UDecalComponent*>();
}

TArray<UDecalComponent*> UProphecyFoliageDecalGridBlueprintLibrary::GetActiveFoliageGridDecalsRef(UObject* DecalGridRef)
{
	return GetActiveFoliageGridDecalsObject(DecalGridRef);
}

void UProphecyFoliageDecalGridBlueprintLibrary::DrawFoliageGridDecalBounds(UProphecyFoliageDecalGridComponent* DecalGrid, float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels)
{
	if (DecalGrid)
	{
		DecalGrid->DrawActiveFoliageGridDecalBounds(DurationSeconds, LineThickness, BoundsHeightCm, LineColor, bColorByMergeLevel, bDrawLabels);
	}
}

void UProphecyFoliageDecalGridBlueprintLibrary::DrawFoliageGridDecalBoundsRef(UObject* DecalGridRef, float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels)
{
	DrawFoliageGridDecalBoundsObject(DecalGridRef, DurationSeconds, LineThickness, BoundsHeightCm, LineColor, bColorByMergeLevel, bDrawLabels);
}
