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
    /** Preserve checkpoint forearm compression/extension during full and half attacks.
     * At upper-body release, capture each arm's length independently and return it
     * to reference length over ReturnTime (60 game ticks per second). Physical
     * wrists capture their own lengths and follow the same duration. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent"))
    static bool SetAttackForearmStretchReturn(AProphecyAgent* Agent,bool Enabled=true,
        UPARAM(meta=(ClampMin="0")) float ReturnTime=.3f);

    /** NN only. Free Position bypasses fixed wrist attachment for both hands.
     * Free Rotation bypasses Set Left Hand Constraint in every mode, including attacks.
     * False restores the existing settings. Does not modify physical joints,
     * inertia/posing controls, or constraints baked into a checkpoint. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent",DisplayName="Set NN Wrist Freedom"))
    static bool SetNNWristFreedom(AProphecyAgent* Agent,bool FreePosition=true,bool FreeRotation=false);

    /** Left wrist angular leeway around the forearm direction: 0 locks bend,
     * 55 allows a 55-degree cone, 180 allows every orientation. Inside the cone
     * the NN rotation is unchanged; axial twist is not locked. Applies to the
     * selected mode, including full/half attacks. All includes locomotion,
     * attacks, parry and dodge. Disabled by default until configured.
     * Positions/right hand unchanged; model-baked behavior is separate. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent"))
    static bool SetLeftHandConstraint(AProphecyAgent* Agent,bool Enabled=false,
        EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All,
        UPARAM(DisplayName="Angle Leeway Degrees",meta=(ClampMin="0",ClampMax="180")) float MaxBendDegrees=55.f);

    /** Checked attacks use the configured Attack angle; unchecked attacks are free.
     * Applies to full/half attacks and in-place family changes. All checked by default.
     * Does not change locomotion, parry/dodge, the configured angle or global switches. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent",DisplayName="Set Left Hand Constraint Attacks"))
    static bool SetLeftHandConstraintAttacks(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") bool SlashL=true, UPARAM(DisplayName="slashR") bool SlashR=true,
        UPARAM(DisplayName="slashLD") bool SlashLD=true, UPARAM(DisplayName="slashRD") bool SlashRD=true,
        UPARAM(DisplayName="slashLU") bool SlashLU=true, UPARAM(DisplayName="slashRU") bool SlashRU=true,
        UPARAM(DisplayName="pike") bool Pike=true,
        UPARAM(DisplayName="jabL") bool JabL=true, UPARAM(DisplayName="jabR") bool JabR=true,
        UPARAM(DisplayName="hookL") bool HookL=true, UPARAM(DisplayName="hookR") bool HookR=true,
        UPARAM(DisplayName="overL") bool OverL=true, UPARAM(DisplayName="overR") bool OverR=true,
        UPARAM(DisplayName="headbutt") bool Headbutt=true,
        UPARAM(DisplayName="kickL") bool KickL=true, UPARAM(DisplayName="kickR") bool KickR=true);

    /** False bypasses this left-hand angular constraint in ALL modes immediately.
     * True restores configured angles and attack choices. Settings may be updated
     * while disabled without re-enabling it. Independent of Free Rotation in
     * Set NN Wrist Freedom (either bypass wins). No physical joint changes. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Animation",meta=(DefaultToSelf="Agent",DisplayName="Set Left Hand Constraint Global Enabled"))
    static bool SetLeftHandConstraintGlobalEnabled(AProphecyAgent* Agent,bool Enabled=true);
};
