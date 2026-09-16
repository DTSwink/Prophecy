#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyJoltStepClient.h"
#include "ProphecyJoltSceneCollisionComponent.generated.h"

class UPrimitiveComponent;
class USceneComponent;
class ULevel;
class UProphecyJoltCharacterWorldSubsystem;
struct FProphecyJoltBodyHandle;
struct FProphecyJoltSceneCollisionState;
struct FProphecyJoltSceneCollisionStateDeleter
{
    void operator()(FProphecyJoltSceneCollisionState* State) const;
};

/** Explicit static collision import into an already initialized shared Jolt world.
 * One owner per world. Original UE query bodies/materials remain intact. No independent tick/step.
 */
UCLASS(ClassGroup = Physics, meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyJoltSceneCollisionComponent : public UActorComponent, public IProphecyJoltStepClient
{
    GENERATED_BODY()
public:
    UProphecyJoltSceneCollisionComponent();
    virtual ~UProphecyJoltSceneCollisionComponent() override;

    // True means enabled or queued at the existing coordinator's next safe admission boundary.
    UFUNCTION(BlueprintCallable, Category = "Prophecy|Jolt")
    bool EnableSceneCollision(FString& OutError);
    UFUNCTION(BlueprintCallable, Category = "Prophecy|Jolt")
    void DisableSceneCollision();
    UFUNCTION(BlueprintPure, Category = "Prophecy|Jolt")
    bool IsSceneCollisionEnabled() const;
    UFUNCTION(BlueprintPure, Category = "Prophecy|Jolt")
    bool IsEnablePending() const { return PendingAdmissionId.IsValid(); }
    int32 GetImportedBodyCount() const;
    bool bAutomaticScenePhysics = false;
    static UProphecyJoltSceneCollisionComponent* FindForWorld(UWorld* World);
    bool GetBodyHandle(const UPrimitiveComponent& Source, int32 InstanceIndex, FProphecyJoltBodyHandle& OutHandle) const;
    UFUNCTION(BlueprintPure, Category = "Prophecy|Jolt")
    const FString& GetLastError() const { return LastError; }

    virtual bool IsJoltStepClientActive() const override { return IsSceneCollisionEnabled(); }
    virtual bool WantsAutomaticJoltStep() const override { return bAutomaticScenePhysics; }
    virtual bool PrepareJoltWorldStep(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError) override;
    virtual bool ConsumeCompletedJoltWorldStep(FString& OutError) override;
    virtual void LatchJoltStepError(const FString& Error) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void OnUnregister() override;

private:
    bool EnableNow(FString& OutError);
    void CompleteDeferredEnable(const FGuid& AdmissionId);
    void CancelDeferredEnable(const FGuid& AdmissionId);
    bool ValidateBinding(FString& OutError) const;
    bool ReconcileSources(FString& OutError);
    void QueueSource(UPrimitiveComponent* Source, bool bPhysicsDestroyed = false);
    void QueueActor(AActor* Actor);
    void ObserveSource(UPrimitiveComponent& Source);
    void OnPhysicsCreated(UActorComponent* Component);
    void OnPhysicsDestroyed(UActorComponent* Component);
    UFUNCTION()
    void OnSourceCollisionSettings(UPrimitiveComponent* Source);
    void OnLevelAdded(ULevel* Level, UWorld* World);
    void OnLevelRemoved(ULevel* Level, UWorld* World);
    void QueueLevel(ULevel* Level);
    bool Fail(FString& OutError, const FString& Error);

    TUniquePtr<FProphecyJoltSceneCollisionState, FProphecyJoltSceneCollisionStateDeleter> State;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> AdmissionCoordinator;
    FGuid PendingAdmissionId;
    FGuid StepRegistrationId;
    bool bEnabling = false;
    bool bReconciling = false;
    FString LastError;
};
