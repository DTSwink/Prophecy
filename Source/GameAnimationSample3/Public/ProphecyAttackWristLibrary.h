#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyClampProfileLibrary.h"
#include "ProphecyAttackWristLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackWristLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-mode left wrist bend constraint; disabled by default in every mode.
     * Attacks always use the training limit of 55 degrees, for all checkpoints
     * including half attacks. Max Bend Degrees only affects Locomotion, Parry
     * and Dodge (or those modes when All is selected). Positions/right hand
     * unchanged. Disable removes our override, not a model's baked constraint. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent"))
    static bool SetLeftHandConstraint(AProphecyAgent* Agent,bool Enabled=false,
        EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All,float MaxBendDegrees=55.f);
};
