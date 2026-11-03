#include "BirdTestDirector.h"
#include "LeafFall.h"
#include "GlobalWind.h"
#include "EngineUtils.h"
#include "Camera/CameraActor.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Misc/App.h"
#include "RenderCore.h"

// -BirdTest=leaves : a small hornbeam grove (tree1 / tree2) in low autumn sun; wide shot, one leaf of each flight style
// followed by the camera, slow motion, the ground (landing -> 7 s -> 1.5 s fade -> gone), a load window. LEAFTEST lines.

FString ABirdTestDirector::LeafStatsJson() const
{
	if (!LeafFall) return TEXT("{}");
	const FLeafFallStats S = LeafFall->GetStats();
	FString By;
	for (int32 i = 0; i < S.ByFlight.Num(); ++i) By += FString::Printf(TEXT("%s%d"), i ? TEXT(",") : TEXT(""), S.ByFlight[i]);
	return FString::Printf(TEXT("{\"trees\":%d,\"in_range\":%d,\"falling\":%d,\"resting\":%d,\"spawned\":%d,\"landed\":%d,\"removed\":%d,\"sliding\":%d,\"liftoffs\":%d,\"by_flight\":[%s],\"avg_ms\":%.4f,\"max_ms\":%.3f}"),
		S.Trees, S.TreesInRange, S.Falling, S.Resting, S.Spawned, S.Landed, S.Removed, S.Sliding, S.LiftOffs, *By, S.AvgTickMs, S.MaxTickMs);
}

void ABirdTestDirector::AddLeafShowcase(int32 Flight, int32 Cond, int32 Shape, float Seconds, float Dilation)
{
	static const TCHAR* Names[6] = { TEXT("flutter"), TEXT("chaotic"), TEXT("tumble"), TEXT("roll"), TEXT("spiral"), TEXT("rock") };
	AddCall([this, Flight, Cond, Shape, Dilation]()
	{
		// an open spot beside the chosen tree, 6.5 m up
		const FVector Side = FVector(-LeafDir.Y, LeafDir.X, 0.f);
		const FVector At = GroundAt(LeafAnchor + LeafDir * 900.f + Side * 500.f) + FVector(0, 0, 650.f);
		LeafIdx = LeafFall ? LeafFall->SpawnLeafWith(At, ELeafCondition(Cond), Shape, Flight) : -1;
		LeafStart = LeafPrev = At; LeafHoriz = 0.f; LeafT = 0.f; LeafSamples = 0; LeafLandedAt = -1.f;
		bCamInit = false;
		if (Dilation != 1.f) UGameplayStatics::SetGlobalTimeDilation(this, Dilation);
	});
	AddRecord(Seconds, [this](float T, float Dt)
	{
		const FLeafSim* L = LeafFall ? LeafFall->GetLeaf(LeafIdx) : nullptr;
		if (!L) return;
		const float GDt = Dt;		// the director's delta is game time (already dilated)
		if (!L->bLanded)
		{
			LeafHoriz += FVector::Dist2D(L->P, LeafPrev);
			LeafT += GDt;
			++LeafSamples;
		}
		else if (LeafLandedAt < 0.f) LeafLandedAt = LeafT;
		LeafPrev = L->P;
		// follow from 80 cm, a little above, keeping the leaf left of centre
		const FVector Goal = L->P + FVector(-75.f, -45.f, 18.f);
		SmoothCam(Goal, L->P, 42.f, Dt, 5.f);
	});
	AddCall([this, Flight]()
	{
		UGameplayStatics::SetGlobalTimeDilation(this, 1.f);
		const FLeafSim* L = LeafFall ? LeafFall->GetLeaf(LeafIdx) : nullptr;
		if (!L) { Log(FString::Printf(TEXT("leafstyle %s: leaf gone"), Names[Flight])); return; }
		const float Drop = (LeafStart.Z - L->P.Z) / 100.f;
		Log(FString::Printf(TEXT("leafstyle %s cond=%d shape=%d flight=%d len=%.1fcm I*=%.2f curl=%.2f twist=%.2f wet=%.2f vz=%.2f m/s horiz=%.2f m/s drift=%.2f m landed=%d"),
			Names[Flight], int32(L->Condition), int32(L->Shape), int32(L->Flight), L->Len * 100.f, L->IStar, L->Curl, L->Twist, L->Wet,
			Drop / FMath::Max(LeafT, 0.01f), LeafHoriz / 100.f / FMath::Max(LeafT, 0.01f), FVector::Dist2D(L->P, LeafStart) / 100.f, L->bLanded ? 1 : 0));
	});
}

FVector ABirdTestDirector::GroundAt(const FVector& P) const
{
	FHitResult H;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(LeafTestGround), false);
	if (LeafFall) Q.AddIgnoredActor(LeafFall);
	if (GetWorld()->LineTraceSingleByChannel(H, P + FVector(0, 0, 3000), P - FVector(0, 0, 5000), ECC_Visibility, Q)) return H.ImpactPoint;
	return FVector(P.X, P.Y, 0.f);
}

void ABirdTestDirector::PickLeafTree()
{
	if (!LeafFall || LeafFall->NumTrees() == 0) { Log(TEXT("no trees found")); return; }
	// the tree closest to the player start / pawn, from the side with open, level ground
	FVector Ref = FVector::ZeroVector;
	if (APlayerController* PC = GetWorld()->GetFirstPlayerController()) if (PC->GetPawn()) Ref = PC->GetPawn()->GetActorLocation();
	int32 Best = 0; float BestD = 1e30f;
	for (int32 i = 0; i < LeafFall->NumTrees(); ++i)
	{
		const float D = FVector::DistSquared2D(LeafFall->TreeBase(i), Ref);
		if (D < BestD) { BestD = D; Best = i; }
	}
	LeafAnchor = GroundAt(LeafFall->TreeBase(Best));
	LeafCanopy = LeafFall->TreeCanopyCentre(Best);
	float BestScore = -1e30f;
	for (int32 k = 0; k < 12; ++k)
	{
		const FVector D = FRotator(0.f, k * 30.f, 0.f).Vector();
		const FVector G = GroundAt(LeafAnchor + D * 900.f);
		FHitResult H;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(LeafTestView), false);
		const bool bBlocked = GetWorld()->LineTraceSingleByChannel(H, G + FVector(0, 0, 160), LeafAnchor + FVector(0, 0, 300), ECC_Visibility, Q) && H.Distance < 700.f;
		const float Score = -FMath::Abs(G.Z - LeafAnchor.Z) - (bBlocked ? 1000.f : 0.f);
		if (Score > BestScore) { BestScore = Score; LeafDir = D; }
	}
	Log(FString::Printf(TEXT("tree %d of %d at %s, canopy %s, view dir %s"), Best, LeafFall->NumTrees(), *LeafAnchor.ToCompactString(), *LeafCanopy.ToCompactString(), *LeafDir.ToCompactString()));
}

void ABirdTestDirector::BuildLeafScene()
{
	const bool bMap = Scene == TEXT("leavesmap");
	FApp::SetUseFixedTimeStep(true);
	FApp::SetFixedDeltaTime(1.0 / 60.0);
	if (!bMap)
	{
		SpawnLighting();
		// low autumn afternoon sun, warm
		for (TActorIterator<ADirectionalLight> It(GetWorld()); It; ++It)
		{
			It->SetActorRotation(FRotator(-17.f, 160.f, 0.f));
			It->GetLightComponent()->SetLightColor(FLinearColor(1.f, 0.82f, 0.6f));
			It->GetLightComponent()->SetIntensity(7.f);
		}
		SpawnBox(FVector(0, 0, -5), FVector(20000, 20000, 10), FLinearColor(0.035f, 0.028f, 0.02f));		// forest floor
		SpawnBox(FVector(2300, -400, 25), FVector(140, 90, 50), FLinearColor(0.3f, 0.29f, 0.27f));		// a rock
		UStaticMesh* T1 = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/_mygame/pcg/tree1.tree1"));
		UStaticMesh* T2 = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/_mygame/pcg/tree2.tree2"));
		struct FT { UStaticMesh* M; FVector P; float Yaw; float S; };
		const FT Grove[] = { { T1, FVector(0, 0, 0), 0.f, 1.f }, { T2, FVector(1100, 700, 0), 80.f, 1.05f }, { T1, FVector(-900, 1300, 0), 200.f, 0.9f },
			{ T2, FVector(-500, -1300, 0), 140.f, 1.f }, { T1, FVector(1500, -2300, 0), 290.f, 1.1f }, { T2, FVector(3800, 600, 0), 30.f, 0.95f } };
		for (const FT& G : Grove)
		{
			if (!G.M) continue;
			const FTransform T(FRotator(0, G.Yaw, 0), G.P, FVector(G.S));
			AStaticMeshActor* A = GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(), T);
			A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Static);
			A->GetStaticMeshComponent()->SetStaticMesh(G.M);
			A->FinishSpawning(T);
		}
	}
	LeafFall = ALeafFall::Find(this, true);
	LeafFall->RescanTrees();
	LeafFall->LeavesPerTreePerMinute = 30.f;		// a film needs more than the in-game 5 / tree / minute
	AddWaitShaders(bMap ? 25.f : 10.f);			// (the map's PCG forest generates meanwhile)
	AddCall([this]() { LeafFall->RescanTrees(); PickLeafTree(); Log(TEXT("start ") + LeafStatsJson()); SetCam(GroundAt(LeafAnchor + LeafDir * 1300.f) + FVector(0, 0, 170), LeafCanopy, 55.f); });
	if (Scene == TEXT("wind")) { AddWindShots(); return; }
	AddWait(12.f);
	AddCall([this]() { Log(TEXT("warm ") + LeafStatsJson()); });
	// 1. under the tree, looking up into the canopy, leaves drifting down past the camera
	AddRecord(9.f, [this](float T, float Dt)
	{
		const FVector D = LeafDir.RotateAngleAxis(-12.f + T * 2.f, FVector::UpVector);
		SetCam(GroundAt(LeafAnchor + D * 1150.f) + FVector(0, 0, 165.f + T * 5.f), FMath::Lerp(LeafCanopy, LeafAnchor + FVector(0, 0, 250), 0.45f + T * 0.02f), 60.f);
	});
	AddCall([this]() { Log(TEXT("wide ") + LeafStatsJson()); });
	// 2. one leaf of each flight style, followed (condition / shape forced only to film each style once)
	AddLeafShowcase(int32(ELeafFlight::Flutter), int32(ELeafCondition::Fresh), int32(ELeafShape::Flat), 5.f);
	AddLeafShowcase(int32(ELeafFlight::Chaotic), int32(ELeafCondition::Dry), int32(ELeafShape::Wavy), 5.f);
	AddLeafShowcase(int32(ELeafFlight::Tumble), int32(ELeafCondition::Dry), int32(ELeafShape::Wavy), 4.f);
	AddLeafShowcase(int32(ELeafFlight::Roll), int32(ELeafCondition::Dry), int32(ELeafShape::Rolled), 4.f);
	AddLeafShowcase(int32(ELeafFlight::Spiral), int32(ELeafCondition::Dry), int32(ELeafShape::Twisted), 5.f);
	AddLeafShowcase(int32(ELeafFlight::Rock), int32(ELeafCondition::Wet), int32(ELeafShape::Wet), 4.f);
	// 3. slow motion (1/4): a flutter and a tumble
	AddLeafShowcase(int32(ELeafFlight::Flutter), int32(ELeafCondition::Fresh), int32(ELeafShape::Flat), 6.f, 0.25f);
	AddLeafShowcase(int32(ELeafFlight::Tumble), int32(ELeafCondition::Dry), int32(ELeafShape::Cupped), 5.f, 0.25f);
	// 4. the ground under the tree: leaves land, lie RestTime, fade over FadeTime, disappear (one is timed)
	AddCall([this]()
	{
		bCamInit = false;
		const FVector Spot = GroundAt(LeafAnchor + LeafDir * 260.f);
		SetCam(GroundAt(LeafAnchor + LeafDir * 560.f) + FVector(0, 0, 120), Spot, 50.f);
		FadeIdx = LeafFall ? LeafFall->SpawnLeafWith(Spot + FVector(0, 0, 280), ELeafCondition::Fresh, int32(ELeafShape::Flat), int32(ELeafFlight::Flutter)) : -1;
		FadeLanded = -1.f;
		LeafT = 0.f;
	});
	AddRecord(14.f, [this](float T, float Dt)
	{
		LeafT = T;
		const FLeafSim* L = LeafFall ? LeafFall->GetLeaf(FadeIdx) : nullptr;
		if (L && L->bLanded && FadeLanded < 0.f) { FadeLanded = T; Log(FString::Printf(TEXT("fade_test landed at %.2f s"), T)); }
		if (!L && FadeLanded >= 0.f && FadeIdx >= 0) { Log(FString::Printf(TEXT("fade_test removed %.2f s after landing"), T - FadeLanded)); FadeIdx = -1; }
	});
	AddCall([this]() { Log(TEXT("ground ") + LeafStatsJson()); });
	// 5. load: up to MaxLeaves in the air at once
	AddCall([this]() { LeafFall->LeavesPerTreePerMinute = 900.f; });
	AddWait(8.f);
	AddCall([this]() { FrameMsSum = GameMsSum = 0.0; FrameSamples = 0; });
	Steps.Add([this](float Dt)
	{
		GameMsSum += FPlatformTime::ToMilliseconds(GGameThreadTime);
		++FrameSamples;
		if (StepTime < 8.f) return false;
		Log(FString::Printf(TEXT("load game_ms=%.3f %s"), GameMsSum / FMath::Max(FrameSamples, 1), *LeafStatsJson()));
		return true;
	});
}

// a meadow of the forest's own Megascans grass (the same materials as the PCG forest, so the same wind overlay)
void ABirdTestDirector::SpawnWindGrass(const FVector& Centre, const FVector& Carpet, const FVector& Dir)
{
	struct FG { const TCHAR* Path; float Weight; bool bShort; };
	static const FG Kinds[] = {
		{ TEXT("/Game/Fab/Megascans/Plants/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/StaticMeshes/tallwildgrass.tallwildgrass"), 3.f, false },
		{ TEXT("/Game/Fab/Megascans/Plants/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/StaticMeshes/wildgrass4.wildgrass4"), 2.f, false },
		{ TEXT("/Game/Fab/Megascans/Plants/Thatching_Grass_uddmcgbia/Medium/uddmcgbia_tier_2/StaticMeshes/wildgrass_bis.wildgrass_bis"), 1.6f, false },
		{ TEXT("/Game/Fab/Megascans/Plants/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/StaticMeshes/wildgrass2.wildgrass2"), 2.f, true },
		{ TEXT("/Game/Fab/Megascans/Plants/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/StaticMeshes/wildgrass3.wildgrass3"), 2.f, true },
		{ TEXT("/Game/Fab/Megascans/Plants/Wild_Grass_vlkhcbxia/High/vlkhcbxia_tier_1/StaticMeshes/wildgrass8.wildgrass8"), 1.5f, true },
		{ TEXT("/Game/Fab/Megascans/Plants/Violet_Wood_Sorrel_uchkajuia/Medium/uchkajuia_tier_2/StaticMeshes/SM_uchkajuia_VarG.SM_uchkajuia_VarG"), 0.7f, true } };
	constexpr int32 NK = UE_ARRAY_COUNT(Kinds);
	AActor* Holder = GetWorld()->SpawnActor<AActor>();
	USceneComponent* Root = NewObject<USceneComponent>(Holder, TEXT("Root"));
	Holder->SetRootComponent(Root);
	Root->RegisterComponent();
	UStaticMesh* Meshes[NK] = {};
	TArray<FTransform> Xf[NK];
	float WSum = 0.f, WShort = 0.f;
	for (int32 k = 0; k < NK; ++k)
	{
		Meshes[k] = LoadObject<UStaticMesh>(nullptr, Kinds[k].Path);
		if (!Meshes[k]) { Log(FString::Printf(TEXT("grass mesh missing %s"), Kinds[k].Path)); continue; }
		WSum += Kinds[k].Weight;
		if (Kinds[k].bShort) WShort += Kinds[k].Weight;
	}
	if (WSum <= 0.f) return;
	const FVector Side(-Dir.Y, Dir.X, 0.f);
	const FVector Cam0 = LeafAnchor + Dir * 120.f, Cam1 = LeafAnchor + Dir * 330.f;
	FRandomStream R(11);
	int32 Total = 0;
	for (int32 i = 0; i < 36000; ++i)
	{
		const float Rad = 3000.f * FMath::Sqrt(R.FRand());
		const float Ang = R.FRandRange(0.f, 2.f * PI);
		const FVector P = Centre + FVector(FMath::Cos(Ang), FMath::Sin(Ang), 0.f) * Rad;
		const FVector L = P - Carpet;
		const bool bCarpet = FMath::Abs(FVector::DotProduct(L, Dir)) < 700.f && FMath::Abs(FVector::DotProduct(L, Side)) < 700.f;
		if (bCarpet && R.FRand() > 0.22f) continue;		// the leaf carpet: only a few short tufts
		if (FVector::Dist2D(P, Cam0) < 300.f || FVector::Dist2D(P, Cam1) < 180.f) continue;
		bool bTrunk = false;
		for (int32 t = 0; t < LeafFall->NumTrees() && !bTrunk; ++t) bTrunk = FVector::Dist2D(P, LeafFall->TreeBase(t)) < 110.f;
		if (bTrunk) continue;
		float Pick = R.FRand() * (bCarpet ? WShort : WSum);
		int32 K = -1;
		for (int32 k = 0; k < NK; ++k)
		{
			if (!Meshes[k] || (bCarpet && !Kinds[k].bShort)) continue;
			K = k;
			if ((Pick -= Kinds[k].Weight) <= 0.f) break;
		}
		if (K < 0) continue;
		const FRotator Rot(R.FRandRange(-5.f, 5.f), R.FRandRange(0.f, 360.f), R.FRandRange(-5.f, 5.f));
		Xf[K].Add(FTransform(Rot, GroundAt(P) - FVector(0, 0, 2.f), FVector(R.FRandRange(0.9f, 1.5f))));
		++Total;
	}
	for (int32 k = 0; k < NK; ++k)
	{
		if (!Meshes[k] || Xf[k].Num() == 0) continue;
		UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(Holder);
		C->SetMobility(EComponentMobility::Static);
		C->SetStaticMesh(Meshes[k]);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCanEverAffectNavigation(false);
		C->SetCullDistances(0, 9000);
		C->SetupAttachment(Root);
		C->RegisterComponent();
		C->AddInstances(Xf[k], false, true);
	}
	Log(FString::Printf(TEXT("grass %d instances, %d kinds"), Total, NK));
}

void ABirdTestDirector::SpawnCarpet(const FVector& C, float Half, int32 N, int32 Seed)
{
	FRandomStream R(Seed);
	for (int32 i = 0; i < N; ++i)
	{
		const FVector P = C + FVector(R.FRandRange(-Half, Half), R.FRandRange(-Half, Half), 0.f);
		LeafFall->SpawnLeafAt(GroundAt(P) + FVector(0, 0, R.FRandRange(4.f, 30.f)), ELeafCondition::Dry, true);
	}
}

// -BirdTest=wind : bursts over a meadow and a carpet of fallen leaves and through the grove (grass waves, trees bending,
// leaves pushed, cartwheeling, lifted off, torn off the canopy), cost of the wind tick. WIND lines.
void ABirdTestDirector::AddWindShots()
{
	auto WindJson = [this]()
	{
		const float I = WindActor ? WindActor->GetGustIntensityAt(GroundAt(LeafAnchor + LeafDir * 600.f)) : 0.f;
		return FString::Printf(TEXT("{\"gusts\":%d,\"intensity_carpet\":%.2f,\"wind_ms\":%.4f,\"field_draws\":%d,\"leaves\":%s}"), WindActor ? WindActor->GetGusts().Num() : -1, I,
			WindActor ? WindActor->AvgTickMs : -1.f, WindActor ? WindActor->FieldDraws : 0, *LeafStatsJson());
	};
	AddCall([this]()
	{
		WindActor = AGlobalWind::Get(this, true);
		WindActor->GustsPerMinute = 0.f;			// bursts on cue for the film
		WindActor->bUseLevelWindDirection = false;
		WindActor->DirectionYaw = LeafDir.Rotation().Yaw + 180.f;
		WindActor->MeanSpeed = 3.f;
		LeafFall->RestTime = 60.f;		// test only: keep the carpet for the whole film
		LeafFall->LeavesPerTreePerMinute = 8.f;
		const FVector C = GroundAt(LeafAnchor + LeafDir * 650.f);
		SpawnWindGrass(LeafAnchor + LeafDir * 1000.f, C, LeafDir);
		SpawnCarpet(C, 650.f, 220, 7);
	});
	AddWaitShaders(8.f);
	AddCall([this, WindJson]() { Log(TEXT("wind carpet ") + WindJson()); });
	// 0. the meadow from the side: a group of bursts rolls across the grass and through the trees (waves in the grass)
	AddCall([this]()
	{
		bCamInit = false;
		const FVector Side(-LeafDir.Y, LeafDir.X, 0.f);
		WindActor->DirectionYaw = Side.Rotation().Yaw;		// crossing the frame
		SetCam(GroundAt(LeafAnchor + LeafDir * 1500.f - Side * 600.f) + FVector(0, 0, 95.f), GroundAt(LeafAnchor + LeafDir * 300.f + Side * 200.f) + FVector(0, 0, 330.f), 66.f);
	});
	AddRecord(2.f, [](float, float) {});
	AddCall([this, WindJson]() { WindActor->TriggerGust(9.f, -4.f, 45.f); Log(TEXT("wind meadow gust ") + WindJson()); });
	AddRecord(5.f, [](float, float) {});
	AddCall([this]() { WindActor->TriggerGust(7.f, 6.f, 40.f); });
	AddRecord(11.f, [this, WindJson](float T, float Dt) { if (FMath::Fmod(T, 2.f) < Dt) Log(FString::Printf(TEXT("wind meadow t=%.0f "), T) + WindJson()); });
	// 0b. down in the meadow, looking upwind: a burst comes through the grass toward the camera
	AddCall([this]()
	{
		bCamInit = false;
		const FVector Side(-LeafDir.Y, LeafDir.X, 0.f);
		WindActor->DirectionYaw = (-Side).Rotation().Yaw;
		const FVector C = GroundAt(LeafAnchor + LeafDir * 1700.f - Side * 1500.f) + FVector(0, 0, 70.f);
		SetCam(C, GroundAt(LeafAnchor + LeafDir * 1700.f + Side * 1500.f) + FVector(0, 0, 120.f), 70.f);
	});
	AddRecord(1.f, [](float, float) {});
	AddCall([this, WindJson]() { WindActor->TriggerGust(10.f, 0.f, 50.f); Log(TEXT("wind meadow-low gust ") + WindJson()); });
	AddRecord(12.f, [this, WindJson](float T, float Dt) { if (FMath::Fmod(T, 2.f) < Dt) Log(FString::Printf(TEXT("wind meadow-low t=%.0f "), T) + WindJson()); });
	// 1. low over the carpet: a burst sweeps across it toward the camera (fresh carpet: the first one has aged out)
	AddCall([this]() { SpawnCarpet(GroundAt(LeafAnchor + LeafDir * 650.f), 650.f, 220, 9); });
	AddWait(2.5f);
	AddCall([this]()
	{
		bCamInit = false;
		WindActor->DirectionYaw = (-LeafDir).Rotation().Yaw;		// from the far side of the carpet toward the tree / camera
		const FVector CamP = GroundAt(LeafAnchor + LeafDir * 120.f) + FVector(0, 0, 45.f);
		SetCam(CamP, GroundAt(LeafAnchor + LeafDir * 900.f) + FVector(0, 0, 20.f), 62.f);
	});
	AddRecord(1.f, [](float, float) {});
	AddCall([this, WindJson]() { const int32 Id = WindActor->TriggerGust(11.f, 0.f, 40.f); Log(FString::Printf(TEXT("wind gust %d triggered "), Id) + WindJson()); });
	AddRecord(13.f, [this, WindJson](float T, float Dt) { if (FMath::Fmod(T, 2.f) < Dt) Log(FString::Printf(TEXT("wind t=%.0f "), T) + WindJson()); });
	// 2. the canopy: a burst bends the tree and tears leaves off it
	AddCall([this]()
	{
		BaseSpawned = LeafFall->GetStats().Spawned;
		bCamInit = false;
		WindActor->DirectionYaw = FRotator(0.f, LeafDir.Rotation().Yaw + 90.f, 0.f).Yaw;
		SetCam(GroundAt(LeafAnchor + LeafDir * 1500.f) + FVector(0, 0, 180.f), LeafCanopy - FVector(0, 0, 250.f), 58.f);
	});
	AddRecord(4.f, [](float, float) {});
	AddCall([this, WindJson]() { Log(FString::Printf(TEXT("wind calm 4 s spawned=%d "), LeafFall->GetStats().Spawned - BaseSpawned) + WindJson()); BaseSpawned = LeafFall->GetStats().Spawned; WindActor->TriggerGust(10.f, 0.f, 35.f); });
	// (diagnostic inside the burst: 1.5 s without temporal AA, then 1.5 s without Nanite foliage, to tell a motion-vector
	// smear from geometry; logged so the frames can be found in the film)
	AddRecord(10.f, [this, WindJson](float T, float Dt)
	{
		if (FMath::Fmod(T, 2.f) < Dt) Log(FString::Printf(TEXT("wind canopy t=%.0f "), T) + WindJson());
		auto Cv = [this](const TCHAR* Name, int32 V)
		{
			IConsoleVariable* C = IConsoleManager::Get().FindConsoleVariable(Name);
			if (C) { Log(FString::Printf(TEXT("cvar %s %d -> %d at frame %d"), Name, C->GetInt(), V, int32(GFrameCounter))); C->Set(V, ECVF_SetByConsole); }
			else Log(FString::Printf(TEXT("cvar %s missing"), Name));
		};
		if (T >= 5.f && T - Dt < 5.f) Cv(TEXT("r.AntiAliasingMethod"), 0);
		if (T >= 6.5f && T - Dt < 6.5f) { Cv(TEXT("r.AntiAliasingMethod"), 4); Cv(TEXT("r.Nanite.Foliage"), 0); }
		if (T >= 8.f && T - Dt < 8.f) Cv(TEXT("r.Nanite.Foliage"), 1);
	});
	AddCall([this, WindJson]() { Log(FString::Printf(TEXT("wind burst 10 s spawned=%d "), LeafFall->GetStats().Spawned - BaseSpawned) + WindJson()); });
	// 3. slow motion (1/3), close on a fresh patch of leaves: they slide, cartwheel and lift off
	AddCall([this]()
	{
		WindActor->DirectionYaw = (-LeafDir).Rotation().Yaw;
		SpawnCarpet(GroundAt(LeafAnchor + LeafDir * 560.f), 260.f, 110, 21);
	});
	AddWait(2.5f);
	AddCall([this]()
	{
		bCamInit = false;
		SetCam(GroundAt(LeafAnchor + LeafDir * 330.f) + FVector(0, 0, 70.f), GroundAt(LeafAnchor + LeafDir * 520.f), 50.f);
		UGameplayStatics::SetGlobalTimeDilation(this, 0.33f);
	});
	AddRecord(1.5f, [](float, float) {});
	AddCall([this]() { WindActor->TriggerGust(13.f, 0.f, 18.f); });
	AddRecord(10.f, [](float, float) {});
	AddCall([this, WindJson]() { UGameplayStatics::SetGlobalTimeDilation(this, 1.f); Log(TEXT("wind end ") + WindJson()); });
}
