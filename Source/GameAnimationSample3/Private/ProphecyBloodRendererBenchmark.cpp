#include "ProphecyBloodRendererBenchmark.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/DecalComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "MeshDescriptionBuilder.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProphecyBloodStainRenderer.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "StaticMeshAttributes.h"

namespace
{
DEFINE_LOG_CATEGORY_STATIC(LogProphecyBloodRendererBenchmark, Log, All);

FString ResolveProjectPath(const FString& Path)
{
	if (Path.IsEmpty())
	{
		return Path;
	}
	if (FPaths::IsRelative(Path))
	{
		return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / Path);
	}
	return Path;
}

void DisableBenchmarkVSync()
{
	if (GEngine)
	{
		GEngine->bSmoothFrameRate = false;
		GEngine->SetMaxFPS(0.0f);
	}
	if (IConsoleVariable* VSyncCVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync")))
	{
		VSyncCVar->Set(0, ECVF_SetByCode);
	}
	if (IConsoleVariable* MotionBlurCVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.MotionBlurQuality")))
	{
		MotionBlurCVar->Set(0, ECVF_SetByCode);
	}
}

FVector MakeLookAtEuler(const FVector& From, const FVector& To)
{
	return (To - From).Rotation().Euler();
}
}

AProphecyBloodRendererBenchmarkActor::AProphecyBloodRendererBenchmarkActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SceneRoot->SetMobility(EComponentMobility::Movable);
	SetRootComponent(SceneRoot);
}

void AProphecyBloodRendererBenchmarkActor::BeginPlay()
{
	Super::BeginPlay();

	ApplyCommandLineOverrides();
	DisableBenchmarkVSync();
	SetupScene();
	BuildSamples();
	PopulateBenchmark();

	UE_LOG(
		LogProphecyBloodRendererBenchmark,
		Display,
		TEXT("Blood renderer benchmark started: method=%s stains=%d updates_per_frame=%d populate=%.3fms populate_flush=%.3fms chunks=%d"),
		*GetMethodName(),
		Samples.Num(),
		UpdatesPerFrame,
		PopulateTotalMs,
		PopulateFlushMs,
		PopulateChunkMs.Num());
}

void AProphecyBloodRendererBenchmarkActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bFinished)
	{
		return;
	}

	ElapsedSeconds += DeltaSeconds;
	++FrameCount;

	const double UpdateStart = FPlatformTime::Seconds();
	UpdateBenchmarkBatch();
	const double UpdateSeconds = FPlatformTime::Seconds() - UpdateStart;

	if (ElapsedSeconds >= WarmupSeconds)
	{
		WarmUpdateSeconds += UpdateSeconds;
		WarmDeltaSeconds += DeltaSeconds;
		++WarmFrameCount;
	}

	if (!bScreenshotRequested && ElapsedSeconds >= ScreenshotSeconds)
	{
		RequestBenchmarkScreenshot();
	}

	LogProgressIfNeeded();

	if (BenchmarkSeconds > 0.0f && ElapsedSeconds >= BenchmarkSeconds)
	{
		FinishBenchmark();
	}
}

void AProphecyBloodRendererBenchmarkActor::ApplyCommandLineOverrides()
{
	const TCHAR* Cmd = FCommandLine::Get();
	FString MethodName;
	if (FParse::Value(Cmd, TEXT("ProphecyBloodMethod="), MethodName))
	{
		EProphecyBloodRendererBenchmarkMethod ParsedMethod = Method;
		if (ParseMethodName(MethodName, ParsedMethod))
		{
			Method = ParsedMethod;
		}
		else
		{
			UE_LOG(LogProphecyBloodRendererBenchmark, Warning, TEXT("Unknown ProphecyBloodMethod '%s'; keeping %s."), *MethodName, *GetMethodName());
		}
	}

	FParse::Value(Cmd, TEXT("ProphecyBloodCount="), StainCount);
	FParse::Value(Cmd, TEXT("ProphecyBloodUpdatesPerFrame="), UpdatesPerFrame);
	FParse::Value(Cmd, TEXT("ProphecyBloodSeconds="), BenchmarkSeconds);
	FParse::Value(Cmd, TEXT("ProphecyBloodWarmup="), WarmupSeconds);
	FParse::Value(Cmd, TEXT("ProphecyBloodScreenshotSeconds="), ScreenshotSeconds);
	FParse::Value(Cmd, TEXT("ProphecyBloodFieldHalfExtent="), FieldHalfExtentCm);
	FParse::Value(Cmd, TEXT("ProphecyBloodMinRadius="), MinRadiusCm);
	FParse::Value(Cmd, TEXT("ProphecyBloodMaxRadius="), MaxRadiusCm);
	FParse::Value(Cmd, TEXT("ProphecyBloodShot="), ScreenshotPath);
	FParse::Value(Cmd, TEXT("ProphecyBloodJson="), JsonPath);
	bExitWhenDone = bExitWhenDone || FParse::Param(Cmd, TEXT("ProphecyBloodBenchmarkExit"));

	StainCount = FMath::Clamp(StainCount, 1, 200000);
	UpdatesPerFrame = FMath::Clamp(UpdatesPerFrame, 0, StainCount);
	BenchmarkSeconds = FMath::Max(BenchmarkSeconds, 0.0f);
	WarmupSeconds = FMath::Max(WarmupSeconds, 0.0f);
	ScreenshotSeconds = FMath::Max(ScreenshotSeconds, 0.0f);
	FieldHalfExtentCm = FMath::Max(FieldHalfExtentCm, 100.0f);
	MinRadiusCm = FMath::Max(MinRadiusCm, 0.2f);
	MaxRadiusCm = FMath::Max(MaxRadiusCm, MinRadiusCm);
}

bool AProphecyBloodRendererBenchmarkActor::ParseMethodName(const FString& Name, EProphecyBloodRendererBenchmarkMethod& OutMethod) const
{
	if (Name.Equals(TEXT("Decal"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("Decals"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("DecalComponents"), ESearchCase::IgnoreCase))
	{
		OutMethod = EProphecyBloodRendererBenchmarkMethod::DecalComponents;
		return true;
	}
	if (Name.Equals(TEXT("ISM"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("Instanced"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("InstancedStaticMesh"), ESearchCase::IgnoreCase))
	{
		OutMethod = EProphecyBloodRendererBenchmarkMethod::InstancedStaticMesh;
		return true;
	}
	if (Name.Equals(TEXT("HISM"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("Hierarchical"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("HierarchicalInstancedStaticMesh"), ESearchCase::IgnoreCase))
	{
		OutMethod = EProphecyBloodRendererBenchmarkMethod::HierarchicalInstancedStaticMesh;
		return true;
	}
	if (Name.Equals(TEXT("MeshDecal"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("MeshDecalISM"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("InstancedMeshDecal"), ESearchCase::IgnoreCase))
	{
		OutMethod = EProphecyBloodRendererBenchmarkMethod::MeshDecalInstancedStaticMesh;
		return true;
	}
	if (Name.Equals(TEXT("Procedural"), ESearchCase::IgnoreCase) ||
		Name.Equals(TEXT("ProceduralMesh"), ESearchCase::IgnoreCase))
	{
		OutMethod = EProphecyBloodRendererBenchmarkMethod::ProceduralMesh;
		return true;
	}
	return false;
}

FString AProphecyBloodRendererBenchmarkActor::GetMethodName() const
{
	switch (Method)
	{
	case EProphecyBloodRendererBenchmarkMethod::DecalComponents:
		return TEXT("DecalComponents");
	case EProphecyBloodRendererBenchmarkMethod::InstancedStaticMesh:
		return TEXT("InstancedStaticMesh");
	case EProphecyBloodRendererBenchmarkMethod::HierarchicalInstancedStaticMesh:
		return TEXT("HierarchicalInstancedStaticMesh");
	case EProphecyBloodRendererBenchmarkMethod::MeshDecalInstancedStaticMesh:
		return TEXT("MeshDecalInstancedStaticMesh");
	case EProphecyBloodRendererBenchmarkMethod::ProceduralMesh:
		return TEXT("ProceduralMesh");
	default:
		return TEXT("Unknown");
	}
}

void AProphecyBloodRendererBenchmarkActor::SetupScene()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	if (UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane")))
	{
		FloorComponent = NewObject<UStaticMeshComponent>(this, TEXT("BloodBenchmarkFloor"));
		if (FloorComponent)
		{
			FloorComponent->SetStaticMesh(PlaneMesh);
			if (UMaterialInterface* FloorMaterial = LoadFloorMaterial())
			{
				FloorComponent->SetMaterial(0, FloorMaterial);
			}
			FloorComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			FloorComponent->SetCastShadow(false);
			FloorComponent->SetMobility(EComponentMobility::Movable);
			FloorComponent->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
			FloorComponent->SetRelativeScale3D(FVector(FieldHalfExtentCm / 50.0f, FieldHalfExtentCm / 50.0f, 1.0f));
			AddInstanceComponent(FloorComponent);
			FloorComponent->RegisterComponent();
		}
	}

	const FVector CameraLocation(0.0, -FieldHalfExtentCm * 1.12f, FieldHalfExtentCm * 1.05f);
	CameraActor = World->SpawnActor<ACameraActor>(CameraLocation, FRotator::ZeroRotator);
	if (CameraActor)
	{
		const FVector Euler = MakeLookAtEuler(CameraLocation, FVector::ZeroVector);
		CameraActor->SetActorRotation(FRotator::MakeFromEuler(Euler));
		CameraActor->GetCameraComponent()->SetFieldOfView(58.0f);
		if (APlayerController* Controller = UGameplayStatics::GetPlayerController(World, 0))
		{
			Controller->SetViewTarget(CameraActor);
		}
	}
}

void AProphecyBloodRendererBenchmarkActor::BuildSamples()
{
	Samples.Reset();
	Samples.Reserve(StainCount);

	const int32 Columns = FMath::Max(1, FMath::CeilToInt(FMath::Sqrt(float(StainCount))));
	const int32 Rows = FMath::Max(1, FMath::CeilToInt(float(StainCount) / float(Columns)));
	const float StepX = Columns > 1 ? (FieldHalfExtentCm * 2.0f) / float(Columns - 1) : 0.0f;
	const float StepY = Rows > 1 ? (FieldHalfExtentCm * 2.0f) / float(Rows - 1) : 0.0f;
	FRandomStream Random(830177);

	for (int32 Index = 0; Index < StainCount; ++Index)
	{
		const int32 X = Index % Columns;
		const int32 Y = Index / Columns;
		const float JitterX = Random.FRandRange(-0.32f, 0.32f) * StepX;
		const float JitterY = Random.FRandRange(-0.32f, 0.32f) * StepY;

		FStainSample Sample;
		Sample.Position = FVector(
			-FieldHalfExtentCm + float(X) * StepX + JitterX,
			-FieldHalfExtentCm + float(Y) * StepY + JitterY,
			1.1f);
		Sample.Normal = FVector::UpVector;
		Sample.RadiusCm = Random.FRandRange(MinRadiusCm, MaxRadiusCm);
		Sample.YawDegrees = Random.FRandRange(0.0f, 360.0f);
		const float Wet = Random.FRandRange(0.78f, 1.0f);
		Sample.Color = FLinearColor(0.85f * Wet, 0.018f * Wet, 0.010f * Wet, 1.0f);
		Samples.Add(Sample);
	}
}

void AProphecyBloodRendererBenchmarkActor::PopulateBenchmark()
{
	const double PopulateStart = FPlatformTime::Seconds();

	switch (Method)
	{
	case EProphecyBloodRendererBenchmarkMethod::DecalComponents:
		PopulateDecalComponents();
		break;
	case EProphecyBloodRendererBenchmarkMethod::InstancedStaticMesh:
		PopulateInstancedStaticMesh(false, false);
		break;
	case EProphecyBloodRendererBenchmarkMethod::HierarchicalInstancedStaticMesh:
		PopulateInstancedStaticMesh(true, false);
		break;
	case EProphecyBloodRendererBenchmarkMethod::MeshDecalInstancedStaticMesh:
		PopulateInstancedStaticMesh(false, true);
		break;
	case EProphecyBloodRendererBenchmarkMethod::ProceduralMesh:
		PopulateProceduralMesh();
		break;
	default:
		break;
	}

	PopulateTotalMs = (FPlatformTime::Seconds() - PopulateStart) * 1000.0;
}

void AProphecyBloodRendererBenchmarkActor::PopulateDecalComponents()
{
	UMaterialInterface* DecalMaterial = LoadDecalMaterial();
	DecalComponents.Reset();
	DecalComponents.Reserve(Samples.Num());

	double ChunkStart = FPlatformTime::Seconds();
	for (int32 Index = 0; Index < Samples.Num(); ++Index)
	{
		const FStainSample& Sample = Samples[Index];
		UDecalComponent* Component = NewObject<UDecalComponent>(this);
		if (!Component)
		{
			continue;
		}
		Component->DecalSize = FVector(8.0f, Sample.RadiusCm * 2.0f, Sample.RadiusCm * 2.0f);
		if (DecalMaterial)
		{
			Component->SetDecalMaterial(DecalMaterial);
		}
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(Component);
		Component->RegisterComponent();
		Component->SetWorldLocationAndRotation(Sample.Position + FVector(0.0, 0.0, 6.0), FRotator(-90.0f, Sample.YawDegrees, 0.0f));
		DecalComponents.Add(Component);

		if ((Index + 1) % 1000 == 0 || Index + 1 == Samples.Num())
		{
			RecordPopulateChunk(FPlatformTime::Seconds() - ChunkStart);
			ChunkStart = FPlatformTime::Seconds();
		}
	}
}

void AProphecyBloodRendererBenchmarkActor::PopulateInstancedStaticMesh(bool bHierarchical, bool bMeshDecal)
{
	TriangleMesh = CreateTriangleMesh();
	if (!TriangleMesh)
	{
		UE_LOG(LogProphecyBloodRendererBenchmark, Error, TEXT("Could not create blood benchmark triangle mesh."));
		return;
	}

	UInstancedStaticMeshComponent* Component = nullptr;
	if (bHierarchical)
	{
		HISMComponent = NewObject<UHierarchicalInstancedStaticMeshComponent>(this, TEXT("BloodBenchmarkHISM"));
		Component = HISMComponent;
	}
	else
	{
		ISMComponent = NewObject<UInstancedStaticMeshComponent>(this, TEXT("BloodBenchmarkISM"));
		Component = ISMComponent;
	}

	if (!Component)
	{
		return;
	}

	Component->SetStaticMesh(TriangleMesh);
	if (UMaterialInterface* BloodMaterial = bMeshDecal ? LoadDecalMaterial() : CreateBloodDebugMaterial())
	{
		Component->SetMaterial(0, BloodMaterial);
	}
	Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Component->SetGenerateOverlapEvents(false);
	Component->SetCastShadow(false);
	Component->SetMobility(EComponentMobility::Movable);
	Component->SetReceivesDecals(false);
	Component->NumCustomDataFloats = 0;
	Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
	AddInstanceComponent(Component);
	Component->RegisterComponent();
	Component->PreAllocateInstancesMemory(Samples.Num());

	double ChunkStart = FPlatformTime::Seconds();
	for (int32 Index = 0; Index < Samples.Num(); ++Index)
	{
		Component->AddInstance(MakeStainTransform(Samples[Index]), true);
		if ((Index + 1) % 1000 == 0 || Index + 1 == Samples.Num())
		{
			RecordPopulateChunk(FPlatformTime::Seconds() - ChunkStart);
			ChunkStart = FPlatformTime::Seconds();
		}
	}
}

void AProphecyBloodRendererBenchmarkActor::PopulateProceduralMesh()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ProceduralRenderer = World->SpawnActor<AProphecyBloodStainRenderer>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
	if (!ProceduralRenderer)
	{
		return;
	}

	ProceduralRenderer->MaxStains = Samples.Num();
	ProceduralRenderer->bFlushEveryTick = false;
	ProceduralRenderer->DefaultRadiusCm = 6.0f;
	ProceduralRenderer->RadiusJitter = 0.0f;
	ProceduralRenderer->StainMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface.M_ProphecyBloodVFX_Surface"));
	if (!ProceduralRenderer->StainMaterial)
	{
		ProceduralRenderer->StainMaterial = CreateBloodDebugMaterial();
	}
	ProceduralRenderer->EnsureMeshInitialized();

	double ChunkStart = FPlatformTime::Seconds();
	for (int32 Index = 0; Index < Samples.Num(); ++Index)
	{
		const FStainSample& Sample = Samples[Index];
		ProceduralRenderer->AddBloodHit(Sample.Position, Sample.Normal, Sample.RadiusCm, Sample.Color);
		if ((Index + 1) % 1000 == 0 || Index + 1 == Samples.Num())
		{
			RecordPopulateChunk(FPlatformTime::Seconds() - ChunkStart);
			ChunkStart = FPlatformTime::Seconds();
		}
	}

	const double FlushStart = FPlatformTime::Seconds();
	ProceduralRenderer->FlushPendingStains();
	PopulateFlushMs = (FPlatformTime::Seconds() - FlushStart) * 1000.0;
}

void AProphecyBloodRendererBenchmarkActor::UpdateBenchmarkBatch()
{
	if (UpdatesPerFrame <= 0 || Samples.Num() == 0)
	{
		return;
	}

	switch (Method)
	{
	case EProphecyBloodRendererBenchmarkMethod::DecalComponents:
		UpdateDecalBatch();
		break;
	case EProphecyBloodRendererBenchmarkMethod::InstancedStaticMesh:
		UpdateInstancedBatch(ISMComponent);
		break;
	case EProphecyBloodRendererBenchmarkMethod::HierarchicalInstancedStaticMesh:
		UpdateInstancedBatch(HISMComponent);
		break;
	case EProphecyBloodRendererBenchmarkMethod::MeshDecalInstancedStaticMesh:
		UpdateInstancedBatch(ISMComponent);
		break;
	case EProphecyBloodRendererBenchmarkMethod::ProceduralMesh:
		UpdateProceduralBatch();
		break;
	default:
		break;
	}
}

void AProphecyBloodRendererBenchmarkActor::UpdateDecalBatch()
{
	const int32 Count = FMath::Min(UpdatesPerFrame, DecalComponents.Num());
	for (int32 LocalIndex = 0; LocalIndex < Count; ++LocalIndex)
	{
		const int32 Index = (UpdateCursor + LocalIndex) % DecalComponents.Num();
		UDecalComponent* Component = DecalComponents[Index];
		if (!Component)
		{
			continue;
		}
		const FStainSample Sample = MakeMovedSample(Index, UpdateGeneration);
		Component->DecalSize = FVector(8.0f, Sample.RadiusCm * 2.0f, Sample.RadiusCm * 2.0f);
		Component->SetWorldLocationAndRotation(Sample.Position + FVector(0.0, 0.0, 6.0), FRotator(-90.0f, Sample.YawDegrees, 0.0f));
	}

	UpdateCursor = (UpdateCursor + Count) % FMath::Max(1, DecalComponents.Num());
	++UpdateGeneration;
}

void AProphecyBloodRendererBenchmarkActor::UpdateInstancedBatch(UInstancedStaticMeshComponent* Component)
{
	if (!Component || Samples.Num() == 0)
	{
		return;
	}

	const int32 Count = FMath::Min(UpdatesPerFrame, Samples.Num());
	for (int32 LocalIndex = 0; LocalIndex < Count; ++LocalIndex)
	{
		const int32 Index = (UpdateCursor + LocalIndex) % Samples.Num();
		const FStainSample Sample = MakeMovedSample(Index, UpdateGeneration);
		Component->UpdateInstanceTransform(Index, MakeStainTransform(Sample), true, false, true);
	}
	Component->MarkRenderStateDirty();

	UpdateCursor = (UpdateCursor + Count) % FMath::Max(1, Samples.Num());
	++UpdateGeneration;
}

void AProphecyBloodRendererBenchmarkActor::UpdateProceduralBatch()
{
	if (!ProceduralRenderer || Samples.Num() == 0)
	{
		return;
	}

	const int32 Count = FMath::Min(UpdatesPerFrame, Samples.Num());
	for (int32 LocalIndex = 0; LocalIndex < Count; ++LocalIndex)
	{
		const int32 Index = (UpdateCursor + LocalIndex) % Samples.Num();
		const FStainSample Sample = MakeMovedSample(Index, UpdateGeneration);
		ProceduralRenderer->AddBloodHit(Sample.Position, Sample.Normal, Sample.RadiusCm, Sample.Color);
	}
	ProceduralRenderer->FlushPendingStains();

	UpdateCursor = (UpdateCursor + Count) % FMath::Max(1, Samples.Num());
	++UpdateGeneration;
}

void AProphecyBloodRendererBenchmarkActor::RequestBenchmarkScreenshot()
{
	bScreenshotRequested = true;
	if (ScreenshotPath.IsEmpty())
	{
		ScreenshotPath = FString::Printf(TEXT("Saved/BloodRendererBenchmarks/%s_%d.png"), *GetMethodName(), Samples.Num());
	}

	const FString ResolvedScreenshotPath = ResolveProjectPath(ScreenshotPath);
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(ResolvedScreenshotPath), true);
	FScreenshotRequest::RequestScreenshot(ResolvedScreenshotPath, false, false);
	UE_LOG(LogProphecyBloodRendererBenchmark, Display, TEXT("Requested blood benchmark screenshot: %s"), *ResolvedScreenshotPath);
}

void AProphecyBloodRendererBenchmarkActor::LogProgressIfNeeded()
{
	if (ElapsedSeconds - LastProgressSeconds < 2.0f)
	{
		return;
	}

	LastProgressSeconds = ElapsedSeconds;
	const double FPS = WarmDeltaSeconds > UE_SMALL_NUMBER ? double(WarmFrameCount) / WarmDeltaSeconds : double(FrameCount) / FMath::Max(double(ElapsedSeconds), UE_SMALL_NUMBER);
	const double UpdateMs = WarmFrameCount > 0 ? WarmUpdateSeconds * 1000.0 / double(WarmFrameCount) : 0.0;
	UE_LOG(
		LogProphecyBloodRendererBenchmark,
		Display,
		TEXT("BloodBenchmark %.1fs method=%s fps=%.1f update_batch=%.3fms frames=%lld"),
		ElapsedSeconds,
		*GetMethodName(),
		FPS,
		UpdateMs,
		FrameCount);
}

void AProphecyBloodRendererBenchmarkActor::FinishBenchmark()
{
	if (bFinished)
	{
		return;
	}

	bFinished = true;
	SaveJsonSummary();

	const double FPS = WarmDeltaSeconds > UE_SMALL_NUMBER ? double(WarmFrameCount) / WarmDeltaSeconds : 0.0;
	const double UpdateMs = WarmFrameCount > 0 ? WarmUpdateSeconds * 1000.0 / double(WarmFrameCount) : 0.0;
	const double FirstChunkMs = PopulateChunkMs.Num() > 0 ? PopulateChunkMs[0] : 0.0;
	const double LastChunkMs = PopulateChunkMs.Num() > 0 ? PopulateChunkMs.Last() : 0.0;
	double MaxChunkMs = 0.0;
	for (const double ChunkMs : PopulateChunkMs)
	{
		MaxChunkMs = FMath::Max(MaxChunkMs, ChunkMs);
	}

	UE_LOG(LogProphecyBloodRendererBenchmark, Display, TEXT("========== Prophecy Blood Renderer Benchmark Summary =========="));
	UE_LOG(LogProphecyBloodRendererBenchmark, Display, TEXT("method=%s stains=%d updates_per_frame=%d"), *GetMethodName(), Samples.Num(), UpdatesPerFrame);
	UE_LOG(LogProphecyBloodRendererBenchmark, Display, TEXT("populate_ms=%.3f populate_flush_ms=%.3f chunk_first_ms=%.3f chunk_last_ms=%.3f chunk_max_ms=%.3f"), PopulateTotalMs, PopulateFlushMs, FirstChunkMs, LastChunkMs, MaxChunkMs);
	UE_LOG(LogProphecyBloodRendererBenchmark, Display, TEXT("fps=%.2f update_batch_ms=%.4f warm_frames=%lld warm_seconds=%.3f screenshot=%s json=%s"), FPS, UpdateMs, WarmFrameCount, WarmDeltaSeconds, *ResolveProjectPath(ScreenshotPath), *ResolveProjectPath(JsonPath));

	if (bExitWhenDone)
	{
		FGenericPlatformMisc::RequestExit(false);
	}
}

void AProphecyBloodRendererBenchmarkActor::SaveJsonSummary() const
{
	if (JsonPath.IsEmpty())
	{
		return;
	}

	const FString ResolvedJsonPath = ResolveProjectPath(JsonPath);
	IFileManager::Get().MakeDirectory(*FPaths::GetPath(ResolvedJsonPath), true);

	double MaxChunkMs = 0.0;
	for (const double ChunkMs : PopulateChunkMs)
	{
		MaxChunkMs = FMath::Max(MaxChunkMs, ChunkMs);
	}

	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("method"), GetMethodName());
	Root->SetNumberField(TEXT("stain_count"), Samples.Num());
	Root->SetNumberField(TEXT("updates_per_frame"), UpdatesPerFrame);
	Root->SetNumberField(TEXT("populate_total_ms"), PopulateTotalMs);
	Root->SetNumberField(TEXT("populate_flush_ms"), PopulateFlushMs);
	Root->SetNumberField(TEXT("populate_chunk_first_ms"), PopulateChunkMs.Num() > 0 ? PopulateChunkMs[0] : 0.0);
	Root->SetNumberField(TEXT("populate_chunk_last_ms"), PopulateChunkMs.Num() > 0 ? PopulateChunkMs.Last() : 0.0);
	Root->SetNumberField(TEXT("populate_chunk_max_ms"), MaxChunkMs);
	Root->SetNumberField(TEXT("warm_fps"), WarmDeltaSeconds > UE_SMALL_NUMBER ? double(WarmFrameCount) / WarmDeltaSeconds : 0.0);
	Root->SetNumberField(TEXT("warm_update_batch_ms"), WarmFrameCount > 0 ? WarmUpdateSeconds * 1000.0 / double(WarmFrameCount) : 0.0);
	Root->SetNumberField(TEXT("warm_frames"), WarmFrameCount);
	Root->SetNumberField(TEXT("warm_seconds"), WarmDeltaSeconds);
	Root->SetStringField(TEXT("screenshot_path"), ResolveProjectPath(ScreenshotPath));

	TArray<TSharedPtr<FJsonValue>> Chunks;
	for (const double ChunkMs : PopulateChunkMs)
	{
		Chunks.Add(MakeShared<FJsonValueNumber>(ChunkMs));
	}
	Root->SetArrayField(TEXT("populate_chunk_ms"), Chunks);

	FString JsonText;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonText);
	if (FJsonSerializer::Serialize(Root, Writer))
	{
		FFileHelper::SaveStringToFile(JsonText, *ResolvedJsonPath);
		UE_LOG(LogProphecyBloodRendererBenchmark, Display, TEXT("Saved blood benchmark JSON: %s"), *ResolvedJsonPath);
	}
}

void AProphecyBloodRendererBenchmarkActor::RecordPopulateChunk(double ChunkSeconds)
{
	PopulateChunkMs.Add(ChunkSeconds * 1000.0);
}

FTransform AProphecyBloodRendererBenchmarkActor::MakeStainTransform(const FStainSample& Sample, float ExtraYawDegrees) const
{
	const FRotator Rotation(0.0f, Sample.YawDegrees + ExtraYawDegrees, 0.0f);
	const FVector Scale(Sample.RadiusCm, Sample.RadiusCm, 1.0f);
	return FTransform(Rotation, Sample.Position, Scale);
}

AProphecyBloodRendererBenchmarkActor::FStainSample AProphecyBloodRendererBenchmarkActor::MakeMovedSample(int32 SampleIndex, int32 Generation) const
{
	FStainSample Sample = Samples.IsValidIndex(SampleIndex) ? Samples[SampleIndex] : FStainSample();
	const float Phase = float(SampleIndex) * 0.173f + float(Generation) * 0.021f;
	const float Drift = FMath::Max(2.0f, Sample.RadiusCm * 0.55f);
	Sample.Position.X += FMath::Sin(Phase) * Drift;
	Sample.Position.Y += FMath::Cos(Phase * 1.37f) * Drift;
	Sample.YawDegrees += float(Generation % 360) * 0.9f;
	return Sample;
}

UStaticMesh* AProphecyBloodRendererBenchmarkActor::CreateTriangleMesh()
{
	if (TriangleMesh)
	{
		return TriangleMesh;
	}

	UMaterialInterface* BloodMaterial = CreateBloodDebugMaterial();
	if (!BloodMaterial)
	{
		BloodMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"));
	}
	if (!BloodMaterial)
	{
		return nullptr;
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	FMeshDescriptionBuilder Builder;
	Builder.SetMeshDescription(&MeshDescription);
	Builder.SetNumUVLayers(1);
	const FPolygonGroupID PolygonGroup = Builder.AppendPolygonGroup(TEXT("BloodTriangle"));

	const FVector A(-0.72, -0.48, 0.0);
	const FVector B(0.70, -0.36, 0.0);
	const FVector C(0.08, 0.82, 0.0);
	const FVector Normal = FVector::UpVector;
	const FVector Tangent = FVector::ForwardVector;
	const FVector4f Color(0.85f, 0.018f, 0.010f, 1.0f);

	const FVertexID VA = Builder.AppendVertex(A);
	const FVertexID VB = Builder.AppendVertex(B);
	const FVertexID VC = Builder.AppendVertex(C);
	const FVertexInstanceID IA = Builder.AppendInstance(VA);
	const FVertexInstanceID IB = Builder.AppendInstance(VB);
	const FVertexInstanceID IC = Builder.AppendInstance(VC);

	Builder.SetInstanceNormal(IA, Normal);
	Builder.SetInstanceNormal(IB, Normal);
	Builder.SetInstanceNormal(IC, Normal);
	Builder.SetInstanceTangentSpace(IA, Normal, Tangent, 1.0f);
	Builder.SetInstanceTangentSpace(IB, Normal, Tangent, 1.0f);
	Builder.SetInstanceTangentSpace(IC, Normal, Tangent, 1.0f);
	Builder.SetInstanceUV(IA, FVector2D(0.0, 0.0));
	Builder.SetInstanceUV(IB, FVector2D(1.0, 0.0));
	Builder.SetInstanceUV(IC, FVector2D(0.5, 1.0));
	Builder.SetInstanceColor(IA, Color);
	Builder.SetInstanceColor(IB, Color);
	Builder.SetInstanceColor(IC, Color);
	Builder.AppendTriangle(IA, IB, IC, PolygonGroup);
	Builder.AppendTriangle(IC, IB, IA, PolygonGroup);

	TriangleMesh = NewObject<UStaticMesh>(this, TEXT("ProphecyBloodBenchmarkTriangle"), RF_Transient);
	if (!TriangleMesh)
	{
		return nullptr;
	}
	TriangleMesh->GetStaticMaterials().Add(FStaticMaterial(BloodMaterial, TEXT("BloodTriangle")));

	UStaticMesh::FBuildMeshDescriptionsParams Params;
	Params.bBuildSimpleCollision = false;
	Params.bCommitMeshDescription = true;
	Params.bFastBuild = true;
	Params.bAllowCpuAccess = false;
	TArray<const FMeshDescription*> MeshDescriptions;
	MeshDescriptions.Add(&MeshDescription);
	if (!TriangleMesh->BuildFromMeshDescriptions(MeshDescriptions, Params))
	{
		UE_LOG(LogProphecyBloodRendererBenchmark, Warning, TEXT("Failed to build blood benchmark triangle static mesh."));
		TriangleMesh = nullptr;
	}

	return TriangleMesh;
}

UMaterialInterface* AProphecyBloodRendererBenchmarkActor::CreateBloodDebugMaterial()
{
	UMaterialInterface* ParentMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (!ParentMaterial)
	{
		ParentMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
	}
	if (!ParentMaterial)
	{
		return nullptr;
	}

	UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(ParentMaterial, this, TEXT("ProphecyBloodBenchmarkRedMaterial"));
	if (!Material)
	{
		return ParentMaterial;
	}

	const FLinearColor BloodRed(0.85f, 0.012f, 0.006f, 1.0f);
	Material->SetVectorParameterValue(TEXT("Color"), BloodRed);
	Material->SetVectorParameterValue(TEXT("BaseColor"), BloodRed);
	Material->SetVectorParameterValue(TEXT("Base Color"), BloodRed);
	Material->SetVectorParameterValue(TEXT("Tint"), BloodRed);
	return Material;
}

UMaterialInterface* AProphecyBloodRendererBenchmarkActor::LoadDecalMaterial() const
{
	if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/_mygame/blood2/MI_blooddecal.MI_blooddecal")))
	{
		return Material;
	}
	if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/_mygame/blood2/M_blood_final.M_blood_final")))
	{
		return Material;
	}
	return LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultDeferredDecalMaterial.DefaultDeferredDecalMaterial"));
}

UMaterialInterface* AProphecyBloodRendererBenchmarkActor::LoadFloorMaterial() const
{
	if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")))
	{
		return Material;
	}
	return LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
}

bool UProphecyBloodRendererBenchmarkSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	return Super::ShouldCreateSubsystem(Outer) && FParse::Param(FCommandLine::Get(), TEXT("ProphecyBloodBenchmark"));
}

void UProphecyBloodRendererBenchmarkSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	if (!InWorld.IsGameWorld() || BenchmarkActor)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.Name = TEXT("ProphecyBloodRendererBenchmark");
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	BenchmarkActor = InWorld.SpawnActor<AProphecyBloodRendererBenchmarkActor>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
}
