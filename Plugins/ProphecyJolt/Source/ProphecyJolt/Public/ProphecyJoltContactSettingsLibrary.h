#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltContactSettingsLibrary.generated.h"

/** Optional shared-world contact tuning; no ticking or per-agent settings. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltContactSettingsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Allowed contact penetration in cm for the entire Jolt world. Default 2; try 0.1.
     * Call once on BeginPlay or when changing it, even before native Jolt initialization.
     * Zero is accepted; negative/nonfinite values fail without changes.
     * This is not a hard overlap cap. Does not enable CCD or alter substeps. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt", meta=(WorldContext="WorldContextObject"))
    static bool SetJoltPenetrationSlop(const UObject* WorldContextObject, float SlopCm = 2.0f);

    /** Current shared-world contact penetration allowance in cm; default 2. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Jolt", meta=(WorldContext="WorldContextObject"))
    static float GetJoltPenetrationSlop(const UObject* WorldContextObject);
};
