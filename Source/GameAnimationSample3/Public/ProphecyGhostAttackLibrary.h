#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyGhostAttackLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyGhostAttackLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Minimum horizontal pelvis-to-target distance for the half-attack upper NN,
     * in cm. Preserves world height; zero disables the clamp. Default 30 cm. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetHalfAttackMinimumReach(AProphecyAgent* Agent,float DistanceCm=30.f);
    /** Unpaused world ticks since BeginPlay/reset or the last full lower release.
     * Counts immediately from BeginPlay; zero throughout a full attack. Full entry,
     * including half-to-full, resets it; full-to-half starts counting. Pure half
     * attacks do not reset it. Reads do not advance it. Initial-agent reset restarts
     * at the last manually set value (zero if never set). */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent"))
    static int64 GetTicksSinceLastAttack(AProphecyAgent* Agent);

    /** Set elapsed attack ticks now and the starting value for initial-agent resets.
     * Call once at startup; counting continues from Ticks on subsequent unpaused ticks.
     * The latest explicit value is remembered even if reset was initialized earlier.
     * Real full attacks still hold zero and start from zero on lower release.
     * Rejects negative values, invalid agents and calls during a full attack.
     * Does not start/stop attacks or change their NN inputs or phase clocks. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent"))
    static bool SetTicksSinceLastAttack(AProphecyAgent* Agent,UPARAM(meta=(ClampMin="0")) int64 Ticks=1000);

    /** Counter the real NN pelvis versus ghost pelvis rotation at spine_01 during
     * half attacks. Keeps the spine attachment and lower body, and preserves the
     * ghost upper body's world orientation. Distribute Along Spine01 To Spine05
     * shares the counter-rotation equally across those five joints instead.
     * Compensate Position also steers the ghost's target direction from the real
     * displaced torso, preserving attack phase and bone lengths (no reach stretch).
     * Default off; call once to set per-agent
     * state. Disabled performs no compensation math, sampling, timers or inference. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent",DisplayName="Enable Spine01 Compensation Half Attack"))
    static bool EnableSpine01CompensationHalfAttack(AProphecyAgent* Agent,bool Enabled=true,
        bool DistributeAlongSpine01ToSpine05=false,bool CompensatePosition=false);

    /** Draw the raw full attack ghost, its PHAT shapes (cyan), sword (yellow), and
     * ghost-space target (red). Works during half and full attacks. Call each Tick;
     * Duration 0 draws one frame. World Offset moves all drawing together for comparison.
     * Shows latest NN policy pose, before graft/clamps/roll corrections, not interpolated.
     * No spawned objects or tick registration. Disabled/inactive/Shipping does no drawing.
     * Uses authored PHAT geometry; physical-only collider trims are not ghost geometry. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Debug",meta=(DefaultToSelf="Agent",AdvancedDisplay="Duration,Thickness"))
    static bool VisualizeGhostAttack(AProphecyAgent* Agent,bool Enabled=true,
        FVector WorldOffset=FVector(150,0,0),float Duration=0.0f,float Thickness=1.0f);
};
