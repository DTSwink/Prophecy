#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyRootVelocityLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyRootVelocityLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Set the mover's world XY velocity in cm/s; Z is ignored by the planar mover.
     * Add to Current adds instead of replacing. Leaves angular velocity and both magic
     * sets unchanged (use magic velocity for independent XYZ motion). No teleport.
     * Normal steering, damping, smoothing, balancing and limits apply from the next
     * policy step; this is not a persistent velocity override. False before initialization,
     * with inference disabled, external bridge or during a full attack.
     * Delay is seconds counted at 60 unpaused ticks/s (zero applies immediately). A delayed
     * true means queued; availability and Add to Current are evaluated when it expires.
     * Reset cancels pending requests. No tick work when no requests are pending. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootVelocity(AProphecyAgent* Agent, FVector WorldVelocity, bool bAddToCurrent=false, float Delay=0.f);

    /** Set the mover's world angular velocity in degrees/s; only Z (yaw) is used.
     * Add to Current adds instead of replacing. Updates the braking/facing target to
     * avoid springing back to the old heading; zero stops mover rotation at its current
     * heading. Leaves linear velocity and both magic sets unchanged. Existing per-step
     * yaw safety cap and normal movement rules apply. Delay and availability follow Set Root Velocity. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootAngVelocity(AProphecyAgent* Agent, FVector WorldAngularVelocityDegrees, bool bAddToCurrent=false, float Delay=0.f);

    /** Add a total world XY velocity change in equal installments over SpreadTicks unpaused
     * game ticks. Delay is seconds counted at 60 unpaused ticks/s; zero starts immediately.
     * SpreadTicks=1 matches Set Root Velocity with Add to Current and the same Delay.
     * Normal mover rules/availability apply to every installment;
     * unavailable installments are discarded. Concurrent calls add independently. Reset
     * cancels the remainder. Z is ignored. No ticking when nothing is pending. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool AddRootSpreadVelocity(AProphecyAgent* Agent, FVector WorldVelocity,
        UPARAM(meta=(ClampMin="1")) int32 SpreadTicks=1,
        UPARAM(meta=(ClampMin="0", Units="s")) float Delay=0.f);

    /** Angular equivalent of Add Root Spread Velocity, in degrees/s. Only Z (yaw) is used.
     * SpreadTicks=1 matches Set Root Ang Velocity with Add to Current and the same Delay. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool AddRootSpreadAngVelocity(AProphecyAgent* Agent, FVector WorldAngularVelocityDegrees,
        UPARAM(meta=(ClampMin="1")) int32 SpreadTicks=1,
        UPARAM(meta=(ClampMin="0", Units="s")) float Delay=0.f);
};
