#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltBodyDriveLibrary.generated.h"

/** Internal event bridge: avoids changing the live WorldSubsystem reflected class. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltBodyDriveLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Global Jolt speculative contact distance in cm. Default 2; increasing it does not guarantee blocking fast slashes.
     * Larger distances can produce a physical response before visible contact. Call once or when changing it.
     * Applies to every body in this world, including before physics initialization; survives agent resets.
     * Set 2 to restore the default. Zero is valid; negative/nonfinite inputs fail without changing anything. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt", meta=(WorldContext="WorldContextObject", DisplayName="Set Jolt Speculative Contact Distance"))
    static bool SetJoltSpeculativeContactDistance(const UObject* WorldContextObject, float DistanceCm = 2.0f);

    /** Current global Jolt speculative contact distance in cm. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Jolt", meta=(WorldContext="WorldContextObject", DisplayName="Get Jolt Speculative Contact Distance"))
    static float GetJoltSpeculativeContactDistance(const UObject* WorldContextObject);

    /** Solver-driven arm magnetisation. Three finite-effort constraints per enabled arm. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics", meta=(DefaultToSelf="Agent", DisplayName="Set Arms Anti Jiggle"))
    static bool SetArmsAntiJiggle(AActor* Agent, bool LeftArm = false, bool RightArm = false);

    /** Temporarily disables both arms, then restores their previous independent choices.
     * Seconds mean 60 unpaused world ticks, independent of FPS, time dilation and physics substeps.
     * Repeated calls restart the duration. Zero cancels the hold and restores immediately.
     * An explicit Set Arms Anti Jiggle cancels the pending restoration. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics", meta=(DefaultToSelf="Agent", DisplayName="Disable Arms Anti Jiggle For Duration"))
    static bool DisableArmsAntiJiggleForDuration(AActor* Agent, float DurationSeconds = 0.1f);

    /** Internal attack-phase gate. Does not overwrite preferences or an active timed hold. */
    UFUNCTION(meta=(BlueprintInternalUseOnly="true"))
    static void NotifyArmsAntiJiggleAttackWindow(AActor* Agent, bool Active);

    UFUNCTION()
    static bool SetDriveFollower(UObject* WorldContext, FGuid Lifetime, int32 BodySlot, int64 BodyGeneration,
        int32 ParentSlot, int64 ParentGeneration, FTransform BodyToParent, bool Enabled);
};
