#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Components/PrimitiveComponent.h"
#include "ProphecyJoltStandardPhysicsLibrary.generated.h"

class UPhysicsConstraintComponent;

/** Internal compiler targets. Users retain the standard Unreal Blueprint nodes and component references. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyJoltStandardPhysicsLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void GetConstraintForce(UPhysicsConstraintComponent* Component, FVector& OutLinearForce, FVector& OutAngularForce);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static float GetCurrentTwist(UPhysicsConstraintComponent* Component);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static float GetCurrentSwing1(UPhysicsConstraintComponent* Component);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static float GetCurrentSwing2(UPhysicsConstraintComponent* Component);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddForce(UPrimitiveComponent* Component, FVector Force, FName BoneName, bool bAccelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddImpulse(UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddTorqueInRadians(UPrimitiveComponent* Component, FVector Torque, FName BoneName, bool bAccelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddAngularImpulseInRadians(UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddForceAtLocation(UPrimitiveComponent* Component, FVector Force, FVector Location, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddForceAtLocationLocal(UPrimitiveComponent* Component, FVector Force, FVector Location, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddImpulseAtLocation(UPrimitiveComponent* Component, FVector Impulse, FVector Location, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddRadialForce(UPrimitiveComponent* Component, FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bAccelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddRadialImpulse(UPrimitiveComponent* Component, FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bVelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetPhysicsLinearVelocity(UPrimitiveComponent* Component, FVector NewVel, bool bAddToCurrent, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetPhysicsAngularVelocityInRadians(UPrimitiveComponent* Component, FVector NewAngVel, bool bAddToCurrent, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetAllPhysicsLinearVelocity(UPrimitiveComponent* Component, FVector NewVel, bool bAddToCurrent);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetAllPhysicsAngularVelocityInRadians(UPrimitiveComponent* Component, const FVector& NewAngVel, bool bAddToCurrent);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetSimulatePhysics(UPrimitiveComponent* Component, bool bSimulate);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetMassOverrideInKg(UPrimitiveComponent* Component, FName BoneName, float MassInKg, bool bOverrideMass);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static FVector GetPhysicsLinearVelocity(UPrimitiveComponent* Component, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static FVector GetPhysicsLinearVelocityAtPoint(UPrimitiveComponent* Component, FVector Point, FName BoneName);
    UFUNCTION(BlueprintPure, meta=(BlueprintInternalUseOnly="true"))
    static FVector GetPhysicsAngularVelocityInRadians(UPrimitiveComponent* Component, FName BoneName);
    UFUNCTION(BlueprintPure, meta=(BlueprintInternalUseOnly="true"))
    static FVector GetPhysicsAngularVelocityInDegrees(UPrimitiveComponent* Component, FName BoneName);
    UFUNCTION(BlueprintPure, meta=(BlueprintInternalUseOnly="true"))
    static bool IsSimulatingPhysics(USceneComponent* Component, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddTorqueInDegrees(UPrimitiveComponent* Component, FVector Torque, FName BoneName, bool bAccelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void AddAngularImpulseInDegrees(UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void SetPhysicsAngularVelocityInDegrees(UPrimitiveComponent* Component, FVector NewAngVel, bool bAddToCurrent, FName BoneName);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void K2_SetWorldLocation(USceneComponent* Component, FVector NewLocation, bool bSweep, FHitResult& SweepHitResult, bool bTeleport);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void K2_SetWorldRotation(USceneComponent* Component, FRotator NewRotation, bool bSweep, FHitResult& SweepHitResult, bool bTeleport);
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true"))
    static void K2_SetWorldTransform(USceneComponent* Component, const FTransform& NewTransform, bool bSweep, FHitResult& SweepHitResult, bool bTeleport);
};
