#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyBombFragmentFadeComponent.generated.h"
class UMaterialInterface;
class UMaterialInstanceDynamic;

// Separate new class keeps existing bomb/controller instance layouts reload-safe.
// No independent tick: the existing debris controller advances the shared opacity.
UCLASS(Transient)
class UProphecyBombFragmentFadeComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyBombFragmentFadeComponent(){PrimaryComponentTick.bCanEverTick=false;PrimaryComponentTick.bStartWithTickEnabled=false;}
    uint64 FadeTicks=0;
    bool bApplied=false;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> Template;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> Material;
};
