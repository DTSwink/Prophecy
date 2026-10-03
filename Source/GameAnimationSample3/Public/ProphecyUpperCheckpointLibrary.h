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
};
