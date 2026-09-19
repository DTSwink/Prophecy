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
    /** Optional minimum collision substeps per rendered frame for the SHARED Jolt world.
     * Off by default. 2 gives at least 120 Hz at 60 FPS; 4 gives at least 240 Hz.
     * 1 preserves the usual project stepping. Higher existing project counts are preserved.
     * May be toggled during attacks; takes effect on subsequent physics preparation.
     * Includes matching animation-drive timing. Does not enable CCD or affect the NN rate.
     * Applies to every Jolt body in this world, not only the calling agent. Range 1..16. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt", meta=(WorldContext="WorldContextObject"))
    static bool SetJoltCollisionSubsteps(const UObject* WorldContextObject, bool bEnabled, int32 Substeps = 2);

    /** Reports the optional override. Disabled returns Substeps=1. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Jolt", meta=(WorldContext="WorldContextObject"))
    static void GetJoltCollisionSubsteps(const UObject* WorldContextObject, bool& bEnabled, int32& Substeps);

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
