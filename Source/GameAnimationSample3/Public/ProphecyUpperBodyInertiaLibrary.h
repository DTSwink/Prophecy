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
     * a special ends or inside Special Ended. Alpha scales the whole effect from
     * zero (disabled) to one (full). Alpha-only changes preserve active spring
     * motion and timing; zero cancels it. Momentum scales outgoing velocity only.
     * Zero response or both times zero also bypass. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Upper Body Inertia"))
    static bool SetAttackUpperBodyInertia(AProphecyAgent* Agent,bool Enabled=true,
        float ResponseTimeSeconds=.25f,float HoldDurationSeconds=0.f,
        float BlendToNormalDurationSeconds=.5f,float MomentumScale=1.f,
        EProphecyUpperHandInertiaSpace HandInertiaSpace=EProphecyUpperHandInertiaSpace::RootLocal,
        UPARAM(meta=(ClampMin="0",ClampMax="1",UIMin="0",UIMax="1")) float Alpha=1.f);
};
