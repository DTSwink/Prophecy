#include "BumblebeeZone.h"
#include "BumblebeeSwarm.h"
#include "Components/BoxComponent.h"

ABumblebeeZone::ABumblebeeZone()
{
	PrimaryActorTick.bCanEverTick = false;
	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	Box->SetBoxExtent(FVector(500.f, 500.f, 250.f));
	Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Box->SetCanEverAffectNavigation(false);
	Box->ShapeColor = FColor(255, 196, 0);
	Box->SetLineThickness(2.f);
	Box->bHiddenInGame = true;
	RootComponent = Box;
#if WITH_EDITOR
	// Tiny actor that owns persistent bee state: keep it loaded in World Partition.
	SetIsSpatiallyLoaded(false);
#endif
}

void ABumblebeeZone::BeginPlay()
{
	Super::BeginPlay();
	if (ABumblebeeSwarm* Swarm = ABumblebeeSwarm::GetOrCreate(this))
	{
		Swarm->RegisterZone(this);
	}
}

void ABumblebeeZone::EndPlay(const EEndPlayReason::Type Reason)
{
	if (ABumblebeeSwarm* Swarm = ABumblebeeSwarm::Find(this))
	{
		Swarm->UnregisterZone(this);
	}
	Super::EndPlay(Reason);
}

bool ABumblebeeZone::IsInside(const FVector& P, float Margin) const
{
	const FTransform& T = Box->GetComponentTransform();
	const FVector L = T.InverseTransformPosition(P);
	const FVector S = T.GetScale3D().GetAbs();
	const FVector E = Box->GetUnscaledBoxExtent() + FVector(Margin) / S.ComponentMax(FVector(KINDA_SMALL_NUMBER));
	return FMath::Abs(L.X) <= E.X && FMath::Abs(L.Y) <= E.Y && FMath::Abs(L.Z) <= E.Z;
}

FVector ABumblebeeZone::RandomPoint(FRandomStream& Rng, float TopBias) const
{
	const FVector E = Box->GetUnscaledBoxExtent();
	const float Z = FMath::Lerp(Rng.FRandRange(-1.f, 1.f), 1.f, TopBias);
	const FVector L(Rng.FRandRange(-E.X, E.X), Rng.FRandRange(-E.Y, E.Y), Z * E.Z);
	return Box->GetComponentTransform().TransformPosition(L);
}

FVector ABumblebeeZone::GetCenter() const
{
	return Box->GetComponentLocation();
}
