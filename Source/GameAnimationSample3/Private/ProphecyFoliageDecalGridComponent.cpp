#include "ProphecyFoliageDecalGridComponent.h"

#include "Components/DecalComponent.h"
#include "Components/PrimitiveComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
DEFINE_LOG_CATEGORY_STATIC(LogProphecyFoliageDecalGrid, Log, All);

FVector SafeNormalOrUp(const FVector& Value)
{
	return Value.GetSafeNormal(KINDA_SMALL_NUMBER, FVector::UpVector);
}

bool IsLikelyFoliageDecalGridComponent(const UObject* Object)
{
	if (!Object)
	{
		return false;
	}

	if (Object->IsA<UProphecyFoliageDecalGridComponent>())
	{
		return true;
	}

	const UClass* Class = Object->GetClass();
	return Class && Class->GetName().Contains(TEXT("ProphecyFoliageDecalGrid"));
}

int32 AddFloorHitToFoliageDecalGridObject(UObject* DecalGridObject, const FHitResult& Hit, float RadiusCm)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		return DecalGrid->AddFloorHitToGrid(Hit, RadiusCm);
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return 0;
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("AddFloorHitToGrid"));
	if (!Function)
	{
		return 0;
	}

	struct FAddFloorHitToGridParams
	{
		FHitResult Hit;
		float RadiusCm = 35.0f;
		int32 ReturnValue = 0;
	};

	FAddFloorHitToGridParams Params;
	Params.Hit = Hit;
	Params.RadiusCm = RadiusCm;
	DecalGridObject->ProcessEvent(Function, &Params);
	return Params.ReturnValue;
}

void SetFoliageGridMergeProcessingEnabledObject(UObject* DecalGridObject, bool bEnabled)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		DecalGrid->SetMergeProcessingEnabled(bEnabled);
		return;
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return;
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("SetMergeProcessingEnabled"));
	if (!Function)
	{
		return;
	}

	struct FSetMergeProcessingEnabledParams
	{
		bool bEnabled = false;
	};

	FSetMergeProcessingEnabledParams Params;
	Params.bEnabled = bEnabled;
	DecalGridObject->ProcessEvent(Function, &Params);
}

TArray<UDecalComponent*> GetActiveFoliageGridDecalsObject(UObject* DecalGridObject)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		return DecalGrid->GetActiveFoliageGridDecals();
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return TArray<UDecalComponent*>();
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("GetActiveFoliageGridDecals"));
	if (!Function)
	{
		return TArray<UDecalComponent*>();
	}

	struct FGetActiveFoliageGridDecalsParams
	{
		TArray<UDecalComponent*> ReturnValue;
	};

	FGetActiveFoliageGridDecalsParams Params;
	DecalGridObject->ProcessEvent(Function, &Params);
	return Params.ReturnValue;
}

void DrawFoliageGridDecalBoundsObject(UObject* DecalGridObject, float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels)
{
	if (UProphecyFoliageDecalGridComponent* DecalGrid = Cast<UProphecyFoliageDecalGridComponent>(DecalGridObject))
	{
		DecalGrid->DrawActiveFoliageGridDecalBounds(DurationSeconds, LineThickness, BoundsHeightCm, LineColor, bColorByMergeLevel, bDrawLabels);
		return;
	}

	if (!IsLikelyFoliageDecalGridComponent(DecalGridObject))
	{
		return;
	}

	UFunction* Function = DecalGridObject->FindFunction(TEXT("DrawActiveFoliageGridDecalBounds"));
	if (!Function)
	{
		return;
	}

	struct FDrawActiveFoliageGridDecalBoundsParams
	{
		float DurationSeconds = 0.1f;
		float LineThickness = 2.0f;
		float BoundsHeightCm = 8.0f;
		FLinearColor LineColor = FLinearColor(0.0f, 1.0f, 0.0f, 1.0f);
		bool bColorByMergeLevel = true;
		bool bDrawLabels = true;
	};

	FDrawActiveFoliageGridDecalBoundsParams Params;
	Params.DurationSeconds = DurationSeconds;
	Params.LineThickness = LineThickness;
	Params.BoundsHeightCm = BoundsHeightCm;
	Params.LineColor = LineColor;
	Params.bColorByMergeLevel = bColorByMergeLevel;
	Params.bDrawLabels = bDrawLabels;
	DecalGridObject->ProcessEvent(Function, &Params);
}
}

UProphecyFoliageDecalGridComponent::UProphecyFoliageDecalGridComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	PrimaryComponentTick.bStartWithTickEnabled = false;

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DecalMaterialFinder(TEXT("/Game/_mygame/blood2/MI_blooddecal.MI_blooddecal"));
	if (DecalMaterialFinder.Succeeded())
	{
		DecalMaterial = DecalMaterialFinder.Object;
	}
}

void UProphecyFoliageDecalGridComponent::BeginPlay()
{
	Super::BeginPlay();
	RefreshMergeTimer();
	RefreshStats();
}

void UProphecyFoliageDecalGridComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(MergeTimerHandle);
	}
	ClearFoliageDecalGrid();
	Super::EndPlay(EndPlayReason);
}

#include "ProphecyDecalRectangles.inl"
#include "Tests/ProphecyDecalRectanglesTests.inl"

int32 UProphecyFoliageDecalGridBlueprintLibrary::AddFloorHitToFoliageDecalGrid(UProphecyFoliageDecalGridComponent* DecalGrid, const FHitResult& Hit, float RadiusCm)
{
	return DecalGrid ? DecalGrid->AddFloorHitToGrid(Hit, RadiusCm) : 0;
}

int32 UProphecyFoliageDecalGridBlueprintLibrary::AddFloorHitToFoliageDecalGridRef(UObject* DecalGridRef, const FHitResult& Hit, float RadiusCm)
{
	return AddFloorHitToFoliageDecalGridObject(DecalGridRef, Hit, RadiusCm);
}

void UProphecyFoliageDecalGridBlueprintLibrary::SetFoliageGridMergeProcessingEnabled(UProphecyFoliageDecalGridComponent* DecalGrid, bool bEnabled)
{
	if (DecalGrid)
	{
		DecalGrid->SetMergeProcessingEnabled(bEnabled);
	}
}

void UProphecyFoliageDecalGridBlueprintLibrary::SetFoliageGridMergeProcessingEnabledRef(UObject* DecalGridRef, bool bEnabled)
{
	SetFoliageGridMergeProcessingEnabledObject(DecalGridRef, bEnabled);
}

TArray<UDecalComponent*> UProphecyFoliageDecalGridBlueprintLibrary::GetActiveFoliageGridDecals(UProphecyFoliageDecalGridComponent* DecalGrid)
{
	return DecalGrid ? DecalGrid->GetActiveFoliageGridDecals() : TArray<UDecalComponent*>();
}

TArray<UDecalComponent*> UProphecyFoliageDecalGridBlueprintLibrary::GetActiveFoliageGridDecalsRef(UObject* DecalGridRef)
{
	return GetActiveFoliageGridDecalsObject(DecalGridRef);
}

void UProphecyFoliageDecalGridBlueprintLibrary::DrawFoliageGridDecalBounds(UProphecyFoliageDecalGridComponent* DecalGrid, float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels)
{
	if (DecalGrid)
	{
		DecalGrid->DrawActiveFoliageGridDecalBounds(DurationSeconds, LineThickness, BoundsHeightCm, LineColor, bColorByMergeLevel, bDrawLabels);
	}
}

void UProphecyFoliageDecalGridBlueprintLibrary::DrawFoliageGridDecalBoundsRef(UObject* DecalGridRef, float DurationSeconds, float LineThickness, float BoundsHeightCm, FLinearColor LineColor, bool bColorByMergeLevel, bool bDrawLabels)
{
	DrawFoliageGridDecalBoundsObject(DecalGridRef, DurationSeconds, LineThickness, BoundsHeightCm, LineColor, bColorByMergeLevel, bDrawLabels);
}
