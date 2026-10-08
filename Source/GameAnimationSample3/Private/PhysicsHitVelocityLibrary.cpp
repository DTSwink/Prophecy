#include "PhysicsHitVelocityLibrary.h"
#include <limits>

#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "PhysicsEngine/BodyInstance.h"
#include "ProphecyHitTrajectory.inl"

bool UPhysicsHitVelocityLibrary::ComputeCatchUp(FVector VictimLocation, FVector VictimVelocity,
    FVector AttackerLocation, double AttackerSpeed, double& Duration, FVector& OptimalAttackerVelocity)
{
    Duration=10000.;
    OptimalAttackerVelocity=FVector::ZeroVector;
    if (VictimLocation.ContainsNaN() || VictimVelocity.ContainsNaN() || AttackerLocation.ContainsNaN()
        || !FMath::IsFinite(AttackerSpeed) || AttackerSpeed<0.) return false;
    const FVector R=VictimLocation-AttackerLocation;
    const double C=R.SizeSquared();
    if (!FMath::IsFinite(C)) return false;
    if (C==0.) { Duration=0.;return true; }
    // Only compute pursuit on failure; successful interception keeps its original cost.
    const auto Pursue=[&]()
    {
        OptimalAttackerVelocity=(R/FMath::Sqrt(C))*AttackerSpeed;
        return false;
    };

    // |R + V*t|^2 = speed^2*t^2. Use half the linear coefficient.
    const double A=VictimVelocity.SizeSquared()-AttackerSpeed*AttackerSpeed;
    const double B=FVector::DotProduct(R,VictimVelocity);
    if (!FMath::IsFinite(A) || !FMath::IsFinite(B)) return false;
    if (A>=0. && B>=0.) return Pursue();
    double T;
    if (A==0.) T=-C/(2.*B); // Equal speeds: the quadratic reduces to a line.
    else
    {
        const double BB=B*B,AC=A*C;
        double D=BB-AC;
        if (!FMath::IsFinite(D)) return false;
        // Admit exact tangency affected only by double-precision roundoff.
        if (D<0.)
        {
            if (D < -8.*std::numeric_limits<double>::epsilon()*FMath::Max(BB,FMath::Abs(AC))) return Pursue();
            D=0.;
        }
        const double Root=FMath::Sqrt(D);
        // Earliest positive root, rationalized to avoid catastrophic cancellation.
        T=B<0. ? C/(Root-B) : (Root+B)/(-A);
    }
    if (!FMath::IsFinite(T) || T<=0.) return false;
    const FVector Velocity=VictimVelocity+R/T;
    if (Velocity.ContainsNaN()) return false;
    Duration=T;
    OptimalAttackerVelocity=Velocity;
    return true;
}

FVector UPhysicsHitVelocityLibrary::GetHitTrajectory(
    const UObject* WorldContextObject,FVector StartLocation,FVector CurrentTargetLocation,
    FVector CurrentTargetSpeed,float Angle,bool& ExactHit,float& FlightTime,float& MissDistance,
    float MaxLaunchSpeed,float MaxFlightTime,float GravityScale)
{
    const UWorld* World=WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
    const double GravityZ=World ? World->GetGravityZ() : -980.;
    const auto Result=ProphecyHitTrajectory::Solve(CurrentTargetLocation-StartLocation,
        CurrentTargetSpeed,Angle,GravityZ*GravityScale,MaxLaunchSpeed,MaxFlightTime);
    ExactHit=Result.Exact;FlightTime=static_cast<float>(Result.Time);MissDistance=static_cast<float>(Result.Miss);
    return Result.Velocity;
}

namespace
{
constexpr double MinMassKg = 1.0e-6;
constexpr double MinInertia = 1.0e-6;
constexpr float MinSpringDeltaSeconds = 1.0e-6f;

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

float ResolveSpringDeltaSeconds(const UObject* WorldContextObject, float DeltaSeconds)
{
	if (DeltaSeconds > MinSpringDeltaSeconds)
	{
		return DeltaSeconds;
	}

	const UWorld* World = WorldContextObject ? WorldContextObject->GetWorld() : nullptr;
	return World ? FMath::Max(World->GetDeltaSeconds(), MinSpringDeltaSeconds) : MinSpringDeltaSeconds;
}

FVector RotationVectorFromTo(const FQuat& FromRotation, const FQuat& ToRotation)
{
	FQuat Delta = ToRotation * FromRotation.Inverse();
	Delta.Normalize();

	if (Delta.W < 0.0)
	{
		Delta.X *= -1.0;
		Delta.Y *= -1.0;
		Delta.Z *= -1.0;
		Delta.W *= -1.0;
	}

	FVector Axis = FVector::ForwardVector;
	double Angle = 0.0;
	Delta.ToAxisAndAngle(Axis, Angle);

	Angle = FMath::UnwindRadians(Angle);
	if (FMath::Abs(Angle) <= KINDA_SMALL_NUMBER || Axis.IsNearlyZero())
	{
		return FVector::ZeroVector;
	}

	return Axis.GetSafeNormal() * Angle;
}

FVector ApplyDeltaVelocityLimits(const FVector& DeltaVelocity, float MaxMagnitude, float Tolerance)
{
	const float SafeTolerance = FMath::Max(0.0f, Tolerance);
	const float SizeSquared = DeltaVelocity.SizeSquared();
	if (SafeTolerance > 0.0f && SizeSquared <= FMath::Square(SafeTolerance))
	{
		return FVector::ZeroVector;
	}

	const float SafeMaxMagnitude = FMath::Max(0.0f, MaxMagnitude);
	if (SafeMaxMagnitude > 0.0f && SizeSquared > FMath::Square(SafeMaxMagnitude))
	{
		return DeltaVelocity.GetClampedToMaxSize(SafeMaxMagnitude);
	}

	return DeltaVelocity;
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

FVector UPhysicsHitVelocityLibrary::spring_cpp(
	const UObject* WorldContextObject,
	FVector Position,
	FVector Velocity,
	FVector TargetPosition,
	float DVelMax,
	float Tolerance,
	float DeltaSeconds)
{
	const float SafeDeltaSeconds = ResolveSpringDeltaSeconds(WorldContextObject, DeltaSeconds);
	const FVector DesiredVelocity = (TargetPosition - Position) / SafeDeltaSeconds;
	// The Blueprint adds this return value to the body's current velocity.
	// Therefore the one-step endpoint correction is Desired - Current exactly
	// once. Subtracting Current a second time makes the resulting body velocity
	// Desired - Current and produces alternating overshoot/lag.
	const FVector DeltaVelocity = DesiredVelocity - Velocity;
	return ApplyDeltaVelocityLimits(DeltaVelocity, DVelMax, Tolerance);
}

FVector UPhysicsHitVelocityLibrary::angspring_cpp(
	const UObject* WorldContextObject,
	FRotator Rotation,
	FVector AngularVelocityRad,
	FRotator TargetRotation,
	float DAngVelMax,
	float Tolerance,
	float DeltaSeconds)
{
	const float SafeDeltaSeconds = ResolveSpringDeltaSeconds(WorldContextObject, DeltaSeconds);
	const FVector RotationErrorRad = RotationVectorFromTo(Rotation.Quaternion(), TargetRotation.Quaternion());
	const FVector DesiredAngularVelocityRad = RotationErrorRad / SafeDeltaSeconds;
	const FVector DeltaAngularVelocityRad = DesiredAngularVelocityRad - AngularVelocityRad;
	return ApplyDeltaVelocityLimits(DeltaAngularVelocityRad, DAngVelMax, Tolerance);
}

#include "ProphecyHitTrajectoryTests.inl"
#include "ProphecyCatchUpTests.inl"
