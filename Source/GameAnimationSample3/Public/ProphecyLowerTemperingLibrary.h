#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyLowerTemperingLibrary.generated.h"

class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyLowerTemperingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-policy-step root-local pose follow: 1 = normal prediction, 0 = previous
     * pose carried with the root. Feet share their own translation/rotation values;
     * pelvis has separate values. Foot rotation also tempers toe and knee-frame
     * motion. Applied before foot pinning; pins still anchor in world space.
     * Legs are resolved before recurrent state and upper NN input. Reach/floor
     * constraints take priority over an impossible pinned endpoint. Disabled or
     * all-one values bypass tempering, history copies and its leg solve entirely.
     * Affects locomotion only; all active full/half attacks, parries and dodges
     * bypass tempering. Values must be finite and in [0,1]. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion", meta=(DisplayName="Set Locomotion Lower Body Tempering"))
    static bool SetLocomotionLowerBodyTempering(AProphecyAgent* Agent, bool Enabled = true,
        float FeetTranslation = 1.f, float FeetRotation = 1.f,
        float PelvisTranslation = 1.f, float PelvisRotation = 1.f);

    /** Hold and restore feet and pelvis to 1 with separate timing for each pair.
     * Completion removes tempering and its timeline entirely. A new Set cancels
     * this return; another Blend starts from the current values. Each authored second
     * means 60 unpaused game ticks, independent of FPS/time dilation. Zero duration snaps after the optional hold. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion")
    static bool BlendLocomotionLowerBodyTemperingToNormal(AProphecyAgent* Agent,
        UPARAM(DisplayName="Feet Duration Seconds") float DurationSeconds = 1.f,
        UPARAM(DisplayName="Feet Hold Duration Seconds") float HoldDurationSeconds = 0.f,
        float PelvisDurationSeconds = 1.f, float PelvisHoldDurationSeconds = 0.f);

    /** Return only feet translation/rotation tempering to 1, with independent hold
     * and blend times. Leaves the pelvis values and its return schedule untouched.
     * 1 second means 60 unpaused game ticks; 0 duration snaps after the hold. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion", meta=(BlueprintInternalUseOnly="true"))
    static bool BlendLocomotionFeetTemperingToNormal(AProphecyAgent* Agent,
        float DurationSeconds = 1.f, float HoldDurationSeconds = 0.f);

    /** Return only pelvis translation/rotation tempering to 1, with independent hold
     * and blend times. Leaves the feet values and their return schedule untouched.
     * 1 second means 60 unpaused game ticks; 0 duration snaps after the hold. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion", meta=(BlueprintInternalUseOnly="true"))
    static bool BlendLocomotionPelvisTemperingToNormal(AProphecyAgent* Agent,
        float DurationSeconds = 1.f, float HoldDurationSeconds = 0.f);
};
