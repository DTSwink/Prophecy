#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltPHATSweepLibrary.generated.h"

class UPrimitiveComponent;
/** Selective contact prediction on the active attack's striking parts. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltPHATSweepLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Sweep only this agent's held sword during slashL/LU/LD/R/RU/RD,
     * including its welded shape but excluding the hand. No pike or unarmed sweeps.
     * Predicts translation AND rotation against other registered Jolt bodies; applies a
     * mass/inertia-weighted contact impulse. Does not teleport bodies, enable Jolt CCD,
     * change global substeps, or affect the NN. Existing overlaps use the normal solver.
     * Strength 0 disables work; 1 applies full predicted normal response. Experimental:
     * the subsequent joint solve can still change motion, so this is not an overlap guarantee.
     * Runs only during slashes, including wind-up; never during dodge/parry or locomotion.
     * Predictive impulses do NOT emit Hit events. Normal solved contacts still do.
     * Attacks default to Strength 1 / 64 iterations unless
     * overridden here; Enabled false disables automatic sweeps for this agent.
     * Call once or on state changes. Settings can be supplied before the rig exists. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt", meta=(DisplayName="Set Jolt PHAT Sweeps"))
    static bool SetJoltPHATSweeps(AActor* Agent, bool Enabled = false, float Strength = 1.0f, int32 MaxIterations = 64);

    UFUNCTION(BlueprintPure, Category="Prophecy|Jolt", meta=(DisplayName="Get Jolt PHAT Sweeps"))
    static void GetJoltPHATSweeps(AActor* Agent, bool& Enabled, float& Strength, int32& MaxIterations);

    /** Internal event-only bridge from the game module; never called from Tick. */
    UFUNCTION(meta=(BlueprintInternalUseOnly="true"))
    static void NotifyAttackState(AActor* Agent, bool Attacking);

    // Game module supplies slash sword selection on entry/family change; no per-tick name polling.
    static void SetAttackParts(AActor* Agent, const TArray<FName>& Bones, UPrimitiveComponent* Sword);

    /** Legacy internal bridge, retained for compatibility; defense never enables sweeps. */
    UFUNCTION(meta=(BlueprintInternalUseOnly="true"))
    static void NotifyDefenseState(AActor* Agent, bool Defending);
};
