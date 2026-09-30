#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySlashTrainDebugLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySlashTrainDebugLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Debug only: teleport the kinematic pose and both NN history frames to viewer
     * seed 2026092223, relative to the current mesh carrier. Call once immediately
     * before the first attack, after initialization. The next 30 full attacks use
     * the viewer's stationary reference frame, then ordinary framing resumes.
     * Does not change checkpoint weights or gameplay tuning. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Debug|Slash Train", meta=(DefaultToSelf="Agent",DevelopmentOnly))
    static bool SetSlashTrainStartingPose(AProphecyAgent* Agent,FString& OutError);

    /** Explicit debug reset: put both NN history frames at original neutral idle frame 0,
     * relative to this agent's current carrier, and return the selected attack's original
     * GT target in world space. Call immediately before Trigger NN Attack. Requires an
     * idle Kinematic agent; does not select a checkpoint or change attack tuning.
     * Reads only the small local fixture on request; no idle tick/inference work. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Debug|Slash Train",
        meta=(DefaultToSelf="Agent",DevelopmentOnly,DisplayName="Prepare GT Attack From Idle"))
    static bool PrepareGTAttackFromIdle(AProphecyAgent* Agent,FName Attack,
        FVector& TargetWorldLocation,FString& OutError);
};
