#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackRecoveryLibrary.h"
#include "ProphecyHandRecoveryLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyHandRecoveryLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** spine_05-local hand follow per NN step: 0 carries the previous pose with the upper torso,
     * 1 follows normal prediction. Repairs the arm chain, preserving hand rotation.
     * Translation XY/Z and rotation are measured in spine_05's local axes.
     * Locomotion only: attack/parry/dodge bypass it. Shared recovery profile for all specials.
     * Disabled/all-one bypass pose copies and IK. Set cancels ongoing tempering returns. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent"))
    static bool SetLocomotionHandTempering(AProphecyAgent* Agent,bool Enabled=true,
        float LeftHandTranslationXY=1.f,float LeftHandTranslationZ=1.f,float LeftHandRotation=1.f,
        float RightHandTranslationXY=1.f,float RightHandTranslationZ=1.f,float RightHandRotation=1.f);

    /** Independent hand holds and smoothstep returns of XY/Z/rotation to1.
     * 1 second means60 unpaused game ticks, unaffected by agent time dilatation.
     * Zero duration snaps after the optional hold. Completed returns retire completely. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent"))
    static bool BlendLocomotionHandTemperingToNormal(AProphecyAgent* Agent,
        float LeftHandHoldDurationSeconds=0.f,float LeftHandBlendDurationSeconds=1.f,
        float RightHandHoldDurationSeconds=0.f,float RightHandBlendDurationSeconds=1.f);

    /** Hand-only recovery after any special. Walk/Run conditions the SAME upper checkpoint
     * on that lower checkpoint's prediction, blending only the arm outputs back to normal.
     * Does not switch the actual legs, torso or root. Independent holds and blend durations.
     * Extra source inference only during active recovery. Zero blend honors the hold,
     * then returns immediately. Normal or both durations zero disables that hand.
     * No kick variant. Configure before a special or in Special Ended.
     * 1 second means60 unpaused game ticks. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|NN Attack",meta=(DefaultToSelf="Agent"))
    static bool SetAttackToLocomotionHandBlend(AProphecyAgent* Agent,
        EProphecyRecoverySource LeftHandSource=EProphecyRecoverySource::Run,
        float LeftHandHoldDurationSeconds=0.f,float LeftHandBlendDurationSeconds=1.f,
        EProphecyRecoverySource RightHandSource=EProphecyRecoverySource::Run,
        float RightHandHoldDurationSeconds=0.f,float RightHandBlendDurationSeconds=1.f);
};
