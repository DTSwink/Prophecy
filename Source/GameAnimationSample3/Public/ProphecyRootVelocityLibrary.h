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
     * with inference disabled, external bridge or during a full attack. No added tick work. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootVelocity(AProphecyAgent* Agent, FVector WorldVelocity, bool bAddToCurrent=false);

    /** Set the mover's world angular velocity in degrees/s; only Z (yaw) is used.
     * Add to Current adds instead of replacing. Updates the braking/facing target to
     * avoid springing back to the old heading; zero stops mover rotation at its current
     * heading. Leaves linear velocity and both magic sets unchanged. Existing per-step
     * yaw safety cap and normal movement rules apply. Same availability as Set Root Velocity. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootAngVelocity(AProphecyAgent* Agent, FVector WorldAngularVelocityDegrees, bool bAddToCurrent=false);
};
