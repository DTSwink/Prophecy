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
    /** Diagnostic for a held, simulated Jolt sword. Removes only the hand grip joint;
     * the sword remains held and independently magnetised to the authored hand target.
     * Does not drop it, disable collision, change velocities or turn simulation on.
     * Re-equip or switch sword simulation mode to restore the grip. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Sword")
    static bool BreakSwordGripConstraint(AProphecyAgent* Agent);
};
