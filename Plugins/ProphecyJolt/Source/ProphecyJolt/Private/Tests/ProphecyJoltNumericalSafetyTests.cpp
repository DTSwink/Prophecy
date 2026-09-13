#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include <atomic>
#include <cmath>
#include <limits>

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemThreadPool.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/FixedConstraint.h>
#include <Jolt/Physics/LargeIslandSplitter.h>
#include <Jolt/Physics/PhysicsStepListener.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::NumericalSafetyTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
static_assert(JPH::Body::cProphecyNumericalSafetyVersion == 1, "Tests require the native correction guard.");

bool RuntimeReady(FAutomationTestBase& Test)
{
    return Test.TestTrue(TEXT("Compatible Jolt runtime"), JPH::VerifyJoltVersionID())
        && Test.TestNotNull(TEXT("Runtime owns Jolt factory"), JPH::Factory::sInstance);
}

class FOneLayer final : public JPH::BroadPhaseLayerInterface
{
public:
    virtual JPH::uint GetNumBroadPhaseLayers() const override { return 1; }
    virtual JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer) const override { return JPH::BroadPhaseLayer(0); }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
    virtual const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer) const override { return "NumericalSafetyFixture"; }
#endif
};
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

class FStepCounter final : public JPH::PhysicsStepListener
{
public:
    virtual void OnStep(const JPH::PhysicsStepListenerContext&) override { Calls.fetch_add(1); }
    std::atomic<uint32> Calls { 0 };
};

struct FSolverTelemetry
{
    std::atomic<uint32> VelocityCalls { 0 };
    std::atomic<uint32> PositionCalls { 0 };
    std::atomic<uint32> SplitCalls { 0 };
    std::atomic<uint32> Injections { 0 };
    std::atomic<bool> RejectedBeforeWrite { false };
};

enum class EInjection : uint8
{
    None, PositionInfinity, PositionBroadPhaseOverflow,
    LinearNaN, LinearInfinity, LinearOverflow,
    AngularNaN, AngularInfinity, AngularOverflow
};

// FixedConstraint is final. This test constraint forwards its real solve and island
// behavior, inserting one invalid correction in a real position or velocity job.
// No production bypass or test-only solver hook is needed.
class FInjectingFixedConstraint final : public JPH::TwoBodyConstraint
{
public:
    FInjectingFixedConstraint(JPH::Body& A, JPH::Body& B, const JPH::FixedConstraintSettings& Settings,
        FSolverTelemetry& InTelemetry, EInjection InInjection)
        : JPH::TwoBodyConstraint(A, B, Settings), Delegate(new JPH::FixedConstraint(A, B, Settings)),
          Telemetry(InTelemetry), Injection(InInjection) {}

    virtual JPH::EConstraintSubType GetSubType() const override { return JPH::EConstraintSubType::User1; }
    virtual void NotifyShapeChanged(const JPH::BodyID& ID, JPH::Vec3Arg Delta) override { Delegate->NotifyShapeChanged(ID, Delta); }
    virtual void ResetWarmStart() override { Delegate->ResetWarmStart(); }
    virtual void SetupVelocityConstraint(float Dt) override { Delegate->SetupVelocityConstraint(Dt); }
    virtual void WarmStartVelocityConstraint(float Ratio) override { Delegate->WarmStartVelocityConstraint(Ratio); }
    virtual bool SolveVelocityConstraint(float Dt) override
    {
        Telemetry.VelocityCalls.fetch_add(1);
        uint32 ExpectedInjections = 0;
        if (Injection >= EInjection::LinearNaN && Telemetry.Injections.compare_exchange_strong(ExpectedInjections, 1))
        {
            const JPH::Vec3 LinearBefore = mBody2->GetLinearVelocity();
            const JPH::Vec3 AngularBefore = mBody2->GetAngularVelocity();
            float Invalid = std::numeric_limits<float>::infinity();
            if (Injection == EInjection::LinearNaN || Injection == EInjection::AngularNaN)
                Invalid = std::numeric_limits<float>::quiet_NaN();
            else if (Injection == EInjection::LinearOverflow || Injection == EInjection::AngularOverflow)
                Invalid = 1.0e30f;
            if (Injection >= EInjection::AngularNaN)
                mBody2->GetMotionProperties()->ApplyAngularVelocityStep(JPH::Vec3(0.0f, Invalid, 0.0f));
            else
                mBody2->GetMotionProperties()->ApplyLinearVelocityStep(JPH::Vec3(0.0f, Invalid, 0.0f));
            Telemetry.RejectedBeforeWrite.store(mBody2->HasNumericalFailure()
                && mBody2->GetLinearVelocity() == LinearBefore && mBody2->GetAngularVelocity() == AngularBefore);
            return true;
        }
        return Delegate->SolveVelocityConstraint(Dt);
    }
    virtual bool SolvePositionConstraint(float Dt, float Baumgarte) override
    {
        Telemetry.PositionCalls.fetch_add(1);
        uint32 ExpectedInjections = 0;
        if ((Injection == EInjection::PositionInfinity || Injection == EInjection::PositionBroadPhaseOverflow)
            && Telemetry.Injections.compare_exchange_strong(ExpectedInjections, 1))
        {
            const JPH::Quat Before = mBody2->GetRotation();
            const JPH::RVec3 PositionBefore = mBody2->GetCenterOfMassPosition();
            if (Injection == EInjection::PositionBroadPhaseOverflow)
                mBody2->AddPositionStep(JPH::Vec3(1.0e16f, 0.0f, 0.0f));
            else
                mBody2->AddRotationStep(JPH::Vec3(std::numeric_limits<float>::infinity(), 0.0f, 0.0f));
            Telemetry.RejectedBeforeWrite.store(mBody2->HasNumericalFailure() && mBody2->GetRotation() == Before
                && mBody2->GetCenterOfMassPosition() == PositionBefore);
            return true;
        }
        return Delegate->SolvePositionConstraint(Dt, Baumgarte);
    }
    virtual JPH::uint BuildIslandSplits(JPH::LargeIslandSplitter& Splitter) const override
    {
        Telemetry.SplitCalls.fetch_add(1);
        return JPH::TwoBodyConstraint::BuildIslandSplits(Splitter);
    }
    virtual JPH::Mat44 GetConstraintToBody1Matrix() const override { return Delegate->GetConstraintToBody1Matrix(); }
    virtual JPH::Mat44 GetConstraintToBody2Matrix() const override { return Delegate->GetConstraintToBody2Matrix(); }
    virtual JPH::Ref<JPH::ConstraintSettings> GetConstraintSettings() const override { return Delegate->GetConstraintSettings(); }
    virtual void SaveState(JPH::StateRecorder& State) const override { Delegate->SaveState(State); }
    virtual void RestoreState(JPH::StateRecorder& State) override { Delegate->RestoreState(State); }
#ifdef JPH_DEBUG_RENDERER
    virtual void DrawConstraint(JPH::DebugRenderer* Renderer) const override { Delegate->DrawConstraint(Renderer); }
#endif

private:
    JPH::Ref<JPH::FixedConstraint> Delegate;
    FSolverTelemetry& Telemetry;
    EInjection Injection;
};

class FNativeFixture final
{
public:
    FNativeFixture() : Temp(16 * 1024 * 1024),
        Jobs(MakeUnique<JPH::JobSystemThreadPool>(JPH::cMaxPhysicsJobs, JPH::cMaxPhysicsBarriers, 2))
    {
        Physics.Init(256, 0, 512, 512, Layers, BroadPairs, ObjectPairs);
        Physics.SetGravity(JPH::Vec3::sZero());
        JPH::PhysicsSettings Settings = Physics.GetPhysicsSettings();
        Settings.mNumVelocitySteps = 2;
        Settings.mNumPositionSteps = 2;
        Settings.mUseLargeIslandSplitter = true;
        Physics.SetPhysicsSettings(Settings);
        Physics.AddStepListener(&Steps);
    }
    ~FNativeFixture()
    {
        Jobs.Reset();
        Physics.RemoveStepListener(&Steps);
        for (const JPH::Ref<JPH::Constraint>& Constraint : Constraints) Physics.RemoveConstraint(Constraint.GetPtr());
        Constraints.Reset();
        for (JPH::Body* Body : Bodies)
        {
            Physics.GetBodyInterface().RemoveBody(Body->GetID());
            Physics.GetBodyInterface().DestroyBody(Body->GetID());
        }
    }
    JPH::Body* Add(JPH::RVec3Arg Position = JPH::RVec3::sZero(), JPH::QuatArg Rotation = JPH::Quat::sIdentity())
    {
        const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
        return AddShape(Shape.GetPtr(), Position, Rotation);
    }
    JPH::Body* AddShape(const JPH::Shape* Shape, JPH::RVec3Arg Position, JPH::QuatArg Rotation, bool bUnitInertia = false)
    {
        JPH::BodyCreationSettings Settings(Shape, Position, Rotation, JPH::EMotionType::Dynamic, 0);
        if (bUnitInertia)
        {
            // The boundary fixture tests transforms, independently of enormous shape mass.
            Settings.mOverrideMassProperties = JPH::EOverrideMassProperties::MassAndInertiaProvided;
            Settings.mMassPropertiesOverride.mMass = 1.0f;
            Settings.mMassPropertiesOverride.mInertia = JPH::Mat44::sIdentity();
        }
        Settings.mAllowSleeping = false;
        Settings.mLinearDamping = Settings.mAngularDamping = 0.0f;
        JPH::Body* Body = Physics.GetBodyInterface().CreateBody(Settings);
        if (Body)
        {
            Bodies.Add(Body);
            Physics.GetBodyInterface().AddBody(Body->GetID(), JPH::EActivation::Activate);
        }
        return Body;
    }
    void Connect(JPH::Body& A, JPH::Body& B, FSolverTelemetry& Telemetry, EInjection Injection)
    {
        JPH::FixedConstraintSettings Settings;
        Settings.mAutoDetectPoint = true;
        JPH::Ref<JPH::Constraint> Constraint = new FInjectingFixedConstraint(A, B, Settings, Telemetry, Injection);
        Physics.AddConstraint(Constraint.GetPtr());
        Constraints.Add(Constraint);
    }
    JPH::EPhysicsUpdateError Step(int32 CollisionSteps)
    {
        return Physics.Update(1.0f / 60.0f, CollisionSteps, &Temp, Jobs.Get());
    }

    FOneLayer Layers;
    FNoObjectPairs ObjectPairs;
    FNoBroadPairs BroadPairs;
    JPH::TempAllocatorImpl Temp;
    JPH::PhysicsSystem Physics;
    FStepCounter Steps;
    TUniquePtr<JPH::JobSystemThreadPool> Jobs;
    TArray<JPH::Body*> Bodies;
    TArray<JPH::Ref<JPH::Constraint>> Constraints;
};

bool FinitePose(const JPH::Body& Body)
{
    const JPH::RVec3 Position = Body.GetCenterOfMassPosition();
    const JPH::Quat Rotation = Body.GetRotation();
    return std::isfinite(Position.GetX()) && std::isfinite(Position.GetY()) && std::isfinite(Position.GetZ())
        && std::isfinite(Rotation.GetX()) && std::isfinite(Rotation.GetY())
        && std::isfinite(Rotation.GetZ()) && std::isfinite(Rotation.GetW()) && Rotation.IsNormalized();
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRotationSafetyTest,
    "Prophecy.Jolt.NumericalSafety.RotationCorrections", ProphecyJolt::NumericalSafetyTests::Flags)

bool FProphecyJoltRotationSafetyTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::NumericalSafetyTests;
    if (!RuntimeReady(*this)) return false;
    FNativeFixture Fixture;
    const JPH::Quat Initial = JPH::Quat::sRotation(JPH::Vec3(0.2f, 0.8f, -0.3f).Normalized(), 0.7f);
    const JPH::Vec3 Axis = JPH::Vec3(0.3f, -0.4f, 0.5f).Normalized();
    for (const float Angle : { 0.0f, 1.0e-7f, 0.003f, 0.8f, 2.3f, 10.0f })
    {
        for (const bool bSubtract : { false, true })
        {
            JPH::Body* Body = Fixture.Add(JPH::RVec3::sZero(), Initial);
            if (!TestNotNull(TEXT("Create ordinary correction body"), Body)) return false;
            const JPH::Vec3 Step = Axis * Angle;
            const float Length = Step.Length();
            const JPH::Quat Expected = Length <= 1.0e-6f ? Initial
                : (JPH::Quat::sRotation(Step / Length, bSubtract ? -Length : Length) * Initial).Normalized();
            if (bSubtract) Body->SubRotationStep(Step); else Body->AddRotationStep(Step);
            TestTrue(TEXT("Ordinary correction preserves original native quaternion result"), Body->GetRotation() == Expected);
            TestFalse(TEXT("Ordinary correction does not fault"), Body->HasNumericalFailure());
        }
    }
    for (const float Magnitude : { 1.0e10f, 1.0e30f })
    {
        for (const bool bSubtract : { false, true })
        {
            JPH::Body* Body = Fixture.Add(JPH::RVec3::sZero(), Initial);
            if (!TestNotNull(TEXT("Create huge finite rotation body"), Body)) return false;
            const JPH::Vec3 Step(Magnitude, -0.5f * Magnitude, 0.25f * Magnitude);
            if (bSubtract) Body->SubRotationStep(Step); else Body->AddRotationStep(Step);
            TestTrue(TEXT("Huge finite angular correction leaves finite normalized pose"), FinitePose(*Body));
            TestFalse(TEXT("Huge finite angular correction remains supported"), Body->HasNumericalFailure());
            TestTrue(TEXT("Huge finite angular correction is applied, not discarded"),
                FMath::Abs(Body->GetRotation().Dot(Initial)) < 0.9999f);
            if (bSubtract) Body->AddRotationStep(Step); else Body->SubRotationStep(Step);
            TestTrue(TEXT("Opposite huge angular corrections cancel"),
                FMath::Abs(Body->GetRotation().Dot(Initial)) > 1.0f - 2.0e-6f);
        }
    }
    for (const float Invalid : { std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity(),
        -std::numeric_limits<float>::infinity() })
    {
        for (const bool bSubtract : { false, true })
        {
            JPH::Body* Body = Fixture.Add(JPH::RVec3(1.0f, 2.0f, 3.0f), Initial);
            if (!TestNotNull(TEXT("Create invalid angular correction body"), Body)) return false;
            const JPH::RVec3 BeforePosition = Body->GetCenterOfMassPosition();
            if (bSubtract) Body->SubRotationStep(JPH::Vec3(0.0f, Invalid, 0.0f));
            else Body->AddRotationStep(JPH::Vec3(0.0f, Invalid, 0.0f));
            TestTrue(TEXT("Invalid angular correction faults before writing rotation"), Body->HasNumericalFailure());
            TestTrue(TEXT("Invalid angular correction preserves full pose"),
                Body->GetRotation() == Initial && Body->GetCenterOfMassPosition() == BeforePosition);
            Body->AddRotationStep(JPH::Vec3(0.1f, 0.2f, 0.3f));
            TestTrue(TEXT("Faulted body rejects subsequent angular correction"), Body->GetRotation() == Initial);
        }
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPositionSafetyTest,
    "Prophecy.Jolt.NumericalSafety.PositionCorrections", ProphecyJolt::NumericalSafetyTests::Flags)

bool FProphecyJoltPositionSafetyTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::NumericalSafetyTests;
    if (!RuntimeReady(*this)) return false;
    FNativeFixture Fixture;
    const JPH::RVec3 Initial(1.0f, 2.0f, 3.0f);
    JPH::Body* Ordinary = Fixture.Add(Initial);
    if (!TestNotNull(TEXT("Create ordinary translation body"), Ordinary)) return false;
    const JPH::Vec3 Step(0.25f, -0.5f, 0.125f);
    Ordinary->AddPositionStep(Step);
    TestTrue(TEXT("Ordinary position correction is unchanged"), Ordinary->GetCenterOfMassPosition() == Initial + Step);
    Ordinary->SubPositionStep(Step);
    TestTrue(TEXT("Opposite ordinary translation cancels"), Ordinary->GetCenterOfMassPosition() == Initial);
    TestFalse(TEXT("Ordinary translation does not fault"), Ordinary->HasNumericalFailure());
    TestTrue(TEXT("Broad-phase regression exceeds world bounds without float norm overflow"),
        std::isfinite(JPH::Vec3(1.0e16f, 0.0f, 0.0f).LengthSq()));
    for (const float Invalid : { std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity(),
        -std::numeric_limits<float>::infinity(), 1.0e30f, 1.0e16f })
    {
        for (const bool bSubtract : { false, true })
        {
            JPH::Body* Body = Fixture.Add(Initial);
            if (!TestNotNull(TEXT("Create rejected translation body"), Body)) return false;
            if (bSubtract) Body->SubPositionStep(JPH::Vec3(Invalid, 0.0f, 0.0f));
            else Body->AddPositionStep(JPH::Vec3(Invalid, 0.0f, 0.0f));
            TestTrue(TEXT("Invalid, float-overflow, or broad-phase-overflow translation faults before writing pose"), Body->HasNumericalFailure());
            TestTrue(TEXT("Rejected translation preserves finite pose"), FinitePose(*Body)
                && Body->GetCenterOfMassPosition() == Initial && Body->GetRotation() == JPH::Quat::sIdentity());
            Body->AddPositionStep(Step);
            TestTrue(TEXT("Faulted body rejects subsequent translation"), Body->GetCenterOfMassPosition() == Initial);
        }
    }
    // COM-only checks miss these finite transforms: a long shape can cross the
    // QuadTree limit even while its center remains inside. Preflight actual bounds
    // before adding the fixture so bad test placement cannot itself assert.
    const auto BoundsWithinTree = [](const JPH::AABox& Bounds)
    {
        const JPH::Vec3 Limit = JPH::Vec3::sReplicate(JPH::cLargeFloat);
        return Bounds.IsValid() && JPH::Vec3::sGreaterOrEqual(Bounds.mMin, -Limit).TestAllXYZTrue()
            && JPH::Vec3::sLessOrEqual(Bounds.mMax, Limit).TestAllXYZTrue();
    };
    const double TreeLimit = double(JPH::cLargeFloat);
    const JPH::RefConst<JPH::Shape> LongBox = new JPH::BoxShape(JPH::Vec3(0.1f, 1.0e8f, 0.1f));
    const JPH::Vec3 QuarterTurnStep(0.0f, 0.0f, JPH::JPH_PI * 0.5f);
    const JPH::Quat QuarterTurn = JPH::Quat::sRotation(JPH::Vec3::sAxisZ(), JPH::JPH_PI * 0.5f);
    const JPH::RVec3 RotationPosition(TreeLimit - 5.0e7, 0.0, 0.0);
    if (!TestTrue(TEXT("Long box initial bounds fit before boundary rotation"), BoundsWithinTree(
        LongBox->GetWorldSpaceBounds(JPH::RMat44::sRotationTranslation(JPH::Quat::sIdentity(), RotationPosition), JPH::Vec3::sOne())))) return false;
    TestFalse(TEXT("Long box rotated extent crosses tree boundary with unchanged valid COM"), BoundsWithinTree(
        LongBox->GetWorldSpaceBounds(JPH::RMat44::sRotationTranslation(QuarterTurn, RotationPosition), JPH::Vec3::sOne())));
    JPH::Body* RotationBody = Fixture.AddShape(LongBox.GetPtr(), RotationPosition, JPH::Quat::sIdentity(), true);
    if (!TestNotNull(TEXT("Create long box for rotation boundary"), RotationBody)) return false;
    TestTrue(TEXT("Actual initial rotation body bounds are within tree"), BoundsWithinTree(RotationBody->GetWorldSpaceBounds()));
    RotationBody->AddRotationStep(QuarterTurnStep);
    TestTrue(TEXT("Shape extent rejects boundary rotation before writing pose"), RotationBody->HasNumericalFailure()
        && RotationBody->GetRotation() == JPH::Quat::sIdentity() && RotationBody->GetCenterOfMassPosition() == RotationPosition);

    const JPH::RVec3 TranslationPosition(TreeLimit - 2.0e8, 0.0, 0.0);
    const JPH::Vec3 TranslationStep(1.5e8f, 0.0f, 0.0f);
    const JPH::RVec3 TranslationCandidate = TranslationPosition + TranslationStep;
    if (!TestTrue(TEXT("Long box initial bounds fit before boundary translation"), BoundsWithinTree(
        LongBox->GetWorldSpaceBounds(JPH::RMat44::sRotationTranslation(QuarterTurn, TranslationPosition), JPH::Vec3::sOne())))) return false;
    TestTrue(TEXT("Boundary translation candidate COM remains inside tree"), TranslationCandidate.GetX() < TreeLimit);
    TestFalse(TEXT("Boundary translation candidate shape edge crosses tree"), BoundsWithinTree(
        LongBox->GetWorldSpaceBounds(JPH::RMat44::sRotationTranslation(QuarterTurn, TranslationCandidate), JPH::Vec3::sOne())));
    JPH::Body* TranslationBody = Fixture.AddShape(LongBox.GetPtr(), TranslationPosition, QuarterTurn, true);
    if (!TestNotNull(TEXT("Create long box for translation boundary"), TranslationBody)) return false;
    TestTrue(TEXT("Actual initial translation body bounds are within tree"), BoundsWithinTree(TranslationBody->GetWorldSpaceBounds()));
    TranslationBody->AddPositionStep(TranslationStep);
    TestTrue(TEXT("Shape extent rejects boundary translation before writing pose"), TranslationBody->HasNumericalFailure()
        && TranslationBody->GetCenterOfMassPosition() == TranslationPosition && TranslationBody->GetRotation() == QuarterTurn);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltWorkerNumericalSafetyTest,
    "Prophecy.Jolt.NumericalSafety.WorkerSolverContainment", ProphecyJolt::NumericalSafetyTests::Flags)

bool FProphecyJoltWorkerNumericalSafetyTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::NumericalSafetyTests;
    if (!RuntimeReady(*this)) return false;
    for (const int32 BodyCount : { 2, 160 })
    {
        for (const int32 CollisionSteps : { 1, 3 })
        {
            for (const EInjection Injection : { EInjection::None, EInjection::PositionInfinity, EInjection::PositionBroadPhaseOverflow,
                EInjection::LinearNaN, EInjection::LinearInfinity, EInjection::LinearOverflow,
                EInjection::AngularNaN, EInjection::AngularInfinity, EInjection::AngularOverflow })
            {
                const bool bInject = Injection != EInjection::None;
                FSolverTelemetry Telemetry;
                FNativeFixture Fixture;
                for (int32 Index = 0; Index < BodyCount; ++Index)
                {
                    JPH::Body* Body = Fixture.Add(JPH::RVec3(0.3f * Index, 0.0f, 1.0f));
                    if (!TestNotNull(TEXT("Create connected solver body"), Body)) return false;
                    Body->SetLinearVelocity(JPH::Vec3(0.1f, 0.2f, -0.1f));
                    if (Index > 0) Fixture.Connect(*Fixture.Bodies[Index - 1], *Body, Telemetry,
                        Index == BodyCount / 2 ? Injection : EInjection::None);
                }
                const JPH::EPhysicsUpdateError Error = Fixture.Step(CollisionSteps);
                const FString Label = FString::Printf(TEXT("%d bodies, %d substeps, injection=%d"), BodyCount, CollisionSteps, int32(Injection));
                TestTrue(*FString::Printf(TEXT("Velocity solver executed: %s"), *Label), Telemetry.VelocityCalls.load() > 0);
                if (Injection < EInjection::LinearNaN)
                    TestTrue(*FString::Printf(TEXT("Position solver executed: %s"), *Label), Telemetry.PositionCalls.load() > 0);
                TestTrue(*FString::Printf(TEXT("Expected native error and no capacity errors: %s"), *Label),
                    Error == (bInject ? JPH::EPhysicsUpdateError::NumericalFailure : JPH::EPhysicsUpdateError::None));
                TestEqual(*FString::Printf(TEXT("No later listener can reactivate a failed substep: %s"), *Label),
                    Fixture.Steps.Calls.load(), uint32(bInject ? 1 : CollisionSteps));
                TestEqual(*FString::Printf(TEXT("Invalid correction rejected at write boundary: %s"), *Label),
                    Telemetry.RejectedBeforeWrite.load(), bInject);
                TestEqual(*FString::Printf(TEXT("Exactly one requested injection: %s"), *Label),
                    Telemetry.Injections.load(), uint32(bInject ? 1 : 0));
                if (BodyCount > int32(JPH::LargeIslandSplitter::cLargeIslandTreshold))
                    TestTrue(*FString::Printf(TEXT("Large island splitting was actually exercised: %s"), *Label), Telemetry.SplitCalls.load() > 0);
                if (bInject && CollisionSteps > 1)
                    TestEqual(*FString::Printf(TEXT("Failed world deactivated before next substep: %s"), *Label),
                        Fixture.Physics.GetNumActiveBodies(JPH::EBodyType::RigidBody), JPH::uint32(0));
                bool bAllFinite = true;
                bool bVelocitiesFinite = true;
                uint32 FailedBodies = 0;
                for (const JPH::Body* Body : Fixture.Bodies)
                {
                    bAllFinite &= FinitePose(*Body);
                    bVelocitiesFinite &= std::isfinite(Body->GetLinearVelocity().LengthSq())
                        && std::isfinite(Body->GetAngularVelocity().LengthSq());
                    FailedBodies += Body->HasNumericalFailure() ? 1 : 0;
                }
                TestTrue(*FString::Printf(TEXT("All body poses remain finite after workers join: %s"), *Label), bAllFinite);
                TestTrue(*FString::Printf(TEXT("All body velocities remain finite after workers join: %s"), *Label), bVelocitiesFinite);
                TestTrue(*FString::Printf(TEXT("Body failure corresponds to injection: %s"), *Label), bInject ? FailedBodies > 0 : FailedBodies == 0);
            }
        }
    }
    return !HasAnyErrors();
}

#endif
