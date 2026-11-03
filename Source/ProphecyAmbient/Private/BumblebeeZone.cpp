#include "BumblebeeZone.h"
#include "BumblebeeSwarm.h"
#include "Components/BillboardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/Texture2D.h"
#include "UObject/ConstructorHelpers.h"

ABumblebeeZone::ABumblebeeZone()
{
	PrimaryActorTick.bCanEverTick = false;
	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	Box->SetBoxExtent(BoxExtent);
	Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Box->SetCanEverAffectNavigation(false);
	Box->SetGenerateOverlapEvents(false);
	Box->ShapeColor = FColor(255, 190, 0);
	Box->SetLineThickness(4.f);
	Box->bHiddenInGame = true;
	RootComponent = Box;

	Label = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	Label->SetupAttachment(Box);
	Label->SetHorizontalAlignment(EHTA_Center);
	Label->SetTextRenderColor(FColor(255, 200, 0));
	Label->SetWorldSize(40.f);
	Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Label->SetCastShadow(false);
	Label->bHiddenInGame = true;

#if WITH_EDITORONLY_DATA
	Sprite = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("Sprite"));
	if (Sprite)
	{
		static ConstructorHelpers::FObjectFinderOptional<UTexture2D> Icon(TEXT("/Engine/EditorResources/S_Emitter"));
		Sprite->Sprite = Icon.Get();
		Sprite->SetupAttachment(Box);
		Sprite->SetRelativeScale3D(FVector(1.5f));
		Sprite->bIsScreenSizeScaled = true;
	}
#endif
#if WITH_EDITOR
	// Tiny actor that owns persistent bee state: keep it loaded in World Partition.
	SetIsSpatiallyLoaded(false);
#endif
}

void ABumblebeeZone::RefreshVisuals()
{
	Box->SetBoxExtent(BoxExtent.ComponentMax(FVector(10.f)));
	if (Label)
	{
		Label->SetText(FText::FromString(FString::Printf(TEXT("Bumblebee Zone\n%d bees  pref %.2f  size x%.2f\nwings %.0f Hz  walk %.1f cm/s  air %.2f"),
			BeeCount, Preference, BeeSizeMultiplier, WingBeatHz, WalkSpeed, AirTime)));
		Label->SetRelativeLocation(FVector(0.f, 0.f, BoxExtent.Z + 30.f));
		Label->SetRelativeRotation(FRotator(0.f, 180.f, 0.f));
	}
#if WITH_EDITORONLY_DATA
	if (Sprite) Sprite->SetRelativeLocation(FVector(0.f, 0.f, BoxExtent.Z));
#endif
}

void ABumblebeeZone::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RefreshVisuals();
}

#if WITH_EDITOR
void ABumblebeeZone::PostEditChangeProperty(FPropertyChangedEvent& Event)
{
	Super::PostEditChangeProperty(Event);
	RefreshVisuals();
}
#endif

void ABumblebeeZone::SetShowInGame(bool bShow)
{
	bShowInGame = bShow;
	Box->SetHiddenInGame(!bShow);
	if (Label) Label->SetHiddenInGame(!bShow);
}

void ABumblebeeZone::BeginPlay()
{
	RefreshVisuals();
	SetShowInGame(bShowInGame);
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
