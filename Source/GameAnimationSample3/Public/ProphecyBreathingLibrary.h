#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyBreathingLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyBreathingMode : uint8
{
    None UMETA(DisplayName="No breathing"),
    UpperOnly UMETA(DisplayName="Upper body only"),
    UpperAndPelvis UMETA(DisplayName="Upper body and pelvis")
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyBreathingLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    // Breathing runs at zero movement input, including throughout D/S.
    UFUNCTION(BlueprintCallable,Category="Prophecy|Locomotion",meta=(DisplayName="Set Breathing Mode"))
    static bool SetBreathingMode(AProphecyAgent* Agent,EProphecyBreathingMode Mode=EProphecyBreathingMode::UpperAndPelvis);
    UFUNCTION(BlueprintPure,Category="Prophecy|Locomotion",meta=(DisplayName="Get Breathing Mode"))
    static EProphecyBreathingMode GetBreathingMode(AProphecyAgent* Agent);

    // Scales successive translation and rotation deltas. Zero disables that
    // region, one preserves the source amplitude; changes do not reset phase.
    UFUNCTION(BlueprintCallable,Category="Prophecy|Locomotion",meta=(DisplayName="Set Breathing Multipliers"))
    static bool SetBreathingMultipliers(AProphecyAgent* Agent,float PelvisMultiplier=1.f,float UpperBodyMultiplier=1.f);

    // Snaps to 0.3, 0.4, ... 1.0. Returns the applied multiplier (0 on invalid
    // input). Uses pre-baked samples; preserves phase and amplitude settings.
    UFUNCTION(BlueprintCallable,Category="Prophecy|Locomotion",meta=(DisplayName="Set Breathing Speed Multiplier",ReturnDisplayName="Applied Multiplier"))
    static float SetBreathingSpeedMultiplier(AProphecyAgent* Agent,float Multiplier=1.f);
};
