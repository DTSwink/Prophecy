#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyUpperRootHorizonLibrary.generated.h"

class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyUpperRootHorizonLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Upper locomotion NN only. 1 = original future orientations; 0.5 = first half of
     * the orientation window stretched over all eight samples; 0 = present orientation.
     * Positions, current velocity, lower NN input and attack-policy inputs are unchanged.
     * Runtime, per agent; values outside 0..1 are rejected. Default 1 bypasses resampling. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Upper Body")
    static bool SetUpperRootRotationHorizon(AProphecyAgent* Agent, float Horizon = 1.0f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Upper Body")
    static bool GetUpperRootRotationHorizon(AProphecyAgent* Agent, float& Horizon);
};
