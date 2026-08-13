#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "PhysicsHitVelocityLibrary.generated.h"

class UPrimitiveComponent;

USTRUCT(BlueprintType)
struct FPreHitVelAngVelResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	bool bSuccess = false;

	// Reconstructed center-of-mass linear velocity before the hit, cm/s.
	UPROPERTY(BlueprintReadOnly)
	FVector PreLinearVelocity = FVector::ZeroVector;

	// Reconstructed angular velocity before the hit, radians/s.
	UPROPERTY(BlueprintReadOnly)
	FVector PreAngularVelocityRad = FVector::ZeroVector;

	// Reconstructed velocity at the impact point before the hit, cm/s.
	UPROPERTY(BlueprintReadOnly)
	FVector PrePointVelocity = FVector::ZeroVector;

	// Current post-hit linear velocity, cm/s.
	UPROPERTY(BlueprintReadOnly)
	FVector FinalLinearVelocity = FVector::ZeroVector;

	// Current post-hit angular velocity, radians/s.
	UPROPERTY(BlueprintReadOnly)
	FVector FinalAngularVelocityRad = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly)
	FVector DeltaLinearVelocity = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly)
	FVector DeltaAngularVelocityRad = FVector::ZeroVector;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UPhysicsHitVelocityLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Reconstructs pre-hit linear/angular velocity from post-hit velocity + collision impulse.
	 *
	 * @param Sword                 The physics component you want to reconstruct.
	 * @param ImpactLocation        World-space impact point, usually Hit.ImpactPoint.
	 * @param NormalImpulseOnSword  The NormalImpulse vector applied to Sword. Pass OnComponentHit's NormalImpulse
	 *                              if the hit event is bound on Sword.
	 * @param BoneName              Optional skeletal bone/body name. Leave None for static mesh.
	 */
	UFUNCTION(BlueprintCallable, Category = "Physics|Hit")
	static FPreHitVelAngVelResult RetrieveVelAngVel(
		UPrimitiveComponent* Sword,
		FVector ImpactLocation,
		FVector NormalImpulseOnSword,
		FName BoneName = NAME_None
	);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Spring", meta = (DisplayName = "spring_cpp", WorldContext = "WorldContextObject", AdvancedDisplay = "DeltaSeconds", ReturnDisplayName = "Delta Velocity", Keywords = "spring delta velocity dvelocity target snap physics"))
	static FVector spring_cpp(
		const UObject* WorldContextObject,
		FVector Position,
		FVector Velocity,
		FVector TargetPosition,
		float DVelMax = 1000000.0f,
		float Tolerance = 0.0f,
		float DeltaSeconds = -1.0f);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Spring", meta = (DisplayName = "angspring_cpp", WorldContext = "WorldContextObject", AdvancedDisplay = "DeltaSeconds", ReturnDisplayName = "Delta Angular Velocity Rad", Keywords = "spring angular delta velocity dvelocity target rotation snap physics"))
	static FVector angspring_cpp(
		const UObject* WorldContextObject,
		FRotator Rotation,
		FVector AngularVelocityRad,
		FRotator TargetRotation,
		float DAngVelMax = 1000000.0f,
		float Tolerance = 0.0f,
		float DeltaSeconds = -1.0f);
};
