#include "BirdTestDirector.h"
#include "Bird.h"
#include "BirdFlock.h"
#include "BirdZone.h"
#include "BirdFish.h"
#include "EngineUtils.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/DamageType.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "ShaderCompiler.h"
#include "ContentStreaming.h"
#include "UnrealClient.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "RHI.h"
#include "RenderCore.h"
#include "RenderingThread.h"
#include "EngineUtils.h"

ABirdTestDirector::ABirdTestDirector()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostUpdateWork;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ABirdTestDirector::Log(const FString& Line)
{
	UE_LOG(LogTemp, Display, TEXT("BIRDTEST %s"), *Line);
	Report += Line + TEXT("\n");
	FFileHelper::SaveStringToFile(Report, *(OutDir / TEXT("report.txt")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void ABirdTestDirector::SetCam(const FVector& Loc, const FVector& Target, float Fov)
{
	if (!Cam) return;
	CamLoc = Loc;
	CamLook = Target;
	bCamInit = true;
	Cam->SetActorLocationAndRotation(Loc, (Target - Loc).Rotation());
	Cam->GetCameraComponent()->SetFieldOfView(Fov);
}

void ABirdTestDirector::SmoothCam(const FVector& Loc, const FVector& Target, float Fov, float Dt, float Rate)
{
	if (!bCamInit) { SetCam(Loc, Target, Fov); return; }
	CamLoc = FMath::VInterpTo(CamLoc, Loc, Dt, Rate);
	CamLook = FMath::VInterpTo(CamLook, Target, Dt, Rate * 1.5f);
	Cam->SetActorLocationAndRotation(CamLoc, (CamLook - CamLoc).Rotation());
	Cam->GetCameraComponent()->SetFieldOfView(Fov);
}

AActor* ABirdTestDirector::SpawnBox(const FVector& Loc, const FVector& SizeCm, const FLinearColor& Color, const TCHAR* Shape, const FRotator& Rot, bool bMovable)
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

void ABirdTestDirector::SpawnLighting()
{
	FActorSpawnParameters P;
	const FTransform Sun(FRotator(-40.f, 35.f, 0.f), FVector(0, 0, 500));
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

void ABirdTestDirector::BuildBeach()
{
	SpawnLighting();
	SpawnBox(FVector(0, 9250, -5), FVector(40000, 21500, 10), FLinearColor(0.42f, 0.36f, 0.25f));		// sand (shore at y = -1500)
	SpawnBox(FVector(0, -11000, -120), FVector(40000, 19000, 10), FLinearColor(0.25f, 0.22f, 0.15f));	// sea floor
	if (AActor* Sea = SpawnBox(FVector(0, -11000, -15), FVector(40000, 19000, 1), FLinearColor(0.03f, 0.11f, 0.16f), TEXT("Plane")))
		Sea->Tags.Add(TEXT("BirdWater"));															// water surface (a plane, like the game's)
	for (int32 i = 0; i < 4; ++i)																	// posts on the shore
		SpawnBox(FVector(-450.f + i * 300.f, -1150.f, 60.f), FVector(20, 20, 120), FLinearColor(0.2f, 0.15f, 0.1f), TEXT("Cylinder"));
	for (int32 i = 0; i < 9; ++i)																	// fence posts (kingfisher perches)
		SpawnBox(FVector(-600.f + i * 220.f, 700.f, 65.f), FVector(22, 22, 130), FLinearColor(0.2f, 0.15f, 0.1f), TEXT("Cylinder"));
	SpawnBox(FVector(300, 700, 128), FVector(1900, 6, 6), FLinearColor(0.2f, 0.15f, 0.1f));			// rail along the posts
	SpawnBox(FVector(-1200, -300, 30), FVector(220, 160, 60), FLinearColor(0.3f, 0.3f, 0.3f));		// rocks
	SpawnBox(FVector(1400, -500, 40), FVector(160, 200, 80), FLinearColor(0.32f, 0.31f, 0.3f));
	SpawnBox(FVector(200, 1700, 90), FVector(1600, 50, 180), FLinearColor(0.45f, 0.43f, 0.4f));		// sea wall
	SpawnBox(FVector(-2000, 1200, 150), FVector(500, 400, 300), FLinearColor(0.5f, 0.45f, 0.4f));		// shed (roof perch)
}

ABirdZone* ABirdTestDirector::Zone(const FVector& C, const FVector& E, EBirdSpecies Sp, int32 Count, int32 Seed, float AirTime)
{
	const FTransform T(C);
	ABirdZone* Z = GetWorld()->SpawnActorDeferred<ABirdZone>(ABirdZone::StaticClass(), T);
	Z->BoxExtent = E;
	Z->Species = Sp;
	Z->BirdCount = Count;
	Z->Seed = Seed;
	Z->AirTime = AirTime;
	Z->ActivationDistance = 0.f;
	Z->FinishSpawning(T);
	Flock = ABirdFlock::Find(this, true);
	return Z;
}

ABird* ABirdTestDirector::FindBird(EBirdSpecies Sp, TFunctionRef<bool(const ABird*)> Pred, const FVector& Near) const
{
	if (!Flock) return nullptr;
	ABird* Best = nullptr;
	float BestD = 1e30f;
	for (ABird* B : Flock->GetBirds())
	{
		if (!B || B->GetSpecies() != Sp || B->IsDead() || !Pred(B)) continue;
		const float D = Near.IsZero() ? 0.f : FVector::DistSquared(B->GetPos(), Near);
		if (!Best || D < BestD) { Best = B; BestD = D; }
	}
	return Best;
}

FString ABirdTestDirector::StatsJson() const
{
	if (!Flock) return TEXT("{}");
	const FBirdFlockStats S = Flock->GetStats();
	return FString::Printf(TEXT("{\"birds\":%d,\"perched\":%d,\"walking\":%d,\"flying\":%d,\"dead\":%d,\"feathers\":%d,\"takeoffs\":%d,\"landings\":%d,\"walks\":%d,\"cries\":%d,\"kills\":%d,\"min_sep_ratio\":%.3f,\"run_min_sep\":%.3f,\"sep_corrections\":%d,\"scrapes\":%d,\"aborted_landings\":%d,\"turns\":%d,\"shuffles\":%d,\"bleeds\":%d,\"avg_ms\":%.4f,\"max_ms\":%.4f}"),
		S.Birds, S.Perched, S.Walking, S.Flying, S.Dead, S.Feathers, S.Takeoffs, S.Landings, S.Walks, S.Cries, S.Kills, S.MinSeparationRatio, MinSepRatio, S.SeparationCorrections, S.Scrapes, S.AbortedLandings, S.Turns, S.Shuffles, S.Bleeds, S.AvgTickMs, S.MaxTickMs);
}

FVector ABirdTestDirector::ClearCamPos(const FVector& Target, float Yaw, float PitchDeg, float Dist) const
{
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdTestCam), false);
	if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
	if (Mover) Q.AddIgnoredActor(Mover);
	for (int32 k = 0; k < 12; ++k)
	{
		const float Y = Yaw + (k % 2 ? 1.f : -1.f) * 30.f * ((k + 1) / 2);
		const float P = PitchDeg + (k >= 8 ? 15.f : 0.f);
		const FVector CamPos = Target - FRotator(-P, Y, 0.f).Vector() * Dist;		// P = camera elevation above the target
		FHitResult H;
		if (!GetWorld()->LineTraceSingleByChannel(H, Target, CamPos, ECC_Visibility, Q)
			&& !GetWorld()->OverlapAnyTestByChannel(CamPos, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(10.f), Q)) return CamPos;
	}
	return Target - FRotator(-(PitchDeg + 40.f), Yaw, 0.f).Vector() * Dist;
}

void ABirdTestDirector::FrameBird(ABird* B, float Dist, float YawOff, float PitchDeg, float Fov, float ZOff)
{
	if (!B) return;
	const FVector C = B->GetPos() + FVector(0, 0, ZOff);
	SetCam(ClearCamPos(C, B->GetActorRotation().Yaw + YawOff, PitchDeg, Dist), C, Fov);
}

// ---------------------------------------------------------------------------------------------------- steps
void ABirdTestDirector::AddWaitShaders(float MinSeconds)
{
	Steps.Add([this, MinSeconds, Quiet = 0.f](float Dt) mutable
	{
		const int32 Jobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		Quiet = Jobs > 0 ? 0.f : Quiet + Dt;
		if (FMath::Fmod(StepTime, 15.f) < Dt) Log(FString::Printf(TEXT("waiting shaders: %d jobs, t=%.0fs"), Jobs, StepTime));
		return (StepTime >= MinSeconds && Quiet > 3.f) || StepTime > 1500.f;
	});
}

void ABirdTestDirector::AddWait(float Seconds)
{
	Steps.Add([this, Seconds](float) { return StepTime >= Seconds; });
}

void ABirdTestDirector::AddShot(const FString& Name, float Settle)
{
	Steps.Add([this, Name, Settle, bRequested = false, bStreamed = false](float) mutable
	{
		const int32 Jobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		if (!bRequested && Jobs > 0 && StepTime < 600.f) { StepTime = FMath::Min(StepTime, 0.f); return false; }
		if (!bStreamed) { IStreamingManager::Get().StreamAllResources(2.0f); bStreamed = true; StepTime = 0.f; return false; }
		if (StepTime < Settle) return false;
		if (!bRequested)
		{
			FScreenshotRequest::RequestScreenshot(OutDir / (Name + TEXT(".png")), false, false);
			bRequested = true;
			Log(FString::Printf(TEXT("shot %s %s"), *Name, *StatsJson()));
			return false;
		}
		return StepTime > Settle + 0.5f;
	});
}

void ABirdTestDirector::AddCall(TFunction<void()> Fn)
{
	Steps.Add([Fn](float) { Fn(); return true; });
}

void ABirdTestDirector::OnShotCaptured(int32 W, int32 H, const TArray<FColor>& Colors)
{
	if (!bRecording) return;
	IImageWrapperModule& M = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
	TSharedPtr<IImageWrapper> Img = M.CreateImageWrapper(EImageFormat::JPEG);
	if (!Img.IsValid() || Colors.Num() != W * H) return;
	TArray<FColor> Opaque = Colors;
	for (FColor& C : Opaque) C.A = 255;
	Img->SetRaw(Opaque.GetData(), Opaque.Num() * sizeof(FColor), W, H, ERGBFormat::BGRA, 8);
	FFileHelper::SaveArrayToFile(Img->GetCompressed(90), *(OutDir / FString::Printf(TEXT("frame_%05d.jpg"), FrameIndex++)));
}

void ABirdTestDirector::AddRecord(float Seconds, TFunction<void(float, float)> CamFn)
{
	Steps.Add([this, Seconds, CamFn](float Dt) mutable
	{
		if (!ShotHandle.IsValid()) ShotHandle = UGameViewportClient::OnScreenshotCaptured().AddUObject(this, &ABirdTestDirector::OnShotCaptured);
		bRecording = true;
		CamFn(StepTime, Dt);
		FScreenshotRequest::RequestScreenshot(false);
		if (StepTime >= Seconds || bEndRecord)
		{
			bRecording = false;
			bEndRecord = false;
			Log(FString::Printf(TEXT("recorded segment, frames %d, process %.0f MB %s"), FrameIndex, FPlatformMemory::GetStats().UsedPhysical / 1048576.0, *StatsJson()));
			return true;
		}
		return false;
	});
}

// ---------------------------------------------------------------------------------------------------- frame
void ABirdTestDirector::BeginPlay()
{
	Super::BeginPlay();
	FString Out;
	OutDir = FParse::Value(FCommandLine::Get(), TEXT("BeeTestOut="), Out) ? Out : FPaths::ProjectSavedDir() / TEXT("BirdTest") / Scene;
	IFileManager::Get().MakeDirectory(*OutDir, true);
	BaseMat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (GEngine) GEngine->Exec(GetWorld(), TEXT("t.MaxFPS 0"));
	Log(FString::Printf(TEXT("scene=%s"), *Scene));
	FActorSpawnParameters P;
	Cam = GetWorld()->SpawnActor<ACameraActor>(FVector(0, -1500, 400), FRotator::ZeroRotator, P);
	Cam->GetCameraComponent()->bConstrainAspectRatio = false;
	Cam->GetCameraComponent()->PostProcessSettings.bOverride_AutoExposureSpeedUp = true;
	Cam->GetCameraComponent()->PostProcessSettings.AutoExposureSpeedUp = 20.f;
	Cam->GetCameraComponent()->PostProcessSettings.bOverride_AutoExposureSpeedDown = true;
	Cam->GetCameraComponent()->PostProcessSettings.AutoExposureSpeedDown = 20.f;
	if (Scene == TEXT("video")) BuildVideoScene();
	else if (Scene == TEXT("perf")) BuildPerfScene();
	else if (Scene == TEXT("leaves") || Scene == TEXT("leavesmap") || Scene == TEXT("wind")) BuildLeafScene();
	else BuildTestScene();
	AddCall([this]() { Log(TEXT("done ") + StatsJson()); FGenericPlatformMisc::RequestExit(false, TEXT("BirdTest")); });
}

void ABirdTestDirector::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	TotalTime += DeltaSeconds;
	StepTime += DeltaSeconds;
	FrameMsSum += DeltaSeconds * 1000.0;
	GameMsSum += FPlatformTime::ToMilliseconds(GGameThreadTime);
	++FrameSamples;
	if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (APawn* Pn = PC->GetPawn()) { PC->UnPossess(); Pn->Destroy(); }
		if (Cam && PC->GetViewTarget() != Cam) PC->SetViewTarget(Cam);
	}
	if (Flock) MinSepRatio = FMath::Min(MinSepRatio, Flock->GetStats().MinSeparationRatio);
	if (Mover && MoverTime > 0.f)
	{
		MoverTime -= DeltaSeconds;
		if (bHoming && Subject && !Subject->IsDead())
		{
			// the target may shuffle or turn while the spear is on its way: keep it on line (test harness only)
			const FVector To = (Subject->GetPos() + FVector(0, 0, 3) - Mover->GetActorLocation()).GetSafeNormal();
			if (FVector::DotProduct(To, MoverVel.GetSafeNormal()) > 0.5f)
			{
				MoverVel = To * MoverVel.Size();
				Mover->SetActorRotation(To.Rotation() + FRotator(-90, 0, 0));
			}
		}
		Mover->SetActorLocation(Mover->GetActorLocation() + MoverVel * DeltaSeconds);
	}
	if (TotalTime > 2400.f)
	{
		Log(TEXT("timeout"));
		FGenericPlatformMisc::RequestExit(false, TEXT("BirdTest timeout"));
		return;
	}
	while (Steps.IsValidIndex(StepIndex))
	{
		if (!Steps[StepIndex](DeltaSeconds)) break;
		++StepIndex;
		StepTime = 0.f;
	}
}

// ---------------------------------------------------------------------------------------------------- scenes
void ABirdTestDirector::BuildTestScene()
{
	FApp::SetUseFixedTimeStep(true);
	FApp::SetFixedDeltaTime(1.0 / 60.0);
	BuildBeach();
	Zone(FVector(0, 0, 300), FVector(2600, 2600, 300), EBirdSpecies::Gull, 8, 11, 0.45f);
	Zone(FVector(300, 700, 150), FVector(1300, 500, 150), EBirdSpecies::Kingfisher, 4, 22, 0.35f);
	AddWaitShaders(8.f);
	AddCall([this]() { SetCam(FVector(-2600, -2600, 900), FVector(0, 300, 100), 60.f); });
	AddShot(TEXT("warmup"), 4.f);
	AddWait(18.f);
	AddShot(TEXT("overview"), 0.5f);
	// close-ups
	AddCall([this]() { Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Perched; }); FrameBird(Subject, 110.f, 90.f, 6.f, 40.f); });
	AddShot(TEXT("gull_perched_side"), 0.6f);
	AddCall([this]() { FrameBird(Subject, 120.f, 35.f, 12.f, 40.f); });
	AddShot(TEXT("gull_perched_34"), 0.4f);
	AddCall([this]() { if (Subject) { Subject->SetBeakOpen(1.f); Subject->Cry(3.f, 1.f); } FrameBird(Subject, 75.f, 135.f, 5.f, 35.f, 10.f); });
	AddShot(TEXT("gull_beak_open"), 0.8f);
	AddCall([this]() { if (Subject) Subject->SetBeakOpen(-1.f); });
	AddCall([this]() { Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return B->GetState() == EBirdState::Perched; }); FrameBird(Subject, 45.f, 90.f, 5.f, 40.f); });
	AddShot(TEXT("kingfisher_perched"), 0.6f);
	AddCall([this]() { if (Subject) { Subject->SetBeakOpen(1.f); } FrameBird(Subject, 38.f, 130.f, 5.f, 40.f, 3.f); });
	AddShot(TEXT("kingfisher_beak_open"), 0.8f);
	AddCall([this]() { if (Subject) Subject->SetBeakOpen(-1.f); });
	AddCall([this]() { Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Flying; }); bCamInit = false; });
	Steps.Add([this](float Dt)
	{
		if (Subject && !Subject->IsDead())
		{
			const FVector V = Subject->GetBirdVelocity().GetSafeNormal();
			SmoothCam(Subject->GetPos() - V * 260.f + FVector(0, 0, 70.f) + FVector::CrossProduct(V, FVector::UpVector) * 120.f, Subject->GetPos(), 45.f, Dt, 8.f);
		}
		return StepTime > 1.5f;
	});
	AddShot(TEXT("gull_flying"), 0.f);
	AddCall([this]() { Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return B->IsFlying(); }); bCamInit = false; });
	Steps.Add([this](float Dt)
	{
		if (Subject && !Subject->IsDead())
		{
			const FVector V = Subject->GetBirdVelocity().GetSafeNormal();
			SmoothCam(Subject->GetPos() - V * 90.f + FVector(0, 0, 25.f) + FVector::CrossProduct(V, FVector::UpVector) * 40.f, Subject->GetPos(), 45.f, Dt, 8.f);
		}
		return StepTime > 1.2f;
	});
	AddShot(TEXT("kingfisher_flying"), 0.f);
	// orientation self-checks: the mesh faces the actor's forward, and banking right puts the right wing down
	AddCall([this]()
	{
		for (ABird* B : Flock ? Flock->GetBirds() : TArray<ABird*>())
		{
			if (!B || B->IsDead() || !B->Mesh) continue;
			const FVector Head = B->Mesh->GetSocketLocation(TEXT("head")), Pel = B->Mesh->GetSocketLocation(TEXT("pelvis"));
			const FVector HL = B->Mesh->GetSocketLocation(TEXT("hand_l")), HR = B->Mesh->GetSocketLocation(TEXT("hand_r"));
			const FVector Right = B->GetActorRightVector();
			Log(FString::Printf(TEXT("orient species=%d state=%d fwd_dot=%.2f roll=%.1f right_wing_side=%.1f right_minus_left_z=%.1f beak=%d"),
				int32(B->GetSpecies()), int32(B->GetState()), FVector::DotProduct((Head - Pel).GetSafeNormal(), B->GetActorForwardVector()),
				B->GetActorRotation().Roll, FVector::DotProduct(HR - B->GetActorLocation(), Right), HR.Z - HL.Z, 0));
		}
	});

	// trajectory capture: 40 s at 60 Hz, every bird
	AddCall([this]()
	{
		SetCam(FVector(-2600, -2600, 900), FVector(0, 300, 100), 60.f);
		Csv = TEXT("frame,bird,species,state,x,y,z,pitch,yaw,roll\n");
		Frame = 0;
		MinSepRatio = 99.f;
		Log(TEXT("traj_start ") + StatsJson());
	});
	Steps.Add([this](float)
	{
		if (Flock)
		{
			int32 i = 0;
			for (ABird* B : Flock->GetBirds())
			{
				const FRotator R = B->GetActorRotation();
				const FVector P = B->GetActorLocation();
				Csv += FString::Printf(TEXT("%d,%d,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f\n"), Frame, i++, int32(B->GetSpecies()), int32(B->GetState()), P.X, P.Y, P.Z, R.Pitch, R.Yaw, R.Roll);
			}
		}
		return ++Frame >= 2400;
	});
	AddCall([this]()
	{
		FFileHelper::SaveStringToFile(Csv, *(OutDir / TEXT("traj.csv")));
		Csv.Empty();
		Log(TEXT("traj_end ") + StatsJson());
		Log(FString::Printf(TEXT("frame timing {\"frames\":%d,\"frame_ms\":%.3f,\"game_ms\":%.3f}"), FrameSamples, FrameMsSum / FMath::Max(FrameSamples, 1), GameMsSum / FMath::Max(FrameSamples, 1)));
	});
	// threat walks through the gulls
	AddCall([this]()
	{
		Mover = SpawnBox(FVector(-3000, -200, 90), FVector(60, 60, 180), FLinearColor(0.1f, 0.1f, 0.4f), TEXT("Cylinder"), FRotator::ZeroRotator, true);
		Mover->Tags.Add(TEXT("BirdThreat"));
		Cast<AStaticMeshActor>(Mover)->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		MoverVel = FVector(350, 0, 0);
		MoverTime = 16.f;
		Log(TEXT("threat_start ") + StatsJson());
	});
	AddWait(6.f);
	AddCall([this]() { SetCam(Mover->GetActorLocation() + FVector(-900, -1300, 500), Mover->GetActorLocation(), 60.f); });
	AddShot(TEXT("threat_flush"), 0.f);
	AddWait(10.f);
	AddCall([this]() { Log(TEXT("threat_end ") + StatsJson()); if (Mover) Mover->Destroy(); Mover = nullptr; });
	AddWait(15.f);
	AddKillTests(false);
}

void ABirdTestDirector::AddKillTests(bool bVideo)
{
	// 1) spear: a fast thin shaft (no collision, tag "Spear") through a perched gull
	AddCall([this]()
	{
		Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Perched; });
		if (!Subject) { Log(TEXT("spear: no perched gull")); return; }
		const FVector C = Subject->GetPos();
		const FVector Dir = FRotator(0, Subject->GetActorRotation().Yaw + 90.f, 0).Vector();
		Mover = SpawnBox(C - Dir * 700.f + FVector(0, 0, 4), FVector(4, 4, 220), FLinearColor(0.35f, 0.25f, 0.15f), TEXT("Cylinder"), Dir.Rotation() + FRotator(-90, 0, 0), true);
		Cast<AStaticMeshActor>(Mover)->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Mover->Tags.Add(TEXT("Spear"));
		MoverVel = Dir * 2400.f;
		MoverTime = 0.6f;
		SetCam(ClearCamPos(C, Dir.Rotation().Yaw - 90.f, 13.f, 270.f), C, 50.f);
		Log(TEXT("spear_thrown ") + StatsJson());
	});
	AddWait(0.32f);
	AddShot(TEXT("spear_hit"), 0.f);
	AddWait(1.f);
	AddShot(TEXT("spear_1s"), 0.f);
	AddWait(4.f);
	AddCall([this]()
	{
		if (Subject)
		{
			USkeletalMeshComponent* M = Subject->Mesh;
			Log(FString::Printf(TEXT("spear_result dead=%d simulating=%d bodies=%d corpse_min_z=%.2f corpse_max_z=%.2f %s"), Subject->IsDead() ? 1 : 0,
				M->IsSimulatingPhysics() ? 1 : 0, M->Bodies.Num(), M->Bounds.Origin.Z - M->Bounds.BoxExtent.Z, M->Bounds.Origin.Z + M->Bounds.BoxExtent.Z, *StatsJson()));
		}
		if (Mover) Mover->Destroy();
		Mover = nullptr;
	});
	AddShot(TEXT("spear_5s"), 0.f);
	AddCall([this]()
	{
		if (!Subject) return;
		const FVector C = Subject->Mesh->Bounds.Origin;
		SetCam(ClearCamPos(C, Subject->GetActorRotation().Yaw + 60.f, 30.f, 85.f), C, 40.f);
	});
	AddShot(TEXT("spear_blood"), 0.f);
	// 2) heavy hit: a falling 6 kg ball on a perched gull
	AddCall([this]()
	{
		Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Perched; });
		if (!Subject)
		{
			Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return true; });
			if (Subject) Subject->PlaceOnRandomSpot(Subject->GetPos());
		}
		if (!Subject || Subject->GetState() != EBirdState::Perched) { Log(TEXT("rock: no perched gull")); return; }
		const FVector C = Subject->GetPos();
		// the body is created simulating (set before FinishSpawning), then launched
		const FTransform BT(FRotator::ZeroRotator, C + FVector(0, 0, 160), FVector(0.3f));
		AStaticMeshActor* Ball = GetWorld()->SpawnActorDeferred<AStaticMeshActor>(AStaticMeshActor::StaticClass(), BT);
		UStaticMeshComponent* SMC = Ball->GetStaticMeshComponent();
		SMC->SetMobility(EComponentMobility::Movable);
		SMC->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
		SMC->SetCollisionProfileName(TEXT("PhysicsActor"));
		SMC->SetSimulatePhysics(true);
		SMC->BodyInstance.bOverrideMass = true;
		SMC->BodyInstance.SetMassOverride(6.f);
		Ball->FinishSpawning(BT);
		SMC->SetPhysicsLinearVelocity(FVector(0, 0, -900));
		SMC->WakeAllRigidBodies();
		BallComp = SMC;
		BallStart = BT.GetLocation();
		Subject->ProbeDebugFrames = 45;
		SetCam(ClearCamPos(C, Subject->GetActorRotation().Yaw - 110.f, 16.f, 290.f), C, 50.f);
		Log(FString::Printf(TEXT("rock_dropped simulating=%d %s"), SMC->IsSimulatingPhysics() ? 1 : 0, *StatsJson()));
	});
	AddWait(0.25f);
	AddCall([this]()
	{
		if (!BallComp) return;
		Log(FString::Printf(TEXT("rock_fell %.1f cm in 0.25 s, speed %.0f mass %.2f"), float(BallStart.Z - BallComp->GetComponentLocation().Z), float(BallComp->GetPhysicsLinearVelocity().Size()), BallComp->GetMass()));
		// what is the ball resting on?
		FHitResult H;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdTestBall), true);
		Q.AddIgnoredActor(BallComp->GetOwner());
		const FVector P = BallComp->GetComponentLocation();
		if (GetWorld()->LineTraceSingleByChannel(H, P, P - FVector(0, 0, 200), ECC_Visibility, Q))
		{
			Log(FString::Printf(TEXT("rock_below %s / %s at %.1f cm, bird z %.1f"), *GetNameSafe(H.GetActor()), *GetNameSafe(H.GetComponent()), float(P.Z - H.ImpactPoint.Z), Subject ? float(Subject->GetPos().Z) : 0.f));
		}
	});
	AddWait(0.25f);
	AddShot(TEXT("rock_hit"), 0.f);
	AddWait(3.f);
	AddCall([this]()
	{
		if (Subject) Log(FString::Printf(TEXT("rock_result dead=%d simulating=%d corpse_min_z=%.2f %s"), Subject->IsDead() ? 1 : 0, Subject->Mesh->IsSimulatingPhysics() ? 1 : 0,
			Subject->Mesh->Bounds.Origin.Z - Subject->Mesh->Bounds.BoxExtent.Z, *StatsJson()));
	});
	// 3) lethal point damage on a flying kingfisher (falls out of the sky)
	AddCall([this]()
	{
		Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return B->IsFlying(); });
		if (!Subject) Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return true; });
		if (!Subject) { Log(TEXT("damage: no kingfisher")); return; }
		FHitResult H;
		H.ImpactPoint = Subject->GetPos();
		H.Location = H.ImpactPoint;
		UGameplayStatics::ApplyPointDamage(Subject, 50.f, FVector(0.3f, 1, 0.2f).GetSafeNormal(), H, nullptr, this, UDamageType::StaticClass());
		SetCam(Subject->GetPos() + FVector(-300, -300, 120), Subject->GetPos() - FVector(0, 0, 80), 55.f);
		Log(TEXT("damage_applied ") + StatsJson());
	});
	AddWait(0.4f);
	AddShot(TEXT("kingfisher_shot"), 0.f);
	AddWait(5.f);
	AddCall([this]()
	{
		if (Subject) Log(FString::Printf(TEXT("damage_result dead=%d corpse_min_z=%.2f corpse_z=%.2f %s"), Subject->IsDead() ? 1 : 0,
			Subject->Mesh->Bounds.Origin.Z - Subject->Mesh->Bounds.BoxExtent.Z, Subject->Mesh->GetComponentLocation().Z, *StatsJson()));
		if (Subject) SetCam(Subject->Mesh->Bounds.Origin + FVector(-120, -120, 70), Subject->Mesh->Bounds.Origin, 45.f);
	});
	AddShot(TEXT("kingfisher_corpse"), 0.3f);
	// 4) a wound: small damage -> few feathers, flees
	AddCall([this]()
	{
		ABird* B = FindBird(EBirdSpecies::Gull, [](const ABird* X) { return !X->IsFlying(); });
		if (!B) B = FindBird(EBirdSpecies::Gull, [](const ABird* X) { return true; });
		if (B) UGameplayStatics::ApplyDamage(B, 2.f, nullptr, this, UDamageType::StaticClass());
		Log(TEXT("wound_applied ") + StatsJson());
	});
	AddWait(3.f);
	AddCall([this]() { Log(TEXT("wound_result ") + StatsJson()); });
	AddWait(12.f);
	AddCall([this]() { Log(TEXT("feathers_after_15s ") + StatsJson()); });
}

void ABirdTestDirector::BuildVideoScene()
{
	int32 Fps = 30;
	FParse::Value(FCommandLine::Get(), TEXT("BirdVideoFps="), Fps);
	FApp::SetUseFixedTimeStep(true);
	FApp::SetFixedDeltaTime(1.0 / FMath::Clamp(Fps, 10, 240));
	BuildBeach();
	int32 Part = 0;
	FParse::Value(FCommandLine::Get(), TEXT("BirdVideoPart="), Part);
	if (Part != 4)
	{
		Zone(FVector(0, 0, 300), FVector(2600, 2600, 300), EBirdSpecies::Gull, 8, 11, 0.45f);
		Zone(FVector(300, 700, 150), FVector(1300, 500, 150), EBirdSpecies::Kingfisher, 4, 22, 0.35f);
	}
	FParse::Value(FCommandLine::Get(), TEXT("BirdVideoPart="), Part);
	if (Part == 4) { BuildFeedingScene(); return; }
	if (Part == 5)
	{
		// slow motion (1/8 speed: with 60 fps frames this is 480 fps footage) following a kingfisher in flapping flight
		AddWaitShaders(8.f);
		AddWait(6.f);
		AddCall([this]()
		{
			Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return B->GetState() == EBirdState::Flying; });
			if (!Subject)
			{
				Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return true; });
				if (Subject) Subject->Startle(Subject->GetPos() - Subject->GetActorForwardVector() * 300.f);
			}
			bCamInit = false;
		});
		AddWait(2.5f);
		AddCall([this]() { UGameplayStatics::SetGlobalTimeDilation(this, 0.125f); Log(TEXT("slowmo start ") + StatsJson()); });
		AddRecord(2.f, [this](float T, float Dt)
		{
			if (!Subject) return;
			const FVector V = Subject->GetBirdVelocity().GetSafeNormal();
			const FVector Side = FVector::CrossProduct(V, FVector::UpVector).GetSafeNormal();
			SetCam(Subject->GetPos() - V * 70.f + Side * 55.f + FVector(0, 0, 18.f), Subject->GetPos() + V * 10.f, 40.f);
		});
		AddCall([this]() { UGameplayStatics::SetGlobalTimeDilation(this, 1.f); });
		return;
	}
	AddWaitShaders(8.f);
	AddCall([this]() { SetCam(FVector(-2600, -2600, 900), FVector(0, 300, 100), 60.f); });
	AddShot(TEXT("warmup"), 4.f);
	AddWait(Part == 3 ? 40.f : 15.f);
	auto Follow = [this](EBirdSpecies Sp, float Back, float Up, float Side, float Fov)
	{
		return [this, Sp, Back, Up, Side, Fov](float T, float Dt)
		{
			if (!Subject || Subject->IsDead() || !Subject->IsFlying())
			{
				Subject = FindBird(Sp, [](const ABird* B) { return B->GetState() == EBirdState::Flying; }, CamLook);
				if (!Subject) return;
			}
			const FVector V = Subject->GetBirdVelocity().GetSafeNormal();
			SmoothCam(Subject->GetPos() - V * Back + FVector(0, 0, Up) + FVector::CrossProduct(V, FVector::UpVector) * Side, Subject->GetPos(), Fov, Dt, 3.f);
		};
	};
	if (Part == 0 || Part == 1)
	{
		AddRecord(8.f, [this](float T, float) { const float A = -2.4f + T * 0.12f; SetCam(FVector(FMath::Cos(A), FMath::Sin(A), 0.f) * 3200.f + FVector(0, 0, 900), FVector(0, 300, 150), 60.f); });
		AddCall([this]() { Subject = nullptr; bCamInit = false; });
		AddRecord(10.f, Follow(EBirdSpecies::Gull, 320.f, 80.f, 160.f, 50.f));
		AddCall([this]() { Subject = nullptr; bCamInit = false; });
		AddRecord(7.f, Follow(EBirdSpecies::Kingfisher, 110.f, 30.f, 50.f, 50.f));
	}
	if (Part == 0 || Part == 2)
	{
		// a landing, a walk and calls
		AddCall([this]() { Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Landing; }); bCamInit = false; });
		AddRecord(9.f, [this](float T, float Dt)
		{
			if (!Subject) Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Landing; });
			if (!Subject) return;
			const FVector Sp = Subject->HasReservedSpot() ? Subject->GetReservedSpot() : Subject->GetPos();
			SmoothCam(Sp + FVector(-350, -420, 160), FMath::Lerp(Subject->GetPos(), Sp, 0.3f), 50.f, Dt, 2.5f);
		});
		AddCall([this]() { Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Walking; }); if (!Subject) Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Perched; }); bCamInit = false; });
		AddRecord(7.f, [this](float T, float Dt)
		{
			if (!Subject) return;
			if (T > 3.f && T < 3.1f) Subject->Cry(1.6f, 1.f);
			SmoothCam(Subject->GetPos() + FRotator(0, Subject->GetActorRotation().Yaw + 80.f, 0).Vector() * 170.f + FVector(0, 0, 20), Subject->GetPos(), 40.f, Dt, 3.f);
		});
		AddCall([this]() { Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return B->GetState() == EBirdState::Perched; }); bCamInit = false; });
		AddRecord(6.f, [this](float T, float Dt)
		{
			if (!Subject) return;
			if (T > 2.f && T < 2.1f) Subject->Cry(1.2f, 1.f);
			SmoothCam(Subject->GetPos() + FRotator(0, Subject->GetActorRotation().Yaw + 75.f, 0).Vector() * 55.f + FVector(0, 0, 6), Subject->GetPos(), 40.f, Dt, 3.f);
		});
	}
	if (Part == 0 || Part == 3)
	{
		// spear kill + feathers
		AddCall([this]()
		{
			Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return B->GetState() == EBirdState::Perched; });
			if (!Subject)
			{
				Subject = FindBird(EBirdSpecies::Gull, [](const ABird* B) { return true; });
				if (Subject) Subject->PlaceOnRandomSpot(Subject->GetPos());
			}
			if (!Subject) return;
			const FVector C = Subject->GetPos();
			const FVector Dir = FRotator(0, Subject->GetActorRotation().Yaw + 90.f, 0).Vector();
			Mover = SpawnBox(C - Dir * 1600.f + FVector(0, 0, 3), FVector(4, 4, 220), FLinearColor(0.35f, 0.25f, 0.15f), TEXT("Cylinder"), Dir.Rotation() + FRotator(-90, 0, 0), true);
			Cast<AStaticMeshActor>(Mover)->GetStaticMeshComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Mover->Tags.Add(TEXT("Spear"));
			MoverVel = Dir * 2000.f;
			MoverTime = 0.f;
			SetCam(ClearCamPos(C, Dir.Rotation().Yaw - 80.f, 12.f, 340.f), C, 50.f);
		});
		AddRecord(1.f, [](float, float) {});
		AddCall([this]()
		{
			// re-aim at launch: the gull may have shuffled or turned meanwhile
			if (Mover && Subject)
			{
				const FVector To = (Subject->GetPos() + FVector(0, 0, 3) - Mover->GetActorLocation()).GetSafeNormal();
				Mover->SetActorRotation(To.Rotation() + FRotator(-90, 0, 0));
				MoverVel = To * 2000.f;
			}
			bHoming = true;
			MoverTime = 1.6f;
		});
		AddRecord(6.f, [this](float T, float Dt) { if (Subject) SmoothCam(CamLoc, FMath::Lerp(CamLook, Subject->Mesh->Bounds.Origin, 0.5f), 50.f, Dt, 1.f); });
		AddCall([this]() { if (Mover) Mover->Destroy(); Mover = nullptr; bHoming = false; });
		// close on the corpse: entry / exit blood on the plumage
		AddRecord(5.f, [this](float T, float Dt)
		{
			if (!Subject) return;
			const FVector C = Subject->Mesh->Bounds.Origin;
			SmoothCam(ClearCamPos(C, Subject->GetActorRotation().Yaw + 60.f + T * 8.f, 28.f, 95.f), C, 40.f, Dt, 1.5f);
		});
	}
}

// ---------------------------------------------------------------------------------------------------- feeding (video part 4)
void ABirdTestDirector::BuildFeedingScene()
{
	// one kingfisher fishes off the shore, eats on the beach and leaves the rest; a gull comes for it
	Zone(FVector(0, 600, 300), FVector(2200, 1800, 300), EBirdSpecies::Gull, 5, 31, 0.3f);
	{
		const FTransform T(FVector(0, -950, 150));
		ABirdZone* Z = GetWorld()->SpawnActorDeferred<ABirdZone>(ABirdZone::StaticClass(), T);
		Z->BoxExtent = FVector(800, 450, 150);
		Z->Species = EBirdSpecies::Kingfisher;
		Z->BirdCount = 2;
		Z->Seed = 41;
		Z->AirTime = 0.1f;
		Z->ActivationDistance = 0.f;
		Z->bOverrideSettings = true;
		Z->Settings = FBirdSpeciesSettings::Defaults(EBirdSpecies::Kingfisher);
		Z->Settings.FishStruggleTime = 12.f;			// 45 s in the game; shortened for the clip
		Z->Settings.FishingInterval = FVector2D(600.f, 900.f);	// only the fishing trip started below
		Z->Settings.FishingSuccess = 0.75f;
		Z->FinishSpawning(T);
	}
	AddWaitShaders(8.f);
	AddCall([this]() { SetCam(FVector(-1200, -2600, 500), FVector(0, -900, 60), 55.f); });
	AddWait(10.f);
	AddCall([this]()
	{
		Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return B->GetState() == EBirdState::Perched; });
		if (!Subject) Subject = FindBird(EBirdSpecies::Kingfisher, [](const ABird* B) { return true; });
		const bool bOk = Subject && Subject->GoFishing();
		Log(FString::Printf(TEXT("feed fishing_start ok=%d water=%d %s"), bOk ? 1 : 0, Flock && Flock->IsWater(FVector(0, -3000, 0)) ? 1 : 0, *StatsJson()));
		FeedPhase = 0;
		LastTask = -1;
		bCamInit = false;
	});
	AddRecord(150.f, [this](float T, float Dt)
	{
		if (!Subject) { bEndRecord = true; return; }
		const EBirdTask K = Subject->GetTask();
		if (int32(K) != LastTask)
		{
			Log(FString::Printf(TEXT("feed kingfisher task %d at %.2f s (state %d, z %.0f, speed %.0f, pitch %.0f, fish %d)"), int32(K), T, int32(Subject->GetState()), Subject->GetPos().Z,
				Subject->GetBirdVelocity().Size(), Subject->GetActorRotation().Pitch, Subject->GetFish() ? 1 : 0));
			if (LastTask == int32(EBirdTask::FishPeck) && K == EBirdTask::None) FeedPhase = 1;
			LastTask = int32(K);
		}
		if (FeedPhase == 0)
		{
			if (K == EBirdTask::None && T > 2.f && FishTries < 6 && Subject->GoFishing()) ++FishTries;
			float Dist = 300.f, Pitch = 10.f, YawOff = 100.f;
			switch (K)
			{
			case EBirdTask::FishHunt: case EBirdTask::FishCarry: Dist = 650.f; Pitch = 8.f; break;
			case EBirdTask::FishHover: Dist = 420.f; Pitch = 5.f; break;
			case EBirdTask::FishDive: case EBirdTask::FishUnder: case EBirdTask::FishEmerge: Dist = 380.f; Pitch = 6.f; break;
			case EBirdTask::FishHold: case EBirdTask::FishPeck: Dist = 75.f; Pitch = 12.f; YawOff = 80.f; break;
			default: break;
			}
			const FVector Tgt = Subject->GetPos();
			const float Yaw = (K == EBirdTask::FishDive || K == EBirdTask::FishUnder || K == EBirdTask::FishHover) ? 90.f : Subject->GetActorRotation().Yaw + YawOff;
			SmoothCam(ClearCamPos(Tgt, Yaw, Pitch, Dist), Tgt, 45.f, Dt, (K == EBirdTask::FishHold || K == EBirdTask::FishPeck) ? 1.2f : 2.5f);
			return;
		}
		// remains: wait for a gull to claim and swallow them
		ABirdFish* Fish = nullptr;
		for (TActorIterator<ABirdFish> It(GetWorld()); It; ++It) Fish = *It;
		if (!Fish)
		{
			if (FeedPhase < 3) { Log(FString::Printf(TEXT("feed remains swallowed at %.1f s %s"), T, *StatsJson())); FeedPhase = 3; EndAt = T + 3.f; }
			if (T > EndAt) bEndRecord = true;
			return;
		}
		ABird* G = Fish->Claimant.Get();
		if (G && FeedPhase == 1) { Log(FString::Printf(TEXT("feed gull claims the remains at %.1f s (dist %.0f)"), T, float(FVector::Dist(G->GetPos(), Fish->GetActorLocation())))); FeedPhase = 2; }
		if (G && int32(G->GetTask()) != LastGullTask) { Log(FString::Printf(TEXT("feed gull task %d at %.1f s"), int32(G->GetTask()), T)); LastGullTask = int32(G->GetTask()); }
		const FVector F = Fish->GetActorLocation();
		const FVector Tgt = G && FVector::Dist(G->GetPos(), F) < 600.f ? FMath::Lerp(F, G->GetPos(), 0.5f) : F;
		const float Dist = G && FVector::Dist(G->GetPos(), F) < 600.f ? 260.f : 420.f;
		SmoothCam(ClearCamPos(Tgt, 160.f, 14.f, Dist), Tgt, 45.f, Dt, 1.5f);
	});
	AddCall([this]() { Log(TEXT("feed end ") + StatsJson()); });
}

// ---------------------------------------------------------------------------------------------------- perf
void ABirdTestDirector::AddPerfWindow(const FString& Name, float Seconds)
{
	AddCall([this]() { PerfGT = PerfRT = PerfGPU = PerfFrame = PerfFlock = 0; for (double& P : PerfParts) P = 0; PerfFrames = PerfSamples = 0; });
	Steps.Add([this, Name, Seconds](float Dt)
	{
		PerfGT += FPlatformTime::ToMilliseconds(GGameThreadTime);
		PerfRT += FPlatformTime::ToMilliseconds(GRenderThreadTime);
		PerfGPU += FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles());
		PerfFrame += Dt * 1000.0;
		++PerfFrames;
		if (Flock && FMath::Fmod(StepTime, 1.f) < Dt)
		{
			const FBirdFlockStats S = Flock->GetStats();
			PerfFlock += S.AvgTickMs;
			const float P[6] = { S.SimulateMs, S.ProbeMs, S.SeparationMs, S.VisualsMs, S.FeathersMs, S.ScansMs };
			for (int32 i = 0; i < 6; ++i) PerfParts[i] += P[i];
			++PerfSamples;
		}
		if (StepTime < Seconds) return false;
		const double F = FMath::Max(PerfFrames, 1), K = FMath::Max(PerfSamples, 1);
		Log(FString::Printf(TEXT("BIRDPERF {\"window\":\"%s\",\"frames\":%d,\"frame_ms\":%.3f,\"game_ms\":%.3f,\"render_ms\":%.3f,\"gpu_ms\":%.3f,\"flock_ms\":%.4f,\"simulate_ms\":%.4f,\"probe_ms\":%.4f,\"separation_ms\":%.4f,\"visuals_ms\":%.4f,\"feathers_ms\":%.4f,\"scans_ms\":%.4f,\"stats\":%s}"),
			*Name, PerfFrames, PerfFrame / F, PerfGT / F, PerfRT / F, PerfGPU / F, PerfFlock / K, PerfParts[0] / K, PerfParts[1] / K, PerfParts[2] / K, PerfParts[3] / K, PerfParts[4] / K, PerfParts[5] / K, *StatsJson()));
		return true;
	});
}

void ABirdTestDirector::BuildPerfScene()
{
	// fixed overview of the beach; the normal population, then a stress population, then everything hidden (baseline)
	BuildBeach();
	Zone(FVector(0, 0, 300), FVector(2600, 2600, 300), EBirdSpecies::Gull, 8, 11, 0.45f);
	Zone(FVector(300, 700, 150), FVector(1300, 500, 150), EBirdSpecies::Kingfisher, 4, 22, 0.35f);
	AddWaitShaders(8.f);
	AddCall([this]() { SetCam(FVector(-2200, -2600, 700), FVector(0, 200, 80), 60.f); });
	AddWait(12.f);
	AddPerfWindow(TEXT("normal_12"), 15.f);
	AddPerfWindow(TEXT("normal_12_b"), 15.f);
	AddCall([this]()
	{
		Zone(FVector(-1500, 1500, 300), FVector(1800, 1500, 300), EBirdSpecies::Gull, 24, 51, 0.45f);
		Zone(FVector(1500, -800, 150), FVector(1200, 600, 150), EBirdSpecies::Kingfisher, 8, 52, 0.35f);
	});
	AddWait(12.f);
	AddPerfWindow(TEXT("stress_44"), 15.f);
	AddPerfWindow(TEXT("stress_44_b"), 15.f);
	// same population seen from ~120 m (distance tiers), then with the camera turned away (nothing on screen)
	AddCall([this]() { SetCam(FVector(-9000, -9500, 1500), FVector(0, 200, 80), 30.f); });
	AddWait(3.f);
	AddPerfWindow(TEXT("stress_44_far"), 10.f);
	AddCall([this]() { SetCam(FVector(-2200, -2600, 700), FVector(-7000, -9000, 900), 60.f); });
	AddWait(3.f);
	AddPerfWindow(TEXT("stress_44_away"), 10.f);
	AddCall([this]() { SetCam(FVector(-2200, -2600, 700), FVector(0, 200, 80), 60.f); });
	AddWait(2.f);
	AddCall([this]()
	{
		// a kill burst in the stress scene (feathers in the air): every 4th bird
		int32 i = 0;
		for (ABird* B : Flock->GetBirds()) if (B && (i++ % 4) == 0) B->Kill(B->GetPos(), FVector(0, 0, 300), nullptr);
	});
	AddPerfWindow(TEXT("stress_feathers"), 10.f);
	AddWait(10.f);
	AddPerfWindow(TEXT("corpses_settled"), 10.f);	// 33 live birds + 11 corpses lying still (25-45 s after the kills)
	AddCall([this]()
	{
		Flock->bEnabled = false;
		for (ABird* B : Flock->GetBirds()) if (B) { B->SetActorHiddenInGame(true); B->Mesh->SetComponentTickEnabled(false); }
	});
	AddWait(3.f);
	AddPerfWindow(TEXT("hidden_baseline"), 15.f);
}
