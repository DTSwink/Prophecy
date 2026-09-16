#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJointDampingLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyJointDampingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Damps rotation of Child Bone relative to its PHAT parent (hand_r means the wrist).
     * Damping is a mass-normalized rate in 1/s, not 0..1. Zero restores current undamped behavior.
     * Requires a live Jolt rig; acts equally on all angular axes. No pose spring or body drag. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints", meta=(AdvancedDisplay="OutError"))
    static bool SetJoltJointAngularDamping(AProphecyAgent* Agent,FName ChildBone,float Damping,FString& OutError);

    /** Set every anatomical PHAT joint in the live Jolt rig. Zero removes the added damping.
     * Does not include the sword grip or external joints. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints", meta=(AdvancedDisplay="OutError"))
    static bool SetJoltAllJointsAngularDamping(AProphecyAgent* Agent,float Damping,FString& OutError);

    /** Automatic per-joint locomotion damping. Walk/Run use the actual checkpoint blend.
     * Drawn means an actual held sword, matching the NN equipment input; otherwise Sheathed.
     * Full and half attacks force zero. Values resume automatically on returning to locomotion.
     * All zero disables this policy. The constant damping nodes also replace this policy.
     * Requires a live Jolt rig to configure; retained across subsequent rig recreation. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints", meta=(AdvancedDisplay="OutError"))
    static bool SetJoltJointLocomotionDamping(AProphecyAgent* Agent,FName ChildBone,
        float WalkSheathed,float RunSheathed,float WalkDrawn,float RunDrawn,FString& OutError);
};
