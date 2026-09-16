#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyRootSpeedLimitsLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyRootSpeedLimitsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Cap combined locomotion root motion, including impulses, balancing and both magic sets.
     * Linear cap is world XYZ speed (cm/s); angular cap is absolute yaw speed (degrees/s).
     * Zero stops that motion. High defaults preserve ordinary movement. Disabled bypasses limiting.
     * Applies to the NN's future window and the actual root together; full attacks/defense retain
     * their authored motion. Explicit placement and pelvis-bounds teleports are not velocity.
     * Configured magic values are preserved; only their applied contribution is reduced. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static bool SetRootVelocityLimits(AProphecyAgent* Agent, float MaxLinearSpeedCmPerSecond = 1000000.f,
        float MaxAngularSpeedDegreesPerSecond = 1000000.f, bool bEnabled = true);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent"))
    static void GetRootVelocityLimits(AProphecyAgent* Agent, bool& bEnabled,
        float& MaxLinearSpeedCmPerSecond, float& MaxAngularSpeedDegreesPerSecond);
};
