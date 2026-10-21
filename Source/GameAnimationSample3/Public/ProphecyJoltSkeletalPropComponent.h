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
