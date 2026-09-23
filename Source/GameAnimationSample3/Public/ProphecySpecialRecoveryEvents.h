#pragma once
#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "ProphecyNNDefenseLibrary.h"
#include "ProphecySpecialRecoveryEvents.generated.h"

UINTERFACE(BlueprintType,Blueprintable)
class GAMEANIMATIONSAMPLE3_API UProphecySpecialRecoveryEvents : public UInterface
{
    GENERATED_BODY()
};
/** Optional shared recovery event. No component, polling or per-frame binding. */
class GAMEANIMATIONSAMPLE3_API IProphecySpecialRecoveryEvents
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintImplementableEvent,Category="Prophecy|Agent|Recovery",meta=(DisplayName="Special Ended"))
    void OnNNSpecialEnded(EProphecyAgentState Special,FName Attack,bool HalfAttack,bool ReturningToLocomotion);
};
