#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProphecyJoltFightSetup.generated.h"

class AProphecyAgent;
class UProphecyJoltSceneCollisionComponent;

/** Place once in a fight level to select Jolt for manual NN fighters starting in Physical mode. */
UCLASS(BlueprintType, Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyJoltFightSetup : public AActor
{
    GENERATED_BODY()
public:
    AProphecyJoltFightSetup();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    /** Choose before Play. False leaves normal Chaos startup unchanged. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Prophecy|Jolt")
    bool bEnableJolt = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Prophecy|Jolt")
    TObjectPtr<UProphecyJoltSceneCollisionComponent> SceneCollision;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category="Prophecy|Jolt")
    int32 StartedAgentCount = 0;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Transient, Category="Prophecy|Jolt")
    FString LastError;

private:
    void QueueActor(AActor* Actor);
    void BeforeActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
    void ReportError(const FString& Error);
    TSet<TWeakObjectPtr<AProphecyAgent>> PendingAgents;
    FDelegateHandle SpawnHandle;
    FDelegateHandle PreActorTickHandle;
};
