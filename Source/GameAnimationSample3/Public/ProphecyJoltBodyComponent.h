#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyJoltStepClient.h"
#include "ProphecyJoltBodyComponent.generated.h"

class UPrimitiveComponent;
class USceneComponent;
class UProphecyJoltCharacterWorldSubsystem;
class UProphecyJoltWorldSubsystem;
struct FProphecyJoltBodyHandle;
struct FProphecyJoltBodyState;
struct FProphecyJoltRayHit;
struct FHitResult;
struct FProphecyJoltBodyComponentState;
struct FProphecyJoltBodyComponentStateDeleter
{
    void operator()(FProphecyJoltBodyComponentState* InState) const;
};

DECLARE_MULTICAST_DELEGATE_TwoParams(FProphecyJoltBodyEnableCompleted, bool, const FString&);

/** Owns one existing, independent primitive component through the shared per-world Jolt coordinator.
 * The original component remains the rendering, material and UE query receiver. No world is created.
 */
UCLASS(ClassGroup = Physics, meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyJoltBodyComponent : public UActorComponent, public IProphecyJoltStepClient
{
    GENERATED_BODY()

public:
    UProphecyJoltBodyComponent();
    virtual ~UProphecyJoltBodyComponent() override;

    // Requires this actor's detached, live dynamic primitive component and an initialized native world.
    // True means enabled or safely queued; a queued request retains the original Chaos ownership.
    bool EnableBody(UPrimitiveComponent& Source, FString& OutError);
    // Optional for freshly launched projectiles: hold their exact launch state until queued admission.
    bool FreezePendingLaunch(UPrimitiveComponent& Source, FString& OutError);
    bool IsEnablePending() const { return PendingAdmissionId.IsValid(); }
    bool IsReceiverRestorePending() const { return DeferredRestore || bDisableInProgress; }
    FProphecyJoltBodyEnableCompleted OnDeferredEnableCompleted;
    // Explicitly retires native ownership. Restores the original collision mode with Chaos simulation
    // OFF; a failed activation alone rolls back the original dynamic body after native cleanup.
    void DisableBody();
    bool IsJoltBody() const;
    bool IsAttachedCollider() const;
    /** Weld the source collision onto Hand without adding mass/inertia; rendering stays socket-attached. */
    bool FollowWelded(const FProphecyJoltBodyHandle& Hand, USceneComponent& Parent, FName Socket, const FTransform& Relative, FString& OutError);
    bool IsSteppingStopped() const;
    bool GetBodyHandle(FProphecyJoltBodyHandle& OutHandle) const;
    bool GetBodyState(FProphecyJoltBodyState& OutState) const;
    bool SetSimulationEnabled(bool bEnabled, FString& OutError);
    bool SetMassKg(float MassKg, FString& OutError);
    void SynchronizeSourceTransform();
    bool GetBodyOriginToComponent(FTransform& OutTransform) const;
    UProphecyJoltWorldSubsystem* GetWorldOwner() const;
    bool GetPointVelocity(const FVector& WorldPointCm, FVector& OutVelocityCmPerSecond) const;
    bool SetBodyVelocity(const FVector& CenterOfMassVelocityCmPerSecond,
        const FVector& AngularVelocityRadiansPerSecond, bool bWake, FString& OutError);
    bool AddPointImpulse(const FVector& ImpulseKgCmPerSecond, const FVector& WorldPointCm, FString& OutError);
    UPrimitiveComponent* GetSourceComponent() const;
    // A native simple hit retains component/actor identity but never invents a UE triangle FaceIndex.
    bool MakeHitResult(const FProphecyJoltRayHit& Hit, FHitResult& OutHit) const;
    bool StepAndPublish(float DeltaSeconds, FString& OutError);
    uint64 GetRevision() const;
    const FString& GetLastError() const { return LastError; }

    virtual bool IsJoltStepClientActive() const override { return IsJoltBody(); }
    virtual bool WantsAutomaticJoltStep() const override { return bAutomaticStep; }
    virtual bool PrepareJoltWorldStep(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError) override;
    virtual bool ConsumeCompletedJoltWorldStep(FString& OutError) override;
    virtual void LatchJoltStepError(const FString& Error) override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Jolt")
    bool bAutomaticStep = true;

    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void OnUnregister() override;

private:
    bool EnableBodyNow(UPrimitiveComponent& Source, FString& OutError);
    void CompleteDeferredEnable(const FGuid& AdmissionId);
    void CancelDeferredEnable(const FGuid& AdmissionId);
    void DisableBodyInternal(bool bRestoreOriginalSimulation, bool bCancelEnable);
    void RestoreReceiver(TUniquePtr<FProphecyJoltBodyComponentState, FProphecyJoltBodyComponentStateDeleter> RemovedState);
    bool ValidateBinding(FString& OutError) const;
    bool SynchronizeCollision(FString& OutError);
    bool PublishCompletedBody(FString& OutError);
    bool Fail(FString& OutError, const FString& Message);

    TUniquePtr<FProphecyJoltBodyComponentState, FProphecyJoltBodyComponentStateDeleter> State;
    TUniquePtr<FProphecyJoltBodyComponentState, FProphecyJoltBodyComponentStateDeleter> DeferredRestore;
    TWeakObjectPtr<UPrimitiveComponent> PendingSource;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> AdmissionCoordinator;
    FGuid PendingAdmissionId;
    FGuid StepRegistrationId;
    bool bEnableInProgress = false;
    bool bDisableInProgress = false;
    bool bPublishing = false;
    bool bEnableCancelled = false;
    FString LastError;
};
