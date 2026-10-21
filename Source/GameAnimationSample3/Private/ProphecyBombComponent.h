#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyVDBLibrary.h"
#include "ProphecyBombComponent.generated.h"
class UStaticMeshComponent;
class UStaticMesh;
class UMaterialInstanceDynamic;
class UNiagaraComponent;

UCLASS(Transient)
class UProphecyBombComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyBombComponent();
    virtual void TickComponent(float DeltaSeconds,ELevelTick TickType,FActorComponentTickFunction* TickFunction) override;
    void Detonate();
    bool GetBurnTip(FVector& Position,FVector& Tangent) const;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Bomb;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> Material;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Visual;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> ShellVisual;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Sparks;
    UPROPERTY(Transient) TObjectPtr<UObject> EffectAsset;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMesh>> Fragments;
    UPROPERTY(Transient) TArray<TObjectPtr<AActor>> Debris;
    EProphecyVDBEffect Effect=EProphecyVDBEffect::ShockwaveExplosion;
    FRotator Rotation=FRotator::ZeroRotator;
    float FragmentVelocity=700,Intensity=1000,Radius=500,FalloffExponent=2,ExplosionVelocity=0;
    float Scale=1,Framerate=30,FadeStart=3,TargetDensity=0,FadeDuration=1;
    uint64 Elapsed=0,BurnTicks=1,DebrisTicks=480,LastFrame=0;
    bool bDebris=false;
    bool bBurning=false;
    bool bFuseHidden=false;
};
