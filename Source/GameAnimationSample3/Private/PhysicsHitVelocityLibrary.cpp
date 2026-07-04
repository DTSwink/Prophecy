#include "PhysicsHitVelocityLibrary.h"

#include "Components/PrimitiveComponent.h"
#include "PhysicsEngine/BodyInstance.h"

namespace
{
constexpr double MinMassKg = 1.0e-6;
constexpr double MinInertia = 1.0e-6;

bool HasUsableInertia(const FVector& InertiaTensor)
{
	return InertiaTensor.X > MinInertia
		&& InertiaTensor.Y > MinInertia
		&& InertiaTensor.Z > MinInertia;
}

FVector DivideByInertiaTensor(const FVector& LocalAngularImpulse, const FVector& InertiaTensor)
{
	return FVector(
		LocalAngularImpulse.X / InertiaTensor.X,
		LocalAngularImpulse.Y / InertiaTensor.Y,
		LocalAngularImpulse.Z / InertiaTensor.Z);
}
}

FPreHitVelAngVelResult UPhysicsHitVelocityLibrary::RetrieveVelAngVel(
	UPrimitiveComponent* Sword,
	FVector ImpactLocation,
	FVector NormalImpulseOnSword,
	FName BoneName)
{
	FPreHitVelAngVelResult Result;
	if (!Sword)
	{
		return Result;
	}

	Result.FinalLinearVelocity = Sword->GetPhysicsLinearVelocity(BoneName);
	Result.FinalAngularVelocityRad = Sword->GetPhysicsAngularVelocityInRadians(BoneName);

	FBodyInstance* BodyInstance = Sword->GetBodyInstance(BoneName);
	if (!BodyInstance)
	{
		Result.PreLinearVelocity = Result.FinalLinearVelocity;
		Result.PreAngularVelocityRad = Result.FinalAngularVelocityRad;
		Result.PrePointVelocity = Result.PreLinearVelocity;
		return Result;
	}

	const double MassKg = static_cast<double>(BodyInstance->GetBodyMass());
	const FVector InertiaTensor = BodyInstance->GetBodyInertiaTensor();
	if (MassKg <= MinMassKg || !HasUsableInertia(InertiaTensor))
	{
		Result.PreLinearVelocity = Result.FinalLinearVelocity;
		Result.PreAngularVelocityRad = Result.FinalAngularVelocityRad;
		Result.PrePointVelocity = Result.PreLinearVelocity;
		return Result;
	}

	const FVector CenterOfMass = BodyInstance->GetCOMPosition();
	const FVector ImpactOffsetFromCOM = ImpactLocation - CenterOfMass;
	const FVector AngularImpulseWorld = FVector::CrossProduct(ImpactOffsetFromCOM, NormalImpulseOnSword);

	const FTransform BodyTransform = BodyInstance->GetUnrealWorldTransform(false);
	const FVector AngularImpulseLocal = BodyTransform.InverseTransformVectorNoScale(AngularImpulseWorld);
	const FVector DeltaAngularLocal = DivideByInertiaTensor(AngularImpulseLocal, InertiaTensor);

	Result.DeltaLinearVelocity = NormalImpulseOnSword / MassKg;
	Result.DeltaAngularVelocityRad = BodyTransform.TransformVectorNoScale(DeltaAngularLocal);

	Result.PreLinearVelocity = Result.FinalLinearVelocity - Result.DeltaLinearVelocity;
	Result.PreAngularVelocityRad = Result.FinalAngularVelocityRad - Result.DeltaAngularVelocityRad;
	Result.PrePointVelocity = Result.PreLinearVelocity + FVector::CrossProduct(Result.PreAngularVelocityRad, ImpactOffsetFromCOM);
	Result.bSuccess = true;
	return Result;
}
