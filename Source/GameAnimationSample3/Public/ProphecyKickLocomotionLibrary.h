#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyKickLocomotionLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyKickLocomotionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Configure before the kick; defaults preserve full kicks without loco drag.
     * Non Kicking Foot Loco Drag permits existing Set Attack Loco Drag settings on the supporting foot only.
     * Kicks always stay full-body; Half Attack requests are ignored.
     * Configuration is per agent and restored by Reset Initial Agents. No work while disabled. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack Feet", meta=(DefaultToSelf="Agent",DisplayName="Set Kick Locomotion"))
    static bool SetKickLocomotion(AProphecyAgent* Agent, bool NonKickingFootLocoDrag=false);
};
