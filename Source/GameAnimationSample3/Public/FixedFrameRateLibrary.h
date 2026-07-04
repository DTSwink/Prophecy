#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "FixedFrameRateLibrary.generated.h"

UCLASS()
class GAMEANIMATIONSAMPLE3_API UFixedFrameRateLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Debug|Framerate")
	static void SetFixedFrameRateRuntime(float FPS);

	UFUNCTION(BlueprintCallable, Category = "Debug|Framerate")
	static void DisableFixedFrameRateRuntime();
};
