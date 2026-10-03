#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyArmConeLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyArmConeLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Optional upper-arm exclusion cone. Disabled by default; selected attacks also default off.
     * Radius is the half-angle in degrees, strength is spring stiffness and damping is 1/s.
     * Explicitly enabling the cone corrects selected full/half attacks. No wrist recoil. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Physics",meta=(DefaultToSelf="Agent",DisplayName="Set Arm Repellant Cone"))
    static bool SetArmRepellantCone(AProphecyAgent* Agent,bool Enabled=false,
        float ConeRadiusDegrees=45.f,float RecoilStrength=100.f,float Damping=20.f,
        float HoldOutTime=.3f,float BlendTime=.5f);

    /** Replace the selected attacks. All start unchecked; both arms use the same selection.
     * Does not enable the master settings. Unchecking the current recovery cancels it. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Physics",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Arm Repellant Cone Enabled"))
    static bool SetAttackArmRepellantConeEnabled(AProphecyAgent* Agent,
        UPARAM(DisplayName="slashL") bool SlashL=false, UPARAM(DisplayName="slashR") bool SlashR=false,
        UPARAM(DisplayName="slashLD") bool SlashLD=false, UPARAM(DisplayName="slashRD") bool SlashRD=false,
        UPARAM(DisplayName="slashLU") bool SlashLU=false, UPARAM(DisplayName="slashRU") bool SlashRU=false,
        UPARAM(DisplayName="pike") bool Pike=false,
        UPARAM(DisplayName="jabL") bool JabL=false, UPARAM(DisplayName="jabR") bool JabR=false,
        UPARAM(DisplayName="hookL") bool HookL=false, UPARAM(DisplayName="hookR") bool HookR=false,
        UPARAM(DisplayName="overL") bool OverL=false, UPARAM(DisplayName="overR") bool OverR=false,
        UPARAM(DisplayName="headbutt") bool Headbutt=false,
        UPARAM(DisplayName="kickL") bool KickL=false, UPARAM(DisplayName="kickR") bool KickR=false);

    /** Explicit cone preview. Disabled configurations return before reading poses or drawing. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Debug",meta=(DefaultToSelf="Agent",DisplayName="Visualize Arm Repellant Cone"))
    static bool VisualizeArmRepellantCone(AProphecyAgent* Agent,float DrawLengthCm=30.f,float Duration=0.f);
};
