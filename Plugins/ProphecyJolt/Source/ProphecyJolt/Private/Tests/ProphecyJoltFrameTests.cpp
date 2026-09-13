#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "PhysicsEngine/SphylElem.h"
#include "ProphecyJoltConversions.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h>
#include <Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/FixedConstraint.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::FrameTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
constexpr float PositionToleranceCm = 2.0e-3f;
constexpr float DirectionTolerance = 2.0e-5f;

bool RuntimeReady(FAutomationTestBase& Test)
{
    return Test.TestTrue(TEXT("Compatible Jolt runtime"), JPH::VerifyJoltVersionID())
        && Test.TestNotNull(TEXT("Module owns Jolt factory"), JPH::Factory::sInstance);
}

// These analytic fixtures need body state and constraint construction, but no solver update or workers.
class FOneBroadPhase final : public JPH::BroadPhaseLayerInterface
{
public:
    virtual JPH::uint GetNumBroadPhaseLayers() const override { return 1; }
    virtual JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer) const override { return JPH::BroadPhaseLayer(0); }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
    virtual const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer) const override { return "FrameFixture"; }
#endif
};
class FAllObjectPairs final : public JPH::ObjectLayerPairFilter
{
public:
    virtual bool ShouldCollide(JPH::ObjectLayer, JPH::ObjectLayer) const override { return true; }
};
class FAllBroadPhasePairs final : public JPH::ObjectVsBroadPhaseLayerFilter
{
public:
    virtual bool ShouldCollide(JPH::ObjectLayer, JPH::BroadPhaseLayer) const override { return true; }
};
class FBodyFixture final
{
public:
    FBodyFixture() { Physics.Init(4, 0, 16, 16, Layers, BroadPairs, ObjectPairs); }
    ~FBodyFixture()
    {
        for (const JPH::BodyID ID : IDs)
        {
            Bodies().RemoveBody(ID);
            Bodies().DestroyBody(ID);
        }
    }
    JPH::BodyID Add(const JPH::Shape* Shape, const FTransform& BodyToWorld)
    {
        using namespace ProphecyJolt::Conversions;
        JPH::BodyCreationSettings Settings(Shape, ToJoltPosition(BodyToWorld.GetTranslation()),
            ToJoltRotation(BodyToWorld.GetRotation()), JPH::EMotionType::Dynamic, 0);
        const JPH::BodyID ID = Bodies().CreateAndAddBody(Settings, JPH::EActivation::Activate);
        if (!ID.IsInvalid()) IDs.Add(ID);
        return ID;
    }
    JPH::BodyInterface& Bodies() { return Physics.GetBodyInterface(); }
private:
    FOneBroadPhase Layers;
    FAllObjectPairs ObjectPairs;
    FAllBroadPhasePairs BroadPairs;
    JPH::PhysicsSystem Physics;
    TArray<JPH::BodyID> IDs;
};

JPH::RMat44 RigidTransform(const FTransform& Transform)
{
    return JPH::RMat44::sRotationTranslation(ProphecyJolt::Conversions::ToJoltRotation(Transform.GetRotation()),
        ProphecyJolt::Conversions::ToJoltPosition(Transform.GetTranslation()));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltCapsuleFrameTest, "Prophecy.Jolt.Frames.CapsuleDimensionsAndAxis", ProphecyJolt::FrameTests::Flags)

bool FProphecyJoltCapsuleFrameTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::FrameTests;
    if (!RuntimeReady(*this)) return false;

    // UE Length excludes both caps; Jolt takes half of that straight-cylinder length.
    FKSphylElem CapsuleUE(15.0f, 80.0f);
    const FBox UnrealBounds = CapsuleUE.CalcAABB(FTransform::Identity, 1.0f);
    TestNearlyEqual(TEXT("UE capsule length axis is Z, total length is Length + 2*Radius"),
        UnrealBounds.GetExtent(), FVector(15.0, 15.0, 55.0), PositionToleranceCm);
    const JPH::Ref<JPH::CapsuleShape> NativeCapsule = new JPH::CapsuleShape(
        CapsuleUE.Length * 0.005f, CapsuleUE.Radius * 0.01f);
    TestNearlyEqual(TEXT("Jolt half-height excludes spherical caps"), NativeCapsule->GetHalfHeightOfCylinder(), 0.4f, 1.0e-6f);
    TestNearlyEqual(TEXT("Jolt radius retains its independent dimension"), NativeCapsule->GetRadius(), 0.15f, 1.0e-6f);
    TestNearlyEqual(TEXT("Native Jolt capsule extends along Y"), FromJoltDirection(NativeCapsule->GetLocalBounds().mMax),
        FVector(0.15, 0.55, 0.15), DirectionTolerance);

    // A local +90 degree X rotation maps native +Y to authored +Z. No global basis reflection is involved.
    const FQuat NativeYToAuthoredZ(FVector(1.0, 0.0, 0.0), UE_DOUBLE_HALF_PI);
    const JPH::Ref<JPH::RotatedTranslatedShape> UprightCapsule = new JPH::RotatedTranslatedShape(
        JPH::Vec3::sZero(), ToJoltRotation(NativeYToAuthoredZ), NativeCapsule.GetPtr());
    TestNearlyEqual(TEXT("Axis-corrected Jolt bounds match the UE capsule"),
        FromJoltDirection(UprightCapsule->GetLocalBounds().mMax) * 100.0, UnrealBounds.GetExtent(), PositionToleranceCm);
    JPH::RayCastResult NativeHit, UprightHit;
    const JPH::RayCast NativeRay(JPH::Vec3(0.0f, 2.0f, 0.0f), JPH::Vec3(0.0f, -4.0f, 0.0f));
    const JPH::RayCast UprightRay(JPH::Vec3(0.0f, 0.0f, 2.0f), JPH::Vec3(0.0f, 0.0f, -4.0f));
    if (!TestTrue(TEXT("Native capsule ray hits the +Y cap"), NativeCapsule->CastRay(NativeRay, JPH::SubShapeIDCreator(), NativeHit))
        || !TestTrue(TEXT("Corrected capsule ray hits the +Z cap"), UprightCapsule->CastRay(UprightRay, JPH::SubShapeIDCreator(), UprightHit))) return false;
    TestNearlyEqual(TEXT("Native tip ray includes cylinder and radius exactly once"), NativeHit.mFraction, 0.3625f, 1.0e-5f);
    TestNearlyEqual(TEXT("Local axis rotation preserves cap location"), UprightHit.mFraction, NativeHit.mFraction, 1.0e-5f);

    CapsuleUE.Center = FVector(23.0, -41.0, 67.0);
    CapsuleUE.Rotation = FRotator(17.0, -31.0, 23.0);
    const JPH::Ref<JPH::RotatedTranslatedShape> AuthoredCapsule = new JPH::RotatedTranslatedShape(
        static_cast<JPH::Vec3>(ToJoltPosition(CapsuleUE.Center)),
        ToJoltRotation(CapsuleUE.Rotation.Quaternion()) * ToJoltRotation(NativeYToAuthoredZ), NativeCapsule.GetPtr());
    const FVector AuthoredTipCm = CapsuleUE.GetTransform().TransformPosition(FVector(0.0, 0.0, 55.0));
    const JPH::Vec3 JoltTip = AuthoredCapsule->GetPosition() + AuthoredCapsule->GetRotation() * JPH::Vec3(0.0f, 0.55f, 0.0f);
    TestNearlyEqual(TEXT("Authored capsule placement follows local axis correction"), FromJoltDirection(JoltTip) * 100.0,
        AuthoredTipCm, PositionToleranceCm);
    JPH::CapsuleShapeSettings ZeroCylinder(0.0f, 0.15f);
    const JPH::Shape::ShapeResult Sphere = ZeroCylinder.Create();
    if (!TestFalse(TEXT("Zero cylinder settings remain valid"), Sphere.HasError())) return false;
    TestTrue(TEXT("Jolt represents a zero-length capsule as a sphere"), Sphere.Get()->GetSubType() == JPH::EShapeSubType::Sphere);
    // All transforms here have unit scale. No negative/nonuniform scale policy or approximation is introduced.
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBoneBodyComTest, "Prophecy.Jolt.Frames.BoneBodyColliderAndOffsetCOM", ProphecyJolt::FrameTests::Flags)

bool FProphecyJoltBoneBodyComTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::FrameTests;
    if (!RuntimeReady(*this)) return false;
    const FTransform BoneToWorld(FQuat(FVector(0.0, 0.0, 1.0), UE_DOUBLE_HALF_PI), FVector(1000.0, -500.0, 200.0));
    const FTransform BodyInBone(FQuat(FVector(1.0, 0.0, 0.0), UE_DOUBLE_HALF_PI), FVector(100.0, 20.0, -30.0));
    const FTransform ColliderInBody(FQuat(FVector(0.0, 1.0, 0.0), UE_DOUBLE_HALF_PI), FVector(20.0, -40.0, 10.0));
    const FVector ComOffsetInBodyCm(5.0, 2.0, -3.0);
    const FTransform BodyToWorld = BodyInBone * BoneToWorld;
    const JPH::RMat44 JoltBodyToWorld = RigidTransform(BoneToWorld) * RigidTransform(BodyInBone);
    TestNearlyEqual(TEXT("UE local-then-parent composition gives the analytic body origin"), BodyToWorld.GetTranslation(),
        FVector(980.0, -400.0, 170.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Jolt parent-times-local matrix composition agrees"), FromJoltPosition(JoltBodyToWorld.GetTranslation()),
        FVector(980.0, -400.0, 170.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Composed rotation maps body X to world Y"), FromJoltDirection(JoltBodyToWorld.GetAxisX()),
        FVector(0.0, 1.0, 0.0), DirectionTolerance);

    const JPH::RefConst<JPH::Shape> Box = new JPH::BoxShape(JPH::Vec3(0.2f, 0.1f, 0.3f), 0.0f);
    const JPH::RefConst<JPH::Shape> Collider = new JPH::RotatedTranslatedShape(
        static_cast<JPH::Vec3>(ToJoltPosition(ColliderInBody.GetTranslation())), ToJoltRotation(ColliderInBody.GetRotation()), Box.GetPtr());
    const JPH::RefConst<JPH::Shape> OffsetShape = new JPH::OffsetCenterOfMassShape(
        Collider.GetPtr(), static_cast<JPH::Vec3>(ToJoltPosition(ComOffsetInBodyCm)));
    FBodyFixture Fixture;
    const JPH::BodyID Body = Fixture.Add(OffsetShape.GetPtr(), BodyToWorld);
    if (!TestFalse(TEXT("Offset-COM body created"), Body.IsInvalid())) return false;
    TestNearlyEqual(TEXT("Authored collider origin stays distinct from body origin"), BodyToWorld.TransformPosition(ColliderInBody.GetTranslation()),
        FVector(990.0, -380.0, 130.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Body position returns shape origin, not COM"), FromJoltPosition(Fixture.Bodies().GetPosition(Body)),
        FVector(980.0, -400.0, 170.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Rotations act on the local collider and COM offsets"), FromJoltPosition(Fixture.Bodies().GetCenterOfMassPosition(Body)),
        FVector(987.0, -375.0, 132.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("World transform retains body origin"), FromJoltPosition(Fixture.Bodies().GetWorldTransform(Body).GetTranslation()),
        FVector(980.0, -400.0, 170.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("COM transform uses the distinct center of mass"), FromJoltPosition(Fixture.Bodies().GetCenterOfMassTransform(Body).GetTranslation()),
        FVector(987.0, -375.0, 132.0), PositionToleranceCm);
    const FTransform ReadBodyToWorld(FromJoltRotation(Fixture.Bodies().GetRotation(Body)), FromJoltPosition(Fixture.Bodies().GetPosition(Body)));
    const FTransform RecoveredBoneToWorld = BodyInBone.Inverse() * ReadBodyToWorld;
    TestNearlyEqual(TEXT("Body readback removes body-in-bone offset to recover bone origin"), RecoveredBoneToWorld.GetTranslation(),
        BoneToWorld.GetTranslation(), PositionToleranceCm);
    TestNearlyEqual(TEXT("Readback recovers bone orientation too"), RecoveredBoneToWorld.TransformVectorNoScale(FVector(1.0, 0.0, 0.0)),
        FVector(0.0, 1.0, 0.0), DirectionTolerance);

    Fixture.Bodies().SetLinearVelocity(Body, ToJoltLinearVelocity(FVector(100.0, -200.0, 300.0)));
    Fixture.Bodies().SetAngularVelocity(Body, ToJoltAngularVelocity(FVector(0.0, 0.0, 2.0)));
    TestNearlyEqual(TEXT("Linear body velocity is COM velocity"), FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(Body)),
        FVector(100.0, -200.0, 300.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Origin velocity includes omega cross origin-minus-COM"),
        FromJoltLinearVelocity(Fixture.Bodies().GetPointVelocity(Body, ToJoltPosition(FVector(980.0, -400.0, 170.0)))),
        FVector(150.0, -214.0, 300.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Collider-center point velocity uses its own lever arm"),
        FromJoltLinearVelocity(Fixture.Bodies().GetPointVelocity(Body, ToJoltPosition(FVector(990.0, -380.0, 130.0)))),
        FVector(110.0, -194.0, 300.0), PositionToleranceCm);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltConstraintFramesTest, "Prophecy.Jolt.Frames.ConstraintLocalCOMVersusWorld", ProphecyJolt::FrameTests::Flags)

bool FProphecyJoltConstraintFramesTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::FrameTests;
    if (!RuntimeReady(*this)) return false;
    const FTransform FirstToWorld(FQuat(FVector(0.0, 0.0, 1.0), UE_DOUBLE_HALF_PI), FVector(100.0, 200.0, 300.0));
    const FTransform SecondToWorld(FQuat(FVector(1.0, 0.0, 0.0), UE_DOUBLE_HALF_PI), FVector(-50.0, 600.0, 200.0));
    const JPH::RefConst<JPH::Shape> Sphere = new JPH::SphereShape(0.25f);
    const JPH::RefConst<JPH::Shape> FirstShape = new JPH::OffsetCenterOfMassShape(Sphere.GetPtr(), JPH::Vec3(0.1f, 0.0f, 0.0f));
    const JPH::RefConst<JPH::Shape> SecondShape = new JPH::OffsetCenterOfMassShape(Sphere.GetPtr(), JPH::Vec3(0.0f, 0.2f, 0.0f));
    FBodyFixture Fixture;
    const JPH::BodyID First = Fixture.Add(FirstShape.GetPtr(), FirstToWorld);
    const JPH::BodyID Second = Fixture.Add(SecondShape.GetPtr(), SecondToWorld);
    if (!TestFalse(TEXT("First rotated body exists"), First.IsInvalid())
        || !TestFalse(TEXT("Second rotated body exists"), Second.IsInvalid())) return false;
    const FVector AnchorCm(140.0, 260.0, 340.0);
    const FVector WorldAxisX(0.0, 0.0, -1.0);
    const FVector WorldAxisY(0.0, 1.0, 0.0);
    JPH::FixedConstraintSettings WorldSettings;
    WorldSettings.mSpace = JPH::EConstraintSpace::WorldSpace;
    WorldSettings.mAutoDetectPoint = false;
    WorldSettings.mPoint1 = WorldSettings.mPoint2 = ToJoltPosition(AnchorCm);
    WorldSettings.mAxisX1 = WorldSettings.mAxisX2 = ToJoltDirection(WorldAxisX);
    WorldSettings.mAxisY1 = WorldSettings.mAxisY2 = ToJoltDirection(WorldAxisY);
    JPH::FixedConstraintSettings LocalSettings;
    LocalSettings.mSpace = JPH::EConstraintSpace::LocalToBodyCOM;
    LocalSettings.mPoint1 = ToJoltPosition(FVector(50.0, -40.0, 40.0));
    LocalSettings.mPoint2 = ToJoltPosition(FVector(190.0, 120.0, 340.0));
    LocalSettings.mAxisX1 = ToJoltDirection(FirstToWorld.GetRotation().UnrotateVector(WorldAxisX));
    LocalSettings.mAxisY1 = ToJoltDirection(FirstToWorld.GetRotation().UnrotateVector(WorldAxisY));
    LocalSettings.mAxisX2 = ToJoltDirection(SecondToWorld.GetRotation().UnrotateVector(WorldAxisX));
    LocalSettings.mAxisY2 = ToJoltDirection(SecondToWorld.GetRotation().UnrotateVector(WorldAxisY));
    // These constraints are introspected only, never added together to over-constrain a simulation.
    const JPH::Ref<JPH::TwoBodyConstraint> WorldConstraint = Fixture.Bodies().CreateConstraint(&WorldSettings, First, Second);
    const JPH::Ref<JPH::TwoBodyConstraint> LocalConstraint = Fixture.Bodies().CreateConstraint(&LocalSettings, First, Second);
    if (!TestNotNull(TEXT("World-space constraint created"), WorldConstraint.GetPtr())
        || !TestNotNull(TEXT("Local-COM constraint created"), LocalConstraint.GetPtr())) return false;
    const JPH::Mat44 WorldFrames[] = { WorldConstraint->GetConstraintToBody1Matrix(), WorldConstraint->GetConstraintToBody2Matrix() };
    const JPH::Mat44 LocalFrames[] = { LocalConstraint->GetConstraintToBody1Matrix(), LocalConstraint->GetConstraintToBody2Matrix() };
    const JPH::BodyID Bodies[] = { First, Second };
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const FString Label = FString::Printf(TEXT("Constraint body %d"), Index + 1);
        TestNearlyEqual(Label + TEXT(" local attachment agrees with world-space construction"),
            FromJoltDirection(WorldFrames[Index].GetTranslation()) * 100.0,
            FromJoltDirection(LocalFrames[Index].GetTranslation()) * 100.0, PositionToleranceCm);
        TestNearlyEqual(Label + TEXT(" reference X axis agrees"), FromJoltDirection(WorldFrames[Index].GetAxisX()),
            FromJoltDirection(LocalFrames[Index].GetAxisX()), DirectionTolerance);
        TestNearlyEqual(Label + TEXT(" reference Y axis agrees"), FromJoltDirection(WorldFrames[Index].GetAxisY()),
            FromJoltDirection(LocalFrames[Index].GetAxisY()), DirectionTolerance);
        TestNearlyEqual(Label + TEXT(" COM frame reconstructs the authored world anchor"),
            FromJoltPosition(Fixture.Bodies().GetCenterOfMassTransform(Bodies[Index]) * LocalFrames[Index].GetTranslation()),
            AnchorCm, PositionToleranceCm);
    }
    // Omitting the COM subtraction produces a measurable wrong anchor despite correct body rotations.
    const FVector IncorrectFirstAnchor = FromJoltPosition(Fixture.Bodies().GetCenterOfMassTransform(First)
        * static_cast<JPH::Vec3>(ToJoltPosition(FirstToWorld.InverseTransformPosition(AnchorCm))));
    TestNearlyEqual(TEXT("Body-origin local coordinates incorrectly shift the anchor by the rotated COM offset"),
        IncorrectFirstAnchor, FVector(140.0, 270.0, 340.0), PositionToleranceCm);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
