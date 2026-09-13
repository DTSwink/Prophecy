#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "ProphecyJoltConversions.h"
#include "ProphecyJoltVelocityServo.h"
#include <limits>

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemThreadPool.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::VelocityServoTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
constexpr float PositionToleranceCm = 2.0e-3f;
constexpr float VelocityToleranceCmPerSecond = 2.0e-3f;
constexpr float AngularToleranceRadiansPerSecond = 2.0e-5f;

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
    virtual const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer) const override { return "VelocityServoFixture"; }
#endif
};

// These bodies isolate the velocity rule. No production collision policy is inferred.
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

class FServoFixture final
{
public:
    explicit FServoFixture(JPH::Vec3Arg Gravity = JPH::Vec3::sZero())
        : Temp(4 * 1024 * 1024)
        , Jobs(MakeUnique<JPH::JobSystemThreadPool>(JPH::cMaxPhysicsJobs, JPH::cMaxPhysicsBarriers, 1))
    {
        Physics.Init(16, 0, 32, 32, Layers, BroadPairs, ObjectPairs);
        Physics.SetGravity(Gravity);
        Physics.AddStepListener(&Servo);
    }

    ~FServoFixture()
    {
        // Update is synchronous; join worker wrappers before destroying anything
        // that the real registered listener can access.
        Jobs.Reset();
        Physics.RemoveStepListener(&Servo);
        for (const JPH::BodyID ID : IDs)
        {
            Bodies().RemoveBody(ID);
            Bodies().DestroyBody(ID);
        }
    }

    JPH::BodyID Add(const JPH::Shape* Shape, const FTransform& BodyToWorld, float Mass = 2.0f)
    {
        JPH::BodyCreationSettings Settings(Shape, Conversions::ToJoltPosition(BodyToWorld.GetTranslation()),
            Conversions::ToJoltRotation(BodyToWorld.GetRotation()), JPH::EMotionType::Dynamic, 0);
        Settings.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
        Settings.mMassPropertiesOverride.mMass = Mass;
        Settings.mAllowSleeping = false;
        Settings.mLinearDamping = 0.0f;
        Settings.mAngularDamping = 0.0f;
        const JPH::BodyID ID = Bodies().CreateAndAddBody(Settings, JPH::EActivation::Activate);
        if (!ID.IsInvalid()) IDs.Add(ID);
        return ID;
    }

    bool Step(FAutomationTestBase& Test, float FrameSeconds, int32 CollisionSteps = 1)
    {
        check(CollisionSteps > 0 && CollisionSteps <= 2);
        FString ActivationError;
        const bool bPrepared = Servo.PrepareActivation(Physics, ActivationError, false, FrameSeconds / float(CollisionSteps));
        if (!Test.TestTrue(FString(TEXT("Prepare conditional native activation: ")) + ActivationError, bPrepared)) return false;
        const JPH::EPhysicsUpdateError Error = Physics.Update(FrameSeconds, CollisionSteps, &Temp, Jobs.Get());
        return Test.TestTrue(TEXT("Synchronous Jolt Update completes without error"), Error == JPH::EPhysicsUpdateError::None);
    }

    bool Publish(FAutomationTestBase& Test, TConstArrayView<FVelocityServo::FTarget> Targets, float Denominator)
    {
        FString Error;
        const bool bPublished = Servo.Publish(Targets, Denominator, Error);
        return Test.TestTrue(FString(TEXT("Publish recorded fixture endpoints: ")) + Error, bPublished);
    }

    bool CheckSamples(FAutomationTestBase& Test, int32 ExpectedBodies)
    {
        if (!Test.TestEqual(TEXT("Listener exposes one sample per published body"), Servo.GetLastSamples().Num(), ExpectedBodies)
            || !Test.TestEqual(TEXT("No-lock body access succeeded"), Servo.GetInvalidBodyCount(), uint64(0))) return false;
        for (const FVelocityServo::FSample& Sample : Servo.GetLastSamples())
        {
            if (!Test.TestTrue(TEXT("Real listener captured valid before/after state"), Sample.bValid)) return false;
        }
        for (const JPH::BodyID ID : IDs)
        {
            if (!Test.TestTrue(TEXT("Body remains active; sleeping did not bypass the test"), Bodies().IsActive(ID))) return false;
        }
        return true;
    }

    JPH::BodyInterface& Bodies() { return Physics.GetBodyInterface(); }
    FVelocityServo& Listener() { return Servo; }

private:
    FOneLayer Layers;
    FNoObjectPairs ObjectPairs;
    FNoBroadPairs BroadPairs;
    JPH::TempAllocatorImpl Temp;
    JPH::PhysicsSystem Physics;
    FVelocityServo Servo;
    TUniquePtr<JPH::JobSystemThreadPool> Jobs;
    TArray<JPH::BodyID> IDs;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoStrengthsTest,
    "Prophecy.Jolt.Servo.StrengthsAndQuaternionSign", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoStrengthsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    struct FCase { float Strength; FVector ExpectedLinear; double ExpectedAngularZ; };
    // h=.1, target displacement=30 cm and target angle=.2 rad: desired
    // velocities are 300 cm/s and 2 rad/s. These are analytic expectations,
    // including extrapolation beyond one, not another controller implementation.
    const FCase Cases[] = {
        { 0.0f, FVector(20.0, -40.0, 10.0), 0.4 },
        { 0.25f, FVector(90.0, -30.0, 7.5), 0.8 },
        { 1.0f, FVector(300.0, 0.0, 0.0), 2.0 },
        { 1.5f, FVector(440.0, 20.0, -5.0), 2.8 }
    };
    const FVector InitialLinear(20.0, -40.0, 10.0);
    const FVector InitialAngular(0.0, 0.0, 0.4);
    TArray<FVelocityServo::FTarget> Targets;
    for (int32 CaseIndex = 0; CaseIndex < UE_ARRAY_COUNT(Cases); ++CaseIndex)
    {
        for (int32 SignIndex = 0; SignIndex < 2; ++SignIndex)
        {
            const FVector Start(100.0, 300.0 * Targets.Num(), 200.0);
            const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(FQuat::Identity, Start), SignIndex == 0 ? 2.0f : 7.0f);
            if (!TestFalse(TEXT("Strength fixture body allocated"), ID.IsInvalid())) return false;
            Fixture.Bodies().SetLinearVelocity(ID, ToJoltLinearVelocity(InitialLinear));
            Fixture.Bodies().SetAngularVelocity(ID, ToJoltAngularVelocity(InitialAngular));
            FVelocityServo::FTarget& Target = Targets.AddDefaulted_GetRef();
            Target.Body = ID;
            Target.TargetPositionCm = Start + FVector(30.0, 0.0, 0.0);
            Target.TargetRotation = FQuat(FVector::UpVector, 0.2) * (SignIndex == 0 ? 1.0 : -1.0);
            Target.LinearStrength = Target.AngularStrength = Cases[CaseIndex].Strength;
        }
    }
    constexpr float ActualStep = 1.0f / 60.0f;
    if (!Fixture.Publish(*this, Targets, 0.1f) || !Fixture.Step(*this, ActualStep)
        || !Fixture.CheckSamples(*this, Targets.Num())) return false;
    TestEqual(TEXT("One registered callback for one collision step"), Fixture.Listener().GetInvocationCount(), uint64(1));
    for (int32 Index = 0; Index < Targets.Num(); ++Index)
    {
        const FCase& Expected = Cases[Index / 2];
        const FVelocityServo::FSample& Sample = Fixture.Listener().GetLastSamples()[Index];
        const FVector Start = Targets[Index].TargetPositionCm - FVector(30.0, 0.0, 0.0);
        const FString Label = FString::Printf(TEXT("Strength %.2f, quaternion sign %d"), Expected.Strength, Index % 2);
        TestNearlyEqual(Label + TEXT(" samples the initial body origin"), Sample.PositionCm, Start, PositionToleranceCm);
        TestNearlyEqual(Label + TEXT(" captures V before rewrite"), Sample.LinearBeforeCmPerSecond, InitialLinear, VelocityToleranceCmPerSecond);
        TestNearlyEqual(Label + TEXT(" captures W before rewrite"), Sample.AngularBeforeRadiansPerSecond, InitialAngular, AngularToleranceRadiansPerSecond);
        TestNearlyEqual(Label + TEXT(" writes the expected COM velocity independent of mass"), Sample.LinearAfterCmPerSecond,
            Expected.ExpectedLinear, VelocityToleranceCmPerSecond);
        TestNearlyEqual(Label + TEXT(" takes the same shortest quaternion arc"), Sample.AngularAfterRadiansPerSecond,
            FVector(0.0, 0.0, Expected.ExpectedAngularZ), AngularToleranceRadiansPerSecond);
        TestNearlyEqual(Label + TEXT(" velocity write affects the current physics step"),
            FromJoltPosition(Fixture.Bodies().GetPosition(Targets[Index].Body)),
            Start + Expected.ExpectedLinear * ActualStep, PositionToleranceCm);
        TestNearlyEqual(Label + TEXT(" is not changed later by an emulated force"),
            FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(Targets[Index].Body)),
            Expected.ExpectedLinear, VelocityToleranceCmPerSecond);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoSubstepTest,
    "Prophecy.Jolt.Servo.RecordedDenominatorAcrossTwoCollisionSteps", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoSubstepTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(FQuat::Identity, FVector(0.0, 0.0, 100.0)));
    if (!TestFalse(TEXT("Substep fixture body allocated"), ID.IsInvalid())) return false;
    FVelocityServo::FTarget Target;
    Target.Body = ID;
    Target.TargetPositionCm = FVector(12.0, 0.0, 100.0);
    Target.AngularStrength = 0.0f;
    constexpr float RecordedH = 1.0f / 30.0f;
    if (!Fixture.Publish(*this, MakeArrayView(&Target, 1), RecordedH)
        || !Fixture.Step(*this, 1.0f / 60.0f, 2) || !Fixture.CheckSamples(*this, 1)) return false;
    TestEqual(TEXT("Real scheduler invokes the same packet twice"), Fixture.Listener().GetInvocationCount(), uint64(2));
    TestNearlyEqual(TEXT("Actual collision-step dt is 1/120"), Fixture.Listener().GetLastIntegrationSeconds(), 1.0f / 120.0f, 1.0e-8f);
    TestNearlyEqual(TEXT("Recorded denominator remains 1/30"), Fixture.Listener().GetDenominatorSeconds(), RecordedH, 1.0e-8f);
    const FVelocityServo::FSample& Sample = Fixture.Listener().GetLastSamples()[0];
    // First step: V=360, X=3. Second step: V=270, X=5.25. Using actual
    // dt instead of h would incorrectly arrive at the 12 cm endpoint immediately.
    TestNearlyEqual(TEXT("Second callback sees first-step integrated position"), Sample.PositionCm,
        FVector(3.0, 0.0, 100.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Second callback sees the first velocity rewrite"), Sample.LinearBeforeCmPerSecond,
        FVector(360.0, 0.0, 0.0), VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("Second callback reuses h with the updated position"), Sample.LinearAfterCmPerSecond,
        FVector(270.0, 0.0, 0.0), VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("Both real collision steps integrate their own rewritten velocities"),
        FromJoltPosition(Fixture.Bodies().GetPosition(ID)), FVector(5.25, 0.0, 100.0), PositionToleranceCm);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoOffsetComTest,
    "Prophecy.Jolt.Servo.BodyOriginVelocityWithRotatedOffsetCOM", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoOffsetComTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Sphere = new JPH::SphereShape(0.25f);
    const JPH::RefConst<JPH::Shape> Shape = new JPH::OffsetCenterOfMassShape(Sphere.GetPtr(), JPH::Vec3(0.1f, 0.0f, 0.0f));
    const FVector Start(100.0, 200.0, 300.0);
    const FQuat Rotation(FVector::UpVector, UE_DOUBLE_HALF_PI);
    const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(Rotation, Start));
    if (!TestFalse(TEXT("Offset COM fixture body allocated"), ID.IsInvalid())) return false;
    TestNearlyEqual(TEXT("Fixture begins with a distinct rotated COM"), FromJoltPosition(Fixture.Bodies().GetCenterOfMassPosition(ID)),
        FVector(100.0, 210.0, 300.0), PositionToleranceCm);
    Fixture.Bodies().SetLinearVelocity(ID, ToJoltLinearVelocity(FVector(10.0, 20.0, 30.0)));
    Fixture.Bodies().SetAngularVelocity(ID, ToJoltAngularVelocity(FVector(0.0, 0.0, 2.0)));
    FVelocityServo::FTarget Target;
    Target.Body = ID;
    Target.TargetPositionCm = Start + FVector(20.0, 0.0, 0.0);
    Target.TargetRotation = Rotation;
    Target.AngularStrength = 0.0f;
    if (!Fixture.Publish(*this, MakeArrayView(&Target, 1), 0.1f) || !Fixture.Step(*this, 0.01f)
        || !Fixture.CheckSamples(*this, 1)) return false;
    const FVelocityServo::FSample& Sample = Fixture.Listener().GetLastSamples()[0];
    TestNearlyEqual(TEXT("Controller samples body origin instead of COM"), Sample.PositionCm, Start, PositionToleranceCm);
    TestNearlyEqual(TEXT("Controller samples the actual rotated body axes"), Sample.Rotation.RotateVector(FVector::ForwardVector),
        FVector::RightVector, 2.0e-5f);
    TestNearlyEqual(TEXT("Offset-body pre-servo V is COM velocity"), Sample.LinearBeforeCmPerSecond,
        FVector(10.0, 20.0, 30.0), VelocityToleranceCmPerSecond);
    // The COM is 10 cm along world Y and spins at +2 rad/s around Z. Its
    // rotational contribution is -20 cm/s along X, so a +200 cm/s origin
    // request requires +180 cm/s COM velocity, not +200.
    TestNearlyEqual(TEXT("Origin velocity request includes the rotated COM's tangential velocity"),
        Sample.LinearAfterCmPerSecond, FVector(180.0, 0.0, 0.0), VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("Zero angular strength preserves existing spin"), Sample.AngularAfterRadiansPerSecond,
        FVector(0.0, 0.0, 2.0), AngularToleranceRadiansPerSecond);
    TestNearlyEqual(TEXT("Integration moves COM by the rewritten COM velocity"),
        FromJoltPosition(Fixture.Bodies().GetCenterOfMassPosition(ID)), FVector(101.8, 210.0, 300.0), PositionToleranceCm);
    const FVector OriginVelocity = FromJoltLinearVelocity(Fixture.Bodies().GetPointVelocity(ID, Fixture.Bodies().GetPosition(ID)));
    TestTrue(TEXT("Spinning offset body retains a distinct body-origin point velocity"),
        (OriginVelocity - Sample.LinearAfterCmPerSecond).Size() > 19.0);
    TestNearlyEqual(TEXT("Actual body-origin point velocity follows the requested +200 cm/s"),
        OriginVelocity.X, 200.0, 0.005);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoOffsetStrengthsTest,
    "Prophecy.Jolt.Servo.OffsetCOMStrengthsAndDisabledChannels", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoOffsetStrengthsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Sphere = new JPH::SphereShape(0.25f);
    const JPH::RefConst<JPH::Shape> Shape = new JPH::OffsetCenterOfMassShape(Sphere.GetPtr(), JPH::Vec3(0.1f, 0, 0));
    struct FCase { float Linear, Angular; FVector ExpectedV; double ExpectedW; };
    // Rotated offset is +10 cm Y. Initial W=2; requested W=4 rad/s.
    // Initial V=(10,20,30); requested origin V=(200,0,0) cm/s.
    const FCase Cases[] = {
        {1, 1, FVector(160, 0, 0), 4},
        {0.25f, 0.5f, FVector(50, 15, 22.5), 3},
        {0, 1, FVector(10, 20, 30), 4},
        {1, 0, FVector(180, 0, 0), 2}
    };
    TArray<FVelocityServo::FTarget> Targets;
    for (int32 Index = 0; Index < UE_ARRAY_COUNT(Cases); ++Index)
    {
        const FVector Start(100, Index * 100, 300);
        const FQuat Rotation(FVector::UpVector, UE_DOUBLE_HALF_PI);
        const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(Rotation, Start));
        if (!TestFalse(TEXT("Offset strength body created"), ID.IsInvalid())) return false;
        Fixture.Bodies().SetLinearVelocity(ID, ToJoltLinearVelocity(FVector(10,20,30)));
        Fixture.Bodies().SetAngularVelocity(ID, JPH::Vec3(0,0,2));
        auto& Target = Targets.AddDefaulted_GetRef();
        Target.Body = ID;
        Target.TargetPositionCm = Start + FVector(20,0,0);
        Target.TargetRotation = FQuat(FVector::UpVector, 0.4) * Rotation;
        Target.LinearStrength = Cases[Index].Linear;
        Target.AngularStrength = Cases[Index].Angular;
    }
    if (!Fixture.Publish(*this, Targets, 0.1f) || !Fixture.Step(*this, 0.01f)
        || !Fixture.CheckSamples(*this, Targets.Num())) return false;
    for (int32 Index = 0; Index < Targets.Num(); ++Index)
    {
        const auto& Sample = Fixture.Listener().GetLastSamples()[Index];
        const FString Label = FString::Printf(TEXT("Offset strength case %d"), Index);
        TestNearlyEqual(Label + TEXT(" COM velocity"), Sample.LinearAfterCmPerSecond,
            Cases[Index].ExpectedV, VelocityToleranceCmPerSecond);
        TestNearlyEqual(Label + TEXT(" angular velocity"), Sample.AngularAfterRadiansPerSecond,
            FVector(0,0,Cases[Index].ExpectedW), AngularToleranceRadiansPerSecond);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoGravityTest,
    "Prophecy.Jolt.Servo.GravityAndExternalForceAfterVelocityRewrite", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoGravityTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture(JPH::Vec3(0.0f, 0.0f, -10.0f));
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    TArray<FVelocityServo::FTarget> Targets;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const FVector Start(0.0, 100.0 * Index, 100.0);
        const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(FQuat::Identity, Start), Index == 0 ? 2.0f : 8.0f);
        if (!TestFalse(TEXT("Gravity/force fixture body allocated"), ID.IsInvalid())) return false;
        // A real 6 N external force, not a delta-velocity or controller input.
        Fixture.Bodies().AddForce(ID, JPH::Vec3(6.0f, 0.0f, 0.0f));
        FVelocityServo::FTarget& Target = Targets.AddDefaulted_GetRef();
        Target.Body = ID;
        Target.TargetPositionCm = Start + FVector(20.0, 0.0, 0.0);
        Target.AngularStrength = 0.0f;
    }
    if (!Fixture.Publish(*this, Targets, 0.1f) || !Fixture.Step(*this, 0.01f)
        || !Fixture.CheckSamples(*this, Targets.Num())) return false;
    for (int32 Index = 0; Index < Targets.Num(); ++Index)
    {
        const FVelocityServo::FSample& Sample = Fixture.Listener().GetLastSamples()[Index];
        TestNearlyEqual(TEXT("Listener runs before gravity and accumulated force integration"), Sample.LinearBeforeCmPerSecond,
            FVector::ZeroVector, VelocityToleranceCmPerSecond);
        TestNearlyEqual(TEXT("Servo writes the same velocity at both masses with no gravity cancellation"), Sample.LinearAfterCmPerSecond,
            FVector(200.0, 0.0, 0.0), VelocityToleranceCmPerSecond);
        const FVector ExpectedAfterPhysics(Index == 0 ? 203.0 : 200.75, 0.0, -10.0);
        TestNearlyEqual(TEXT("Only known F/m and gravity increments follow the rewrite; no artificial servo force"),
            FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(Targets[Index].Body)),
            ExpectedAfterPhysics, VelocityToleranceCmPerSecond);
        const FVector Start(0.0, 100.0 * Index, 100.0);
        TestNearlyEqual(TEXT("The current step integrates gravity and force after the servo"),
            FromJoltPosition(Fixture.Bodies().GetPosition(Targets[Index].Body)),
            Start + ExpectedAfterPhysics * 0.01, PositionToleranceCm);
    }
    // Check the Chaos acceleration rule at two masses and integration durations,
    // including disabled linear control and changing cancellation on a live body.
    for (const float Mass : { 2.0f, 8.0f })
    for (const float H : { 0.01f, 0.005f })
    for (const float Strength : { 0.0f, 0.5f, 1.0f })
    {
        FServoFixture Case(JPH::Vec3(0.0f, 0.0f, -10.0f));
        FVelocityServo::FTarget Target;
        Target.Body = Case.Add(Shape.GetPtr(), FTransform::Identity, Mass);
        Target.LinearStrength = Strength;
        Target.AngularStrength = 0.0f;
        Target.DenominatorSeconds = H;
        for (const bool Cancel : { false, true, false })
        {
            const FVector Before = FromJoltLinearVelocity(Case.Bodies().GetLinearVelocity(Target.Body));
            Target.TargetPositionCm = FromJoltPosition(Case.Bodies().GetPosition(Target.Body));
            Target.GravityCompensationCmPerSecondSquared = Cancel ? 1000.0f : 0.0f;
            Case.Bodies().AddForce(Target.Body, JPH::Vec3(6.0f, 0.0f, 0.0f));
            if (!Case.Publish(*this, { Target }, H) || !Case.Step(*this, H)) return false;
            FVector Expected = Before * (1.0f - Strength);
            Expected.X += (600.0f / Mass) * H;
            Expected.Z -= 1000.0f * H * (1.0f - (Cancel ? Strength : 0.0f));
            TestNearlyEqual(TEXT("Runtime cancellation matches strength-scaled Chaos gravity while retaining external force"),
                FromJoltLinearVelocity(Case.Bodies().GetLinearVelocity(Target.Body)), Expected, VelocityToleranceCmPerSecond);
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoNativeCapsTest,
    "Prophecy.Jolt.Servo.NativeVelocityCaps", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoNativeCapsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform::Identity);
    if (!TestFalse(TEXT("Velocity-cap fixture body allocated"), ID.IsInvalid())) return false;
    Fixture.Bodies().SetMaxLinearVelocity(ID, 1.0f);
    Fixture.Bodies().SetMaxAngularVelocity(ID, 2.0f);
    FVelocityServo::FTarget Target;
    Target.Body = ID;
    Target.TargetPositionCm = FVector(3.0, 4.0, 0.0);
    Target.TargetRotation = FQuat(FVector::UpVector, 0.3);
    // h=.01 requests 500 cm/s along the 3:4 direction and 30 rad/s about Z.
    // Native setters cap those to 100 cm/s and 2 rad/s, preserving direction.
    if (!Fixture.Publish(*this, MakeArrayView(&Target, 1), 0.01f)
        || !Fixture.Step(*this, 0.01f) || !Fixture.CheckSamples(*this, 1)) return false;
    const FVelocityServo::FSample& Sample = Fixture.Listener().GetLastSamples()[0];
    TestNearlyEqual(TEXT("Oversized linear request is clamped by the native setter"),
        Sample.LinearAfterCmPerSecond, FVector(60.0, 80.0, 0.0), VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("Oversized angular request is clamped by the native setter"),
        Sample.AngularAfterRadiansPerSecond, FVector(0.0, 0.0, 2.0), AngularToleranceRadiansPerSecond);
    TestNearlyEqual(TEXT("Current step integrates the capped linear velocity"),
        FromJoltPosition(Fixture.Bodies().GetPosition(ID)), FVector(0.6, 0.8, 0.0), PositionToleranceCm);
    TestNearlyEqual(TEXT("Linear cap remains unchanged"), Fixture.Bodies().GetMaxLinearVelocity(ID), 1.0f, 1.0e-7f);
    TestNearlyEqual(TEXT("Angular cap remains unchanged"), Fixture.Bodies().GetMaxAngularVelocity(ID), 2.0f, 1.0e-7f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoWakeGravityTest,
    "Prophecy.Jolt.Servo.ConditionalWakeIncludesFirstStepGravity", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoWakeGravityTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture(JPH::Vec3(0.0f, 0.0f, -10.0f));
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    const FVector Start(0.0, 0.0, 100.0);
    const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(FQuat::Identity, Start));
    if (!TestFalse(TEXT("Sleeping target body allocated"), ID.IsInvalid())) return false;
    Fixture.Bodies().DeactivateBody(ID);
    if (!TestFalse(TEXT("All fixture bodies start asleep"), Fixture.Bodies().IsActive(ID))) return false;
    FVelocityServo::FTarget Target;
    Target.Body = ID;
    Target.TargetPositionCm = Start + FVector(20.0, 0.0, 0.0);
    Target.AngularStrength = 0.0f;
    if (!Fixture.Publish(*this, MakeArrayView(&Target, 1), 0.1f)
        || !Fixture.Step(*this, 0.01f) || !Fixture.CheckSamples(*this, 1)) return false;
    TestEqual(TEXT("Registered listener runs for the newly awakened target"), Fixture.Listener().GetInvocationCount(), uint64(1));
    const FVelocityServo::FSample& Sample = Fixture.Listener().GetLastSamples()[0];
    TestNearlyEqual(TEXT("Activation preparation changes no velocity"), Sample.LinearBeforeCmPerSecond,
        FVector::ZeroVector, VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("Listener writes the target velocity"), Sample.LinearAfterCmPerSecond,
        FVector(200.0, 0.0, 0.0), VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("The first awakened step includes gravity"),
        FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(ID)), FVector(200.0, 0.0, -10.0), VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("The first awakened step integrates both target velocity and gravity"),
        FromJoltPosition(Fixture.Bodies().GetPosition(ID)), FVector(2.0, 0.0, 99.9), PositionToleranceCm);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoNoWakeTest,
    "Prophecy.Jolt.Servo.ZeroAndDisabledTargetsStayAsleep", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoNoWakeTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture(JPH::Vec3(0.0f, 0.0f, -10.0f));
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    TArray<FVelocityServo::FTarget> Targets;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const FVector Start(0.0, 100.0 * Index, 100.0);
        const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(FQuat::Identity, Start));
        if (!TestFalse(TEXT("No-wake fixture body allocated"), ID.IsInvalid())) return false;
        Fixture.Bodies().DeactivateBody(ID);
        FVelocityServo::FTarget& Target = Targets.AddDefaulted_GetRef();
        Target.Body = ID;
        Target.TargetPositionCm = Index == 0 ? Start : Start + FVector(100.0, 0.0, 0.0);
        Target.TargetRotation = Index == 0 ? FQuat::Identity : FQuat(FVector::UpVector, 0.5);
        Target.LinearStrength = Target.AngularStrength = Index == 0 ? 1.0f : 0.0f;
    }
    if (!Fixture.Publish(*this, Targets, 0.1f) || !Fixture.Step(*this, 0.01f)) return false;
    // Pinned Jolt still invokes registered step listeners when every body is asleep.
    TestEqual(TEXT("All-sleeping Update invokes the listener"), Fixture.Listener().GetInvocationCount(), uint64(1));
    TestEqual(TEXT("Zero/no-write sleeping candidates remain valid"), Fixture.Listener().GetInvalidBodyCount(), uint64(0));
    if (!TestEqual(TEXT("Both sleeping targets have samples"), Fixture.Listener().GetLastSamples().Num(), 2)) return false;
    for (int32 Index = 0; Index < Targets.Num(); ++Index)
    {
        TestTrue(TEXT("Sleeping target sample is valid"), Fixture.Listener().GetLastSamples()[Index].bValid);
        TestFalse(TEXT("Zero and disabled inputs do not wake bodies"), Fixture.Bodies().IsActive(Targets[Index].Body));
        TestNearlyEqual(TEXT("Sleeping bodies do not start falling from an unconditional wake"),
            FromJoltPosition(Fixture.Bodies().GetPosition(Targets[Index].Body)), FVector(0.0, 100.0 * Index, 100.0), PositionToleranceCm);
        TestNearlyEqual(TEXT("Sleeping bodies retain zero linear velocity"),
            FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(Targets[Index].Body)), FVector::ZeroVector, VelocityToleranceCmPerSecond);
        TestNearlyEqual(TEXT("Sleeping bodies retain zero angular velocity"),
            FromJoltAngularVelocity(Fixture.Bodies().GetAngularVelocity(Targets[Index].Body)), FVector::ZeroVector, AngularToleranceRadiansPerSecond);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoPacketPreflightTest,
    "Prophecy.Jolt.Servo.RejectedAndEmptyPacketsPreserveBodyState", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoPacketPreflightTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    TArray<FVelocityServo::FTarget> Accepted;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        const FVector Start(0.0, 100.0 * Index, 100.0);
        const JPH::BodyID ID = Fixture.Add(Shape.GetPtr(), FTransform(FQuat::Identity, Start));
        if (!TestFalse(TEXT("Preflight fixture body allocated"), ID.IsInvalid())) return false;
        auto& Target = Accepted.AddDefaulted_GetRef();
        Target.Body = ID;
        Target.TargetPositionCm = Start + FVector(30.0, 0.0, 0.0);
        Target.LinearStrength = 1.0f;
        Target.AngularStrength = 0.0f;
        Target.DenominatorSeconds = Index == 0 ? 0.1f : 0.2f;
    }
    FString Error;
    if (!TestTrue(TEXT("Accept two explicit per-target denominators"), Fixture.Listener().PublishPerTarget(Accepted, Error))) return false;
    const float NaN = std::numeric_limits<float>::quiet_NaN();
    const float Infinity = std::numeric_limits<float>::infinity();
    const TCHAR* Cases[] = { TEXT("invalid body"), TEXT("duplicate body"), TEXT("NaN position"), TEXT("infinite position"),
        TEXT("unnormalized rotation"), TEXT("NaN rotation"), TEXT("negative linear strength"), TEXT("infinite linear strength"),
        TEXT("negative angular strength"), TEXT("NaN angular strength"), TEXT("zero denominator"), TEXT("NaN denominator"),
        TEXT("infinite denominator"), TEXT("negative denominator"), TEXT("negative trajectory duration"),
        TEXT("NaN trajectory duration"), TEXT("infinite trajectory duration"), TEXT("NaN trajectory start"),
        TEXT("infinite trajectory start"), TEXT("unnormalized trajectory start rotation"), TEXT("NaN trajectory start rotation") };
    constexpr float StepSeconds = 0.01f;
    for (int32 CaseIndex = 0; CaseIndex < UE_ARRAY_COUNT(Cases); ++CaseIndex)
    {
        TArray<FVelocityServo::FTarget> Rejected = Accepted;
        // A valid but changed prefix must not leak into the accepted packet when the later row fails.
        Rejected[0].TargetPositionCm.X += 1000.0;
        Rejected[0].DenominatorSeconds = 0.7f;
        auto& Invalid = Rejected[1];
        switch (CaseIndex)
        {
        case 0: Invalid.Body = JPH::BodyID(); break;
        case 1: Invalid.Body = Accepted[0].Body; break;
        case 2: Invalid.TargetPositionCm.X = NaN; break;
        case 3: Invalid.TargetPositionCm.X = Infinity; break;
        case 4: Invalid.TargetRotation.W = 2.0; break;
        case 5: Invalid.TargetRotation.X = NaN; break;
        case 6: Invalid.LinearStrength = -1.0f; break;
        case 7: Invalid.LinearStrength = Infinity; break;
        case 8: Invalid.AngularStrength = -1.0f; break;
        case 9: Invalid.AngularStrength = NaN; break;
        case 10: Invalid.DenominatorSeconds = 0.0f; break;
        case 11: Invalid.DenominatorSeconds = NaN; break;
        case 12: Invalid.DenominatorSeconds = Infinity; break;
        case 13: Invalid.DenominatorSeconds = -1.0f; break;
        case 14: Invalid.TrajectoryDurationSeconds = -1.0f; break;
        case 15: Invalid.TrajectoryDurationSeconds = NaN; break;
        case 16: Invalid.TrajectoryDurationSeconds = Infinity; break;
        case 17: Invalid.TrajectoryDurationSeconds = 0.1f; Invalid.StartPositionCm.X = NaN; break;
        case 18: Invalid.TrajectoryDurationSeconds = 0.1f; Invalid.StartPositionCm.X = Infinity; break;
        case 19: Invalid.TrajectoryDurationSeconds = 0.1f; Invalid.StartRotation.W = 2.0; break;
        case 20: Invalid.TrajectoryDurationSeconds = 0.1f; Invalid.StartRotation.X = NaN; break;
        }
        const FString Label(Cases[CaseIndex]);
        if (!TestFalse(Label + TEXT(" is rejected by the validated native entry point"), Fixture.Listener().PublishPerTarget(Rejected, Error))
            || !TestFalse(Label + TEXT(" returns a reason"), Error.IsEmpty())) return false;
        FVector Positions[2];
        for (int32 Index = 0; Index < 2; ++Index)
            Positions[Index] = FromJoltPosition(Fixture.Bodies().GetPosition(Accepted[Index].Body));
        if (!Fixture.Step(*this, StepSeconds) || !Fixture.CheckSamples(*this, 2)) return false;
        TestEqual(Label + TEXT(" preserves the mixed-h diagnostic"), Fixture.Listener().GetDenominatorSeconds(), 0.0f);
        for (int32 Index = 0; Index < 2; ++Index)
        {
            // Unit strength and zero drag: the unchanged endpoint/h is the analytic velocity.
            const FVector ExpectedVelocity = (Accepted[Index].TargetPositionCm - Positions[Index]) / Accepted[Index].DenominatorSeconds;
            TestNearlyEqual(Label + TEXT(" preserves the old endpoint and h for both rows"),
                Fixture.Listener().GetLastSamples()[Index].LinearAfterCmPerSecond, ExpectedVelocity, VelocityToleranceCmPerSecond);
            TestNearlyEqual(Label + TEXT(" preserves actual integrated body motion"),
                FromJoltPosition(Fixture.Bodies().GetPosition(Accepted[Index].Body)),
                Positions[Index] + ExpectedVelocity * StepSeconds, PositionToleranceCm);
        }
    }
    const uint64 PreviousInvocations = Fixture.Listener().GetInvocationCount();
    const FVector PositionBeforeClear = FromJoltPosition(Fixture.Bodies().GetPosition(Accepted[0].Body));
    const FVector VelocityBeforeClear = FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(Accepted[0].Body));
    const TArray<FVelocityServo::FTarget> Empty;
    if (!TestTrue(TEXT("Empty native packet is accepted"), Fixture.Listener().PublishPerTarget(Empty, Error))
        || !TestTrue(TEXT("Accepted empty packet clears a previous rejection reason"), Error.IsEmpty())
        || !Fixture.Step(*this, StepSeconds)) return false;
    TestTrue(TEXT("Empty native packet exposes no stale samples"), Fixture.Listener().GetLastSamples().IsEmpty());
    TestEqual(TEXT("Empty native packet produces no servo invocation"), Fixture.Listener().GetInvocationCount(), PreviousInvocations);
    TestNearlyEqual(TEXT("Removing control keeps existing body velocity"),
        FromJoltLinearVelocity(Fixture.Bodies().GetLinearVelocity(Accepted[0].Body)), VelocityBeforeClear, VelocityToleranceCmPerSecond);
    TestNearlyEqual(TEXT("Removing control lets the body coast"), FromJoltPosition(Fixture.Bodies().GetPosition(Accepted[0].Body)),
        PositionBeforeClear + VelocityBeforeClear * StepSeconds, PositionToleranceCm);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoChangingSubstepsTest,
    "Prophecy.Jolt.Servo.ChangingSubsteps", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoChangingSubstepsTest::RunTest(const FString&)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    TArray<FVelocityServo::FTarget> Targets;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        auto& Target = Targets.AddDefaulted_GetRef();
        Target.Body = Fixture.Add(Shape, FTransform(FVector(0.0, Index * 100.0, 0.0)));
        Target.LinearStrength = 1.0f;
        Target.AngularStrength = 0.0f;
        Target.TargetPositionCm = FVector(0.0, Index * 100.0, 0.0);
    }
    double EndpointX = 0.0, MaximumOldLag = 0.0, MaximumCorrectedError = 0.0;
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        // Measured adjacent frame durations from the camera-relative capture.
        const float Dt = Frame % 2 == 0 ? 0.0170364007f : 0.0166667998f;
        const int32 Steps = Frame % 2 == 0 ? 2 : 1;
        EndpointX += 180.0 * Dt;
        for (int32 Index = 0; Index < 2; ++Index)
        {
            Targets[Index].TargetPositionCm.X = EndpointX;
            Targets[Index].DenominatorSeconds = Index == 0 ? FMath::Min(Dt, 0.016667f) : Dt / float(Steps);
        }
        FString Error;
        if (!TestTrue(TEXT("Publish old and corrected timing side by side"), Fixture.Listener().PublishPerTarget(Targets, Error))
            || !Fixture.Step(*this, Dt, Steps)) return false;
        MaximumOldLag = FMath::Max(MaximumOldLag, EndpointX - FromJoltPosition(Fixture.Bodies().GetPosition(Targets[0].Body)).X);
        MaximumCorrectedError = FMath::Max(MaximumCorrectedError,
            FMath::Abs(EndpointX - FromJoltPosition(Fixture.Bodies().GetPosition(Targets[1].Body)).X));
    }
    TestTrue(TEXT("Negative control reproduces more than 0.7 cm alternating lag"), MaximumOldLag > 0.7);
    TestTrue(TEXT("Actual step duration removes alternating endpoint lag"), MaximumCorrectedError < PositionToleranceCm);
    AddInfo(FString::Printf(TEXT("120 moving frames: old maximum lag %.6f cm; corrected maximum error %.6f cm"), MaximumOldLag, MaximumCorrectedError));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltServoAuthoredTrajectoryTest,
    "Prophecy.Jolt.Servo.AuthoredTrajectorySubsteps", ProphecyJolt::VelocityServoTests::Flags)

bool FProphecyJoltServoAuthoredTrajectoryTest::RunTest(const FString&)
{
    using namespace ProphecyJolt;
    using namespace ProphecyJolt::Conversions;
    using namespace ProphecyJolt::VelocityServoTests;
    if (!RuntimeReady(*this)) return false;
    FServoFixture Fixture;
    const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
    TArray<FVelocityServo::FTarget> Targets;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        auto& Target = Targets.AddDefaulted_GetRef();
        Target.Body = Fixture.Add(Shape, FTransform(FVector(0.0, Index * 100.0, 0.0)));
        if (!TestFalse(TEXT("Trajectory fixture body allocated"), Target.Body.IsInvalid())) return false;
    }
    double Time = 0.0;
    constexpr double Speed = 180.0, AngularSpeed = 0.75;
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        const float Dt = Frame % 2 == 0 ? 0.0170364007f : 0.0166667998f;
        const int32 Steps = Frame % 2 == 0 ? 2 : 1;
        for (int32 Index = 0; Index < 2; ++Index)
        {
            auto& Target = Targets[Index];
            Target.StartPositionCm = FVector(Speed * Time, Index * 100.0, 0.0);
            Target.TargetPositionCm = FVector(Speed * (Time + Dt), Index * 100.0, 0.0);
            Target.StartRotation = FQuat(FVector::UpVector, AngularSpeed * Time);
            Target.TargetRotation = FQuat(FVector::UpVector, AngularSpeed * (Time + Dt));
            if (Frame % 2 == 0) Target.TargetRotation = Target.TargetRotation * -1.0;
            Target.DenominatorSeconds = Dt / float(Steps);
            Target.TrajectoryDurationSeconds = Index == 0 ? 0.0f : Dt;
        }
        FString Error;
        if (!TestTrue(TEXT("Publish static endpoint negative control and authored trajectory"),
                Fixture.Listener().PublishPerTarget(Targets, Error))
            || !Fixture.Step(*this, Dt, Steps) || !Fixture.CheckSamples(*this, 2)) return false;
        Time += Dt;
        const auto& Samples = Fixture.Listener().GetLastSamples();
        TestNearlyEqual(TEXT("Trajectory integrates the constant-speed endpoint"),
            FromJoltPosition(Fixture.Bodies().GetPosition(Targets[1].Body)),
            Targets[1].TargetPositionCm, PositionToleranceCm);
        TestNearlyEqual(TEXT("Trajectory retains constant final linear velocity at either step count"),
            Samples[1].LinearAfterCmPerSecond, FVector(Speed, 0.0, 0.0), 0.005f);
        TestNearlyEqual(TEXT("Trajectory retains angular velocity including opposite quaternion signs"),
            Samples[1].AngularAfterRadiansPerSecond, FVector(0.0, 0.0, AngularSpeed), 0.001f);
        TestTrue(TEXT("Trajectory reaches the authored rotation without an endpoint snap"),
            FromJoltRotation(Fixture.Bodies().GetRotation(Targets[1].Body))
                .GetNormalized().AngularDistance(Targets[1].TargetRotation) < 2.0e-5);
        TestNearlyEqual(TEXT("Static negative control also has a deceptively correct position"),
            FromJoltPosition(Fixture.Bodies().GetPosition(Targets[0].Body)),
            Targets[0].TargetPositionCm, PositionToleranceCm);
        TestNearlyEqual(TEXT("Static negative control alternates final velocity between moving and stopped"),
            Samples[0].LinearAfterCmPerSecond, FVector(Steps == 1 ? Speed : 0.0, 0.0, 0.0), 0.005f);
    }
    // Split one publication across separate Updates: inspect both half-step
    // velocities, then verify an additional Update holds rather than replays it.
    Targets.RemoveAt(0);
    auto& Target = Targets[0];
    constexpr float Duration = 0.02f;
    Target.StartPositionCm = Target.TargetPositionCm;
    Target.StartRotation = Target.TargetRotation;
    Target.TargetPositionCm += FVector(Speed * Duration, 0.0, 0.0);
    Target.TargetRotation = FQuat(FVector::UpVector, AngularSpeed * (Time + Duration));
    Target.TrajectoryDurationSeconds = Duration;
    FString Error;
    if (!TestTrue(TEXT("Publish two-update trajectory"), Fixture.Listener().PublishPerTarget(Targets, Error))) return false;
    for (int32 Half = 0; Half < 2; ++Half)
    {
        if (!Fixture.Step(*this, Duration * 0.5f)) return false;
        TestNearlyEqual(TEXT("Each individual trajectory substep has physical movement velocity"),
            Fixture.Listener().GetLastSamples()[0].LinearAfterCmPerSecond,
            FVector(Speed, 0.0, 0.0), 0.005f);
        TestNearlyEqual(TEXT("Each individual trajectory substep has authored angular velocity"),
            Fixture.Listener().GetLastSamples()[0].AngularAfterRadiansPerSecond,
            FVector(0.0, 0.0, AngularSpeed), 0.001f);
    }
    if (!Fixture.Step(*this, Duration)) return false;
    TestNearlyEqual(TEXT("A consumed trajectory does not restart without publication"),
        Fixture.Listener().GetLastSamples()[0].LinearAfterCmPerSecond, FVector::ZeroVector, 0.005f);
    TestNearlyEqual(TEXT("A consumed trajectory holds its endpoint"),
        FromJoltPosition(Fixture.Bodies().GetPosition(Target.Body)), Target.TargetPositionCm, PositionToleranceCm);
    // First sample can equal a sleeping body's position while a later sample
    // moves. It must join Jolt's active snapshot before the Update starts.
    const FVector SleepingPosition = FromJoltPosition(Fixture.Bodies().GetPosition(Target.Body));
    Target.StartPositionCm = SleepingPosition - FVector(1.8, 0.0, 0.0);
    Target.TargetPositionCm = SleepingPosition + FVector(1.8, 0.0, 0.0);
    Target.AngularStrength = 0.0f;
    Fixture.Bodies().DeactivateBody(Target.Body);
    if (!TestTrue(TEXT("Publish future motion with a stationary first substep"),
            Fixture.Listener().PublishPerTarget(Targets, Error)) || !Fixture.Step(*this, Duration, 2)) return false;
    TestTrue(TEXT("Pending authored movement wakes before the active-body snapshot"), Fixture.Bodies().IsActive(Target.Body));
    TestNearlyEqual(TEXT("The second substep moves the previously sleeping body"),
        FromJoltPosition(Fixture.Bodies().GetPosition(Target.Body)), Target.TargetPositionCm, PositionToleranceCm);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
