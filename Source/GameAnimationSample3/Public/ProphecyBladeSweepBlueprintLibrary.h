#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyBladeSweepBlueprintLibrary.generated.h"

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyBladeSweepBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintPure, Category = "Prophecy|Blade Sweep", meta = (DisplayName = "Build Blade Depth Sweep Samples", Keywords = "sword blade depth sweep niagara interval"))
	static TArray<float> BuildBladeDepthSweepSamples(float PreviousDepth, float CurrentDepth, float Interval);
};
