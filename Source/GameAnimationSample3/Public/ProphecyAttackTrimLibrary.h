#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackTrimLibrary.generated.h"

class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackTrimLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Shorten each named attack's normal ending by this many 60 Hz frames (1 = 1/60 second).
     * Zero preserves its original duration. Odd trims retire on the intervening unpaused game tick.
     * No persistent tick, timer or extra inference; the half-frame callback exists only until that handoff.
     * Trims the authored post-Hit tail, never before the learned Hit. Applies to full and half attacks.
     * Updates an ongoing attack without resetting its pose, target, Armed or Hit. Negative values are rejected. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Attack", meta=(DisplayName="Set Trim Attack",DefaultToSelf="Agent",ClampMin="0"))
    static bool SetTrimAttack(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") int32 SlashL=0, UPARAM(DisplayName="slashR") int32 SlashR=0,
        UPARAM(DisplayName="slashLD") int32 SlashLD=0, UPARAM(DisplayName="slashRD") int32 SlashRD=0,
        UPARAM(DisplayName="slashLU") int32 SlashLU=0, UPARAM(DisplayName="slashRU") int32 SlashRU=0,
        UPARAM(DisplayName="pike") int32 Pike=0,
        UPARAM(DisplayName="jabL") int32 JabL=0, UPARAM(DisplayName="jabR") int32 JabR=0,
        UPARAM(DisplayName="hookL") int32 HookL=0, UPARAM(DisplayName="hookR") int32 HookR=0,
        UPARAM(DisplayName="overL") int32 OverL=0, UPARAM(DisplayName="overR") int32 OverR=0,
        UPARAM(DisplayName="headbutt") int32 Headbutt=0,
        UPARAM(DisplayName="kickL") int32 KickL=0, UPARAM(DisplayName="kickR") int32 KickR=0);
};
