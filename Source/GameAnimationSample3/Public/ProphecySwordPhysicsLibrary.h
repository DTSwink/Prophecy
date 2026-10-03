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
