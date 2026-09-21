#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAngularLimitBlendLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAngularLimitBlendLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Gradually restore all anatomical PHAT angular limits from their current settings.
     * Free axes start at180; locked authored axes reach0 then become Locked at completion.
     * Authored Free axes stay free when starting free. Frames, offsets and linear limits
     * are preserved. Duration1 =60 unpaused game ticks, regardless of FPS. Zero is instant.
     * Works with Jolt and Chaos. Keep the existing Jolt automatic target publisher
     * ticking while it is enabled; this blend does not change that requirement.
     * A new limit setter cancels the active restore. No recurring work after completion. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Physics",meta=(AdvancedDisplay="OutError",CPP_Default_DurationSeconds="1.0"))
    static bool BlendToAuthoredAngularLimits(AProphecyAgent* Agent,float DurationSeconds,FString& OutError);
};
