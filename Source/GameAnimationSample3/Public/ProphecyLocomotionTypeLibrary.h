#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyLocomotionTypeLibrary.generated.h"
class AProphecyAgent;
UENUM(BlueprintType)
enum class EProphecyLocomotionType : uint8 { NN, GetUp UMETA(DisplayName="Get Up"), Clanker };

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyLocomotionTypeLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Select the NN pose controller or a fully physical robot. Accepted deferred changes fire the event only on completion. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Locomotion Type"))
    static bool SetLocomotionType(AProphecyAgent* Agent,EProphecyLocomotionType Type,FString& Error);
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Get Locomotion Type"))
    static EProphecyLocomotionType GetLocomotionType(AProphecyAgent* Agent);
    /** Player camera: blend from the NN root to robot COM projected onto floor Z=0, then back. Seconds mean 60 unpaused ticks. May be set in Locomotion Type Changed. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Locomotion Camera Blend"))
    static bool SetLocomotionCameraBlend(AProphecyAgent* Agent,float BlendIn=.4f,float BlendOut=1.f);
    /** Independent return controls. May be set inside Locomotion Type Changed; seconds mean 60 unpaused ticks. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Locomotion Switch Blend"))
    static bool SetLocomotionSwitchBlend(AProphecyAgent* Agent,float LowerDuration=1.5f,float UpperDuration=.39f,
        float UpperInertia=.18f,float UpperEasing=0.f,float NNAlphaHold=.17f,float NNTakeoverCoefficient=1.f);
    /** Change only the upper-body return, including from the switch event. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Locomotion Switch Upper Blend"))
    static bool SetLocomotionSwitchUpperBlend(AProphecyAgent* Agent,float Duration=.39f,float Inertia=.18f,
        float Easing=0.f,float NNAlphaHold=.17f,float NNTakeoverCoefficient=1.f);
    /** Hold the captured lower pose, then blend to NN; seconds mean 60 unpaused ticks. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Locomotion Switch Lower Blend"))
    static bool SetLocomotionSwitchLowerBlend(AProphecyAgent* Agent,float Duration=1.5f,float HoldDuration=0.f);
};
