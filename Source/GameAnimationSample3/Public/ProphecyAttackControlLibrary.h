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
