#include "BumblebeeSwarm.h"
#include "BumblebeeZone.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkinnedMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"
#include "Components/BoxComponent.h"
#include "Algo/Sort.h"

DEFINE_LOG_CATEGORY_STATIC(LogBumblebees, Log, All);

static TAutoConsoleVariable<int32> CVarBeeEnable(TEXT("bumblebees.Enable"), 1, TEXT("0 = pause the bumblebee simulation (rendering stays)."));
static TAutoConsoleVariable<int32> CVarBeeDebug(TEXT("bumblebees.Debug"), 0, TEXT("1 = draw paths/states of near bees."));
static TAutoConsoleVariable<float> CVarBeeLogStats(TEXT("bumblebees.LogStats"), 0.f, TEXT("Log swarm stats every N seconds (0 = off)."));
static TAutoConsoleVariable<int32> CVarBeeProfile(TEXT("bumblebees.Profile"), 0, TEXT("1 = time each part of the swarm update (logged with bumblebees.LogStats)."));
static TAutoConsoleVariable<int32> CVarBeeRender(TEXT("bumblebees.Render"), 1, TEXT("0 = hide all bees (cost A/B: GPU + render thread)."));
static TAutoConsoleVariable<int32> CVarBeeShadows(TEXT("bumblebees.Shadows"), 1, TEXT("0 = near bees cast no shadows."));
static TAutoConsoleVariable<int32> CVarBeeWPO(TEXT("bumblebees.WPO"), 1, TEXT("0 = no wing/leg animation (World Position Offset off)."));

namespace BeeConst
{
	static constexpr float BodyHeight = 0.85f;		// body centre above the surface when landed (cm)
	static constexpr float TakeoffHeight = 10.f;		// first point straight off the surface
	static constexpr float ApproachHeight = 8.f;	// last waypoint in front of the landing spot (approach along the normal)
	static constexpr float Accel = 450.f;
	static constexpr float Decel = 900.f;
	static constexpr float ProbeStep = 0.8f;		// walking: checked segment length (cm, x bee scale)
	static const FTransform Parked(FQuat::Identity, FVector(0.0, 0.0, -1.0e7));
	static constexpr int32 NumLods = 4;
}

// =====================================================================================================================
ABumblebeeSwarm::ABumblebeeSwarm()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	FlyMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Prophecy/Creatures/Bumblebee/SM_Bumblebee_Fly.SM_Bumblebee_Fly")));
	LandedMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/Prophecy/Creatures/Bumblebee/SM_Bumblebee_Landed.SM_Bumblebee_Landed")));
#if WITH_EDITOR
	SetIsSpatiallyLoaded(false);
#endif
}

ABumblebeeSwarm* ABumblebeeSwarm::Find(const UObject* WorldContext)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World) return nullptr;
	for (TActorIterator<ABumblebeeSwarm> It(World); It; ++It)
	{
		if (IsValid(*It)) return *It;
	}
	return nullptr;
}

ABumblebeeSwarm* ABumblebeeSwarm::GetOrCreate(const UObject* WorldContext)
{
	if (ABumblebeeSwarm* S = Find(WorldContext)) return S;
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World || !World->IsGameWorld()) return nullptr;
	FActorSpawnParameters P;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	P.Name = TEXT("BumblebeeSwarm");
	P.NameMode = FActorSpawnParameters::ESpawnActorNameMode::Requested;
	return World->SpawnActor<ABumblebeeSwarm>(FVector::ZeroVector, FRotator::ZeroRotator, P);
}

void ABumblebeeSwarm::BeginPlay()
{
	Super::BeginPlay();
	Rng.Initialize(0xB33B);
	SetActorTransform(FTransform::Identity);
	EnsureComponents();
	for (AActor* A : ThreatActors) AddThreatActor(A);
	if (!ThreatTag.IsNone())
	{
		for (TActorIterator<AActor> It(GetWorld()); It; ++It)
		{
			if (It->ActorHasTag(ThreatTag)) AddThreatActor(*It);
		}
	}
	for (TActorIterator<ABumblebeeZone> It(GetWorld()); It; ++It)
	{
		if (It->HasActorBegunPlay()) RegisterZone(*It);
	}
}

void ABumblebeeSwarm::EndPlay(const EEndPlayReason::Type Reason)
{
	Bees.Reset();
	Zones.Reset();
	Super::EndPlay(Reason);
}

void ABumblebeeSwarm::EnsureComponents()
{
	if (Instances.Num() == 2 * BeeConst::NumLods) return;
	UStaticMesh* Meshes[2] = { FlyMesh.LoadSynchronous(), LandedMesh.LoadSynchronous() };
	bAssetsReady = Meshes[0] && Meshes[1];
	if (!bAssetsReady)
	{
		UE_LOG(LogBumblebees, Error, TEXT("Bumblebee meshes missing (%s / %s). Run Exports/Bumblebee/setup_bumblebee.py."),
			*FlyMesh.ToString(), *LandedMesh.ToString());
	}
	for (int32 Pose = 0; Pose < 2; ++Pose)
	{
		for (int32 Lod = 0; Lod < BeeConst::NumLods; ++Lod)
		{
			const FName Name(*FString::Printf(TEXT("%s_LOD%d"), Pose == 0 ? TEXT("Fly") : TEXT("Landed"), Lod));
			UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(this, Name);
			C->SetupAttachment(RootComponent);
			C->SetUsingAbsoluteLocation(true);
			C->SetUsingAbsoluteRotation(true);
			C->SetUsingAbsoluteScale(true);
			C->SetMobility(EComponentMobility::Movable);
			C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			C->SetCollisionResponseToAllChannels(ECR_Ignore);
			C->SetGenerateOverlapEvents(false);
			C->SetCanEverAffectNavigation(false);
			C->SetNumCustomDataFloats(4);	// 0 flap, 1 leg cycles walked, 2 stride x walk amount, 3 wing Hz
			C->SetForcedLodModel(Lod + 1);
			C->SetCullDistances(0, FMath::RoundToInt(VisibleDistance));
			C->SetCastShadow(bCastShadowsNear && Lod <= 1);
			C->bCastDynamicShadow = bCastShadowsNear && Lod <= 1;
			C->bAffectDistanceFieldLighting = false;
			C->bAffectDynamicIndirectLighting = false;
			C->bVisibleInRayTracing = false;
			C->bUseAsOccluder = false;
			C->bReceivesDecals = false;
			C->bEvaluateWorldPositionOffset = Lod < 3;
			C->SetStaticMesh(Meshes[Pose]);
			C->RegisterComponent();
			C->SetWorldTransform(FTransform::Identity);
			AddInstanceComponent(C);
			Instances.Add(C);
		}
	}
}

// =====================================================================================================================
void ABumblebeeSwarm::RegisterZone(ABumblebeeZone* Zone)
{
	if (!Zone) return;
	for (const FZoneEntry& E : Zones)
	{
		if (E.Zone.Get() == Zone) return;
	}
	EnsureComponents();
	FZoneEntry& E = Zones.AddDefaulted_GetRef();
	E.Zone = Zone;
	E.FirstBee = Bees.Num();
	E.Count = FMath::Max(0, Zone->BeeCount);
	AllocateZoneBees(E);
}

void ABumblebeeSwarm::UnregisterZone(ABumblebeeZone* Zone)
{
	for (FZoneEntry& E : Zones)
	{
		if (E.Zone.Get() == Zone) E.Zone = nullptr;		// bees persist, preference is dropped
	}
}

void ABumblebeeSwarm::AllocateZoneBees(FZoneEntry& Entry)
{
	const int32 ZoneIndex = Zones.Num() - 1;
	const int32 Start = Bees.Num();
	const ABumblebeeZone* Zone = Entry.Zone.Get();
	Bees.AddDefaulted(Entry.Count);
	TArray<FTransform> Parked;
	Parked.Init(BeeConst::Parked, Entry.Count);
	for (int32 i = Start; i < Bees.Num(); ++i)
	{
		Bees[i].Zone = (int16)ZoneIndex;
		Bees[i].WobbleSeed = Rng.FRand() * 100.f;
		// bumblebee workers vary a lot in size; queens are the large ones
		Bees[i].SizeVariation = Rng.FRand() < 0.06f ? Rng.FRandRange(1.2f, 1.35f) : Rng.FRandRange(SizeVariation.X, SizeVariation.Y);
		RefreshBeeScale(Bees[i]);
		// bigger bees beat their wings a little slower; walking speed varies per individual
		Bees[i].WingHz = (Zone ? Zone->WingBeatHz : 150.f) * Rng.FRandRange(0.94f, 1.06f) / FMath::Sqrt(Bees[i].SizeVariation);
		Bees[i].WalkBase = (Zone ? Zone->WalkSpeed : 2.5f) * Rng.FRandRange(WalkSpeedVariation.X, WalkSpeedVariation.Y);
	}
	for (int32 c = 0; c < Instances.Num(); ++c)
	{
		UInstancedStaticMeshComponent* C = Instances[c];
		C->AddInstances(Parked, false, false, false);
		const float Flap = c < BeeConst::NumLods ? 1.f : 0.f;
		for (int32 i = Start; i < Bees.Num(); ++i)
		{
			C->SetCustomDataValue(i, 0, Flap, false);
			C->SetCustomDataValue(i, 3, Bees[i].WingHz, false);
		}
	}
}

const ABumblebeeZone* ABumblebeeSwarm::ZoneOf(const FBumblebee& B) const
{
	return Zones.IsValidIndex(B.Zone) ? Zones[B.Zone].Zone.Get() : nullptr;
}

bool ABumblebeeSwarm::TryPlaceBee(int32 Index, const ABumblebeeZone* Zone)
{
	FBumblebee& B = Bees[Index];
	const FVector Top = Zone->RandomPoint(Rng, 0.75f);
	const float Depth = Zone->Box->GetScaledBoxExtent().Z * 2.f + 600.f;
	FHitResult H;
	if (!Line(Top, Top - FVector::UpVector * Depth, H) || !IsLandable(H) || !Zone->IsInside(H.ImpactPoint, 150.f))
	{
		return false;
	}
	if (Zone->bAvoidIndoors && IsEnclosed(H.ImpactPoint + H.ImpactNormal * 20.f, true))
	{
		return false;
	}
	B.Pos = H.ImpactPoint;
	B.Up = H.ImpactNormal;
	const FVector R = FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.f);
	B.Fwd = FVector::VectorPlaneProject(R.IsNearlyZero() ? FVector::ForwardVector : R, B.Up).GetSafeNormal();
	if (B.Fwd.IsNearlyZero()) B.Fwd = B.Up.ToOrientationQuat().GetAxisY();
	B.Rot = FRotationMatrix::MakeFromZX(B.Up, B.Fwd).ToQuat();
	B.State = EBeeState::Landed;
	StartLandedBehaviour(B, false);
	B.bRenderDirty = true;
	return true;
}

int32 ABumblebeeSwarm::RelocateBeesTo(FVector Location, float Radius, int32 Count, bool bWalkers)
{
	int32 Moved = 0;
	for (int32 i = 0; i < Bees.Num() && Moved < Count; ++i)
	{
		FBumblebee& B = Bees[i];
		if (B.State != EBeeState::Landed) continue;
		for (int32 Try = 0; Try < 6; ++Try)
		{
			const FVector P = Location + FVector(Rng.FRandRange(-Radius, Radius), Rng.FRandRange(-Radius, Radius), 50.f);
			FHitResult H;
			FCollisionQueryParams Q(SCENE_QUERY_STAT(BumblebeeRelocate), bTraceComplex, this);
			if (GetWorld()->LineTraceSingleByChannel(H, P, P - FVector(0, 0, 400), TraceChannel, Q) && IsLandable(H))
			{
				B.Pos = H.ImpactPoint;
				B.Up = H.ImpactNormal;
				B.Fwd = FVector::VectorPlaneProject(FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.01f), B.Up).GetSafeNormal();
				B.Rot = FRotationMatrix::MakeFromZX(B.Up, B.Fwd).ToQuat();
				B.bEscaping = false;
				B.IndoorCheckAge = 1e9f;
				StartLandedBehaviour(B, false);
				B.LandedTimeLeft = bWalkers ? Rng.FRandRange(10.f, 16.f) : Rng.FRandRange(2.f, 8.f);
				if (bWalkers) { B.bWalker = true; B.BoutTimeLeft = 0.05f; }
				B.bRenderDirty = true;
				++Moved;
				break;
			}
		}
	}
	return Moved;
}

// =====================================================================================================================
void ABumblebeeSwarm::AddThreatActor(AActor* Actor)
{
	if (!Actor) return;
	for (const FThreat& T : Threats)
	{
		if (T.Actor.Get() == Actor) return;
	}
	FThreat& T = Threats.AddDefaulted_GetRef();
	T.Actor = Actor;
	ThreatActors.AddUnique(Actor);
}

void ABumblebeeSwarm::RemoveThreatActor(AActor* Actor)
{
	Threats.RemoveAll([Actor](const FThreat& T) { return T.Actor.Get() == Actor; });
	ThreatActors.Remove(Actor);
}

void ABumblebeeSwarm::GatherViewersAndThreats(float Dt)
{
	Viewers.Reset();
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		APlayerController* PC = It->Get();
		if (!PC) continue;
		if (PC->PlayerCameraManager) Viewers.Add(PC->PlayerCameraManager->GetCameraLocation());
		if (bPlayerPawnsAreThreats && PC->GetPawn()) AddThreatActor(PC->GetPawn());
	}
	for (int32 i = Threats.Num() - 1; i >= 0; --i)
	{
		FThreat& T = Threats[i];
		AActor* A = T.Actor.Get();
		if (!IsValid(A))
		{
			Threats.RemoveAtSwap(i);
			continue;
		}
		const FVector P = A->GetActorLocation();
		const float Moved = T.bValid && Dt > 0.f ? float(FVector::Dist(P, T.LastPos)) / Dt : 0.f;
		T.Speed = FMath::Max(Moved, float(A->GetVelocity().Size()));
		T.LastPos = P;
		T.Pos = P;
		T.bValid = true;
	}
}

float ABumblebeeSwarm::NearestViewerDistSq(const FVector& P) const
{
	float Best = TNumericLimits<float>::Max();
	for (const FVector& V : Viewers) Best = FMath::Min(Best, float(FVector::DistSquared(P, V)));
	return Best;
}

void ABumblebeeSwarm::UpdateTier(FBumblebee& B) const
{
	const float D2 = NearestViewerDistSq(B.Pos);
	B.ViewDist = FMath::Sqrt(D2);
	B.Tier = D2 < FMath::Square(NearDistance) ? 0 : (D2 < FMath::Square(VisibleDistance) ? 1 : 2);
}

// =====================================================================================================================
bool ABumblebeeSwarm::HasBudget(int32 Needed, bool bUrgent) const
{
	return TracesThisFrame + Needed <= MaxTracesPerFrame + (bUrgent ? 24 : 0);
}

bool ABumblebeeSwarm::Line(const FVector& A, const FVector& B, FHitResult& Hit)
{
	++TracesThisFrame;
	++TracesWindow;
	const uint64 C0 = bProfile ? FPlatformTime::Cycles64() : 0;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BumblebeeLine), bTraceComplex, this);
	Q.bReturnPhysicalMaterial = false;
	const bool bHit = GetWorld()->LineTraceSingleByChannel(Hit, A, B, TraceChannel, Q);
	if (bProfile) ProfSec[TraceCtx] += FPlatformTime::ToSeconds64(FPlatformTime::Cycles64() - C0);
	if (bDrawDebug || CVarBeeDebug.GetValueOnGameThread() > 1)
	{
		DrawDebugLine(GetWorld(), A, bHit ? FVector(Hit.ImpactPoint) : B, bHit ? FColor::Red : FColor::Green, false, 0.5f);
	}
	return bHit;
}

bool ABumblebeeSwarm::Sweep(const FVector& A, const FVector& B, float Radius, FHitResult& Hit)
{
	++TracesThisFrame;
	++TracesWindow;
	const uint64 C0 = bProfile ? FPlatformTime::Cycles64() : 0;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BumblebeeSweep), false, this);
	Q.bReturnPhysicalMaterial = false;
	bool bHit = GetWorld()->SweepSingleByChannel(Hit, A, B, FQuat::Identity, TraceChannel, FCollisionShape::MakeSphere(Radius), Q);
	if (bHit && Hit.bStartPenetrating)
	{
		// starting close to a surface (take-off next to a wall): retry with a body-sized sphere
		++TracesThisFrame;
		++TracesWindow;
		bHit = GetWorld()->SweepSingleByChannel(Hit, A, B, FQuat::Identity, TraceChannel, FCollisionShape::MakeSphere(Radius * 0.35f), Q);
	}
	if (bProfile) ProfSec[TraceCtx] += FPlatformTime::ToSeconds64(FPlatformTime::Cycles64() - C0);
	return bHit;
}

bool ABumblebeeSwarm::IsLandable(const FHitResult& Hit) const
{
	if (!Hit.bBlockingHit || Hit.ImpactNormal.Z < MinLandingNormalZ) return false;
	const UPrimitiveComponent* C = Hit.GetComponent();
	if (!C) return false;
	if (!bLandOnMovableComponents && C->Mobility == EComponentMobility::Movable) return false;
	if (C->IsA<USkinnedMeshComponent>()) return false;
	const AActor* A = Hit.GetActor();
	if (A && (A->IsA<APawn>() || A == this)) return false;
	return true;
}

bool ABumblebeeSwarm::HasOpenSky(const FVector& P)
{
	FHitResult H;
	return !Line(P, P + FVector::UpVector * 2000.f, H);
}

bool ABumblebeeSwarm::IsEnclosed(const FVector& P, bool bUrgent)
{
	if (!HasBudget(5, bUrgent)) return false;
	FHitResult H;
	if (!Line(P, P + FVector::UpVector * 1500.f, H)) return false;		// open sky
	int32 Walls = 0;
	const float A0 = Rng.FRand() * PI;
	for (int32 k = 0; k < 4; ++k)
	{
		const float A = A0 + k * HALF_PI;
		const FVector D(FMath::Cos(A), FMath::Sin(A), 0.f);
		if (Line(P, P + D * 1000.f, H)) ++Walls;
	}
	return Walls >= 3;
}

// =====================================================================================================================
float ABumblebeeSwarm::HeavyTailPause()
{
	// insects idle with heavy-tailed (power-law) pause durations: mostly short stops, occasionally long ones
	const float U = FMath::Max(Rng.FRand(), 0.02f);
	return FMath::Min(PauseScale * FMath::Pow(U, -1.f / 1.5f), 6.f);
}

void ABumblebeeSwarm::StartLandedBehaviour(FBumblebee& B, bool bFresh)
{
	const ABumblebeeZone* Z = ZoneOf(B);
	const float Air = Z ? Z->AirTime : 0.5f;
	const float U = Rng.FRand();
	B.LandedTimeLeft = FMath::Lerp(LandedTimeRange.X, LandedTimeRange.Y, U * U) * FMath::Lerp(1.6f, 0.35f, Air);
	if (!bFresh) B.LandedTimeLeft *= Rng.FRand();		// stagger initial take-offs
	B.bWalker = Rng.FRand() < WalkerFraction;
	B.bWalking = false;
	B.BoutTimeLeft = Rng.FRandRange(0.15f, 0.6f);		// settle briefly after touchdown, then walk
	B.TurnRate = 0.f;
	B.WalkAmount = 0.f;
	B.WalkSegRemain = 0.f;
	B.bThreatened = false;
	B.bWantsPlan = false;
	B.PlanCooldown = 0.f;
	B.ValidateTimer = Rng.FRandRange(2.f, 5.f);
	B.Vel = FVector::ZeroVector;
	B.Speed = 0.f;
	B.FlightPhase = 0;
}

void ABumblebeeSwarm::CheckThreat(FBumblebee& B)
{
	if (B.bThreatened || B.ThreatCooldown > 0.f) return;
	for (const FThreat& T : Threats)
	{
		if (!T.bValid) continue;
		const float D2 = float(FVector::DistSquared(T.Pos, B.Pos));
		if (D2 < FMath::Square(ThreatPanicRadius) || (D2 < FMath::Square(ThreatRadius) && T.Speed > ThreatMinSpeed))
		{
			B.bThreatened = true;
			B.bWantsPlan = true;
			B.ThreatPos = T.Pos;
			return;
		}
	}
}

void ABumblebeeSwarm::TickLanded(int32 Index, FBumblebee& B, float Dt)
{
	TraceCtx = P_TraceWalk;
	B.LandedTimeLeft -= Dt;
	B.PlanCooldown -= Dt;
	B.ThreatCooldown -= Dt;
	if (B.LandedTimeLeft <= 0.f && B.PlanCooldown <= 0.f) B.bWantsPlan = true;

	// near, resting bees occasionally confirm their surface still exists (destroyed props, opened doors...)
	if (B.Tier == 0)
	{
		B.ValidateTimer -= Dt;
		if (B.ValidateTimer <= 0.f && HasBudget(1, false))
		{
			B.ValidateTimer = Rng.FRandRange(3.f, 6.f);
			FHitResult H;
			if (!Line(B.Pos + B.Up * B.Scale, B.Pos - B.Up * 1.5f * B.Scale, H))
			{
				B.LandedTimeLeft = 0.f;
				B.PlanCooldown = 0.f;
				B.bWantsPlan = true;
			}
		}
	}

	B.BoutTimeLeft -= Dt;
	if (B.BoutTimeLeft <= 0.f)
	{
		if (B.bWalking)
		{
			B.bWalking = false;
			B.BoutTimeLeft = HeavyTailPause();
		}
		else if (B.bWalker && B.Tier == 0 && B.ViewDist < WalkDistance)
		{
			B.bWalking = true;
			B.BoutTimeLeft = FMath::Clamp(-WalkBoutMean * FMath::Loge(FMath::Max(Rng.FRand(), 0.01f)), 0.6f, 4.f * WalkBoutMean);
			B.WalkSpeed = B.WalkBase * Rng.FRandRange(0.85f, 1.15f);
			// insects lengthen their stride as they walk faster (and step faster): stride in model cm
			const float VModel = B.WalkSpeed / FMath::Max(B.Scale, 0.05f);
			B.StrideModel = FMath::Clamp(0.45f + 0.1f * VModel, 0.45f, 1.1f);
			B.Fwd = FQuat(B.Up, FMath::DegreesToRadians(Rng.FRandRange(-60.f, 60.f))).RotateVector(B.Fwd);
		}
		else
		{
			B.BoutTimeLeft = HeavyTailPause();
		}
	}

	bool bMoved = false;
	float Moved = 0.f;
	if (B.bWalking && B.Tier == 0 && B.ViewDist < WalkDistance * 1.2f)
	{
		// desired heading: correlated random walk (Ornstein-Uhlenbeck turning rate), steered back into the zone, climbing on walls
		B.TurnRate += (-B.TurnRate / 0.6f) * Dt + Rng.FRandRange(-1.f, 1.f) * 2.8f * FMath::Sqrt(Dt);
		FVector F = FQuat(B.Up, B.TurnRate * Dt).RotateVector(B.Fwd);
		if (const ABumblebeeZone* Z = ZoneOf(B))
		{
			if (!Z->IsInside(B.Pos, 50.f))
			{
				const FVector To = FVector::VectorPlaneProject(Z->GetCenter() - B.Pos, B.Up).GetSafeNormal();
				F = (F + To * 2.f * Dt).GetSafeNormal();
			}
		}
		if (B.Up.Z < 0.75f)
		{
			const FVector Upslope = FVector::VectorPlaneProject(FVector::UpVector, B.Up).GetSafeNormal();
			F = (F + Upslope * 0.9f * Dt).GetSafeNormal();
		}
		B.Fwd = FVector::VectorPlaneProject(F, B.Up).GetSafeNormal();
		if (B.Fwd.IsNearlyZero()) B.Fwd = B.Up.ToOrientationQuat().GetAxisY();

		// next segment: check the path (head height) and the foothold at its end BEFORE walking it
		if (B.WalkSegRemain <= KINDA_SMALL_NUMBER && WalkTracesThisFrame + 2 <= MaxWalkTracesPerFrame && HasBudget(2, false))
		{
			WalkTracesThisFrame += 2;
			const float Seg = BeeConst::ProbeStep * B.Scale;
			FHitResult H;
			const FVector Eye = B.Pos + B.Up * 0.55f * B.Scale;
			if (Line(Eye, Eye + B.Fwd * (Seg + 0.6f * B.Scale), H))
			{
				// obstacle ahead (raised flower centre, wall, stem): turn away, short hesitation, keep walking
				B.Fwd = FQuat(B.Up, FMath::DegreesToRadians(Rng.FRandRange(110.f, 250.f))).RotateVector(B.Fwd);
				B.bWalking = false;
				B.BoutTimeLeft = Rng.FRandRange(0.1f, 0.45f);
			}
			else
			{
				// foothold: same surface only (small rise/drop), no stepping off a rim onto something below
				const FVector Ahead = B.Pos + B.Fwd * Seg;
				const bool bHit = Line(Ahead + B.Up * 0.5f * B.Scale, Ahead - B.Up * 0.5f * B.Scale, H);
				const float Rise = bHit ? float(FVector::DotProduct(FVector(H.ImpactPoint) - B.Pos, B.Up)) : 0.f;
				if (bHit && IsLandable(H) && FVector::DotProduct(FVector(H.ImpactNormal), B.Up) > 0.6f && FMath::Abs(Rise) <= 0.3f * B.Scale)
				{
					B.WalkStart = B.Pos;
					B.WalkStartUp = B.Up;
					B.WalkTarget = H.ImpactPoint;
					B.WalkTargetN = H.ImpactNormal;
					B.WalkSegLen = float(FVector::Dist(B.WalkStart, B.WalkTarget));
					B.WalkSegRemain = B.WalkSegLen;
				}
				else
				{
					// edge / gap / step: don't leave the surface, turn around
					B.Fwd = FQuat(B.Up, FMath::DegreesToRadians(Rng.FRandRange(140.f, 220.f))).RotateVector(B.Fwd);
					B.bWalking = false;
					B.BoutTimeLeft = Rng.FRandRange(0.1f, 0.45f);
				}
			}
		}
		// glide along the checked segment: feet stay on the surface, body tilt blends between the two normals
		if (B.bWalking && B.WalkSegRemain > KINDA_SMALL_NUMBER)
		{
			const float Step = FMath::Min(B.WalkSpeed * Dt, B.WalkSegRemain);
			B.WalkSegRemain -= Step;
			const float A = B.WalkSegLen > KINDA_SMALL_NUMBER ? 1.f - B.WalkSegRemain / B.WalkSegLen : 1.f;
			B.Pos = FMath::Lerp(B.WalkStart, B.WalkTarget, A);
			B.Up = FMath::Lerp(B.WalkStartUp, B.WalkTargetN, A).GetSafeNormal();
			Moved = Step;
			bMoved = true;
		}
		// legs: one cycle per stride actually travelled, so the feet stay planted at any speed or frame rate
		if (bMoved) B.WalkPhase += Moved / (B.StrideModel * B.Scale);
	}
	else if (B.bWalking)
	{
		B.bWalking = false;		// too far to see walking: just rest
	}

	// a walker briefly waiting for its probe holds its legs mid-step (phase only advances with distance)
	const float TargetAmount = B.bWalking ? 1.f : 0.f;
	const float NewAmount = FMath::FInterpTo(B.WalkAmount, TargetAmount, Dt, 12.f);
	if (bMoved || B.bSettling || !FMath::IsNearlyEqual(NewAmount, B.WalkAmount, 0.001f))
	{
		B.WalkAmount = NewAmount;
		const FQuat Target = FRotationMatrix::MakeFromZX(B.Up, B.Fwd).ToQuat();
		B.Rot = FQuat::Slerp(B.Rot, Target, 1.f - FMath::Exp(-12.f * Dt));
		if (B.bSettling && B.Rot.AngularDistance(Target) < 0.01f) B.bSettling = false;
		B.bRenderDirty = true;
	}
}

// =====================================================================================================================
// Flight paths: validated polylines whose corners are replaced by circular arcs (fillets). Arcs have constant speed along
// their length, exact length and constant curvature, so speed and heading change smoothly. An arc whose apex stays within
// 30% of the clearance (tangent length D <= Dev / tan(phi/4)) lies inside space the leg sweeps already validated; wider
// arcs are swept along their own length first.
namespace
{
	struct FArc
	{
		FVector P0 = FVector::ZeroVector, O = FVector::ZeroVector, Din = FVector::ForwardVector, N0 = FVector::RightVector;
		float Rarc = 0.f, Phi = 0.f, Len = 0.f;
		bool bValid = false;
	};
	FORCEINLINE float TurnAngle(const FVector& Din, const FVector& Dout)
	{
		return FMath::Acos(FMath::Clamp(float(FVector::DotProduct(Din, Dout)), -1.f, 1.f));
	}
	FArc MakeArc(const FVector& Din, const FVector& Dout, const FVector& C, float D)
	{
		FArc A;
		A.Din = Din;
		A.Phi = TurnAngle(Din, Dout);
		if (D <= 0.f || A.Phi < 1e-3f) return A;
		FVector N0 = Dout - Din * FMath::Cos(A.Phi);
		if (N0.SizeSquared() < 1e-8f)
		{
			N0 = FVector::CrossProduct(Din, FVector::UpVector);
			if (N0.IsNearlyZero()) N0 = FVector::CrossProduct(Din, FVector::ForwardVector);
		}
		A.N0 = N0.GetSafeNormal();
		A.Rarc = D / FMath::Tan(FMath::Min(A.Phi, PI - 1e-3f) * 0.5f);
		A.Len = A.Rarc * A.Phi;
		A.P0 = C - Din * D;
		A.O = A.P0 + A.N0 * A.Rarc;
		A.bValid = true;
		return A;
	}
	FORCEINLINE FVector ArcPoint(const FArc& A, float S, FVector* OutDir)
	{
		const float Al = A.Rarc > KINDA_SMALL_NUMBER ? FMath::Clamp(S / A.Rarc, 0.f, A.Phi) : A.Phi;
		const float Co = FMath::Cos(Al), Si = FMath::Sin(Al);
		if (OutDir) *OutDir = A.Din * Co + A.N0 * Si;
		return A.O + (A.Din * Si - A.N0 * Co) * A.Rarc;
	}
	// length of the corner piece that replaces 2*D of polyline (arc, or straight-through when not turning)
	FORCEINLINE float CornerPieceLen(const FArc& A, float D) { return A.bValid ? A.Len : 2.f * D; }
}

FVector ABumblebeeSwarm::PathPoint(const FBumblebee& B, float S, FVector* OutDir)
{
	const int32 N = B.PathNum;
	if (N < 2)
	{
		if (OutDir) *OutDir = B.Fwd;
		return N ? B.Path[0] : B.Pos;
	}
	for (int32 i = 0; i + 1 < N; ++i)
	{
		const float LineEnd = B.LineStartS[i] + B.LineLen[i];
		const FVector D(B.SegDir[i]);
		if (S <= LineEnd || i + 2 == N)
		{
			const float R0 = i > 0 ? B.CornerR[i] : 0.f;
			if (OutDir) *OutDir = D;
			return B.Path[i] + D * (R0 + FMath::Clamp(S - B.LineStartS[i], 0.f, B.LineLen[i]));
		}
		const int32 Cn = i + 1;
		if (B.CornerR[Cn] > 0.f && S <= LineEnd + B.ArcLen[Cn])
		{
			const float Local = S - LineEnd;
			if (B.ArcR[Cn] > 0.f)
			{
				const float Al = FMath::Clamp(Local / B.ArcR[Cn], 0.f, B.ArcPhi[Cn]);
				float Si, Co;
				FMath::SinCos(&Si, &Co, Al);
				const FVector N0(B.ArcN0[Cn]);
				if (OutDir) *OutDir = D * Co + N0 * Si;
				return B.ArcO[Cn] + (D * Si - N0 * Co) * B.ArcR[Cn];
			}
			if (OutDir) *OutDir = D;
			return B.Path[Cn] - D * B.CornerR[Cn] + D * Local;
		}
	}
	if (OutDir) *OutDir = FVector(B.SegDir[N - 2]);
	return B.Path[N - 1];
}

float ABumblebeeSwarm::SpeedLimit(const FBumblebee& B) const
{
	const float Rem = FMath::Max(B.PathLen - B.PathS, 0.f);
	float V = B.CruiseSpeed;
	if (B.bLandAtEnd)
	{
		// constant time-to-contact approach (as in landing insects): slows smoothly, touches down still moving
		V = FMath::Min(V, FMath::Max(TouchdownSpeed * FMath::Max(B.Scale, 0.5f), ApproachRate * Rem));
	}
	else
	{
		// end of a leg without a follow-up yet (rare): slow right down so the turn-back is gentle
		const float EndV = 15.f * FMath::Max(B.Scale, 0.5f);
		V = FMath::Min(V, FMath::Sqrt(FMath::Square(EndV) + 2.f * BeeConst::Decel * Rem));
	}
	// brake for the corners ahead (precomputed corner speeds)
	const int32 N = B.PathNum;
	for (int32 Cn = 1; Cn + 1 < N; ++Cn)
	{
		const float ArcStart = B.LineStartS[Cn - 1] + B.LineLen[Cn - 1];
		if (ArcStart - B.PathS > 600.f) break;
		if (B.CornerVc[Cn] >= 1e6f || ArcStart + B.ArcLen[Cn] < B.PathS) continue;
		const float Vc = B.CornerVc[Cn];
		V = FMath::Min(V, B.PathS < ArcStart ? FMath::Sqrt(Vc * Vc + 2.f * BeeConst::Decel * (ArcStart - B.PathS)) : Vc);
	}
	return FMath::Max(V, 0.5f * TouchdownSpeed * FMath::Max(B.Scale, 0.5f));
}

bool ABumblebeeSwarm::CornerCurveIsFree(const FBumblebee& B, const FVector& Din, const FVector& Dout, const FVector& C, float D)
{
	// sweep the arc as 4 chords; the chord sagitta is added to the sphere radius
	if (!HasBudget(4, false)) return false;
	const FArc Arc = MakeArc(Din, Dout, C, D);
	if (!Arc.bValid) return true;
	const float Sagitta = Arc.Rarc * (1.f - FMath::Cos(Arc.Phi / 8.f));
	const float Radius = Clearance(B) * 0.8f + Sagitta;
	FVector Prev = Arc.P0;
	for (int32 k = 1; k <= 4; ++k)
	{
		const FVector P = ArcPoint(Arc, Arc.Len * k / 4.f, nullptr);
		FHitResult H;
		if (Sweep(Prev, P, Radius, H)) return false;
		Prev = P;
	}
	return true;
}

void ABumblebeeSwarm::SetFlightPath(FBumblebee& B, TArrayView<const FVector> Points, bool bLand, const FVector& LandPoint, const FVector& LandNormal)
{
	const int32 N = FMath::Min(Points.Num(), 6);
	B.PathNum = (uint8)N;
	for (int32 i = 0; i < N; ++i)
	{
		B.Path[i] = Points[i];
		B.CornerR[i] = 0.f;
	}
	const float Dev = 0.3f * Clearance(B);
	const uint8 SavedCtx = TraceCtx;
	TraceCtx = P_TracePlan;
	for (int32 i = 1; i + 1 < N; ++i)
	{
		const FVector In = B.Path[i] - B.Path[i - 1];
		const FVector Out = B.Path[i + 1] - B.Path[i];
		const float Lin = float(In.Size()), Lout = float(Out.Size());
		if (Lin < KINDA_SMALL_NUMBER || Lout < KINDA_SMALL_NUMBER) continue;
		const FVector Di = In / Lin, Do = Out / Lout;
		const float Phi = TurnAngle(Di, Do);
		if (Phi < 1e-3f) continue;
		// a segment shared by two corners gives each up to 45%; the first segment (take-off) and the last one have one
		// corner only (landings keep at least half of the final approach straight, along the surface normal)
		const float MaxIn = (i - 1 == 0 ? 0.9f : 0.45f) * Lin;
		const float MaxOut = (i + 1 == N - 1 ? (bLand ? 0.5f : 0.9f) : 0.45f) * Lout;
		const float DWant = FMath::Min3(MaxIn, MaxOut, MaxCornerRadius);
		const float TanQ = FMath::Tan(Phi * 0.25f);
		const float DSafe = TanQ > 1e-4f ? FMath::Min(DWant, Dev / TanQ) : DWant;
		float Dt = DSafe;
		if (DWant > DSafe * 1.2f && DWant > 3.f)
		{
			if (CornerCurveIsFree(B, Di, Do, B.Path[i], DWant)) Dt = DWant;
			else
			{
				const float DMid = 0.5f * (DWant + DSafe);
				if (DMid > DSafe * 1.2f && CornerCurveIsFree(B, Di, Do, B.Path[i], DMid)) Dt = DMid;
			}
		}
		B.CornerR[i] = Dt;
	}
	TraceCtx = SavedCtx;
	// precompute the leg geometry once
	const float MinRadius = 0.3f * FMath::Max(B.Scale, 0.5f);
	float SAcc = 0.f;
	for (int32 i = 0; i + 1 < N; ++i)
	{
		const FVector C = B.Path[i + 1];
		const FVector D = (C - B.Path[i]).GetSafeNormal();
		B.SegDir[i] = FVector3f(D);
		const float R0 = i > 0 ? B.CornerR[i] : 0.f;
		const float R1 = (i + 1 < N - 1) ? B.CornerR[i + 1] : 0.f;
		B.LineStartS[i] = SAcc;
		B.LineLen[i] = FMath::Max(float(FVector::Dist(B.Path[i], C)) - R0 - R1, 0.f);
		SAcc += B.LineLen[i];
		if (i + 2 < N)
		{
			const int32 Cn = i + 1;
			const FVector Dn = (B.Path[i + 2] - C).GetSafeNormal();
			const FArc Arc = MakeArc(D, Dn, C, R1);
			B.ArcR[Cn] = Arc.bValid ? Arc.Rarc : 0.f;
			B.ArcPhi[Cn] = Arc.bValid ? Arc.Phi : TurnAngle(D, Dn);
			B.ArcO[Cn] = Arc.O;
			B.ArcN0[Cn] = FVector3f(Arc.N0);
			B.ArcLen[Cn] = R1 > 0.f ? CornerPieceLen(Arc, R1) : 0.f;
			const float Radius = FMath::Max(MinRadius, B.ArcR[Cn]);
			B.CornerVc[Cn] = B.ArcPhi[Cn] > 0.05f
				? FMath::Min(FMath::Sqrt(TurnAcceleration * Radius), FMath::DegreesToRadians(MaxPathTurnRate) * Radius) : 1e7f;
			SAcc += B.ArcLen[Cn];
		}
	}
	B.PathLen = SAcc;
	B.LastLegS = N >= 2 ? B.LineStartS[N - 2] : B.PathLen;		// start of the final straight
	B.PathS = 0.f;
	const float NewCruise = Rng.FRandRange(CruiseSpeedRange.X, CruiseSpeedRange.Y);
	if (B.State == EBeeState::Flying)
	{
		B.CruiseSpeed = FMath::Lerp(B.CruiseSpeed, NewCruise, 0.5f);	// keeps its speed: continuous flight
	}
	else
	{
		B.CruiseSpeed = NewCruise;
		B.Speed = 10.f * FMath::Max(B.Scale, 0.5f);						// lift-off
	}
	B.bLandAtEnd = bLand;
	B.LandPoint = LandPoint;
	B.LandNormal = LandNormal;
	B.ApproachLen = (bLand && N >= 2) ? float(FVector::Dist(B.Path[N - 2], B.Path[N - 1])) : 0.f;
	B.FlightPhase = 0;
	if (B.State != EBeeState::Flying)
	{
		B.SwayAmp = 0.f;
		B.SwaySide = FVector::CrossProduct((Points.Num() > 1 ? (Points[1] - Points[0]) : FVector::ForwardVector).GetSafeNormal(), FVector::UpVector).GetSafeNormal();
		if (B.SwaySide.IsNearlyZero()) B.SwaySide = FVector::RightVector;
		B.Accel = FVector::ZeroVector;
		B.PathVel = FVector::ZeroVector;
		B.Pos = Points[0];
	}
	B.State = EBeeState::Flying;
	B.Base = Points[0];			// in flight Pos keeps its sway offset: continuous across legs
	B.bWalking = false;
	B.WalkAmount = 0.f;
	B.PlanCooldown = 0.f;
	B.bRenderDirty = true;
}

void ABumblebeeSwarm::Remember(FBumblebee& B, const FVector& P)
{
	B.Visited[B.VisitedHead] = P;
	B.VisitedHead = (B.VisitedHead + 1) % 6;
	B.VisitedNum = (uint8)FMath::Min(B.VisitedNum + 1, 6);
}

void ABumblebeeSwarm::Land(FBumblebee& B)
{
	B.State = EBeeState::Landed;
	B.Pos = B.LandPoint;
	B.Up = B.LandNormal;
	FVector F = FVector::VectorPlaneProject(B.Rot.GetForwardVector(), B.Up).GetSafeNormal();
	if (F.IsNearlyZero()) F = FVector::VectorPlaneProject(FVector::UpVector, B.Up).GetSafeNormal();
	if (F.IsNearlyZero()) F = B.Up.ToOrientationQuat().GetAxisY();
	B.Fwd = F;
	B.bSettling = true;		// keep the current attitude; TickLanded eases it onto the surface (no snap at touchdown)
	++Stats.Landings;
	StartLandedBehaviour(B, true);
	B.bRenderDirty = true;
}

void ABumblebeeSwarm::TickFlying(int32 Index, FBumblebee& B, float Dt)
{
	const FVector Old = B.Pos;
	B.PlanCooldown -= Dt;

	// ask for the next leg before the end of this one, so the flight flows on without a stop. Only on the final straight
	// segment: the new path starts at the bee and runs to this segment's end, so it stays inside validated space.
	const float Rem0 = B.PathLen - B.PathS;
	if (!B.bLandAtEnd && !B.bWantsPlan && B.PlanCooldown <= 0.f && B.PathS >= B.LastLegS && Rem0 < FMath::Max(60.f, B.Speed * 0.8f))
	{
		B.bWantsPlan = true;
	}

	const float Limit = SpeedLimit(B);
	B.Speed = FMath::Clamp(Limit, B.Speed - BeeConst::Decel * Dt, B.Speed + BeeConst::Accel * Dt);
	B.Speed = FMath::Max(B.Speed, 2.f);
	B.PathS = FMath::Min(B.PathS + B.Speed * Dt, B.PathLen);
	FVector Dir;
	B.Base = PathPoint(B, B.PathS, &Dir);
	const float Rem = B.PathLen - B.PathS;

	// side-to-side sway: persistent (continuous across legs), proportional to speed, gone at touchdown;
	// always inside the clearance the path was validated with
	const float SpeedK = FMath::Clamp(B.Speed / FMath::Max(B.CruiseSpeed, 1.f), 0.f, 1.f);
	const float LandK = B.bLandAtEnd ? FMath::Clamp(Rem / FMath::Max(B.ApproachLen * 3.f, 1.f), 0.f, 1.f) : 1.f;
	B.SwayAmp = FMath::FInterpTo(B.SwayAmp, 0.25f * Clearance(B) * SpeedK * LandK, Dt, 3.f);
	// sway frame transported along the path: re-orthogonalise last frame's side vector to the new direction
	FVector Side = FVector::VectorPlaneProject(B.SwaySide, Dir);
	if (Side.SizeSquared() < 1e-4f)
	{
		Side = FVector::CrossProduct(Dir, FVector::UpVector);
		if (Side.SizeSquared() < 1e-4f) Side = FVector::CrossProduct(Dir, FVector::ForwardVector);
	}
	Side = Side.GetSafeNormal();
	B.SwaySide = Side;
	const FVector Up2 = FVector::CrossProduct(Side, Dir);
	const float W = B.WobbleSeed;
	const FVector Sway = (Side * FMath::Sin(Time * 6.1f + W) + Up2 * 0.7f * FMath::Sin(Time * 4.3f + W * 1.7f)) * B.SwayAmp;
	B.Pos = B.Base + Sway;

	if (Rem <= KINDA_SMALL_NUMBER)
	{
		if (B.bLandAtEnd)
		{
			Land(B);
			return;
		}
		// nothing planned yet (rare): turn back along the validated path at low speed instead of hanging in the air
		FVector Rev[6];
		const int32 First = B.PathNum >= 3 ? 1 : 0;
		int32 NumRev = 0;
		for (int32 i = B.PathNum - 1; i >= First; --i) Rev[NumRev++] = B.Path[i];
		const float KeepSpeed = FMath::Min(B.Speed, 0.3f * B.CruiseSpeed);
		Rev[0] = B.Base;
		SetFlightPath(B, MakeArrayView(Rev, NumRev), false, FVector::ZeroVector, FVector::UpVector);
		B.Speed = KeepSpeed;
		B.FlightPhase = 1;
		++Stats.DoubleBacks;
	}

	// motion state from the path (not frame differences, which are noisy with reduced-rate updates)
	const FVector PathVel = Dir * B.Speed;
	if (Dt > 1e-4f)
	{
		const FVector RawAccel = (PathVel - B.PathVel) / Dt;
		B.Accel = FMath::Lerp(B.Accel, RawAccel.GetClampedToMaxSize(4000.f), 1.f - FMath::Exp(-8.f * Dt));
	}
	B.PathVel = PathVel;
	B.Vel = (B.Pos - Old) / FMath::Max(Dt, 1e-4f);

	// body attitude: heading along the flight direction, nose up when braking or slow, banked into turns
	const FVector Face = Dir;
	FRotator R = Face.Rotation();
	const float Along = float(FVector::DotProduct(B.Accel, Dir));
	const FVector Lateral = B.Accel - Dir * Along;
	const float Slow = 1.f - SpeedK;
	R.Pitch = FMath::Clamp(R.Pitch * 0.6f, -35.f, 35.f) + 14.f * Slow + FMath::Clamp(-Along / 980.f * 20.f, -10.f, 15.f);
	const FVector RightH = FVector::CrossProduct(FVector::UpVector, FVector(Face.X, Face.Y, 0.f)).GetSafeNormal();
	const float LatG = RightH.IsNearlyZero() ? 0.f : float(FVector::DotProduct(Lateral, RightH)) / 980.f;
	R.Roll = FMath::Clamp(LatG * BankPerG, -35.f, 35.f);
	FQuat TargetRot = R.Quaternion();
	if (B.bLandAtEnd)
	{
		// rotate into the landed pose during the approach (legs towards the flower/wall)
		const float Blend = FMath::Clamp(1.f - Rem / FMath::Max(B.ApproachLen * 1.6f, 1.f), 0.f, 1.f);
		if (Blend > 0.f)
		{
			FVector F = FVector::VectorPlaneProject(TargetRot.GetForwardVector(), B.LandNormal).GetSafeNormal();
			if (F.IsNearlyZero()) F = FVector::VectorPlaneProject(FVector::UpVector, B.LandNormal).GetSafeNormal();
			if (!F.IsNearlyZero()) TargetRot = FQuat::Slerp(TargetRot, FRotationMatrix::MakeFromZX(B.LandNormal, F).ToQuat(), Blend);
		}
	}
	// ease towards the target, never faster than a body saccade
	const float Ang = B.Rot.AngularDistance(TargetRot);
	const float Step = FMath::Min(Ang * (1.f - FMath::Exp(-10.f * Dt)), FMath::DegreesToRadians(MaxBodyTurnRate) * Dt);
	if (Ang > 1e-4f) B.Rot = FQuat::Slerp(B.Rot, TargetRot, FMath::Clamp(Step / Ang, 0.f, 1.f));
	B.Rot.Normalize();
	B.Fwd = Face;
	B.bRenderDirty = true;
}

// =====================================================================================================================
void ABumblebeeSwarm::BeginFlight(FBumblebee& B)
{
	const ABumblebeeZone* Z = ZoneOf(B);
	const float Air = Z ? Z->AirTime : 0.5f;
	// number of extra aerial legs before landing (exponential, mean ~5*AirTime)
	const float Legs = -FMath::Loge(FMath::Max(Rng.FRand(), 0.01f)) * 5.f * Air;
	B.AirLegsLeft = (uint8)FMath::Clamp(FMath::FloorToInt(Legs), 0, 8);
}

ABumblebeeSwarm::EPlan ABumblebeeSwarm::Plan(int32 Index, FBumblebee& B)
{
	TraceCtx = P_TracePlan;
	const bool bUrgent = B.bThreatened;
	if (B.State == EBeeState::Landed)
	{
		if (!HasBudget(bUrgent ? 6 : 8, bUrgent)) return EPlan::Deferred;
		const FVector Start = B.Pos + B.Up * BeeConst::BodyHeight * B.Scale;
		const FVector Off = B.Pos + B.Up * BeeConst::TakeoffHeight * FMath::Max(B.Scale, 0.8f);
		FHitResult H;
		if (Line(B.Pos + B.Up * 0.4f * B.Scale, Off, H))
		{
			if (bUrgent) B.ThreatCooldown = Rng.FRandRange(1.f, 2.f);
			B.PlanCooldown = Rng.FRandRange(2.f, 5.f);
			B.LandedTimeLeft = B.PlanCooldown;
			B.bThreatened = false;
			return EPlan::Failed;
		}
		const ABumblebeeZone* Z = ZoneOf(B);
		bool bEscape = false;
		if (B.Tier == 0 && !bUrgent && (!Z || Z->bAvoidIndoors) && Stats.Escaping < MaxEscapingBees)
		{
			bEscape = IsEnclosed(Off, false);
		}
		FBumblebee Saved = B;
		B.Pos = Start;
		bool bOk;
		if (bEscape)
		{
			B.bEscaping = true;
			B.EscapeTime = 0.f;
			B.VisitedNum = 0;
			++Stats.EscapesStarted;
			bOk = PlanEscapeStep(Index, B, Off);
		}
		else if (bUrgent)
		{
			bOk = PlanLanding(Index, B, Off, B.ThreatPos);
		}
		else
		{
			BeginFlight(B);
			bOk = B.AirLegsLeft > 0 ? (PlanAirLeg(Index, B, Off) || PlanLanding(Index, B, Off, FVector::ZeroVector))
									: (PlanLanding(Index, B, Off, FVector::ZeroVector) || PlanAirLeg(Index, B, Off));
			if (bOk && B.AirLegsLeft > 0 && !B.bLandAtEnd) --B.AirLegsLeft;
		}
		if (bOk)
		{
			// the path starts at the body centre and goes straight off the surface first
			if (B.PathNum < 6 && !FVector(B.Path[0]).Equals(Start, 0.01))
			{
				FVector Pts[6];
				Pts[0] = Start;
				for (int32 i = 0; i < B.PathNum; ++i) Pts[i + 1] = B.Path[i];
				const bool bLand = B.bLandAtEnd;
				const FVector LP = B.LandPoint, LN = B.LandNormal;
				B.State = EBeeState::Landed;		// still lifting off: SetFlightPath sets the lift-off speed
				SetFlightPath(B, MakeArrayView(Pts, B.PathNum + 1), bLand, LP, LN);
			}
			B.Pos = Start;
			++Stats.Takeoffs;
			if (bUrgent) ++Stats.ThreatTakeoffs;
			B.bThreatened = false;
			return EPlan::Done;
		}
		const bool bWasEscape = bEscape;
		B = Saved;
		if (bWasEscape) { B.bEscaping = false; }
		++Stats.PlanFailures;
		B.PlanCooldown = Rng.FRandRange(1.f, 3.f);
		B.LandedTimeLeft = FMath::Max(B.LandedTimeLeft, B.PlanCooldown);
		if (bUrgent) B.ThreatCooldown = Rng.FRandRange(1.f, 2.f);
		B.bThreatened = false;
		return EPlan::Failed;
	}

	// airborne: plan the next leg from the end of the current one (the bee keeps flying meanwhile)
	if (!HasBudget(B.bEscaping ? 14 : 8, false)) return EPlan::Deferred;
	const FVector From = B.PathNum ? B.Path[B.PathNum - 1] : B.Pos;
	if (B.bEscaping)
	{
		Remember(B, From);
		B.EscapeTime += 2.f;
		if (HasOpenSky(From))
		{
			B.bEscaping = false;
			++Stats.EscapesSucceeded;
		}
		else if (B.EscapeTime < 60.f && PlanEscapeStep(Index, B, From))
		{
			return EPlan::Done;
		}
		else
		{
			B.bEscaping = false;	// give up for now, land somewhere and retry later
		}
	}
	if (B.AirLegsLeft > 0)
	{
		--B.AirLegsLeft;
		if (PlanAirLeg(Index, B, From)) return EPlan::Done;
	}
	if (PlanLanding(Index, B, From, FVector::ZeroVector)) return EPlan::Done;
	if (PlanAirLeg(Index, B, From)) return EPlan::Done;		// nothing to land on here: keep flying
	++Stats.PlanFailures;
	B.PlanCooldown = Rng.FRandRange(0.3f, 0.7f);
	return EPlan::Failed;
}

bool ABumblebeeSwarm::PlanAirLeg(int32 Index, FBumblebee& B, const FVector& From)
{
	if (!HasBudget(3, false)) return false;
	const ABumblebeeZone* Z = ZoneOf(B);
	FVector Dir;
	float Len;
	if (Z && (Rng.FRand() < Z->Preference || !Z->IsInside(From, 100.f)))
	{
		Dir = Z->RandomPoint(Rng, 0.f) - From;
		Len = FMath::Clamp(float(Dir.Size()), AirLegRange.X, AirLegRange.Y);
	}
	else
	{
		Dir = FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-0.35f, 0.35f));
		Len = Rng.FRandRange(AirLegRange.X, AirLegRange.Y);
	}
	Dir = Dir.GetSafeNormal();
	if (Dir.IsNearlyZero()) return false;
	// avoid hairpins: bees turn, but rarely reverse straight back
	const FVector In = (From - FlightBase(B)).GetSafeNormal();
	if (!In.IsNearlyZero() && FVector::DotProduct(Dir, In) < -0.2f) Dir = (Dir + In * 1.2f).GetSafeNormal();
	if (Dir.IsNearlyZero()) return false;
	FVector W = From + Dir * Len;
	// cruise low over the vegetation: 20..150 cm above whatever is below the waypoint
	FHitResult H;
	if (Line(W + FVector(0, 0, 80.f), W - FVector(0, 0, 600.f), H))
	{
		const float Above = float(W.Z - H.ImpactPoint.Z);
		if (Above < 20.f || Above > 220.f) W.Z = H.ImpactPoint.Z + Rng.FRandRange(25.f, 130.f);
	}
	FHitResult HS;
	if (Sweep(From, W, Clearance(B), HS))
	{
		if (HS.bStartPenetrating || HS.Distance < 40.f) return false;
		W = From + (W - From).GetSafeNormal() * (HS.Distance - 2.f);		// fly the free part
	}
	FVector Pts[3];
	int32 Num = 0;
	if (!FlightBase(B).Equals(From, 0.01)) Pts[Num++] = FlightBase(B);
	Pts[Num++] = From;
	Pts[Num++] = W;
	SetFlightPath(B, MakeArrayView(Pts, Num), false, FVector::ZeroVector, FVector::UpVector);
	return true;
}

bool ABumblebeeSwarm::PlanLanding(int32 Index, FBumblebee& B, const FVector& From, const FVector& AwayFrom)
{
	const ABumblebeeZone* Z = ZoneOf(B);
	const bool bFlee = !AwayFrom.IsZero();
	for (int32 Attempt = 0; Attempt < 4; ++Attempt)
	{
		if (!HasBudget(4, bFlee)) return false;
		FVector Dir;
		float Range;
		bool bHop = false;
		const bool bTowardZone = Z && !bFlee && (Rng.FRand() < Z->Preference || !Z->IsInside(From, 100.f));
		if (bFlee)
		{
			Dir = (From - AwayFrom).GetSafeNormal2D() + FVector(Rng.FRandRange(-0.5f, 0.5f), Rng.FRandRange(-0.5f, 0.5f), Rng.FRandRange(0.1f, 0.6f));
			Range = Rng.FRandRange(200.f, FMath::Max(FlightRange.Y, 250.f));
		}
		else if (bTowardZone)
		{
			FVector Q = Z->RandomPoint(Rng, -0.4f);
			// aim roughly level most of the time so the ray meets stems, walls, fences, rocks and leaves, not only the ground
			if (Rng.FRand() < 0.6f) Q.Z = From.Z + Rng.FRandRange(-40.f, 15.f);
			Dir = Q - From;
			const float Dist = float(Dir.Size());
			if (Dist > FlightRange.Y)
			{
				bHop = true;
				Range = FlightRange.Y * Rng.FRandRange(0.6f, 0.95f);
			}
			else
			{
				// overshoot the sample point so the ray meets whatever is there: wall, stem, leaf, rock, flower or ground
				Range = FMath::Clamp(Dist * Rng.FRandRange(1.3f, 2.2f), FlightRange.X, FlightRange.Y);
			}
		}
		else
		{
			Dir = FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-0.8f, 0.5f));
			Range = Rng.FRandRange(FlightRange.X, FlightRange.Y);
		}
		Dir = Dir.GetSafeNormal();
		if (Dir.IsNearlyZero()) continue;

		if (bHop)
		{
			// long way back to the preference box: fly to a free point in the air and plan again from there
			const FVector W = From + Dir * Range + FVector(0, 0, Rng.FRandRange(20.f, 80.f));
			FHitResult HS;
			if (Sweep(From, W, Clearance(B), HS)) continue;
			FVector HopPts[3];
			int32 Num = 0;
			if (!FlightBase(B).Equals(From, 0.01)) HopPts[Num++] = FlightBase(B);
			HopPts[Num++] = From;
			HopPts[Num++] = W;
			SetFlightPath(B, MakeArrayView(HopPts, Num), false, FVector::ZeroVector, FVector::UpVector);
			return true;
		}

		const FVector End = From + Dir * Range;
		FHitResult H;
		if (!Line(From, End, H))
		{
			// the ray met nothing: sometimes drop to what is below (mostly ground and flower tops), otherwise try another direction
			if (Rng.FRand() < 0.5f || !Line(End, End - FVector::UpVector * 1500.f, H)) continue;
		}
		if (!IsLandable(H)) continue;
		// open flat ground is what most rays find: sometimes keep looking for something else
		if (H.ImpactNormal.Z > 0.97f && Attempt < 3 && Rng.FRand() < 0.35f) continue;
		const FVector S = H.ImpactPoint;
		const FVector N = H.ImpactNormal;
		if (bTowardZone && !Z->IsInside(S, 150.f)) continue;
		if (FVector::DistSquared(S, From) < FMath::Square(25.f)) continue;
		const FVector A = S + N * BeeConst::ApproachHeight * FMath::Max(B.Scale, 0.8f);
		FHitResult H2;
		if (!Line(A, S - N * 2.f, H2) || FVector::DistSquared(FVector(H2.ImpactPoint), S) > FMath::Square(1.5f * FMath::Max(B.Scale, 1.f))) continue;
		if (Z && Z->bAvoidIndoors && B.Tier == 0 && !bFlee && HasBudget(6, false) && IsEnclosed(S + N * 20.f, false)) continue;
		FHitResult H3;
		if (Sweep(From, A, Clearance(B), H3)) continue;

		FVector Pts[6];
		int32 Num = 0;
		if (!FlightBase(B).Equals(From, 0.01)) Pts[Num++] = FlightBase(B);
		Pts[Num++] = From;
		// sometimes take a detour through the air (less robotic flights)
		const float Len = float(FVector::Dist(From, A));
		if (Len > 150.f && Rng.FRand() < 0.4f && HasBudget(2, bFlee))
		{
			const FVector Mid = (From + A) * 0.5f;
			const FVector Perp = FVector::CrossProduct((A - From).GetSafeNormal(), FVector::UpVector).GetSafeNormal();
			const FVector Wp = Mid + Perp * Rng.FRandRange(-0.35f, 0.35f) * Len + FVector(0, 0, Rng.FRandRange(20.f, 90.f));
			FHitResult H4, H5;
			if (!Sweep(From, Wp, Clearance(B), H4) && !Sweep(Wp, A, Clearance(B), H5)) Pts[Num++] = Wp;
		}
		Pts[Num++] = A;
		Pts[Num++] = S + N * BeeConst::BodyHeight * B.Scale;		// touchdown: body centre over the landing point
		SetFlightPath(B, MakeArrayView(Pts, Num), true, S, N);
		return true;
	}
	return false;
}

bool ABumblebeeSwarm::PlanEscapeStep(int32 Index, FBumblebee& B, const FVector& From)
{
	// Lightweight "find the way out": probe a fan of directions, prefer long free rays, open sky and unvisited space.
	if (!HasBudget(12, false)) return false;
	struct FCand { FVector Dir; float Free; float Score; };
	FCand C[9];
	const float A0 = Rng.FRand() * TWO_PI;
	int32 NumC = 0;
	for (int32 k = 0; k < 8; ++k)
	{
		const float A = A0 + k * (TWO_PI / 8.f) + Rng.FRandRange(-0.2f, 0.2f);
		C[NumC++].Dir = FVector(FMath::Cos(A), FMath::Sin(A), Rng.FRandRange(-0.15f, 0.35f)).GetSafeNormal();
	}
	if (const ABumblebeeZone* Z = ZoneOf(B))
	{
		C[NumC++].Dir = (Z->GetCenter() - From).GetSafeNormal();
	}
	for (int32 k = 0; k < NumC; ++k)
	{
		FHitResult H;
		const float MaxD = 700.f;
		C[k].Free = Line(From, From + C[k].Dir * MaxD, H) ? float(H.Distance) : MaxD;
		const FVector Probe = From + C[k].Dir * FMath::Min(C[k].Free * 0.7f, 400.f);
		float Penalty = 0.f;
		for (int32 v = 0; v < B.VisitedNum; ++v)
		{
			Penalty += 300.f * FMath::Exp(-float(FVector::DistSquared(Probe, B.Visited[v])) / FMath::Square(150.f));
		}
		C[k].Score = C[k].Free - Penalty + Rng.FRandRange(0.f, 60.f);
	}
	Algo::Sort(MakeArrayView(C, NumC), [](const FCand& L, const FCand& R) { return L.Score > R.Score; });
	// open-sky bonus for the best few (a door/window leads outside)
	for (int32 k = 0; k < FMath::Min(3, NumC); ++k)
	{
		if (C[k].Free < 80.f) continue;
		const FVector P = From + C[k].Dir * FMath::Min(C[k].Free - 30.f, 400.f);
		if (HasOpenSky(P)) C[k].Score += 2000.f;
	}
	Algo::Sort(MakeArrayView(C, NumC), [](const FCand& L, const FCand& R) { return L.Score > R.Score; });
	for (int32 k = 0; k < FMath::Min(2, NumC); ++k)
	{
		if (C[k].Free < 70.f) continue;
		const FVector W = From + C[k].Dir * FMath::Clamp(C[k].Free - 30.f, 40.f, 400.f);
		FHitResult H;
		if (Sweep(From, W, Clearance(B) * 0.8f, H)) continue;
		TArray<FVector, TInlineAllocator<3>> Pts;
		if (!FlightBase(B).Equals(From, 0.01)) Pts.Add(FlightBase(B));
		Pts.Add(From);
		Pts.Add(W);
		SetFlightPath(B, Pts, false, FVector::ZeroVector, FVector::UpVector);
		B.bEscaping = true;
		return true;
	}
	return false;
}

// =====================================================================================================================
void ABumblebeeSwarm::UpdateRender(int32 Index, FBumblebee& B)
{
	if (!bAssetsReady) return;
	const int8 Pose = B.State == EBeeState::Landed ? 1 : 0;
	const float D = B.ViewDist;
	const int8 Lod = D < LOD0Distance ? 0 : (D < LOD1Distance ? 1 : (D < LOD2Distance ? 2 : 3));
	const bool bPoseChanged = Pose != B.Pose || Lod != B.Lod;
	if (bPoseChanged)
	{
		if (B.Pose >= 0)
		{
			Instances[B.Pose * BeeConst::NumLods + B.Lod]->UpdateInstanceTransform(Index, BeeConst::Parked, false, false, true);
		}
		B.Pose = Pose;
		B.Lod = Lod;
		B.bRenderDirty = true;
	}
	if (!B.bRenderDirty) return;
	if (Pose == 1 && !bPoseChanged && D > LOD0Distance)
	{
		// bees on surfaces move slowly: beyond close-up range only send an update once the change would be ~half a pixel
		// (1080p, 90 deg FOV ~ 0.0015 rad per pixel); the pending change accumulates, nothing is lost
		const float Tol = 0.0007f * D;
		if (FVector::DistSquared(B.Pos, B.LastRenderPos) < FMath::Square(Tol) && B.Rot.AngularDistance(B.LastRenderRot) < 0.004f
			&& FMath::Abs(B.WalkAmount - B.LastRenderAmount) < 0.05f)
		{
			return;
		}
	}
	UInstancedStaticMeshComponent* C = Instances[Pose * BeeConst::NumLods + Lod];
	C->UpdateInstanceTransform(Index, FTransform(B.Rot, B.Pos, FVector(B.Scale)), false, false, true);
	if (Pose == 1)
	{
		const float Data[4] = { 0.f, FMath::Fmod(B.WalkPhase, 1024.f), B.WalkAmount * B.StrideModel, B.WingHz };
		C->SetCustomData(Index, MakeArrayView(Data, 4), false);		// one write instead of two
	}
	++InstanceUpdatesWindow;
	B.LastRenderPos = B.Pos;
	B.LastRenderRot = B.Rot;
	B.LastRenderAmount = B.WalkAmount;
	B.bRenderDirty = false;
}

// =====================================================================================================================
void ABumblebeeSwarm::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bAssetsReady) return;
	ApplyDebugToggles();
	if (CVarBeeEnable.GetValueOnGameThread() == 0) return;
	const double T0 = FPlatformTime::Seconds();
	bProfile = CVarBeeProfile.GetValueOnGameThread() != 0;
	double SecPlace = 0.0, SecLanded = 0.0, SecFlight = 0.0, SecPlan = 0.0, SecRender = 0.0;
	auto Now = [this]() { return bProfile ? FPlatformTime::Seconds() : 0.0; };
	const float Dt = FMath::Min(DeltaSeconds, 0.1f);
	Time += Dt;
	++FrameCounter;
	TracesThisFrame = 0;
	WalkTracesThisFrame = 0;
	GatherViewersAndThreats(Dt);

	// lazy placement: zones near a viewer place their bees on surfaces (collision is loaded there)
	const double TP0 = Now();
	TraceCtx = P_TracePlace;
	for (FZoneEntry& E : Zones)
	{
		const ABumblebeeZone* Z = E.Zone.Get();
		if (!Z || E.Placed >= E.Count) continue;
		const float R = float(Z->Box->GetScaledBoxExtent().Size());
		if (NearestViewerDistSq(Z->GetCenter()) > FMath::Square(PlacementDistance + R)) continue;
		for (int32 k = 0; k < 8 && E.Placed < E.Count && HasBudget(6, false); ++k)
		{
			const int32 Index = E.FirstBee + E.Placed;
			if (TryPlaceBee(Index, Z)) ++E.Placed;
		}
	}
	SecPlace += Now() - TP0;

	UrgentQueue.Reset();
	NearQueue.Reset();
	MidQueue.Reset();
	int32 Escaping = 0;
	const bool bDebug = bDrawDebug || CVarBeeDebug.GetValueOnGameThread() > 0;
	for (int32 i = 0; i < Bees.Num(); ++i)
	{
		FBumblebee& B = Bees[i];
		if (B.State == EBeeState::Unplaced) continue;
		// frozen far bees only re-check their distance every 8th frame (staggered)
		if (B.Tier == 2 && ((uint32(i) + FrameCounter) & 7u) != 0u) continue;
		UpdateTier(B);
		if (B.Tier == 2) { B.PendingDt = 0.f; continue; }		// frozen: keeps its valid pose/path until it is near again
		Escaping += B.bEscaping ? 1 : 0;
		// reduced update rate for small-on-screen bees (staggered so the cost is spread evenly)
		B.PendingDt += Dt;
		const uint32 Every = (B.Tier == 1 || B.ViewDist > LOD2Distance) ? 2u : 1u;	// full rate within LOD2 (10 m): no visible stepping
		if (Every > 1u && ((uint32(i) + FrameCounter) % Every) != 0u) continue;
		const float BeeDt = FMath::Min(B.PendingDt, 0.25f);
		B.PendingDt = 0.f;
		if (B.State == EBeeState::Landed)
		{
			if (!Threats.IsEmpty()) CheckThreat(B);
			const double T1 = Now();
			TickLanded(i, B, BeeDt);
			SecLanded += Now() - T1;
		}
		else
		{
			const double T1 = Now();
			TickFlying(i, B, BeeDt);
			SecFlight += Now() - T1;
		}
		if (B.bWantsPlan)
		{
			// threatened bees first, then bees already in the air (they need their next leg before the current one ends)
			(B.bThreatened || B.State == EBeeState::Flying ? UrgentQueue : (B.Tier == 0 ? NearQueue : MidQueue)).Add(i);
		}
		const double T2 = Now();
		UpdateRender(i, B);
		SecRender += Now() - T2;
		if (bDebug && B.Tier == 0 && B.State != EBeeState::Landed)
		{
			for (int32 p = 0; p + 1 < B.PathNum; ++p)
			{
				DrawDebugLine(GetWorld(), B.Path[p], B.Path[p + 1], B.bEscaping ? FColor::Orange : FColor::Cyan, false, -1.f, 0, 0.3f);
			}
		}
	}
	Stats.Escaping = Escaping;

	auto RunQueue = [this, &SecPlan, &SecRender, &Now](TArray<int32>& Q)
	{
		if (Q.IsEmpty()) return;
		const int32 Offset = int32(FrameCounter % uint32(Q.Num()));		// round robin: no starvation
		for (int32 k = 0; k < Q.Num(); ++k)
		{
			const int32 i = Q[(k + Offset) % Q.Num()];
			FBumblebee& B = Bees[i];
			if (!B.bWantsPlan) continue;
			B.bWantsPlan = false;
			const double T1 = Now();
			const EPlan Result = Plan(i, B);
			const double T2 = Now();
			SecPlan += T2 - T1;
			if (Result == EPlan::Deferred)
			{
				B.bWantsPlan = true;
				if (!B.bThreatened) break;
			}
			UpdateRender(i, B);
			SecRender += Now() - T2;
		}
	};
	RunQueue(UrgentQueue);
	RunQueue(NearQueue);
	RunQueue(MidQueue);

	const double TotalSec = FPlatformTime::Seconds() - T0;
	const float Ms = float(TotalSec * 1000.0);
	if (bProfile)
	{
		// sections include their traces; traces are reported separately, logic = section - its traces
		ProfSec[P_Place] += SecPlace;
		ProfSec[P_Landed] += SecLanded;
		ProfSec[P_Flight] += SecFlight;
		ProfSec[P_Plan] += SecPlan;
		ProfSec[P_Render] += SecRender;
		ProfSec[P_Scan] += FMath::Max(0.0, TotalSec - SecPlace - SecLanded - SecFlight - SecPlan - SecRender);
		++ProfFrames;
	}
	TickMsSum += Ms;
	++TickCount;
	TickMsMax = FMath::Max(TickMsMax, Ms);
	UpdateStats(Dt);
}

void ABumblebeeSwarm::UpdateStats(float Dt)
{
	StatsWindow += Dt;
	if (StatsWindow < 1.f) return;
	Stats.Bees = Bees.Num();
	Stats.Unplaced = Stats.Landed = Stats.Walking = Stats.Flying = Stats.Near = Stats.Mid = Stats.Far = 0;
	for (const FBumblebee& B : Bees)
	{
		switch (B.State)
		{
		case EBeeState::Unplaced: ++Stats.Unplaced; continue;
		case EBeeState::Landed: ++Stats.Landed; Stats.Walking += B.bWalking ? 1 : 0; break;
		default: ++Stats.Flying; break;
		}
		(B.Tier == 0 ? Stats.Near : (B.Tier == 1 ? Stats.Mid : Stats.Far)) += 1;
	}
	Stats.AvgTickMs = TickCount ? float(TickMsSum / TickCount) : 0.f;
	Stats.MaxTickMs = TickMsMax;
	Stats.TracesPerSecond = TracesWindow / StatsWindow;
	Stats.InstanceUpdatesPerSecond = FMath::RoundToInt(InstanceUpdatesWindow / StatsWindow);
	const float LogEvery = CVarBeeLogStats.GetValueOnGameThread();
	LogTimer += StatsWindow;
	if (LogEvery > 0.f && LogTimer >= LogEvery)
	{
		LogTimer = 0.f;
		UE_LOG(LogBumblebees, Log, TEXT("BEESTATS {\"t\":%.1f,\"bees\":%d,\"unplaced\":%d,\"landed\":%d,\"walking\":%d,\"flying\":%d,\"near\":%d,\"mid\":%d,\"far\":%d,\"escaping\":%d,\"avg_ms\":%.4f,\"max_ms\":%.4f,\"traces_s\":%.0f,\"takeoffs\":%d,\"threat_takeoffs\":%d,\"landings\":%d,\"esc_started\":%d,\"esc_ok\":%d,\"plan_fail\":%d}"),
			Time, Stats.Bees, Stats.Unplaced, Stats.Landed, Stats.Walking, Stats.Flying, Stats.Near, Stats.Mid, Stats.Far, Stats.Escaping,
			Stats.AvgTickMs, Stats.MaxTickMs, Stats.TracesPerSecond, Stats.Takeoffs, Stats.ThreatTakeoffs, Stats.Landings,
			Stats.EscapesStarted, Stats.EscapesSucceeded, Stats.PlanFailures);
		if (bProfile && ProfFrames > 0)
		{
			const double K = 1000.0 / ProfFrames;		// ms per frame
			UE_LOG(LogBumblebees, Log, TEXT("BEEPROF {\"frames\":%d,\"scan_threats_tiers\":%.4f,\"landed_walk_logic\":%.4f,\"walk_surface_traces\":%.4f,\"flight\":%.4f,\"plan_logic\":%.4f,\"plan_traces\":%.4f,\"place_logic\":%.4f,\"place_traces\":%.4f,\"instance_updates\":%.4f,\"inst_updates_s\":%d,\"double_backs\":%d,\"bee_bytes\":%d}"),
				ProfFrames, ProfSec[P_Scan] * K, (ProfSec[P_Landed] - ProfSec[P_TraceWalk]) * K, ProfSec[P_TraceWalk] * K, ProfSec[P_Flight] * K,
				(ProfSec[P_Plan] - ProfSec[P_TracePlan]) * K, ProfSec[P_TracePlan] * K, (ProfSec[P_Place] - ProfSec[P_TracePlace]) * K, ProfSec[P_TracePlace] * K,
				ProfSec[P_Render] * K, Stats.InstanceUpdatesPerSecond, Stats.DoubleBacks, int32(sizeof(FBumblebee)));
		}
		for (double& V : ProfSec) V = 0.0;
		ProfFrames = 0;
	}
	StatsWindow = 0.f;
	TracesWindow = 0;
	InstanceUpdatesWindow = 0;
	TickMsSum = 0.0;
	TickCount = 0;
	TickMsMax = 0.f;
}

FTransform ABumblebeeSwarm::GetBeeTransform(int32 Index) const
{
	if (!Bees.IsValidIndex(Index)) return FTransform::Identity;
	return FTransform(Bees[Index].Rot, Bees[Index].Pos, FVector(Bees[Index].Scale));
}

bool ABumblebeeSwarm::IsBeeLanded(int32 Index) const
{
	return Bees.IsValidIndex(Index) && Bees[Index].State == EBeeState::Landed;
}

bool ABumblebeeSwarm::IsBeeFlying(int32 Index) const
{
	return Bees.IsValidIndex(Index) && (Bees[Index].State == EBeeState::Flying || Bees[Index].State == EBeeState::Hover);
}

bool ABumblebeeSwarm::IsBeeWalking(int32 Index) const
{
	return Bees.IsValidIndex(Index) && Bees[Index].State == EBeeState::Landed && Bees[Index].bWalking;
}

FVector ABumblebeeSwarm::GetBeeSurfaceNormal(int32 Index) const
{
	return (Bees.IsValidIndex(Index) && Bees[Index].State == EBeeState::Landed) ? Bees[Index].Up : FVector::ZeroVector;
}

void ABumblebeeSwarm::ApplyDebugToggles()
{
	const bool bHide = CVarBeeRender.GetValueOnGameThread() == 0;
	const bool bNoShadow = CVarBeeShadows.GetValueOnGameThread() == 0;
	const bool bNoWpo = CVarBeeWPO.GetValueOnGameThread() == 0;
	if (bHide == bRenderHidden && bNoShadow == bShadowsOff && bNoWpo == bWpoOff) return;
	for (int32 c = 0; c < Instances.Num(); ++c)
	{
		UInstancedStaticMeshComponent* C = Instances[c];
		const int32 Lod = c % BeeConst::NumLods;
		if (bHide != bRenderHidden) C->SetVisibility(!bHide);
		if (bNoShadow != bShadowsOff) C->SetCastShadow(!bNoShadow && bCastShadowsNear && Lod <= 1);
		if (bNoWpo != bWpoOff) C->SetEvaluateWorldPositionOffset(!bNoWpo && Lod < 3);
	}
	bRenderHidden = bHide;
	bShadowsOff = bNoShadow;
	bWpoOff = bNoWpo;
}

float ABumblebeeSwarm::Clearance(const FBumblebee& B) const
{
	return FlightClearance * FMath::Max(B.Scale, 1.f);
}

void ABumblebeeSwarm::RefreshBeeScale(FBumblebee& B)
{
	float ZoneMul = 1.f;
	if (const ABumblebeeZone* Z = ZoneOf(B)) ZoneMul = Z->BeeSizeMultiplier;
	B.Scale = FMath::Max(0.05f, BeeScale * ZoneMul * B.SizeVariation);
	B.bRenderDirty = true;
}

void ABumblebeeSwarm::SetBeeScale(float NewScale)
{
	BeeScale = FMath::Max(0.05f, NewScale);
	for (FBumblebee& B : Bees) RefreshBeeScale(B);
}
