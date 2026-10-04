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
     * Each attack vector is X = Alpha Hold, Y = Trim, both fractions in [0,1].
     * Defaults are (0.1, 0.34) independently for every attack.
     * Alpha Hold 0.5 keeps full FK control for the first half, then blends over the
     * remaining half. 0 preserves immediate blending; 1 holds until the deadline.
     * The coefficient shapes this remaining blend window; FK motion continues during hold.
     * 1 = linear; 2 = NN takes over later. Disabled gives unfiltered NN immediately.
     * Trim removes this fraction from the end for that attack: 0 keeps the full
     * duration, 0.5 reaches full NN halfway through, 1 skips return. FK motion and
     * inertia retain their original timing; hold/takeover use the shortened window.
     * Configuration affects the next attack end; disabling also cancels a running return.
     * Lower-body controls are unchanged. Old upper recovery/tempering nodes no longer
     * modify locomotion output. Each duration second means 60 unpaused game ticks,
     * independent of FPS/time dilation. Hitches never catch up this timer. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Recovery", meta=(DefaultToSelf="Agent", DisplayName="Set Attack FK Return"))
    static bool SetAttackFKReturn(AProphecyAgent* Agent, bool Enabled=true,
        UPARAM(meta=(ClampMin="0.01", UIMin="0.1", UIMax="5")) float NNTakeoverCoefficient=1.f,
        FVector2D Headbutt=FVector2D(0.1, 0.34),
        FVector2D HookL=FVector2D(0.1, 0.34),
        FVector2D HookR=FVector2D(0.1, 0.34),
        FVector2D JabL=FVector2D(0.1, 0.34),
        FVector2D JabR=FVector2D(0.1, 0.34),
        FVector2D KickL=FVector2D(0.1, 0.34),
        FVector2D KickR=FVector2D(0.1, 0.34),
        FVector2D OverL=FVector2D(0.1, 0.34),
        FVector2D OverR=FVector2D(0.1, 0.34),
        FVector2D Pike=FVector2D(0.1, 0.34),
        FVector2D SlashL=FVector2D(0.1, 0.34),
        FVector2D SlashLD=FVector2D(0.1, 0.34),
        FVector2D SlashLU=FVector2D(0.1, 0.34),
        FVector2D SlashR=FVector2D(0.1, 0.34),
        FVector2D SlashRD=FVector2D(0.1, 0.34),
        FVector2D SlashRU=FVector2D(0.1, 0.34));

    /** Override one attack family's lab profile. None applies to all families.
     * Accepted lab profiles are already installed; this node is optional.
     * Effective inertia = Inertia * the bone group's weight. Easing 0 is linear,
     * 1 is quintic smoothstep. Hands follow their parents and return without local inertia.
     * Inertia Hold delays momentum decay (fraction), independently of Alpha Hold on
     * Set Attack FK Return. Spine Angle Time adds seconds per 90 degrees of initial
     * spine_01 departure from idle relative to pelvis; independent of base return time.
     * World Inertia keeps rotational momentum axes independent of parent inertia.
     * Continuous spring is intentionally not included. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Recovery", meta=(DefaultToSelf="Agent", DisplayName="Set Attack FK Return Profile", AdvancedDisplay="BoneInertia,InertiaHold,InertiaDecay,WorldInertia,SpineAngleTime"))
    static bool SetAttackFKReturnProfile(AProphecyAgent* Agent, FName Attack=NAME_None,
        UPARAM(meta=(ClampMin="0")) float ReturnTime=.26f,
        UPARAM(meta=(ClampMin="0", ClampMax="1")) float Inertia=.51f,
        UPARAM(meta=(ClampMin="0", ClampMax="1")) float Easing=.12f,
        FProphecyFKInertiaWeights BoneInertia=FProphecyFKInertiaWeights(),
        UPARAM(meta=(ClampMin="0", ClampMax="0.8")) float InertiaHold=0.f,
        UPARAM(meta=(ClampMin="0", ClampMax="4")) float InertiaDecay=1.f,
        bool WorldInertia=false,
        UPARAM(meta=(ClampMin="0", ClampMax="4", Units="s")) float SpineAngleTime=0.f);
};
