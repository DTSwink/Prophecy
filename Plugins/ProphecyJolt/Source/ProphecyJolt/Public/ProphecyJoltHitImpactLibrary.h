#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltHitImpactLibrary.generated.h"

UCLASS()
class PROPHECYJOLT_API UProphecyJoltHitImpactLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Call directly inside a Jolt Hit event, before any Delay. Hit Receiver is the
     * receiving actor (Self) or receiving component. The current hit is read automatically.
     * Impact Speed is incoming relative closing speed along the contact normal,
     * in cm/s, measured before solving, including both bodies' angular motion.
     * Relative Velocity is receiver minus other at the sampled contact points.
     * Multiple points/substeps report the fastest closing sample, not their sum.
     * Both recipients get the same nonnegative speed. Returns false/zero outside
     * the matching event or without a native pre-solve sample (including Chaos).
     * This is speed, not impulse/energy; sustained contacts can produce more events. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Physics|Hit", meta=(DefaultToSelf="HitReceiver", DisplayName="Get Hit Impact Speed", ReturnDisplayName="Valid", AdvancedDisplay="RelativeVelocity"))
    static bool GetHitImpactSpeed(const UObject* HitReceiver,
        double& ImpactSpeed, FVector& RelativeVelocity);
};
