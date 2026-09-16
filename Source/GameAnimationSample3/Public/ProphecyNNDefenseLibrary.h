#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyNNDefenseLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyParryBlocker : uint8 { Blade, LeftArm, RightArm };

USTRUCT(BlueprintType)
struct FProphecyNNDefenseStatus
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly,Category="Defense") bool Active=false;
    UPROPERTY(BlueprintReadOnly,Category="Defense") bool Blocked=false;
    UPROPERTY(BlueprintReadOnly,Category="Defense") bool HarmfulContact=false;
    UPROPERTY(BlueprintReadOnly,Category="Defense") int32 CompletedSteps=0;
    UPROPERTY(BlueprintReadOnly,Category="Defense") int32 AttackerFrame=0;
    UPROPERTY(BlueprintReadOnly,Category="Defense") float ContactTimeSeconds=-1;
    UPROPERTY(BlueprintReadOnly,Category="Defense") FName ContactCollider;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyNNDefenseLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Start the saved upper-only parry checkpoint against an already active NN attack.
     * Keeps lower locomotion unchanged. Target and initial root command are captured once. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool StartNNParry(AProphecyAgent* Agent,AProphecyAgent* Attacker,EProphecyParryBlocker Blocker,
        FString& OutError,float MaximumDurationSeconds=3.f);
    /** Start the saved banked Dodge with its own frozen walk/run lower policy.
     * Captures the current locomotion category and root command for this episode. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool StartNNDodge(AProphecyAgent* Agent,AProphecyAgent* Attacker,
        FString& OutError,float MaximumDurationSeconds=3.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool StopNNDefense(AProphecyAgent* Agent);
    /** Read the last completed result; does not sample bones, sweep or run inference. */
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool GetNNDefenseStatus(AProphecyAgent* Agent,FProphecyNNDefenseStatus& Status);
};
