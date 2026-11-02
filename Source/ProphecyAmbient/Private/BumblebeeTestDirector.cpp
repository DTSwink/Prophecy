#include "BumblebeeTestDirector.h"
#include "BumblebeeSwarm.h"
#include "BumblebeeZone.h"
#include "Animation/AnimSequence.h"
#include "Animation/SkeletalMeshActor.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "RHI.h"
#include "RenderCore.h"
#include "RenderingThread.h"
#include "ShaderCompiler.h"
#include "UnrealClient.h"

namespace
{
	const TCHAR* BeeFolder = TEXT("/Game/Prophecy/Creatures/Bumblebee");
	void Cmd(UWorld* W, const TCHAR* C)
	{
		if (GEngine) GEngine->Exec(W, C);
	}
}

ABumblebeeTestDirector::ABumblebeeTestDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ABumblebeeTestDirector::Log(const FString& Line)
{
	UE_LOG(LogTemp, Display, TEXT("BEETEST %s"), *Line);
	Report += Line + TEXT("\n");
	Flush();
}

void ABumblebeeTestDirector::Flush()
{
	FFileHelper::SaveStringToFile(Report, *(OutDir / TEXT("report.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void ABumblebeeTestDirector::ResetTiming()
{
	FrameMsSum = GameMsSum = RenderMsSum = GpuMsSum = 0.0;
	FrameSamples = 0;
}

FString ABumblebeeTestDirector::TimingJson() const
{
	const double N = FMath::Max(FrameSamples, 1);
	return FString::Printf(TEXT("{\"frames\":%d,\"frame_ms\":%.3f,\"game_ms\":%.3f,\"render_ms\":%.3f,\"gpu_ms\":%.3f}"),
		FrameSamples, FrameMsSum / N, GameMsSum / N, RenderMsSum / N, GpuMsSum / N);
}

FString ABumblebeeTestDirector::StatsJson() const
{
	if (!Swarm) return TEXT("{}");
	const FBumblebeeStats S = Swarm->GetStats();
	return FString::Printf(TEXT("{\"bees\":%d,\"unplaced\":%d,\"landed\":%d,\"walking\":%d,\"flying\":%d,\"near\":%d,\"mid\":%d,\"far\":%d,\"escaping\":%d,\"avg_ms\":%.4f,\"max_ms\":%.4f,\"traces_s\":%.0f,\"takeoffs\":%d,\"threat_takeoffs\":%d,\"landings\":%d,\"esc_started\":%d,\"esc_ok\":%d,\"plan_fail\":%d}"),
		S.Bees, S.Unplaced, S.Landed, S.Walking, S.Flying, S.Near, S.Mid, S.Far, S.Escaping, S.AvgTickMs, S.MaxTickMs, S.TracesPerSecond,
		S.Takeoffs, S.ThreatTakeoffs, S.Landings, S.EscapesStarted, S.EscapesSucceeded, S.PlanFailures);
}

void ABumblebeeTestDirector::SetCam(const FVector& Loc, const FVector& Target, float Fov)
{
	if (!Cam) return;
	Cam->SetActorLocationAndRotation(Loc, (Target - Loc).Rotation());
	Cam->GetCameraComponent()->SetFieldOfView(Fov);
}

AActor* ABumblebeeTestDirector::SpawnBox(const FVector& Loc, const FVector& SizeCm, const FLinearColor& Color, const TCHAR* Shape, const FRotator& Rot, bool bMovable)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *FString::Printf(TEXT("/Engine/BasicShapes/%s.%s"), Shape, Shape));
	const FTransform T(Rot, Loc, SizeCm / 100.f);
	AStaticMeshActor* A = GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(), T);
	if (!A) return nullptr;
	UStaticMeshComponent* C = A->GetStaticMeshComponent();
	C->SetMobility(bMovable ? EComponentMobility::Movable : EComponentMobility::Static);
	C->SetStaticMesh(Mesh);
	if (BaseMat)
	{
		UMaterialInstanceDynamic* M = UMaterialInstanceDynamic::Create(BaseMat, A);
		M->SetVectorParameterValue(TEXT("Color"), Color);
		C->SetMaterial(0, M);
	}
	A->FinishSpawning(T);
	return A;
}

void ABumblebeeTestDirector::SpawnLighting()
{
	FActorSpawnParameters P;
	const FTransform Sun(FRotator(-38.f, 35.f, 0.f), FVector(0, 0, 500));
	ADirectionalLight* L = GetWorld()->SpawnActorDeferred<ADirectionalLight>(ADirectionalLight::StaticClass(), Sun);
	L->GetLightComponent()->SetMobility(EComponentMobility::Movable);
	L->FinishSpawning(Sun);
	L->GetLightComponent()->SetIntensity(8.f);
	ASkyLight* Sky = GetWorld()->SpawnActorDeferred<ASkyLight>(ASkyLight::StaticClass(), FTransform::Identity);
	Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);
	Sky->GetLightComponent()->bRealTimeCapture = true;
	Sky->FinishSpawning(FTransform::Identity);
	GetWorld()->SpawnActor<ASkyAtmosphere>(P);
}

ABumblebeeZone* ABumblebeeTestDirector::SpawnZone(const FVector& Center, const FVector& Extent, int32 Count, float Preference)
{
	const FTransform T(Center);
	ABumblebeeZone* Z = GetWorld()->SpawnActorDeferred<ABumblebeeZone>(ABumblebeeZone::StaticClass(), T);
	Z->Box->SetBoxExtent(Extent);
	Z->BeeCount = Count;
	Z->Preference = Preference;
	Z->FinishSpawning(T);
	Swarm = ABumblebeeSwarm::Find(this);
	return Z;
}

int32 ABumblebeeTestDirector::FindBee(bool bLanded, const FVector& Near, float MaxDist) const
{
	if (!Swarm) return INDEX_NONE;
	int32 Best = INDEX_NONE;
	double BestD = FMath::Square(MaxDist);
	for (int32 i = 0; i < Swarm->GetNumBees(); ++i)
	{
		const FTransform T = Swarm->GetBeeTransform(i);
		if (bLanded ? !Swarm->IsBeeLanded(i) : !Swarm->IsBeeFlying(i)) continue;
		const double D = FVector::DistSquared(T.GetLocation(), Near);
		if (D < BestD) { BestD = D; Best = i; }
	}
	return Best;
}

void ABumblebeeTestDirector::FrameBee(int32 Index, float Dist, float Yaw, float Pitch, float Fov)
{
	if (!Swarm || Index == INDEX_NONE) return;
	const FTransform T = Swarm->GetBeeTransform(Index);
	const FVector Up = T.GetRotation().GetUpVector();
	const FVector Centre = T.GetLocation() + (Swarm->IsBeeLanded(Index) ? Up * 0.8f : FVector::ZeroVector);
	const FRotator R(Pitch, T.Rotator().Yaw + Yaw, 0.f);
	SetCam(Centre - R.Vector() * Dist, Centre, Fov);
}

// ---------------------------------------------------------------------------------------------------------------------
void ABumblebeeTestDirector::AddWaitShaders(float MinSeconds)
{
	Steps.Add([this, MinSeconds, Quiet = 0.f](float Dt) mutable
	{
		const int32 Jobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		Quiet = Jobs > 0 ? 0.f : Quiet + Dt;
		if (FMath::Fmod(StepTime, 15.f) < Dt) Log(FString::Printf(TEXT("waiting shaders: %d jobs, t=%.0fs"), Jobs, StepTime));
		return (StepTime >= MinSeconds && Quiet > 3.f) || StepTime > 1500.f;
	});
}

void ABumblebeeTestDirector::AddWait(float Seconds)
{
	Steps.Add([this, Seconds](float) { return StepTime >= Seconds; });
}

void ABumblebeeTestDirector::AddShot(const FString& Name, float Settle)
{
	Steps.Add([this, Name, Settle, bRequested = false](float) mutable
	{
		if (StepTime < Settle) return false;
		if (!bRequested)
		{
			FScreenshotRequest::RequestScreenshot(OutDir / (Name + TEXT(".png")), false, false);
			bRequested = true;
			Log(FString::Printf(TEXT("shot %s"), *Name));
			return false;
		}
		return StepTime > Settle + 0.6f;
	});
}

void ABumblebeeTestDirector::AddCall(TFunction<void()> Fn)
{
	Steps.Add([Fn](float) { Fn(); return true; });
}

// ---------------------------------------------------------------------------------------------------------------------
void ABumblebeeTestDirector::BeginPlay()
{
	Super::BeginPlay();
	FString Out;
	OutDir = FParse::Value(FCommandLine::Get(), TEXT("BeeTestOut="), Out) ? Out : FPaths::ProjectSavedDir() / TEXT("BeeTest") / Scene;
	IFileManager::Get().MakeDirectory(*OutDir, true);
	BaseMat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	Cmd(GetWorld(), TEXT("bumblebees.LogStats 1"));
	Cmd(GetWorld(), TEXT("t.MaxFPS 0"));
	Log(FString::Printf(TEXT("scene=%s map=%s"), *Scene, *GetWorld()->GetMapName()));

	FActorSpawnParameters P;
	Cam = GetWorld()->SpawnActor<ACameraActor>(FVector(0, -30, 15), FRotator::ZeroRotator, P);
	Cam->GetCameraComponent()->bConstrainAspectRatio = false;
	Cam->GetCameraComponent()->PostProcessSettings.bOverride_AutoExposureSpeedUp = true;
	Cam->GetCameraComponent()->PostProcessSettings.AutoExposureSpeedUp = 20.f;
	Cam->GetCameraComponent()->PostProcessSettings.bOverride_AutoExposureSpeedDown = true;
	Cam->GetCameraComponent()->PostProcessSettings.AutoExposureSpeedDown = 20.f;

	if (Scene == TEXT("model")) BuildModelScene();
	else if (Scene == TEXT("swarm")) BuildSwarmScene();
	else BuildMapScene();

	AddCall([this]() { Log(TEXT("done")); FGenericPlatformMisc::RequestExit(false, TEXT("BeeTest")); });
}

void ABumblebeeTestDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	TotalTime += DeltaSeconds;
	StepTime += DeltaSeconds;
	FrameMsSum += DeltaSeconds * 1000.0;
	GameMsSum += FPlatformTime::ToMilliseconds(GGameThreadTime);
	RenderMsSum += FPlatformTime::ToMilliseconds(GRenderThreadTime);
	GpuMsSum += FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles());
	++FrameSamples;

	if (bOverrideView && Cam)
	{
		if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
		{
			if (PC->GetViewTarget() != Cam) PC->SetViewTarget(Cam);
		}
	}
	if (bMoveThreat && ThreatActor)
	{
		ThreatAngle += DeltaSeconds * 150.f / 400.f;
		ThreatActor->SetActorLocation(ThreatCenter + FVector(FMath::Cos(ThreatAngle), FMath::Sin(ThreatAngle), 0.f) * 400.f);
	}
	if (TotalTime > 2400.f)
	{
		Log(TEXT("timeout"));
		FGenericPlatformMisc::RequestExit(false, TEXT("BeeTest timeout"));
		return;
	}
	while (Steps.IsValidIndex(StepIndex))
	{
		if (!Steps[StepIndex](DeltaSeconds)) break;
		++StepIndex;
		StepTime = 0.f;
	}
}

// ---------------------------------------------------------------------------------------------------------------------
void ABumblebeeTestDirector::BuildModelScene()
{
	SpawnLighting();
	SpawnBox(FVector(0, 0, -5), FVector(4000, 4000, 10), FLinearColor(0.10f, 0.22f, 0.05f));
	// a few "flowers" to land on
	for (int32 i = 0; i < 6; ++i)
	{
		const FVector P(40.f + i * 9.f, (i % 2 ? 1 : -1) * 8.f, 0.f);
		SpawnBox(P + FVector(0, 0, 4), FVector(1.2f, 1.2f, 8.f), FLinearColor(0.1f, 0.3f, 0.05f), TEXT("Cylinder"));
		SpawnBox(P + FVector(0, 0, 8.5f), FVector(6.f, 6.f, 1.5f), FLinearColor(0.8f, 0.25f, 0.45f), TEXT("Cylinder"));
	}

	FString AnimPath;
	if (!FParse::Value(FCommandLine::Get(), TEXT("BeeFlyAnim="), AnimPath)) AnimPath = FString(BeeFolder) / TEXT("SK_Bumblebee_Anim_Armature_Fly");
	USkeletalMesh* SK = LoadObject<USkeletalMesh>(nullptr, *(FString(BeeFolder) / TEXT("SK_Bumblebee")));
	UAnimSequence* Fly = LoadObject<UAnimSequence>(nullptr, *AnimPath);
	Log(FString::Printf(TEXT("skeletal=%s anim=%s"), SK ? TEXT("ok") : TEXT("MISSING"), Fly ? TEXT("ok") : TEXT("MISSING")));
	if (SK)
	{
		ASkeletalMeshActor* A = GetWorld()->SpawnActor<ASkeletalMeshActor>(FVector(0, 0, 14), FRotator::ZeroRotator);
		A->GetSkeletalMeshComponent()->SetSkeletalMeshAsset(SK);
		if (Fly) A->GetSkeletalMeshComponent()->PlayAnimation(Fly, true);
	}
	UStaticMesh* Landed = LoadObject<UStaticMesh>(nullptr, *(FString(BeeFolder) / TEXT("SM_Bumblebee_Landed")));
	if (Landed)
	{
		const FTransform T(FRotator(0, 20, 0), FVector(0, 9, 0));
		AStaticMeshActor* A = GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(), T);
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(Landed);
		A->FinishSpawning(T);
	}
	SpawnZone(FVector(60, 0, 20), FVector(40, 30, 25), 10, 1.f);

	AddWaitShaders(8.f);
	AddWait(3.f);
	AddCall([this]() { SetCam(FVector(0.5f, -17.f, 13.f), FVector(-0.2f, 0, 13.6f), 15.f); });
	AddShot(TEXT("01_skeletal_side"), 1.5f);
	AddCall([this]() { SetCam(FVector(10.f, -11.f, 19.f), FVector(-0.2f, 0, 13.8f), 15.f); });
	AddShot(TEXT("02_skeletal_hero"), 1.0f);
	AddCall([this]() { SetCam(FVector(16.f, -2.f, 14.f), FVector(0, 0, 13.8f), 15.f); });
	AddShot(TEXT("03_skeletal_front"), 1.0f);
	AddCall([this]() { SetCam(FVector(9.f, -5.f, 6.f), FVector(0, 9, 0.8f), 15.f); });
	AddShot(TEXT("04_static_landed"), 1.0f);
	AddWait(4.f);
	AddCall([this]() { FrameBee(FindBee(true, FVector(60, 0, 0), 300.f), 14.f, -60.f, -25.f, 18.f); });
	AddShot(TEXT("05_swarm_landed_bee"), 0.8f);
	AddCall([this]() { FrameBee(FindBee(true, FVector(60, 0, 0), 300.f), 13.f, 90.f, -15.f, 18.f); });
	AddShot(TEXT("06_swarm_landed_bee_side"), 0.8f);
	Steps.Add([this](float) { return FindBee(false, FVector(60, 0, 0), 400.f) != INDEX_NONE || StepTime > 30.f; });
	AddCall([this]() { FrameBee(FindBee(false, FVector(60, 0, 0), 400.f), 22.f, 70.f, -10.f, 20.f); });
	AddShot(TEXT("07_swarm_flying_bee"), 0.05f);
	AddCall([this]() { SetCam(FVector(-30.f, -90.f, 45.f), FVector(55, 0, 6), 30.f); });
	AddShot(TEXT("08_overview"), 1.0f);
	AddCall([this]() { Log(TEXT("stats ") + StatsJson()); });
}

void ABumblebeeTestDirector::BuildSwarmScene()
{
	SpawnLighting();
	SpawnBox(FVector(0, 0, -5), FVector(16000, 16000, 10), FLinearColor(0.10f, 0.22f, 0.05f));
	FRandomStream R(7);
	// garden props in the main zone
	for (int32 i = 0; i < 60; ++i)
	{
		const FVector P(R.FRandRange(-850, 850), R.FRandRange(-850, 850), 0);
		const float H = R.FRandRange(10, 70);
		SpawnBox(P + FVector(0, 0, H * 0.5f), FVector(2, 2, H), FLinearColor(0.08f, 0.25f, 0.04f), TEXT("Cylinder"));
		const FLinearColor Petal = (i % 3 == 0) ? FLinearColor(0.85f, 0.75f, 0.1f) : (i % 3 == 1 ? FLinearColor(0.8f, 0.2f, 0.5f) : FLinearColor(0.5f, 0.3f, 0.85f));
		SpawnBox(P + FVector(0, 0, H + 1), FVector(10, 10, 2), Petal, TEXT("Cylinder"));
	}
	for (int32 i = 0; i < 12; ++i)
	{
		SpawnBox(FVector(R.FRandRange(-800, 800), R.FRandRange(-800, 800), 20), FVector(R.FRandRange(40, 120), R.FRandRange(40, 120), 40), FLinearColor(0.35f, 0.33f, 0.3f), TEXT("Cube"), FRotator(0, R.FRandRange(0, 90), 0));
	}
	// a closed room with one door (front wall faces -X)
	const FVector House(1500, 0, 0);
	const FLinearColor Wall(0.45f, 0.32f, 0.2f);
	SpawnBox(House + FVector(250, 0, 150), FVector(20, 520, 300), Wall);
	SpawnBox(House + FVector(0, 250, 150), FVector(520, 20, 300), Wall);
	SpawnBox(House + FVector(0, -250, 150), FVector(520, 20, 300), Wall);
	SpawnBox(House + FVector(-250, 170, 150), FVector(20, 180, 300), Wall);		// front wall, door at y -20..80
	SpawnBox(House + FVector(-250, -140, 150), FVector(20, 240, 300), Wall);
	SpawnBox(House + FVector(-250, 30, 260), FVector(20, 100, 80), Wall);		// lintel, door height 220
	SpawnBox(House + FVector(0, 0, 310), FVector(540, 540, 20), FLinearColor(0.3f, 0.12f, 0.08f));	// roof
	SpawnBox(House + FVector(100, 0, 40), FVector(150, 80, 80), FLinearColor(0.4f, 0.25f, 0.1f));	// table inside
	Log(TEXT("room 500x500x300 at x=1500, door 100x220 in the -X wall, roof at 310"));

	SpawnZone(FVector(0, 0, 100), FVector(900, 900, 150), 300);
	SpawnZone(FVector(-1800, 900, 100), FVector(500, 500, 150), 100);
	SpawnZone(FVector(6000, 0, 100), FVector(500, 500, 150), 100);

	// moving "player-like" threat
	ThreatCenter = FVector(150, -150, 60);
	ThreatActor = SpawnBox(ThreatCenter + FVector(400, 0, 0), FVector(60, 60, 120), FLinearColor(0.1f, 0.1f, 0.6f), TEXT("Sphere"), FRotator::ZeroRotator, true);

	AddWaitShaders(8.f);
	AddCall([this]() { SetCam(FVector(-900, -900, 300), FVector(0, 0, 20), 60.f); });
	AddWait(10.f);
	AddCall([this]() { Log(TEXT("placed ") + StatsJson()); });
	AddShot(TEXT("01_overview"));
	AddCall([this]() { SetCam(FVector(-150, -150, 60), FVector(100, 100, 10), 50.f); ResetTiming(); });
	AddWait(15.f);
	AddCall([this]() { Log(TEXT("near_view timing ") + TimingJson() + TEXT(" stats ") + StatsJson()); });
	AddShot(TEXT("02_ground_view"));
	AddCall([this]() { FrameBee(FindBee(true, Cam->GetActorLocation(), 2000.f), 14.f, -50.f, -25.f, 18.f); });
	AddShot(TEXT("03_landed_closeup"), 1.0f);
	Steps.Add([this](float) { return FindBee(false, FVector(-150, -150, 60), 1200.f) != INDEX_NONE || StepTime > 20.f; });
	AddCall([this]() { FrameBee(FindBee(false, FVector(-150, -150, 60), 1200.f), 30.f, 80.f, -10.f, 22.f); });
	AddShot(TEXT("04_flying_closeup"), 0.03f);

	// threat: something walking through the garden
	AddCall([this]()
	{
		if (Swarm && ThreatActor) Swarm->AddThreatActor(ThreatActor);
		bMoveThreat = true;
		SetCam(FVector(150, -900, 250), ThreatCenter, 55.f);
		Log(TEXT("threat_start ") + StatsJson());
	});
	AddWait(8.f);
	AddShot(TEXT("05_threat"), 0.f);
	AddWait(12.f);
	AddCall([this]() { bMoveThreat = false; Log(TEXT("threat_end ") + StatsJson()); });

	// escape: bees indoors, player inside the room
	AddCall([this]()
	{
		const int32 Moved = Swarm ? Swarm->RelocateBeesTo(FVector(1500, 0, 0), 180.f, 12) : 0;
		SetCam(FVector(1700, -200, 170), FVector(1250, 30, 100), 75.f);
		Log(FString::Printf(TEXT("escape_start moved=%d %s"), Moved, *StatsJson()));
	});
	AddWait(3.f);
	AddShot(TEXT("06_indoor"), 0.f);
	AddWait(20.f);
	AddShot(TEXT("07_indoor_20s"), 0.f);
	AddWait(25.f);
	AddCall([this]()
	{
		int32 Inside = 0;
		for (int32 i = 0; Swarm && i < Swarm->GetNumBees(); ++i)
		{
			const FVector P = Swarm->GetBeeTransform(i).GetLocation();
			if (FMath::Abs(P.X - 1500) < 240 && FMath::Abs(P.Y) < 240 && P.Z < 300 && P.Z > -1) ++Inside;
		}
		Log(FString::Printf(TEXT("escape_end inside_room=%d %s"), Inside, *StatsJson()));
	});

	// far away: everything frozen; then lazy placement of the distant zone
	AddCall([this]() { SetCam(FVector(-12000, -12000, 3000), FVector(0, 0, 0), 60.f); ResetTiming(); });
	AddWait(8.f);
	AddCall([this]() { Log(TEXT("far timing ") + TimingJson() + TEXT(" stats ") + StatsJson()); });
	AddCall([this]() { SetCam(FVector(5300, -700, 200), FVector(6000, 0, 0), 55.f); });
	AddWait(8.f);
	AddCall([this]() { Log(TEXT("zone3 ") + StatsJson()); });
	AddShot(TEXT("08_zone3"), 0.f);

	// cost A/B from a busy view
	AddCall([this]() { SetCam(FVector(-150, -150, 60), FVector(100, 100, 10), 50.f); ResetTiming(); });
	AddWait(10.f);
	AddCall([this]() { Log(TEXT("ab_on ") + TimingJson() + TEXT(" stats ") + StatsJson()); Cmd(GetWorld(), TEXT("bumblebees.Enable 0")); ResetTiming(); });
	AddWait(10.f);
	AddCall([this]() { Log(TEXT("ab_off ") + TimingJson()); Cmd(GetWorld(), TEXT("bumblebees.Enable 1")); });
}

void ABumblebeeTestDirector::BuildMapScene()
{
	bOverrideView = false;
	AddWaitShaders(20.f);
	AddWait(5.f);
	AddCall([this]()
	{
		FVector L = FVector::ZeroVector;
		FRotator V = FRotator::ZeroRotator;
		if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
		{
			PC->GetPlayerViewPoint(L, V);
		}
		Log(FString::Printf(TEXT("player view %s"), *L.ToString()));
		const FVector Offs[] = { FVector(600, 0, 0), FVector(2500, 800, 0), FVector(-2500, 1500, 0), FVector(0, -3000, 0), FVector(6000, 6000, 0) };
		for (const FVector& O : Offs)
		{
			SpawnZone(L + O + FVector(0, 0, 100), FVector(800, 800, 500), 100);
		}
		ResetTiming();
	});
	AddWait(20.f);
	AddCall([this]() { Log(TEXT("map_on ") + TimingJson() + TEXT(" stats ") + StatsJson()); Cmd(GetWorld(), TEXT("bumblebees.Enable 0")); ResetTiming(); });
	AddWait(15.f);
	AddCall([this]() { Log(TEXT("map_off ") + TimingJson()); Cmd(GetWorld(), TEXT("bumblebees.Enable 1")); ResetTiming(); });
	AddWait(10.f);
	AddShot(TEXT("01_player_view"), 0.f);
	AddCall([this]()
	{
		bOverrideView = true;
		FVector L; FRotator V;
		GetWorld()->GetFirstPlayerController()->GetPlayerViewPoint(L, V);
		const int32 Bee = FindBee(true, L, 3000.f);
		Log(FString::Printf(TEXT("closeup bee %d"), Bee));
		FrameBee(Bee, 16.f, -40.f, -20.f, 18.f);
	});
	AddShot(TEXT("02_map_landed_closeup"), 1.5f);
	AddCall([this]()
	{
		FVector L; FRotator V;
		bOverrideView = false;
		GetWorld()->GetFirstPlayerController()->GetPlayerViewPoint(L, V);
		bOverrideView = true;
		const int32 Bee = FindBee(true, L, 3000.f);
		if (Bee != INDEX_NONE) SetCam(Swarm->GetBeeTransform(Bee).GetLocation() + FVector(-250, -250, 150), Swarm->GetBeeTransform(Bee).GetLocation(), 55.f);
	});
	AddShot(TEXT("03_map_zone_view"), 6.0f);
	AddCall([this]() { Log(TEXT("final ") + StatsJson()); });
}
