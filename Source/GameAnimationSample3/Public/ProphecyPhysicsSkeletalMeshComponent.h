#pragma once

#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "ProphecyPhysicsSkeletalMeshComponent.generated.h"

/** Standard UE physics commands use Jolt when it owns this receiver; otherwise use Chaos. */
UCLASS(ClassGroup = Physics, meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicsSkeletalMeshComponent : public USkeletalMeshComponent
{
    GENERATED_BODY()
public:
    virtual void AddForce(FVector Force, FName BoneName, bool bAccelChange) override;
    virtual void AddImpulse(FVector Impulse, FName BoneName, bool bVelChange) override;
    virtual void AddTorqueInRadians(FVector Torque, FName BoneName, bool bAccelChange) override;
    virtual void AddAngularImpulseInRadians(FVector Impulse, FName BoneName, bool bVelChange) override;
    virtual void AddForceAtLocation(FVector Force, FVector Location, FName BoneName) override;
    virtual void AddForceAtLocationLocal(FVector Force, FVector Location, FName BoneName) override;
    virtual void AddImpulseAtLocation(FVector Impulse, FVector Location, FName BoneName) override;
    virtual void AddRadialForce(FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bAccelChange) override;
    virtual void AddRadialImpulse(FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bVelChange) override;
    virtual void SetPhysicsLinearVelocity(FVector NewVel, bool bAddToCurrent, FName BoneName) override;
    virtual void SetPhysicsAngularVelocityInRadians(FVector NewAngVel, bool bAddToCurrent, FName BoneName) override;
    virtual void SetAllPhysicsLinearVelocity(FVector NewVel, bool bAddToCurrent) override;
    virtual void SetAllPhysicsAngularVelocityInRadians(const FVector& NewAngVel, bool bAddToCurrent) override;
    virtual void AddForceToAllBodiesBelow(FVector Force, FName BoneName, bool bAccelChange, bool bIncludeSelf) override;
    virtual void AddImpulseToAllBodiesBelow(FVector Impulse, FName BoneName, bool bVelChange, bool bIncludeSelf) override;
};
