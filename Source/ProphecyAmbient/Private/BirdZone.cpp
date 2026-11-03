#include "BirdZone.h"
#include "Bird.h"
#include "BirdFlock.h"
#include "Components/BillboardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/TextRenderComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "UObject/ConstructorHelpers.h"

ABirdZone::ABirdZone()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickInterval = 0.f;
	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	Box->SetBoxExtent(BoxExtent);
	Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Box->SetCanEverAffectNavigation(false);
	Box->SetGenerateOverlapEvents(false);
	Box->ShapeColor = FColor(80, 200, 255);
	Box->SetLineThickness(6.f);
	Box->bHiddenInGame = true;
	RootComponent = Box;
	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(Box);
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetTextRenderColor(FColor(90, 210, 255));
	Label->SetWorldSize(70.f);
	Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Label->SetCastShadow(false);
	Label->bHiddenInGame = true;
#if WITH_EDITORONLY_DATA
	Icon = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("Sprite"));
	if (Icon)
	{
		static ConstructorHelpers::FObjectFinderOptional<UTexture2D> Tex(TEXT("/Engine/EditorResources/S_Emitter"));
		Icon->Sprite = Tex.Get();
		Icon->SetupAttachment(Box);
		Icon->SetRelativeScale3D(FVector(2.f));
		Icon->bIsScreenSizeScaled = true;
	}
#endif
#if WITH_EDITOR
	SetIsSpatiallyLoaded(false);
#endif
	Settings = FBirdSpeciesSettings::Defaults(EBirdSpecies::Gull);
}

void ABirdZone::UpdateLabel()
{
	Box->SetBoxExtent(BoxExtent.ComponentMax(FVector(100.f)));
	if (Label)
	{
		Label->SetText(FText::FromString(FString::Printf(TEXT("Bird Zone: %d %s%s\nair %.2f  size x%.2f  cries %s"),
			BirdCount, Species == EBirdSpecies::Gull ? TEXT("gull") : TEXT("kingfisher"), BirdCount == 1 ? TEXT("") : TEXT("s"),
			AirTime, SizeMultiplier, bAmbientCries ? TEXT("on") : TEXT("off"))));
		Label->SetRelativeLocation(FVector(0.f, 0.f, BoxExtent.Z + 60.f));
		Label->SetRelativeRotation(FRotator(0.f, 180.f, 0.f));
	}
#if WITH_EDITORONLY_DATA
	if (Icon) Icon->SetRelativeLocation(FVector(0.f, 0.f, BoxExtent.Z));
#endif
}

void ABirdZone::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	if (!bOverrideSettings) Settings = FBirdSpeciesSettings::Defaults(Species);
	UpdateLabel();
}

void ABirdZone::SetShowInGame(bool bShow)
{
	bShowInGame = bShow;
	Box->SetHiddenInGame(!bShow);
	if (Label) Label->SetHiddenInGame(!bShow);
}

FBirdSpeciesSettings ABirdZone::EffectiveSettings() const
{
	return bOverrideSettings ? Settings : FBirdSpeciesSettings::Defaults(Species);
}

void ABirdZone::BeginPlay()
{
	UpdateLabel();
	SetShowInGame(bShowInGame);
	Super::BeginPlay();
	Rng.Initialize(Seed != 0 ? Seed : int32(GetUniqueID() * 2654435761u));
	ABirdFlock::Find(this, true);
	PendingSpawn = BirdCount;
}

void ABirdZone::EndPlay(const EEndPlayReason::Type Reason)
{
	for (ABird* B : SpawnedBirds) if (IsValid(B)) B->Destroy();
	SpawnedBirds.Reset();
	Super::EndPlay(Reason);
}

TArray<ABird*> ABirdZone::GetBirds() const
{
	TArray<ABird*> Out;
	for (ABird* B : SpawnedBirds) if (IsValid(B)) Out.Add(B);
	return Out;
}

void ABirdZone::SetColours(FLinearColor Primary, FLinearColor Secondary)
{
	PrimaryColour = Primary;
	SecondaryColour = Secondary;
	for (ABird* B : SpawnedBirds) if (IsValid(B)) B->SetColours(Primary, Secondary);
}

ABird* ABirdZone::MakeBirdCry(FVector Near, float Duration)
{
	ABird* Pick = nullptr;
	float Best = 1e30f;
	for (ABird* B : SpawnedBirds)
	{
		if (!IsValid(B) || B->IsDead() || B->GetState() == EBirdState::Unplaced) continue;
		const float D = Near.IsZero() ? Rng.FRand() : FVector::DistSquared(B->GetPos(), Near);
		if (D < Best) { Best = D; Pick = B; }
	}
	if (Pick) Pick->Cry(Duration, 1.f);
	return Pick;
}

void ABirdZone::HandleBirdCry(ABird* Bird, float Duration)
{
	OnZoneBirdCry.Broadcast(Bird, Duration);
}

bool ABirdZone::IsInside(const FVector& P, float Margin) const
{
	const FTransform& T = Box->GetComponentTransform();
	const FVector L = T.InverseTransformPosition(P);
	const FVector Sc = T.GetScale3D().GetAbs().ComponentMax(FVector(KINDA_SMALL_NUMBER));
	const FVector E = Box->GetUnscaledBoxExtent() + FVector(Margin) / Sc;
	return FMath::Abs(L.X) <= E.X && FMath::Abs(L.Y) <= E.Y && FMath::Abs(L.Z) <= E.Z;
}

FVector ABirdZone::RandomPoint(FRandomStream& R, float Grow) const
{
	const FVector E = Box->GetUnscaledBoxExtent();
	const FVector L(R.FRandRange(-E.X, E.X) * Grow, R.FRandRange(-E.Y, E.Y) * Grow, R.FRandRange(-E.Z, E.Z));
	return Box->GetComponentTransform().TransformPosition(L);
}

FBox ABirdZone::WorldBounds(float Grow) const
{
	const FVector E = Box->GetUnscaledBoxExtent() * FVector(Grow, Grow, 1.f);
	return FBox(-E, E).TransformBy(Box->GetComponentTransform());
}

FVector ABirdZone::GetCenter() const
{
	return Box->GetComponentLocation();
}

void ABirdZone::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (PendingSpawn <= 0) { SetActorTickEnabled(false); return; }
	Check -= DeltaSeconds;
	if (!bSpawned)
	{
		if (Check > 0.f) return;
		Check = 0.5f;
		bool bNear = ActivationDistance <= 0.f;
		for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It && !bNear; ++It)
		{
			const APlayerController* PC = It->Get();
			if (PC && PC->PlayerCameraManager && WorldBounds(1.f).ComputeSquaredDistanceToPoint(PC->PlayerCameraManager->GetCameraLocation()) < FMath::Square(ActivationDistance)) bNear = true;
		}
		if (!bNear) return;
		bSpawned = true;
	}
	TrySpawn();
}

void ABirdZone::TrySpawn()
{
	ABirdFlock* Flock = ABirdFlock::Find(this, true);
	if (!Flock) return;
	const FBirdSpeciesSettings S = EffectiveSettings();
	for (int32 n = 0; n < 2 && PendingSpawn > 0; ++n)
	{
		--PendingSpawn;
		FActorSpawnParameters P;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		P.ObjectFlags |= RF_Transient;
		const FVector Start = GetCenter() + FVector(0, 0, BoxExtent.Z);
		ABird* B = GetWorld()->SpawnActor<ABird>(ABird::StaticClass(), Start, FRotator::ZeroRotator, P);
		if (!B) continue;
		B->Setup(Flock, this, Species, S, SizeMultiplier * Rng.FRandRange(0.94f, 1.06f), Rng.RandHelper(0x7fffffff));
		auto Jitter = [&](const FLinearColor& C)
		{
			const float V = 1.f + Rng.FRandRange(-ColourVariation, ColourVariation);
			return FLinearColor(C.R * V * (1.f + Rng.FRandRange(-0.3f, 0.3f) * ColourVariation), C.G * V, C.B * V, 1.f);
		};
		B->SetColours(Jitter(PrimaryColour), Jitter(SecondaryColour));
		SpawnedBirds.Add(B);
		const bool bAir = Rng.FRand() < AirTime * 0.6f;
		if (bAir || !B->PlaceOnRandomSpot(Start))
		{
			FVector C = RandomPoint(Rng, 1.f);
			C.Z = WorldBounds().Max.Z + Rng.FRandRange(S.CruiseHeight.X, S.CruiseHeight.Y) * 0.5f;
			B->PlaceFlying(C, FRotator(Rng.FRandRange(-5.f, 5.f), Rng.FRandRange(0.f, 360.f), 0.f).Vector() * S.CruiseSpeed);
		}
	}
}
