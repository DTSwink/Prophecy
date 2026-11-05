#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyJoltStepClient.h"
#include "ProphecyJoltSkeletalPropComponent.generated.h"

class USkeletalMeshComponent;
class UPrimitiveComponent;
struct FProphecyJoltBodyHandle;
struct FProphecyJoltSkeletalPropState;
struct FProphecyJoltSkeletalPropStateDeleter
{
    void operator()(FProphecyJoltSkeletalPropState*) const;
};

/** Passive PHAT articulation for directly placed skeletal actors; no agent/NN controller. */
UCLASS(Transient)
class GAMEANIMATIONSAMPLE3_API UProphecyJoltSkeletalPropComponent : public UActorComponent, public IProphecyJoltStepClient
{
    GENERATED_BODY()
public:
    UProphecyJoltSkeletalPropComponent();
    virtual ~UProphecyJoltSkeletalPropComponent() override;
    static UProphecyJoltSkeletalPropComponent* Find(const UPrimitiveComponent* Mesh);
    static bool Admit(USkeletalMeshComponent& Mesh, FString& Error);
    bool GetBodyHandle(FName Bone, FProphecyJoltBodyHandle& Handle) const;
    bool RefreshCollisionPolicy(FString& Error);
    double GetCapturedBodyMassKg(FName Bone) const;
    bool SetSimulationEnabled(bool Enabled, FString& Error);
    /** Kinematic bodies only: the world body-origin pose they follow from the next step on
     * (stored relative to the mesh, so moving the actor still carries it). */
    bool SetKinematicBodyTarget(FName Bone, const FTransform& BodyOriginWorld, FString& Error);
    /** Retired bodies keep their mass and joints but collide with nothing. Unchanged input is free. */
    bool SetBodiesCollisionRetired(TConstArrayView<FName> Bones, TConstArrayView<bool> Retired, FString& Error);
    bool IsBodyDynamic(FName Bone) const;
    /** Rig-wide Jolt solver steps (long light chains such as ropes need more than the world default). */
    bool SetSolverIterations(int32 Velocity, int32 Position, FString& Error);
    /** Absolute dynamic mass of one body (inertia scales with it), e.g. to carry a welded attachment. */
    bool SetBodyMassKg(FName Bone, float MassKg, FString& Error);
    bool bAutomaticStep = true;
    bool StepAndPublish(float DeltaSeconds, FString& Error);
    virtual bool IsJoltStepClientActive() const override;
    virtual bool WantsAutomaticJoltStep() const override { return bAutomaticStep; }
    virtual bool PrepareJoltWorldStep(float DeltaSeconds, bool, FString& Error) override;
    virtual bool ConsumeCompletedJoltWorldStep(FString& Error) override;
    virtual void LatchJoltStepError(const FString& Error) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void OnUnregister() override;
private:
    bool Enable(USkeletalMeshComponent& Mesh, FString& Error);
    bool EnableNow(FString& Error);
    void Complete(const FGuid& Token);
    void Cancel(const FGuid& Token);
    void Release();
    TUniquePtr<FProphecyJoltSkeletalPropState, FProphecyJoltSkeletalPropStateDeleter> State;
};
