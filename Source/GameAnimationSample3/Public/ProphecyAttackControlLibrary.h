#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackControlLibrary.generated.h"

class AProphecyAgent;
class UStaticMeshComponent;

UENUM(BlueprintType)
enum class EProphecyAttackInitializationMode : uint8
{
    Dynamic,
    Static
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackControlLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Clamp a wanted world target to this attack's horizontal GT reach + extra reach.
     * GT reach is measured from the first-frame flat feet midpoint to its saved hit target.
     * The live cylinder is centered on the agent's current flat feet midpoint (the normal
     * self-balancing target, even when balancing is disabled). Height is unchanged.
     * Attack is an explicit family name, so this can run before starting an attack.
     * Difference = Effective Target - Wanted Target. No attack/NN state is changed.
     * Distance To Limit is the remaining horizontal reach in cm for the wanted target:
     * radius minus planar distance, clamped to zero on/outside the boundary.
     * Unknown attack names have zero horizontal reach. Missing feet use the live root;
     * invalid agents/targets pass through unchanged with zero Difference/Distance To Limit. No tick work. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|NN Attack", meta=(DefaultToSelf="Agent"))
    static void GetValidAttackTarget(AProphecyAgent* Agent, FName Attack, FVector Target,
        FVector& EffectiveTarget, FVector& Difference, FVector& WantedTarget, double& DistanceToLimit);

    /** Set this agent's extra horizontal reach in cm independently for each attack.
     * Each defaults to 50; zero uses that attack's measured GT reach. All values must
     * be finite and nonnegative; invalid input leaves every setting unchanged.
     * All 50 removes overrides. Does not alter a running attack's target. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack", meta=(DefaultToSelf="Agent", ClampMin="0"))
    static bool SetAttackTargetExtraReach(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") float ExtraReachCm=50.f, UPARAM(DisplayName="slashR") float SlashR=50.f,
        UPARAM(DisplayName="slashLD") float SlashLD=50.f, UPARAM(DisplayName="slashRD") float SlashRD=50.f,
        UPARAM(DisplayName="slashLU") float SlashLU=50.f, UPARAM(DisplayName="slashRU") float SlashRU=50.f,
        UPARAM(DisplayName="pike") float Pike=50.f,
        UPARAM(DisplayName="jabL") float JabL=50.f, UPARAM(DisplayName="jabR") float JabR=50.f,
        UPARAM(DisplayName="hookL") float HookL=50.f, UPARAM(DisplayName="hookR") float HookR=50.f,
        UPARAM(DisplayName="overL") float OverL=50.f, UPARAM(DisplayName="overR") float OverR=50.f,
        UPARAM(DisplayName="headbutt") float Headbutt=50.f,
        UPARAM(DisplayName="kickL") float KickL=50.f, UPARAM(DisplayName="kickR") float KickR=50.f);

    /** Fade the full-attack camera's added horizontal pelvis offset back to zero after the attack.
     * Only affects this agent while player-possessed. Default 1 means 60 unpaused game ticks,
     * independent of FPS/time dilation; 0 removes the offset immediately. Changes also retime
     * an active fade from its current value. No camera tick is retained after completion. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Camera", meta=(DefaultToSelf="Agent"))
    static bool SetAttackCameraOffsetFadeDuration(AProphecyAgent* Agent,float DurationSeconds=1.f);

    /** Read-only metadata for an ongoing NN attack, including before Armed.
     * BoneNames contains the attacking PHAT bodies, not every body that can collide.
     * Slash/pike returns only SwordCollider, with an empty BoneNames array.
     * A missing/dropped sword returns null. False/inactive clears every output.
     * This does not change collision, Armed gating, or hit detection. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|NN Attack", meta=(DisplayName="Get NN Attack Colliders"))
    static bool GetNNAttackColliders(AProphecyAgent* Agent, FName& Attack,
        TArray<FName>& BoneNames, UStaticMeshComponent*& SwordCollider);

    /** Per-agent choice for the NEXT attack start, including chained attacks. Dynamic
     * preserves existing history. Static copies the current lower AND upper recurrent
     * frames into their previous slots once; later inference advances normally.
     * Half attacks retain their GT ghost placement, using its current seed twice.
     * Does not freeze the agent, reset a running attack, or change the root mover. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack")
    static bool SetAttackInitializationMode(AProphecyAgent* Agent,
        EProphecyAttackInitializationMode Mode = EProphecyAttackInitializationMode::Dynamic);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|NN Attack")
    static EProphecyAttackInitializationMode GetAttackInitializationMode(AProphecyAgent* Agent);

    /** Choose this agent's root placement when an attack finishes/cancels into
     * locomotion. True (default): flat feet midpoint, matching root balancing.
     * False: directly below the current pelvis. Preserves root height and shifts
     * the whole window/reset magic cube through the existing handoff. Does not
     * require the balancing spring to be enabled. No per-tick work. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack")
    static bool SetAttackReturnToRootBalancing(AProphecyAgent* Agent, bool UseRootBalancingTarget = true);
};
