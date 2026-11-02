#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyFootIKLibrary.generated.h"
class AProphecyAgent;

USTRUCT(BlueprintType)
struct FProphecyFootIKState
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) bool Enabled=false;
    UPROPERTY(BlueprintReadOnly) bool Preparing=false;
    UPROPERTY(BlueprintReadOnly) bool Playing=false;
    UPROPERTY(BlueprintReadOnly) int32 Frame=0;
    UPROPERTY(BlueprintReadOnly) float SolveMilliseconds=0;
    UPROPERTY(BlueprintReadOnly) FVector Root=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector Velocity=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FString Phase;
    UPROPERTY(BlueprintReadOnly) FString Error;
    UPROPERTY(BlueprintReadOnly) FString DiagnosticsJson;
};

/** Opt-in exact Foot IK lab course. Settings are independent of Bodyflip and
    existing agent defaults. No level assets or Blueprint links are changed. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyFootIKLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Enable the configured course; disable cancels preparation, destroys its
        solver/NN history and returns ownership to ordinary locomotion. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK|Diagnostics",meta=(DisplayName="Play Foot IK Reference Course"))
    static bool SetFootIKEnabled(AProphecyAgent* Agent,bool Enabled,FString& Error);
    /** Same settings/units as Foot IK Lab. Empty settings use a flat walk.
        Changes prepare on a serial worker and preserve the displayed frame. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK|Diagnostics",meta=(DisplayName="Configure Foot IK Reference Course"))
    static bool ConfigureFootIK(AProphecyAgent* Agent,const FString& SettingsJson,FString& Error);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK|Diagnostics",meta=(DisplayName="Set Foot IK Reference Platforms"))
    static bool SetFootIKPlatforms(AProphecyAgent* Agent,const TArray<FTransform>& WorldTransforms,const TArray<FVector>& FullSizesCm,FString& Error);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK|Diagnostics",meta=(DisplayName="Pause Foot IK Reference Course"))
    static bool PauseFootIK(AProphecyAgent* Agent,bool Paused);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK|Diagnostics",meta=(DisplayName="Seek Foot IK Reference Course"))
    static bool SeekFootIK(AProphecyAgent* Agent,int32 Frame,FString& Error);
    UFUNCTION(BlueprintPure,Category="Prophecy|Foot IK|Diagnostics",meta=(DisplayName="Get Foot IK Reference State"))
    static bool GetFootIKState(AProphecyAgent* Agent,FProphecyFootIKState& State);
};
