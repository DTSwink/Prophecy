#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyRootPhysicsLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyRootPhysicsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Constant world-space velocity added to locomotion and its future window, in cm/s.
     * Separate from mover velocity: no mover acceleration, braking or damping is applied to it.
     * Add to Current accumulates this term only; otherwise replaces it. Zero clears linear magic.
     * Applies during locomotion/half attacks; paused during full attacks, NN defense or disabled inference. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootMagicVelocity(AProphecyAgent* Agent, FVector WorldLinearVelocity, bool bAddToCurrent = false);

    /** Constant world angular velocity in degrees/s, added independently to the root's yaw.
     * Only Z is used; the locomotion root stays upright. Add to Current accumulates this term
     * only; otherwise replaces it. Zero clears angular magic. No angular impulse or damping.
     * Carries the facing target along, so this rotation is not opposed by the old target. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootMagicAngVelocity(AProphecyAgent* Agent, FVector WorldAngularVelocityDegrees, bool bAddToCurrent = false);

    /** Configured world-space magic velocity in cm/s, excluding mover velocity. Zero when unset.
     * Reports the stored value even while an attack/disabled inference pauses its application. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static FVector GetRootMagicVelocity(AProphecyAgent* Agent);

    /** Configured world angular magic velocity in degrees/s; X/Y are zero, Z is yaw. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static FVector GetRootMagicAngVelocity(AProphecyAgent* Agent);

    /** Independent second world-space velocity term (cm/s), added to Root Magic Velocity.
     * Add to Current modifies only set 2. Zero clears only this set's linear velocity.
     * Shares the original term's root-window integration and attack/defense pause rules. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Set Root Magic Velocity 2"))
    static bool SetRootMagicVelocity2(AProphecyAgent* Agent, FVector WorldLinearVelocity, bool bAddToCurrent = false);

    /** Independent second angular term (world degrees/s, Z yaw only), added to set 1.
     * Add to Current modifies only set 2. Zero clears only this set's angular velocity. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Set Root Magic Ang Velocity 2"))
    static bool SetRootMagicAngVelocity2(AProphecyAgent* Agent, FVector WorldAngularVelocityDegrees, bool bAddToCurrent = false);

    /** Stored linear velocity of set 2 only, in world cm/s. Zero when unset. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Get Root Magic Velocity 2"))
    static FVector GetRootMagicVelocity2(AProphecyAgent* Agent);

    /** Stored angular velocity of set 2 only, in world degrees/s; X/Y are zero. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Get Root Magic Ang Velocity 2"))
    static FVector GetRootMagicAngVelocity2(AProphecyAgent* Agent);

    /** Move the actual locomotion root low point (continuous window index 0) to World Location.
     * Translates the stored prediction and presentation history by the same offset, preserving
     * window shape, rotations, velocity and local NN poses. Immediate, unswept placement;
     * subsequent movement still uses normal collision/steering. Does not teleport Jolt bodies.
     * False before initialization, with inference disabled, external bridge, full attack or NN defense.
     * On demand only: no added tick or persistent override. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetLocomotionRootWindowLocation(AProphecyAgent* Agent, FVector WorldLocation);

    /** Presentation-aligned locomotion prediction, evaluated only when called.
     * Returns 9 world transforms: CURRENT at index 0, then 8 future roots;
     * times are 0, 1/NNUpdateHz, ... relative to the displayed current root.
     * Resamples the last input trajectory at the visual interpolation phase and
     * anchors it to the applied root (including capsule collision corrections).
     * Future predictions may change when input/collision changes. No NN update or tick work.
     * False before the first input, while inference is disabled, or during a full attack. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool GetContinuousLocomotionRootWindow(AProphecyAgent* Agent,
        TArray<FTransform>& WorldRoots, TArray<float>& TimeOffsetsSeconds);

    /** Adds angular impulse to the upright root mover. Only world Z (yaw) is supported;
     * X/Y are ignored. Units: kg*cm^2/s, or rad/s with Velocity Change enabled.
     * Uses the existing Add Root Impulse path with zero linear impulse. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool AddRootAngularImpulse(AProphecyAgent* Agent, FVector WorldAngularImpulseRadians,
        bool bVelocityChange = false);

    /** Apply force/torque for DeltaSeconds through the root mover's existing impulse path.
     * Force: kg*cm/s^2, torque: kg*cm^2/s^2. Acceleration Change uses cm/s^2 and rad/s^2 instead.
     * Horizontal force and yaw torque only, matching Add Root Impulse. No immediate teleport.
     * Call each frame with its Delta Seconds for sustained force; this node does not latch or tick.
     * Root smoothing/steering/collision still govern subsequent motion. Invalid input fails atomically. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root")
    static bool AddRootForceAndTorque(AProphecyAgent* Agent, FVector WorldForce,
        FVector WorldTorqueRadians, float DeltaSeconds, bool bAccelerationChange = false);

    /** Configure an automatic per-agent planar spring toward the midpoint of foot_l/foot_r.
     * Off by default. Physical feet when simulating, visible feet when kinematic.
     * Runs only below Speed Threshold and at/below Move Input Threshold (stick amplitude 0..1,
     * before speed scaling). Input above the threshold restores normal movement next policy step.
     * Frequency controls strength; damping ratio 1 is critical. Max speed is additionally capped
     * by Speed Threshold so the spring cannot disengage itself. No yaw/height change.
     * Full attacks retain their authored root; half attacks permit balancing.
     * Balancing is also off while magic linear speed (XYZ magnitude) or absolute yaw speed
     * exceeds its respective Magic threshold. Threshold units are cm/s and degrees/s.
     * Existing root-window smoothing and capsule collision still apply. Call once or retune at runtime. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root")
    static bool SetRootSelfBalancing(AProphecyAgent* Agent, bool bEnabled,
        float SpeedThresholdCmPerSecond = 60.f, float MoveInputThreshold = 0.05f,
        float SpringFrequencyHz = 2.f, float DampingRatio = 1.f,
        float MaxBalanceSpeedCmPerSecond = 30.f, float ToleranceCm = 0.f,
        float MagicVelocityThresholdCmPerSecond = 10000.f,
        float MagicAngVelocityThresholdDegreesPerSecond = 10000.f);

    /** Last policy-step state; flat feet midpoint is projected onto the root's Z plane.
     * Does not sample bones or enable capture. Active may be true at rest with zero correction. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root")
    static void GetRootSelfBalancingState(AProphecyAgent* Agent, bool& bEnabled,
        bool& bActive, FVector& FlatFeetMidpoint);
};
