#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyPelvisInertiaLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyPelvisInertiaLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-agent pelvis inertia. Follow values 0..1: 1 original motion, 0 retain world velocity.
     * Horizontal = world XY; Vertical = world Z; Yaw = world Z angular velocity;
     * Pitch Roll = world XY angular velocity, shared. Off by default; all-one bypasses.
     * Simulated Body selects velocity-drive inertia in Sim (contacts/forces/joints still act).
     * Otherwise filters the kinematic target, including in Kinematic and Half Sim.
     * Target mode resolves fixed-length legs into lower state before upper inference.
     * Upper body uses the corrected pelvis. Does not move the root window. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Pelvis")
    static bool SetPelvisInertia(AProphecyAgent* Agent, bool bEnabled,
        float HorizontalFollow = 1.f, float VerticalFollow = 1.f,
        float YawFollow = 1.f, float PitchRollFollow = 1.f, bool bSimulatedBody = false);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Pelvis")
    static void GetPelvisInertia(AProphecyAgent* Agent, bool& bEnabled,
        float& HorizontalFollow, float& VerticalFollow,
        float& YawFollow, float& PitchRollFollow, bool& bSimulatedBody);
};
