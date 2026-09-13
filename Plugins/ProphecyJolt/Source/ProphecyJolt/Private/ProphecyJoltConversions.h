#pragma once

#include "CoreMinimal.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Math/Quat.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::Conversions
{
static_assert(sizeof(JPH::Real) == sizeof(double), "Prophecy requires Jolt double-precision world positions.");

inline constexpr double CentimetersToMeters = 0.01;
inline constexpr double MetersToCentimeters = 100.0;
inline constexpr double SquareCentimetersToSquareMeters = 0.0001;
inline constexpr double SquareMetersToSquareCentimeters = 10000.0;

// Numeric basis is unchanged: +X forward, +Y right, +Z up. World up/gravity
// and shape-local axes are separate configuration. This is not the NN basis.
namespace Detail
{
inline JPH::Vec3 ToScaledVector(const FVector& Value, double Scale)
{
	return JPH::Vec3(static_cast<float>(Value.X * Scale), static_cast<float>(Value.Y * Scale), static_cast<float>(Value.Z * Scale));
}

inline FVector FromScaledVector(JPH::Vec3Arg Value, double Scale)
{
	return FVector(Value.GetX(), Value.GetY(), Value.GetZ()) * Scale;
}
}

inline JPH::RVec3 ToJoltPosition(const FVector& Centimeters)
{
	return JPH::RVec3(Centimeters.X * CentimetersToMeters, Centimeters.Y * CentimetersToMeters, Centimeters.Z * CentimetersToMeters);
}

inline FVector FromJoltPosition(JPH::RVec3Arg Meters)
{
	return FVector(Meters.GetX() * MetersToCentimeters, Meters.GetY() * MetersToCentimeters, Meters.GetZ() * MetersToCentimeters);
}

inline JPH::Vec3 ToJoltDirection(const FVector& Direction)
{
	return Detail::ToScaledVector(Direction, 1.0);
}

inline FVector FromJoltDirection(JPH::Vec3Arg Direction)
{
	return Detail::FromScaledVector(Direction, 1.0);
}

inline JPH::Quat ToJoltRotation(const FQuat& Rotation)
{
	// Preserve quaternion components; do not silently normalize an invalid input.
	checkSlow(Rotation.IsNormalized());
	return JPH::Quat(static_cast<float>(Rotation.X), static_cast<float>(Rotation.Y), static_cast<float>(Rotation.Z), static_cast<float>(Rotation.W));
}

inline FQuat FromJoltRotation(JPH::QuatArg Rotation)
{
	return FQuat(Rotation.GetX(), Rotation.GetY(), Rotation.GetZ(), Rotation.GetW());
}

// These velocities refer to the same point in both APIs. Body velocity in
// Jolt is COM velocity; converting units does not move it to a body origin.
inline JPH::Vec3 ToJoltLinearVelocity(const FVector& CentimetersPerSecond)
{
	return Detail::ToScaledVector(CentimetersPerSecond, CentimetersToMeters);
}

inline FVector FromJoltLinearVelocity(JPH::Vec3Arg MetersPerSecond)
{
	return Detail::FromScaledVector(MetersPerSecond, MetersToCentimeters);
}

inline JPH::Vec3 ToJoltAngularVelocity(const FVector& RadiansPerSecond)
{
	return Detail::ToScaledVector(RadiansPerSecond, 1.0);
}

inline FVector FromJoltAngularVelocity(JPH::Vec3Arg RadiansPerSecond)
{
	return Detail::FromScaledVector(RadiansPerSecond, 1.0);
}

// Force/torque inputs are physical quantities, not UE acceleration-change
// calls. Those calls need mass/world-inertia application at their call site.
inline JPH::Vec3 ToJoltForce(const FVector& KilogramCentimetersPerSecondSquared)
{
	return Detail::ToScaledVector(KilogramCentimetersPerSecondSquared, CentimetersToMeters);
}

inline FVector FromJoltForce(JPH::Vec3Arg Newtons)
{
	return Detail::FromScaledVector(Newtons, MetersToCentimeters);
}

inline JPH::Vec3 ToJoltLinearImpulse(const FVector& KilogramCentimetersPerSecond)
{
	return Detail::ToScaledVector(KilogramCentimetersPerSecond, CentimetersToMeters);
}

inline FVector FromJoltLinearImpulse(JPH::Vec3Arg NewtonSeconds)
{
	return Detail::FromScaledVector(NewtonSeconds, MetersToCentimeters);
}

inline JPH::Vec3 ToJoltTorque(const FVector& KilogramSquareCentimetersPerSecondSquared)
{
	return Detail::ToScaledVector(KilogramSquareCentimetersPerSecondSquared, SquareCentimetersToSquareMeters);
}

inline FVector FromJoltTorque(JPH::Vec3Arg NewtonMeters)
{
	return Detail::FromScaledVector(NewtonMeters, SquareMetersToSquareCentimeters);
}

inline JPH::Vec3 ToJoltAngularImpulse(const FVector& KilogramSquareCentimetersPerSecond)
{
	return Detail::ToScaledVector(KilogramSquareCentimetersPerSecond, SquareCentimetersToSquareMeters);
}

inline FVector FromJoltAngularImpulse(JPH::Vec3Arg NewtonMeterSeconds)
{
	return Detail::FromScaledVector(NewtonMeterSeconds, SquareMetersToSquareCentimeters);
}

// Principal moments in the same mass frame, not a general tensor transform.
inline JPH::Vec3 ToJoltInertiaDiagonal(const FVector& KilogramSquareCentimeters)
{
	return Detail::ToScaledVector(KilogramSquareCentimeters, SquareCentimetersToSquareMeters);
}

inline FVector FromJoltInertiaDiagonal(JPH::Vec3Arg KilogramSquareMeters)
{
	return Detail::FromScaledVector(KilogramSquareMeters, SquareMetersToSquareCentimeters);
}

inline float ToJoltMass(double Kilograms)
{
	return static_cast<float>(Kilograms);
}

inline double FromJoltMass(float Kilograms)
{
	return static_cast<double>(Kilograms);
}

inline JPH::Vec3 GetJoltPointVelocity(JPH::Vec3Arg CenterOfMassVelocity, JPH::Vec3Arg AngularVelocity,
	JPH::RVec3Arg CenterOfMassPosition, JPH::RVec3Arg PointPosition)
{
	// Subtract in world precision before narrowing the local lever arm.
	const JPH::Vec3 Offset = static_cast<JPH::Vec3>(PointPosition - CenterOfMassPosition);
	return CenterOfMassVelocity + AngularVelocity.Cross(Offset);
}
}
