#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyLowerTemperingLibrary.generated.h"

class AProphecyAgent;

/** Per-agent diagnostic switch; does not change the normal NN pose decoder or physics constraints. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyLegChainDebugLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Enabled by default. Disable the extra leg-chain reconstruction after tempering,
     * pelvis inertia and Dodge lower-body modifications. Those modifiers still move
     * pelvis/feet, but do not repair thigh orientation or project ankle reach/floor
     * through the chain solver. Normal NN decoding, pinning, clamps and physical
     * joint constraints remain active. Call again with Enabled=true to restore. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Debug", meta=(DisplayName="Set Leg Chain Reconstruction"))
    static bool SetLegChainReconstruction(AProphecyAgent* Agent, bool Enabled = true);

    /** Inner hip-to-ankle distance = abs(thigh length - calf length) * Multiplier.
     * Default 1.2; 1 restores the mathematical minimum. Does not change foot
     * rotation or enable an outer reach clamp. Shared by both legs. No work when
     * tempering/reconstruction is inactive. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion", meta=(DisplayName="Set Locomotion Minimum Leg Reach"))
    static bool SetLocomotionMinimumLegReach(AProphecyAgent* Agent, float Multiplier = 1.2f);
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyLowerTemperingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-policy-step root-local pose follow: 1 = normal prediction, 0 = previous
     * pose carried with the root. Feet share XY translation, Z translation and
     * rotation controls; pelvis has its own three controls. Foot rotation tempers toe and knee-frame
     * motion. Applied before foot pinning; pins still anchor in world space.
     * Legs are resolved before recurrent state and upper NN input. Reach/floor
     * constraints take priority over an impossible pinned endpoint. Disabled or
     * all-one values bypass tempering, history copies and its leg solve entirely.
     * Affects locomotion only; all active full/half attacks, parries and dodges
     * bypass tempering. Values must be finite and in [0,1]. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion", meta=(DisplayName="Set Locomotion Lower Body Tempering"))
    static bool SetLocomotionLowerBodyTempering(AProphecyAgent* Agent, bool Enabled = true,
        UPARAM(DisplayName="Feet Translation XY") float FeetTranslation = 1.f,
        float FeetTranslationZ = 1.f, float FeetRotation = 1.f,
        UPARAM(DisplayName="Pelvis Translation XY") float PelvisTranslation = 1.f,
        float PelvisTranslationZ = 1.f, float PelvisRotation = 1.f);

    /** Configure separate tempering automatically selected on return from kickL/kickR.
     * Independent root-local XY/Z/rotation for kicking foot, non-kicking foot and pelvis.
     * Foot roles automatically swap for kickR. Applied only in locomotion.
     * Regular attacks select the regular Set profile. Until this node is called,
     * existing behavior is unchanged. Blend To Normal uses the selected values.
     * Disabled/all-one means no tempering after kicks, without disabling the regular profile. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Locomotion", meta=(DisplayName="Set Kick Locomotion Lower Body Tempering"))
    static bool SetKickLocomotionLowerBodyTempering(AProphecyAgent* Agent, bool Enabled = true,
        UPARAM(DisplayName="Kicking Foot Translation XY") float FeetTranslation = 1.f,
        UPARAM(DisplayName="Kicking Foot Translation Z") float FeetTranslationZ = 1.f,
        UPARAM(DisplayName="Kicking Foot Rotation") float FeetRotation = 1.f,
        float NonKickingFootTranslationXY = 1.f, float NonKickingFootTranslationZ = 1.f,
        float NonKickingFootRotation = 1.f,
        UPARAM(DisplayName="Pelvis Translation XY") float PelvisTranslation = 1.f,
        float PelvisTranslationZ = 1.f, float PelvisRotation = 1.f);

    /** Hold and restore feet and pelvis to 1 with separate timing for each group.
     * Each group's XY translation, Z translation and rotation return together.
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
