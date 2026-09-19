#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltPHATSweepLibrary.generated.h"

/** Selective contact prediction, gated by attack and active defense lifecycles. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltPHATSweepLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Sweep this agent's PhysicalMesh PHAT bodies (including an attached welded sword).
     * Predicts translation AND rotation against other registered Jolt bodies; applies a
     * mass/inertia-weighted contact impulse. Does not teleport bodies, enable Jolt CCD,
     * change global substeps, or affect the NN. Existing overlaps use the normal solver.
     * Strength 0 disables work; 1 applies full predicted normal response. Experimental:
     * the subsequent joint solve can still change motion, so this is not an overlap guarantee.
     * Runs during attacks and active dodge/parry checkpoint control (not waiting for Armed).
     * These states default to Strength 1 / 64 iterations unless
     * overridden here; Enabled false disables automatic sweeps for this agent.
     * Call once or on state changes. Settings can be supplied before the rig exists. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt", meta=(DisplayName="Set Jolt PHAT Sweeps"))
    static bool SetJoltPHATSweeps(AActor* Agent, bool Enabled = false, float Strength = 1.0f, int32 MaxIterations = 64);

    UFUNCTION(BlueprintPure, Category="Prophecy|Jolt", meta=(DisplayName="Get Jolt PHAT Sweeps"))
    static void GetJoltPHATSweeps(AActor* Agent, bool& Enabled, float& Strength, int32& MaxIterations);

    /** Internal event-only bridge from the game module; never called from Tick. */
    UFUNCTION(meta=(BlueprintInternalUseOnly="true"))
    static void NotifyAttackState(AActor* Agent, bool Attacking);

    /** Active checkpoint ownership only: queued defenses must not enable sweeps. */
    UFUNCTION(meta=(BlueprintInternalUseOnly="true"))
    static void NotifyDefenseState(AActor* Agent, bool Defending);
};
