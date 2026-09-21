#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyWalkPinningLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyWalkPinningLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Walk only: clear each foot's selected pin weight when its raw NN output is
     * strictly above Limit. Does not transfer the pin to the other foot. The limit
     * is in signed raw NN units, not decoded probability. Default is 2 per agent. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning")
    static bool SetWalkPinningLimit(AProphecyAgent* Agent,float Limit=2.f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Foot Pinning")
    static float GetWalkPinningLimit(AProphecyAgent* Agent);

    /** Walk only: if both raw NN pin outputs are positive and their absolute difference is
     * <= Tolerance, bypass the hard winner. Tolerance is in raw NN output units, not cm.
     * Zero tolerance disables the exception, preserving the original rule (including ties).
     * Tolerance Fallback: 0 = both unpinned; 1 = decoded soft weights; intermediate values scale them.
     * Uses the existing sigmoid decode and PinScale. Does not change Run or attack pinning. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning")
    static bool SetWalkPinningTolerance(AProphecyAgent* Agent,float Tolerance=0.f,float ToleranceFallback=0.f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Foot Pinning")
    static bool GetWalkPinningTolerance(AProphecyAgent* Agent,float& Tolerance,float& ToleranceFallback);
};
