#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "RenderCommandFence.h"
#include "ProphecyVDBOptimisedComponent.generated.h"

class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class FFloatProperty;
class FBoolProperty;

// Optional marker on a burning bomb; no ticking or changes to the existing bomb layout.
UCLASS(Transient)
class UProphecyBombVDBOptimisedComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyBombVDBOptimisedComponent(){PrimaryComponentTick.bCanEverTick=false;PrimaryComponentTick.bStartWithTickEnabled=false;}
};

// Owns only the optional cached renderer. The existing playback controller retains
// the authored clock, density and lifetime; the original actor retains GPU resources.
UCLASS(Transient)
class UProphecyVDBOptimisedComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyVDBOptimisedComponent();
    bool Initialize(UActorComponent* InPlayback,UActorComponent* InMaterial,UActorComponent* Clock,int32 Frames);
    virtual void TickComponent(float DeltaSeconds,ELevelTick TickType,FActorComponentTickFunction* TickFunction) override;
    bool IsCached() const{return bCached;}
private:
    void RestoreLiveRenderer();
    bool CapturePreparedVolume();
    UPROPERTY(Transient) TObjectPtr<UActorComponent> Playback;
    UPROPERTY(Transient) TObjectPtr<UActorComponent> Material;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> SourceMesh;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> CachedMesh;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> CachedMaterial;
    UPROPERTY(Transient) TArray<TObjectPtr<UActorComponent>> SuspendedComponents;
    FFloatProperty* FrameProperty=nullptr;
    FFloatProperty* DensityProperty=nullptr;
    FBoolProperty* VisibleProperty=nullptr;
    FRenderCommandFence PreparationFence;
    FTransform PreparedTransform;
    uint64 LastGameFrame=0,CandidateFrame=0;
    float PreparedDensity=1.f,CandidateRenderTime=0.f;
    int32 FrameCount=0;
    uint8 Phase=0;
    bool bCached=false,bActorTickWasEnabled=false;
};
