#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySlashReturnLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySlashReturnLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-attack gate for the entire neutral return, including the additional arm.
     * Checked permits the existing configured return; unchecked blocks both hands.
     * Defaults preserve all existing behavior. Does not enable the master return
     * or change speed/hold/blend/both-arm choices. Configure before an attack or
     * inside Upper Special Ended. Unchecking an active return cancels it immediately. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Arm Return Enabled"))
    static bool SetAttackArmReturnEnabled(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") bool SlashL=true, UPARAM(DisplayName="slashR") bool SlashR=true,
        UPARAM(DisplayName="slashLD") bool SlashLD=true, UPARAM(DisplayName="slashRD") bool SlashRD=true,
        UPARAM(DisplayName="slashLU") bool SlashLU=true, UPARAM(DisplayName="slashRU") bool SlashRU=true,
        UPARAM(DisplayName="pike") bool Pike=true,
        UPARAM(DisplayName="jabL") bool JabL=true, UPARAM(DisplayName="jabR") bool JabR=true,
        UPARAM(DisplayName="hookL") bool HookL=true, UPARAM(DisplayName="hookR") bool HookR=true,
        UPARAM(DisplayName="overL") bool OverL=true, UPARAM(DisplayName="overR") bool OverR=true,
        UPARAM(DisplayName="headbutt") bool Headbutt=true,
        UPARAM(DisplayName="kickL") bool KickL=true, UPARAM(DisplayName="kickR") bool KickR=true);

    /** After slashL/R/LD/RD/LU/RU or pike, guide the right arm toward authored idle around
     * the front of the torso. Also guides the attacking arm after jabL/R, hookL/R and overL/R:
     * left for jabL/hookL/overL, right for jabR/hookR/overR, including half attacks.
     * Kicks/headbutts are excluded unless explicitly selected by the both-arm node; defense is excluded.
     * Right Hold/Blend set the right arm's times. Left times of -1 inherit the
     * corresponding right time; zero is an explicit zero duration.
     * Each arm retires independently. Left/Right Alpha: 0 = incoming NN pose,
     * 1 = full neutral return, intermediate values blend local joint rotations
     * while preserving arm lengths. Alpha multiplies that arm's timed influence.
     * Return Speed is cm per authored second at an initial hand-to-idle distance
     * of100cm. Each return captures Speed * InitialDistanceCm /100 once from the
     * outgoing pose; approaching or moving the target does not rescale it.
     * One authored second is60 unpaused game ticks, independent of FPS.
     * Configure before attacking or inside Special Ended. Repeating settings or
     * changing only alphas preserves elapsed time. Disabled/no effective arms
     * removes the feature; a new special cancels the active return. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Arm Return To Neutral",Keywords="Slash Pike Jab Hook Over Idle"))
    static bool SetSlashRightArmReturnToNeutral(AProphecyAgent* Agent,bool Enabled=true,
        UPARAM(DisplayName="Right Hold Duration Seconds") float HoldDurationSeconds=.3f,
        UPARAM(DisplayName="Right Blend To NN Duration Seconds") float BlendToNNDurationSeconds=.5f,float ReturnSpeed=100.f,
        float LeftHoldDurationSeconds=-1.f,float LeftBlendToNNDurationSeconds=-1.f,
        float LeftAlpha=1.f,float RightAlpha=1.f);

    /** Replace the per-attack selection for returning both arms to their own neutral poses.
     * Requires Set Both Arms Return To Neutral Enabled and the existing arm-return settings.
     * All checkboxes default off. Configure before the attack or in Special Ended.
     * Unselected attacks keep their usual behavior. Selected kicks/headbutt can return both arms too.
     * Unchecking the active attack cancels its additional-arm return immediately. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Both Arms Return To Neutral"))
    static bool SetAttackBothArmsReturnToNeutral(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") bool SlashL=false, UPARAM(DisplayName="slashR") bool SlashR=false,
        UPARAM(DisplayName="slashLD") bool SlashLD=false, UPARAM(DisplayName="slashRD") bool SlashRD=false,
        UPARAM(DisplayName="slashLU") bool SlashLU=false, UPARAM(DisplayName="slashRU") bool SlashRU=false,
        UPARAM(DisplayName="pike") bool Pike=false,
        UPARAM(DisplayName="jabL") bool JabL=false, UPARAM(DisplayName="jabR") bool JabR=false,
        UPARAM(DisplayName="hookL") bool HookL=false, UPARAM(DisplayName="hookR") bool HookR=false,
        UPARAM(DisplayName="overL") bool OverL=false, UPARAM(DisplayName="overR") bool OverR=false,
        UPARAM(DisplayName="headbutt") bool Headbutt=false,
        UPARAM(DisplayName="kickL") bool KickL=false, UPARAM(DisplayName="kickR") bool KickR=false);

    /** Master switch for the additional-arm extension; initially OFF per agent.
     * Preserves per-attack choices and the original arm's return. Each arm uses its own
     * hold/blend/alpha settings, idle rotation and initial-distance speed.
     * Enable before the attack or in Special Ended. Disable cancels the extra arm immediately. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Both Arms Return To Neutral Enabled"))
    static bool SetBothArmsReturnToNeutralEnabled(AProphecyAgent* Agent,bool Enabled=true);

    /** Rotation only: 0 follows anatomical pelvis rotation, 1 follows current root rotation.
     * Intermediate values use quaternion interpolation. Separate values for attacks using
     * the spine-local or pelvis-local position mode. Applies to both returning arms and idle.
     * Configure before return or in Special Ended; changes during motion apply next return.
     * Until this node is called, spine mode retains its original torso rotation.
     * Does not enable return itself. Reset snapshots include these settings. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Arm Return Rotation Blend",Keywords="Pelvis Root Spine Reference",ClampMin="0",ClampMax="1"))
    static bool SetAttackArmReturnRotationBlend(AProphecyAgent* Agent,
        float SpineLocalRotationBlend=0.f,float PelvisLocalRotationBlend=1.f);

    /** Select the return reference per attack: checked = pelvis position with current root rotation, unchecked = original upper-torso local.
     * Applies to both returning arms, including the optional additional arm. All default false.
     * Replaces all choices. Configure before the return or in Special Ended; an already moving
     * return keeps its reference to avoid a discontinuity. Idle destination follows the same reference.
     * Does not enable arm return itself. Body/sword clearance still uses the actual torso. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Arm Return Pelvis Local",Keywords="Spine Reference Space Idle"))
    static bool SetAttackArmReturnPelvisLocal(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") bool SlashL=false, UPARAM(DisplayName="slashR") bool SlashR=false,
        UPARAM(DisplayName="slashLD") bool SlashLD=false, UPARAM(DisplayName="slashRD") bool SlashRD=false,
        UPARAM(DisplayName="slashLU") bool SlashLU=false, UPARAM(DisplayName="slashRU") bool SlashRU=false,
        UPARAM(DisplayName="pike") bool Pike=false,
        UPARAM(DisplayName="jabL") bool JabL=false, UPARAM(DisplayName="jabR") bool JabR=false,
        UPARAM(DisplayName="hookL") bool HookL=false, UPARAM(DisplayName="hookR") bool HookR=false,
        UPARAM(DisplayName="overL") bool OverL=false, UPARAM(DisplayName="overR") bool OverR=false,
        UPARAM(DisplayName="headbutt") bool Headbutt=false,
        UPARAM(DisplayName="kickL") bool KickL=false, UPARAM(DisplayName="kickR") bool KickR=false);
};
