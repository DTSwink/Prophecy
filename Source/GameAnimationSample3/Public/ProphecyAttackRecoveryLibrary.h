#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackRecoveryLibrary.generated.h"

class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyRecoverySource : uint8 { Normal, Walk, Run };

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackRecoveryLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Independent pelvis/left-leg/right-leg recovery after an attack. Each part
     * holds its selected checkpoint, then blends to NORMAL locomotion selection
     * (including ordinary walk/run blends). Does not change root motion.
     * Duration zero or Source Normal disables that part. All disabled means no
     * recovery clock, correction or extra inference. 1 second = 60 unpaused ticks.
     * Positive settings apply at the next attack end, or the current handoff when
     * called from On Attack Ended before its first locomotion prediction.
     * KickL/KickR use the separate kick profile once it has been configured. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack", meta=(DisplayName="Set Attack To Locomotion Blend", ClampMin="0.0", Units="s"))
    static bool SetAttackToLocomotionBlend(AProphecyAgent* Agent,
        EProphecyRecoverySource PelvisSource = EProphecyRecoverySource::Run,
        UPARAM(DisplayName="Pelvis Hold Duration Seconds") float HoldDurationSeconds = 0.f,
        UPARAM(DisplayName="Pelvis Blend Duration Seconds") float DurationSeconds = 1.f,
        EProphecyRecoverySource LeftLegSource = EProphecyRecoverySource::Run,
        float LeftLegHoldDurationSeconds = 0.f,
        UPARAM(DisplayName="Left Leg Blend Duration Seconds") float LeftLegDurationSeconds = 1.f,
        EProphecyRecoverySource RightLegSource = EProphecyRecoverySource::Run,
        float RightLegHoldDurationSeconds = 0.f,
        UPARAM(DisplayName="Right Leg Blend Duration Seconds") float RightLegDurationSeconds = 1.f);

    /** Automatically selected after kickL/kickR. Same independent regions and tick
     * timing as the regular profile. Until configured, kicks use the regular profile. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Attack", meta=(DisplayName="Set Kick To Locomotion Blend", ClampMin="0.0", Units="s"))
    static bool SetKickToLocomotionBlend(AProphecyAgent* Agent,
        EProphecyRecoverySource PelvisSource = EProphecyRecoverySource::Run,
        UPARAM(DisplayName="Pelvis Hold Duration Seconds") float HoldDurationSeconds = 0.f,
        UPARAM(DisplayName="Pelvis Blend Duration Seconds") float DurationSeconds = 1.f,
        UPARAM(DisplayName="Kicking Leg Source") EProphecyRecoverySource LeftLegSource = EProphecyRecoverySource::Run,
        UPARAM(DisplayName="Kicking Leg Hold Duration Seconds") float LeftLegHoldDurationSeconds = 0.f,
        UPARAM(DisplayName="Kicking Leg Blend Duration Seconds") float LeftLegDurationSeconds = 1.f,
        UPARAM(DisplayName="Non Kicking Leg Source") EProphecyRecoverySource RightLegSource = EProphecyRecoverySource::Run,
        UPARAM(DisplayName="Non Kicking Leg Hold Duration Seconds") float RightLegHoldDurationSeconds = 0.f,
        UPARAM(DisplayName="Non Kicking Leg Blend Duration Seconds") float RightLegDurationSeconds = 1.f);
};
