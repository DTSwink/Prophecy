#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "PhysicsEngine/SphylElem.h"
#include "ProphecyJoltRig.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltScaledCapsuleTest,
    "Prophecy.Jolt.Rig.ScaledCapsuleGeometryAndCOM",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltScaledCapsuleTest::RunTest(const FString& Parameters)
{
    // A displaced, rotated capsule exposes missing center scaling, radius/total-height confusion,
    // a missing native Y-to-UE-Z conversion, and accidental reapplication of BuildScale or COM scale.
    FKSphylElem Authored(15.0f, 80.0f);
    Authored.Center = FVector(30.0, -40.0, 70.0);
    Authored.Rotation = FQuat(FVector(0.0, 1.0, 0.0), UE_DOUBLE_HALF_PI).Rotator();
    const FVector BodyScale(0.8);
    const FKSphylElem Scaled = Authored.GetFinalScaled(BodyScale, FTransform::Identity);
    constexpr float ToleranceCm = 2.0e-3f;
    TestNearlyEqual(TEXT("Uniform scale retains authored radius ratio"), Scaled.Radius, 12.0f, 1.0e-5f);
    TestNearlyEqual(TEXT("Straight cylinder length excludes both scaled caps"), Scaled.Length, 64.0f, 1.0e-5f);
    TestNearlyEqual(TEXT("Body-local center receives live body scale once"), Scaled.Center,
        FVector(24.0, -32.0, 56.0), ToleranceCm);
    TestNearlyEqual(TEXT("Positive uniform scale retains the authored local capsule axis"),
        Scaled.Rotation.RotateVector(FVector(0.0, 0.0, 1.0)), FVector(1.0, 0.0, 0.0), 1.0e-5f);
    TestNearlyEqual(TEXT("Source AggGeom is unchanged by GetFinalScaled"), Authored.Center,
        FVector(30.0, -40.0, 70.0), 1.0e-8f);

    FProphecyJoltRigSnapshot Snapshot;
    Snapshot.CaptureId = FGuid::NewGuid();
    FProphecyJoltRigBody& Body = Snapshot.Bodies.AddDefaulted_GetRef();
    Body.SourceBodyIndex = 0;
    Body.BoneIndex = 0;
    Body.BodyName = TEXT("ScaledCapsuleFixture");
    Body.SourceBodyScale3D = BodyScale;
    // Provenance only: the incoming AggGeom already contains any earlier build-scale application.
    Body.SourceBuildScale3D = FVector(2.0);
    Body.MassFrameToBodyOrigin = FTransform(FQuat::Identity, FVector(5.0, -3.0, 2.0));
    Body.MassKg = 2.0;
    Body.PrincipalInertiaKgCmSquared = FVector(1000.0);
    Body.MaxLinearVelocityCmPerSecond = 10000.0;
    Body.MaxAngularVelocityRadiansPerSecond = 100.0;
    FProphecyJoltRigShape& Shape = Body.Shapes.AddDefaulted_GetRef();
    Shape.Kind = EProphecyJoltRigShape::Capsule;
    Shape.SourceElementIndex = 0;
    Shape.AuthoredLocalToBodyOrigin = Authored.GetTransform();
    Shape.AuthoredRadiusCm = Authored.Radius;
    Shape.AuthoredCapsuleCylinderLengthCm = Authored.Length;
    Shape.LocalToBodyOrigin = Scaled.GetTransform();
    Shape.RadiusCm = Scaled.Radius;
    Shape.CapsuleCylinderLengthCm = Scaled.Length;
    Shape.CurrentCollisionEnabled = ECollisionEnabled::QueryAndPhysics;

    const int32 LivePreparedBefore = FProphecyJoltPreparedRig::GetLivePreparedRigCount();
    FProphecyJoltPreparedRig Prepared;
    FString Error;
    if (!TestTrue(TEXT("Scaled geometry prepares through the runtime rig path: ") + Error,
        Prepared.Build(Snapshot, Error)))
    {
        AddError(Error);
        return false;
    }
    FVector COM;
    FBox Bounds(ForceInit);
    if (!TestTrue(TEXT("Prepared geometry can be inspected"), Prepared.GetBodyGeometrySummary(0, COM, Bounds, Error)))
    {
        AddError(Error);
        return false;
    }
    TestNearlyEqual(TEXT("Captured COM is already in physical cm and is not scaled again"), COM,
        FVector(5.0, -3.0, 2.0), ToleranceCm);
    TestNearlyEqual(TEXT("Prepared collider retains the scaled body-local center"), Bounds.GetCenter(),
        FVector(24.0, -32.0, 56.0), ToleranceCm);
    TestNearlyEqual(TEXT("Rotated total half-height is 32 + 12 cm; build scale is not reapplied"), Bounds.GetExtent(),
        FVector(44.0, 12.0, 12.0), ToleranceCm);
    Prepared.Reset();
    TestEqual(TEXT("Preparing scaled geometry releases its native state"),
        FProphecyJoltPreparedRig::GetLivePreparedRigCount(), LivePreparedBefore);

    // This is UE initial-cooking behavior, including its 0.1 cm straight-length floor. It is not
    // a custom Jolt radius/length retune, nor a claim about later UpdateBodyScale geometry mutations.
    const FKSphylElem ZeroCylinder(10.0f, 0.0f);
    const FKSphylElem ScaledZero = ZeroCylinder.GetFinalScaled(FVector(0.5), FTransform::Identity);
    TestNearlyEqual(TEXT("UE scales the zero-cylinder capsule radius"), ScaledZero.Radius, 5.0f, 1.0e-6f);
    TestNearlyEqual(TEXT("UE initial cooking supplies its own minimum cylinder length"), ScaledZero.Length, 0.1f, 1.0e-6f);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
