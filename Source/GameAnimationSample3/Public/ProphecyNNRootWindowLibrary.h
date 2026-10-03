#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyNNRootWindowLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyNNRootWindowLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-NN-step smoothing of future roots only. 1=new prediction, 0=retain previous value.
     * Distance is from root0; Direction and Orientation are relative to root0's rotation.
     * Root0 stays the anchor while constructing the window; movement then advances to filtered root1.
     * Distance Acceleration is used when a sample's distance grows; Distance Deceleration when it shrinks.
     * Distance Deceleration -1 inherits Distance Acceleration, preserving the original shared smoothing.
     * All-zero from idle stays idle. All resolved factors at 1 restore ordinary movement. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Locomotion")
    static bool SetLocomotionRootWindowSmoothing(AProphecyAgent* Agent,
        UPARAM(DisplayName="Distance Acceleration") float Distance = 1.f, float Direction = 1.f, float Orientation = 1.f,
        float DistanceDeceleration = -1.f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|NN Locomotion")
    static void GetLocomotionRootWindowSmoothing(AProphecyAgent* Agent,
        UPARAM(DisplayName="Distance Acceleration") float& Distance, float& Direction, float& Orientation,
        float& DistanceDeceleration);
};
