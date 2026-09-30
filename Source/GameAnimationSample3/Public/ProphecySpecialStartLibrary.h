#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySpecialStartLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySpecialStartLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Off by default. New attacks (full/half), parries and dodges start from the
     * actual simulated pose. Prior history is estimated from current physical velocities.
     * Set before triggering; ongoing specials and kinematic agents are unchanged.
     * Samples only at entry, with no added tick or inference work. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Specials", meta=(DefaultToSelf="Agent"))
    static void SetSpecialStartFromPhysical(AProphecyAgent* Agent, bool Enabled = false);
};
