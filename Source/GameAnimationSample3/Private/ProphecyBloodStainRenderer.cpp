#include "ProphecyBloodStainRenderer.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
DEFINE_LOG_CATEGORY_STATIC(LogProphecyBloodStain, Log, All);

constexpr int32 VerticesPerStain = 3;

uint32 HashPosition(const FVector& Position, uint32 Serial)
{
	const uint32 X = GetTypeHash(FMath::RoundToInt(Position.X * 10.0));
	const uint32 Y = GetTypeHash(FMath::RoundToInt(Position.Y * 10.0));
	const uint32 Z = GetTypeHash(FMath::RoundToInt(Position.Z * 10.0));
	return HashCombine(HashCombine(HashCombine(X, Y), Z), Serial * 2654435761u);
}
}

AProphecyBloodStainRenderer::AProphecyBloodStainRenderer()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	MeshComponent = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("BloodStainMesh"));
	SetRootComponent(MeshComponent);
	MeshComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	MeshComponent->SetCastShadow(false);
	MeshComponent->bUseAsyncCooking = false;

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface.M_ProphecyBloodVFX_Surface"));
	if (MaterialFinder.Succeeded())
	{
		StainMaterial = MaterialFinder.Object;
	}
}

void AProphecyBloodStainRenderer::BeginPlay()
{
	Super::BeginPlay();
	EnsureMeshInitialized();
}

void AProphecyBloodStainRenderer::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	EnsureMeshInitialized();
}

void AProphecyBloodStainRenderer::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bFlushEveryTick && bMeshDirty)
	{
		FlushPendingStains();
	}
}

void AProphecyBloodStainRenderer::ReceiveParticleData_Implementation(const TArray<FBasicParticleData>& Data, UNiagaraSystem* NiagaraSystem, const FVector& SimulationPositionOffset)
{
	AddBloodParticleData(Data, SimulationPositionOffset);
}

void AProphecyBloodStainRenderer::AddBloodHit(const FVector& WorldPosition, const FVector& WorldNormal, float RadiusCm, FLinearColor Color)
{
	EnsureMeshInitialized();

	if (MaxStains <= 0 || !bMeshInitialized)
	{
		return;
	}

	const int32 StainIndex = NextStainIndex;
	NextStainIndex = (NextStainIndex + 1) % MaxStains;
	ActiveStainCount = FMath::Min(ActiveStainCount + 1, MaxStains);
	++TotalStainsAccepted;

	const float BaseRadius = RadiusCm > KINDA_SMALL_NUMBER ? RadiusCm : DefaultRadiusCm;
	WriteTriangle(StainIndex, WorldPosition, WorldNormal, BaseRadius, Color.A > 0.0f ? Color : DefaultColor);
	bMeshDirty = true;
}

void AProphecyBloodStainRenderer::AddBloodParticleData(const TArray<FBasicParticleData>& Data, const FVector& SimulationPositionOffset)
{
	for (const FBasicParticleData& Particle : Data)
	{
		const float Radius = Particle.Size > KINDA_SMALL_NUMBER ? Particle.Size * ParticleSizeToRadius : DefaultRadiusCm;
		AddBloodHit(Particle.Position + SimulationPositionOffset, Particle.Velocity, Radius, DefaultColor);
	}

	FlushPendingStains();
}

void AProphecyBloodStainRenderer::FlushPendingStains()
{
	if (!bMeshDirty || !bMeshInitialized || !MeshComponent)
	{
		return;
	}

	MeshComponent->UpdateMeshSection_LinearColor(0, Vertices, Normals, UV0, VertexColors, Tangents, false);
	bMeshDirty = false;
}

void AProphecyBloodStainRenderer::ClearBloodStains()
{
	EnsureMeshInitialized();

	for (int32 StainIndex = 0; StainIndex < MaxStains; ++StainIndex)
	{
		WriteHiddenTriangle(StainIndex);
	}

	NextStainIndex = 0;
	ActiveStainCount = 0;
	TotalStainsAccepted = 0;
	bMeshDirty = true;
	FlushPendingStains();
}

void AProphecyBloodStainRenderer::BindAsNiagaraExportCallback(UNiagaraComponent* NiagaraComponent, FName CallbackUserParameterName)
{
	if (!NiagaraComponent)
	{
		return;
	}

	NiagaraComponent->SetVariableObject(CallbackUserParameterName, this);
}

void AProphecyBloodStainRenderer::EnsureMeshInitialized()
{
	if (!MeshComponent || MaxStains <= 0)
	{
		return;
	}

	const int32 DesiredVertexCount = MaxStains * VerticesPerStain;
	const int32 DesiredIndexCount = MaxStains * VerticesPerStain;
	if (bMeshInitialized && Vertices.Num() == DesiredVertexCount && Triangles.Num() == DesiredIndexCount)
	{
		if (StainMaterial && MeshComponent->GetMaterial(0) != StainMaterial)
		{
			MeshComponent->SetMaterial(0, StainMaterial);
		}
		return;
	}

	Vertices.SetNumZeroed(DesiredVertexCount);
	Normals.SetNumZeroed(DesiredVertexCount);
	UV0.SetNumZeroed(DesiredVertexCount);
	VertexColors.SetNumZeroed(DesiredVertexCount);
	Tangents.SetNum(DesiredVertexCount);
	Triangles.SetNumUninitialized(DesiredIndexCount);

	for (int32 StainIndex = 0; StainIndex < MaxStains; ++StainIndex)
	{
		const int32 BaseVertex = StainIndex * VerticesPerStain;
		Triangles[BaseVertex + 0] = BaseVertex + 0;
		Triangles[BaseVertex + 1] = BaseVertex + 1;
		Triangles[BaseVertex + 2] = BaseVertex + 2;
		WriteHiddenTriangle(StainIndex);
	}

	MeshComponent->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UV0, VertexColors, Tangents, false, false);
	if (StainMaterial)
	{
		MeshComponent->SetMaterial(0, StainMaterial);
	}

	NextStainIndex = 0;
	ActiveStainCount = 0;
	TotalStainsAccepted = 0;
	bMeshInitialized = true;
	bMeshDirty = false;
}

void AProphecyBloodStainRenderer::WriteTriangle(int32 StainIndex, const FVector& WorldPosition, const FVector& WorldNormal, float RadiusCm, const FLinearColor& Color)
{
	const int32 BaseVertex = StainIndex * VerticesPerStain;
	if (!Vertices.IsValidIndex(BaseVertex + 2))
	{
		return;
	}

	const FTransform ComponentTransform = MeshComponent ? MeshComponent->GetComponentTransform() : FTransform::Identity;
	const FVector NormalWorld = MakeStableFallbackNormal(WorldNormal);
	const FVector NormalLocal = ComponentTransform.InverseTransformVectorNoScale(NormalWorld).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	const FVector CenterLocal = ComponentTransform.InverseTransformPosition(WorldPosition + NormalWorld * SurfaceOffsetCm);

	FVector ReferenceAxis = FMath::Abs(NormalLocal.Z) < 0.92f ? FVector::UpVector : FVector::RightVector;
	FVector Tangent = FVector::CrossProduct(ReferenceAxis, NormalLocal).GetSafeNormal(UE_SMALL_NUMBER, FVector::RightVector);
	FVector Bitangent = FVector::CrossProduct(NormalLocal, Tangent).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);

	const uint32 Serial = ++StainSerial;
	FRandomStream Stream(HashPosition(WorldPosition, Serial));
	const float Rotation = Stream.FRandRange(0.0f, 2.0f * PI);
	const float CosR = FMath::Cos(Rotation);
	const float SinR = FMath::Sin(Rotation);
	const FVector RotTangent = Tangent * CosR + Bitangent * SinR;
	const FVector RotBitangent = -Tangent * SinR + Bitangent * CosR;

	const float JitterAmount = FMath::Clamp(RadiusJitter, 0.0f, 0.95f);
	const float Radius = FMath::Max(0.1f, RadiusCm * Stream.FRandRange(1.0f - JitterAmount, 1.0f + JitterAmount));
	const float Stretch = Stream.FRandRange(0.78f, 1.35f);
	const float Squash = Stream.FRandRange(0.80f, 1.20f);

	const FVector P0 = CenterLocal + (-0.62f * RotTangent * Stretch - 0.45f * RotBitangent * Squash) * Radius;
	const FVector P1 = CenterLocal + ( 0.66f * RotTangent * Stretch - 0.36f * RotBitangent * Squash) * Radius;
	const FVector P2 = CenterLocal + ( 0.08f * RotTangent * Stretch + 0.78f * RotBitangent * Squash) * Radius;

	Vertices[BaseVertex + 0] = P0;
	Vertices[BaseVertex + 1] = P1;
	Vertices[BaseVertex + 2] = P2;

	Normals[BaseVertex + 0] = NormalLocal;
	Normals[BaseVertex + 1] = NormalLocal;
	Normals[BaseVertex + 2] = NormalLocal;

	UV0[BaseVertex + 0] = FVector2D(0.0f, 0.0f);
	UV0[BaseVertex + 1] = FVector2D(1.0f, 0.0f);
	UV0[BaseVertex + 2] = FVector2D(0.5f, 1.0f);

	VertexColors[BaseVertex + 0] = Color;
	VertexColors[BaseVertex + 1] = Color;
	VertexColors[BaseVertex + 2] = Color;

	const FProcMeshTangent ProcTangent(RotTangent, false);
	Tangents[BaseVertex + 0] = ProcTangent;
	Tangents[BaseVertex + 1] = ProcTangent;
	Tangents[BaseVertex + 2] = ProcTangent;
}

void AProphecyBloodStainRenderer::WriteHiddenTriangle(int32 StainIndex)
{
	const int32 BaseVertex = StainIndex * VerticesPerStain;
	if (!Vertices.IsValidIndex(BaseVertex + 2))
	{
		return;
	}

	const FVector Hidden = FVector::ZeroVector;
	for (int32 Offset = 0; Offset < VerticesPerStain; ++Offset)
	{
		Vertices[BaseVertex + Offset] = Hidden;
		Normals[BaseVertex + Offset] = FVector::UpVector;
		UV0[BaseVertex + Offset] = FVector2D::ZeroVector;
		VertexColors[BaseVertex + Offset] = FLinearColor::Transparent;
		Tangents[BaseVertex + Offset] = FProcMeshTangent(1.0f, 0.0f, 0.0f);
	}
}

FVector AProphecyBloodStainRenderer::MakeStableFallbackNormal(const FVector& Normal) const
{
	if (Normal.SizeSquared() > KINDA_SMALL_NUMBER)
	{
		return Normal.GetSafeNormal();
	}
	return FVector::UpVector;
}

AProphecyBloodStainRenderer* UProphecyBloodStainBlueprintLibrary::GetOrSpawnBloodStainRenderer(const UObject* WorldContextObject)
{
	UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	if (!World)
	{
		return nullptr;
	}

	for (TActorIterator<AProphecyBloodStainRenderer> It(World); It; ++It)
	{
		return *It;
	}

	FActorSpawnParameters SpawnParams;
	SpawnParams.Name = TEXT("ProphecyBloodStainRenderer");
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AProphecyBloodStainRenderer* Renderer = World->SpawnActor<AProphecyBloodStainRenderer>(FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
	if (Renderer)
	{
		Renderer->EnsureMeshInitialized();
	}
	return Renderer;
}

AProphecyBloodStainRenderer* UProphecyBloodStainBlueprintLibrary::AddBloodHitToWorld(const UObject* WorldContextObject, FVector WorldPosition, FVector WorldNormal, float RadiusCm, FLinearColor Color)
{
	AProphecyBloodStainRenderer* Renderer = GetOrSpawnBloodStainRenderer(WorldContextObject);
	if (Renderer)
	{
		Renderer->AddBloodHit(WorldPosition, WorldNormal, RadiusCm, Color);
		Renderer->FlushPendingStains();
	}
	return Renderer;
}

AProphecyBloodStainRenderer* UProphecyBloodStainBlueprintLibrary::AddBloodParticleDataToWorld(const UObject* WorldContextObject, const TArray<FBasicParticleData>& Data, FVector SimulationPositionOffset)
{
	AProphecyBloodStainRenderer* Renderer = GetOrSpawnBloodStainRenderer(WorldContextObject);
	if (Renderer)
	{
		Renderer->AddBloodParticleData(Data, SimulationPositionOffset);
	}
	return Renderer;
}

AProphecyBloodStainRenderer* UProphecyBloodStainBlueprintLibrary::BindBloodRendererAsNiagaraExportCallback(const UObject* WorldContextObject, UNiagaraComponent* NiagaraComponent, FName CallbackUserParameterName)
{
	AProphecyBloodStainRenderer* Renderer = GetOrSpawnBloodStainRenderer(WorldContextObject);
	if (Renderer)
	{
		Renderer->BindAsNiagaraExportCallback(NiagaraComponent, CallbackUserParameterName);
	}
	return Renderer;
}
