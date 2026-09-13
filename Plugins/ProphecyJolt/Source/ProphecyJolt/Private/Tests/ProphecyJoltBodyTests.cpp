#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "ProphecyJoltBody.h"
#include "ProphecyJoltBodyConversion.h"
#include "ProphecyJoltConversions.h"
#include "Chaos/Box.h"
#include "Chaos/Capsule.h"
#include "Chaos/Convex.h"
#include "Chaos/ImplicitObjectScaled.h"
#include "Chaos/ImplicitObjectTransformed.h"
#include "Chaos/Sphere.h"
#include "Misc/AutomationTest.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/RayCast.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::BodyTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
constexpr float ToleranceCm = 2.0e-3f;

FProphecyJoltBodySnapshot MakeSnapshot(const FProphecyJoltRigShape& Shape)
{
    FProphecyJoltBodySnapshot Snapshot;
    Snapshot.CaptureId = FGuid::NewGuid();
    Snapshot.Body.bSimulating = true;
    Snapshot.Body.bCCD = true; // Capture/preparation preserves this input; world creation selects motion quality.
    Snapshot.Body.MassKg = 2.0;
    Snapshot.Body.PrincipalInertiaKgCmSquared = FVector(200.0, 500.0, 650.0);
    Snapshot.Body.MassFrameToBodyOrigin = FTransform(FRotator(17.0, -31.0, 23.0), FVector(-4.0, 8.0, 3.0));
    Snapshot.Body.BodyOriginToWorld = FTransform(FRotator(13.0, 7.0, -9.0), FVector(1000.0, -500.0, 80.0));
    Snapshot.Body.MaxLinearVelocityCmPerSecond = 10000.0;
    Snapshot.Body.MaxAngularVelocityRadiansPerSecond = 100.0;
    Snapshot.Body.CenterOfMassVelocityCmPerSecond = FVector(17.0, -23.0, 11.0);
    Snapshot.Body.AngularVelocityRadiansPerSecond = FVector(0.2, -0.5, 0.7);
    // Geometry already contains native scale decisions. These deliberately different source scales
    // expose any accidental second application during shape/mass preparation.
    Snapshot.Body.SourceBodyScale3D = FVector(4.0, 5.0, 6.0);
    Snapshot.Body.SourceBuildScale3D = FVector(3.0, 7.0, 2.0);
    Snapshot.Body.Shapes.Add(Shape);
    return Snapshot;
}

FProphecyJoltRigShape ShapeIdentity(EProphecyJoltRigShape Kind)
{
    FProphecyJoltRigShape Shape;
    Shape.Kind = Kind;
    Shape.SourceElementIndex = 0;
    Shape.CurrentCollisionEnabled = ECollisionEnabled::QueryAndPhysics;
    return Shape;
}

Chaos::FConvexPtr Tetrahedron()
{
    TArray<Chaos::FConvex::FVec3Type> Points;
    Points.Emplace(0.0f, 0.0f, 0.0f);
    Points.Emplace(20.0f, 0.0f, 0.0f);
    Points.Emplace(0.0f, 20.0f, 0.0f);
    Points.Emplace(0.0f, 0.0f, 20.0f);
    // Interior input points must disappear through native cooking, not become purported hull vertices.
    Points.Emplace(2.0f, 2.0f, 2.0f);
    return Chaos::FConvexPtr(new Chaos::FConvex(Points, 0.0));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBodyConvexTest,
    "Prophecy.Jolt.Body.CookedConvexWrappersAndMass", ProphecyJolt::BodyTests::Flags)

bool FProphecyJoltBodyConvexTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace BodyTests;
    const Chaos::FConvexPtr Hull = Tetrahedron();
    if (!TestEqual(TEXT("Native cooker retains only four hull vertices"), Hull->NumVertices(), 4)) return false;
    const FVector NativeScale(0.7, 1.3, 2.1);
    const FTransform Inner(FRotator(19.0, -37.0, 11.0), FVector(23.0, -17.0, 41.0));
    const FTransform Outer(FRotator(-13.0, 29.0, 7.0), FVector(-9.0, 31.0, 5.0));
    const Chaos::FImplicitObjectPtr Scaled = MakeImplicitObjectPtr<Chaos::TImplicitObjectScaled<Chaos::FConvex>>(Hull, Chaos::FVec3(NativeScale), 0.1);
    const Chaos::FImplicitObjectPtr Transformed = MakeImplicitObjectPtr<Chaos::FImplicitObjectTransformed>(Scaled, Chaos::FRigidTransform3(Inner));
    const Chaos::FImplicitObjectPtr Root = MakeImplicitObjectPtr<Chaos::FImplicitObjectTransformed>(Transformed, Chaos::FRigidTransform3(Outer));
    FProphecyJoltRigShape Shape = ShapeIdentity(EProphecyJoltRigShape::Convex);
    FString Error;
    if (!TestTrue(TEXT("Cooked scaled/rotated hull captures"), BodyConversion::CaptureGeometry(*Root, Shape, Error)))
    { AddError(Error); return false; }
    TestEqual(TEXT("Only cooked native vertices are captured"), Shape.ConvexVerticesCm.Num(), Hull->NumVertices());
    TestTrue(TEXT("Wrapper transforms are baked into hull positions"), Shape.LocalToBodyOrigin.Equals(FTransform::Identity));
    TestNearlyEqual(TEXT("Outer native margin is retained as provenance"), Shape.NativeCollisionMarginCm, double(Root->GetMarginf()), 1.0e-6);
    FBox ExpectedBounds(ForceInit);
    for (int32 VertexIndex = 0; VertexIndex < Hull->NumVertices(); ++VertexIndex)
    {
        const FVector Expected = Outer.TransformPosition(Inner.TransformPosition(FVector(Hull->GetVertex(VertexIndex)) * NativeScale));
        TestNearlyEqual(FString::Printf(TEXT("Cooked vertex %d has scale exactly once and correct wrapper order"), VertexIndex),
            Shape.ConvexVerticesCm[VertexIndex], Expected, ToleranceCm);
        ExpectedBounds += Expected;
    }
    const int32 PreparedBefore = FProphecyJoltPreparedBody::GetLivePreparedBodyCount();
    const FProphecyJoltBodySnapshot Snapshot = MakeSnapshot(Shape);
    FProphecyJoltPreparedBody Prepared;
    if (!TestTrue(TEXT("Standalone data prepares without skeletal identities"), Prepared.Build(Snapshot, Error)))
    { AddError(Error); return false; }
    TestEqual(TEXT("Prepared standalone lifetime is tracked"), FProphecyJoltPreparedBody::GetLivePreparedBodyCount(), PreparedBefore + 1);
    FVector COM;
    FBox Bounds(ForceInit);
    if (!TestTrue(TEXT("Prepared hull exposes body-origin geometry summary"), Prepared.GetGeometrySummary(COM, Bounds, Error))) return false;
    TestNearlyEqual(TEXT("Captured COM is not derived from the hull centroid or rescaled"), COM,
        Snapshot.Body.MassFrameToBodyOrigin.GetTranslation(), ToleranceCm);
    TestNearlyEqual(TEXT("Cooked convex bounds minimum survives preparation"), Bounds.Min, ExpectedBounds.Min, ToleranceCm);
    TestNearlyEqual(TEXT("Cooked convex bounds maximum survives preparation"), Bounds.Max, ExpectedBounds.Max, ToleranceCm);
    JPH::MassProperties Mass;
    if (!TestTrue(TEXT("Explicit captured mass tensor is available"), Prepared.GetNativeMassProperties(Mass))) return false;
    TestNearlyEqual(TEXT("Mass override is retained"), Mass.mMass, 2.0f, 1.0e-6f);
    for (int32 Axis = 0; Axis < 3; ++Axis)
    {
        FVector LocalAxis = FVector::ZeroVector;
        LocalAxis[Axis] = 1.0;
        const FVector PrincipalDirection = Snapshot.Body.MassFrameToBodyOrigin.GetRotation().RotateVector(LocalAxis);
        const JPH::Vec3 NativeDirection = Conversions::ToJoltDirection(PrincipalDirection);
        const JPH::Vec3 NativeResult = Mass.mInertia.Multiply3x3(NativeDirection);
        TestNearlyEqual(FString::Printf(TEXT("Principal inertia axis %d is rotated once and converted kg cm2 to kg m2"), Axis),
            Conversions::FromJoltDirection(NativeResult), PrincipalDirection * Snapshot.Body.PrincipalInertiaKgCmSquared[Axis] * 0.0001,
            1.0e-6f);
    }
    const auto ToBody = [&](const FVector& Point) { return Outer.TransformPosition(Inner.TransformPosition(Point * NativeScale)); };
    const auto Cast = [&](const FVector& From, const FVector& To, JPH::RayCastResult& Hit)
    {
        const FVector Start = ToBody(From), End = ToBody(To);
        const JPH::RayCast Ray(static_cast<JPH::Vec3>(Conversions::ToJoltPosition(Start - COM)),
            static_cast<JPH::Vec3>(Conversions::ToJoltPosition(End - Start)));
        return Prepared.GetNativeShape()->CastRay(Ray, JPH::SubShapeIDCreator(), Hit);
    };
    JPH::RayCastResult Hit;
    if (TestTrue(TEXT("Ray hits the real tetrahedral hull"), Cast(FVector(5.0, 5.0, 30.0), FVector(5.0, 5.0, -10.0), Hit)))
        TestNearlyEqual(TEXT("Tetrahedral face retains analytic fraction after wrapper/COM conversion"), Hit.mFraction, 0.5f, 1.0e-4f);
    JPH::RayCastResult Miss;
    TestFalse(TEXT("Ray inside hull AABB but outside tetrahedron rejects a box approximation"),
        Cast(FVector(18.0, 18.0, 30.0), FVector(18.0, 18.0, -10.0), Miss));

    // Instanced convex wrappers add no extra scale/transform, including their nonzero contact margin.
    const Chaos::FImplicitObjectPtr Instance = MakeImplicitObjectPtr<Chaos::TImplicitObjectInstanced<Chaos::FConvex>>(Hull, 0.25);
    auto InstanceShape = ShapeIdentity(EProphecyJoltRigShape::Convex);
    if (TestTrue(TEXT("Instanced cooked convex captures"), BodyConversion::CaptureGeometry(*Instance, InstanceShape, Error)))
        for (int32 VertexIndex = 0; VertexIndex < Hull->NumVertices(); ++VertexIndex)
            TestNearlyEqual(TEXT("Instance margin does not inflate cooked outer vertices"), InstanceShape.ConvexVerticesCm[VertexIndex],
                FVector(Hull->GetVertex(VertexIndex)), 1.0e-6f);
    FProphecyJoltBodySnapshot Invalid = Snapshot;
    Invalid.Body.bMACD = true;
    TestFalse(TEXT("Unsupported MACD is explicit"), Prepared.Build(Invalid, Error));
    TestTrue(TEXT("Failed preparation retains previous sealed body"), Prepared.GetCaptureId() == Snapshot.CaptureId);
    Prepared.Reset();
    TestEqual(TEXT("Standalone native shapes are released"), FProphecyJoltPreparedBody::GetLivePreparedBodyCount(), PreparedBefore);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBodyPrimitiveTest,
    "Prophecy.Jolt.Body.NativePrimitiveFramesAndRefusals", ProphecyJolt::BodyTests::Flags)

bool FProphecyJoltBodyPrimitiveTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace BodyTests;
    FString Error;
    const FTransform Placement(FRotator(0.0, 0.0, 90.0), FVector(12.0, -7.0, 19.0));
    const Chaos::FImplicitObjectPtr Sphere = MakeImplicitObjectPtr<Chaos::FSphere>(Chaos::FVec3(3.0, 4.0, 5.0), 7.0);
    const Chaos::FImplicitObjectPtr MovedSphere = MakeImplicitObjectPtr<Chaos::FImplicitObjectTransformed>(Sphere, Chaos::FRigidTransform3(Placement));
    auto SphereShape = ShapeIdentity(EProphecyJoltRigShape::Sphere);
    if (!TestTrue(TEXT("Translated native sphere captures"), BodyConversion::CaptureGeometry(*MovedSphere, SphereShape, Error))) return false;
    TestNearlyEqual(TEXT("Sphere radius excludes translation"), SphereShape.RadiusCm, 7.0, 1.0e-6);
    TestNearlyEqual(TEXT("Sphere local center passes through wrapper once"), SphereShape.LocalToBodyOrigin.GetLocation(),
        Placement.TransformPosition(FVector(3.0, 4.0, 5.0)), 1.0e-6f);
    const Chaos::FImplicitObjectPtr Capsule = MakeImplicitObjectPtr<Chaos::FCapsule>(Chaos::FVec3(-20.0, 2.0, 3.0), Chaos::FVec3(20.0, 2.0, 3.0), 5.0);
    auto CapsuleShape = ShapeIdentity(EProphecyJoltRigShape::Capsule);
    if (!TestTrue(TEXT("Actual native capsule captures"), BodyConversion::CaptureGeometry(*Capsule, CapsuleShape, Error))) return false;
    TestNearlyEqual(TEXT("Capsule cylinder excludes both caps"), CapsuleShape.CapsuleCylinderLengthCm, 40.0, 1.0e-6);
    TestNearlyEqual(TEXT("Capsule native segment axis becomes local Z placement"),
        CapsuleShape.LocalToBodyOrigin.GetRotation().RotateVector(FVector::UpVector), FVector::ForwardVector, 1.0e-6f);
    FProphecyJoltPreparedBody Prepared;
    if (!TestTrue(TEXT("Captured capsule prepares through shared shape/mass path"), Prepared.Build(MakeSnapshot(CapsuleShape), Error))) return false;
    FVector COM;
    FBox Bounds(ForceInit);
    Prepared.GetGeometrySummary(COM, Bounds, Error);
    TestNearlyEqual(TEXT("Prepared native capsule bounds include cap radius once"), Bounds.GetExtent(), FVector(25.0, 5.0, 5.0), ToleranceCm);
    TestNearlyEqual(TEXT("Prepared capsule retains native center"), Bounds.GetCenter(), FVector(0.0, 2.0, 3.0), ToleranceCm);
    const Chaos::FImplicitObjectPtr Box = MakeImplicitObjectPtr<Chaos::TBox<Chaos::FReal, 3>>(Chaos::FVec3(-3.0, -5.0, -7.0), Chaos::FVec3(9.0, 11.0, 13.0));
    auto BoxShape = ShapeIdentity(EProphecyJoltRigShape::Box);
    TestTrue(TEXT("Native box captures"), BodyConversion::CaptureGeometry(*Box, BoxShape, Error));
    TestNearlyEqual(TEXT("Box center is not assumed to be zero"), BoxShape.LocalToBodyOrigin.GetLocation(), FVector(3.0), 1.0e-6f);
    TestNearlyEqual(TEXT("Box half extents derive from native bounds"), BoxShape.BoxHalfExtentCm, FVector(6.0, 8.0, 10.0), 1.0e-6f);
    auto WrongKind = ShapeIdentity(EProphecyJoltRigShape::Convex);
    TestFalse(TEXT("Authored/native shape identity mismatch is rejected"), BodyConversion::CaptureGeometry(*Sphere, WrongKind, Error));
    const Chaos::FConvexPtr Hull = Tetrahedron();
    const Chaos::FImplicitObjectPtr Mirrored = MakeImplicitObjectPtr<Chaos::TImplicitObjectScaled<Chaos::FConvex>>(Hull, Chaos::FVec3(-1.0, 1.0, 1.0), 0.0);
    auto ConvexShape = ShapeIdentity(EProphecyJoltRigShape::Convex);
    TestFalse(TEXT("Mirrored convex is refused rather than silently abs-scaled"), BodyConversion::CaptureGeometry(*Mirrored, ConvexShape, Error));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBodyHullLimitTest,
    "Prophecy.Jolt.Body.FinalHullVertexLimit", ProphecyJolt::BodyTests::Flags)

bool FProphecyJoltBodyHullLimitTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::BodyTests;
    auto Shape = ShapeIdentity(EProphecyJoltRigShape::Convex);
    for (int32 X : {-1, 1}) for (int32 Y : {-1, 1}) for (int32 Z : {-1, 1})
        Shape.ConvexVerticesCm.Emplace(20.0 * X, 20.0 * Y, 20.0 * Z);
    for (int32 Index = 0; Index < 301; ++Index)
        Shape.ConvexVerticesCm.Emplace(10.0 * FMath::Sin(Index * 0.37),
            10.0 * FMath::Cos(Index * 0.71), 10.0 * FMath::Sin(Index * 0.23));
    FString Error;
    FProphecyJoltPreparedBody Prepared;
    if (!TestTrue(TEXT("309 input points with an eight-vertex hull prepare without simplification"),
        Prepared.Build(MakeSnapshot(Shape), Error))) { AddError(Error); return false; }
    FVector COM;
    FBox Bounds(ForceInit);
    if (!TestTrue(TEXT("Prepared hull has geometry"), Prepared.GetGeometrySummary(COM, Bounds, Error))) return false;
    TestNearlyEqual(TEXT("Redundant points preserve the exact cube bounds"), Bounds.GetExtent(), FVector(20.0), ToleranceCm);
    Prepared.Reset();

    Shape.ConvexVerticesCm.Reset();
    // Distinct points on a sphere are all extreme vertices, unlike redundant input samples.
    for (int32 Index = 0; Index < 309; ++Index)
    {
        const double Z = 1.0 - 2.0 * (Index + 0.5) / 309.0;
        const double Radius = FMath::Sqrt(1.0 - Z * Z);
        const double Angle = Index * 2.399963229728653;
        Shape.ConvexVerticesCm.Emplace(50.0 * Radius * FMath::Cos(Angle),
            50.0 * Radius * FMath::Sin(Angle), 50.0 * Z);
    }
    TestFalse(TEXT("A hull above the final limit is not silently reduced"), Prepared.Build(MakeSnapshot(Shape), Error));
    TestFalse(TEXT("Rejected oversized hull owns no prepared geometry"), Prepared.IsValid());
    return TestTrue(TEXT("Failure names the native final hull limit"), Error.Contains(TEXT("final hull vertices")));
}

#endif
