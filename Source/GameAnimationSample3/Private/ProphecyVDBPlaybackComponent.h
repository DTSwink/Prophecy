#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyVDBTiming.h"
#include "ProphecyVDBPlaybackComponent.generated.h"

class FFloatProperty;

/** Runtime-only lifetime controller for effects created by Spawn VDB Effect. */
UCLASS(Transient)
class UProphecyVDBPlaybackComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyVDBPlaybackComponent();
    bool Initialize(UActorComponent* InPlayback,UActorComponent* InMaterial,int32 Frames,
        float FPS,float FadeStart,float FadeDuration,float Target);
    virtual void TickComponent(float DeltaSeconds,ELevelTick TickType,FActorComponentTickFunction* TickFunction) override;
private:
    UPROPERTY(Transient) TObjectPtr<UActorComponent> Playback;
    UPROPERTY(Transient) TObjectPtr<UActorComponent> Material;
    FFloatProperty* FrameProperty=nullptr;
    FFloatProperty* DensityProperty=nullptr;
    ProphecyVDB::FTimeline Timeline;
    uint64 ElapsedTicks=0, LastGameFrame=0;
};
