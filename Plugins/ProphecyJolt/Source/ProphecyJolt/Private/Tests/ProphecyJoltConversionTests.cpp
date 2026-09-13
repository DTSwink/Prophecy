#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "ProphecyJoltConversions.h"

namespace ProphecyJolt::ConversionTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
constexpr float VectorTolerance = 1.0e-5f;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBasisAndRotationTest, "Prophecy.Jolt.Conversions.BasisAndRotations", ProphecyJolt::ConversionTests::Flags)

bool FProphecyJoltBasisAndRotationTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyJolt::Conversions;
	using namespace ProphecyJolt::ConversionTests;

	const FVector Axes[] = { FVector(1, 0, 0), FVector(0, 1, 0), FVector(0, 0, 1) };
	const FVector RotationInputs[] = { FVector(0, 1, 0), FVector(0, 0, 1), FVector(1, 0, 0) };
	const FVector PositiveRotationOutputs[] = { FVector(0, 0, 1), FVector(1, 0, 0), FVector(0, 1, 0) };
	for (int32 AxisIndex = 0; AxisIndex < 3; ++AxisIndex)
	{
		for (const double Sign : { -1.0, 1.0 })
		{
			const FString Label = FString::Printf(TEXT("Axis %d, sign %.0f"), AxisIndex, Sign);
			const FVector SignedAxis = Axes[AxisIndex] * Sign;
			const JPH::Vec3 JoltAxis = ToJoltDirection(SignedAxis);
			TestNearlyEqual(Label + TEXT(" numeric direction"), FVector(JoltAxis.GetX(), JoltAxis.GetY(), JoltAxis.GetZ()), SignedAxis, VectorTolerance);
			TestNearlyEqual(Label + TEXT(" direction round trip"), FromJoltDirection(JoltAxis), SignedAxis, VectorTolerance);

			const FQuat UnrealRotation(Axes[AxisIndex], Sign * UE_DOUBLE_HALF_PI);
			const FVector Expected = PositiveRotationOutputs[AxisIndex] * Sign;
			TestNearlyEqual(Label + TEXT(" UE axis-angle rotation"), UnrealRotation.RotateVector(RotationInputs[AxisIndex]), Expected, VectorTolerance);
			const JPH::Quat JoltRotation = ToJoltRotation(UnrealRotation);
			TestNearlyEqual(Label + TEXT(" Jolt axis-angle rotation"), FromJoltDirection(JoltRotation * ToJoltDirection(RotationInputs[AxisIndex])), Expected, VectorTolerance);
			TestNearlyEqual(Label + TEXT(" quaternion round trip"), FromJoltRotation(JoltRotation).RotateVector(RotationInputs[AxisIndex]), Expected, VectorTolerance);
		}
	}

	// UE's Euler pitch/roll signs are not inferred from Jolt's axis-angle names.
	const FRotator EulerRotations[] = { FRotator(0, 90, 0), FRotator(90, 0, 0), FRotator(0, 0, 90) };
	const FVector EulerInputs[] = { FVector(1, 0, 0), FVector(1, 0, 0), FVector(0, 1, 0) };
	const FVector EulerExpected[] = { FVector(0, 1, 0), FVector(0, 0, 1), FVector(0, 0, -1) };
	for (int32 Index = 0; Index < 3; ++Index)
	{
		const FQuat UnrealRotation = EulerRotations[Index].Quaternion();
		TestNearlyEqual(FString::Printf(TEXT("Positive UE Euler %d"), Index), UnrealRotation.RotateVector(EulerInputs[Index]), EulerExpected[Index], VectorTolerance);
		TestNearlyEqual(FString::Printf(TEXT("Converted positive UE Euler %d"), Index), FromJoltDirection(ToJoltRotation(UnrealRotation) * ToJoltDirection(EulerInputs[Index])), EulerExpected[Index], VectorTolerance);
	}

	const FQuat CompoundRotation = FRotator(31, -47, 19).Quaternion();
	const FVector ArbitraryDirection(0.25, -0.5, 0.75);
	TestNearlyEqual(TEXT("Compound rotation preserves vector action"), FromJoltDirection(ToJoltRotation(CompoundRotation) * ToJoltDirection(ArbitraryDirection)), CompoundRotation.RotateVector(ArbitraryDirection), VectorTolerance);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltDimensionsTest, "Prophecy.Jolt.Conversions.Dimensions", ProphecyJolt::ConversionTests::Flags)

bool FProphecyJoltDimensionsTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyJolt::Conversions;
	using namespace ProphecyJolt::ConversionTests;

	const FVector PositionCm(125.0, -250.0, 375.0);
	const JPH::RVec3 PositionM = ToJoltPosition(PositionCm);
	TestNearlyEqual(TEXT("Position centimeters to meters"), FVector(PositionM.GetX(), PositionM.GetY(), PositionM.GetZ()), FVector(1.25, -2.5, 3.75), VectorTolerance);
	TestNearlyEqual(TEXT("Position round trip"), FromJoltPosition(PositionM), PositionCm, VectorTolerance);
	const FVector LargePositionCm(1000000123.125, -2000000456.25, 3000000789.5);
	TestNearlyEqual(TEXT("World positions retain sub-centimeter precision"), FromJoltPosition(ToJoltPosition(LargePositionCm)), LargePositionCm, VectorTolerance);

	const FVector LinearUE(100.0, -200.0, 300.0);
	const FVector LinearSI(1.0, -2.0, 3.0);
	TestNearlyEqual(TEXT("Linear velocity scale"), FromJoltDirection(ToJoltLinearVelocity(LinearUE)), LinearSI, VectorTolerance);
	TestNearlyEqual(TEXT("Linear velocity round trip"), FromJoltLinearVelocity(ToJoltLinearVelocity(LinearUE)), LinearUE, VectorTolerance);
	TestNearlyEqual(TEXT("Force scale"), FromJoltDirection(ToJoltForce(LinearUE)), LinearSI, VectorTolerance);
	TestNearlyEqual(TEXT("Force round trip"), FromJoltForce(ToJoltForce(LinearUE)), LinearUE, VectorTolerance);
	TestNearlyEqual(TEXT("Linear impulse scale"), FromJoltDirection(ToJoltLinearImpulse(LinearUE)), LinearSI, VectorTolerance);
	TestNearlyEqual(TEXT("Linear impulse round trip"), FromJoltLinearImpulse(ToJoltLinearImpulse(LinearUE)), LinearUE, VectorTolerance);

	const FVector SquaredUE(10000.0, -20000.0, 30000.0);
	const FVector SquaredSI(1.0, -2.0, 3.0);
	TestNearlyEqual(TEXT("Torque scale"), FromJoltDirection(ToJoltTorque(SquaredUE)), SquaredSI, VectorTolerance);
	TestNearlyEqual(TEXT("Torque round trip"), FromJoltTorque(ToJoltTorque(SquaredUE)), SquaredUE, VectorTolerance);
	TestNearlyEqual(TEXT("Angular impulse scale"), FromJoltDirection(ToJoltAngularImpulse(SquaredUE)), SquaredSI, VectorTolerance);
	TestNearlyEqual(TEXT("Angular impulse round trip"), FromJoltAngularImpulse(ToJoltAngularImpulse(SquaredUE)), SquaredUE, VectorTolerance);
	const FVector InertiaUE(10000.0, 20000.0, 30000.0);
	TestNearlyEqual(TEXT("Principal inertia scale"), FromJoltDirection(ToJoltInertiaDiagonal(InertiaUE)), FVector(1, 2, 3), VectorTolerance);
	TestNearlyEqual(TEXT("Principal inertia round trip"), FromJoltInertiaDiagonal(ToJoltInertiaDiagonal(InertiaUE)), InertiaUE, VectorTolerance);

	const FVector AngularVelocity(0.5, -1.25, 2.0);
	TestNearlyEqual(TEXT("Angular velocity stays in radians per second"), FromJoltDirection(ToJoltAngularVelocity(AngularVelocity)), AngularVelocity, VectorTolerance);
	TestNearlyEqual(TEXT("Angular velocity round trip"), FromJoltAngularVelocity(ToJoltAngularVelocity(AngularVelocity)), AngularVelocity, VectorTolerance);
	TestNearlyEqual(TEXT("Mass stays in kilograms"), static_cast<double>(ToJoltMass(90.0)), 90.0);
	TestNearlyEqual(TEXT("Mass round trip"), FromJoltMass(ToJoltMass(90.0)), 90.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPointVelocityAndImpulseTest, "Prophecy.Jolt.Conversions.PointVelocityAndImpulse", ProphecyJolt::ConversionTests::Flags)

bool FProphecyJoltPointVelocityAndImpulseTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyJolt::Conversions;
	using namespace ProphecyJolt::ConversionTests;

	const FVector CenterOfMassCm(1000000000.0, -2000000000.0, 3000000000.0);
	const FVector OffsetCm(100.0, 0.0, 0.0);
	const FVector VelocityCmPerSecond(100.0, 200.0, 300.0);
	const FVector AngularVelocityRadians(0.0, 0.0, 2.0);
	const JPH::Vec3 PointVelocity = GetJoltPointVelocity(ToJoltLinearVelocity(VelocityCmPerSecond), ToJoltAngularVelocity(AngularVelocityRadians), ToJoltPosition(CenterOfMassCm), ToJoltPosition(CenterOfMassCm + OffsetCm));
	TestNearlyEqual(TEXT("COM translation plus angular point velocity"), FromJoltLinearVelocity(PointVelocity), FVector(100.0, 400.0, 300.0), VectorTolerance);
	TestNearlyEqual(TEXT("Point velocity agrees with UE cross product"), FromJoltLinearVelocity(PointVelocity), VelocityCmPerSecond + FVector::CrossProduct(AngularVelocityRadians, OffsetCm), VectorTolerance);
	const JPH::Vec3 OppositePointVelocity = GetJoltPointVelocity(ToJoltLinearVelocity(VelocityCmPerSecond), ToJoltAngularVelocity(AngularVelocityRadians), ToJoltPosition(CenterOfMassCm), ToJoltPosition(CenterOfMassCm - OffsetCm));
	TestNearlyEqual(TEXT("Opposite lever arm reverses angular contribution"), FromJoltLinearVelocity(OppositePointVelocity), FVector(100.0, 0.0, 300.0), VectorTolerance);

	// One meter along +X, impulse of 2 N*s along +Y: +2 N*m*s about Z.
	const FVector LinearImpulseUE(0.0, 200.0, 0.0);
	const JPH::Vec3 LeverArmM = static_cast<JPH::Vec3>(ToJoltPosition(CenterOfMassCm + OffsetCm) - ToJoltPosition(CenterOfMassCm));
	const JPH::Vec3 AngularImpulse = LeverArmM.Cross(ToJoltLinearImpulse(LinearImpulseUE));
	TestNearlyEqual(TEXT("Off-center impulse sign and SI magnitude"), FromJoltDirection(AngularImpulse), FVector(0.0, 0.0, 2.0), VectorTolerance);
	TestNearlyEqual(TEXT("Off-center impulse agrees with UE dimensions"), FromJoltAngularImpulse(AngularImpulse), FVector::CrossProduct(OffsetCm, LinearImpulseUE), VectorTolerance);
	const JPH::Vec3 Torque = LeverArmM.Cross(ToJoltForce(FVector(0.0, 200.0, 0.0)));
	TestNearlyEqual(TEXT("Off-center force sign and torque units"), FromJoltTorque(Torque), FVector(0.0, 0.0, 20000.0), VectorTolerance);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
