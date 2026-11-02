#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyBodyflipOptions.h"
#include "ProphecyBodyflipLibrary.generated.h"
class AProphecyAgent;

USTRUCT(BlueprintType)
struct FProphecyBodyflipState
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) bool Active=false;
    UPROPERTY(BlueprintReadOnly) bool Playing=false;
    UPROPERTY(BlueprintReadOnly) bool Grounded=false;
    UPROPERTY(BlueprintReadOnly) float Time=0;
    UPROPERTY(BlueprintReadOnly) float SolveMilliseconds=0;
    UPROPERTY(BlueprintReadOnly) FString Phase;
    UPROPERTY(BlueprintReadOnly) FString Error;
    UPROPERTY(BlueprintReadOnly) FVector Root=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FVector Velocity=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) FString DiagnosticsJson;
};

// Opt-in live controller. Nothing changes in the level until Start is called.
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyBodyflipLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Start with normal typed pins. Split Settings or use Make Bodyflip Settings. No automatic jump is queued. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip",meta=(DisplayName="Start Bodyflip",AutoCreateRefTerm="Settings"))
    static bool StartBodyflipWithOptions(AProphecyAgent* Agent,const FProphecyBodyflipSettings& Settings,FString& Error);
    /** AtTime is absolute playback seconds. Inherit preserves spin; explicit zero stops it. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip",meta=(DisplayName="Queue Bodyflip Jump",AutoCreateRefTerm="Spin,Pose,Attack",CPP_Default_JumpPercent="100",CPP_Default_PushWith="Foot"))
    static bool QueueBodyflipJumpWithOptions(AProphecyAgent* Agent,float AtTime,float JumpPercent,EProphecyBodyflipPush PushWith,const FProphecyBodyflipSpinOptions& Spin,const FProphecyBodyflipPoseOptions& Pose,const FProphecyBodyflipAttackOptions& Attack,FString& Error,bool Enabled=true);
    /** Settings use the same JSON fields as Bodyflip Lab. RunJson is the native
        NN rollout override; leave empty to run the packaged native NN. JSON uses lab
        metres/Y-up. World target and platform helpers handle conversion. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip|Legacy",meta=(DeprecatedFunction,DeprecationMessage="Use Start Bodyflip with typed settings",DisplayName="Start Bodyflip (Legacy JSON)"))
    static bool StartBodyflip(AProphecyAgent* Agent,const FString& SettingsJson,const FString& RunJson,FString& Error);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip")
    static bool StopBodyflip(AProphecyAgent* Agent);
    /** Replay the captured November 2 lab scene and tuning, in this agent's starting frame. Does not change Blueprint defaults or wiring. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip",meta=(DisplayName="Start Bodyflip Saved Lab Setup"))
    static bool StartBodyflipSavedLabSetup(AProphecyAgent* Agent,FString& Error);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip")
    static bool PauseBodyflip(AProphecyAgent* Agent,bool Paused);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip")
    static bool SeekBodyflip(AProphecyAgent* Agent,float Time,FString& Error);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip")
    static bool SetBodyflipTarget(AProphecyAgent* Agent,FVector WorldTarget,FString& Error);
    UFUNCTION(BlueprintPure,Category="Prophecy|Bodyflip")
    static bool GetBodyflipState(AProphecyAgent* Agent,FProphecyBodyflipState& State);
    /** Append an event using the exact per-jump lab fields (flip/twist in deg/s,
        jumpPercent, pushWith, pose, attack, delays, ramps and Instant spin). */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip|Legacy",meta=(DeprecatedFunction,DeprecationMessage="Use Queue Bodyflip Jump with typed options",DisplayName="Queue Bodyflip Jump (Legacy JSON)"))
    static bool QueueBodyflipJump(AProphecyAgent* Agent,float AtTime,const FString& JumpJson,FString& Error);
    /** Finite oriented box platforms in UE world centimetres. Settings are
        rebuilt at the current time so the support cone and body contact agree. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Bodyflip")
    static bool SetBodyflipPlatforms(AProphecyAgent* Agent,const TArray<FTransform>& WorldTransforms,const TArray<FVector>& FullSizesCm,FString& Error);
};
