#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyVDBColorComponent.generated.h"

namespace ProphecyVDB
{
inline FLinearColor DefaultTemperatureColor(){return FLinearColor(.99f,.13f,.011f,1.f);}
inline bool IsValidColor(const FLinearColor& Color)
{
    return FMath::IsFinite(Color.R) && FMath::IsFinite(Color.G) && FMath::IsFinite(Color.B)
        && FMath::IsFinite(Color.A) && Color.R>=0.f && Color.G>=0.f && Color.B>=0.f;
}
}

// Only non-default bomb colors need deferred storage; this component never ticks.
// Separate from existing retained components so the change is safe to Live Code.
UCLASS(Transient)
class UProphecyBombVDBColorComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyBombVDBColorComponent(){PrimaryComponentTick.bCanEverTick=false;PrimaryComponentTick.bStartWithTickEnabled=false;}
    FLinearColor TemperatureColor=ProphecyVDB::DefaultTemperatureColor();
    FLinearColor ScatteringColor=FLinearColor::White;
};
