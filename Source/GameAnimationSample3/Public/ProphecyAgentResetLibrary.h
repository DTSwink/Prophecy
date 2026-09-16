#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAgentResetLibrary.generated.h"

/** Explicit, session-only reset checkpoints. No ticking component or polling. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAgentResetLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Call once after NN initialization, before starting movement. Captures the agents currently
     * registered in this world. Repeated calls keep the original checkpoint. No assets are saved. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Debug|Reset", meta=(WorldContext="WorldContextObject"))
    static bool InitializeAgentReset(const UObject* WorldContextObject, int32& AgentCount, FString& OutError);

    /** Queue one reset at the next timer boundary, safe from key/hit callbacks. Restores captured
     * root/pose and clears movement input, momentum, both magic sets and interpolation history.
     * Keeps current tuning and simulation mode. Does not reset arbitrary Blueprint variables.
     * Returns whether the request was accepted; failures during reset are logged. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Debug|Reset", meta=(WorldContext="WorldContextObject"))
    static bool ResetInitialAgents(const UObject* WorldContextObject, FString& OutError);
};
