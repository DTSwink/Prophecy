#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyUpperCheckpointLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyUpperCheckpoint : uint8
{
    ProjectDefault = 0 UMETA(DisplayName="Project Default"),
    October1Step82500 = 1 UMETA(DisplayName="October 1 - Previous (82500)"),
    HandVelocityBound85750 = 2 UMETA(DisplayName="October 1 - Hand Velocity Bound (85750)"),
    HandVelocityBound86750 = 3 UMETA(DisplayName="October 1 - Hand Velocity Bound (86750)"),
    HandVelocityBound83750 = 4 UMETA(DisplayName="October 1 - Hand Velocity Bound (83750)")
};

UENUM(BlueprintType)
enum class EProphecyParryCheckpoint : uint8
{
    ProjectDefault = 0 UMETA(DisplayName="Project Default (current 1149700)"),
    Step1149700 = 1 UMETA(DisplayName="Parry 1149700"),
    Step1178405 = 2 UMETA(DisplayName="Parry 1178405"),
    Step1216457 = 3 UMETA(DisplayName="Parry 1216457")
};

UENUM(BlueprintType)
enum class EProphecyDodgeCheckpoint : uint8
{
    ProjectDefault = 0 UMETA(DisplayName="Project Default (current 322925)"),
    Step322925 = 1 UMETA(DisplayName="Dodge 322925"),
    Inertia151341 = 2 UMETA(DisplayName="Dodge 151341 - Inertia x3")
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyUpperCheckpointLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Switches the shared upper locomotion model for ALL agents in Agent's manager.
     * Call after agent initialization (delayed BeginPlay). Applies next NN update;
     * preserves pose/history. Loads and validates on selection changes only, with no
     * additional per-tick inference. Failure leaves the previous model active.
     * Project Default uses the usual upper model files; named choices are frozen. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Upper Body",meta=(DefaultToSelf="Agent",CPP_Default_Checkpoint="October1Step82500"))
    static bool SetUpperCheckpoint(AProphecyAgent* Agent,EProphecyUpperCheckpoint Checkpoint,FString& OutError);

    /** Returns the shared selection; false for an uninitialized agent or custom model paths. */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Upper Body",meta=(DefaultToSelf="Agent"))
    static bool GetUpperCheckpoint(AProphecyAgent* Agent,EProphecyUpperCheckpoint& Checkpoint);

    /** Shared Parry selection for ALL agents in this agent's manager. Call after
     * agent initialization. Loads only when changed, preserves active histories,
     * applies on the next policy update. Failure preserves the previous selection.
     * Default keeps the installed model; numbered choices are frozen. No extra inference per tick. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Parry",meta=(DefaultToSelf="Agent"))
    static bool SetParryCheckpoint(AProphecyAgent* Agent,EProphecyParryCheckpoint Checkpoint,FString& OutError);
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense|Parry",meta=(DefaultToSelf="Agent"))
    static bool GetParryCheckpoint(AProphecyAgent* Agent,EProphecyParryCheckpoint& Checkpoint);

    /** Shared Dodge selection for ALL agents in this agent's manager. Same loading,
     * failure and history rules as Parry. These choices have identical frozen lower
     * policies, settings and bank limits, verified at export; only upper weights switch. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent"))
    static bool SetDodgeCheckpoint(AProphecyAgent* Agent,EProphecyDodgeCheckpoint Checkpoint,FString& OutError);
    UFUNCTION(BlueprintPure,Category="Prophecy|NN Defense|Dodge",meta=(DefaultToSelf="Agent"))
    static bool GetDodgeCheckpoint(AProphecyAgent* Agent,EProphecyDodgeCheckpoint& Checkpoint);
};
