#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyExplosionReceiverComponent.generated.h"

class UPrimitiveComponent;

USTRUCT(BlueprintType)
struct PROPHECYJOLT_API FProphecyExplosionImpact
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly, Category="Explosion") FVector ExplosionOrigin = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category="Explosion") FVector ImpactLocation = FVector::ZeroVector;
    /** Actual momentum applied to the first affected body, in kg cm/s; not the sum across limbs. */
    UPROPERTY(BlueprintReadOnly, Category="Explosion") FVector Impulse = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category="Explosion") FName BoneName;
    UPROPERTY(BlueprintReadOnly, Category="Explosion") TObjectPtr<UPrimitiveComponent> HitComponent = nullptr;
};

DECLARE_DYNAMIC_DELEGATE_OneParam(FProphecyExplosionImpactCallback, const FProphecyExplosionImpact&, Impact);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FProphecyExplosionImpactEvent, const FProphecyExplosionImpact&, Impact);

/** One receiver per actor, shared by every physical limb. No tick when idle. */
UCLASS(ClassGroup=(Prophecy), meta=(BlueprintSpawnableComponent))
class PROPHECYJOLT_API UProphecyExplosionReceiverComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyExplosionReceiverComponent();
    /** First delivered explosion impact fires immediately; ignored impacts do not extend the 30-tick cooldown. */
    UPROPERTY(BlueprintAssignable, Category="Prophecy|Physics") FProphecyExplosionImpactEvent OnExplosionImpact;
    // Native delivery reserves the gate before executing any Blueprint callbacks.
    bool TryAcceptImpact();
protected:
    virtual void OnUnregister() override;
private:
    void AdvanceCooldown(UWorld* World, ELevelTick TickType, float DeltaSeconds);
    void StopCooldown();
    int32 RemainingTicks = 0;
    FDelegateHandle CooldownHandle;
};
