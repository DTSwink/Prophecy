#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyClampProfileLibrary.h"
#include "ProphecyPhysicalFootTargetLibrary.generated.h"

class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicalFootTargetLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Jolt physical feet only. Zero keeps the position target exactly at the authored calf endpoint.
     * Positive leeway permits that much displacement toward the original NN foot target.
     * Does not change rotations or the visible kinematic/NN pose. Shared left/right.
     * All writes locomotion, attack (including half attack), parry and dodge together. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physics", meta=(DefaultToSelf="Agent", ClampMin="0"))
    static bool SetPhysicalFootTargetClampLeeway(AProphecyAgent* Agent, float LeewayCm=0.f,
        EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All);
};
