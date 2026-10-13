#pragma once

#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimInstance.h"
#include "ProphecyHolsterStrapComponent.generated.h"

/** Cosmetic, collision-free five-bone strap using the engine AnimDynamics solver. */
UCLASS(ClassGroup=(Prophecy), meta=(BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyHolsterStrapComponent : public USkeletalMeshComponent
{
    GENERATED_BODY()
public:
    UProphecyHolsterStrapComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, BlueprintSetter=SetStrapEnabled, Category="Holster Strap")
    bool bStrapEnabled=true;
    /** Zero removes distance culling. A 10% hysteresis prevents boundary flicker. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Holster Strap", meta=(ClampMin="0", Units="cm"))
    float MaxSimulationDistance=1500.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Holster Strap", meta=(ClampMin="0"))
    float Stiffness=20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Holster Strap", meta=(ClampMin="0.7", ClampMax="10"))
    float Damping=1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Holster Strap", meta=(ClampMin="0", ClampMax="180", Units="deg"))
    float MaxBendAngle=65.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Holster Strap", meta=(ClampMin="0"))
    float StrapGravityScale=1.f;
    UFUNCTION(BlueprintCallable, BlueprintSetter, Category="Holster Strap", meta=(DisplayName="Set Holster Strap Enabled"))
    void SetStrapEnabled(bool bEnabled);
    UFUNCTION(BlueprintPure, Category="Holster Strap")
    bool IsStrapSimulating() const { return bRunning; }
    UFUNCTION(BlueprintCallable, Category="Holster Strap", meta=(DisplayName="Reset Holster Strap"))
    void ResetStrap();
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
protected:
    virtual void BeginPlay() override;
private:
    void UpdateEligibility();
    void SetRunning(bool bRun);
    bool bRunning=false;
    uint8 GateTicks=0;
    FTransform LastTransform;
};

UCLASS(Transient)
class GAMEANIMATIONSAMPLE3_API UProphecyHolsterStrapAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};
