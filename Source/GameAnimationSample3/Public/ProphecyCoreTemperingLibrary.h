#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyCoreTemperingLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyCoreTemperingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Rotation follow per NN step for spine_01..spine_05, neck_01/02, head and both clavicles.
     * Slerps each joint in its parent's local frame: 0 holds the accepted local bend,
     * 1 follows prediction. FK keeps offsets and attachments intact; pelvis is unchanged.
     * Locomotion only; all specials bypass. Attack end restores this configured value.
     * Disabled/1 bypass processing. Set cancels an ongoing return. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Locomotion FK Core Tempering"))
    static bool SetLocomotionFKCoreTempering(AProphecyAgent* Agent,bool Enabled=true,float Rotation=1.f);

    /** Hold the current core follow value, then smoothstep it back to 1.
     * 1 second means 60 unpaused game ticks, independent of FPS and time dilatation.
     * Zero blend snaps after the hold. Finished returns retain no tick/pose work. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Blend Locomotion FK Core Tempering to Normal"))
    static bool BlendLocomotionFKCoreTemperingToNormal(AProphecyAgent* Agent,
        float HoldDurationSeconds=0.f,float BlendDurationSeconds=1.f);
};
