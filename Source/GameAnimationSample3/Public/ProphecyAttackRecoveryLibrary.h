#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackRecoveryLibrary.generated.h"

class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackRecoveryLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** After an attack returns to locomotion, start with the run checkpoint and
     * hold run for HoldDurationSeconds (default 0), then blend to walk over
     * DurationSeconds (default 1). Overrides checkpoint selection
     * during recovery, without changing movement input or root speed. Normal rules
     * resume afterward. Zero disables recovery and preserves normal selection with
     * no recovery work or extra inference. Positive values apply to the next handoff. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack", meta=(DisplayName="Set Attack To Locomotion Blend", ClampMin="0.0", Units="s"))
    static bool SetAttackToLocomotionBlend(AProphecyAgent* Agent, float DurationSeconds = 1.f,
        float HoldDurationSeconds = 0.f);
};
