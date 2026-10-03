#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyUpperBodyInertiaLibrary.generated.h"
class AProphecyAgent;
UENUM(BlueprintType)
enum class EProphecyUpperHandInertiaSpace : uint8
{
    RootLocal UMETA(DisplayName="Root Local"),
    SpineLocal UMETA(DisplayName="Spine Local")
};
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyUpperBodyInertiaLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Preserve outgoing core angular motion and reference-local arm/hand motion after
     * any special, then fade to normal controls. Hand targets remain reachable;
     * forearms retain their fixed anatomical length. Response
     * controls spring softness; larger is more inertial.
     * Hold/blend use 60 unpaused game ticks per authored second. Configure before
     * a special ends or inside Special Ended. Core Alpha and Arms Alpha scale
     * their own regions from zero (disabled) to one (full). Arms Alpha -1 inherits
     * Core Alpha. Alpha-only changes preserve ongoing spring motion and timing;
     * zero retires only that region, which can restart at the next special end.
     * Momentum scales outgoing velocity only.
     * ArmsResponseTimeSeconds and ArmsBlendToNormalDurationSeconds apply equally
     * to both arms; -1 inherits the corresponding core value. Hold is shared.
     * Zero response or hold plus blend zero bypasses that region only. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Upper Body Inertia"))
    static bool SetAttackUpperBodyInertia(AProphecyAgent* Agent,bool Enabled=true,
        UPARAM(DisplayName="Core Response Time Seconds") float ResponseTimeSeconds=.25f,float HoldDurationSeconds=0.f,
        UPARAM(DisplayName="Core Blend To Normal Duration Seconds") float BlendToNormalDurationSeconds=.5f,float MomentumScale=1.f,
        EProphecyUpperHandInertiaSpace HandInertiaSpace=EProphecyUpperHandInertiaSpace::RootLocal,
        UPARAM(DisplayName="Core Alpha",meta=(ClampMin="0",ClampMax="1",UIMin="0",UIMax="1")) float Alpha=1.f,
        UPARAM(meta=(ClampMin="-1")) float ArmsResponseTimeSeconds=-1.f,
        UPARAM(meta=(ClampMin="-1")) float ArmsBlendToNormalDurationSeconds=-1.f,
        UPARAM(meta=(ClampMin="-1",ClampMax="1",UIMin="-1",UIMax="1")) float ArmsAlpha=-1.f);
};
