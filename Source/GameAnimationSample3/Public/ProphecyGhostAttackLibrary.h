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
    /** Unpaused world ticks since BeginPlay/reset or the last full lower release.
     * Counts immediately from BeginPlay; zero throughout a full attack. Full entry,
     * including half-to-full, resets it; full-to-half starts counting. Pure half
     * attacks do not reset it. Reads do not advance it. Initial-agent reset restarts it. */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent"))
    static int64 GetTicksSinceLastAttack(AProphecyAgent* Agent);

    /** Prevent the Armed phase latch while the checkpoint continues wind-up.
     * Hit keeps its existing rules and is not independently blocked.
     * Set true before Armed, then false to allow the checkpoint to arm naturally.
     * Does not rewind an already Armed/Hit attack. Persists across attacks until changed.
     * Applies to full and half attacks. Default false; no timer or extra inference. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent"))
    static bool SetAttackArmedBlocked(AProphecyAgent* Agent,bool Blocked=true);

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
