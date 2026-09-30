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
    /** NN upper-arm exclusion, mirrored at the NN shoulders and aimed horizontally inward.
     * Radius is the cone half-angle in degrees. Strength is spring stiffness (1/s^2), damping is 1/s.
     * Corrects the NN target; physical meshes follow it through their ordinary drives. Recovery does not rewrite the locomotion checkpoint.
     * Full strength throughout selected full/half attacks. Upper release starts Hold, then Blend
     * fades to zero; one authored second is 60 unpaused game ticks. Lower release does not start the timer.
     * New specials cancel it; zero Hold/Blend means cone during attack only. Right wrist twist starts only
     * at upper release. Smoothly follows the live NN hand/blade direction restricted to an idle cone in root space.
     * Root-local signed yaw and elevation springs: yaw sign comes from the flattened blade direction,
     * elevation takes the short return. Inside the cone, NN motion and axial roll continue through hold.
     * Twist Limit Degrees is the idle direction allowance. Strength is stiffness (1/s^2).
     * Damping has a critical-damping minimum; larger values slow response. Hold/Blend controls influence.
     * Roll Recoil Strength independently controls roll around the blade axis; -1 uses Twist Recoil Strength,
     * 0 follows NN roll directly. Roll shares Twist Damping and the existing hold/blend.
     * All wrist coefficients zero bypass wrist work. Left wrist remains excluded.
     * Wrist recoil leaves positions and forearm rotation unchanged. Blend releases angle and roll smoothly to the continuing NN pose.
     * Initially disabled. Zero radius/strength bypasses the cone; wrist recoil is independent.
     * Configure before attacking or in Upper Special Ended. Works without simulated bodies. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Physics",meta=(DefaultToSelf="Agent",DisplayName="Set Arm Repellant Cone"))
    static bool SetArmRepellantCone(AProphecyAgent* Agent,bool Enabled=false,
        float ConeRadiusDegrees=45.f,float RecoilStrength=100.f,float Damping=20.f,
        float HoldOutTime=.3f,float BlendTime=.5f,
        bool EnableWristTwistRecoil=false,float TwistLimitDegrees=90.f,
        float TwistRecoilStrength=100.f,float TwistDamping=20.f,float RollRecoilStrength=-1.f);

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

    /** Draw on demand; call on Tick for a moving preview. Gray=inactive, green=active/clear,
     * red=NN arm inside forbidden cone. Uses the presented NN pose, not physics.
     * Enabled wrist recoil also draws its idle direction cone after first recovery: cyan=idle reference,
     * yellow=limits, green/red=current direction inside/outside. Reference follows the NN root.
     * Draw length affects visualization only. No persistent tick. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Debug",meta=(DefaultToSelf="Agent",DisplayName="Visualize Arm Repellant Cone"))
    static bool VisualizeArmRepellantCone(AProphecyAgent* Agent,float DrawLengthCm=30.f,float Duration=0.f);
};
