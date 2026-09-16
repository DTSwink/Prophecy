#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Containers/ArrayView.h"
#include "ProphecyJoltStepClient.h"
#include "ProphecyJoltCharacterComponent.generated.h"

struct FProphecyJoltBodyHandle;
struct FProphecyJoltRayHit;
struct FHitResult;
struct FConstraintProfileProperties;
class UProphecyJoltCharacterWorldSubsystem;
class UPhysicalMaterial;
struct FProphecyJoltCharacterState;
struct FProphecyJoltCharacterStateDeleter
{
    void operator()(FProphecyJoltCharacterState* InState) const;
};

DECLARE_MULTICAST_DELEGATE_TwoParams(FProphecyJoltDeferredEnableCompleted, bool, const FString&);

/** Opt-in rig binding to one shared per-world Jolt step coordinator. No world geometry is invented. */
UCLASS(ClassGroup = Physics, meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyJoltCharacterComponent : public UActorComponent, public IProphecyJoltStepClient
{
    GENERATED_BODY()

public:
    UProphecyJoltCharacterComponent();
    virtual ~UProphecyJoltCharacterComponent() override;

    // True means enabled or accepted for the next safe pre-tick admission. Pending keeps Chaos ownership.
    // Requires a live manual PhysicalMesh and initialized Jolt world; inspect IsEnablePending for async status.
    bool EnablePhysicalAnimation(FString& OutError);
    bool IsEnablePending() const { return PendingAdmissionId.IsValid(); }
    bool WasEnableCancelled() const { return bEnableCancelled; }
    // Native ownership is already gone; mesh restoration is finishing at the current publication boundary.
    bool IsKinematicRestorePending() const { return DeferredMeshRestore || bDisableInProgress; }
    // One-shot deferred result. Cleared before broadcast; cancellation clears without a callback.
    FProphecyJoltDeferredEnableCompleted OnDeferredEnableCompleted;
    void DisablePhysicalAnimation();
    bool IsJoltPhysical() const;
    // An automatic-step failure retains Jolt ownership and its error. Only explicit Disable/Enable recovers.
    bool IsSteppingStopped() const;
    bool PublishAuthoredTargets(float DeltaSeconds, FString& OutError);
    // Explicit shared-world step; refused while any registered client requests automatic stepping.
    // Caller publishes targets explicitly. Every registered client consumes the same completed world step.
    bool StepAndPublish(float DeltaSeconds, FString& OutError);
    bool SampleCompletedComponentPose(TConstArrayView<FName> BoneNames, TArrayView<FTransform> OutTransforms) const;
    // Paired with the authored target of that completed step, not today's published pose.
    // First request arms the small capture cache; false until a matching step completes.
    bool SampleCompletedLowerFeedbackPose(TConstArrayView<FName> BoneNames, const FTransform& Reference,
        TArrayView<FTransform> OutActual, TArrayView<FTransform> OutAuthored) const;
    bool GetBodyState(FName BoneName, FTransform& OutBodyWorld, FVector& OutLinearVelocity,
        FVector& OutAngularVelocity, bool& bOutSimulating) const;
    bool GetBodyHandle(FName BoneName, FProphecyJoltBodyHandle& OutHandle) const;
    bool GetRigIdentityBody(FProphecyJoltBodyHandle& OutHandle) const;
    void SetHitEventsEnabled(bool bEnabled);
    double GetCapturedBodyMassKg(FName BoneName) const;
    // Preserve the original skeletal receiver identity. Native subshape IDs are never UE triangle FaceIndex values.
    bool MakeHitResult(const FProphecyJoltRayHit& Hit, FHitResult& OutHit) const;
    uint64 GetRevision() const;
    // On-demand diagnostics only; never sampled by the simulation path.
    int32 GetSpeculativeSwingJointCount() const;
    bool SetCCDMode(uint8 Mode, FString& OutError);
    bool SetSolverIterations(int32 Velocity, int32 Position, FString& OutError);
    // Complete angular-only update; preserves native articulation and synchronizes the UE receiver.
    bool ApplyAngularLimitProfiles(TConstArrayView<FConstraintProfileProperties> Profiles, FString& OutError);
    bool SetSelfCollisionEnabled(bool bEnabled, FString& OutError);
    bool SetBodiesPhysicalMaterialOverride(TConstArrayView<FName> BodyBones, UPhysicalMaterial* Material, FString& OutError);
    bool SetBodiesSelfCollisionEnabled(TConstArrayView<FName> BodyBones, bool bEnabled, FString& OutError);
    bool SetSelfCollisionBelow(FName BoneName, bool bEnabled, bool bIncludeSelf, FString& OutError);
    bool SetBodyPairSelfCollisionEnabled(FName Bone1, FName Bone2, bool bEnabled, FString& OutError);
    bool ResetSelfCollision(FString& OutError);
    bool GetBodyPairSelfCollisionEnabled(FName Bone1, FName Bone2, bool& bOutEnabled, FString& OutError) const;
    const FString& GetLastError() const { return LastError; }

    virtual bool IsJoltStepClientActive() const override { return IsJoltPhysical(); }
    virtual bool WantsAutomaticJoltStep() const override { return bAutomaticStep; }
    virtual bool PrepareJoltWorldStep(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError) override;
    virtual bool ConsumeCompletedJoltWorldStep(FString& OutError) override;
    virtual void LatchJoltStepError(const FString& Error) override;

    /** Requests a shared automatic world step. False does not freeze this rig when another client requests a step. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Jolt")
    bool bAutomaticStep = true;

    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void OnUnregister() override;

private:
    friend class AProphecyAgent;
    void RefreshPlayerSwingLimits();
    bool ReadPoseErrorBody(FName BoneName, int32& OutBodyIndex, double& OutMassKg, FTransform& OutBodyWorld) const;
    friend class UProphecyJoltCharacterWorldSubsystem;
    static void PrepareCompletedPoseBatch(TConstArrayView<UProphecyJoltCharacterComponent*> Characters, float DeltaSeconds);
    bool EnablePhysicalAnimationNow(FString& OutError);
    void CompleteDeferredEnable(const FGuid& AdmissionId);
    void CancelDeferredEnable(const FGuid& AdmissionId);
    void DisablePhysicalAnimationInternal(bool bCancelEnable);
    void RestoreKinematicMesh(TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> RemovedState);
    bool PrepareForCoordinatedWorldStep(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError);
    bool ValidateAngularLimitSource(FString& OutError) const;
    bool ValidateSelfCollisionSource(FString& OutError) const;
    bool SynchronizeAngularLimits(FString& OutError);
    bool ConsumeCompletedWorldStep(FString& OutError);
    void LatchSteppingStopped(const FString& Error);
    bool PublishCompletedPose(FString& OutError);
    bool Fail(FString& OutError, const FString& Message);
    TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> State;
    TUniquePtr<FProphecyJoltCharacterState, FProphecyJoltCharacterStateDeleter> DeferredMeshRestore;
    bool bPublishingCompletedPose = false;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> AdmissionCoordinator;
    FGuid PendingAdmissionId;
    FGuid StepRegistrationId;
    bool bEnableInProgress = false;
    bool bDisableInProgress = false;
    bool bEnableCancelled = false;
    FString LastError;
};
