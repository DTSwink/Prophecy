#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyArmedPoseLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyArmedPoseLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Move all16 controlled spine_01 descendant joints to an attack's GT Armed
     * parent-local rotations. The farthest joint uses Max Joint Speed; all others
     * arrive together. Degrees per60 unpaused game ticks. Preserves bone offsets
     * and locomotion pelvis/legs. Holds the result until disabled or a real special
     * or animation layer starts. Call once; repeated same-attack calls retune speed
     * without restarting. Requires locomotion; no attack checkpoint is evaluated.
     * Disabled keeps no state/clock/pose work. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Armed Pose",meta=(DefaultToSelf="Agent",DisplayName="Set Upper Body Armed Pose"))
    static bool SetUpperBodyArmedPose(AProphecyAgent* Agent,bool Enabled,FName Attack,
        FString& OutError,float MaxJointSpeedDegreesPerSecond=180.f);

    /** Release the manual upper pose and resume the normal upper checkpoint from
     * the last authored recurrent pose. Works while moving to the pose or holding
     * it. Idempotent; no recovery timer or extra inference after release. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Armed Pose",meta=(DefaultToSelf="Agent",DisplayName="Stop Upper Body Armed Pose"))
    static bool StopUpperBodyArmedPose(AProphecyAgent* Agent);

    /** Mean shortest angular difference in degrees across all16 upper joints,
     * each relative to its parent, comparing the current presented NN target to
     * the GT Armed frame. Zero means matching rotations. Does not measure physical
     * tracking error or position. Samples only when called; false on invalid input. */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Armed Pose",meta=(DefaultToSelf="Agent",DisplayName="Get Upper Body Armed Pose Distance"))
    static bool GetUpperBodyArmedPoseDistance(AProphecyAgent* Agent,FName Attack,float& AverageDegrees);
};
