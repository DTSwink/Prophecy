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
    /** Print one line per PHAT bone, head at the top and feet at the bottom.
     * Each pair is linear/angular: magnetization scales (including global scales,
     * zero when disabled) / feedback tolerances / inbound angular damping.
     * Hand/foot rows also show locomotion Hand/Forearm or Foot/Calf clamp leeway (off when disabled).
     * Unsupported tolerance/joint entries show n/a. Printed values have no units.
     * Reads the current applied profile/blend values. One screen block per agent
     * is replaced on repeated calls. No automatic tick or work when not called.
     * Returns the printed text. Duration uses normal engine debug-display seconds. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Debug", meta=(DevelopmentOnly, AdvancedDisplay="Duration,TextColor"))
    static FString PrintPhysicalBoneProfiles(AProphecyAgent* Agent, float Duration = 0.0f,
        FLinearColor TextColor = FLinearColor(1.f,1.f,1.f,1.f));

    /** Call after configuring your agent. Saves every body's magnetization enabled/scales and
     * all supported feedback tolerances and joint damping, including all walk/run and drawn/sheathed profiles.
     * Also captures shared left/right clamps for locomotion, attack, parry and dodge.
     * Saves current blend values, not unfinished blend destinations. During attacks saves the
     * underlying locomotion profiles, not the temporary attack overrides. Same name overwrites.
     * Does not capture simulation membership, gravity, physics state or global drive settings. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool SavePhysicalProfileSnapshot(AProphecyAgent* Agent, FName SnapshotName = NAME_None);

    /** Restore this bone's four saved profiles using the existing smoothstep blend.
     * Duration <= 0 restores immediately. Missing snapshot/bone returns false without changes. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool BlendBodyMagnetizationToSnapshot(AProphecyAgent* Agent, FName BoneName,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendBodyMagnetizationBelowToSnapshot(AProphecyAgent* Agent, FName ParentBone,
        bool bIncludeParent = true, float DurationSeconds = 1.f, FName SnapshotName = NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendAllBodyMagnetizationToSnapshot(AProphecyAgent* Agent,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool BlendPhysicalFeedbackToleranceToSnapshot(AProphecyAgent* Agent, FName BoneName,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendPhysicalFeedbackToleranceBelowToSnapshot(AProphecyAgent* Agent, FName ParentBone,
        bool bIncludeParent = true, float DurationSeconds = 1.f, FName SnapshotName = NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendAllPhysicalFeedbackTolerancesToSnapshot(AProphecyAgent* Agent,
        float DurationSeconds = 1.f, FName SnapshotName = NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static bool BlendJointAngularDampingToSnapshot(AProphecyAgent* Agent,FName ChildBone,
        float DurationSeconds=1.f,FName SnapshotName=NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendJointAngularDampingBelowToSnapshot(AProphecyAgent* Agent,FName ParentBone,
        bool IncludeParent=true,float DurationSeconds=1.f,FName SnapshotName=NAME_None);

    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physical Profiles")
    static int32 BlendAllJointAngularDampingToSnapshot(AProphecyAgent* Agent,
        float DurationSeconds=1.f,FName SnapshotName=NAME_None);
};
