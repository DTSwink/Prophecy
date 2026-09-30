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
     * without restarting. Blend In Time fades from live upper locomotion to the
     * manual track. Joint alphas: 0=locomotion, 1=manual; parent-local rotations.
     * Hitting/Non Hitting arm pins map automatically: left/right punches, right
     * for all sword attacks, both hitting for headbutt/kicks. Both arms share speed
     * and blend time. Speed limits the manual track; locomotion also contributes
     * motion while blending. Partial alphas keep upper locomotion inference alive;
     * all-one influence skips it after blend-in. Requires locomotion; no attack checkpoint is evaluated.
     * Disabled keeps no state/clock/pose work. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Armed Pose",meta=(DefaultToSelf="Agent",DisplayName="Set Upper Body Armed Pose"))
    static bool SetUpperBodyArmedPose(AProphecyAgent* Agent,bool Enabled,FName Attack,
        FString& OutError,float MaxJointSpeedDegreesPerSecond=180.f,float BlendInTime=0.f,
        float Spine01Alpha=1.f,float Spine02Alpha=1.f,float Spine03Alpha=1.f,float Spine04Alpha=1.f,float Spine05Alpha=1.f,
        float Neck01Alpha=1.f,float Neck02Alpha=1.f,float HeadAlpha=1.f,
        float HittingClavicleAlpha=1.f,float HittingUpperarmAlpha=1.f,float HittingLowerarmAlpha=1.f,float HittingHandAlpha=1.f,
        float NonHittingClavicleAlpha=1.f,float NonHittingUpperarmAlpha=1.f,float NonHittingLowerarmAlpha=1.f,float NonHittingHandAlpha=1.f);

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
