#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltBlueprintLibrary.generated.h"

/** Explicit setup for the shared local Jolt world used by characters and scene collision. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyJoltBlueprintLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Call once during gameplay setup, before enabling Jolt scene, character or body components.
     * Existing worlds are never reset or resized by this call.
     */
    UFUNCTION(BlueprintCallable, Category = "Prophecy|Jolt",
        meta = (WorldContext = "WorldContextObject", AdvancedDisplay = "BodyCapacity,WorkerThreads"))
    static bool InitializeJoltWorld(const UObject* WorldContextObject, FString& OutError,
        int32 BodyCapacity = 16384, int32 WorkerThreads = 7);

    UFUNCTION(BlueprintPure, Category = "Prophecy|Jolt", meta = (WorldContext = "WorldContextObject"))
    static bool IsJoltWorldReady(const UObject* WorldContextObject);
};
