#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyFootIKLiveLibrary.generated.h"
class AProphecyAgent;

USTRUCT(BlueprintType)
struct FProphecyFootIKLiveState
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) bool Enabled=false;
    UPROPERTY(BlueprintReadOnly) bool Preparing=false;
    UPROPERTY(BlueprintReadOnly) bool Ready=false;
    UPROPERTY(BlueprintReadOnly) int32 AppliedFrame=-1;
    UPROPERTY(BlueprintReadOnly) int32 PreparedThroughFrame=-1;
    UPROPERTY(BlueprintReadOnly) float SolveMilliseconds=0;
    UPROPERTY(BlueprintReadOnly) FString Error;
    UPROPERTY(BlueprintReadOnly) FString DiagnosticsJson;
};

/** Terrain correction of the active game NN/controller, independent of the
    diagnostic reference course. Disabling releases all live solver state. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyFootIKLiveLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK",meta=(DisplayName="Set Foot IK Enabled"))
    static bool SetFootIKEnabled(AProphecyAgent* Agent,bool Enabled,FString& Error);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Foot IK",meta=(DisplayName="Configure Live Foot IK"))
    static bool ConfigureLiveFootIK(AProphecyAgent* Agent,const FString& SettingsJson,FString& Error);
    UFUNCTION(BlueprintPure,Category="Prophecy|Foot IK",meta=(DisplayName="Get Live Foot IK State"))
    static bool GetLiveFootIKState(AProphecyAgent* Agent,FProphecyFootIKLiveState& State);
};
