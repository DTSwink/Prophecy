#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyRootPelvisBoundsLibrary.generated.h"
class AProphecyAgent;
class UPrimitiveComponent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyRootPelvisBoundsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Keep the displayed locomotion root inside a horizontal circle around the physical pelvis.
     * Off until enabled. Radius is centimetres; zero places the root directly below the pelvis.
     * Outside the circle, translate the root and its entire window/history by the minimum offset.
     * Preserves height, yaw, window shape and velocities; does not teleport character bodies.
     * Recenters the root without moving world-space NN body targets; stored poses are rebased.
     * Optional Magic Cube is registered weakly and teleported by the same correction, preserving velocity.
     * Automatic each presentation frame, only for enabled agents with a simulated pelvis.
     * Paused during full attacks, NN defense, external bridge, or disabled NN inference.
     * Call once or retune at runtime; no per-agent tick/component is created. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootPelvisBounds(AProphecyAgent* Agent, bool bEnabled = true, float RadiusCm = 20.f, UPrimitiveComponent* MagicCube = nullptr);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static void GetRootPelvisBounds(AProphecyAgent* Agent, bool& bEnabled, float& RadiusCm);
};
