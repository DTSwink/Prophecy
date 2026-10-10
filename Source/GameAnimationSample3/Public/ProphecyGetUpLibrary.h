#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyGetUpLibrary.generated.h"
class AProphecyAgent;
class UAnimSequence;

UENUM(BlueprintType)
enum class EProphecyGetUpInterpolation : uint8 { Linear, SmoothStep, SmootherStep };

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyGetUpLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Capture the actual fallen pose, select front/back, restore magnetization and rise in simulation.
     * Multiplier affects clip playback, not entry or handoff durations. Repeated calls during a rise do nothing.
     * False means the request could not start (see log); no simulation-mode change is made. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Get Up",meta=(DefaultToSelf="Agent",DisplayName="Get Up"))
    static bool GetUp(AProphecyAgent* Agent,float PlayRateMultiplier=1.f);

    /** Configure subsequent get-ups. Null clips use AS_GetUp_Front1 / AS_GetUp_Back1 on the mannequin skeleton.
     * First blend the snapshot to frame zero, then play. Durations use 60 unpaused game ticks per second.
     * Restore magnetization from the named snapshot; if missing, blend body strengths to 1.
     * Ground offset adjusts clip height above the supporting floor. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Get Up",meta=(DefaultToSelf="Agent",DisplayName="Get Up Profile",AdvancedDisplay="FrontAnimation,BackAnimation,MagnetizationSnapshot,GroundOffsetCm"))
    static bool GetUpProfile(AProphecyAgent* Agent,float PoseBlendDurationSeconds=.35f,
        EProphecyGetUpInterpolation PoseInterpolation=EProphecyGetUpInterpolation::SmoothStep,
        EProphecyGetUpInterpolation HandoffInterpolation=EProphecyGetUpInterpolation::SmoothStep,
        float MagnetizationBlendDurationSeconds=.35f,UAnimSequence* FrontAnimation=nullptr,
        UAnimSequence* BackAnimation=nullptr,FName MagnetizationSnapshot=FName(TEXT("1")),float GroundOffsetCm=0.f);

    /** Independent get-up profile; never edits attack, Dodge or regular locomotion tuning.
     * Handoff Alpha is normalized clip time: 1=end, .5=halfway, 0=after the entry blend.
     * Follow values have the same per-prediction meaning as existing lower tempering. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Get Up",meta=(DefaultToSelf="Agent",DisplayName="Set Get Up Lowerbody Tempering"))
    static bool SetGetUpLowerbodyTempering(AProphecyAgent* Agent,bool Enabled=true,float HandoffAlpha=1.f,
        float FeetTranslationXY=1.f,float FeetTranslationZ=1.f,float FeetRotation=1.f,
        float PelvisTranslationXY=1.f,float PelvisTranslationZ=1.f,float PelvisRotation=1.f);

    /** Store automatic lower handoff timing for the next Get Up. Holds begin at lower Handoff Alpha.
     * Each group blends from the clip to locomotion while its follow values return to 1.
     * Zero duration snaps after the hold. Calling this node does not start a clock. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Get Up",meta=(DefaultToSelf="Agent",DisplayName="Blend Get Up Lowerbody Tempering"))
    static bool BlendGetUpLowerbodyTempering(AProphecyAgent* Agent,float FeetDurationSeconds=1.f,
        float FeetHoldDurationSeconds=0.f,float PelvisDurationSeconds=1.f,float PelvisHoldDurationSeconds=0.f);

    /** Same spine_05-local hand controls and parent-local core rotation as existing tempering.
     * Handoff Alpha is independent of lower body. Disabled means normal follow, not disabled handoff. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Get Up",meta=(DefaultToSelf="Agent",DisplayName="Set Get Up Upperbody Tempering"))
    static bool SetGetUpUpperbodyTempering(AProphecyAgent* Agent,bool Enabled=true,float HandoffAlpha=1.f,
        float LeftHandTranslationXY=1.f,float LeftHandTranslationZ=1.f,float LeftHandRotation=1.f,
        float RightHandTranslationXY=1.f,float RightHandTranslationZ=1.f,float RightHandRotation=1.f,
        float FKCoreRotation=1.f);

    /** Store automatic upper handoff timing for the next Get Up. All holds start at upper Handoff Alpha.
     * Each hand and the FK core have independent hold/blend durations. No timer until Get Up. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Get Up",meta=(DefaultToSelf="Agent",DisplayName="Blend Get Up Upperbody Tempering"))
    static bool BlendGetUpUpperbodyTempering(AProphecyAgent* Agent,
        float LeftHandHoldDurationSeconds=0.f,float LeftHandBlendDurationSeconds=1.f,
        float RightHandHoldDurationSeconds=0.f,float RightHandBlendDurationSeconds=1.f,
        float FKCoreHoldDurationSeconds=0.f,float FKCoreBlendDurationSeconds=1.f);
};
