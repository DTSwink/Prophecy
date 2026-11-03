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
#include "Engine/GameViewportClient.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Misc/App.h"
#include "ContentStreaming.h"
#include "GameFramework/Pawn.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/Texture.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

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
	return FString::Printf(TEXT("{\"bees\":%d,\"unplaced\":%d,\"landed\":%d,\"walking\":%d,\"flying\":%d,\"near\":%d,\"mid\":%d,\"far\":%d,\"escaping\":%d,\"avg_ms\":%.4f,\"max_ms\":%.4f,\"traces_s\":%.0f,\"takeoffs\":%d,\"threat_takeoffs\":%d,\"landings\":%d,\"esc_started\":%d,\"esc_ok\":%d,\"plan_fail\":%d,\"double_backs\":%d,\"inst_upd_s\":%d}"),
		S.Bees, S.Unplaced, S.Landed, S.Walking, S.Flying, S.Near, S.Mid, S.Far, S.Escaping, S.AvgTickMs, S.MaxTickMs, S.TracesPerSecond,
		S.Takeoffs, S.ThreatTakeoffs, S.Landings, S.EscapesStarted, S.EscapesSucceeded, S.PlanFailures, S.DoubleBacks, S.InstanceUpdatesPerSecond);
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
	Z->BoxExtent = Extent;
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

void ABumblebeeTestDirector::AddShot(const FString& Name, float Settle, bool bStream)
{
	Steps.Add([this, Name, Settle, bRequested = false, bStreamed = !bStream](float) mutable
	{
		// shaders for newly visible permutations (instanced bees!) + full texture mips before every shot
		const int32 Jobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		if (!bRequested && Jobs > 0 && StepTime < 900.f) { StepTime = FMath::Min(StepTime, 0.f); return false; }
		if (!bRequested && !bStreamed)
		{
			IStreamingManager::Get().StreamAllResources(3.0f);
			bStreamed = true;
			StepTime = 0.f;
			return false;
		}
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
	else if (Scene == TEXT("video")) BuildVideoScene();
	else if (Scene == TEXT("size")) BuildSizeScene();
	else if (Scene == TEXT("traj")) BuildTrajScene();
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

	if (Scene != TEXT("map"))
	{
		if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
		{
			if (APawn* P = PC->GetPawn()) { PC->UnPossess(); P->Destroy(); }
		}
	}
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
	SpawnBox(FVector(0, 0, -5), FVector(4000, 4000, 10), FLinearColor(0.05f, 0.08f, 0.03f));
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
	AddShot(TEXT("06b_warmup"), 0.5f);
	Steps.Add([this](float) { return FindBee(false, FVector(60, 0, 0), 400.f) != INDEX_NONE || StepTime > 30.f; });
	AddCall([this]() { FrameBee(FindBee(false, FVector(60, 0, 0), 400.f), 22.f, 70.f, -10.f, 20.f); });
	AddShot(TEXT("07_swarm_flying_bee"), 0.05f, false);
	AddCall([this]() { SetCam(FVector(-30.f, -90.f, 45.f), FVector(55, 0, 6), 30.f); });
	AddShot(TEXT("08_overview"), 1.0f);
	AddCall([this]() { Log(TEXT("stats ") + StatsJson()); });
}

void ABumblebeeTestDirector::AddCostAB(const FString& Name, const TCHAR* Command, TFunction<void()> Undo)
{
	// 1 s settle, then 6 s of timing with the change applied
	FString C = Command ? FString(Command) : FString();
	AddCall([this, C]() { if (!C.IsEmpty()) Cmd(GetWorld(), *C); });
	AddWait(1.f);
	AddCall([this]() { ResetTiming(); });
	AddWait(6.f);
	AddCall([this, Name, Undo]()
	{
		Log(FString::Printf(TEXT("cost %s %s stats %s"), *Name, *TimingJson(), *StatsJson()));
		if (Undo) Undo();
	});
}

FString ABumblebeeTestDirector::MemoryJson() const
{
	if (!Swarm) return TEXT("{}");
	int64 InstBytes = 0;
	int32 Instances = 0;
	TArray<UInstancedStaticMeshComponent*> Comps;
	Swarm->GetComponents<UInstancedStaticMeshComponent>(Comps);
	for (UInstancedStaticMeshComponent* C : Comps)
	{
		Instances += C->GetInstanceCount();
		InstBytes += C->GetResourceSizeBytes(EResourceSizeMode::EstimatedTotal);
	}
	int64 MeshBytes = 0;
	for (const TCHAR* N : { TEXT("SM_Bumblebee_Fly"), TEXT("SM_Bumblebee_Landed") })
	{
		if (UObject* O = LoadObject<UObject>(nullptr, *(FString(BeeFolder) / N))) MeshBytes += O->GetResourceSizeBytes(EResourceSizeMode::EstimatedTotal);
	}
	int64 TexBytes = 0;
	for (const TCHAR* N : { TEXT("T_Bumblebee_Body_BC"), TEXT("T_Bumblebee_Body_N"), TEXT("T_Bumblebee_Body_ORM"), TEXT("T_Bumblebee_Fur_BC"), TEXT("T_Bumblebee_Fur_N"), TEXT("T_Bumblebee_Wing_BC") })
	{
		if (UObject* O = LoadObject<UObject>(nullptr, *(FString(BeeFolder) / TEXT("Textures") / N))) TexBytes += O->GetResourceSizeBytes(EResourceSizeMode::EstimatedTotal);
	}
	const int32 BeeBytes = Swarm->GetNumBees() * 680;		// approx, exact sizeof logged by BEEPROF
	return FString::Printf(TEXT("{\"bees\":%d,\"ism_components\":%d,\"ism_instances\":%d,\"ism_bytes\":%lld,\"static_mesh_bytes\":%lld,\"texture_bytes\":%lld,\"bee_state_bytes_approx\":%d}"),
		Swarm->GetNumBees(), Comps.Num(), Instances, InstBytes, MeshBytes, TexBytes, BeeBytes);
}

int32 ABumblebeeTestDirector::FindBeeWhere(const FVector& Near, float MaxDist, TFunctionRef<bool(int32)> Pred) const
{
	if (!Swarm) return INDEX_NONE;
	int32 Best = INDEX_NONE;
	double BestD = FMath::Square(MaxDist);
	for (int32 i = 0; i < Swarm->GetNumBees(); ++i)
	{
		if (!Pred(i)) continue;
		const double D = FVector::DistSquared(Swarm->GetBeeTransform(i).GetLocation(), Near);
		if (D < BestD) { BestD = D; Best = i; }
	}
	return Best;
}

FString ABumblebeeTestDirector::SurfaceTally(const FVector& C, float Radius) const
{
	int32 Ground = 0, Top = 0, Slope = 0, Vertical = 0, Under = 0, Flying = 0, Walking = 0;
	for (int32 i = 0; Swarm && i < Swarm->GetNumBees(); ++i)
	{
		const FVector P = Swarm->GetBeeTransform(i).GetLocation();
		if (FVector::DistSquared(P, C) > FMath::Square(Radius)) continue;
		if (Swarm->IsBeeFlying(i)) { ++Flying; continue; }
		if (!Swarm->IsBeeLanded(i)) continue;
		Walking += Swarm->IsBeeWalking(i) ? 1 : 0;
		const FVector N = Swarm->GetBeeSurfaceNormal(i);
		if (N.Z > 0.9) (P.Z < 1.5 ? Ground : Top) += 1;
		else if (N.Z > 0.3) ++Slope;
		else if (N.Z > -0.3) ++Vertical;
		else ++Under;
	}
	return FString::Printf(TEXT("{\"flying\":%d,\"landed_ground\":%d,\"landed_tops\":%d,\"landed_slopes\":%d,\"landed_vertical\":%d,\"landed_under\":%d,\"walking\":%d}"),
		Flying, Ground, Top, Slope, Vertical, Under, Walking);
}

void ABumblebeeTestDirector::AddSurfaceProps(const FVector& C)
{
	// rock, tilted board, fence planks, leaves on stems and a fallen log: walls, slopes and undersides to land on
	SpawnBox(C + FVector(-50, 40, 0), FVector(40, 30, 24), FLinearColor(0.32f, 0.31f, 0.29f), TEXT("Sphere"));
	SpawnBox(C + FVector(40, -45, 12), FVector(40, 22, 1.5f), FLinearColor(0.35f, 0.22f, 0.12f), TEXT("Cube"), FRotator(30.f, 20.f, 0.f));
	for (int32 k = 0; k < 4; ++k)
	{
		SpawnBox(C + FVector(-70, -55 + k * 15.f, 27.5f), FVector(3, 13, 55), FLinearColor(0.55f, 0.42f, 0.28f), TEXT("Cube"));
	}
	SpawnBox(C + FVector(70, 40, 7), FVector(14, 14, 60), FLinearColor(0.22f, 0.15f, 0.09f), TEXT("Cylinder"), FRotator(90.f, 70.f, 0.f));
	FRandomStream R(11);
	for (int32 k = 0; k < 8; ++k)
	{
		const FVector P = C + FVector(R.FRandRange(-60, 60), R.FRandRange(-60, 60), 0);
		const float H = R.FRandRange(14, 30);
		SpawnBox(P + FVector(0, 0, H * 0.5f), FVector(0.8f, 0.8f, H), FLinearColor(0.06f, 0.18f, 0.03f), TEXT("Cylinder"));
		SpawnBox(P + FVector(4, 0, H * 0.6f), FVector(14, 6, 0.4f), FLinearColor(0.1f, 0.3f, 0.05f), TEXT("Cube"), FRotator(-25.f, R.FRandRange(0, 360), 15.f));
	}
}

void ABumblebeeTestDirector::AddSpeckles(const FVector& C, float Radius, int32 Count)
{
	// grit on the ground: small flat flakes (thin cubes: plain mesh actors render reliably in -game)
	// shows how fast bees walk and whether the feet slide
	FRandomStream R(5);
	const FLinearColor Cols[3] = { FLinearColor(0.16f, 0.13f, 0.08f), FLinearColor(0.42f, 0.38f, 0.30f), FLinearColor(0.02f, 0.03f, 0.015f) };
	for (int32 k = 0; k < Count; ++k)
	{
		const float A = R.FRand() * TWO_PI, Rad = FMath::Sqrt(R.FRand()) * Radius;
		const float S = R.FRandRange(0.3f, 1.0f);
		AActor* Flake = SpawnBox(C + FVector(FMath::Cos(A) * Rad, FMath::Sin(A) * Rad, 0.06f), FVector(S, S * R.FRandRange(0.6f, 1.4f), 0.12f),
			Cols[k % 3], TEXT("Cylinder"), FRotator(0, R.FRandRange(0, 360), 0));
		// visual only: bees must not step up and down on the grit
		if (AStaticMeshActor* SM = Cast<AStaticMeshActor>(Flake)) SM->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	}
	Log(FString::Printf(TEXT("speckles: %d flakes"), Count));
}

void ABumblebeeTestDirector::BuildSwarmScene()
{
	SpawnLighting();
	SpawnBox(FVector(0, 0, -5), FVector(16000, 16000, 10), FLinearColor(0.05f, 0.08f, 0.03f));
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
	for (const FVector& C : { FVector(-300, -300, 0), FVector(300, 200, 0), FVector(-500, 400, 0), FVector(500, -500, 0) }) AddSurfaceProps(C);
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
	AddCall([this]() { Cmd(GetWorld(), TEXT("bumblebees.Profile 1")); SetCam(FVector(-900, -900, 300), FVector(0, 0, 20), 60.f); });
	AddWait(10.f);
	AddCall([this]() { Log(TEXT("placed ") + StatsJson()); Log(TEXT("memory ") + MemoryJson()); });
	AddShot(TEXT("01_overview"));
	AddCall([this]() { SetCam(FVector(-150, -150, 60), FVector(100, 100, 10), 50.f); ResetTiming(); });
	AddWait(15.f);
	AddCall([this]() { Log(TEXT("near_view timing ") + TimingJson() + TEXT(" stats ") + StatsJson()); });
	// behaviour tally: time share in the air / walking and which surfaces bees choose (sampled every 2 s for 30 s)
	for (int32 k = 0; k < 15; ++k)
	{
		AddWait(2.f);
		AddCall([this, k]() { Log(FString::Printf(TEXT("tally %d %s"), k, *SurfaceTally(FVector(0, 0, 0), 1000.f))); });
	}
	AddShot(TEXT("02_ground_view"));
	AddCall([this]() { FrameBee(FindBee(true, Cam->GetActorLocation(), 2000.f), 14.f, -50.f, -25.f, 18.f); });
	AddShot(TEXT("03_landed_closeup"), 1.0f);

	// threat: something walking through the garden
	AddCall([this]()
	{
		if (Swarm && ThreatActor) Swarm->AddThreatActor(ThreatActor);
		bMoveThreat = true;
		SetCam(FVector(150, -900, 250), ThreatCenter, 55.f);
		Log(TEXT("threat_start ") + StatsJson());
	});
	AddWait(12.f);
	AddCall([this]() { bMoveThreat = false; if (ThreatActor) ThreatActor->SetActorLocation(FVector(0, 0, -3000)); Log(TEXT("threat_end ") + StatsJson()); });

	// escape: bees indoors, player inside the room
	AddCall([this]()
	{
		const int32 Moved = Swarm ? Swarm->RelocateBeesTo(FVector(1500, 0, 0), 180.f, 12) : 0;
		SetCam(FVector(1700, -200, 170), FVector(1250, 30, 100), 75.f);
		Log(FString::Printf(TEXT("escape_start moved=%d %s"), Moved, *StatsJson()));
	});
	AddWait(40.f);
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

	// far away: everything frozen
	AddCall([this]() { SetCam(FVector(-12000, -12000, 3000), FVector(0, 0, 0), 60.f); ResetTiming(); });
	AddWait(8.f);
	AddCall([this]() { Log(TEXT("far timing ") + TimingJson() + TEXT(" stats ") + StatsJson()); });

	// cost breakdown from the busy close view (each change for 6 s, then undone)
	AddCall([this]() { SetCam(FVector(-150, -150, 60), FVector(100, 100, 10), 50.f); });
	AddWait(6.f);
	AddCostAB(TEXT("base"), nullptr);
	AddCostAB(TEXT("hidden"), TEXT("bumblebees.Render 0"), [this]() { Cmd(GetWorld(), TEXT("bumblebees.Render 1")); });
	AddCostAB(TEXT("no_shadows"), TEXT("bumblebees.Shadows 0"), [this]() { Cmd(GetWorld(), TEXT("bumblebees.Shadows 1")); });
	AddCostAB(TEXT("no_wpo"), TEXT("bumblebees.WPO 0"), [this]() { Cmd(GetWorld(), TEXT("bumblebees.WPO 1")); });
	AddCall([this]() { if (Swarm) Swarm->NearDistance = 600.f; });
	AddCostAB(TEXT("near600"), nullptr, [this]() { if (Swarm) Swarm->NearDistance = 1500.f; });
	AddCall([this]() { Cmd(GetWorld(), TEXT("bumblebees.Profile 0")); });
	AddCostAB(TEXT("profiler_off"), nullptr);
	AddCostAB(TEXT("sim_paused"), TEXT("bumblebees.Enable 0"), [this]() { Cmd(GetWorld(), TEXT("bumblebees.Enable 1")); });
	AddCall([this]() { Cmd(GetWorld(), TEXT("bumblebees.Enable 0")); Cmd(GetWorld(), TEXT("bumblebees.Render 0")); });
	AddWait(1.f);
	AddCall([this]() { ResetTiming(); });
	AddWait(6.f);
	AddCall([this]() { Log(TEXT("cost no_bees_at_all ") + TimingJson()); Cmd(GetWorld(), TEXT("bumblebees.Render 1")); Cmd(GetWorld(), TEXT("bumblebees.Enable 1")); });
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

// =====================================================================================================================
// Video + size scenes
void ABumblebeeTestDirector::OnShotCaptured(int32 W, int32 H, const TArray<FColor>& Colors)
{
	if (!bRecording) return;
	IImageWrapperModule& M = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	TSharedPtr<IImageWrapper> Img = M.CreateImageWrapper(EImageFormat::JPEG);
	if (!Img.IsValid() || Colors.Num() != W * H) return;
	TArray<FColor> Opaque = Colors;
	for (FColor& C : Opaque) C.A = 255;
	Img->SetRaw(Opaque.GetData(), Opaque.Num() * sizeof(FColor), W, H, ERGBFormat::BGRA, 8);
	const TArray64<uint8> Jpg = Img->GetCompressed(90);
	FFileHelper::SaveArrayToFile(Jpg, *(OutDir / FString::Printf(TEXT("frame_%05d.jpg"), FrameIndex++)));
}

void ABumblebeeTestDirector::AddRecord(float Seconds, TFunction<void(float)> CamFn)
{
	Steps.Add([this, Seconds, CamFn](float) mutable
	{
		if (!ShotHandle.IsValid())
		{
			ShotHandle = UGameViewportClient::OnScreenshotCaptured().AddUObject(this, &ABumblebeeTestDirector::OnShotCaptured);
		}
		bRecording = true;
		CamFn(StepTime);
		FScreenshotRequest::RequestScreenshot(false);
		if (StepTime >= Seconds)
		{
			bRecording = false;
			const FPlatformMemoryStats M = FPlatformMemory::GetStats();
			Log(FString::Printf(TEXT("recorded segment, frames so far %d, process %.0f MB, %s"), FrameIndex, M.UsedPhysical / 1048576.0, *StatsJson()));
			return true;
		}
		return false;
	});
}

void ABumblebeeTestDirector::BuildGarden(bool bPatch)
{
	SpawnLighting();
	SpawnBox(FVector(0, 0, -5), FVector(16000, 16000, 10), FLinearColor(0.05f, 0.08f, 0.03f));
	FRandomStream R(7);
	auto Flower = [this, &R](const FVector& P, float H, int32 i)
	{
		SpawnBox(P + FVector(0, 0, H * 0.5f), FVector(0.8f, 0.8f, H), FLinearColor(0.06f, 0.18f, 0.03f), TEXT("Cylinder"));
		const FLinearColor Petal = (i % 3 == 0) ? FLinearColor(0.85f, 0.72f, 0.08f) : (i % 3 == 1 ? FLinearColor(0.75f, 0.18f, 0.45f) : FLinearColor(0.45f, 0.25f, 0.8f));
		SpawnBox(P + FVector(0, 0, H + 0.6f), FVector(7, 7, 1.2f), Petal, TEXT("Cylinder"));
		SpawnBox(P + FVector(0, 0, H + 1.4f), FVector(2.4f, 2.4f, 1.f), FLinearColor(0.9f, 0.6f, 0.05f), TEXT("Cylinder"));
	};
	for (int32 i = 0; i < 60; ++i)
	{
		Flower(FVector(R.FRandRange(-850, 850), R.FRandRange(-850, 850), 0), R.FRandRange(15, 60), i);
	}
	for (int32 i = 0; i < 12; ++i)
	{
		SpawnBox(FVector(R.FRandRange(-800, 800), R.FRandRange(-800, 800), 20), FVector(R.FRandRange(40, 120), R.FRandRange(40, 120), 40), FLinearColor(0.35f, 0.33f, 0.3f), TEXT("Cube"), FRotator(0, R.FRandRange(0, 90), 0));
	}
	if (bPatch)
	{
		// dense flower patch for close filming, with walls/slopes/leaves, on gritty ground
		const FVector C(-400, 0, 0);
		for (int32 i = 0; i < 20; ++i)
		{
			const float A = R.FRand() * TWO_PI, Rad = FMath::Sqrt(R.FRand()) * 70.f;
			Flower(C + FVector(FMath::Cos(A) * Rad, FMath::Sin(A) * Rad, 0), R.FRandRange(12, 35), i);
		}
		AddSurfaceProps(C);
		AddSpeckles(FVector(-410, -100, 0), 20.f, 2200);	// clear ground at the patch edge (no leaves/flowers above)
		SpawnZone(FVector(-400, 0, 30), FVector(85, 85, 40), 45, 0.95f);
	}
	SpawnZone(FVector(0, 0, 100), FVector(900, 900, 150), 250);
}

// ---------------------------------------------------------------------------------------------------------------------
// Data-driven shots: -BeeShots=<json file>. New/changed shots need no rebuild.
// {"shots":[{"type":"orbit","seconds":7,"part":1,"center":[-400,0,15],"radius":95,"height":32,"fov":42,"spin":0.12}, ...]}
// types: orbit, chase, walk, surface, wings, threat, fixed (loc,target,fov), wait (not recorded), cmd ("cmd":"console command")
namespace
{
	FVector JVec(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, const FVector& Def)
	{
		const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
		if (O->TryGetArrayField(Key, A) && A && A->Num() == 3) return FVector((*A)[0]->AsNumber(), (*A)[1]->AsNumber(), (*A)[2]->AsNumber());
		return Def;
	}
	float JNum(const TSharedPtr<FJsonObject>& O, const TCHAR* Key, float Def)
	{
		double V = Def;
		O->TryGetNumberField(Key, V);
		return float(V);
	}
}

void ABumblebeeTestDirector::AddShotsFromFile(const FString& Path, int32 Part)
{
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root)
	{
		Log(FString::Printf(TEXT("shots: cannot read %s"), *Path));
		return;
	}
	const TArray<TSharedPtr<FJsonValue>>* Shots = nullptr;
	if (!Root->TryGetArrayField(TEXT("shots"), Shots) || !Shots) return;
	const FVector Patch(-400, 0, 20);
	for (const TSharedPtr<FJsonValue>& V : *Shots)
	{
		const TSharedPtr<FJsonObject> O = V->AsObject();
		if (!O) continue;
		const int32 ShotPart = int32(JNum(O, TEXT("part"), 1.f));
		if (Part != 0 && ShotPart != Part) continue;
		const FString Type = O->GetStringField(TEXT("type"));
		const float Secs = JNum(O, TEXT("seconds"), 5.f);
		const float Fov = JNum(O, TEXT("fov"), 40.f);
		Log(FString::Printf(TEXT("shot plan: %s %.1fs part %d"), *Type, Secs, ShotPart));
		if (Type == TEXT("wait")) { AddWait(Secs); continue; }
		if (Type == TEXT("cmd")) { const FString C = O->GetStringField(TEXT("cmd")); AddCall([this, C]() { Cmd(GetWorld(), *C); }); continue; }
		if (Type == TEXT("orbit"))
		{
			const FVector C = JVec(O, TEXT("center"), Patch);
			const float Rad = JNum(O, TEXT("radius"), 95.f), H = JNum(O, TEXT("height"), 32.f), Spin = JNum(O, TEXT("spin"), 0.12f), A0 = JNum(O, TEXT("angle"), -2.2f);
			AddRecord(Secs, [this, C, Rad, H, Spin, A0, Fov](float T)
			{
				const float A = A0 + T * Spin;
				SetCam(C + FVector(FMath::Cos(A) * Rad, FMath::Sin(A) * Rad, H), C + FVector(0, 0, -5), Fov);
			});
		}
		else if (Type == TEXT("fixed"))
		{
			const FVector L = JVec(O, TEXT("loc"), Patch + FVector(-90, -60, 45)), Tg = JVec(O, TEXT("target"), Patch);
			AddRecord(Secs, [this, L, Tg, Fov](float) { SetCam(L, Tg, Fov); });
		}
		else if (Type == TEXT("chase"))
		{
			const FVector Off = JVec(O, TEXT("offset"), FVector(-26, -18, 12)), Near = JVec(O, TEXT("near"), Patch);
			const float Lerp = JNum(O, TEXT("lerp"), 0.08f);
			AddCall([this, Near]() { FollowBee = FindBee(false, Near, 250.f); CamSmoothLoc = Cam->GetActorLocation(); });
			AddRecord(Secs, [this, Off, Near, Lerp, Fov](float T)
			{
				if (!Swarm) return;
				if (FollowBee == INDEX_NONE) { FollowBee = FindBee(false, Near, 250.f); return; }
				const FVector P = Swarm->GetBeeTransform(FollowBee).GetLocation();
				CamSmoothLoc = FMath::Lerp(T < 0.05f ? P + Off : CamSmoothLoc, P + Off, Lerp);
				SetCam(CamSmoothLoc, P, Fov);
			});
		}
		else if (Type == TEXT("walk"))
		{
			const FVector Spot = JVec(O, TEXT("spot"), FVector(-410, -100, 0)), Off = JVec(O, TEXT("offset"), FVector(-7, -9, 7));
			const float Lerp = JNum(O, TEXT("lerp"), 0.05f);
			const int32 Walkers = int32(JNum(O, TEXT("walkers"), 5.f));
			AddCall([this, Spot, Walkers]() { if (Swarm) Swarm->RelocateBeesTo(Spot, 10.f, Walkers, true); });
			AddWait(1.5f);
			AddCall([this, Spot]()
			{
				FollowBee = FindBeeWhere(Spot, 60.f, [this](int32 i) { return Swarm->IsBeeWalking(i); });
				if (FollowBee == INDEX_NONE) FollowBee = FindBee(true, Spot, 60.f);
				if (FollowBee != INDEX_NONE) CamSmoothLoc = Swarm->GetBeeTransform(FollowBee).GetLocation();
			});
			AddRecord(Secs, [this, Off, Lerp, Fov](float)
			{
				if (!Swarm || FollowBee == INDEX_NONE) return;
				const FVector P = Swarm->GetBeeTransform(FollowBee).GetLocation();
				CamSmoothLoc = FMath::Lerp(CamSmoothLoc, P, Lerp);
				CamLookSmooth = FMath::Lerp(CamLookSmooth.IsZero() ? P : CamLookSmooth, P, 0.3f);
				SetCam(CamSmoothLoc + Off, CamLookSmooth + FVector(0, 0, 0.6f), Fov);
			});
		}
		else if (Type == TEXT("surface"))
		{
			const float Dist = JNum(O, TEXT("dist"), 14.f);
			AddCall([this, Patch]()
			{
				FollowBee = FindBeeWhere(Patch, 150.f, [this](int32 i) { return Swarm->IsBeeLanded(i) && Swarm->GetBeeSurfaceNormal(i).Z < 0.8f; });
				if (FollowBee != INDEX_NONE) CamSmoothLoc = Swarm->GetBeeTransform(FollowBee).GetLocation();
			});
			AddRecord(Secs, [this, Dist, Fov](float)
			{
				if (!Swarm || FollowBee == INDEX_NONE) return;
				const FVector P = Swarm->GetBeeTransform(FollowBee).GetLocation();
				const FVector N = Swarm->IsBeeLanded(FollowBee) ? Swarm->GetBeeSurfaceNormal(FollowBee) : FVector::UpVector;
				CamSmoothLoc = FMath::Lerp(CamSmoothLoc, P, 0.05f);
				const FVector Side = FVector::CrossProduct(N, FVector::UpVector).GetSafeNormal();
				SetCam(CamSmoothLoc + N * Dist + Side * Dist * 0.55f + FVector(0, 0, 4.f), CamSmoothLoc, Fov);
			});
		}
		else if (Type == TEXT("wings"))
		{
			const float Dist = JNum(O, TEXT("dist"), 14.f);
			AddCall([this, Patch]() { FollowBee = FindBee(false, Patch, 200.f); if (FollowBee != INDEX_NONE) CamSmoothLoc = Swarm->GetBeeTransform(FollowBee).GetLocation(); });
			AddRecord(Secs, [this, Patch, Dist, Fov](float T)
			{
				if (!Swarm) return;
				if (FollowBee == INDEX_NONE) { FollowBee = FindBee(false, Patch, 200.f); return; }
				const FTransform B = Swarm->GetBeeTransform(FollowBee);
				CamSmoothLoc = FMath::Lerp(CamSmoothLoc, B.GetLocation(), 0.25f);
				FVector F = B.GetRotation().GetForwardVector();
				F.Z = 0.f;
				F = F.IsNearlyZero() ? FVector::ForwardVector : F.GetSafeNormal();
				CamSideSmooth = FMath::Lerp(T < 0.05f ? FVector::CrossProduct(FVector::UpVector, F) : CamSideSmooth, FVector::CrossProduct(FVector::UpVector, F), 0.05f).GetSafeNormal();
				SetCam(CamSmoothLoc + CamSideSmooth * Dist + FVector(0, 0, 2.f), CamSmoothLoc, Fov);
			});
		}
		else if (Type == TEXT("threat"))
		{
			AddCall([this]() { if (Swarm && ThreatActor) Swarm->AddThreatActor(ThreatActor); });
			AddRecord(Secs, [this, Patch, Fov](float T)
			{
				if (ThreatActor) ThreatActor->SetActorLocation(Patch + FVector(-260.f + T * 95.f, 10.f, 15.f));
				SetCam(Patch + FVector(-20, -170, 55), Patch + FVector(0, 0, 5), Fov);
			});
		}
	}
}

// Trajectory log: every bee near the patch, every frame at 60 Hz, for checking smoothness numerically.
void ABumblebeeTestDirector::BuildTrajScene()
{
	FApp::SetUseFixedTimeStep(true);
	FApp::SetFixedDeltaTime(1.0 / 60.0);
	BuildGarden(true);
	const FVector Patch(-400, 0, 20);
	AddWaitShaders(5.f);
	AddCall([this, Patch]() { SetCam(Patch + FVector(-90, -60, 45), Patch, 45.f); });
	AddWait(15.f);
	AddCall([this]() { TrajCsv = TEXT("frame,bee,flying,x,y,z,qx,qy,qz,qw,scale\n"); FrameIndex = 0; });
	Steps.Add([this, Patch](float) mutable
	{
		for (int32 i = 0; Swarm && i < Swarm->GetNumBees(); ++i)
		{
			const FTransform T = Swarm->GetBeeTransform(i);
			if (FVector::DistSquared(T.GetLocation(), Patch) > FMath::Square(450.f)) continue;
			const FQuat Q = T.GetRotation();
			TrajCsv += FString::Printf(TEXT("%d,%d,%d,%.4f,%.4f,%.4f,%.6f,%.6f,%.6f,%.6f,%.3f\n"), FrameIndex, i, Swarm->IsBeeFlying(i) ? 1 : 0,
				T.GetLocation().X, T.GetLocation().Y, T.GetLocation().Z, Q.X, Q.Y, Q.Z, Q.W, T.GetScale3D().X);
		}
		++FrameIndex;
		return FrameIndex >= 1500;		// 25 s
	});
	AddCall([this]()
	{
		FFileHelper::SaveStringToFile(TrajCsv, *(OutDir / TEXT("traj.csv")));
		Log(FString::Printf(TEXT("traj frames=%d bytes=%d %s"), FrameIndex, TrajCsv.Len(), *StatsJson()));
		TrajCsv.Empty();
	});
}

void ABumblebeeTestDirector::BuildVideoScene()
{
	FApp::SetUseFixedTimeStep(true);
	FApp::SetFixedDeltaTime(1.0 / 30.0);
	BuildGarden(true);
	const FVector Patch(-400, 0, 20);
	ThreatCenter = Patch;
	ThreatActor = SpawnBox(Patch + FVector(-300, 0, 15), FVector(25, 25, 30), FLinearColor(0.15f, 0.12f, 0.35f), TEXT("Sphere"), FRotator::ZeroRotator, true);

	AddWaitShaders(8.f);
	// warm-up: look at everything once so instanced/LOD permutations compile and textures stream
	AddCall([this, Patch]() { SetCam(Patch + FVector(-90, -60, 45), Patch, 45.f); });
	AddShot(TEXT("warmup_patch"), 4.f);
	AddCall([this, Patch]() { SetCam(Patch + FVector(20, -25, 6), Patch + FVector(0, 0, -15), 30.f); });
	AddShot(TEXT("warmup_close"), 3.f);
	AddCall([this, Patch]() { SetCam(Patch + FVector(-90, -60, 45), Patch, 45.f); });
	AddShot(TEXT("warmup_patch2"), 8.f);
	AddWait(12.f);		// let the swarm reach its steady mix of flying / walking / resting
	AddCall([this]() { Log(TEXT("tally_start ") + SurfaceTally(FVector(-400, 0, 0), 150.f) + TEXT(" ") + StatsJson()); });
	// -BeeVideoPart=1|2|3 records a third of the shots per process (screenshot readback memory grows per frame)
	int32 Part = 0;
	FParse::Value(FCommandLine::Get(), TEXT("BeeVideoPart="), Part);
	Log(FString::Printf(TEXT("video part %d"), Part));
	FString ShotFile;
	const bool bShotFile = FParse::Value(FCommandLine::Get(), TEXT("BeeShots="), ShotFile);
	if (bShotFile) AddShotsFromFile(ShotFile, Part);
	if (!bShotFile && (Part == 0 || Part == 1))
	{

	// 1. slow orbit around the flower patch
	AddRecord(7.f, [this, Patch](float T)
	{
		const float A = -2.2f + T * 0.12f;
		SetCam(Patch + FVector(FMath::Cos(A) * 95.f, FMath::Sin(A) * 95.f, 32.f), Patch + FVector(0, 0, -5), 42.f);
	});
	// 2. follow one bee through its flight legs and into a landing (it never stops in the air)
	AddCall([this, Patch]() { FollowBee = FindBee(false, Patch, 200.f); CamSmoothLoc = Cam->GetActorLocation(); Log(FString::Printf(TEXT("chase bee %d"), FollowBee)); });
	AddRecord(10.f, [this, Patch](float T)
	{
		if (!Swarm) return;
		if (FollowBee == INDEX_NONE || (!Swarm->IsBeeFlying(FollowBee) && T < 0.5f)) FollowBee = FindBee(false, Patch, 200.f);
		if (FollowBee == INDEX_NONE) return;
		const FTransform B = Swarm->GetBeeTransform(FollowBee);
		const FVector Want = B.GetLocation() + FVector(-26.f, -18.f, 12.f);
		CamSmoothLoc = FMath::Lerp(T < 0.05f ? Want : CamSmoothLoc, Want, 0.08f);
		SetCam(CamSmoothLoc, B.GetLocation(), 38.f);
	});
	}
	if (!bShotFile && (Part == 0 || Part == 2))
	{
	// 3. walking close-up on gritty ground: the camera barely follows, so the walking speed and the stepping are readable
	AddCall([this, Patch]()
	{
		const FVector Spot(-410, -100, 0);
		const int32 N = Swarm ? Swarm->RelocateBeesTo(Spot, 12.f, 5, true) : 0;
		Log(FString::Printf(TEXT("walkers placed %d"), N));
	});
	AddWait(1.5f);
	AddCall([this, Patch]()
	{
		const FVector Spot(-410, -100, 0);
		FollowBee = FindBeeWhere(Spot, 60.f, [this](int32 i) { return Swarm->IsBeeWalking(i); });
		if (FollowBee == INDEX_NONE) FollowBee = FindBee(true, Spot, 60.f);
		Log(FString::Printf(TEXT("walk bee %d at %s"), FollowBee, FollowBee != INDEX_NONE ? *Swarm->GetBeeTransform(FollowBee).GetLocation().ToString() : TEXT("-")));
		if (FollowBee != INDEX_NONE) CamSmoothLoc = Swarm->GetBeeTransform(FollowBee).GetLocation();
	});
	AddRecord(8.f, [this](float T)
	{
		if (!Swarm || FollowBee == INDEX_NONE) return;
		const FTransform B = Swarm->GetBeeTransform(FollowBee);
		// camera trails slowly (so the grit slides past at the walking speed) but always looks at the bee
		CamSmoothLoc = FMath::Lerp(CamSmoothLoc, B.GetLocation(), 0.05f);
		CamLookSmooth = FMath::Lerp(T < 0.05f ? B.GetLocation() : CamLookSmooth, B.GetLocation(), 0.3f);
		SetCam(CamSmoothLoc + FVector(-7.f, -9.f, 7.f), CamLookSmooth + FVector(0, 0, 0.6f), 34.f);
	});
	// 4. bees on walls, slopes and leaves
	AddCall([this, Patch]()
	{
		FollowBee = FindBeeWhere(Patch, 150.f, [this](int32 i) { const FVector N = Swarm->GetBeeSurfaceNormal(i); return Swarm->IsBeeLanded(i) && N.Z < 0.8f; });
		Log(FString::Printf(TEXT("non-flat bee %d normal %s"), FollowBee, FollowBee != INDEX_NONE ? *Swarm->GetBeeSurfaceNormal(FollowBee).ToString() : TEXT("-")));
		if (FollowBee != INDEX_NONE) CamSmoothLoc = Swarm->GetBeeTransform(FollowBee).GetLocation();
	});
	AddRecord(5.f, [this](float T)
	{
		if (!Swarm || FollowBee == INDEX_NONE) return;
		const FTransform B = Swarm->GetBeeTransform(FollowBee);
		const FVector N = Swarm->IsBeeLanded(FollowBee) ? Swarm->GetBeeSurfaceNormal(FollowBee) : FVector::UpVector;
		CamSmoothLoc = FMath::Lerp(CamSmoothLoc, B.GetLocation(), 0.05f);
		const FVector Side = FVector::CrossProduct(N, FVector::UpVector).GetSafeNormal();
		SetCam(CamSmoothLoc + N * 14.f + Side * 8.f + FVector(0, 0, 4.f), CamSmoothLoc, 36.f);
	});
	}
	if (!bShotFile && (Part == 0 || Part == 3))
	{
	// 5. wings: side view of a flying bee
	AddCall([this, Patch]() { FollowBee = FindBee(false, Patch, 200.f); if (FollowBee != INDEX_NONE) CamSmoothLoc = Swarm->GetBeeTransform(FollowBee).GetLocation(); });
	AddRecord(5.f, [this, Patch](float T)
	{
		if (!Swarm) return;
		if (FollowBee == INDEX_NONE) { FollowBee = FindBee(false, Patch, 200.f); return; }
		const FTransform B = Swarm->GetBeeTransform(FollowBee);
		CamSmoothLoc = FMath::Lerp(CamSmoothLoc, B.GetLocation(), 0.25f);
		// level side view: perpendicular to the bee's heading in the horizontal plane
		FVector Fwd = B.GetRotation().GetForwardVector();
		Fwd.Z = 0.f;
		Fwd = Fwd.IsNearlyZero() ? FVector::ForwardVector : Fwd.GetSafeNormal();
		CamSideSmooth = FMath::Lerp(T < 0.05f ? FVector::CrossProduct(FVector::UpVector, Fwd) : CamSideSmooth, FVector::CrossProduct(FVector::UpVector, Fwd), 0.05f).GetSafeNormal();
		SetCam(CamSmoothLoc + CamSideSmooth * 14.f + FVector(0, 0, 2.f), CamSmoothLoc, 32.f);
	});
	// 6. something walks through the patch
	AddCall([this]() { if (Swarm && ThreatActor) Swarm->AddThreatActor(ThreatActor); });
	AddRecord(6.f, [this, Patch](float T)
	{
		if (ThreatActor) ThreatActor->SetActorLocation(Patch + FVector(-260.f + T * 95.f, 10.f, 15.f));
		SetCam(Patch + FVector(-20, -170, 55), Patch + FVector(0, 0, 5), 50.f);
	});
	}
	AddCall([this]()
	{
		if (ShotHandle.IsValid()) UGameViewportClient::OnScreenshotCaptured().Remove(ShotHandle);
		ShotHandle.Reset();
		FApp::SetUseFixedTimeStep(false);
		Log(TEXT("tally_end ") + SurfaceTally(FVector(-400, 0, 0), 150.f));
		Log(FString::Printf(TEXT("video frames=%d %s"), FrameIndex, *StatsJson()));
	});
}

void ABumblebeeTestDirector::BuildSizeScene()
{
	SpawnLighting();
	SpawnBox(FVector(0, 0, -5), FVector(4000, 4000, 10), FLinearColor(0.05f, 0.08f, 0.03f));
	USkeletalMesh* Manny = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	Log(FString::Printf(TEXT("mannequin=%s"), Manny ? TEXT("ok") : TEXT("MISSING")));
	FVector Hand(10, -60, 100);
	if (Manny)
	{
		ASkeletalMeshActor* A = GetWorld()->SpawnActor<ASkeletalMeshActor>(FVector::ZeroVector, FRotator(0, 90, 0));
		A->GetSkeletalMeshComponent()->SetSkeletalMeshAsset(Manny);
		A->GetSkeletalMeshComponent()->RefreshBoneTransforms();
		Hand = A->GetSkeletalMeshComponent()->GetSocketLocation(TEXT("hand_r"));
		const FBoxSphereBounds B = A->GetSkeletalMeshComponent()->Bounds;
		Log(FString::Printf(TEXT("mannequin height %.1f cm, hand_r %s"), B.BoxExtent.Z * 2.f, *Hand.ToString()));
	}
	// a flower stalk right next to the hand with a landed bee on it, plus the normal swarm around the feet
	const FVector Stalk = Hand + FVector(0, -6, 0);
	SpawnBox(FVector(Stalk.X, Stalk.Y, Stalk.Z * 0.5f), FVector(0.8f, 0.8f, Stalk.Z), FLinearColor(0.06f, 0.18f, 0.03f), TEXT("Cylinder"));
	SpawnBox(FVector(Stalk.X, Stalk.Y, Stalk.Z + 0.6f), FVector(7, 7, 1.2f), FLinearColor(0.75f, 0.18f, 0.45f), TEXT("Cylinder"));
	UStaticMesh* Landed = LoadObject<UStaticMesh>(nullptr, *(FString(BeeFolder) / TEXT("SM_Bumblebee_Landed")));
	if (Landed)
	{
		const float S = 0.75f;		// default worker size (same as the swarm's BeeScale)
		const FTransform T(FRotator(0, 30, 0), FVector(Stalk.X, Stalk.Y, Stalk.Z + 1.2f), FVector(S));
		AStaticMeshActor* A = GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(), T);
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(Landed);
		A->FinishSpawning(T);
	}
	FRandomStream R(3);
	for (int32 i = 0; i < 14; ++i)
	{
		const FVector P(R.FRandRange(-90, 90), R.FRandRange(-90, 90), 0);
		const float H = R.FRandRange(15, 45);
		SpawnBox(P + FVector(0, 0, H * 0.5f), FVector(0.8f, 0.8f, H), FLinearColor(0.06f, 0.18f, 0.03f), TEXT("Cylinder"));
		SpawnBox(P + FVector(0, 0, H + 0.6f), FVector(7, 7, 1.2f), FLinearColor(0.85f, 0.72f, 0.08f), TEXT("Cylinder"));
	}
	SpawnZone(FVector(0, 0, 30), FVector(100, 100, 40), 25, 1.f);

	AddWaitShaders(8.f);
	AddCall([this]() { SetCam(FVector(380, -260, 120), FVector(0, 0, 85), 40.f); });
	AddShot(TEXT("01_full_body"), 3.f);
	AddCall([this, Hand, Stalk]() { SetCam(Stalk + FVector(30, -45, 12), (Hand + Stalk) * 0.5f, 35.f); });
	AddShot(TEXT("02_hand_and_bee"), 1.5f);
	AddCall([this]() { SetCam(FVector(150, -120, 35), FVector(0, 0, 25), 40.f); });
	AddShot(TEXT("03_feet_level"), 1.5f);
	AddCall([this]() { Log(TEXT("size stats ") + StatsJson()); });
}
