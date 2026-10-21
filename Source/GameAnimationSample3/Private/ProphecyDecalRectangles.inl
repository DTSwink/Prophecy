// Production adapter for BloodDecalLab's tested occupancy/rectangle pipeline.
// Included only by ProphecyFoliageDecalGridComponent.cpp.
#include "ProphecyDecalRectangleMesher.h"

struct FProphecyDecalRectState
{
	struct FSurface
	{
		TWeakObjectPtr<UPrimitiveComponent> Receiver;
		int32 Item = INDEX_NONE;
		FVector Normal, Origin, U, V;
	};
	struct FRegion
	{
		BloodRect::Mask Mask{};
		TArray<UDecalComponent*> Decals;
		bool bDirty = false;
	};
	TArray<FSurface> Surfaces;
	TMap<FIntVector, FRegion> Regions;
	TArray<FIntVector> Dirty;
	TArray<UDecalComponent*> Spare;
	std::vector<BloodRect::Rect> Scratch;
	int32 Head = 0;
	int32 BlockedAtCapacity = -1;
	float CellSize = 0;
	FVector2D Origin;
	int32 Side = 32;

	explicit FProphecyDecalRectState(const UProphecyFoliageDecalGridComponent& C)
		: CellSize(C.CellSizeCm), Origin(C.GridOrigin), Side(1 << FMath::Clamp(C.MaxMergeLevel, 0, 5))
	{
		Scratch.reserve(512);
	}
	static int32 FloorDiv(int32 V, int32 S) { return V >= 0 ? V / S : int32((int64(V) - S + 1) / S); }
	int32 Surface(UPrimitiveComponent* Receiver, int32 Item, const FVector& P, const FVector& N, int32 Cap)
	{
		for (int32 I = 0; I < Surfaces.Num(); ++I)
		{
			const FSurface& S = Surfaces[I];
			if (S.Receiver == Receiver && S.Item == Item && FVector::DotProduct(S.Normal, N) > .99999 &&
				FMath::Abs(FVector::DotProduct(P - S.Origin, S.Normal)) < .1)
				return I;
		}
		if (Surfaces.Num() >= Cap) return INDEX_NONE;
		FSurface S;
		S.Receiver = Receiver; S.Item = Item; S.Normal = N;
		const FVector Anchor(Origin.X, Origin.Y, 0);
		S.Origin = Anchor + N * FVector::DotProduct(P - Anchor, N);
		S.U = (FVector::ForwardVector - N * N.X).GetSafeNormal();
		if (S.U.IsNearlyZero()) S.U = (FVector::RightVector - N * N.Y).GetSafeNormal();
		S.V = FVector::CrossProduct(N, S.U);
		return Surfaces.Add(S);
	}
	bool Add(UProphecyFoliageDecalGridComponent& C, int32 SurfaceIndex, int32 X, int32 Y)
	{
		if (C.bLimitGridSize && (X < 0 || Y < 0 || X >= C.GridSizeCells.X || Y >= C.GridSizeCells.Y)) return false;
		const FIntVector Key(FloorDiv(X, Side), FloorDiv(Y, Side), SurfaceIndex);
		FRegion* R = Regions.Find(Key);
		if (!R)
		{
			// Bound occupancy independently of the number of rectangles it compresses to.
			if (Regions.Num() >= FMath::Max(1, C.MaxActiveDecals)) return false;
			R = &Regions.Add(Key);
		}
		const int32 LX = X - Key.X * Side, LY = Y - Key.Y * Side;
		const uint32 Bit = uint32(1) << LX;
		if (R->Mask[LY] & Bit) return false;
		R->Mask[LY] |= Bit;
		if (!R->bDirty) { R->bDirty = true; Dirty.Add(Key); }
		BlockedAtCapacity = -1;
		++C.TotalCellsSpawned;
		return true;
	}
	UDecalComponent* Create(UProphecyFoliageDecalGridComponent& C)
	{
		if (C.OwnedRectangleDecals.Num() >= FMath::Max(1, C.MaxActiveDecals)) return nullptr;
		UDecalComponent* D = NewObject<UDecalComponent>(C.GetOwner());
		D->SetMobility(EComponentMobility::Movable);
		D->SetDecalMaterial(C.DecalMaterial);
		D->SetFadeScreenSize(C.FadeScreenSize);
		D->SetSortOrder(C.SortOrder);
		D->SetDecalColor(C.DecalColor);
		D->SetVisibility(false);
		// World-anchored like the old floor grid; manager movement must not move stains.
		C.GetOwner()->AddInstanceComponent(D);
		D->RegisterComponentWithWorld(C.GetWorld());
		C.OwnedRectangleDecals.Add(D);
		return D;
	}
	void Place(UProphecyFoliageDecalGridComponent& C, UDecalComponent* D, const FIntVector& Key, const BloodRect::Rect& Q)
	{
		const FSurface& S = Surfaces[Key.Z];
		const float Depth = FMath::Max(1.f, C.ProjectionDepthCm);
		// Keep the receiver inside the full-opacity portion of UE's depth fade,
		// not barely inside the projector's far edge.
		const float Offset = FMath::Clamp(C.ProjectionSurfaceOffsetCm, 0.f, Depth * .25f);
		const FVector Location = S.Origin + S.U * ((Key.X * Side + Q.X + Q.W * .5) * CellSize) +
			S.V * ((Key.Y * Side + Q.Y + Q.H * .5) * CellSize) + S.Normal * Offset;
		// Decal local X projects into the receiver, Y follows V, Z follows U.
		const FQuat Rotation = FRotationMatrix::MakeFromXY(-S.Normal, S.V).ToQuat();
		const FVector Size(Depth * .5f, Q.H * CellSize * C.DecalPadding * .5f, Q.W * CellSize * C.DecalPadding * .5f);
		if (D->IsVisible() && D->DecalSize == Size && D->GetComponentLocation().Equals(Location) &&
			D->GetComponentQuat().Equals(Rotation)) return;
		D->DecalSize = Size;
		D->SetWorldLocationAndRotation(Location, Rotation);
		D->SetVisibility(true);
		D->MarkRenderStateDirty();
	}
	bool Rebuild(UProphecyFoliageDecalGridComponent& C, const FIntVector& Key, FRegion& R, double Deadline, int32& Created)
	{
		BloodRect::Mesh(R.Mask, Scratch);
		const int32 Need = int32(Scratch.size());
		if (C.ActiveDecalComponents.Num() - R.Decals.Num() + Need > C.MaxActiveDecals)
		{
			BlockedAtCapacity = C.MaxActiveDecals; return false;
		}
		const int32 Extra = FMath::Max(0, Need - R.Decals.Num());
		while (Spare.Num() < Extra)
		{
			if (Created >= 16 || (Created > 0 && FPlatformTime::Seconds() >= Deadline)) return false;
			UDecalComponent* D = Create(C);
			if (!D) { BlockedAtCapacity = C.MaxActiveDecals; return false; }
			Spare.Add(D); ++Created;
		}
		if (Created > 0 && FPlatformTime::Seconds() >= Deadline) return false;
		const int32 Previous = R.Decals.Num();
		while (R.Decals.Num() > Need)
		{
			UDecalComponent* D = R.Decals.Pop(EAllowShrinking::No);
			D->SetVisibility(false); Spare.Add(D);
			C.ActiveDecalComponents.RemoveSingleSwap(D, EAllowShrinking::No);
		}
		while (R.Decals.Num() < Need)
		{
			UDecalComponent* D = Spare.Pop(EAllowShrinking::No);
			R.Decals.Add(D); C.ActiveDecalComponents.Add(D);
		}
		for (int32 I = 0; I < Need; ++I) Place(C, R.Decals[I], Key, Scratch[I]);
		C.TotalMerges += FMath::Max(0, Previous - Need);
		return true;
	}
};

int32 UProphecyFoliageDecalGridComponent::AddRectangleStain(FVector P, FVector N, float Radius, UPrimitiveComponent* Receiver, int32 Item)
{
	if (!GetWorld() || !GetOwner() || !DecalMaterial || !FMath::IsFinite(CellSizeCm) || CellSizeCm < 1 ||
		!FMath::IsFinite(Radius) || Radius < 0 || P.ContainsNaN() || N.ContainsNaN() || MaxCellsPerHit <= 0) return 0;
	N = SafeNormalOrUp(N);
	if (bRequireFloorNormal && N.Z < FloorNormalMinZ) return 0;
	const int32 Side = 1 << FMath::Clamp(MaxMergeLevel, 0, 5);
	if (RectangleState && (RectangleState->CellSize != CellSizeCm || RectangleState->Origin != GridOrigin || RectangleState->Side != Side))
		ClearFoliageDecalGrid();
	if (!RectangleState) RectangleState = MakeShared<FProphecyDecalRectState>(*this);
	auto& State = *RectangleState;
	const int32 Surface = State.Surface(Receiver, Item, P, N, FMath::Max(1, MaxActiveDecals));
	if (Surface == INDEX_NONE) return 0;
	const auto& S = State.Surfaces[Surface];
	const FVector Delta = P - S.Origin;
	const FVector2D Local(FVector::DotProduct(Delta, S.U), FVector::DotProduct(Delta, S.V));
	// Avoid integer overflow on malformed world locations and bound candidate work.
	if (FMath::Abs(Local.X / CellSizeCm) > 1.e8 || FMath::Abs(Local.Y / CellSizeCm) > 1.e8) return 0;
	const int32 CX = FMath::FloorToInt(Local.X / CellSizeCm), CY = FMath::FloorToInt(Local.Y / CellSizeCm);
	const int32 Reach = Radius > 0 ? FMath::CeilToInt(FMath::Min(double(Radius / CellSizeCm + .5f),
		double(FMath::Clamp(MaxCellsPerHit, 1, 128)))) : 0;
	struct FCandidate { int32 X, Y; double Distance; };
	TArray<FCandidate> Candidates;
	const double Limit = FMath::Square(double(Radius) + CellSizeCm * .7072);
	for (int32 Y = CY - Reach; Y <= CY + Reach; ++Y) for (int32 X = CX - Reach; X <= CX + Reach; ++X)
	{
		if (bLimitGridSize && (X < 0 || Y < 0 || X >= GridSizeCells.X || Y >= GridSizeCells.Y)) continue;
		const double D = FMath::Square((X + .5) * CellSizeCm - Local.X) + FMath::Square((Y + .5) * CellSizeCm - Local.Y);
		if (Radius == 0 || D <= Limit) Candidates.Add({X, Y, D});
	}
	Candidates.Sort([](const FCandidate& A, const FCandidate& B) { return A.Distance < B.Distance; });
	int32 Accepted = 0;
	for (int32 I = 0; I < FMath::Min(Candidates.Num(), MaxCellsPerHit); ++I)
		Accepted += State.Add(*this, Surface, Candidates[I].X, Candidates[I].Y) ? 1 : 0;
	RefreshStats();
	if (Accepted) RefreshMergeTimer();
	return Accepted;
}

int32 UProphecyFoliageDecalGridComponent::AddFloorHitToGrid(const FHitResult& Hit, float RadiusCm)
{
	if (!Hit.bBlockingHit) return 0;
	return AddRectangleStain(Hit.ImpactPoint, Hit.ImpactNormal.IsNearlyZero() ? Hit.Normal : Hit.ImpactNormal,
		RadiusCm, Hit.GetComponent(), Hit.Item);
}

int32 UProphecyFoliageDecalGridComponent::AddFloorStainToGrid(FVector WorldLocation, FVector WorldNormal, float RadiusCm)
{
	return AddRectangleStain(WorldLocation, WorldNormal, RadiusCm, nullptr, INDEX_NONE);
}

void UProphecyFoliageDecalGridComponent::ProcessPendingMerges()
{
	if (!RectangleState) return;
	auto& S = *RectangleState;
	if (S.BlockedAtCapacity == MaxActiveDecals) { RefreshMergeTimer(); return; }
	S.BlockedAtCapacity = -1;
	const double Start = FPlatformTime::Seconds();
	const double Deadline = MergeBudgetMs > 0 ? Start + MergeBudgetMs * .001 : TNumericLimits<double>::Max();
	int32 Created = 0, Count = 0;
	const int32 Limit = FMath::Max(0, FMath::Min(MaxMergeChecksPerPass, MaxMergesPerPass));
	while (S.Head < S.Dirty.Num() && Count < Limit)
	{
		if (Count && FPlatformTime::Seconds() >= Deadline) break;
		const FIntVector Key = S.Dirty[S.Head];
		auto& R = S.Regions.FindChecked(Key);
		if (!S.Rebuild(*this, Key, R, Deadline, Created)) break;
		R.bDirty = false; ++S.Head; ++Count;
	}
	if (S.Head == S.Dirty.Num()) { S.Dirty.Reset(); S.Head = 0; }
	RefreshStats();
	RefreshMergeTimer();
}

void UProphecyFoliageDecalGridComponent::RefreshMergeTimer()
{
	UWorld* World = GetWorld();
	if (!World) return;
	const bool Work = RectangleState && RectangleState->Head < RectangleState->Dirty.Num() &&
		RectangleState->BlockedAtCapacity != MaxActiveDecals && MaxMergesPerPass > 0 && MaxMergeChecksPerPass > 0;
	if (!bAutoProcessMerges || !Work)
	{
		World->GetTimerManager().ClearTimer(MergeTimerHandle); return;
	}
	// Do not reset an active timer on every hit: a continuous spray would starve it.
	if (!World->GetTimerManager().IsTimerActive(MergeTimerHandle))
		World->GetTimerManager().SetTimer(MergeTimerHandle, this,
			&UProphecyFoliageDecalGridComponent::ProcessPendingMerges,
			FMath::Max(.01f, MergeProcessIntervalSeconds), true);
}

void UProphecyFoliageDecalGridComponent::SetMergeProcessingEnabled(bool bEnabled) { bAutoProcessMerges = bEnabled; RefreshMergeTimer(); }
void UProphecyFoliageDecalGridComponent::StartMergeProcessing() { SetMergeProcessingEnabled(true); }
void UProphecyFoliageDecalGridComponent::StopMergeProcessing() { SetMergeProcessingEnabled(false); }
bool UProphecyFoliageDecalGridComponent::IsMergeProcessingEnabled() const { return bAutoProcessMerges; }

void UProphecyFoliageDecalGridComponent::ClearFoliageDecalGrid()
{
	if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(MergeTimerHandle);
	for (UDecalComponent* D : OwnedRectangleDecals)
		if (IsValid(D)) { if (GetOwner()) GetOwner()->RemoveInstanceComponent(D); D->DestroyComponent(); }
	OwnedRectangleDecals.Reset(); ActiveDecalComponents.Reset(); RectangleState.Reset();
	RefreshStats();
}
void UProphecyFoliageDecalGridComponent::RefreshStats()
{
	ActiveDecalCount = ActiveDecalComponents.Num();
	PendingMergeCount = RectangleState ? RectangleState->Dirty.Num() - RectangleState->Head : 0;
}
FString UProphecyFoliageDecalGridComponent::GetFoliageDecalGridStatsString() const
{
	return FString::Printf(TEXT("FoliageDecalGrid rectangles=%d dirtyRegions=%d acceptedCells=%d reduced=%d pooled=%d capacityBlocked=%s"),
		ActiveDecalCount, PendingMergeCount, TotalCellsSpawned, TotalMerges,
		RectangleState ? RectangleState->Spare.Num() : 0,
		RectangleState && RectangleState->BlockedAtCapacity >= 0 ? TEXT("true") : TEXT("false"));
}
TArray<UDecalComponent*> UProphecyFoliageDecalGridComponent::GetActiveFoliageGridDecals() const
{
	TArray<UDecalComponent*> Result;
	Result.Reserve(ActiveDecalComponents.Num());
	for (UDecalComponent* D : ActiveDecalComponents) if (IsValid(D)) Result.Add(D);
	return Result;
}
void UProphecyFoliageDecalGridComponent::DrawActiveFoliageGridDecalBounds(float DurationSeconds, float LineThickness,
	float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels) const
{
	if (!GetWorld()) return;
	for (UDecalComponent* D : ActiveDecalComponents)
	{
		if (!IsValid(D)) continue;
		FVector Extent = D->DecalSize, Center = D->GetComponentLocation();
		const FVector Normal = -D->GetForwardVector();
		if (BoundsHeightCm > 0)
		{
			Center += Normal * (-FMath::Clamp(ProjectionSurfaceOffsetCm, 0.f, D->DecalSize.X * .5f) + BoundsHeightCm * .5f);
			Extent.X = BoundsHeightCm * .5f;
		}
		const FColor Color = bColorByMergeLevel ? (FMath::IsNearlyEqual(Extent.Y, Extent.Z) ? FColor::Green : FColor::Cyan) : LineColor.ToFColor(true);
		DrawDebugBox(GetWorld(), Center, Extent, D->GetComponentQuat(), Color, false,
			FMath::Max(0.f, DurationSeconds), 0, FMath::Max(0.f, LineThickness));
		if (bDrawLabels)
			DrawDebugString(GetWorld(), Center + Normal * 8,
				FString::Printf(TEXT("%.0f x %.0fcm"), D->DecalSize.Z * 2, D->DecalSize.Y * 2),
				nullptr, Color, FMath::Max(0.f, DurationSeconds), false, 1.f);
	}
}
