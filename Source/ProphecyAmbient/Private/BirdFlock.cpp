#include "BirdFlock.h"
#include "Bird.h"
#include "BirdFish.h"
#include "Components/StaticMeshComponent.h"
#include "BirdZone.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Level.h"
#include "Misc/StringBuilder.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "HAL/IConsoleManager.h"
#include "NiagaraFunctionLibrary.h"
#include "SceneInterface.h"
#include "NiagaraSystem.h"

static TAutoConsoleVariable<int32> CVarBirdsEnable(TEXT("birds.Enable"), 1, TEXT("0 = freeze every ambient bird"));

namespace
{
	constexpr int32 CellCoverDark = 6, CellCoverLight = 7, CellContourLight = 9, CellContourDark = 10, CellDownLight = 11, CellDownDark = 12;
	const TCHAR* FeatherMeshPath = TEXT("/Game/Prophecy/Creatures/Birds/SM_BirdFeatherFX.SM_BirdFeatherFX");
	constexpr int32 PoolSize = 500;
	const FTransform Hidden(FQuat::Identity, FVector(0, 0, -1e6), FVector(0.001f));
}

ABirdFlock::ABirdFlock()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	BloodSplatSystem = TSoftObjectPtr<UNiagaraSystem>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/NS_bloodsplat.NS_bloodsplat")));
	FishMesh = TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/_mygame/assets/fish/SM_Fish.SM_Fish")));
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	LethalClasses.Add(TSoftClassPtr<AActor>(FSoftObjectPath(TEXT("/Game/_mygame/spear/A_Spear.A_Spear_C"))));
}

ABirdFlock* ABirdFlock::Find(const UObject* WorldContext, bool bCreate)
{
	UWorld* W = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!W) return nullptr;
	for (TActorIterator<ABirdFlock> It(W); It; ++It) return *It;
	if (!bCreate) return nullptr;
	FActorSpawnParameters P;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	P.ObjectFlags |= RF_Transient;
	return W->SpawnActor<ABirdFlock>(FVector::ZeroVector, FRotator::ZeroRotator, P);
}

void ABirdFlock::BeginPlay()
{
	Super::BeginPlay();
	SpawnHandle = GetWorld()->AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &ABirdFlock::OnAnyActorSpawned));
	for (TSoftClassPtr<AActor>& C : LethalClasses) C.LoadSynchronous();
	for (TSoftClassPtr<AActor>& C : ThreatClasses) C.LoadSynchronous();
	for (AActor* A : ThreatActors) AddThreatActor(A);
	if (bBloodSplat) BloodSplatSystem.LoadSynchronous();		// no hitch at the first bleeding hit
	FishMesh.LoadSynchronous();
	ScanWater();
	ScanLethals();		// one full pass now; afterwards the world is re-covered in slices (ScanSlice) and spawns are caught at once
	ScanCycleStart = FPlatformTime::Seconds();
}

void ABirdFlock::AddWaterActor(AActor* Actor)
{
	if (!Actor) return;
	WaterActors.AddUnique(Actor);
	ScanWater();
}

bool ABirdFlock::IsWaterActor(const AActor* A) const
{
	if (!A) return false;
	for (const FWater& W : Waters) if (W.Actor.Get() == A) return true;
	return false;
}

void ABirdFlock::ScanWater()
{
	Waters.Reset();
	auto AddActor = [this](AActor* A)
	{
		if (!A) return;
		const FBox B = A->GetComponentsBoundingBox(true);
		if (B.IsValid) Waters.Add({ A, B });
	};
	for (AActor* A : WaterActors) AddActor(A);
	WaterChecked.Reset();
	if (!bAutoDetectWater) return;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* A = *It;
		if (!A || WaterActors.Contains(A) || Cast<ABird>(A) || Cast<ABirdFish>(A)) continue;
		WaterChecked.Add(FObjectKey(A));
		if (LooksLikeWater(A)) AddActor(A);
	}
}

bool ABirdFlock::LooksLikeWater(AActor* A) const
{
	if (A->ActorHasTag(TEXT("BirdWater"))) return true;
	FString Names = A->GetClass()->GetName() + TEXT(" ") + A->GetName();
#if WITH_EDITOR
	Names += TEXT(" ") + A->GetActorLabel();
#endif
	A->ForEachComponent<UStaticMeshComponent>(false, [&](UStaticMeshComponent* C) { if (C->GetStaticMesh()) Names += TEXT(" ") + C->GetStaticMesh()->GetName(); });
	const FString L = Names.ToLower();
	if (!((L.Contains(TEXT("water")) || L.Contains(TEXT("ocean")) || L.Contains(TEXT("lake")) || L.Contains(TEXT("sea"))) && !L.Contains(TEXT("well")))) return false;
	// must be a flat surface of some size (not a bucket called "water")
	const FBox B = A->GetComponentsBoundingBox(true);
	const FVector E = B.GetExtent();
	return B.IsValid && E.X > 150.f && E.Y > 150.f && E.Z < 0.05f * FMath::Min(E.X, E.Y) + 5.f;
}

bool ABirdFlock::IsWater(const FVector& P, float* OutSurfaceZ, float Margin) const
{
	for (const FWater& W : Waters)
	{
		const FBox& B = W.Box;
		if (P.X >= B.Min.X + Margin && P.X <= B.Max.X - Margin && P.Y >= B.Min.Y + Margin && P.Y <= B.Max.Y - Margin && P.Z >= B.Min.Z - 200.f)
		{
			if (OutSurfaceZ) *OutSurfaceZ = B.Max.Z;
			return true;
		}
	}
	return false;
}

bool ABirdFlock::PickWaterPoint(const FVector& From, float Range, float Inset, FRandomStream& Rng, FVector& Out) const
{
	float Best = 1e30f;
	bool bFound = false;
	for (int32 k = 0; k < 24; ++k)
	{
		const float A = Rng.FRandRange(0.f, 2.f * PI);
		const float D = Rng.FRandRange(300.f, Range);
		const FVector P = From + FVector(FMath::Cos(A) * D, FMath::Sin(A) * D, 0.f);
		float Z = 0.f;
		if (!IsWater(FVector(P.X, P.Y, From.Z), &Z, Inset)) continue;
		// shallow water near the shore is where kingfishers fish: prefer the closest candidate
		if (D < Best) { Best = D; Out = FVector(P.X, P.Y, Z); bFound = true; }
	}
	return bFound;
}

void ABirdFlock::RegisterFood(ABirdFish* Fish)
{
	if (Fish) Foods.AddUnique(Fish);
	IgnoreListHolder.AddUnique(Fish);
	IgnoreList.AddUnique(Fish);
}

ABirdFish* ABirdFlock::FindFood(const FVector& P, float Radius) const
{
	ABirdFish* Best = nullptr;
	float BestD = Radius * Radius;
	for (const TWeakObjectPtr<ABirdFish>& W : Foods)
	{
		ABirdFish* F = W.Get();
		if (!F || F->FishState != EBirdFishState::Remains || F->Claimant.IsValid()) continue;
		const float D = FVector::DistSquared(F->GetActorLocation(), P);
		if (D < BestD) { BestD = D; Best = F; }
	}
	return Best;
}

bool ABirdFlock::DefaultShouldBleed(const FBirdHitInfo& Hit) const
{
	return Hit.bLethal || Hit.bLethalObject || (Hit.Source == EBirdHitSource::Damage && Hit.Damage >= LethalDamage * 0.5f);
}

void ABirdFlock::SpawnBloodSplat(const FVector& At, const FVector& Dir, float ScaleMul)
{
	if (!bBloodSplat || ScaleMul <= 0.f) return;
	UNiagaraSystem* Sys = BloodSplatSystem.LoadSynchronous();
	if (!Sys) return;
	UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Sys, At, Dir.Rotation(), FVector(ScaleMul), true, true, ENCPoolMethod::AutoRelease);
}

void ABirdFlock::OnAnyActorSpawned(AActor* A)
{
	// tags / names are often set right after spawning: re-check for a second
	if (A && !Cast<ABird>(A)) Fresh.Add({ A, 0.f });
}

void ABirdFlock::EndPlay(const EEndPlayReason::Type Reason)
{
	if (SpawnHandle.IsValid() && GetWorld()) GetWorld()->RemoveOnActorSpawnedHandler(SpawnHandle);
	Super::EndPlay(Reason);
}

TArray<ABird*> ABirdFlock::GetBirds() const
{
	TArray<ABird*> Out;
	for (ABird* B : Birds) if (B) Out.Add(B);
	return Out;
}

void ABirdFlock::Register(ABird* Bird)
{
	if (!Bird) return;
	Birds.AddUnique(Bird);
	IgnoreListHolder.AddUnique(Bird);
	IgnoreList.AddUnique(Bird);
	GetPool(Bird->Settings().FeatherFXMaterial.LoadSynchronous());
}

void ABirdFlock::Unregister(ABird* Bird)
{
	Birds.Remove(Bird);
	IgnoreListHolder.Remove(Bird);
	IgnoreList.Remove(Bird);
}

void ABirdFlock::AddThreatActor(AActor* Actor)
{
	if (!Actor) return;
	for (const FThreat& T : Threats) if (T.Actor.Get() == Actor) return;
	FThreat& T = Threats.AddDefaulted_GetRef();
	T.Actor = Actor;
	ThreatActors.AddUnique(Actor);
}

void ABirdFlock::RemoveThreatActor(AActor* Actor)
{
	Threats.RemoveAll([Actor](const FThreat& T) { return T.Actor.Get() == Actor; });
	ThreatActors.Remove(Actor);
}

void ABirdFlock::AddLethalClass(TSubclassOf<AActor> Class)
{
	if (Class) LethalClasses.AddUnique(TSoftClassPtr<AActor>(Class.Get()));
	ClassFlags.Reset();
}

uint8 ABirdFlock::GetClassFlags(const UClass* C) const
{
	if (!C) return 0;
	if (const uint8* F = ClassFlags.Find(FObjectKey(C))) return *F;
	uint8 F = 0;
	for (const TSoftClassPtr<AActor>& L : LethalClasses) if (const UClass* Cl = L.Get()) if (C->IsChildOf(Cl)) { F |= 1; break; }
	if (!(F & 1))
	{
		const FString CN = C->GetName();
		for (const FString& S : LethalNameContains) if (!S.IsEmpty() && CN.Contains(S)) { F |= 1; break; }
	}
	for (const TSoftClassPtr<AActor>& T : ThreatClasses) if (const UClass* Cl = T.Get()) if (C->IsChildOf(Cl)) { F |= 2; break; }
	ClassFlags.Add(FObjectKey(C), F);
	return F;
}

bool ABirdFlock::IsLethal(const AActor* A) const
{
	if (!A || Cast<ABird>(A)) return false;
	if (LethalSet.Contains(FObjectKey(A))) return true;
	if (GetClassFlags(A->GetClass()) & 1) return true;		// class / class-name rules, cached per class
	for (const FName& Tag : LethalTags) if (A->ActorHasTag(Tag)) return true;
	if (LethalNameContains.Num())
	{
		TStringBuilder<256> N;		// object name without a heap allocation
		A->GetFName().AppendString(N);
		for (const FString& S : LethalNameContains)
		{
			if (!S.IsEmpty() && FCString::Stristr(N.ToString(), *S)) return true;
		}
	}
	return false;
}

void ABirdFlock::AddLethal(AActor* A)
{
	if (!A || LethalSet.Contains(FObjectKey(A))) return;
	LethalSet.Add(FObjectKey(A));
	Lethals.AddDefaulted_GetRef().Actor = A;
}

void ABirdFlock::ConsiderActor(AActor* A, bool bWaterCheck)
{
	if (A == this || Cast<ABird>(A) || Cast<ABirdFish>(A)) return;
	const FObjectKey K(A);
	const uint8 CF = GetClassFlags(A->GetClass());
	if (!LethalSet.Contains(K) && IsLethal(A)) AddLethal(A);
	bool bThreat = (CF & 2) != 0;
	if (!bThreat) for (const FName& T : ThreatTags) if (A->ActorHasTag(T)) { bThreat = true; break; }
	if (bThreat) AddThreatActor(A);
	if (bWaterCheck && bAutoDetectWater && !WaterChecked.Contains(K))
	{
		WaterChecked.Add(K);
		if (!WaterActors.Contains(A) && !IsWaterActor(A) && LooksLikeWater(A))
		{
			const FBox B = A->GetComponentsBoundingBox(true);
			if (B.IsValid) Waters.Add({ A, B });
		}
	}
}

void ABirdFlock::ScanSlice()
{
	UWorld* W = GetWorld();
	const TArray<ULevel*>& Levels = W->GetLevels();
	if (Levels.Num() == 0) return;
	int32 Budget = FMath::Max(ScanActorsPerFrame, 16);
	int32 Hops = Levels.Num() + 1;		// at most one full wrap per frame (empty levels)
	while (Budget > 0 && Hops > 0)
	{
		if (!Levels.IsValidIndex(ScanLevelIdx))
		{
			// one pass over the whole world finished
			const double Now = FPlatformTime::Seconds();
			Stats.ScanCycleSeconds = float(Now - ScanCycleStart);
			ScanCycleStart = Now;
			ScanLevelIdx = 0;
			ScanActorIdx = 0;
			--Hops;
			Lethals.RemoveAll([](const FLethal& L) { return !L.Actor.IsValid(); });
			LethalSet.Reset();
			for (const FLethal& L : Lethals) LethalSet.Add(FObjectKey(L.Actor.Get()));
			continue;
		}
		ULevel* L = Levels[ScanLevelIdx];
		if (!L || !L->bIsVisible || ScanActorIdx >= L->Actors.Num())
		{
			++ScanLevelIdx;
			ScanActorIdx = 0;
			--Hops;
			continue;
		}
		const int32 End = FMath::Min(L->Actors.Num(), ScanActorIdx + Budget);
		for (int32 i = ScanActorIdx; i < End; ++i)
		{
			AActor* A = L->Actors[i];
			if (IsValid(A)) ConsiderActor(A, true);
		}
		Budget -= End - ScanActorIdx;
		ScanActorIdx = End;
	}
}

bool ABirdFlock::IsSpotFree(const ABird* Self, const FVector& Foot, float Radius) const
{
	for (const ABird* O : Birds)
	{
		if (!O || O == Self || O->IsDead() || O->GetState() == EBirdState::Unplaced) continue;
		const float R = FMath::Max(Radius, O->Settings().HalfSpan * O->GetScale() * 0.75f + O->BodyR() * 1.1f + 3.f);
		if (O->HasReservedSpot() && FVector::DistSquared(O->GetReservedSpot(), Foot) < R * R) return false;
		if (!O->IsFlying() && FVector::DistSquared(O->GetFootSpot(), Foot) < R * R) return false;
	}
	return true;
}

void ABirdFlock::StartleNear(const FVector& At, float Radius, const ABird* Except)
{
	for (ABird* B : Birds)
	{
		if (!B || B == Except || B->IsDead()) continue;
		if (FVector::DistSquared(B->GetPos(), At) < Radius * Radius) B->Startle(At);
	}
}

// ---------------------------------------------------------------------------------------------------- threats
void ABirdFlock::GatherThreats(float Dt)
{
	ThreatScan -= Dt;
	if (ThreatScan <= 0.f)
	{
		ThreatScan = 1.f;
		// (tagged / class threats are found by the background scan)
		for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
		{
			if (bPlayerPawnsAreThreats && It->Get() && It->Get()->GetPawn()) AddThreatActor(It->Get()->GetPawn());
		}
	}
	for (int32 i = Threats.Num() - 1; i >= 0; --i)
	{
		FThreat& T = Threats[i];
		AActor* A = T.Actor.Get();
		if (!A) { Threats.RemoveAtSwap(i); continue; }
		T.PrevPos = T.Pos;
		T.Pos = A->GetActorLocation();
		if (!T.bInit) { T.PrevPos = T.Pos; T.bInit = true; }
		const FVector V = (T.Pos - T.PrevPos) / FMath::Max(Dt, 1e-3f);
		T.Vel = FMath::Lerp(T.Vel, V, FMath::Min(1.f, Dt * 8.f));
		T.Speed = T.Vel.Size();
	}
}

// ---------------------------------------------------------------------------------------------------- lethal objects
void ABirdFlock::ScanLethals()
{
	// full pass (BeginPlay); afterwards ScanSlice keeps re-covering the world a few hundred actors per frame
	for (TActorIterator<AActor> It(GetWorld()); It; ++It) if (IsValid(*It)) ConsiderActor(*It, false);
}

void ABirdFlock::UpdateLethals(float Dt)
{
	for (int32 i = Fresh.Num() - 1; i >= 0; --i)
	{
		AActor* A = Fresh[i].Key.Get();
		Fresh[i].Value += Dt;
		if (A && IsLethal(A))
		{
			AddLethal(A);
			Fresh.RemoveAtSwap(i);
		}
		else if (!A || Fresh[i].Value > 1.f) Fresh.RemoveAtSwap(i);
	}
	if (Birds.Num() == 0) return;
	for (FLethal& L : Lethals)
	{
		AActor* A = L.Actor.Get();
		if (!A) continue;
		// long axis of the biggest primitive = the shaft (tip / tail are its two ends); found once a second, not every frame
		UPrimitiveComponent* Best = L.Shape.Get();
		L.Refind -= Dt;
		if (!Best || L.Refind <= 0.f || !Best->IsRegistered() || !Best->IsVisible())
		{
			L.Refind = 1.f;
			Best = nullptr;
			float BigR = 0.f;
			A->ForEachComponent<UPrimitiveComponent>(false, [&](UPrimitiveComponent* C)
			{
				if (!C->IsRegistered() || !C->IsVisible()) return;
				const float R = C->Bounds.SphereRadius;
				if (R > BigR) { BigR = R; Best = C; }
			});
			L.Shape = Best;
			if (!Best) { L.bInit = false; continue; }
			const FBoxSphereBounds LB = Best->CalcBounds(FTransform::Identity);
			const FVector E = LB.BoxExtent;
			L.LocalOrigin = LB.Origin;
			L.LocalAxis = E.X >= E.Y && E.X >= E.Z ? FVector(E.X, 0, 0) : (E.Y >= E.Z ? FVector(0, E.Y, 0) : FVector(0, 0, E.Z));
			L.Radius = BigR;
		}
		const float BestR = L.Radius;
		const FTransform T = Best->GetComponentTransform();
		L.PrevTip = L.Tip;
		L.PrevTail = L.Tail;
		L.Tip = T.TransformPosition(L.LocalOrigin + L.LocalAxis);
		L.Tail = T.TransformPosition(L.LocalOrigin - L.LocalAxis);
		if (!L.bInit) { L.PrevTip = L.Tip; L.PrevTail = L.Tail; L.bInit = true; continue; }
		const FVector VTip = (L.Tip - L.PrevTip) / FMath::Max(Dt, 1e-3f);
		const FVector VTail = (L.Tail - L.PrevTail) / FMath::Max(Dt, 1e-3f);
		L.Vel = VTip.SizeSquared() > VTail.SizeSquared() ? VTip : VTail;
		const float Speed = L.Vel.Size();
		if (Speed < LethalMinSpeed) continue;
		for (ABird* B : Birds)
		{
			if (!B || B->IsDead() || B->GetState() == EBirdState::Unplaced) continue;
			const FVector C = B->GetPos();
			const float Reach = B->Settings().HalfSpan * B->GetScale() + Speed * Dt + BestR;
			if (FVector::DistSquared(C, L.Tip) > FMath::Square(Reach + BestR)) continue;
			// test points: body, and the two wings when flying
			FVector Pts[3] = { C, C, C };
			float Rad[3] = { B->BodyR() * 1.1f, 0.f, 0.f };
			int32 N = 1;
			if (B->IsFlying())
			{
				const FVector Right = B->GetActorRightVector();
				const float HS = B->Settings().HalfSpan * B->GetScale();
				Pts[1] = C + Right * HS * 0.55f; Rad[1] = HS * 0.3f;
				Pts[2] = C - Right * HS * 0.55f; Rad[2] = HS * 0.3f;
				N = 3;
			}
			const FVector Segs[3][2] = { { L.PrevTip, L.Tip }, { L.PrevTail, L.Tail }, { L.Tail, L.Tip } };
			for (int32 p = 0; p < N; ++p)
			{
				bool bHit = false;
				FVector HitAt = FVector::ZeroVector;
				for (const auto& Sg : Segs)
				{
					const FVector Q = FMath::ClosestPointOnSegment(Pts[p], Sg[0], Sg[1]);
					if (FVector::DistSquared(Q, Pts[p]) < Rad[p] * Rad[p]) { bHit = true; HitAt = Q; break; }
				}
				if (bHit)
				{
					const FName Bone = p == 0 ? NAME_None : FName(p == 1 ? TEXT("lowerarm_r") : TEXT("lowerarm_l"));
					FBirdHitInfo H;
					H.Source = EBirdHitSource::LethalObject;
					H.Object = A;
					H.Component = Best;
					H.Location = HitAt;
					H.Direction = (L.Vel - B->GetBirdVelocity()).GetSafeNormal();
					H.Speed = (L.Vel - B->GetBirdVelocity()).Size();
					H.Momentum = Best->IsSimulatingPhysics() ? Best->GetMass() * H.Speed : 0.f;
					H.ObjectForward = A->GetActorForwardVector();
					H.Bone = Bone;
					H.bLethalObject = true;
					H.Time = GetWorld()->GetTimeSeconds();
					B->SetHitContext(H);
					B->Kill(HitAt, L.Vel.GetSafeNormal() * FMath::Clamp(Speed * 0.35f, 300.f, 1600.f), A, Bone);
					break;
				}
			}
		}
	}
}

// ---------------------------------------------------------------------------------------------------- no-overlap rule
void ABirdFlock::EnforceSeparation(float FixedDt)
{
	// gather once (position, radius, speed, mobility), then the pair test is plain arithmetic; squared distances until a pair
	// actually overlaps
	struct FSep { ABird* B; FVector P; float R; float Speed; bool bMove; };
	TArray<FSep, TInlineAllocator<128>> L;
	for (ABird* B : Birds)
	{
		if (!B || B->IsDead() || B->GetState() == EBirdState::Unplaced) continue;
		L.Add({ B, B->GetPos(), B->SeparationRadius(), float(B->GetBirdVelocity().Size()), B->IsFlying() || B->GetState() == EBirdState::Walking });
	}
	auto Refresh = [](FSep& E) { E.P = E.B->GetPos(); E.R = E.B->SeparationRadius(); E.bMove = E.B->IsFlying() || E.B->GetState() == EBirdState::Walking; };
	float MinRatioSq = 99.f * 99.f;
	for (int32 i = 0; i < L.Num(); ++i)
	{
		for (int32 j = i + 1; j < L.Num(); ++j)
		{
			FSep& A = L[i];
			FSep& B = L[j];
			const float R = A.R + B.R;
			const FVector D = B.P - A.P;
			const float D2 = float(D.SizeSquared());
			MinRatioSq = FMath::Min(MinRatioSq, D2 / FMath::Max(R * R, 1.f));
			if (D2 >= R * R) continue;
			const float Dist = FMath::Sqrt(D2);
			FVector N = Dist > 1e-3f ? D / Dist : FVector::UpVector;
			const float Pen = FMath::Min(R - Dist + 0.5f, 3.f + FMath::Max(A.Speed, B.Speed) * FixedDt * 0.6f);
			if (A.bMove && B.bMove)
			{
				A.B->PushApart(-N * Pen * 0.5f, true);
				B.B->PushApart(N * Pen * 0.5f, true);
			}
			else if (A.bMove) A.B->PushApart(-N * Pen, true);
			else B.B->PushApart(N * Pen, true);
			Refresh(A);
			Refresh(B);
			++Stats.SeparationCorrections;
		}
	}
	Stats.MinSeparationRatio = FMath::Sqrt(MinRatioSq);
}

// ---------------------------------------------------------------------------------------------------- distance tiers
void ABirdFlock::GatherCameras()
{
	Cameras.Reset();
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		const APlayerController* PC = It->Get();
		if (PC && PC->PlayerCameraManager) Cameras.Add(PC->PlayerCameraManager->GetCameraLocation());
	}
}

float ABirdFlock::CameraDistSq(const FVector& P) const
{
	if (Cameras.Num() == 0) return 0.f;		// no local viewer (server): treat every bird as near
	float Best = TNumericLimits<float>::Max();
	for (const FVector& C : Cameras) Best = FMath::Min(Best, float(FVector::DistSquared(C, P)));
	return Best;
}

void ABirdFlock::UpdateTiers()
{
	// a slice of the birds per frame (each bird re-evaluated about every 8 frames), with hysteresis so nothing flickers
	const int32 N = Birds.Num();
	if (N == 0) return;
	const int32 Count = FMath::Min(N, N / 8 + 1);
	for (int32 k = 0; k < Count; ++k)
	{
		TierCursor = (TierCursor + 1) % N;
		ABird* B = Birds[TierCursor];
		if (!B || B->GetState() == EBirdState::Unplaced) continue;
		const float D2 = CameraDistSq(B->IsDead() && B->Mesh ? FVector(B->Mesh->Bounds.Origin) : B->GetPos());
		const bool bShadow = ShadowDistance <= 0.f || D2 < FMath::Square(ShadowDistance * (B->bShadowOn ? 1.1f : 1.f));
		if (bShadow != B->bShadowOn) B->SetShadowCasting(bShadow);
		B->bFar = FarDistance > 0.f && D2 > FMath::Square(FarDistance * (B->bFar ? 0.9f : 1.f));
		B->bMid = UpdateRateDistance > 0.f && D2 > FMath::Square(UpdateRateDistance * (B->bMid ? 0.9f : 1.f));
	}
}

// ---------------------------------------------------------------------------------------------------- ragdoll asset
UPhysicsAsset* ABirdFlock::GetRagdollAsset(USkeletalMesh* Mesh, const FBirdSpeciesSettings& S)
{
	if (!Mesh) return nullptr;
	if (TObjectPtr<UPhysicsAsset>* Found = Ragdolls.Find(Mesh)) return *Found;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	const TArray<FTransform>& Local = Ref.GetRefBonePose();
	TArray<FTransform> CS;
	CS.SetNum(Local.Num());
	for (int32 i = 0; i < Local.Num(); ++i)
	{
		const int32 P = Ref.GetParentIndex(i);
		CS[i] = P == INDEX_NONE ? Local[i] : Local[i] * CS[P];
	}
	auto Pos = [&](const TCHAR* Name, bool& bOk) -> FVector
	{
		const int32 I = Ref.FindBoneIndex(Name);
		if (I == INDEX_NONE) { bOk = false; return FVector::ZeroVector; }
		return CS[I].GetLocation();
	};
	const float H = S.BodyHeight;
	UPhysicsAsset* PA = NewObject<UPhysicsAsset>(this, NAME_None, RF_Transient);
	struct FDef { FString Bone, Parent; FVector A, B; float R; float Mass; float S1, S2, Tw; float LinDamp; bool bSphere; };
	TArray<FDef> Defs;
	bool bOk = true;
	const FVector Pelvis = Pos(TEXT("pelvis"), bOk), Spine2 = Pos(TEXT("spine_02"), bOk), Neck1 = Pos(TEXT("neck_01"), bOk), Head = Pos(TEXT("head"), bOk), Jaw = Pos(TEXT("jaw"), bOk), Tail = Pos(TEXT("tail"), bOk);
	if (!bOk)
	{
		UE_LOG(LogTemp, Warning, TEXT("Birds: %s lacks the expected bones (pelvis, spine_02, neck_01, head, jaw, tail) - no ragdoll"), *Mesh->GetName());
		Ragdolls.Add(Mesh, nullptr);
		return nullptr;
	}
	Defs.Add({ TEXT("pelvis"), TEXT(""), Pelvis + (Pelvis - Neck1) * 0.45f, Spine2, 0.38f * H, 0.60f, 0, 0, 0, 0.05f, false });
	if (Ref.FindBoneIndex(TEXT("neck_02")) != INDEX_NONE)
	{
		Defs.Add({ TEXT("neck_02"), TEXT("pelvis"), Neck1, Head, 0.19f * H, 0.05f, 45, 45, 30, 0.1f, false });
	}
	Defs.Add({ TEXT("head"), TEXT("neck_02"), Head + (Jaw - Head) * 0.45f, Head + (Jaw - Head) * 0.45f, 0.27f * H, 0.07f, 40, 40, 35, 0.1f, true });
	Defs.Add({ TEXT("tail"), TEXT("pelvis"), Tail, Tail + (Tail - Pelvis).GetSafeNormal() * 0.5f * H, 0.1f * H, 0.03f, 25, 25, 10, 0.3f, false });
	for (const TCHAR* Sd : { TEXT("l"), TEXT("r") })
	{
		bool bW = true;
		const FVector UA = Pos(*FString::Printf(TEXT("upperarm_%s"), Sd), bW), LA = Pos(*FString::Printf(TEXT("lowerarm_%s"), Sd), bW), HA = Pos(*FString::Printf(TEXT("hand_%s"), Sd), bW);
		if (bW)
		{
			Defs.Add({ FString::Printf(TEXT("upperarm_%s"), Sd), TEXT("pelvis"), UA, LA, 0.11f * H, 0.05f, 75, 75, 40, 0.6f, false });
			Defs.Add({ FString::Printf(TEXT("lowerarm_%s"), Sd), FString::Printf(TEXT("upperarm_%s"), Sd), LA, HA, 0.09f * H, 0.035f, 65, 65, 15, 0.8f, false });
			Defs.Add({ FString::Printf(TEXT("hand_%s"), Sd), FString::Printf(TEXT("lowerarm_%s"), Sd), HA, HA + (HA - LA) * 0.8f, 0.08f * H, 0.02f, 45, 45, 15, 1.0f, false });
		}
		bool bL = true;
		const FVector SH = Pos(*FString::Printf(TEXT("shin_%s"), Sd), bL), TA = Pos(*FString::Printf(TEXT("tarsus_%s"), Sd), bL), TO = Pos(*FString::Printf(TEXT("toes_%s"), Sd), bL);
		if (bL)
		{
			Defs.Add({ FString::Printf(TEXT("shin_%s"), Sd), TEXT("pelvis"), SH, TA, 0.06f * H, 0.015f, 50, 50, 10, 0.1f, false });
			Defs.Add({ FString::Printf(TEXT("tarsus_%s"), Sd), FString::Printf(TEXT("shin_%s"), Sd), TA, TO, 0.045f * H, 0.01f, 60, 60, 10, 0.1f, false });
		}
	}
	TMap<FString, int32> BodyIndex;
	for (const FDef& D : Defs)
	{
		const int32 BI = Ref.FindBoneIndex(*D.Bone);
		if (BI == INDEX_NONE) continue;
		USkeletalBodySetup* BS = NewObject<USkeletalBodySetup>(PA, NAME_None, RF_Transient);
		BS->BoneName = *D.Bone;
		BS->PhysicsType = PhysType_Default;
		BS->CollisionTraceFlag = CTF_UseSimpleAsComplex;
		const FTransform& B = CS[BI];
		const FVector Mid = (D.A + D.B) * 0.5f;
		if (D.bSphere)
		{
			FKSphereElem E(D.R);
			E.Center = B.InverseTransformPosition(Mid);
			BS->AggGeom.SphereElems.Add(E);
		}
		else
		{
			const FVector Seg = D.B - D.A;
			FKSphylElem E(D.R, FMath::Max(float(Seg.Size()) - D.R * 0.5f, 0.1f));
			E.Center = B.InverseTransformPosition(Mid);
			const FVector AxisL = B.InverseTransformVectorNoScale(Seg.GetSafeNormal());
			E.Rotation = FRotationMatrix::MakeFromZ(AxisL.IsNearlyZero() ? FVector::UpVector : AxisL).Rotator();
			BS->AggGeom.SphylElems.Add(E);
		}
		BS->DefaultInstance.SetMassOverride(FMath::Max(S.MassKg * D.Mass, 0.002f), true);
		BS->DefaultInstance.SetInstanceNotifyRBCollision(true);
		// continuous collision only on the torso and head (the bodies that carry the mass and must never tunnel through thin
		// ground); the jointed limbs follow them. CCD on all 14 bodies cost more than the rest of the ragdoll.
		BS->DefaultInstance.bUseCCD = D.Bone == TEXT("pelvis") || D.Bone == TEXT("head");
		// a corpse goes to sleep sooner (3x the normal threshold) instead of micro-jittering on the sand for seconds
		BS->DefaultInstance.SleepFamily = ESleepFamily::Custom;
		BS->DefaultInstance.CustomSleepThresholdMultiplier = 3.f;
		BS->DefaultInstance.LinearDamping = D.LinDamp;
		BS->DefaultInstance.AngularDamping = 0.6f;
		BS->CreatePhysicsMeshes();
		BodyIndex.Add(D.Bone, PA->SkeletalBodySetups.Add(BS));
	}
	PA->UpdateBodySetupIndexMap();
	PA->UpdateBoundsBodiesArray();
	for (const FDef& D : Defs)
	{
		if (D.Parent.IsEmpty() || !BodyIndex.Contains(D.Bone) || !BodyIndex.Contains(D.Parent)) continue;
		const int32 CI = Ref.FindBoneIndex(*D.Bone), ParentIdx = Ref.FindBoneIndex(*D.Parent);
		UPhysicsConstraintTemplate* CT = NewObject<UPhysicsConstraintTemplate>(PA, NAME_None, RF_Transient);
		FConstraintInstance& C = CT->DefaultInstance;
		C.JointName = *D.Bone;
		C.ConstraintBone1 = *D.Bone;
		C.ConstraintBone2 = *D.Parent;
		const FVector Dir = (D.B - D.A).IsNearlyZero() ? (CS[CI].GetLocation() - CS[ParentIdx].GetLocation()).GetSafeNormal() : (D.B - D.A).GetSafeNormal();
		const FTransform Joint(FRotationMatrix::MakeFromX(Dir).ToQuat(), CS[CI].GetLocation());
		C.SetRefFrame(EConstraintFrame::Frame1, Joint.GetRelativeTransform(CS[CI]));
		C.SetRefFrame(EConstraintFrame::Frame2, Joint.GetRelativeTransform(CS[ParentIdx]));
		C.SetLinearLimits(LCM_Locked, LCM_Locked, LCM_Locked, 0.f);
		C.SetAngularSwing1Limit(ACM_Limited, D.S1);
		C.SetAngularSwing2Limit(ACM_Limited, D.S2);
		C.SetAngularTwistLimit(ACM_Limited, D.Tw);
		C.SetDisableCollision(true);
		PA->ConstraintSetup.Add(CT);
		PA->DisableCollision(BodyIndex[D.Bone], BodyIndex[D.Parent]);
	}
	// wings / legs never collide with the torso they are folded against
	if (const int32* P = BodyIndex.Find(TEXT("pelvis")))
	{
		for (const auto& KV : BodyIndex) if (KV.Value != *P) PA->DisableCollision(*P, KV.Value);
	}
	Ragdolls.Add(Mesh, PA);
	UE_LOG(LogTemp, Display, TEXT("Birds: ragdoll for %s: %d bodies, %d constraints, %.3f kg"), *Mesh->GetName(), PA->SkeletalBodySetups.Num(), PA->ConstraintSetup.Num(), S.MassKg);
	return PA;
}

// ---------------------------------------------------------------------------------------------------- feathers
FBirdFeatherPool* ABirdFlock::GetPool(UMaterialInterface* Mat)
{
	if (!Mat) return nullptr;
	if (FBirdFeatherPool* P = Pools.Find(Mat)) return P;
	UStaticMesh* SM = LoadObject<UStaticMesh>(nullptr, FeatherMeshPath);
	if (!SM) return nullptr;
	UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(this);
	ISM->SetMobility(EComponentMobility::Movable);
	ISM->SetStaticMesh(SM);
	ISM->SetMaterial(0, Mat);
	ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	ISM->SetCanEverAffectNavigation(false);
	ISM->SetNumCustomDataFloats(8);
	ISM->bCastDynamicShadow = true;
	ISM->SetupAttachment(RootComponent);
	ISM->RegisterComponent();
	AddInstanceComponent(ISM);
	TArray<FTransform> Init;
	Init.Init(Hidden, PoolSize);
	ISM->AddInstances(Init, false, true, false);
	PoolComponents.Add(ISM);
	FBirdFeatherPool& Pool = Pools.Add(Mat);
	Pool.ISM = ISM;
	Pool.Feathers.SetNum(PoolSize);
	Pool.Xf.Init(Hidden, PoolSize);
	for (int32 i = PoolSize - 1; i >= 0; --i) Pool.Free.Add(i);
	return &Pool;
}

FVector ABirdFlock::WindAt(const FVector& P, float HeightAboveGround, float Time) const
{
	const float Speed = WindNow.Size();
	// log wind profile (sand roughness ~2 cm): 45 % of the 2 m speed at 10 cm, almost still at the surface
	constexpr float Z0 = 2.f;
	const float Prof = FMath::Clamp(FMath::Loge(1.f + FMath::Max(HeightAboveGround, 0.f) / Z0) / FMath::Loge(1.f + 200.f / Z0), 0.f, 1.25f);
	// turbulence: eddies a few metres across drifting with the wind, so feathers a metre apart already feel different gusts
	const FVector Q = (P - WindNow * Time) * 0.0021f;
	const float Gust = WindGustiness * FMath::Max(Speed, 40.f);
	const FVector Turb(
		FMath::Sin(Q.X * 1.0f + Q.Y * 0.6f + Time * 0.9f) + 0.5f * FMath::Sin(Q.Y * 2.3f - Q.Z * 1.1f + Time * 2.1f),
		FMath::Sin(Q.Y * 1.1f - Q.Z * 0.7f + Time * 0.7f + 1.7f) + 0.5f * FMath::Sin(Q.X * 2.1f + Q.Z * 1.3f + Time * 1.9f + 0.4f),
		0.6f * FMath::Sin(Q.Z * 1.2f + Q.X * 0.8f + Time * 1.3f + 2.9f) + 0.3f * FMath::Sin(Q.X * 2.7f - Q.Y * 1.9f + Time * 2.7f));
	return (WindNow + Turb * (Gust * 0.67f)) * Prof;
}

void ABirdFlock::SpawnFeathers(const ABird* Bird, const FVector& At, const FVector& Dir, int32 Count, float Energy, const FVector* BaseVel)
{
	if (!Bird || Count <= 0) return;
	const FBirdSpeciesSettings& S = Bird->Settings();
	FBirdFeatherPool* Pool = GetPool(S.FeatherFXMaterial.LoadSynchronous());
	if (!Pool) return;
	FRandomStream R(int32(GFrameCounter * 7919u + uint32(Count)));
	const FLinearColor Pc = Bird->bTintActive ? Bird->GetPrimary() : S.FeatherPrimary;
	const FLinearColor Sc = Bird->bTintActive ? Bird->GetSecondary() : S.FeatherSecondary;
	const float Tint = Bird->bTintActive ? 1.f : 0.f;
	const FVector BirdVel = BaseVel ? *BaseVel : Bird->GetBirdVelocity();
	const FVector D = Dir.IsNearlyZero() ? FVector::UpVector : Dir.GetSafeNormal();
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdFeather), false);
	Q.AddIgnoredActors(IgnoreList);
	for (int32 n = 0; n < Count && Pool->Free.Num(); ++n)
	{
		const int32 Slot = Pool->Free.Pop(EAllowShrinking::No);
		FBirdFeather& F = Pool->Feathers[Slot];
		F = FBirdFeather();
		F.Slot = Slot;
		F.bActive = true;
		const float K = R.FRand();
		const bool bDark = R.FRand() < S.DarkFeatherFraction;
		int32 Cell;
		const float Sz = S.FeatherSize * Bird->GetScale();
		if (K < 0.38f)			// down: tiny, floats for a long time
		{
			Cell = bDark ? CellDownDark : CellDownLight;
			F.Size = Sz * R.FRandRange(0.25f, 0.45f);
			F.Width = 1.5f;
			F.Vt = R.FRandRange(18.f, 32.f);
			F.Amp = R.FRandRange(6.f, 18.f);
		}
		else if (K < 0.86f)		// contour feathers
		{
			Cell = bDark ? CellContourDark : CellContourLight;
			F.Size = Sz * R.FRandRange(0.7f, 1.25f);
			F.Width = 1.05f;
			F.Vt = R.FRandRange(45.f, 75.f);
			F.Amp = R.FRandRange(15.f, 40.f);
		}
		else					// coverts
		{
			Cell = bDark ? CellCoverDark : CellCoverLight;
			F.Size = Sz * R.FRandRange(1.3f, 1.8f);
			F.Width = 1.15f;
			F.Vt = R.FRandRange(75.f, 120.f);
			F.Amp = R.FRandRange(20.f, 45.f);
		}
		// torn out along the struck part of the body (entry to exit), not from one point
		F.P = At + D * (R.FRandRange(-0.8f, 0.8f) * Bird->BodyR()) + R.VRand() * Bird->BodyR() * R.FRandRange(0.f, 0.5f);
		// most feathers just come loose, a few are carried off fast along the strike; all keep the bird's own velocity
		const FVector Cone = FMath::VRandCone(D, FMath::DegreesToRadians(50.f));
		F.V = (Cone * FMath::Lerp(80.f, 900.f, FMath::Pow(R.FRand(), 2.5f)) + R.VRand() * R.FRandRange(40.f, 200.f)) * Energy + BirdVel * 0.8f + FVector(0, 0, 40.f);
		F.Q = FQuat(R.VRand(), R.FRandRange(0.f, PI * 2.f));
		F.W = R.VRand() * R.FRandRange(6.f, 24.f);
		// asymmetric vanes: every feather glides a little to one side as it rocks down (falling-leaf drift)
		F.TiltBias = R.FRandRange(4.f, 14.f) * (R.FRand() < 0.5f ? -1.f : 1.f);
		F.TiltAmp = R.FRandRange(22.f, 40.f);
		F.Freq = R.FRandRange(1.1f, 2.4f);
		F.Phase = R.FRandRange(0.f, PI * 2.f);
		F.Spin = R.FRandRange(-60.f, 60.f);
		F.SwayDir = FRotator(0, R.FRandRange(0.f, 360.f), 0).Vector();
		F.Life = R.FRandRange(25.f, 60.f);
		F.GroundCheck = 0.f;
		const float Data[8] = { float(Cell), Pc.R, Pc.G, Pc.B, Sc.R, Sc.G, Sc.B, Tint };
		Pool->ISM->SetCustomData(Slot, TArrayView<const float>(Data, 8), false);	// render state is dirtied by the transform update this frame
		++Pool->Active;
		Pool->bDirty = true;
	}
}

void ABirdFlock::UpdateFeathers(float Dt)
{
	const float Time = GetWorld()->GetTimeSeconds();
	WindCheck -= Dt;
	if (WindCheck <= 0.f)
	{
		WindCheck = 1.f;
		WindNow = Wind;
		if (bUseLevelWindDirection && GetWorld()->Scene)
		{
			FVector WDir = FVector::ZeroVector;
			float WSpeed = 0.f, WMin = 0.f, WMax = 0.f;
			GetWorld()->Scene->GetWindParameters_GameThread(GetActorLocation(), WDir, WSpeed, WMin, WMax);
			const FVector Hd(WDir.X, WDir.Y, 0.f);
			if (WSpeed > 0.f && !Hd.IsNearlyZero()) WindNow = Hd.GetSafeNormal() * Wind.Size();
		}
	}
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdFeatherGround), false);
	Q.AddIgnoredActors(IgnoreList);
	int32 Total = 0;
	for (auto& KV : Pools)
	{
		FBirdFeatherPool& Pool = KV.Value;
		if (Pool.Active == 0 && !Pool.bDirty) continue;
		// only instances that changed this frame are sent to the renderer (landed feathers lie still for most of their life)
		int32 Lo = MAX_int32, Hi = -1;
		TArray<FTransform>& Xf = Pool.Xf;
		auto Put = [&](int32 Slot, const FTransform& T) { Xf[Slot] = T; Lo = FMath::Min(Lo, Slot); Hi = FMath::Max(Hi, Slot); };
		for (int32 Fi = 0; Fi < Pool.Feathers.Num(); ++Fi)
		{
			FBirdFeather& F = Pool.Feathers[Fi];
			if (!F.bActive) continue;
			F.Age += Dt;
			float Shrink = 1.f;
			if (F.Age > F.Life)
			{
				Shrink = 1.f - (F.Age - F.Life) / 1.5f;
				if (Shrink <= 0.f)
				{
					F.bActive = false;
					Pool.Free.Add(F.Slot);
					--Pool.Active;
					Put(F.Slot, Hidden);
					continue;
				}
			}
			const bool bWasLanded = F.bLanded;
			if (!F.bLanded)
			{
				F.GroundCheck -= Dt;
				if (F.GroundCheck <= 0.f)
				{
					F.GroundCheck = 0.35f;
					FHitResult H;
					if (GetWorld()->LineTraceSingleByChannel(H, F.P + FVector(0, 0, 5.f), F.P - FVector(0, 0, 5000.f), ECC_Visibility, Q))
					{
						F.GroundZ = H.ImpactPoint.Z;
						F.GroundN = H.ImpactNormal;
					}
					else F.GroundZ = F.P.Z - 5000.f;
				}
				// a feather is a flat plate: high drag across its vane, little along it (implicit per component, relative to the
				// moving air). A tilted plate therefore slides along its own plane - the side-glide of a falling feather.
				const FVector Air = WindAt(F.P, F.P.Z - F.GroundZ, Time);
				const FVector N = F.Q.GetAxisZ();
				FVector Vr = F.V + FVector(0, 0, -980.f) * Dt - Air;
				const float Kn = 980.f / (F.Vt * F.Vt);
				const float Sp = Vr.Size();
				const FVector Vn = N * FVector::DotProduct(Vr, N);
				Vr = Vn / (1.f + Kn * Sp * Dt) + (Vr - Vn) / (1.f + Kn * 0.15f * Sp * Dt);
				F.V = Air + Vr;
				F.P += F.V * Dt;
				// orientation: tumble, then aerodynamic torque turns it flat into a rocking, slightly lopsided descent
				const float Wl = 1.f - FMath::Clamp(Vr.Size() / (3.f * F.Vt), 0.f, 1.f);
				const float Ph = F.Phase + 2.f * PI * F.Freq * F.Age;
				F.W *= FMath::Exp(-2.2f * Dt);
				if (!F.W.IsNearlyZero()) F.Q = (FQuat(F.W.GetSafeNormal(), F.W.Size() * Dt) * F.Q).GetNormalized();
				const FVector TiltAxis = FVector::CrossProduct(FVector::UpVector, F.SwayDir).GetSafeNormal();
				const FQuat Leaf = FQuat(TiltAxis, FMath::DegreesToRadians(F.TiltBias + F.TiltAmp * FMath::Sin(Ph))) * FQuat(FVector::UpVector, FMath::DegreesToRadians(F.Spin * F.Age));
				F.Q = FQuat::Slerp(F.Q, Leaf, FMath::Min(1.f, Dt * (1.2f + 3.f * Wl))).GetNormalized();
				if (F.P.Z <= F.GroundZ + 0.25f)
				{
					F.P.Z = F.GroundZ + 0.25f;
					F.bLanded = true;
					const FQuat Yaw(FVector::UpVector, FMath::DegreesToRadians(F.Spin * F.Age));
					F.Q = (FQuat::FindBetweenNormals(FVector::UpVector, F.GroundN) * Yaw).GetNormalized();
				}
			}
			if (!bWasLanded || Shrink < 1.f) Put(F.Slot, FTransform(F.Q, F.P, FVector(F.Size, F.Size * F.Width, F.Size) * Shrink));
		}
		Total += Pool.Active;
		if (Hi >= Lo)
		{
			Pool.ISM->BatchUpdateInstancesTransforms(Lo, TArrayView<const FTransform>(Xf.GetData() + Lo, Hi - Lo + 1), true, true, false);
		}
		Pool.bDirty = false;
	}
	Stats.Feathers = Total;
}

// ---------------------------------------------------------------------------------------------------- tick
void ABirdFlock::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bEnabled || CVarBirdsEnable.GetValueOnGameThread() == 0) return;
	const double T0 = FPlatformTime::Seconds();
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	Birds.RemoveAll([](const TObjectPtr<ABird>& B) { return !IsValid(B); });
	IgnoreList.RemoveAll([](AActor* A) { return !IsValid(A); });
	IgnoreListHolder.RemoveAll([](const TObjectPtr<AActor>& A) { return !IsValid(A); });
	Foods.RemoveAll([](const TWeakObjectPtr<ABirdFish>& F) { return !F.IsValid(); });
	double Tp = T0;
	auto Lap = [&](int32 Part) { const double N = FPlatformTime::Seconds(); PartMs[Part] += (N - Tp) * 1000.0; Tp = N; };
	GatherCameras();
	ScanSlice();		// lethal / threat / streamed-in water discovery, a slice of the world per frame
	GatherThreats(Dt);
	UpdateLethals(Dt);
	UpdateTiers();
	Lap(5);
	// idle perched birds far from every camera think every Nth frame (staggered by index) with the summed time step
	const int32 Interval = FMath::Clamp(FarTickInterval, 1, 8);
	int32 FarN = 0;
	for (int32 i = 0; i < Birds.Num(); ++i)
	{
		ABird* B = Birds[i];
		float Step = Dt;
		if (Interval > 1 && B->bFar && B->CanThinkSlowly())
		{
			++FarN;
			B->FarDt += Dt;
			if (int32((GFrameCounter + uint64(i)) % uint64(Interval)) != 0) continue;
			Step = B->FarDt;
		}
		else if (B->FarDt > 0.f && B->GetState() == EBirdState::Perched) Step = B->FarDt + Dt;	// back from the far tier while still perched: catch up the skipped time (never folded into a flight step)
		B->FarDt = 0.f;
		B->Simulate(FMath::Min(Step, 0.25f));
	}
	Lap(0);
	for (ABird* B : Birds) B->ProbeImpacts(Dt);
	Lap(1);
	EnforceSeparation(Dt);
	Lap(2);
	for (ABird* B : Birds) B->PushVisuals(Dt);
	Lap(3);
	UpdateFeathers(Dt);
	Lap(4);

	const double Ms = (FPlatformTime::Seconds() - T0) * 1000.0;
	TickMsSum += Ms;
	++TickSamples;
	Stats.MaxTickMs = FMath::Max(Stats.MaxTickMs, float(Ms));
	StatsWindow += DeltaSeconds;
	if (StatsWindow >= 1.f)
	{
		Stats.AvgTickMs = float(TickMsSum / FMath::Max(TickSamples, 1));
		float* Parts[6] = { &Stats.SimulateMs, &Stats.ProbeMs, &Stats.SeparationMs, &Stats.VisualsMs, &Stats.FeathersMs, &Stats.ScansMs };
		for (int32 i = 0; i < 6; ++i) { *Parts[i] = float(PartMs[i] / FMath::Max(TickSamples, 1)); PartMs[i] = 0.0; }
		TickMsSum = 0.0;
		TickSamples = 0;
		StatsWindow = 0.f;
		Stats.Birds = Stats.Perched = Stats.Walking = Stats.Flying = Stats.Dead = 0;
		Stats.FarBirds = FarN;
		Stats.ShadowCasters = 0;
		for (const ABird* B : Birds) if (B && B->bShadowOn) ++Stats.ShadowCasters;
		Stats.Takeoffs = Stats.Landings = Stats.Walks = Stats.Cries = Stats.Scrapes = Stats.AbortedLandings = Stats.Turns = Stats.Shuffles = Stats.Bleeds = 0;
		for (const ABird* B : Birds)
		{
			++Stats.Birds;
			switch (B->GetState())
			{
			case EBirdState::Perched: ++Stats.Perched; break;
			case EBirdState::Walking: ++Stats.Walking; break;
			case EBirdState::Dead: ++Stats.Dead; break;
			case EBirdState::Unplaced: break;
			default: ++Stats.Flying; break;
			}
			Stats.Takeoffs += B->Takeoffs;
			Stats.Landings += B->Landings;
			Stats.Walks += B->Walks;
			Stats.Cries += B->Cries;
			Stats.Scrapes += B->Scrapes;
			Stats.AbortedLandings += B->AbortedLandings;
			Stats.Turns += B->Turns;
			Stats.Shuffles += B->Shuffles;
			Stats.Bleeds += B->Bleeds;
		}
	}
}
