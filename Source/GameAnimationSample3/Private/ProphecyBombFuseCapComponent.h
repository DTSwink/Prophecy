#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyBombFuseCapComponent.generated.h"

/** Optional early detonation deadline; the existing controller owns the burn clock. */
UCLASS(Transient)
class UProphecyBombFuseCapComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyBombFuseCapComponent();
    uint64 DetonationTicks=0;
};
