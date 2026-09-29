#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackFootLocomotionLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyAttackFootLocomotionMode : uint8 { Walk,Run,CurrentBlend };

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackFootLocomotionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Full non-kick attacks only. A foot outside either limit starts locomotion-owned;
     * once inside both, it becomes attack-owned permanently for this attack.
     * Distance limits only backward horizontal projection on pelvis-to-target;
     * forward distance is unrestricted. Height
     * is ankle height above the root floor. Current Blend continues normal gait blending.
     * Freeze Blend (0..1) blends the locomotion root window toward the NN pelvis
     * projected onto root-floor height. Zero preserves normal motion; one collapses
     * all window positions under the pelvis. Can be changed during loco drag.
     * Alpha Rotation: 1 uses locomotion foot/toe orientation, 0 uses attack.
     * Each foot blends to attack after entering both limits, using its own duration
     * (60 unpaused game ticks per second). Feet starting in attack do not blend.
     * Locomotion inference and delayed foot inertia hand off when the blend finishes.
     * Knee Pole Blend Duration Seconds: positive starts a foot-local locomotion-to-attack
     * knee direction blend immediately for each dragging foot. Zero disables this
     * extra correction. Uses the final authored foot rotation; half mode pauses it.
     * Configure before attack. Disabling releases remaining feet immediately. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Feet",meta=(DefaultToSelf="Agent"))
    static bool SetAttackFootLocomotion(AProphecyAgent* Agent,bool Enabled,
        EProphecyAttackFootLocomotionMode Mode=EProphecyAttackFootLocomotionMode::CurrentBlend,
        float DistanceLimitCm=40.f,float HeightLimitCm=15.f,
        UPARAM(meta=(ClampMin="0",ClampMax="1")) float FreezeBlend=0.f,
        UPARAM(meta=(ClampMin="0",ClampMax="1")) float AlphaRotation=1.f,
        UPARAM(meta=(ClampMin="0")) float LeftBlendDurationSeconds=0.f,
        UPARAM(meta=(ClampMin="0")) float RightBlendDurationSeconds=0.f,
        UPARAM(meta=(ClampMin="0")) float KneePoleBlendDurationSeconds=0.f);
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Attack Feet",meta=(DefaultToSelf="Agent"))
    static void GetAttackFootLocomotion(AProphecyAgent* Agent,bool& LeftLocomotion,bool& RightLocomotion);
    /** Draw explicitly per frame. Cyan = locomotion, red = attack. No debug tick/delegate. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Feet",meta=(DefaultToSelf="Agent"))
    static void DrawAttackFootLocomotion(AProphecyAgent* Agent,float Duration=0.f);
};
