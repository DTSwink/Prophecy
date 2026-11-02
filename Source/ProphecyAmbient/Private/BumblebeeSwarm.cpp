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

namespace BeeConst
{
	static constexpr float BodyHeight = 0.85f;		// body centre above the surface when landed (cm)
	static constexpr float TakeoffHeight = 6.f;		// first point straight off the surface
	static constexpr float ApproachHeight = 8.f;	// hover/inspection point in front of the landing spot
	static constexpr float ApproachSpeed = 22.f;
	static constexpr float Accel = 450.f;
	static constexpr float StrideCm = 0.35f;		// distance per leg cycle (drives the material)
	static constexpr float ProbeStep = 0.8f;		// walking: surface probe every N cm
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
			C->SetNumCustomDataFloats(3);
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
	Bees.AddDefaulted(Entry.Count);
	TArray<FTransform> Parked;
	Parked.Init(BeeConst::Parked, Entry.Count);
	for (int32 i = Start; i < Bees.Num(); ++i)
	{
		Bees[i].Zone = (int16)ZoneIndex;
		Bees[i].WobbleSeed = Rng.FRand() * 100.f;
	}
	for (int32 c = 0; c < Instances.Num(); ++c)
	{
		UInstancedStaticMeshComponent* C = Instances[c];
		C->AddInstances(Parked, false, false, false);
		const float Flap = c < BeeConst::NumLods ? 1.f : 0.f;
		for (int32 i = Start; i < Bees.Num(); ++i)
		{
			C->SetCustomDataValue(i, 0, Flap, false);
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

int32 ABumblebeeSwarm::RelocateBeesTo(FVector Location, float Radius, int32 Count)
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
				B.LandedTimeLeft = Rng.FRandRange(2.f, 8.f);
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
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BumblebeeLine), bTraceComplex, this);
	Q.bReturnPhysicalMaterial = false;
	const bool bHit = GetWorld()->LineTraceSingleByChannel(Hit, A, B, TraceChannel, Q);
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
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BumblebeeSweep), false, this);
	Q.bReturnPhysicalMaterial = false;
	bool bHit = GetWorld()->SweepSingleByChannel(Hit, A, B, FQuat::Identity, TraceChannel, FCollisionShape::MakeSphere(Radius), Q);
	if (bHit && Hit.bStartPenetrating)
	{
		// starting close to a surface (take-off / hover next to a wall): retry with a body-sized sphere
		++TracesThisFrame;
		++TracesWindow;
		bHit = GetWorld()->SweepSingleByChannel(Hit, A, B, FQuat::Identity, TraceChannel, FCollisionShape::MakeSphere(Radius * 0.35f), Q);
		if (bHit && Hit.bStartPenetrating) return true;
	}
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
	return FMath::Min(0.35f * FMath::Pow(U, -1.f / 1.4f), 10.f);
}

void ABumblebeeSwarm::StartLandedBehaviour(FBumblebee& B, bool bFresh)
{
	const float U = Rng.FRand();
	B.LandedTimeLeft = FMath::Lerp(LandedTimeRange.X, LandedTimeRange.Y, U * U);
	if (!bFresh) B.LandedTimeLeft *= Rng.FRand();		// stagger initial take-offs
	B.bWalker = Rng.FRand() < WalkerFraction;
	B.bWalking = false;
	B.BoutTimeLeft = HeavyTailPause();
	B.TurnRate = 0.f;
	B.WalkAmount = 0.f;
	B.bThreatened = false;
	B.bWantsPlan = false;
	B.PlanCooldown = 0.f;
	B.ValidateTimer = Rng.FRandRange(2.f, 5.f);
	B.Vel = FVector::ZeroVector;
}

void ABumblebeeSwarm::CheckThreat(FBumblebee& B)
{
	if (B.bThreatened) return;
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
	B.LandedTimeLeft -= Dt;
	B.PlanCooldown -= Dt;
	if (B.LandedTimeLeft <= 0.f && B.PlanCooldown <= 0.f) B.bWantsPlan = true;

	// near, resting bees occasionally confirm their surface still exists (destroyed props, opened doors...)
	if (B.Tier == 0)
	{
		B.ValidateTimer -= Dt;
		if (B.ValidateTimer <= 0.f && HasBudget(1, false))
		{
			B.ValidateTimer = Rng.FRandRange(3.f, 6.f);
			FHitResult H;
			if (!Line(B.Pos + B.Up * 1.f, B.Pos - B.Up * 1.5f, H))
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
		else if (B.bWalker && B.Tier == 0)
		{
			B.bWalking = true;
			B.BoutTimeLeft = FMath::Clamp(-1.3f * FMath::Loge(FMath::Max(Rng.FRand(), 0.01f)), 0.3f, 4.f);
			B.WalkSpeed = Rng.FRandRange(WalkSpeedRange.X, WalkSpeedRange.Y);
			B.Fwd = FQuat(B.Up, FMath::DegreesToRadians(Rng.FRandRange(-60.f, 60.f))).RotateVector(B.Fwd);
		}
		else
		{
			B.BoutTimeLeft = HeavyTailPause();
		}
	}

	bool bMoved = false;
	if (B.bWalking && B.Tier == 0)
	{
		const float Step = B.WalkSpeed * Dt;
		const bool bNeedProbe = B.ProbeDistance + Step >= BeeConst::ProbeStep;
		if (!bNeedProbe || HasBudget(2, false))
		{
			// correlated random walk (Ornstein-Uhlenbeck turning rate)
			B.TurnRate += (-B.TurnRate / 0.6f) * Dt + Rng.FRandRange(-1.f, 1.f) * 2.8f * FMath::Sqrt(Dt);
			FVector F = FQuat(B.Up, B.TurnRate * Dt).RotateVector(B.Fwd);
			if (const ABumblebeeZone* Z = ZoneOf(B))
			{
				if (!Z->IsInside(B.Pos, 50.f))	// wandered out of the preference box: steer back
				{
					const FVector To = FVector::VectorPlaneProject(Z->GetCenter() - B.Pos, B.Up).GetSafeNormal();
					F = (F + To * 2.f * Dt).GetSafeNormal();
				}
			}
			B.Fwd = FVector::VectorPlaneProject(F, B.Up).GetSafeNormal();
			if (bNeedProbe)
			{
				B.ProbeDistance = 0.f;
				FHitResult H;
				const FVector Eye = B.Pos + B.Up * 0.6f;
				if (Line(Eye, Eye + B.Fwd * 1.2f, H))
				{
					// obstacle ahead: turn away and stop for a moment
					B.Fwd = FQuat(B.Up, FMath::DegreesToRadians(Rng.FRandRange(110.f, 250.f))).RotateVector(B.Fwd);
					B.bWalking = false;
					B.BoutTimeLeft = HeavyTailPause();
				}
				else
				{
					const FVector Ahead = B.Pos + B.Fwd * Step;
					if (Line(Ahead + B.Up * 1.f, Ahead - B.Up * 1.5f, H) && IsLandable(H) && FVector::DotProduct(FVector(H.ImpactNormal), B.Up) > 0.5f)
					{
						B.Pos = H.ImpactPoint;
						B.Up = (B.Up + FVector(H.ImpactNormal) * 1.5f).GetSafeNormal();
						B.Fwd = FVector::VectorPlaneProject(B.Fwd, B.Up).GetSafeNormal();
						bMoved = true;
					}
					else
					{
						// edge / gap: don't step off, turn around
						B.Fwd = FQuat(B.Up, FMath::DegreesToRadians(Rng.FRandRange(140.f, 220.f))).RotateVector(B.Fwd);
						B.bWalking = false;
						B.BoutTimeLeft = HeavyTailPause();
					}
				}
			}
			else
			{
				B.Pos += B.Fwd * Step;
				B.ProbeDistance += Step;
				bMoved = true;
			}
			if (bMoved) B.WalkPhase += Step / BeeConst::StrideCm;
		}
	}
	else if (B.bWalking)
	{
		B.bWalking = false;		// left the near tier: just rest
	}

	const float TargetAmount = (B.bWalking && bMoved) ? 1.f : 0.f;
	const float NewAmount = FMath::FInterpTo(B.WalkAmount, TargetAmount, Dt, 12.f);
	if (bMoved || !FMath::IsNearlyEqual(NewAmount, B.WalkAmount, 0.001f))
	{
		B.WalkAmount = NewAmount;
		const FQuat Target = FRotationMatrix::MakeFromZX(B.Up, B.Fwd).ToQuat();
		B.Rot = FQuat::Slerp(B.Rot, Target, 1.f - FMath::Exp(-12.f * Dt));
		B.bRenderDirty = true;
	}
}

// =====================================================================================================================
FVector ABumblebeeSwarm::PathPoint(const FBumblebee& B, float S, FVector* OutDir)
{
	for (int32 i = 0; i + 1 < B.PathNum; ++i)
	{
		const FVector Seg = B.Path[i + 1] - B.Path[i];
		const float L = float(Seg.Size());
		if (S <= L || i + 2 == B.PathNum)
		{
			if (OutDir) *OutDir = L > KINDA_SMALL_NUMBER ? Seg / L : FVector::ForwardVector;
			return B.Path[i] + Seg * (L > KINDA_SMALL_NUMBER ? FMath::Clamp(S / L, 0.f, 1.f) : 0.f);
		}
		S -= L;
	}
	if (OutDir) *OutDir = FVector::ForwardVector;
	return B.PathNum ? B.Path[B.PathNum - 1] : B.Pos;
}

void ABumblebeeSwarm::SetFlightPath(FBumblebee& B, TArrayView<const FVector> Points, bool bLand, const FVector& LandPoint, const FVector& LandNormal)
{
	B.PathNum = (uint8)FMath::Min(Points.Num(), 6);
	B.PathLen = 0.f;
	for (int32 i = 0; i < B.PathNum; ++i)
	{
		B.Path[i] = Points[i];
		if (i) B.PathLen += float(FVector::Dist(Points[i - 1], Points[i]));
	}
	B.PathS = 0.f;
	B.Speed = 20.f;
	B.CruiseSpeed = Rng.FRandRange(CruiseSpeedRange.X, CruiseSpeedRange.Y);
	B.bLandAtEnd = bLand;
	B.LandPoint = LandPoint;
	B.LandNormal = LandNormal;
	B.HoverTimeLeft = bLand ? Rng.FRandRange(0.25f, 1.1f) : Rng.FRandRange(0.2f, 0.7f);
	B.FlightPhase = 0;
	B.State = EBeeState::Flying;
	B.Pos = Points[0];
	B.bWalking = false;
	B.WalkAmount = 0.f;
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
	B.Rot = FRotationMatrix::MakeFromZX(B.Up, B.Fwd).ToQuat();
	++Stats.Landings;
	StartLandedBehaviour(B, true);
	B.bRenderDirty = true;
}

void ABumblebeeSwarm::TickFlying(int32 Index, FBumblebee& B, float Dt)
{
	FVector Dir = B.Fwd;
	const FVector Old = B.Pos;
	FQuat TargetRot = B.Rot;

	if (B.FlightPhase == 0)
	{
		const float Remaining = B.PathLen - B.PathS;
		const float EndSpeed = 15.f;
		const float Desired = FMath::Min(B.CruiseSpeed, FMath::Sqrt(2.f * BeeConst::Accel * FMath::Max(Remaining, 0.f)) + EndSpeed);
		B.Speed = FMath::Clamp(Desired, B.Speed - BeeConst::Accel * Dt, B.Speed + BeeConst::Accel * Dt);
		B.PathS = FMath::Min(B.PathS + B.Speed * Dt, B.PathLen);
		FVector Base = PathPoint(B, B.PathS, &Dir);
		// meander (bounded by the validated clearance, fades out at both ends)
		const float Amp = FMath::Min(2.f, 0.06f * FMath::Min(B.PathS, B.PathLen - B.PathS));
		const FVector Side = FVector::CrossProduct(Dir, FVector::UpVector).GetSafeNormal();
		const FVector Up2 = FVector::CrossProduct(Side, Dir);
		const float W = B.WobbleSeed;
		B.Pos = Base + (Side * FMath::Sin(Time * 6.1f + W) + Up2 * 0.7f * FMath::Sin(Time * 4.3f + W * 1.7f)) * Amp;
		if (B.PathS >= B.PathLen - KINDA_SMALL_NUMBER)
		{
			B.FlightPhase = 1;
			Remember(B, B.Pos);
		}
	}
	else if (B.FlightPhase == 1)
	{
		// hover: inspect the landing spot / look around while searching
		B.HoverTimeLeft -= Dt;
		const FVector C = B.PathNum ? B.Path[B.PathNum - 1] : B.Pos;
		const float W = B.WobbleSeed;
		B.Pos = C + FVector(FMath::Sin(Time * 3.7f + W), FMath::Sin(Time * 2.9f + W * 1.3f), 0.6f * FMath::Sin(Time * 5.1f + W * 0.7f)) * 0.7f;
		if (B.HoverTimeLeft <= 0.f)
		{
			if (B.bLandAtEnd) B.FlightPhase = 2;
			else B.bWantsPlan = true;		// keep hovering until a new plan is made
		}
	}
	else
	{
		// final approach along the surface normal, rotating into the landed pose
		const FVector Touch = B.LandPoint + B.LandNormal * BeeConst::BodyHeight;
		const FVector To = Touch - B.Pos;
		const float D = float(To.Size());
		const float Step = BeeConst::ApproachSpeed * Dt;
		if (D <= Step)
		{
			Land(B);
			return;
		}
		B.Pos += To / D * Step;
		FVector F = FVector::VectorPlaneProject(B.Rot.GetForwardVector(), B.LandNormal).GetSafeNormal();
		if (F.IsNearlyZero()) F = FVector::VectorPlaneProject(FVector::UpVector, B.LandNormal).GetSafeNormal();
		const FQuat Landed = FRotationMatrix::MakeFromZX(B.LandNormal, F).ToQuat();
		B.Rot = FQuat::Slerp(B.Rot, Landed, 1.f - FMath::Exp(-14.f * Dt));
		B.Vel = (B.Pos - Old) / FMath::Max(Dt, 1e-4f);
		B.bRenderDirty = true;
		return;
	}

	B.Vel = (B.Pos - Old) / FMath::Max(Dt, 1e-4f);
	const float Spd = float(B.Vel.Size());
	FVector Face = Spd > 20.f ? B.Vel / Spd : B.Rot.GetForwardVector();
	if (B.FlightPhase == 1 && B.bLandAtEnd)
	{
		// face the flower/wall before landing
		const FVector ToSurf = (B.LandPoint - B.Pos).GetSafeNormal();
		Face = (ToSurf.Z > -0.8f) ? ToSurf : Face;
	}
	FRotator R = Face.Rotation();
	const float Slow = 1.f - FMath::Clamp(Spd / FMath::Max(B.CruiseSpeed, 1.f), 0.f, 1.f);
	R.Pitch = FMath::Clamp(R.Pitch * 0.6f, -35.f, 35.f) + 18.f * Slow;
	R.Roll = 0.f;
	TargetRot = R.Quaternion();
	B.Rot = FQuat::Slerp(B.Rot, TargetRot, 1.f - FMath::Exp(-9.f * Dt));
	B.Fwd = Face;
	B.bRenderDirty = true;
}

// =====================================================================================================================
ABumblebeeSwarm::EPlan ABumblebeeSwarm::Plan(int32 Index, FBumblebee& B)
{
	const bool bUrgent = B.bThreatened;
	if (B.State == EBeeState::Landed)
	{
		if (!HasBudget(bUrgent ? 6 : 8, bUrgent)) return EPlan::Deferred;
		const FVector Start = B.Pos + B.Up * BeeConst::BodyHeight;
		const FVector Off = B.Pos + B.Up * BeeConst::TakeoffHeight;
		FHitResult H;
		if (Line(B.Pos + B.Up * 0.4f, Off, H))
		{
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
		else
		{
			bOk = PlanLanding(Index, B, Off, bUrgent ? B.ThreatPos : FVector::ZeroVector);
		}
		if (bOk)
		{
			// the path starts at the body centre and goes straight off the surface first
			if (B.PathNum < 6 && !FVector(B.Path[0]).Equals(Start, 0.01))
			{
				for (int32 i = B.PathNum; i > 0; --i) B.Path[i] = B.Path[i - 1];
				B.Path[0] = Start;
				++B.PathNum;
				B.PathLen += float(FVector::Dist(B.Path[0], B.Path[1]));
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
		B.bThreatened = false;
		return EPlan::Failed;
	}

	// airborne (end of an air hop / escape step)
	if (!HasBudget(B.bEscaping ? 14 : 8, false)) return EPlan::Deferred;
	if (B.bEscaping)
	{
		B.EscapeTime += 2.f;
		if (HasOpenSky(B.Pos))
		{
			B.bEscaping = false;
			++Stats.EscapesSucceeded;
		}
		else if (B.EscapeTime < 60.f && PlanEscapeStep(Index, B, B.Pos))
		{
			return EPlan::Done;
		}
		else
		{
			B.bEscaping = false;	// give up for now, land somewhere and retry later
		}
	}
	if (PlanLanding(Index, B, B.Pos, FVector::ZeroVector)) return EPlan::Done;
	++Stats.PlanFailures;
	B.HoverTimeLeft = Rng.FRandRange(0.3f, 0.8f);
	B.FlightPhase = 1;
	return EPlan::Failed;
}

bool ABumblebeeSwarm::PlanLanding(int32 Index, FBumblebee& B, const FVector& From, const FVector& AwayFrom)
{
	const ABumblebeeZone* Z = ZoneOf(B);
	const bool bFlee = !AwayFrom.IsZero();
	for (int32 Attempt = 0; Attempt < 3; ++Attempt)
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
			const FVector Q = Z->RandomPoint(Rng, -0.4f);
			Dir = Q - From;
			const float Dist = float(Dir.Size());
			if (Dist > FlightRange.Y)
			{
				bHop = true;
				Range = FlightRange.Y * Rng.FRandRange(0.6f, 0.95f);
			}
			else
			{
				Range = FMath::Clamp(Dist * 1.25f, FlightRange.X, FlightRange.Y);
			}
		}
		else
		{
			Dir = FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-0.75f, 0.3f));
			Range = Rng.FRandRange(FlightRange.X, FlightRange.Y);
		}
		Dir = Dir.GetSafeNormal();
		if (Dir.IsNearlyZero()) continue;

		if (bHop)
		{
			// long way back to the preference box: fly to a free point in the air and plan again from there
			const FVector W = From + Dir * Range + FVector(0, 0, Rng.FRandRange(20.f, 80.f));
			FHitResult HS;
			if (Sweep(From, W, FlightClearance, HS)) continue;
			TArray<FVector, TInlineAllocator<3>> HopPts;
			if (!B.Pos.Equals(From, 0.01)) HopPts.Add(B.Pos);
			HopPts.Add(From);
			HopPts.Add(W);
			SetFlightPath(B, HopPts, false, FVector::ZeroVector, FVector::UpVector);
			return true;
		}

		const FVector End = From + Dir * Range;
		FHitResult H;
		if (!Line(From, End, H))
		{
			if (!Line(End, End - FVector::UpVector * 1500.f, H)) continue;
		}
		if (!IsLandable(H)) continue;
		const FVector S = H.ImpactPoint;
		const FVector N = H.ImpactNormal;
		if (bTowardZone && !Z->IsInside(S, 150.f)) continue;
		if (FVector::DistSquared(S, From) < FMath::Square(25.f)) continue;
		const FVector A = S + N * BeeConst::ApproachHeight;
		FHitResult H2;
		if (!Line(A, S - N * 2.f, H2) || FVector::DistSquared(FVector(H2.ImpactPoint), S) > FMath::Square(1.5f)) continue;
		if (Z && Z->bAvoidIndoors && B.Tier == 0 && !bFlee && HasBudget(6, false) && IsEnclosed(S + N * 20.f, false)) continue;
		FHitResult H3;
		if (Sweep(From, A, FlightClearance, H3)) continue;

		TArray<FVector, TInlineAllocator<6>> Pts;
		if (!B.Pos.Equals(From, 0.01)) Pts.Add(B.Pos);
		Pts.Add(From);
		// sometimes take a detour through the air (less robotic flights)
		const float Len = float(FVector::Dist(From, A));
		if (Len > 150.f && Rng.FRand() < 0.4f && HasBudget(2, bFlee))
		{
			const FVector Mid = (From + A) * 0.5f;
			const FVector Perp = FVector::CrossProduct((A - From).GetSafeNormal(), FVector::UpVector).GetSafeNormal();
			const FVector Wp = Mid + Perp * Rng.FRandRange(-0.35f, 0.35f) * Len + FVector(0, 0, Rng.FRandRange(20.f, 90.f));
			FHitResult H4, H5;
			if (!Sweep(From, Wp, FlightClearance, H4) && !Sweep(Wp, A, FlightClearance, H5)) Pts.Add(Wp);
		}
		Pts.Add(A);
		SetFlightPath(B, Pts, true, S, N);
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
		if (Sweep(From, W, FlightClearance * 0.8f, H)) continue;
		TArray<FVector, TInlineAllocator<3>> Pts;
		if (!B.Pos.Equals(From, 0.01)) Pts.Add(B.Pos);
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
	if (Pose != B.Pose || Lod != B.Lod)
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
	UInstancedStaticMeshComponent* C = Instances[Pose * BeeConst::NumLods + Lod];
	C->UpdateInstanceTransform(Index, FTransform(B.Rot, B.Pos), false, false, true);
	if (Pose == 1)
	{
		C->SetCustomDataValue(Index, 1, FMath::Fmod(B.WalkPhase, 1024.f), false);
		C->SetCustomDataValue(Index, 2, B.WalkAmount, false);
	}
	B.bRenderDirty = false;
}

// =====================================================================================================================
void ABumblebeeSwarm::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bAssetsReady || CVarBeeEnable.GetValueOnGameThread() == 0) return;
	const double T0 = FPlatformTime::Seconds();
	const float Dt = FMath::Min(DeltaSeconds, 0.1f);
	Time += Dt;
	++FrameCounter;
	TracesThisFrame = 0;
	GatherViewersAndThreats(Dt);

	// lazy placement: zones near a viewer place their bees on surfaces (collision is loaded there)
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

	UrgentQueue.Reset();
	NearQueue.Reset();
	MidQueue.Reset();
	int32 Escaping = 0;
	const bool bDebug = bDrawDebug || CVarBeeDebug.GetValueOnGameThread() > 0;
	for (int32 i = 0; i < Bees.Num(); ++i)
	{
		FBumblebee& B = Bees[i];
		if (B.State == EBeeState::Unplaced) continue;
		UpdateTier(B);
		if (B.Tier == 2) continue;		// frozen: keeps its valid pose/path until it is near again
		if (B.State == EBeeState::Landed)
		{
			if (!Threats.IsEmpty()) CheckThreat(B);
			TickLanded(i, B, Dt);
		}
		else
		{
			TickFlying(i, B, Dt);
		}
		Escaping += B.bEscaping ? 1 : 0;
		if (B.bWantsPlan)
		{
			(B.bThreatened ? UrgentQueue : (B.Tier == 0 ? NearQueue : MidQueue)).Add(i);
		}
		UpdateRender(i, B);
		if (bDebug && B.Tier == 0 && B.State != EBeeState::Landed)
		{
			for (int32 p = 0; p + 1 < B.PathNum; ++p)
			{
				DrawDebugLine(GetWorld(), B.Path[p], B.Path[p + 1], B.bEscaping ? FColor::Orange : FColor::Cyan, false, -1.f, 0, 0.3f);
			}
		}
	}
	Stats.Escaping = Escaping;

	auto RunQueue = [this](TArray<int32>& Q)
	{
		if (Q.IsEmpty()) return;
		const int32 Offset = int32(FrameCounter % uint32(Q.Num()));		// round robin: no starvation
		for (int32 k = 0; k < Q.Num(); ++k)
		{
			const int32 i = Q[(k + Offset) % Q.Num()];
			FBumblebee& B = Bees[i];
			if (!B.bWantsPlan) continue;
			B.bWantsPlan = false;
			if (Plan(i, B) == EPlan::Deferred)
			{
				B.bWantsPlan = true;
				if (!B.bThreatened) break;
			}
			UpdateRender(i, B);
		}
	};
	RunQueue(UrgentQueue);
	RunQueue(NearQueue);
	RunQueue(MidQueue);

	const float Ms = float((FPlatformTime::Seconds() - T0) * 1000.0);
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
	const float LogEvery = CVarBeeLogStats.GetValueOnGameThread();
	LogTimer += StatsWindow;
	if (LogEvery > 0.f && LogTimer >= LogEvery)
	{
		LogTimer = 0.f;
		UE_LOG(LogBumblebees, Log, TEXT("BEESTATS {\"t\":%.1f,\"bees\":%d,\"unplaced\":%d,\"landed\":%d,\"walking\":%d,\"flying\":%d,\"near\":%d,\"mid\":%d,\"far\":%d,\"escaping\":%d,\"avg_ms\":%.4f,\"max_ms\":%.4f,\"traces_s\":%.0f,\"takeoffs\":%d,\"threat_takeoffs\":%d,\"landings\":%d,\"esc_started\":%d,\"esc_ok\":%d,\"plan_fail\":%d}"),
			Time, Stats.Bees, Stats.Unplaced, Stats.Landed, Stats.Walking, Stats.Flying, Stats.Near, Stats.Mid, Stats.Far, Stats.Escaping,
			Stats.AvgTickMs, Stats.MaxTickMs, Stats.TracesPerSecond, Stats.Takeoffs, Stats.ThreatTakeoffs, Stats.Landings,
			Stats.EscapesStarted, Stats.EscapesSucceeded, Stats.PlanFailures);
	}
	StatsWindow = 0.f;
	TracesWindow = 0;
	TickMsSum = 0.0;
	TickCount = 0;
	TickMsMax = 0.f;
}

FTransform ABumblebeeSwarm::GetBeeTransform(int32 Index) const
{
	if (!Bees.IsValidIndex(Index)) return FTransform::Identity;
	return FTransform(Bees[Index].Rot, Bees[Index].Pos);
}

bool ABumblebeeSwarm::IsBeeLanded(int32 Index) const
{
	return Bees.IsValidIndex(Index) && Bees[Index].State == EBeeState::Landed;
}

bool ABumblebeeSwarm::IsBeeFlying(int32 Index) const
{
	return Bees.IsValidIndex(Index) && (Bees[Index].State == EBeeState::Flying || Bees[Index].State == EBeeState::Hover);
}
