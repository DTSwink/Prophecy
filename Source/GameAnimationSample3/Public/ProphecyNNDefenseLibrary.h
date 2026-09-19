#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyNNDefenseLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyAgentState : uint8 { Locomotion, Parrying, Dodging, Attacking };

USTRUCT(BlueprintType)
struct FProphecyNNDefenseStatus
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly,Category="Defense") bool Active=false;
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
    /** Current active NN mode. A defense waiting for Armed leaves the current locomotion/attack state unchanged. */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent",meta=(DefaultToSelf="Agent"))
    static EProphecyAgentState GetAgentState(AProphecyAgent* Agent);
    /** Start the saved upper-only parry checkpoint against an already active NN attack.
     * Keeps lower locomotion live; target and mover conditioning update each policy step. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool StartNNParry(AProphecyAgent* Agent,AProphecyAgent* Attacker,
        FString& OutError,float MaximumDurationSeconds=3.f);
    /** Start the saved banked Dodge with its own frozen walk/run lower policy.
     * Follows the live locomotion category and combines the mover command with learned root corrections. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool StartNNDodge(AProphecyAgent* Agent,AProphecyAgent* Attacker,
        FString& OutError,float MaximumDurationSeconds=3.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool StopNNDefense(AProphecyAgent* Agent);
    /** Read the last completed result; does not sample bones, sweep or run inference. */
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool GetNNDefenseStatus(AProphecyAgent* Agent,FProphecyNNDefenseStatus& Status);

    /** Per defender. End Dodge at first attacker Hit frame + Frames (30 Hz NN frames).
     * 0 ends on Hit itself; default 1. Changes also affect an ongoing Dodge.
     * Earlier contact, attack end/cancellation and maximum duration still apply. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames=1);
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent"))
    static int32 GetDodgeFramesAfterHit(AProphecyAgent* Agent);

    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetParryFootClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetParryCalfClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetParryHandClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetParryForearmClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeFootClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeCalfClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeHandClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeForearmClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
};
