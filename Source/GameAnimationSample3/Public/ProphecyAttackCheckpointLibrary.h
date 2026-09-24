#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackCheckpointLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyAttackCheckpoint : uint8
{
    Current174664 UMETA(DisplayName="Current (174664)"),
    PredictivePin160664 UMETA(DisplayName="Predictive Pin x5 (160664)"),
    PredictivePin184064 UMETA(DisplayName="Predictive Pin x5 Refresh 2 (184064)")
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackCheckpointLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-agent comparison. Current is the default. Applies to the next new full/half
     * attack; an ongoing attack keeps its checkpoint and history until it ends.
     * The first alternate selection loads/validates its model once per manager.
     * Call after agent initialization, preferably in delayed BeginPlay. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent"))
    static bool SetAttackCheckpoint(AProphecyAgent* Agent,EProphecyAttackCheckpoint Checkpoint,FString& OutError);

    /** Selected is for the next new attack. Effective identifies the ongoing attack,
     * or matches Selected when idle. */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent"))
    static bool GetAttackCheckpoint(AProphecyAgent* Agent,EProphecyAttackCheckpoint& Selected,
        EProphecyAttackCheckpoint& Effective,bool& Attacking);
};
