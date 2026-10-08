#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySwordPhysicsLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySwordPhysicsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** At fresh attack entry, a gap strictly greater than this many ticks forces the
     * melee sword rule, including for slash/pike: suppress all sword collision until
     * first NN Hit (or attack end). Read before the existing last-attack counter resets.
     * Default 2. Applies to subsequent attacks; does not change the current phase.
     * This entry rule takes precedence over residual sword collision cooldown. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Sword", meta=(DefaultToSelf="Agent"))
    static bool SetSwordCollisionMeleeGapThreshold(AProphecyAgent* Agent, UPARAM(meta=(ClampMin="0")) int32 Ticks=2);

    /** After an armed slash ends, retain external sword collision through this many
     * subsequent unpaused world ticks, including a new melee attack's preparation.
     * Default 4; 0 disables and cancels the current cooldown. Positive edits apply
     * to the next qualifying end. Owner rules and explicit global disable still win.
     * Pikes and slashes that never reached Armed do not start the cooldown. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Sword", meta=(DefaultToSelf="Agent"))
    static bool SetSwordCollisionCooldown(AProphecyAgent* Agent, UPARAM(meta=(ClampMin="0")) int32 Ticks=4);

    /** Toggle all held-sword collision without changing its grip, simulation or momentum.
     * Retained for future equips. Enabled restores normal attack Armed/Hit collision timing;
     * disabled overrides it. Dropped swords regain their original collision responses. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Sword")
    static void SetSwordCollisionEnabled(AProphecyAgent* Agent, bool Enabled = true);

    /** Toggle collision between this agent and their own held sword only.
     * False keeps owner contact suppressed through attack Hit/end and future equips.
     * True restores normal attack-phase owner rules; the gripping-hand exclusion remains.
     * Other agents/world collision, body self-collision, grip and momentum are unchanged.
     * Dropping releases the owner exclusion. Applies to Jolt and Chaos sword bodies. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Sword", meta=(DefaultToSelf="Agent"))
    static void SetOwnSwordCollisionEnabled(AProphecyAgent* Agent, bool Enabled = true);

    /** Diagnostic for a held, simulated Jolt sword. Removes only the hand grip joint;
     * the sword remains held and independently magnetised to the authored hand target.
     * Does not drop it, disable collision, change velocities or turn simulation on.
     * Re-equip or switch sword simulation mode to restore the grip. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Sword")
    static bool BreakSwordGripConstraint(AProphecyAgent* Agent);
};
