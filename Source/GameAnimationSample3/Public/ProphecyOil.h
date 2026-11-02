#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyOil.generated.h"
class UMaterialInterface;
class UNiagaraSystem;
class UProphecyPhysicsStaticMeshComponent;
class UDecalComponent;
class UMaterialInstanceDynamic;
class UInstancedStaticMeshComponent;
struct FProphecyJoltRayHit;
struct FProphecyOilSpillState;
struct FProphecyOilSpillStateDeleter { void operator()(FProphecyOilSpillState*) const; };

USTRUCT(BlueprintType)
struct FProphecyOilSettings
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil",meta=(ClampMin="10",ClampMax="600")) float Radius=180;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil",meta=(ClampMin="0",ClampMax="1")) float Slipperiness=1;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil",meta=(ClampMin="0")) float HoldDuration=4;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil",meta=(ClampMin="0")) float FadeDuration=4;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") TObjectPtr<UMaterialInterface> DecalMaterial;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") TObjectPtr<UMaterialInterface> TintMaterial;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") TObjectPtr<UNiagaraSystem> SplashSystem;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") TObjectPtr<UMaterialInterface> DropletMaterial;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil",meta=(ClampMin="8",ClampMax="64")) int32 DropletCount=56;
};

UCLASS(BlueprintType)
class GAMEANIMATIONSAMPLE3_API AProphecyOilSpill : public AActor
{
    GENERATED_BODY()
public:
    AProphecyOilSpill();
    ~AProphecyOilSpill();
    bool Initialize(const FVector& Location,const FVector& Normal,const FProphecyOilSettings& InSettings);
    bool InitializeSplash(const FVector& Location,const FVector& Normal,const FVector& Velocity,const FProphecyOilSettings& InSettings);
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    UFUNCTION(BlueprintPure,Category="Oil") float GetOilAmount() const;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Oil") FProphecyOilSettings Settings;
private:
    bool Prepare(const FVector& Location,const FVector& Normal,const FProphecyOilSettings& InSettings);
    bool Deposit(const FProphecyJoltRayHit& Hit,float Radius,bool bFreshLanding);
    TUniquePtr<FProphecyOilSpillState,FProphecyOilSpillStateDeleter> State;
    UPROPERTY(Transient) TArray<TObjectPtr<UDecalComponent>> Decals;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> Materials;
    UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> Droplets;
};

UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyOilBottle : public AActor
{
    GENERATED_BODY()
public:
    AProphecyOilBottle();
    virtual void BeginPlay() override;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Oil") TObjectPtr<UProphecyPhysicsStaticMeshComponent> Bottle;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") FProphecyOilSettings Oil;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") FVector LaunchVelocity=FVector(700,0,100);
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil") bool bLaunchOnPlay=true;
    /** Incoming relative contact speed in cm/s, including rotation. Only evaluated on hits. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Breaking",meta=(ClampMin="0")) float BreakImpactSpeed=250;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Breaking") bool bBreakOnHit=true;
    UPROPERTY(VisibleInstanceOnly,BlueprintReadOnly,Category="Oil|Breaking") float LastImpactSpeed=0;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Debris") bool bSpawnFragments=true;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Debris") TArray<TObjectPtr<UStaticMesh>> FragmentMeshes;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Debris",meta=(ClampMin="0")) float FragmentVelocity=120;
    /** Authored seconds: 60 unpaused game ticks. Includes the fade. Zero suppresses debris. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Debris",meta=(ClampMin="0",ClampMax="600")) float FragmentLifetime=4;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil|Debris",meta=(ClampMin="0",ClampMax="600")) float FragmentFadeDuration=1;
    UFUNCTION(BlueprintCallable,Category="Oil") void BreakBottle(const FVector& Location,const FVector& Normal);
private:
    bool bBroken=false;
    UFUNCTION() void Hit(UPrimitiveComponent* HitComponent,AActor* OtherActor,UPrimitiveComponent* OtherComponent,FVector Impulse,const FHitResult& HitResult);
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyOilLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable,Category="Prophecy|Oil",meta=(WorldContext="WorldContextObject"))
    static AProphecyOilSpill* SpawnOilSpill(UObject* WorldContextObject,FVector Location,FVector SurfaceNormal,const FProphecyOilSettings& Settings);
};
