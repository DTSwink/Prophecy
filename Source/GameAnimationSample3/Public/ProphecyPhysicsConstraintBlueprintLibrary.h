#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "PhysicsEngine/ConstraintTypes.h"
#include "ProphecyPhysicsConstraintBlueprintLibrary.generated.h"

class UPhysicsConstraintComponent;
class UPrimitiveComponent;
class USkeletalMeshComponent;
class UStaticMeshComponent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicsConstraintBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Physics|Components|PhysicsConstraint", meta = (DisplayName = "Get Linear ZLimit", Keywords = "constraint physics linear z limit motion free limited locked"))
	static void GetLinearZLimit(
		UPhysicsConstraintComponent* Target,
		TEnumAsByte<ELinearConstraintMotion>& ConstraintType,
		float& LimitSize);

	/**
	 * Continuously retracts or expands the Potence rope while its Physics Asset bodies simulate.
	 * The `joint` body remains kinematic and reels the unchanged constraint chain above the
	 * fixed visual anchor. Hidden joint1..joint27 shapes stop colliding but remain simulated.
	 * The target must be a UProphecyRetractableSkeletalMeshComponent so the same component
	 * can render its Z-only shortened pose without duplicating the mesh or its collision.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Rope", meta = (DisplayName = "Update Potence Rope Physics", ReturnDisplayName = "Succeeded"))
	static bool UpdatePotenceRopePhysics(
		USkeletalMeshComponent* Target,
		float Amount);

	/**
	 * Rigidly joins the existing noose body to the terminal PHAT body. This is a
	 * one-time weld, not a per-frame transform correction: the noose shapes become
	 * part of joint27, so collision remains physical without a second constraint
	 * accumulating visible solver stretch.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Rope", meta = (DisplayName = "Weld Noose To Rope End", ReturnDisplayName = "Succeeded"))
	static bool WeldNooseToRopeEnd(
		UPhysicsConstraintComponent* Constraint,
		UStaticMeshComponent* Noose,
		USkeletalMeshComponent* Rope,
		FName TerminalBone = TEXT("joint27"));

	/**
	 * Applies a continuous, deterministic small-wave load to one simulated body.
	 * Three band-limited wave components create heave and a spatial wave slope;
	 * the slope is integrated across four virtual hull corners to produce physical
	 * roll/pitch torque. Two slower components provide bounded horizontal drift.
	 *
	 * Call once per Tick while the boat is active. Unlike a random impulse, this
	 * force is continuous across frames and Unreal maintains it across physics
	 * substeps. The function is stateless, allocation-free, and uses only three
	 * wave evaluations regardless of hull size.
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Boat",
		meta = (
			DisplayName = "Apply Gentle Boat Wave Forces",
			ReturnDisplayName = "Applied",
			Keywords = "boat buoyancy waves heave drift roll pitch force physics",
			AdvancedDisplay = "FrequencySpread,WaveDirection,DirectionSpreadDegrees,WavelengthCm,HullHalfLengthYcm,HullHalfWidthXcm,RockingStrength,DriftDirection,DriftAcceleration,DriftFrequencyHz,HorizontalDamping,VerticalDamping,AngularDamping,YawAccelerationDegrees,Seed,TimeScale,PhaseOffsetSeconds,BoneName"))
	static bool ApplyBoatWaveForces(
		UPrimitiveComponent* Target,
		float Strength = 1.0f,
		float HeaveAcceleration = 25.0f,
		float WaveFrequencyHz = 0.22f,
		float FrequencySpread = 0.28f,
		FVector2D WaveDirection = FVector2D(1.0f, 0.0f),
		float DirectionSpreadDegrees = 25.0f,
		float WavelengthCm = 1200.0f,
		float HullHalfLengthYcm = 220.0f,
		float HullHalfWidthXcm = 120.0f,
		float RockingStrength = 0.65f,
		FVector2D DriftDirection = FVector2D(1.0f, 0.0f),
		float DriftAcceleration = 3.0f,
		float DriftFrequencyHz = 0.04f,
		float HorizontalDamping = 0.12f,
		float VerticalDamping = 0.04f,
		float AngularDamping = 0.25f,
		float YawAccelerationDegrees = 0.3f,
		int32 Seed = 1337,
		float TimeScale = 1.0f,
		float PhaseOffsetSeconds = 0.0f,
		FName BoneName = NAME_None);
};
