#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyPhysicalContextTypes.h"
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

    /** Set the four locomotion damping values on inbound PHAT joints below Parent Bone.
     * Include Parent also selects that bone's inbound joint. Non-physical bones are skipped.
     * Uses the same checkpoint blend, equipment selection, attack suppression and snapshots
     * as the single-joint node. Returns the number of joints changed. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints", meta=(AdvancedDisplay="OutError"))
    static int32 SetJoltJointLocomotionDampingBelow(AProphecyAgent* Agent,FName ParentBone,bool IncludeParent,
        float WalkSheathed,float RunSheathed,float WalkDrawn,float RunDrawn,FString& OutError);

    /** Smoothstep blend of inbound-joint damping. Duration1 =60 game ticks.
     * Both/Both edits every locomotion profile; attacks use zero. Requires Jolt. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints")
    static bool BlendJoltJointAngularDamping(AProphecyAgent* Agent,FName ChildBone,float Damping,
        float DurationSeconds=1.f,EProphecyLocomotionSelection Locomotion=EProphecyLocomotionSelection::Both,
        EProphecyEquipmentSelection Equipment=EProphecyEquipmentSelection::Both);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints")
    static int32 BlendJoltJointAngularDampingBelow(AProphecyAgent* Agent,FName ParentBone,bool IncludeParent,
        float Damping,float DurationSeconds=1.f,EProphecyLocomotionSelection Locomotion=EProphecyLocomotionSelection::Both,
        EProphecyEquipmentSelection Equipment=EProphecyEquipmentSelection::Both);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Joints")
    static int32 BlendJoltAllJointsAngularDamping(AProphecyAgent* Agent,float Damping,float DurationSeconds=1.f,
        EProphecyLocomotionSelection Locomotion=EProphecyLocomotionSelection::Both,
        EProphecyEquipmentSelection Equipment=EProphecyEquipmentSelection::Both);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Jolt|Joints")
    static bool GetJoltJointAngularDamping(AProphecyAgent* Agent,FName ChildBone,float& Damping);
};
