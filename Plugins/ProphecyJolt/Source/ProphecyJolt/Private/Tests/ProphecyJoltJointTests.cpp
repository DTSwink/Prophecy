#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltConversions.h"
#include "ProphecyJoltJointConversion.h"
#include "ProphecyJoltRig.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END
#include "ProphecyJoltSpeculativeJoint.h"

namespace ProphecyJolt::JointTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
using EJointAxis = JPH::SixDOFConstraintSettings::EAxis;

FProphecyJoltRigJoint MakeJoint()
{
    FProphecyJoltRigJoint Joint;
    Joint.JointName = TEXT("HardLimitFixture");
    Joint.Body1Index = 0; // child
    Joint.Body2Index = 1; // parent
    Joint.Frame1 = FTransform(FRotator(17.0, -29.0, 11.0), FVector(12.0, -18.0, 7.0));
    Joint.Frame2 = FTransform(FRotator(-13.0, 23.0, 31.0), FVector(-20.0, 10.0, 15.0));
    FConstraintProfileProperties& Profile = Joint.CurrentProfile;
    Profile.LinearLimit.XMotion = LCM_Locked;
    Profile.LinearLimit.YMotion = LCM_Locked;
    Profile.LinearLimit.ZMotion = LCM_Locked;
    Profile.ConeLimit.Swing1Motion = ACM_Limited;
    Profile.ConeLimit.Swing2Motion = ACM_Limited;
    Profile.TwistLimit.TwistMotion = ACM_Limited;
    Profile.ConeLimit.Swing1LimitDegrees = 50.0f;
    Profile.ConeLimit.Swing2LimitDegrees = 15.0f;
    Profile.TwistLimit.TwistLimitDegrees = 25.0f;
    Profile.ConeLimit.bSoftConstraint = true; // explicit accepted hard-limit policy
    Profile.TwistLimit.bSoftConstraint = true;
    Profile.bDisableCollision = true;
    Profile.bEnableProjection = false;
    Profile.bEnableMassConditioning = false;
    Profile.bEnableShockPropagation = false;
    Profile.bParentDominates = false;
    Profile.bUseLinearJointSolver = false;
    Profile.AngularDrive.AngularDriveMode = EAngularDriveMode::SLERP;
    Profile.AngularDrive.SlerpDrive.bEnablePositionDrive = false;
    Profile.AngularDrive.SlerpDrive.bEnableVelocityDrive = false;
    return Joint;
}

bool RuntimeReady(FAutomationTestBase& Test)
{
    return Test.TestTrue(TEXT("Jolt ABI agrees"), JPH::VerifyJoltVersionID())
        && Test.TestNotNull(TEXT("Runtime module owns Jolt factory"), JPH::Factory::sInstance);
}

class FOneLayer final : public JPH::BroadPhaseLayerInterface
{
public:
    virtual JPH::uint GetNumBroadPhaseLayers() const override { return 1; }
    virtual JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer) const override { return JPH::BroadPhaseLayer(0); }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
    virtual const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer) const override { return "JointFixture"; }
#endif
};
// The fixture isolates joint response. This is not the production layer policy.
class FNoObjectPairs final : public JPH::ObjectLayerPairFilter
{
public:
    virtual bool ShouldCollide(JPH::ObjectLayer, JPH::ObjectLayer) const override { return false; }
};
class FNoBroadPairs final : public JPH::ObjectVsBroadPhaseLayerFilter
{
public:
    virtual bool ShouldCollide(JPH::ObjectLayer, JPH::BroadPhaseLayer) const override { return false; }
};

class FJointFixture final
{
public:
    FJointFixture() : Temp(4 * 1024 * 1024), Jobs(JPH::cMaxPhysicsJobs)
    {
        Physics.Init(4, 0, 16, 16, Layers, BroadPairs, ObjectPairs);
        Physics.SetGravity(JPH::Vec3::sZero());
    }
    ~FJointFixture()
    {
        if (Constraint != nullptr)
        {
            Physics.RemoveConstraint(RegisteredConstraint.GetPtr());
            RegisteredConstraint = nullptr;
            Constraint = nullptr;
        }
        for (const JPH::BodyID ID : IDs)
        {
            Bodies().RemoveBody(ID);
            Bodies().DestroyBody(ID);
        }
    }

    bool Init(FAutomationTestBase& Test, const FProphecyJoltRigJoint& Joint, const FQuat& ChildRelativeRotation,
        const FVector& InitialAnchorError = FVector::ZeroVector, bool bAnchorAtCOM = true,
        bool bSpeculative = false, bool bDynamicParent = false)
    {
        // Keep angular boundary cases analytic with spherical inertia and an
        // attachment at COM. Both COMs are still offset from their body origins.
        // The separate displaced-attachment case uses nonzero joint-to-COM arms.
        const FTransform ChildCOM(FQuat::Identity, bAnchorAtCOM ? Joint.Frame1.GetTranslation() : FVector(7.0, -11.0, 4.0));
        const FTransform ParentCOM(FQuat::Identity, bAnchorAtCOM ? Joint.Frame2.GetTranslation() : FVector(-8.0, 3.0, 9.0));
        const FTransform ParentToWorld(FRotator(29.0, 47.0, -19.0), FVector(700.0, -300.0, 450.0));
        const FVector Anchor = ParentToWorld.TransformPosition(Joint.Frame2.GetTranslation());
        const FQuat ParentFrameRotation = ParentToWorld.GetRotation() * Joint.Frame2.GetRotation();
        const FQuat ChildRotation = ParentFrameRotation * ChildRelativeRotation * Joint.Frame1.GetRotation().Inverse();
        const FTransform ChildToWorld(ChildRotation,
            Anchor + InitialAnchorError - ChildRotation.RotateVector(Joint.Frame1.GetTranslation()));
        const FTransform BodyToWorld[] = { ChildToWorld, ParentToWorld };
        const FTransform COMToOrigin[] = { ChildCOM, ParentCOM };
        for (int32 Index = 0; Index < 2; ++Index)
        {
            JPH::RefConst<JPH::Shape> Shape = new JPH::RotatedTranslatedShape(
                static_cast<JPH::Vec3>(Conversions::ToJoltPosition(COMToOrigin[Index].GetTranslation())),
                JPH::Quat::sIdentity(), new JPH::SphereShape(0.15f));
            JPH::BodyCreationSettings Settings(Shape, Conversions::ToJoltPosition(BodyToWorld[Index].GetTranslation()),
                Conversions::ToJoltRotation(BodyToWorld[Index].GetRotation()),
                Index == 0 || bDynamicParent ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, 0);
            Settings.mAllowSleeping = false;
            Settings.mLinearDamping = 0.0f;
            Settings.mAngularDamping = 0.0f;
            const JPH::BodyID ID = Bodies().CreateAndAddBody(Settings, Index == 0 || bDynamicParent ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
            if (!Test.TestFalse(TEXT("Joint fixture body allocated"), ID.IsInvalid())) return false;
            IDs.Add(ID);
        }
        JPH::SixDOFConstraintSettings Settings;
        FHardJointConversionReport Report;
        FString Error;
        const bool bMapped = BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error);
        if (!Test.TestTrue(TEXT("Hard joint maps: ") + Error, bMapped))
        {
            Test.AddError(Error);
            return false;
        }
        Constraint = static_cast<JPH::SixDOFConstraint*>(Bodies().CreateConstraint(&Settings,
            IDs[Report.JoltBody1Index], IDs[Report.JoltBody2Index]));
        if (!Test.TestNotNull(TEXT("Native SixDOF created"), Constraint.GetPtr())) return false;
        RegisteredConstraint = bSpeculative ? static_cast<JPH::TwoBodyConstraint*>(new FSpeculativeJoint(*Constraint, Settings)) : Constraint.GetPtr();
        Physics.AddConstraint(RegisteredConstraint.GetPtr());
        Test.TestNearlyEqual(TEXT("Parent-first relative orientation matches authored frame math"),
            FMath::Abs(Conversions::FromJoltRotation(Constraint->GetRotationInConstraintSpace()) | ChildRelativeRotation), 1.0, 2.0e-6);
        return true;
    }

    bool Step(FAutomationTestBase& Test, int32 Count = 90)
    {
        const double Deadline = FPlatformTime::Seconds() + 10.0;
        for (int32 Index = 0; Index < Count; ++Index)
        {
            if (FPlatformTime::Seconds() >= Deadline)
            {
                Test.AddError(TEXT("Joint fixture exceeded its bounded stepping deadline."));
                return false;
            }
            if (Physics.Update(1.0f / 60.0f, 1, &Temp, &Jobs) != JPH::EPhysicsUpdateError::None)
            {
                Test.AddError(TEXT("Jolt joint fixture update failed."));
                return false;
            }
        }
        return true;
    }

    FQuat RelativeRotation() const { return Conversions::FromJoltRotation(Constraint->GetRotationInConstraintSpace()); }
    double AnchorErrorCm()
    {
        const JPH::RVec3 ParentAnchor = Bodies().GetCenterOfMassTransform(IDs[1]) * Constraint->GetConstraintToBody1Matrix().GetTranslation();
        const JPH::RVec3 ChildAnchor = Bodies().GetCenterOfMassTransform(IDs[0]) * Constraint->GetConstraintToBody2Matrix().GetTranslation();
        return Conversions::FromJoltPosition(ChildAnchor - ParentAnchor).Length();
    }
    const JPH::SixDOFConstraint& JointConstraint() const { return *Constraint; }
    JPH::SixDOFConstraint& MutableJointConstraint() { return *Constraint; }
    JPH::PhysicsSystem& World() { return Physics; }
    JPH::Ref<JPH::TwoBodyConstraint>& RegisteredJoint() { return RegisteredConstraint; }
    JPH::BodyID ChildID() const { return IDs[0]; }
    JPH::BodyInterface& Bodies() { return Physics.GetBodyInterface(); }
    void SetChildAngularVelocity(JPH::Vec3Arg ConstraintSpaceVelocity)
    {
        const JPH::Quat Frame = Constraint->GetBody1()->GetRotation() * Constraint->GetConstraintToBody1Matrix().GetQuaternion();
        Bodies().SetAngularVelocity(IDs[0], Frame * ConstraintSpaceVelocity);
    }
    JPH::Vec3 ChildAngularVelocity() { return Bodies().GetAngularVelocity(IDs[0]); }
    void SetAngularRanges(JPH::Vec3Arg Minimum, JPH::Vec3Arg Maximum)
    {
        check(RegisteredConstraint->GetSubType() == JPH::EConstraintSubType::User1);
        static_cast<FSpeculativeJoint*>(RegisteredConstraint.GetPtr())->SetRotationLimits(Minimum, Maximum);
    }

private:
    FOneLayer Layers;
    FNoObjectPairs ObjectPairs;
    FNoBroadPairs BroadPairs;
    JPH::TempAllocatorImpl Temp;
    JPH::JobSystemSingleThreaded Jobs;
    JPH::PhysicsSystem Physics;
    TArray<JPH::BodyID> IDs;
    JPH::Ref<JPH::SixDOFConstraint> Constraint;
    JPH::Ref<JPH::TwoBodyConstraint> RegisteredConstraint;
};

double SignedAngleDegrees(const FQuat& Rotation, const FVector& Axis)
{
    const double Sign = Rotation.W < 0.0 ? -1.0 : 1.0;
    return FMath::RadiansToDegrees(2.0 * FMath::Atan2(
        Sign * FVector::DotProduct(FVector(Rotation.X, Rotation.Y, Rotation.Z), Axis), Sign * Rotation.W));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltJointMappingTest, "Prophecy.Jolt.Joints.MappingAndReadiness", ProphecyJolt::JointTests::Flags)

bool FProphecyJoltJointMappingTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::JointTests;
    FProphecyJoltRigJoint Joint = MakeJoint();
    const FTransform ChildCOM(FQuat::Identity, FVector(7.0, -11.0, 4.0));
    const FTransform ParentCOM(FQuat::Identity, FVector(-8.0, 3.0, 9.0));
    // Reproduce PhysicsConstraintComponent::UpdateConstraintFrames: the offset
    // rotates reference axes before transformation into body2 local space.
    Joint.AngularRotationOffsetDegrees = FRotator(13.0, -21.0, 9.0);
    const FQuat BaseFrame2 = Joint.Frame2.GetRotation();
    Joint.Frame2.SetRotation(BaseFrame2 * Joint.AngularRotationOffsetDegrees.Quaternion());
    FConstraintInstance Authored;
    Authored.AngularRotationOffset = Joint.AngularRotationOffsetDegrees;
    Authored.SetRefFrame(EConstraintFrame::Frame2, Joint.Frame2);
    TestNearlyEqual(TEXT("GetRefFrame returns stored offset axes without applying offset twice"),
        Authored.GetRefFrame(EConstraintFrame::Frame2).GetRotation().GetAxisX(), Joint.Frame2.GetRotation().GetAxisX(), 1.0e-6f);
    JPH::SixDOFConstraintSettings Settings;
    FHardJointConversionReport Report;
    FString Error;
    if (!TestTrue(TEXT("Lossless hard-limit mapping succeeds"), BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error)))
    {
        AddError(Error);
        return false;
    }
    TestEqual(TEXT("Jolt reference body is UE parent Body2"), Report.JoltBody1Index, 1);
    TestEqual(TEXT("Jolt moving body is UE child Body1"), Report.JoltBody2Index, 0);
    TestNearlyEqual(TEXT("Parent anchor subtracts parent COM in centimeters before unit conversion"),
        Conversions::FromJoltPosition(Settings.mPosition1), Joint.Frame2.GetTranslation() - ParentCOM.GetTranslation(), 1.0e-6f);
    TestNearlyEqual(TEXT("Child anchor subtracts child COM"), Conversions::FromJoltPosition(Settings.mPosition2),
        Joint.Frame1.GetTranslation() - ChildCOM.GetTranslation(), 1.0e-6f);
    TestNearlyEqual(TEXT("Offset is retained once in the parent X axis"), Conversions::FromJoltDirection(Settings.mAxisX1),
        Joint.Frame2.GetRotation().GetAxisX(), 1.0e-6f);
    TestNearlyEqual(TEXT("Swing1 retains 50 degrees around Z"), Settings.mLimitMax[EJointAxis::RotationZ], JPH::DegreesToRadians(50.0f), 1.0e-7f);
    TestNearlyEqual(TEXT("Swing2 retains 15 degrees around Y"), Settings.mLimitMax[EJointAxis::RotationY], JPH::DegreesToRadians(15.0f), 1.0e-7f);
    TestNearlyEqual(TEXT("Twist retains 25 degrees around X"), Settings.mLimitMax[EJointAxis::RotationX], JPH::DegreesToRadians(25.0f), 1.0e-7f);
    TestEqual(TEXT("Three hard angular limits recorded"), Report.HardAngularAxisCount, 3);
    TestEqual(TEXT("No authored threshold losses"), Report.RejectedThresholdAxisCount, 0);
    TestTrue(TEXT("Authored soft flags retained as explicit hard-policy provenance"), Report.bAuthoredSoftSwing && Report.bAuthoredSoftTwist);
    TestTrue(TEXT("Collision-disable request is explicit for caller filtering"), Report.bDisableCollision);
    TestTrue(TEXT("Stock coupled cone selected"), Settings.mSwingType == JPH::ESwingType::Cone);

    Joint.CurrentProfile.bEnableProjection = true;
    Joint.CurrentProfile.bEnableMassConditioning = true;
    Joint.CurrentProfile.AngularDrive.SlerpDrive.bEnablePositionDrive = true;
    TestTrue(TEXT("Fixture geometry remains available with explicit production readiness gaps"),
        BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error));
    TestTrue(TEXT("Active motor is reported"), Report.DeferredProfileFeatures.ContainsByPredicate([](const FString& Note) { return Note.Contains(TEXT("angular motors")); }));
    TestTrue(TEXT("Projection is reported"), Report.DeferredProfileFeatures.ContainsByPredicate([](const FString& Note) { return Note.Contains(TEXT("projection")); }));
    TestTrue(TEXT("Mass conditioning is reported"), Report.DeferredProfileFeatures.ContainsByPredicate([](const FString& Note) { return Note.Contains(TEXT("mass conditioning")); }));

    Joint = MakeJoint();
    Joint.CurrentProfile.LinearLimit.XMotion = LCM_Limited;
    Joint.CurrentProfile.LinearLimit.YMotion = LCM_Limited;
    TestFalse(TEXT("Coupled circular/spherical translation cannot become a box"), BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error));
    TestTrue(TEXT("Coupling refusal explains unsupported geometry"), Error.Contains(TEXT("coupled circle/sphere")));
    Joint = MakeJoint();
    Joint.CurrentProfile.ConeLimit.Swing1LimitDegrees = 179.75f;
    TestFalse(TEXT("Near-free Limited angle is rejected without retuning"), BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error));
    TestEqual(TEXT("Near-free threshold refusal recorded"), Report.RejectedThresholdAxisCount, 1);
    TestNearlyEqual(TEXT("Failed conversion preserves previous output"), Settings.mLimitMax[EJointAxis::RotationZ], JPH::DegreesToRadians(50.0f), 1.0e-7f);
    Joint.CurrentProfile.ConeLimit.Swing1LimitDegrees = 0.25f;
    TestFalse(TEXT("Near-locked Limited angle is rejected without retuning"), BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error));
    Joint = MakeJoint();
    Joint.Frame1.SetScale3D(FVector(2.0, 1.0, 1.0));
    TestFalse(TEXT("Unbaked frame scale is rejected"), BuildHardJointSettings(Joint, ChildCOM, ParentCOM, Settings, Report, Error));
    Joint = MakeJoint();
    const FTransform PrincipalMassFrame(FRotator(20.0, 30.0, 10.0), ChildCOM.GetTranslation());
    TestFalse(TEXT("Principal inertia orientation cannot be substituted for Jolt COM frame"),
        BuildHardJointSettings(Joint, PrincipalMassFrame, ParentCOM, Settings, Report, Error));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltJointMotionTest, "Prophecy.Jolt.Joints.NativeLockedFreeLimited", ProphecyJolt::JointTests::Flags)

bool FProphecyJoltJointMotionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::JointTests;
    if (!RuntimeReady(*this)) return false;
    for (EAngularConstraintMotion Motion : { ACM_Locked, ACM_Free, ACM_Limited })
    {
        FProphecyJoltRigJoint Joint = MakeJoint();
        Joint.CurrentProfile.ConeLimit.Swing1Motion = ACM_Locked;
        Joint.CurrentProfile.ConeLimit.Swing2Motion = ACM_Locked;
        Joint.CurrentProfile.TwistLimit.TwistMotion = Motion;
        FJointFixture Fixture;
        if (!Fixture.Init(*this, Joint, FQuat(FVector::XAxisVector, FMath::DegreesToRadians(70.0))) || !Fixture.Step(*this)) return false;
        const double Angle = SignedAngleDegrees(Fixture.RelativeRotation(), FVector::XAxisVector);
        if (Motion == ACM_Locked)
        {
            TestTrue(TEXT("Locked twist is actually fixed in the native constraint"), Fixture.JointConstraint().IsFixedAxis(EJointAxis::RotationX));
            TestTrue(TEXT("Locked twist solves to zero"), FMath::Abs(Angle) < 0.5);
        }
        else if (Motion == ACM_Free)
        {
            TestTrue(TEXT("Free twist is actually free in the native constraint"), Fixture.JointConstraint().IsFreeAxis(EJointAxis::RotationX));
            TestNearlyEqual(TEXT("Free twist preserves the initial 70-degree pose"), Angle, 70.0, 0.1);
        }
        else
        {
            TestTrue(TEXT("Limited twist converges to authored 25-degree boundary"), Angle >= 24.0 && Angle <= 26.0);
        }
        TestTrue(TEXT("Locked translation anchors coincide with off-center COMs"), Fixture.AnchorErrorCm() < 0.2);
    }
    // A displaced attachment must be corrected in world space even though both
    // joint reference frames and the parent body have nontrivial rotations.
    FProphecyJoltRigJoint Joint = MakeJoint();
    Joint.CurrentProfile.ConeLimit.Swing1Motion = ACM_Locked;
    Joint.CurrentProfile.ConeLimit.Swing2Motion = ACM_Locked;
    Joint.CurrentProfile.TwistLimit.TwistMotion = ACM_Locked;
    FJointFixture Fixture;
    if (!Fixture.Init(*this, Joint, FQuat::Identity, FVector(15.0, -25.0, 40.0), false)) return false;
    TestTrue(TEXT("Initial anchor displacement is real"), Fixture.AnchorErrorCm() > 45.0);
    if (!Fixture.Step(*this)) return false;
    TestTrue(TEXT("Native locked XYZ corrects displaced anchors"), Fixture.AnchorErrorCm() < 0.2);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltJointSwingTest, "Prophecy.Jolt.Joints.NativeAsymmetricSwingFrames", ProphecyJolt::JointTests::Flags)

bool FProphecyJoltJointSwingTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::JointTests;
    if (!RuntimeReady(*this)) return false;
    struct FCase { FVector Axis; double Initial; double Expected; const TCHAR* Label; };
    const FCase Cases[] = {
        { FVector::YAxisVector, 35.0, 15.0, TEXT("Swing2 Y uses narrow 15-degree limit") },
        { FVector::ZAxisVector, 35.0, 35.0, TEXT("Swing1 Z permits 35 degrees within wide 50-degree limit") },
        { FVector::ZAxisVector, 80.0, 50.0, TEXT("Swing1 Z stops at positive authored 50 degrees") },
        { FVector::ZAxisVector, -80.0, -50.0, TEXT("Swing1 Z stops at negative authored 50 degrees") }
    };
    for (const FCase& Case : Cases)
    {
        FProphecyJoltRigJoint Joint = MakeJoint();
        FJointFixture Fixture;
        if (!Fixture.Init(*this, Joint, FQuat(Case.Axis, FMath::DegreesToRadians(Case.Initial))) || !Fixture.Step(*this)) return false;
        TestNearlyEqual(Case.Label, SignedAngleDegrees(Fixture.RelativeRotation(), Case.Axis), Case.Expected, 1.0);
        TestTrue(TEXT("Asymmetric swing keeps the off-center anchors attached"), Fixture.AnchorErrorCm() < 0.2);
    }
    // A combined swing+twist proves parent/child frame order, which pure-axis
    // rotations alone could miss. It lies well inside both authored limits.
    const FQuat Relative = FQuat(FVector::YAxisVector, FMath::DegreesToRadians(7.0))
        * FQuat(FVector::XAxisVector, FMath::DegreesToRadians(12.0));
    FJointFixture Fixture;
    if (!Fixture.Init(*this, MakeJoint(), Relative) || !Fixture.Step(*this)) return false;
    TestNearlyEqual(TEXT("Combined swing/twist inside limits is preserved with parent-first frame order"),
        FMath::Abs(Fixture.RelativeRotation() | Relative), 1.0, 2.0e-5);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSpeculativeSwingTest,
    "Prophecy.Jolt.Joints.SpeculativeSwingBoundary", ProphecyJolt::JointTests::Flags)

bool FProphecyJoltSpeculativeSwingTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::JointTests;
    if (!RuntimeReady(*this)) return false;
    // A velocity servo can request a large outward speed while the joint is still
    // inside the cone. Reproduce that single-step release, with real solver jobs.
    for (const bool bDynamicParent : { false, true })
    for (const float Limit : { 25.0f, 45.0f })
    for (const bool bCorrected : { false, true })
    {
        FProphecyJoltRigJoint Joint = MakeJoint();
        Joint.CurrentProfile.ConeLimit.Swing2LimitDegrees = Limit;
        Joint.CurrentProfile.ConeLimit.Swing1LimitDegrees = 45.0f;
        FJointFixture Fixture;
        if (!Fixture.Init(*this, Joint, FQuat(FVector::YAxisVector, FMath::DegreesToRadians(Limit - 0.1f)),
            FVector::ZeroVector, true, bCorrected, bDynamicParent)) return false;
        Fixture.SetChildAngularVelocity(JPH::Vec3(0, 30, 0));
        if (!Fixture.Step(*this, 1)) return false;
        const double Angle = SignedAngleDegrees(Fixture.RelativeRotation(), FVector::YAxisVector);
        if (bCorrected)
        {
            TestTrue(TEXT("Approaching cone cannot release outward for a full step"), Angle <= Limit + 0.05);
            TestTrue(TEXT("Correction permits remaining interior clearance"), Angle >= Limit - 0.11);
        }
        else TestTrue(TEXT("Control reproduces stock inside-to-outside overshoot"), Angle > Limit + 5.0);
    }
    // It is a unilateral boundary constraint, not a friction or damping term.
    for (const JPH::Vec3 Velocity : { JPH::Vec3(0, -4, 0), JPH::Vec3(0, 0, 0.5f), JPH::Vec3(0.5f, 0, 0) })
    {
        FProphecyJoltRigJoint Joint = MakeJoint();
        Joint.CurrentProfile.ConeLimit.Swing1LimitDegrees = Joint.CurrentProfile.ConeLimit.Swing2LimitDegrees = 45.0f;
        FJointFixture Fixture;
        if (!Fixture.Init(*this, Joint, FQuat(FVector::YAxisVector, FMath::DegreesToRadians(30.0)),
            FVector::ZeroVector, true, true)) return false;
        Fixture.SetChildAngularVelocity(Velocity);
        const JPH::Vec3 Before = Fixture.ChildAngularVelocity();
        if (!Fixture.Step(*this, 1)) return false;
        TestTrue(TEXT("Inward, tangential and twist motion inside the cone retain velocity"),
            (Fixture.ChildAngularVelocity() - Before).Length() < 1.0e-4f);
    }
    {
        FProphecyJoltRigJoint Joint = MakeJoint();
        Joint.CurrentProfile.ConeLimit.Swing1Motion = Joint.CurrentProfile.ConeLimit.Swing2Motion = ACM_Free;
        Joint.CurrentProfile.TwistLimit.TwistMotion = ACM_Free;
        FJointFixture Fixture;
        if (!Fixture.Init(*this, Joint, FQuat(FVector::YAxisVector, FMath::DegreesToRadians(44.9)),
            FVector::ZeroVector, true, true)) return false;
        const JPH::Vec3 Limited = JPH::Vec3::sReplicate(JPH::DegreesToRadians(45.0f));
        Fixture.SetAngularRanges(-Limited, Limited);
        Fixture.SetChildAngularVelocity(JPH::Vec3(0, 30, 0));
        if (!Fixture.Step(*this, 1)) return false;
        TestTrue(TEXT("Runtime Free-to-Limited activates the interior boundary"),
            SignedAngleDegrees(Fixture.RelativeRotation(), FVector::YAxisVector) <= 45.05);
        Fixture.SetAngularRanges(JPH::Vec3::sReplicate(-JPH::JPH_PI), JPH::Vec3::sReplicate(JPH::JPH_PI));
        Fixture.SetChildAngularVelocity(JPH::Vec3(0, 30, 0));
        const JPH::Vec3 Before = Fixture.ChildAngularVelocity();
        if (!Fixture.Step(*this, 1)) return false;
        TestTrue(TEXT("Runtime Limited-to-Free removes boundary and stale impulse"),
            (Fixture.ChildAngularVelocity() - Before).Length() < 1.0e-4f);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSingleAxisEndpointTest,
    "Prophecy.Jolt.Joints.SingleAxisWithFullRangeEndpoints", ProphecyJolt::JointTests::Flags)

bool FProphecyJoltSingleAxisEndpointTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::JointTests;
    if (!RuntimeReady(*this)) return false;
    const FVector Axes[] = { FVector::XAxisVector, FVector::YAxisVector, FVector::ZAxisVector };
    for (int32 Selected = 0; Selected < 3; ++Selected)
    for (const float Limit : { 0.0f, 1.0f })
    {
        auto Joint = MakeJoint();
        auto& P = Joint.CurrentProfile;
        P.ConeLimit.Swing1LimitDegrees = P.ConeLimit.Swing2LimitDegrees = P.TwistLimit.TwistLimitDegrees = 180;
        if (Selected == 0) P.TwistLimit.TwistLimitDegrees = Limit;
        if (Selected == 1) P.ConeLimit.Swing2LimitDegrees = Limit;
        if (Selected == 2) P.ConeLimit.Swing1LimitDegrees = Limit;
        FJointFixture Fixture;
        if (!Fixture.Init(*this, Joint, FQuat(Axes[Selected], FMath::DegreesToRadians(35.0)))
            || !Fixture.Step(*this)) return false;
        TestNearlyEqual(TEXT("A single zero/one-degree axis corrects rotation with other axes at Limited 180"),
            SignedAngleDegrees(Fixture.RelativeRotation(), Axes[Selected]), double(Limit), 0.05);
        for (int32 Index = 0; Index < 3; ++Index)
            if (Index != Selected) TestTrue(TEXT("Other 180-degree axes remain unrestricted"),
                Fixture.JointConstraint().IsFreeAxis(static_cast<EJointAxis>(EJointAxis::RotationX + Index)));
        // Also exercise real motion in an unselected direction, not just mode flags.
        FJointFixture FreeFixture;
        const FVector Other = Axes[(Selected + 1) % 3];
        if (!FreeFixture.Init(*this, Joint, FQuat(Other, FMath::DegreesToRadians(70.0)))
            || !FreeFixture.Step(*this)) return false;
        TestNearlyEqual(TEXT("Limiting one axis leaves another axis's 70-degree pose alone"),
            SignedAngleDegrees(FreeFixture.RelativeRotation(), Other), 70.0, 0.05);
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltJointTransitionTest,
    "Prophecy.Jolt.Joints.RuntimeLimitContinuity", ProphecyJolt::JointTests::Flags)

bool FProphecyJoltJointTransitionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::JointTests;
    if (!RuntimeReady(*this)) return false;
    FProphecyJoltRigJoint Description = MakeJoint();
    Description.CurrentProfile.ConeLimit.Swing1Motion = ACM_Free;
    Description.CurrentProfile.ConeLimit.Swing2Motion = ACM_Free;
    Description.CurrentProfile.TwistLimit.TwistMotion = ACM_Free;
    FJointFixture Control, Changed;
    if (!Control.Init(*this, Description, FQuat::Identity, FVector::ZeroVector, false, false, true)
        || !Changed.Init(*this, Description, FQuat::Identity, FVector::ZeroVector, false, false, true)) return false;
    for (FJointFixture* F : { &Control, &Changed })
    {
        F->Bodies().AddForce(F->ChildID(), JPH::Vec3(13, -19, 31));
        if (!F->Step(*this, 1)) return false;
    }
    auto& Native = Changed.MutableJointConstraint();
    const JPH::Vec3 AnchorImpulse = Native.GetTotalLambdaPosition();
    TestTrue(TEXT("Loaded off-center attachment has a nonzero warm-start impulse"), AnchorImpulse.LengthSq() > 1.0e-8f);

    // A later registration catches the old remove/swap-last/add reorder.
    const JPH::Ref<JPH::ConstraintSettings> Settings = Native.GetConstraintSettings();
    JPH::Ref<JPH::TwoBodyConstraint> Later = static_cast<JPH::SixDOFConstraintSettings*>(Settings.GetPtr())
        ->Create(*Native.GetBody1(), *Native.GetBody2());
    Later->SetEnabled(false);
    Changed.World().AddConstraint(Later.GetPtr());
    const float Radians = JPH::DegreesToRadians(170.0f);
    Native.SetRotationLimits(JPH::Vec3::sReplicate(-Radians), JPH::Vec3::sReplicate(Radians));
    TestTrue(TEXT("Angular mode change preserves attachment impulse exactly"), Native.GetTotalLambdaPosition() == AnchorImpulse);
    JPH::Ref<JPH::TwoBodyConstraint> Wrapper = new FSpeculativeJoint(Native,
        *static_cast<JPH::SixDOFConstraintSettings*>(Settings.GetPtr()));
    Changed.World().ReplaceConstraint(Changed.RegisteredJoint().GetPtr(), Wrapper.GetPtr());
    Changed.RegisteredJoint() = Wrapper;
    auto Order = Changed.World().GetConstraints();
    TestTrue(TEXT("Replacement stays in its original solve slot"), Order[0].GetPtr() == Wrapper.GetPtr());
    TestTrue(TEXT("Unrelated constraint stays in its original slot"), Order[1].GetPtr() == Later.GetPtr());

    if (!Control.Step(*this, 10) || !Changed.Step(*this, 10))
    {
        Changed.World().RemoveConstraint(Later.GetPtr());
        return false;
    }
    TestTrue(TEXT("Inactive wide limits do not perturb loaded attachment rotation"),
        Control.Bodies().GetRotation(Control.ChildID()) == Changed.Bodies().GetRotation(Changed.ChildID()));
    TestTrue(TEXT("Inactive wide limits do not perturb loaded attachment position"),
        Control.Bodies().GetPosition(Control.ChildID()) == Changed.Bodies().GetPosition(Changed.ChildID()));

    Changed.World().ReplaceConstraint(Wrapper.GetPtr(), &Native);
    Changed.RegisteredJoint() = &Native;
    Order = Changed.World().GetConstraints();
    TestTrue(TEXT("Unwrapping retains both slots"), Order[0].GetPtr() == &Native && Order[1].GetPtr() == Later.GetPtr());
    Changed.World().RemoveConstraint(Later.GetPtr());

    // Locked angular rows must still enforce rotation and clear their own cache
    // when disabled; preservation must not restore stale angular reactions.
    Native.SetRotationLimits(JPH::Vec3::sZero(), JPH::Vec3::sZero());
    Changed.SetChildAngularVelocity(JPH::Vec3(3, 2, 1));
    if (!Changed.Step(*this, 1)) return false;
    TestTrue(TEXT("Locked angular rows generate an actual reaction"), Native.GetTotalLambdaRotation().LengthSq() > 1.0e-8f);
    const JPH::Vec3 LockedAnchorImpulse = Native.GetTotalLambdaPosition();
    Native.SetRotationLimits(JPH::Vec3::sReplicate(-JPH::JPH_PI), JPH::Vec3::sReplicate(JPH::JPH_PI));
    TestTrue(TEXT("Free clears the angular reaction"), Native.GetTotalLambdaRotation() == JPH::Vec3::sZero());
    TestTrue(TEXT("Free retains the independent attachment reaction"), Native.GetTotalLambdaPosition() == LockedAnchorImpulse);
    return !HasAnyErrors();
}

#endif // WITH_DEV_AUTOMATION_TESTS
