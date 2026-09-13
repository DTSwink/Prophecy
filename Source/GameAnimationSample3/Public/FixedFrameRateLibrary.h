#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FixedFrameRateLibrary.generated.h"

UCLASS()
class GAMEANIMATIONSAMPLE3_API UFixedFrameRateLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	// Changes the simulation clock itself. For slow-motion debugging, keep this
	// at 60 and use t.MaxFPS (30 = half speed, 15 = quarter speed, 0 = restore).
	UFUNCTION(BlueprintCallable, Category = "Debug|Framerate")
	static void SetFixedFrameRateRuntime(float FPS);

	UFUNCTION(BlueprintCallable, Category = "Debug|Framerate")
	static void DisableFixedFrameRateRuntime();
};
