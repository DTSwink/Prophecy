#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PhysicsEngine/PhysicalAnimationComponent.h"
#include "ProphecyHalfSimDriveComponent.generated.h"

class USkeletalMeshComponent;

UENUM(BlueprintType)
enum class EProphecyHalfSimDriveMethod : uint8
{
    NativeWorld UMETA(DisplayName="Native World Drives (original)"),
    NativeLocal UMETA(DisplayName="Native Local Drives (unsupported pelvis)"),
    NativeLocalPelvis UMETA(DisplayName="Native Local Drives + Pelvis Support"),
    JointMotors UMETA(DisplayName="Anatomical Joint Motors (unsupported pelvis)"),
    JointMotorsPelvis UMETA(DisplayName="Anatomical Joint Motors + Pelvis Support"),
    WorldForcePD UMETA(DisplayName="World Force / Torque PD (experimental)"),
    Passive UMETA(DisplayName="Passive Ragdoll (no drives)"),
    WorldOneStep UMETA(DisplayName="World Magnetization (existing native Sim rule)")
};

/** Shared native implementation used by Half Sim and the headless benchmark.
 * Never creates another skeletal mesh. Joint modes reuse the PHAT constraints. */
UCLASS(ClassGroup=Physics, meta=(BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyHalfSimDriveComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyHalfSimDriveComponent();
    bool Configure(USkeletalMeshComponent* InMesh, UPhysicalAnimationComponent* InNative,
        EProphecyHalfSimDriveMethod InMethod, FName InRoot,
        const FPhysicalAnimationData& InSettings, float InStrength);
    void Stop();
    void SetBodySettings(FName Bone, const FPhysicalAnimationData& Data, bool CancelGravity = true);
    static bool ApplyOneStepBody(FBodyInstance* Body, const FTransform& Target, float Dt,
        float LinearScale, float AngularScale, bool CancelGravity, float GravityZ);
    void SetStrength(float Value);
    int32 GetNativeTargetCount() const { return NativeTargetCount; }
    int32 GetJointMotorCount() const { return JointMotorCount; }
    EProphecyHalfSimDriveMethod GetMethod() const { return Method; }
    virtual void TickComponent(float Dt, ELevelTick Type, FActorComponentTickFunction* Tick) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Mesh;
    UPROPERTY(Transient) TObjectPtr<UPhysicalAnimationComponent> Native;
    EProphecyHalfSimDriveMethod Method = EProphecyHalfSimDriveMethod::NativeWorld;
    FName Root;
    float Strength = 1;
    TMap<FName,FPhysicalAnimationData> BodySettings;
    TMap<FName,bool> BodyCancelGravity;
    FPhysicalAnimationData BaseSettings;
    TArray<FTransform> AnimationCS;
    int32 NativeTargetCount = 0, JointMotorCount = 0;
};
