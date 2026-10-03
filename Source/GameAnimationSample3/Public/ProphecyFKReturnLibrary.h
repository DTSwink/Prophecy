#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyFKReturnLibrary.generated.h"
class AProphecyAgent;

/** Symmetric parent-local inertia multipliers. Hands deliberately have no local inertia. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyFKInertiaWeights
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float Spine=0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float Clavicle=.19f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float UpperArm=1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float LowerArm=.63f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float Neck01=1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float Neck02=1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="FK Return", meta=(ClampMin="0", ClampMax="1")) float Head=1.f;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyFKReturnLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Enabled by default for all attacks. At attack end, use the lab's FK idle return and
     * blend toward the upper NN, which predicts from the accepted blended pose.
     * Alpha Hold 0.5 keeps full FK control for the first half, then blends over the
     * remaining half. 0 preserves immediate blending; 1 holds until the deadline.
     * The coefficient shapes this remaining blend window; FK motion continues during hold.
     * 1 = linear; 2 = NN takes over later. Disabled gives unfiltered NN immediately.
     * Configuration affects the next attack end; disabling also cancels a running return.
     * Lower-body controls are unchanged. Old upper recovery/tempering nodes no longer
     * modify locomotion output. Each duration second means 60 unpaused game ticks,
     * independent of FPS/time dilation. Hitches never catch up this timer. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Recovery", meta=(DefaultToSelf="Agent", DisplayName="Set Attack FK Return"))
    static bool SetAttackFKReturn(AProphecyAgent* Agent, bool Enabled=true,
        UPARAM(meta=(ClampMin="0.01", UIMin="0.1", UIMax="5")) float NNTakeoverCoefficient=1.f,
        UPARAM(meta=(ClampMin="0", ClampMax="1")) float AlphaHold=0.f);

    /** Override one attack family's lab profile. None applies to all families.
     * Accepted lab profiles are already installed; this node is optional.
     * Effective inertia = Inertia * the bone group's weight. Easing 0 is linear,
     * 1 is quintic smoothstep. Hands follow their parents and return without local inertia. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Recovery", meta=(DefaultToSelf="Agent", DisplayName="Set Attack FK Return Profile", AdvancedDisplay="BoneInertia"))
    static bool SetAttackFKReturnProfile(AProphecyAgent* Agent, FName Attack=NAME_None,
        UPARAM(meta=(ClampMin="0")) float ReturnTime=.26f,
        UPARAM(meta=(ClampMin="0", ClampMax="1")) float Inertia=.51f,
        UPARAM(meta=(ClampMin="0", ClampMax="1")) float Easing=.12f,
        FProphecyFKInertiaWeights BoneInertia=FProphecyFKInertiaWeights());
};
