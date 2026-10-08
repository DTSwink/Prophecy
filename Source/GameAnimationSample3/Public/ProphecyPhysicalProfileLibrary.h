#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyPhysicalProfileLibrary.generated.h"

class AProphecyAgent;

/** Named, per-agent runtime snapshots. No tick or work is added by saving a snapshot. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicalProfileLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** 0 follows the actual physical parent; 1 keeps world targets. Pelvis stays global.
     * Intermediate values use one blended target and one servo. Default is 1. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static bool SetMagnetizationMode(AProphecyAgent* Agent, UPARAM(meta=(ClampMin="0",ClampMax="1")) float Mode=1.f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static float GetMagnetizationMode(AProphecyAgent* Agent);

    /** Change one physical body's configured mode. Pelvis still stays global. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static bool SetBodyMagnetizationMode(AProphecyAgent* Agent,FName BoneName,float Mode=1.f);

    /** Change physical bodies in this skeletal subtree; returns the number changed. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent", DisplayName="Set Body Magnetization Mode Below"))
    static int32 SetMagnetizationModeBelow(AProphecyAgent* Agent,FName ParentBone,float Mode=1.f,bool IncludeParent=true);

    /** Read this body's configured mode. The pelvis always uses world targets regardless. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static float GetBodyMagnetizationMode(AProphecyAgent* Agent,FName BoneName);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static bool BlendMagnetizationModeToSnapshot(AProphecyAgent* Agent,float DurationSeconds=1.f,
        FName SnapshotName=NAME_None,float HoldOutTime=0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static bool BlendBodyMagnetizationModeToSnapshot(AProphecyAgent* Agent,FName BoneName,float DurationSeconds=1.f,
        FName SnapshotName=NAME_None,float HoldOutTime=0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles", meta=(DefaultToSelf="Agent"))
    static int32 BlendMagnetizationModeBelowToSnapshot(AProphecyAgent* Agent,FName ParentBone,bool IncludeParent=true,
        float DurationSeconds=1.f,FName SnapshotName=NAME_None,float HoldOutTime=0.f);

    /** Print one line per PHAT bone, head at the top and feet at the bottom.
     * Each pair is linear/angular: magnetization scales (including global scales,
     * zero when disabled) / feedback tolerances / inbound angular damping.
     * Hands show fixed attachment; feet show locomotion Foot/Calf clamp leeway (off when disabled).
     * Unsupported tolerance/joint entries show n/a. Printed values have no units.
     * Reads the current applied profile/blend values. One screen block per agent
     * is replaced on repeated calls. No automatic tick or work when not called.
     * Returns the printed text. Duration uses normal engine debug-display seconds. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Debug", meta=(DevelopmentOnly, AdvancedDisplay="Duration,TextColor"))
    static FString PrintPhysicalBoneProfiles(AProphecyAgent* Agent, float Duration = 0.0f,
        FLinearColor TextColor = FLinearColor(1.f,1.f,1.f,1.f));

    /** Call after configuring your agent. Saves every body's magnetization enabled/scales and
     * all supported feedback tolerances and joint damping, including all walk/run and drawn/sheathed profiles.
     * Also captures magnetization mode and shared left/right clamps for locomotion, attack, parry and dodge.
     * Saves current blend values, not unfinished blend destinations. During attacks saves the
     * underlying locomotion profiles, not the temporary attack overrides. Same name overwrites.
     * Does not capture simulation membership, gravity, physics state or global drive settings. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool SavePhysicalProfileSnapshot(AProphecyAgent* Agent, FName SnapshotName = NAME_None);

    /** Restore this bone's four saved profiles using the existing smoothstep blend.
     * Hold Out Time delays interpolation without changing current values. Duration <= 0 snaps after the hold. Missing snapshot/bone returns false without changes. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool BlendBodyMagnetizationToSnapshot(AProphecyAgent* Agent, FName BoneName,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None, float HoldOutTime = 0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendBodyMagnetizationBelowToSnapshot(AProphecyAgent* Agent, FName ParentBone,
        bool bIncludeParent = true, float DurationSeconds = 1.f, FName SnapshotName = NAME_None, float HoldOutTime = 0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendAllBodyMagnetizationToSnapshot(AProphecyAgent* Agent,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None, float HoldOutTime = 0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool BlendPhysicalFeedbackToleranceToSnapshot(AProphecyAgent* Agent, FName BoneName,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None, float HoldOutTime = 0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendPhysicalFeedbackToleranceBelowToSnapshot(AProphecyAgent* Agent, FName ParentBone,
        bool bIncludeParent = true, float DurationSeconds = 1.f, FName SnapshotName = NAME_None, float HoldOutTime = 0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendAllPhysicalFeedbackTolerancesToSnapshot(AProphecyAgent* Agent,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None, float HoldOutTime = 0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool BlendJointAngularDampingToSnapshot(AProphecyAgent* Agent,FName ChildBone,
        float DurationSeconds=1.f,FName SnapshotName=NAME_None,float HoldOutTime=0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendJointAngularDampingBelowToSnapshot(AProphecyAgent* Agent,FName ParentBone,
        bool IncludeParent=true,float DurationSeconds=1.f,FName SnapshotName=NAME_None,float HoldOutTime=0.f);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendAllJointAngularDampingToSnapshot(AProphecyAgent* Agent,
        float DurationSeconds=1.f,FName SnapshotName=NAME_None,float HoldOutTime=0.f);
};
