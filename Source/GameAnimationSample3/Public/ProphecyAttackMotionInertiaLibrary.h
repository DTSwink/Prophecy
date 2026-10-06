#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackMotionInertiaLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackMotionInertiaLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Optional parent-local angular inertia on the final attack upper-body pose.
     * Presentation and physical targets only; its smoothed pose is not fed back to the NN.
     * Off by default. Inertia is the response time in authored seconds; zero bypasses.
     * Frames After Armed counts 60 Hz game ticks, not policy steps. The Armed
     * prediction is included when this is positive; zero ends before that prediction.
     * Core Only Throughout Attack instead filters spine/neck/head until attack end,
     * excluding clavicle and arm local joints. After Hit optionally resumes all
     * upper joints from their current motion through attack end, including in core mode.
     * At exit the FK return inherits the accepted pose; this filter stops.
     * Settings latch at the next attack;
     * disabling cancels immediately. Does not filter pelvis/legs or override learned phase gates. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent"))
    static bool SetAttackMotionInertia(AProphecyAgent* Agent,bool Enabled=false,
        UPARAM(meta=(ClampMin="0")) float Inertia=.03f,
        UPARAM(meta=(ClampMin="0")) int32 FramesAfterArmed=1,
        bool CoreOnlyThroughoutAttack=false,bool AfterHit=false);
};
