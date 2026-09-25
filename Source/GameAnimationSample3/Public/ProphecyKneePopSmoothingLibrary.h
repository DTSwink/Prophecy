#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyKneePopSmoothingLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyKneePopSmoothingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Optional soft approach to full knee extension, shared by rendered and physical
     * locomotion targets. During attacks it applies only while attack-start pelvis
     * inertia is active, AFTER that correction. Ordinary attacks/parry/dodge bypass it.
     * Soft Zone is how far before maximum reach the
     * correction begins. Moves the ankle directly toward the hip by the shortest
     * correction, preserving foot rotation, pelvis and both segment lengths.
     * This can lift/move a pinned foot. No time delay or change to raw NN recurrence.
     * Off until called; disabling/zero removes all smoothing work and stored settings.
     * Call after NN pose-source initialization. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetKneePopSmoothing(AProphecyAgent* Agent,bool Enabled=true,float SoftZoneCm=4.f);
};
