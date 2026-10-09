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
    /** Draw the attacker's pelvis and single attack collider consumed by this
     * defender's latest completed Parry/Dodge prediction (including half attacks).
     * Current: cyan pelvis/yellow collider. Previous: blue pelvis/orange collider.
     * Includes configured perception velocity removal and exact trained box sizes.
     * Call on the defender each Tick; no inference, tracing, or recurring work when unused.
     * False before the first completed defense step, when inactive/disabled, or Shipping. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Debug",meta=(DefaultToSelf="Agent",AdvancedDisplay="Duration,Thickness"))
    static bool VisualizeDefenseInputGhost(AProphecyAgent* Agent,bool Enabled=true,
        FVector WorldOffset=FVector(150,0,0),bool ShowPrevious=true,float Duration=0.f,float Thickness=1.f);

    /** Per incoming attack on this defender: nonnegative game ticks after the
     * attacker's first Armed output. 0 starts at Armed; 1 waits one unpaused tick.
     * Starts on the first defense policy step at/after the deadline (30 Hz NN).
     * Does not request defense itself or change existing post-Hit/end deadlines.
     * Synthetic spear excluded; Pike is the sword thrust. Native name retained for saved graphs. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry",meta=(DefaultToSelf="Agent",ClampMin="0",DisplayName="Set Parry Start Delays",Keywords="ticks armed"))
    static bool SetParryStartHitThresholds(AProphecyAgent* Agent,
        int32 Headbutt=0,int32 HookL=0,int32 HookR=0,int32 JabL=0,int32 JabR=0,
        int32 KickL=0,int32 KickR=0,int32 OverL=0,int32 OverR=0,int32 Pike=0,
        int32 SlashL=0,int32 SlashLD=0,int32 SlashLU=0,int32 SlashR=0,int32 SlashRD=0,int32 SlashRU=0);
    /** Dodge equivalent of Set Parry Start Delays. Independent per-attack integer
     * game-tick delays from first Armed, default0; spear excluded. Existing
     * post-Hit/end settings still apply. Native name retained for saved graphs. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent",ClampMin="0",DisplayName="Set Dodge Start Delays",Keywords="ticks armed"))
    static bool SetDodgeStartHitThresholds(AProphecyAgent* Agent,
        int32 Headbutt=0,int32 HookL=0,int32 HookR=0,int32 JabL=0,int32 JabR=0,
        int32 KickL=0,int32 KickR=0,int32 OverL=0,int32 OverR=0,int32 Pike=0,
        int32 SlashL=0,int32 SlashLD=0,int32 SlashLU=0,int32 SlashR=0,int32 SlashRD=0,int32 SlashRU=0);
    /** On half attacks only, remove attacker pelvis horizontal translation from
     * the two observed pelvis/collider samples. Current positions, rotations,
     * height and actual physics stay unchanged. Use Root Velocity selects root
     * translation instead of pelvis translation; subtracts that same motion from
     * both pelvis and collider perception. Remove must be enabled. Spear excluded. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool SetDefenseHalfAttackHorizontalVelocity(AProphecyAgent* Agent,bool bRemove=false,bool bUseRootVelocity=false);
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

    /** Incoming attack aim point captured relative to this defender's capsule root
     * when Parry/Dodge activates. World Target follows the current root translation
     * and rotation; Root Local Target stays fixed (cm, unscaled root axes).
     * Does not track head/bone motion or later attacker retargets, and does not
     * change NN conditioning. False/zero outside active defense, including pre-Armed.
     * One cached lookup and transform on demand; no ticking or inference. */
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static bool GetNNDefenseRelativeTarget(AProphecyAgent* Agent,FVector& WorldTarget,FVector& RootLocalTarget);

    /** Set both Dodge and Parry to end at first attacker Hit frame + Frames (30 Hz NN frames).
     * 0 ends on Hit itself; default 3. Updates ongoing defenses. Attack end/cancellation
     * and maximum duration still end defense earlier; collisions never end it automatically. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetDefenseFramesAfterHit(AProphecyAgent* Agent,int32 Frames=3);
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense",meta=(DefaultToSelf="Agent"))
    static void GetDefenseFramesAfterHit(AProphecyAgent* Agent,int32& DodgeFrames,int32& ParryFrames);

    /** Dodge-only override retained for existing Blueprints. The shared setter updates both modes. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames=3);
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent"))
    static int32 GetDodgeFramesAfterHit(AProphecyAgent* Agent);

    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetParryFootClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetParryCalfClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeFootClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge|Clamps",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeCalfClamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm=0.f);
};
