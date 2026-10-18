#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyVDBLibrary.generated.h"

UENUM(BlueprintType)
enum class EProphecyVDBEffect : uint8
{
    Shockwave,
    ShockwaveExplosion UMETA(DisplayName="Shockwave Explosion")
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyVDBLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Spawn one VDB at Location/Rotation with uniform Scale. Framerate is source frames per
     * authored second (60 unpaused game ticks). Density starts at 1, then linearly approaches
     * Target Density after Density Fade Start over Density Fade Duration, in the same seconds.
     * Plays once. Holds the last frame if the fade outlasts the clip; destroys the spawned actor
     * after both finish. Zero fade duration changes density instantly at the start time.
     * Changes only density, not temperature/flame tuning. Invalid inputs or unavailable assets
     * return None without spawning. The two selected assets are included in packaged builds. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|VFX", meta=(WorldContext="WorldContextObject", DisplayName="Spawn VDB Effect", ReturnDisplayName="Spawned VDB", AdvancedDisplay="Rotation"))
    static AActor* SpawnVDBEffect(const UObject* WorldContextObject, EProphecyVDBEffect Effect, FVector Location,
        float Scale=1.f, float Framerate=30.f, float DensityFadeStart=3.f, float TargetDensity=0.f,
        float DensityFadeDuration=1.f, FRotator Rotation=FRotator::ZeroRotator);
};
