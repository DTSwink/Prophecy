#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltConversions.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemThreadPool.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Collision/CastResult.h>
#include <Jolt/Physics/Collision/RayCast.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Constraints/FixedConstraint.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::FoundationTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
constexpr JPH::ObjectLayer StaticLayer = 0;
constexpr JPH::ObjectLayer MovingLayer = 1;
constexpr float StepSeconds = 1.0f / 60.0f;

// Only this fixture uses these two layers. They do not define project channels.
class FFixtureBroadPhaseLayers final : public JPH::BroadPhaseLayerInterface
{
public:
	virtual JPH::uint GetNumBroadPhaseLayers() const override { return 2; }

	virtual JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer Layer) const override
	{
		check(Layer == StaticLayer || Layer == MovingLayer);
		return JPH::BroadPhaseLayer(static_cast<JPH::uint8>(Layer));
	}

#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
	virtual const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer Layer) const override
	{
		return Layer == JPH::BroadPhaseLayer(0) ? "FixtureStatic" : "FixtureMoving";
	}
#endif
};

class FFixtureObjectPairs final : public JPH::ObjectLayerPairFilter
{
public:
	virtual bool ShouldCollide(JPH::ObjectLayer First, JPH::ObjectLayer Second) const override
	{
		check(First <= MovingLayer && Second <= MovingLayer);
		return First == MovingLayer || Second == MovingLayer;
	}
};

class FFixtureObjectVsBroadPhase final : public JPH::ObjectVsBroadPhaseLayerFilter
{
public:
	virtual bool ShouldCollide(JPH::ObjectLayer Object, JPH::BroadPhaseLayer BroadPhase) const override
	{
		check(Object <= MovingLayer);
		return Object == MovingLayer || BroadPhase == JPH::BroadPhaseLayer(1);
	}
};

bool VerifyRuntime(FAutomationTestBase& Test)
{
	if (!Test.TestTrue(TEXT("Pinned library/header ABI agrees"), JPH::VerifyJoltVersionID())
		|| !Test.TestNotNull(TEXT("Runtime module owns a Jolt factory"), JPH::Factory::sInstance))
	{
		return false;
	}
	return Test.TestNotNull(TEXT("Runtime module registered sphere settings"), JPH::Factory::sInstance->Find("SphereShapeSettings"));
}

class FScopedPhysicsFixture final
{
public:
	explicit FScopedPhysicsFixture(JPH::Vec3Arg Gravity = JPH::Vec3(0.0f, 0.0f, -9.81f))
		: TempAllocator(8 * 1024 * 1024)
		, Jobs(MakeUnique<JPH::JobSystemThreadPool>(JPH::cMaxPhysicsJobs, JPH::cMaxPhysicsBarriers, 1))
		, DeadlineSeconds(FPlatformTime::Seconds() + 15.0)
	{
		Physics.Init(64, 0, 128, 128, BroadPhaseLayers, ObjectVsBroadPhase, ObjectPairs);
		Physics.SetGravity(Gravity);
	}

	~FScopedPhysicsFixture()
	{
		// Update waits for its jobs; joining also ends worker-wrapper lifetimes
		// before constraints, bodies, the physics system and allocator disappear.
		Jobs.Reset();
		Clear();
	}

	FScopedPhysicsFixture(const FScopedPhysicsFixture&) = delete;
	FScopedPhysicsFixture& operator=(const FScopedPhysicsFixture&) = delete;

	JPH::BodyID CreateBody(const JPH::BodyCreationSettings& Settings)
	{
		const JPH::EActivation Activation = Settings.mMotionType == JPH::EMotionType::Static
			? JPH::EActivation::DontActivate : JPH::EActivation::Activate;
		const JPH::BodyID Body = Bodies().CreateAndAddBody(Settings, Activation);
		if (!Body.IsInvalid())
		{
			BodyIDs.Add(Body);
		}
		return Body;
	}

	bool AddFixedConstraint(const JPH::BodyID& First, const JPH::BodyID& Second)
	{
		JPH::FixedConstraintSettings Settings;
		Settings.mAutoDetectPoint = true;
		JPH::Ref<JPH::Constraint> Constraint = Bodies().CreateConstraint(&Settings, First, Second);
		if (Constraint == nullptr)
		{
			return false;
		}
		Physics.AddConstraint(Constraint.GetPtr());
		Constraints.Add(Constraint);
		return true;
	}

	void RemoveConstraints()
	{
		for (const JPH::Ref<JPH::Constraint>& Constraint : Constraints)
		{
			Physics.RemoveConstraint(Constraint.GetPtr());
		}
		Constraints.Reset();
	}

	void Clear()
	{
		RemoveConstraints();
		for (const JPH::BodyID& Body : BodyIDs)
		{
			Bodies().RemoveBody(Body);
			Bodies().DestroyBody(Body);
		}
		BodyIDs.Reset();
	}

	bool Step(FAutomationTestBase& Test, int32 Count)
	{
		check(Count > 0 && Count <= 300);
		for (int32 Index = 0; Index < Count; ++Index)
		{
			// This bounds the stepping loop; the external automation timeout must
			// still catch a deadlock inside an individual synchronous Update.
			if (FPlatformTime::Seconds() >= DeadlineSeconds)
			{
				Test.AddError(TEXT("Foundation fixture exceeded its 15-second stepping deadline."));
				return false;
			}
			const JPH::EPhysicsUpdateError Error = Physics.Update(StepSeconds, 1, &TempAllocator, Jobs.Get());
			if (Error != JPH::EPhysicsUpdateError::None)
			{
				Test.AddError(FString::Printf(TEXT("Jolt Update failed at fixture step %d, error bits 0x%x."), Index, static_cast<uint32>(Error)));
				return false;
			}
		}
		return true;
	}

	JPH::BodyInterface& Bodies() { return Physics.GetBodyInterface(); }
	JPH::PhysicsSystem& System() { return Physics; }

private:
	// Filters and temporary memory outlive the PhysicsSystem.
	FFixtureBroadPhaseLayers BroadPhaseLayers;
	FFixtureObjectPairs ObjectPairs;
	FFixtureObjectVsBroadPhase ObjectVsBroadPhase;
	JPH::TempAllocatorImpl TempAllocator;
	JPH::PhysicsSystem Physics;
	TUniquePtr<JPH::JobSystemThreadPool> Jobs;
	TArray<JPH::Ref<JPH::Constraint>> Constraints;
	TArray<JPH::BodyID> BodyIDs;
	double DeadlineSeconds;
};

JPH::BodyCreationSettings DynamicSphere(const JPH::Shape* Shape, JPH::RVec3Arg Position)
{
	JPH::BodyCreationSettings Settings(Shape, Position, JPH::Quat::sIdentity(), JPH::EMotionType::Dynamic, MovingLayer);
	Settings.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
	Settings.mMassPropertiesOverride.mMass = 2.0f;
	Settings.mAllowSleeping = false;
	Settings.mLinearDamping = 0.0f;
	Settings.mAngularDamping = 0.0f;
	Settings.mRestitution = 0.0f;
	return Settings;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRuntimeIsolationTest, "Prophecy.Jolt.Foundation.RuntimeAndIsolation", ProphecyJolt::FoundationTests::Flags)

bool FProphecyJoltRuntimeIsolationTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyJolt::FoundationTests;
	using namespace ProphecyJolt::Conversions;
	if (!VerifyRuntime(*this))
	{
		return false;
	}
	JPH::Factory* const ModuleFactory = JPH::Factory::sInstance;
	for (int32 Cycle = 0; Cycle < 3; ++Cycle)
	{
		{
			FScopedPhysicsFixture FallingWorld;
			FScopedPhysicsFixture ZeroGravityWorld(JPH::Vec3::sZero());
			const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.5f);
			const JPH::RVec3 Start(0.0, 0.0, 5.0);
			const JPH::BodyID FallingBody = FallingWorld.CreateBody(DynamicSphere(Shape, Start));
			const JPH::BodyID OtherBody = ZeroGravityWorld.CreateBody(DynamicSphere(Shape, Start));
			if (!TestFalse(TEXT("Falling-world body created"), FallingBody.IsInvalid())
				|| !TestFalse(TEXT("Independent-world body created"), OtherBody.IsInvalid()))
			{
				return false;
			}
			ZeroGravityWorld.Bodies().SetLinearVelocity(OtherBody, JPH::Vec3(1.0f, 0.0f, 0.0f));
			if (!FallingWorld.Step(*this, 30))
			{
				return false;
			}
			TestTrue(TEXT("Explicit Z gravity lowers the first body"), FallingWorld.Bodies().GetPosition(FallingBody).GetZ() < 4.0);
			TestNearlyEqual(TEXT("Stepping first world leaves second world unchanged"), FromJoltPosition(ZeroGravityWorld.Bodies().GetPosition(OtherBody)), FVector(0.0, 0.0, 500.0), 1.0e-5f);
			const FVector FallingPosition = FromJoltPosition(FallingWorld.Bodies().GetPosition(FallingBody));
			if (!ZeroGravityWorld.Step(*this, 30))
			{
				return false;
			}
			TestNearlyEqual(TEXT("Second world has independent velocity and gravity"), FromJoltPosition(ZeroGravityWorld.Bodies().GetPosition(OtherBody)), FVector(50.0, 0.0, 500.0), 1.0e-3f);
			TestNearlyEqual(TEXT("Stepping second world leaves first world unchanged"), FromJoltPosition(FallingWorld.Bodies().GetPosition(FallingBody)), FallingPosition, 1.0e-5f);
			FallingWorld.Clear();
			TestEqual(TEXT("First world releases every body"), static_cast<int32>(FallingWorld.System().GetNumBodies()), 0);
			TestTrue(TEXT("First world releases every constraint"), FallingWorld.System().GetConstraints().empty());
			TestEqual(TEXT("Clearing first world preserves second world"), static_cast<int32>(ZeroGravityWorld.System().GetNumBodies()), 1);
			ZeroGravityWorld.Clear();
			TestEqual(TEXT("Second world releases every body"), static_cast<int32>(ZeroGravityWorld.System().GetNumBodies()), 0);
		}
		TestTrue(TEXT("World teardown preserves module-owned factory"), JPH::Factory::sInstance == ModuleFactory);
		if (!VerifyRuntime(*this))
		{
			return false;
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltFallAndRayTest, "Prophecy.Jolt.Foundation.FallAndRay", ProphecyJolt::FoundationTests::Flags)

bool FProphecyJoltFallAndRayTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyJolt::FoundationTests;
	if (!VerifyRuntime(*this))
	{
		return false;
	}
	FScopedPhysicsFixture World;
	const JPH::RefConst<JPH::Shape> FloorShape = new JPH::BoxShape(JPH::Vec3(5.0f, 5.0f, 0.5f));
	const JPH::RefConst<JPH::Shape> SphereShape = new JPH::SphereShape(0.5f);
	const JPH::BodyID Floor = World.CreateBody(JPH::BodyCreationSettings(FloorShape, JPH::RVec3(0.0, 0.0, -0.5), JPH::Quat::sIdentity(), JPH::EMotionType::Static, StaticLayer));
	const JPH::BodyID Sphere = World.CreateBody(DynamicSphere(SphereShape, JPH::RVec3(0.0, 0.0, 3.0)));
	if (!TestFalse(TEXT("Floor created"), Floor.IsInvalid()) || !TestFalse(TEXT("Sphere created"), Sphere.IsInvalid()) || !World.Step(*this, 1))
	{
		return false;
	}
	TestTrue(TEXT("Sphere begins falling on Z"), World.Bodies().GetPosition(Sphere).GetZ() < 3.0 && World.Bodies().GetLinearVelocity(Sphere).GetZ() < 0.0f);
	if (!World.Step(*this, 239))
	{
		return false;
	}
	const JPH::RVec3 RestPosition = World.Bodies().GetPosition(Sphere);
	TestNearlyEqual(TEXT("Half-meter sphere rests on floor within contact slop"), RestPosition.GetZ(), 0.5, 0.03);
	TestNearlyEqual(TEXT("Sphere has no lateral drift"), RestPosition.GetX(), 0.0, 1.0e-5);
	TestNearlyEqual(TEXT("Sphere has no Y drift"), RestPosition.GetY(), 0.0, 1.0e-5);
	TestTrue(TEXT("Sphere is supported rather than falling through"), FMath::Abs(World.Bodies().GetLinearVelocity(Sphere).GetZ()) < 0.05f);

	JPH::RayCastResult FloorHit;
	const JPH::RRayCast FloorRay(JPH::RVec3(2.0, 0.0, 5.0), JPH::Vec3(0.0f, 0.0f, -10.0f));
	if (!TestTrue(TEXT("Ray beside sphere hits floor"), World.System().GetNarrowPhaseQuery().CastRay(FloorRay, FloorHit)))
	{
		return false;
	}
	TestTrue(TEXT("Ray identifies the floor body"), FloorHit.mBodyID == Floor);
	TestNearlyEqual(TEXT("Ray fraction includes the supplied ray length"), FloorHit.mFraction, 0.5f, 1.0e-5f);
	TestNearlyEqual(TEXT("Floor ray returns its top surface"), FloorRay.GetPointOnRay(FloorHit.mFraction).GetZ(), 0.0, 1.0e-5);
	JPH::RayCastResult SphereHit;
	const JPH::RRayCast SphereRay(JPH::RVec3(0.0, 0.0, 5.0), JPH::Vec3(0.0f, 0.0f, -10.0f));
	if (!TestTrue(TEXT("Ray through sphere returns a hit"), World.System().GetNarrowPhaseQuery().CastRay(SphereRay, SphereHit)))
	{
		return false;
	}
	TestTrue(TEXT("Closest ray hit is sphere before floor"), SphereHit.mBodyID == Sphere);
	TestNearlyEqual(TEXT("Sphere ray returns its upper surface"), SphereRay.GetPointOnRay(SphereHit.mFraction).GetZ(), RestPosition.GetZ() + 0.5, 1.0e-5);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltImpulseAndConstraintTest, "Prophecy.Jolt.Foundation.ImpulseAndConstraint", ProphecyJolt::FoundationTests::Flags)

bool FProphecyJoltImpulseAndConstraintTest::RunTest(const FString& Parameters)
{
	using namespace ProphecyJolt::FoundationTests;
	using namespace ProphecyJolt::Conversions;
	if (!VerifyRuntime(*this))
	{
		return false;
	}
	{
		FScopedPhysicsFixture World(JPH::Vec3::sZero());
		const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.5f);
		const JPH::RVec3 Center(10.0, 20.0, 30.0);
		const JPH::BodyID Sphere = World.CreateBody(DynamicSphere(Shape, Center));
		if (!TestFalse(TEXT("Impulse sphere created"), Sphere.IsInvalid()))
		{
			return false;
		}
		const JPH::RVec3 ImpulsePoint = Center + JPH::Vec3(1.0f, 0.0f, 0.0f);
		World.Bodies().AddImpulse(Sphere, JPH::Vec3(0.0f, 2.0f, 0.0f), ImpulsePoint);
		// Solid sphere: I = 2/5 * 2 kg * (0.5 m)^2 = 0.2 kg*m^2.
		TestNearlyEqual(TEXT("Off-center impulse gives J/m COM velocity"), FromJoltLinearVelocity(World.Bodies().GetLinearVelocity(Sphere)), FVector(0.0, 100.0, 0.0), 1.0e-3f);
		TestNearlyEqual(TEXT("Off-center impulse gives inverse-inertia angular velocity"), FromJoltAngularVelocity(World.Bodies().GetAngularVelocity(Sphere)), FVector(0.0, 0.0, 10.0), 1.0e-4f);
		TestNearlyEqual(TEXT("Body point velocity includes angular lever arm"), FromJoltLinearVelocity(World.Bodies().GetPointVelocity(Sphere, ImpulsePoint)), FVector(0.0, 1100.0, 0.0), 1.0e-2f);
	}
	{
		FScopedPhysicsFixture World;
		const JPH::RefConst<JPH::Shape> Shape = new JPH::SphereShape(0.1f);
		const JPH::BodyID Anchor = World.CreateBody(JPH::BodyCreationSettings(Shape, JPH::RVec3(0.0, 0.0, 3.0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, StaticLayer));
		const JPH::BodyID Supported = World.CreateBody(DynamicSphere(Shape, JPH::RVec3(1.0, 0.0, 3.0)));
		if (!TestFalse(TEXT("Constraint anchor created"), Anchor.IsInvalid())
			|| !TestFalse(TEXT("Constrained dynamic body created"), Supported.IsInvalid())
			|| !TestTrue(TEXT("Two-body fixed constraint created"), World.AddFixedConstraint(Anchor, Supported)))
		{
			return false;
		}
		TestEqual(TEXT("Fixed constraint registered"), static_cast<int32>(World.System().GetConstraints().size()), 1);
		World.Bodies().AddImpulse(Supported, JPH::Vec3(0.0f, 1.0f, 0.0f));
		if (!World.Step(*this, 120))
		{
			return false;
		}
		TestNearlyEqual(TEXT("Fixed constraint preserves body offset under gravity and impulse"), FromJoltPosition(World.Bodies().GetPosition(Supported)), FVector(100.0, 0.0, 300.0), 1.0f);
		TestNearlyEqual(TEXT("Static anchor remains fixed"), FromJoltPosition(World.Bodies().GetPosition(Anchor)), FVector(0.0, 0.0, 300.0), 1.0e-5f);
		World.RemoveConstraints();
		TestTrue(TEXT("Fixed constraint removed before body destruction"), World.System().GetConstraints().empty());
		if (!World.Step(*this, 30))
		{
			return false;
		}
		TestTrue(TEXT("Released dynamic body resumes falling"), World.Bodies().GetPosition(Supported).GetZ() < 2.5);
		World.Clear();
		TestEqual(TEXT("Constraint fixture releases all bodies"), static_cast<int32>(World.System().GetNumBodies()), 0);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
