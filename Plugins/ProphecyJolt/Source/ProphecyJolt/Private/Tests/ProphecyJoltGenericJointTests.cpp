#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltPhysicsCommand.h"
#include "ProphecyJoltWorldSubsystem.h"

namespace ProphecyJolt::GenericJointTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

class FScopedWorld final
{
public:
    FScopedWorld()
    {
        const UWorld::InitializationValues Values = UWorld::InitializationValues()
            .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(false)
            .CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
            .EnableTraceCollision(false).CreateFXSystem(false).SetTransactional(false);
        World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (World && GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    }
    ~FScopedWorld()
    {
        if (!World) return;
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
        World->MarkAsGarbage();
    }
    UProphecyJoltWorldSubsystem* Get() const { return World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr; }
private:
    UWorld* World = nullptr;
};

bool Okay(FAutomationTestBase& Test, const TCHAR* Context, const FProphecyJoltWorldStatus& Status)
{
    if (Status.IsSuccess()) return true;
    Test.AddError(FString::Printf(TEXT("%s: %u: %s"), Context, static_cast<uint32>(Status.Code), *Status.Message));
    return false;
}

FProphecyJoltWorldSettings Settings()
{
    FProphecyJoltWorldSettings Result;
    Result.GravityCmPerSecondSquared = FVector::ZeroVector;
    Result.MaxBodies = 16;
    Result.MaxBodyPairs = Result.MaxContactConstraints = 128;
    return Result;
}

bool Start(FAutomationTestBase& Test, FScopedWorld& Scope, const FProphecyJoltWorldSettings& In = Settings())
{
    return Test.TestNotNull(TEXT("Transient game world owner"), Scope.Get())
        && Okay(Test, TEXT("Initialize bounded joint world"), Scope.Get()->InitializeSimulation(In));
}

bool Steps(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& World, int32 Count = 60)
{
    for (int32 Index = 0; Index < Count; ++Index)
        if (!Okay(Test, TEXT("Advance real native physics"), World.Step(1.0f / 120.0f, 1))) return false;
    return true;
}

bool Counts(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& World, uint32 Joints, uint32 Pairs)
{
    FProphecyJoltWorldDiagnostics Out;
    return Okay(Test, TEXT("Read joint diagnostics"), World.GetDiagnostics(Out))
        && Test.TestEqual(TEXT("Exact generic joint count"), Out.GenericJointCount, Joints)
        && Test.TestEqual(TEXT("Native constraint count agrees in fixtures without PHAT joints"), Out.ConstraintCount, Joints)
        && Test.TestEqual(TEXT("Exact unique suppression pair count"), Out.SuppressedBodyPairCount, Pairs);
}

FProphecyJoltJointSettings FreeJoint(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    FProphecyJoltJointSettings Result;
    Result.BodyA = A; Result.BodyB = B; Result.Type = EProphecyJoltJointType::HardSixDOF;
    for (int32 Axis = 0; Axis < 3; ++Axis)
        Result.Translation[Axis].Motion = Result.Rotation[Axis].Motion = EProphecyJoltAxisMotion::Free;
    return Result;
}

FProphecyJoltRigSnapshot Rig(int32 BodyCount = 2, double Y = 0.0)
{
    FProphecyJoltRigSnapshot Result;
    Result.CaptureId = FGuid::NewGuid();
    Result.ComponentPath = TEXT("Synthetic generic-joint fixture; no source actor or asset");
    for (int32 Index = 0; Index < BodyCount; ++Index)
    {
        auto& Body = Result.Bodies.AddDefaulted_GetRef();
        Body.SourceBodyIndex = Body.BoneIndex = Index;
        Body.BodyName = FName(*FString::Printf(TEXT("body_%d"), Index));
        Body.BodyOriginToWorld = FTransform(FQuat::Identity, FVector(Index == 0 ? -30.0 : 30.0, Y, 0.0));
        Body.MassKg = 2.0;
        Body.PrincipalInertiaKgCmSquared = FVector(80.0);
        Body.bSimulating = Body.bAwake = true;
        Body.bGravityEnabled = false;
        Body.MaxLinearVelocityCmPerSecond = 50000.0;
        Body.MaxAngularVelocityRadiansPerSecond = 15.0 * UE_DOUBLE_PI;
        Body.PositionSolverIterations = 4; Body.VelocitySolverIterations = 1; Body.ProjectionSolverIterations = 0;
        Body.CollisionEnabled = ECollisionEnabled::QueryAndPhysics;
        Body.ObjectType = ECC_PhysicsBody;
        Body.CollisionResponses.SetAllChannels(ECR_Block);
        Body.LinearDamping = Body.AngularDamping = Body.Friction = Body.Restitution = 0.0;
        auto& Shape = Body.Shapes.AddDefaulted_GetRef();
        Shape.Kind = EProphecyJoltRigShape::Sphere;
        Shape.SourceElementIndex = 0; Shape.ElementName = TEXT("sphere"); Shape.RadiusCm = 10.0;
        Shape.AuthoredCollisionEnabled = Shape.CurrentCollisionEnabled = ECollisionEnabled::QueryAndPhysics;
        Shape.bContributesToAuthoredMass = true;
    }
    if (BodyCount == 2)
    {
        auto& Pair = Result.DisabledPairs.AddDefaulted_GetRef();
        Pair.Body1Index = 0; Pair.Body2Index = 1; Pair.bFromPhysicsAsset = true;
    }
    return Result;
}

bool CreateRig(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& World, const FProphecyJoltRigSnapshot& Snapshot,
    FProphecyJoltPreparedRig& Prepared, FProphecyJoltRigHandle& OutRig, TArray<FProphecyJoltBodyHandle>& Out)
{
    FString Error;
    TArray<FString> Notes;
    const bool bBuilt = Prepared.Build(Snapshot, Error);
    return Test.TestTrue(FString(TEXT("Prepare synthetic captured bodies: ")) + Error, bBuilt)
        && Okay(Test, TEXT("Create independently owned rig"), World.CreateRig(Snapshot, Prepared, OutRig, Out, Notes));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltFixedGripTest,
    "Prophecy.Jolt.GenericJoint.FixedGripAndDrop", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltFixedGripTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    FScopedWorld Scope;
    auto In = Settings(); In.GravityCmPerSecondSquared = FVector(0, 0, -981);
    if (!Start(*this, Scope, In)) return false;
    auto& World = *Scope.Get();
    FProphecyJoltFixtureBodySettings Anchor;
    Anchor.bDynamic = false; Anchor.Rotation = FQuat(FVector::UpVector, 0.35);
    FProphecyJoltBodyHandle A;
    if (!Okay(*this, TEXT("Create rotated static grip anchor"), World.CreateSphere(2.0, Anchor, A))) return false;
    auto Snapshot = Rig(1);
    Snapshot.Bodies[0].BodyOriginToWorld = FTransform(FQuat(FVector::RightVector, 0.4), FVector(40, 0, 0));
    Snapshot.Bodies[0].MassFrameToBodyOrigin = FTransform(FQuat(FVector::UpVector, 0.2), FVector(4, -3, 2));
    Snapshot.Bodies[0].bGravityEnabled = true;
    FProphecyJoltPreparedRig Prepared;
    FProphecyJoltRigHandle RigHandle;
    TArray<FProphecyJoltBodyHandle> Bodies;
    if (!CreateRig(*this, World, Snapshot, Prepared, RigHandle, Bodies)) return false;
    FProphecyJoltJointSettings Grip;
    Grip.BodyA = A; Grip.BodyB = Bodies[0];
    const FTransform WorldGrip(FQuat(FVector::ForwardVector, 0.3) * FQuat(FVector::UpVector, -0.25), FVector(20, 3, 5));
    Grip.FrameA = WorldGrip.GetRelativeTransform(FTransform(Anchor.Rotation, Anchor.PositionCm));
    Grip.FrameB = WorldGrip.GetRelativeTransform(Snapshot.Bodies[0].BodyOriginToWorld);
    FProphecyJoltJointHandle Joint;
    if (!Okay(*this, TEXT("Create explicit off-center fixed grip"), World.CreateJoint(Grip, {}, Joint))
        || !Okay(*this, TEXT("Apply off-center impulse"), World.AddPointImpulse(Bodies[0], FVector(0, 100, 50), FVector(40, 8, 0)))
        || !Steps(*this, World)) return false;
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Read constrained body"), World.ReadBody(Bodies[0], State))) return false;
    const FTransform Actual = Grip.FrameB * FTransform(State.Rotation, State.PositionCm);
    TestTrue(TEXT("Offset COM does not shift the body-origin grip anchor"), Actual.GetTranslation().Equals(WorldGrip.GetTranslation(), 1.0));
    TestTrue(TEXT("Rotated connector orientation stays fixed"), Actual.GetRotation().AngularDistance(WorldGrip.GetRotation()) < 0.03);
    TestTrue(TEXT("Captured nonzero COM offset is present"), FVector::Distance(State.CenterOfMassPositionCm, State.PositionCm) > 4.0);
    const double BeforeDrop = State.PositionCm.Z;
    if (!Okay(*this, TEXT("Drop fixed grip"), World.DestroyJoint(Joint)) || !Steps(*this, World, 30)
        || !Okay(*this, TEXT("Read falling released body"), World.ReadBody(Bodies[0], State))) return false;
    TestTrue(TEXT("Dropped body moves independently under gravity"), State.PositionCm.Z < BeforeDrop - 10.0);
    TestFalse(TEXT("Released joint handle is stale"), World.OwnsJoint(Joint));
    return Counts(*this, World, 0, 0);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltHardSixDOFTest,
    "Prophecy.Jolt.GenericJoint.HardSixDOFAndReplacement", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltHardSixDOFTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    FProphecyJoltFixtureBodySettings Static;
    Static.bDynamic = false; Static.CollisionResponses.SetAllChannels(ECR_Ignore);
    FProphecyJoltBodyHandle A, B;
    if (!Okay(*this, TEXT("Create reference body"), World.CreateSphere(2, Static, A))
        || !Okay(*this, TEXT("Create dynamic test sphere"), World.CreateSphere(10, {}, B))) return false;
    auto Joint = FreeJoint(A, B);
    Joint.FrameA = Joint.FrameB = FTransform(FQuat(FVector::UpVector, UE_DOUBLE_PI / 2.0));
    Joint.Translation[1].Motion = Joint.Translation[2].Motion = EProphecyJoltAxisMotion::Locked;
    Joint.Rotation[0] = { EProphecyJoltAxisMotion::Limited, FMath::DegreesToRadians(-10.0), FMath::DegreesToRadians(25.0) };
    Joint.Rotation[1].Motion = Joint.Rotation[2].Motion = EProphecyJoltAxisMotion::Locked;
    FProphecyJoltJointHandle Handle;
    if (!Okay(*this, TEXT("Create rotated hard six DOF"), World.CreateJoint(Joint, {}, Handle))
        || !Okay(*this, TEXT("Impulse along free local X/world Y"), World.AddPointImpulse(B, FVector(0, 100, 0), FVector::ZeroVector))
        || !Okay(*this, TEXT("Impulse rotating positive local X/world Y"), World.AddPointImpulse(B, FVector(0, 0, -20), FVector(10, 0, 0)))
        || !Steps(*this, World)) return false;
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Read limited sphere"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Free local X moves along world Y"), State.PositionCm.Y > 40.0);
    TestTrue(TEXT("Other translations remain locked"), FMath::Abs(State.PositionCm.X) < 0.5 && FMath::Abs(State.PositionCm.Z) < 0.5);
    const FQuat Relative = Joint.FrameA.GetRotation().Inverse() * State.Rotation * Joint.FrameB.GetRotation();
    const double Twist = FMath::UnwindRadians(2.0 * FMath::Atan2(Relative.X, Relative.W));
    TestTrue(TEXT("Asymmetric positive twist is stopped by authored +25 degrees"), Twist > 0.2 && Twist < FMath::DegreesToRadians(28.0));
    Joint.Translation[0] = { EProphecyJoltAxisMotion::Limited, -5.0, 10.0 };
    if (!Okay(*this, TEXT("Replace free axis with bounded hard range"), World.UpdateJoint(Handle, Joint))
        || !Steps(*this, World)
        || !Okay(*this, TEXT("Read updated hard range"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Updated linear range constrains actual motion"), State.PositionCm.Y <= 11.0 && State.PositionCm.Y >= -6.0);
    auto Invalid = Joint;
    Invalid.Rotation[1] = { EProphecyJoltAxisMotion::Limited, -0.2, 0.4 };
    TestEqual(TEXT("Asymmetric cone preflight rejects without replacement"), World.UpdateJoint(Handle, Invalid).Code, EProphecyJoltWorldResult::InvalidArgument);
    FProphecyJoltJointSettings Readback;
    if (!Okay(*this, TEXT("Read surviving old joint settings"), World.ReadJoint(Handle, Readback))) return false;
    TestEqual(TEXT("Exact supplied hard maximum retained"), Readback.Translation[0].Maximum, 10.0);
    TestEqual(TEXT("Failed replacement did not change angular mode"), Readback.Rotation[1].Motion, EProphecyJoltAxisMotion::Locked);
    // Pyramid supports that asymmetric swing request without silently symmetrizing it.
    Invalid.SwingGeometry = EProphecyJoltSwingGeometry::Pyramid;
    if (!Okay(*this, TEXT("Accept explicit pyramid geometry"), World.UpdateJoint(Handle, Invalid)) || !Steps(*this, World, 8)) return false;
    return Counts(*this, World, 1, 0);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSuppressionCacheTest,
    "Prophecy.Jolt.GenericJoint.CachedSuppressionReferenceCounts", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltSuppressionCacheTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    FScopedWorld Scope;
    auto In = Settings(); In.GravityCmPerSecondSquared = FVector(0, 0, -1000);
    if (!Start(*this, Scope, In)) return false;
    auto& World = *Scope.Get();
    FProphecyJoltFixtureBodySettings Floor; Floor.bDynamic = false; Floor.PositionCm.Z = -20;
    FProphecyJoltFixtureBodySettings Sphere; Sphere.PositionCm.Z = 15; Sphere.bAllowSleeping = true;
    FProphecyJoltBodyHandle A, B;
    if (!Okay(*this, TEXT("Create thick contact floor"), World.CreateBox(FVector(200, 200, 20), 0, Floor, A))
        || !Okay(*this, TEXT("Create sleeping-capable sphere"), World.CreateSphere(10, Sphere, B))
        || !Steps(*this, World, 240)) return false;
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Read established cached contact"), World.ReadBody(B, State))) return false;
    TestFalse(TEXT("Resting sphere slept before hold"), State.bActive);
    const double RestHeight = State.PositionCm.Z;
    const FProphecyJoltBodyPair Duplicated[] = { { A, B }, { B, A }, { A, B } };
    const FProphecyJoltBodyPair Single[] = { { B, A } };
    FProphecyJoltJointHandle First, Second;
    const auto Free = FreeJoint(A, B); // all-free constraints cannot themselves support the sphere.
    if (!Okay(*this, TEXT("First scoped suppression with duplicates"), World.CreateJoint(Free, MakeArrayView(Duplicated), First))
        || !Okay(*this, TEXT("Second owner of same pair"), World.CreateJoint(Free, MakeArrayView(Single), Second))
        || !Counts(*this, World, 2, 1)
        || !Okay(*this, TEXT("Read one-time activation"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Hold wakes the previously sleeping endpoint"), State.bActive);
    if (!Okay(*this, TEXT("Release only first owner"), World.DestroyJoint(First)) || !Counts(*this, World, 1, 1)
        || !Steps(*this, World, 12)
        || !Okay(*this, TEXT("Read unsupported sphere within floor"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Remaining owner vetoes previously cached contacts"), State.PositionCm.Z < RestHeight - 3.0);
    if (!Okay(*this, TEXT("Release final pair reference"), World.DestroyJoint(Second)) || !Counts(*this, World, 0, 0)
        || !Steps(*this, World)
        || !Okay(*this, TEXT("Read restored actual contact"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Final release invalidates no-contact cache and restores floor response"), State.PositionCm.Z > 7.5);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSuppressionPHATTest,
    "Prophecy.Jolt.GenericJoint.SuppressionPreservesPHATAndPeers", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltSuppressionPHATTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    auto OwnerSnapshot = Rig(), PeerSnapshot = Rig(2, 100.0);
    for (int32 Index = 0; Index < 2; ++Index)
    {
        OwnerSnapshot.Bodies[Index].CenterOfMassVelocityCmPerSecond = FVector(Index == 0 ? 100.0 : -100.0, 0, 0);
        PeerSnapshot.Bodies[Index].CenterOfMassVelocityCmPerSecond = OwnerSnapshot.Bodies[Index].CenterOfMassVelocityCmPerSecond;
    }
    FProphecyJoltPreparedRig OwnerPrepared, PeerPrepared;
    FProphecyJoltRigHandle OwnerRig, PeerRig;
    TArray<FProphecyJoltBodyHandle> Owner, Peer;
    if (!CreateRig(*this, World, OwnerSnapshot, OwnerPrepared, OwnerRig, Owner)
        || !CreateRig(*this, World, PeerSnapshot, PeerPrepared, PeerRig, Peer)) return false;
    FProphecyJoltFixtureBodySettings Static; Static.bDynamic = false;
    FProphecyJoltBodyHandle Prop, PeerProp;
    if (!Okay(*this, TEXT("Create owner's held prop geometry"), World.CreateSphere(10, Static, Prop))) return false;
    Static.PositionCm.Y = 100;
    if (!Okay(*this, TEXT("Create unrelated same-profile prop"), World.CreateSphere(10, Static, PeerProp))) return false;
    const FProphecyJoltBodyPair Pairs[] = { { Owner[0], Prop }, { Owner[1], Prop } };
    FProphecyJoltJointHandle Lease;
    if (!Okay(*this, TEXT("Suppress only explicit owner's pairs"), World.CreateJoint(FreeJoint(Owner[0], Prop), MakeArrayView(Pairs), Lease))
        || !Steps(*this, World)) return false;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FProphecyJoltBodyState O, P;
        if (!Okay(*this, TEXT("Read excluded owner"), World.ReadBody(Owner[Index], O))
            || !Okay(*this, TEXT("Read unrelated peer"), World.ReadBody(Peer[Index], P))) return false;
        TestTrue(TEXT("Owner crosses held prop and its own PHAT-disabled partner"), Index == 0 ? O.PositionCm.X > 15 : O.PositionCm.X < -15);
        TestTrue(TEXT("Unrelated same-profile peer still blocks on prop"), Index == 0 ? P.PositionCm.X < -17 : P.PositionCm.X > 17);
    }
    if (!Okay(*this, TEXT("Release scoped pairs"), World.DestroyJoint(Lease))
        || !Okay(*this, TEXT("Remove intervening prop for PHAT-only return pass"), World.DestroyBody(Prop))) return false;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FProphecyJoltBodyState State;
        if (!Okay(*this, TEXT("Read owner before reversal"), World.ReadBody(Owner[Index], State))
            || !Okay(*this, TEXT("Reverse owner velocity"), World.AddPointImpulse(Owner[Index], State.CenterOfMassVelocityCmPerSecond * -4.0, State.CenterOfMassPositionCm))) return false;
    }
    if (!Steps(*this, World)) return false;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FProphecyJoltBodyState State;
        if (!Okay(*this, TEXT("Read return pass through original PHAT exclusion"), World.ReadBody(Owner[Index], State))) return false;
        TestTrue(TEXT("Releasing temporary exclusions preserved PHAT pair"), Index == 0 ? State.PositionCm.X < -25 : State.PositionCm.X > 25);
    }
    return Counts(*this, World, 0, 0);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltJointLifetimeTest,
    "Prophecy.Jolt.GenericJoint.EndpointThirdPartyAndReuse", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltJointLifetimeTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    for (int32 Endpoint = 0; Endpoint < 2; ++Endpoint)
    {
        FScopedWorld Scope;
        if (!Start(*this, Scope)) return false;
        auto& World = *Scope.Get();
        FProphecyJoltBodyHandle A, B, C, Replacement;
        FProphecyJoltFixtureBodySettings Body;
        Body.PositionCm.X = -200;
        if (!Okay(*this, TEXT("Create A"), World.CreateSphere(10, Body, A))) return false;
        Body.PositionCm.X = 200;
        if (!Okay(*this, TEXT("Create B"), World.CreateSphere(10, Body, B))) return false;
        Body.PositionCm.X = 0;
        if (!Okay(*this, TEXT("Create third party"), World.CreateSphere(10, Body, C))) return false;
        const FProphecyJoltBodyPair Pairs[] = { { A, B }, { B, C } };
        FProphecyJoltJointHandle First, Second;
        if (!Okay(*this, TEXT("Create joint with third-party suppression"), World.CreateJoint(FreeJoint(A, B), MakeArrayView(Pairs), First))
            || !Okay(*this, TEXT("Remove third party before either endpoint"), World.DestroyBody(C))
            || !Counts(*this, World, 1, 1)) return false;
        TestTrue(TEXT("Unrelated suppression-body removal keeps joint alive"), World.OwnsJoint(First));
        if (!Okay(*this, TEXT("Reuse retired body slot"), World.CreateSphere(10, Body, Replacement))) return false;
        TestEqual(TEXT("Body slot reused"), Replacement.Slot, C.Slot);
        TestTrue(TEXT("Body generation advanced"), Replacement.Generation > C.Generation);
        const FProphecyJoltBodyPair NewPair[] = { { B, Replacement } };
        if (!Okay(*this, TEXT("Create new-generation suppression"), World.CreateJoint(FreeJoint(A, B), MakeArrayView(NewPair), Second))
            || !Okay(*this, TEXT("Release old-generation owner"), World.DestroyJoint(First))
            || !Counts(*this, World, 1, 1)) return false;
        // The old joint's retired B/C entry must not decrement B/replacement's count.
        if (!Okay(*this, TEXT("Destroy an actual joint endpoint"), World.DestroyBody(Endpoint == 0 ? A : B))
            || !Counts(*this, World, 0, 0) || !Steps(*this, World, 4)) return false;
        TestFalse(TEXT("Endpoint removal destroyed constraint before body"), World.OwnsJoint(Second));
        FProphecyJoltJointSettings Read;
        TestEqual(TEXT("Stale joint read rejected"), World.ReadJoint(Second, Read).Code, EProphecyJoltWorldResult::InvalidHandle);
        FProphecyJoltJointHandle Reused;
        const auto Surviving = Endpoint == 0 ? B : A;
        if (!Okay(*this, TEXT("Reuse joint identity slot"), World.CreateJoint(FreeJoint(Surviving, Replacement), {}, Reused))) return false;
        TestEqual(TEXT("First free joint slot reused"), Reused.Slot, First.Slot);
        TestTrue(TEXT("Joint generation advanced"), Reused.Generation > First.Generation);
        TestFalse(TEXT("Old same-slot handle stays stale"), World.OwnsJoint(First));
        // A live joint intentionally remains for world teardown coverage.
    }
    // Rig-owned endpoint deletion must use the same external joint cleanup path.
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    const auto Snapshot = Rig(1);
    FProphecyJoltPreparedRig Prepared;
    FProphecyJoltRigHandle RigHandle;
    TArray<FProphecyJoltBodyHandle> Handles;
    FProphecyJoltBodyHandle Prop;
    if (!CreateRig(*this, World, Snapshot, Prepared, RigHandle, Handles)
        || !Okay(*this, TEXT("Create independently owned prop"), World.CreateSphere(5, {}, Prop))) return false;
    FProphecyJoltJointHandle Grip;
    if (!Okay(*this, TEXT("Join rig to independent prop"), World.CreateJoint(FreeJoint(Handles[0], Prop), {}, Grip))
        || !Okay(*this, TEXT("Destroy owner rig first"), World.DestroyRig(RigHandle)) || !Steps(*this, World, 4)) return false;
    TestFalse(TEXT("Owner rig teardown removed external grip"), World.OwnsJoint(Grip));
    FProphecyJoltBodyState Survivor;
    return Okay(*this, TEXT("Independent prop survives owner teardown"), World.ReadBody(Prop, Survivor)) && Counts(*this, World, 0, 0);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltJointPreflightTest,
    "Prophecy.Jolt.GenericJoint.CapacityAndAtomicPreflight", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltJointPreflightTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    FScopedWorld Scope;
    auto In = Settings(); In.MaxGenericJoints = In.MaxSuppressedBodyPairs = 1;
    if (!Start(*this, Scope, In)) return false;
    auto& World = *Scope.Get();
    FProphecyJoltFixtureBodySettings Body; Body.bDynamic = false;
    FProphecyJoltBodyHandle A, B, C;
    if (!Okay(*this, TEXT("Create static endpoint"), World.CreateSphere(2, Body, A))) return false;
    Body.bDynamic = true; Body.PositionCm.X = 30;
    if (!Okay(*this, TEXT("Create dynamic endpoint"), World.CreateSphere(2, Body, B))) return false;
    Body.PositionCm.X = 100;
    if (!Okay(*this, TEXT("Create third body"), World.CreateSphere(2, Body, C))) return false;
    FProphecyJoltJointSettings Fixed;
    Fixed.BodyA = A; Fixed.BodyB = B; Fixed.FrameA.SetTranslation(FVector(30, 0, 0));
    const FProphecyJoltBodyPair TooMany[] = { { A, B }, { B, C } };
    FProphecyJoltJointHandle Handle;
    TestEqual(TEXT("Whole pair batch is rejected before mutation"), World.CreateJoint(Fixed, MakeArrayView(TooMany), Handle).Code, EProphecyJoltWorldResult::CapacityExceeded);
    TestFalse(TEXT("Failed creation clears output identity"), Handle.IsSet());
    if (!Counts(*this, World, 0, 0)) return false;
    auto Bad = Fixed; Bad.FrameB.SetScale3D(FVector(2, 1, 1));
    TestEqual(TEXT("Scaled frame fails before creation"), World.CreateJoint(Bad, {}, Handle).Code, EProphecyJoltWorldResult::InvalidArgument);
    Bad = Fixed; Bad.BodyB = {};
    TestEqual(TEXT("Missing endpoint cannot become fixed-to-world"), World.CreateJoint(Bad, {}, Handle).Code, EProphecyJoltWorldResult::InvalidHandle);
    const FProphecyJoltBodyPair Pair[] = { { A, B }, { B, A } };
    if (!Okay(*this, TEXT("Deduplicated pair fits exact capacity"), World.CreateJoint(Fixed, MakeArrayView(Pair), Handle))) return false;
    TestEqual(TEXT("Invalid pair update is atomic"), World.UpdateJointSuppressedPairs(Handle, MakeArrayView(TooMany)).Code,
        EProphecyJoltWorldResult::CapacityExceeded);
    if (!Counts(*this, World, 1, 1)
        || !Okay(*this, TEXT("Enable contacts without replacing joint"), World.UpdateJointSuppressedPairs(Handle, {}))
        || !Counts(*this, World, 1, 0)
        || !Okay(*this, TEXT("Disable contacts on same joint"), World.UpdateJointSuppressedPairs(Handle, MakeArrayView(Pair)))
        || !Counts(*this, World, 1, 1)) return false;
    FProphecyJoltJointSettings Unchanged;
    if (!Okay(*this, TEXT("Read original connector after collision toggles"), World.ReadJoint(Handle, Unchanged))) return false;
    TestTrue(TEXT("Collision toggles preserve authored grip frames"),
        Unchanged.FrameA.Equals(Fixed.FrameA) && Unchanged.FrameB.Equals(Fixed.FrameB));
    FProphecyJoltJointHandle Overflow;
    TestEqual(TEXT("Joint capacity rejects second joint"), World.CreateJoint(Fixed, {}, Overflow).Code, EProphecyJoltWorldResult::CapacityExceeded);
    Bad = Fixed; Swap(Bad.BodyA, Bad.BodyB);
    TestEqual(TEXT("Endpoint order is immutable during updates"), World.UpdateJoint(Handle, Bad).Code, EProphecyJoltWorldResult::InvalidArgument);
    Bad = Fixed; Bad.FrameA.SetScale3D(FVector(2));
    TestEqual(TEXT("Invalid update preserves original native constraint"), World.UpdateJoint(Handle, Bad).Code, EProphecyJoltWorldResult::InvalidArgument);
    if (!Steps(*this, World)) return false;
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Read preserved grip"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Old connector still holds after invalid update"), State.PositionCm.Equals(FVector(30, 0, 0), 0.5));
    Fixed.FrameA.SetTranslation(FVector(40, 0, 0));
    if (!Okay(*this, TEXT("Replace fixed connector frames"), World.UpdateJoint(Handle, Fixed))
        || !Steps(*this, World)
        || !Okay(*this, TEXT("Read moved connector"), World.ReadBody(B, State))) return false;
    TestTrue(TEXT("Validated replacement changes actual target pose"), State.PositionCm.Equals(FVector(40, 0, 0), 0.5));
    if (!Okay(*this, TEXT("Shutdown with live joint and suppression"), World.ShutdownSimulation())
        || !Okay(*this, TEXT("Reinitialize new world lifetime"), World.InitializeSimulation(In))) return false;
    TestFalse(TEXT("Old joint cannot survive world lifetime change"), World.OwnsJoint(Handle));
    TestEqual(TEXT("Old body identities rejected in new world"), World.CreateJoint(Fixed, {}, Overflow).Code, EProphecyJoltWorldResult::InvalidHandle);
    return Counts(*this, World, 0, 0);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltAttachedCollisionTest,
    "Prophecy.Jolt.GenericJoint.KinematicFollowerContacts", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltAttachedCollisionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    FProphecyJoltBodyHandle Follower, Dynamic;
    FProphecyJoltFixtureBodySettings In;
    if (!Okay(*this,TEXT("Create follower shape"),World.CreateSphere(5,In,Follower))) return false;
    In.PositionCm = FVector(20,0,0);
    if (!Okay(*this,TEXT("Create simulated contact body"),World.CreateSphere(5,In,Dynamic))
        || !Okay(*this,TEXT("Make follower kinematic"),World.SetBodyKinematic(Follower))) return false;
    const FProphecyJoltBodyPair Pair[]={{Follower,Dynamic}};
    if (!Okay(*this,TEXT("Suppress owner during attack"),World.UpdateBodySuppressedPairs(Follower,MakeArrayView(Pair)))) return false;
    const auto StepFollower = [&]()
    {
        return Okay(*this,TEXT("Submit kinematic movement"),World.MoveKinematicBody(Follower,FTransform(FVector(15,0,0)),1.f/60))
            && Okay(*this,TEXT("Solve shared world"),World.Step(1.f/60,1));
    };
    for(int I=0;I<8;++I) if(!StepFollower()) return false;
    FProphecyJoltBodyState Before,After,Guide;
    if(!Okay(*this,TEXT("Read suppressed contact"),World.ReadBody(Dynamic,Before))) return false;
    TestTrue(TEXT("Attack exclusion prevents response"),Before.PositionCm.Equals(In.PositionCm,1.e-4));
    if(!Okay(*this,TEXT("Restore locomotion collision"),World.UpdateBodySuppressedPairs(Follower,{}))) return false;
    for(int I=0;I<30;++I) if(!StepFollower()) return false;
    if(!Okay(*this,TEXT("Read real contact response"),World.ReadBody(Dynamic,After))
        || !Okay(*this,TEXT("Read follower"),World.ReadBody(Follower,Guide))) return false;
    // Pinned Jolt PhysicsSettings allows 2 cm penetration. From 5 cm overlap,
    // this test must recover about 3 cm; it does not claim zero-penetration tuning.
    AddInfo(FString::Printf(TEXT("Contact displaced body from X=%.6f to X=%.6f cm"),Before.PositionCm.X,After.PositionCm.X));
    TestTrue(TEXT("Kinematic contact resolves overlap to the native 2 cm slop"),After.PositionCm.X>22.9);
    TestTrue(TEXT("Follower stays at target and is not dynamic"),!Guide.bDynamic && Guide.PositionCm.Equals(FVector(15,0,0),1.e-4));
    if(!Okay(*this,TEXT("Reapply owned exclusions"),World.UpdateBodySuppressedPairs(Follower,MakeArrayView(Pair)))
        || !Okay(*this,TEXT("Destroy follower"),World.DestroyBody(Follower))) return false;
    return Counts(*this,World,0,0) && !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltWeldedCollisionTest,
    "Prophecy.Jolt.GenericJoint.WeldedHandContacts", ProphecyJolt::GenericJointTests::Flags)

bool FProphecyJoltWeldedCollisionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::GenericJointTests;
    for (bool DestroyParent : {false, true})
    {
        FScopedWorld Scope;
        if (!Start(*this, Scope)) return false;
        auto& World = *Scope.Get();
        FProphecyJoltBodyHandle Hand, Sword, Thigh;
        FProphecyJoltFixtureBodySettings In;
        if (!Okay(*this,TEXT("Create light hand"),World.CreateSphere(2,In,Hand))) return false;
        In.PositionCm.X=10;
        if (!Okay(*this,TEXT("Create sword shape"),World.CreateSphere(5,In,Sword))) return false;
        In.PositionCm.X=16; In.MassKg=20;
        if (!Okay(*this,TEXT("Create heavy thigh"),World.CreateSphere(5,In,Thigh))) return false;
        const auto Impulse=[&](FProphecyJoltBodyState& Out)
        {
            FProphecyJoltPhysicsCommand C;
            C.Operation=EProphecyJoltPhysicsCommand::Impulse; C.Value=FVector(1,0,0);
            if (!Okay(*this,TEXT("Linear impulse"),World.ExecutePhysicsCommand(Hand,C))) return false;
            C.Operation=EProphecyJoltPhysicsCommand::AngularImpulse; C.Value=FVector(0,0,1);
            return Okay(*this,TEXT("Angular impulse"),World.ExecutePhysicsCommand(Hand,C))
                && Okay(*this,TEXT("Read impulse response"),World.ReadBody(Hand,Out))
                && Okay(*this,TEXT("Clear velocities"),World.SetBodyVelocity(Hand,{},{},true));
        };
        FProphecyJoltBodyState Original, Welded, HandState, SwordState, ThighState;
        if (!Impulse(Original)
            || !Okay(*this,TEXT("Weld without extra mass"),World.WeldBodyShape(Hand,Sword,FTransform(FVector(10,0,0))))
            || !Impulse(Welded)) return false;
        TestTrue(TEXT("Weld preserves mass and inertia exactly"),Original.CenterOfMassVelocityCmPerSecond.Equals(Welded.CenterOfMassVelocityCmPerSecond,1.e-6)
            && Original.AngularVelocityRadiansPerSecond.Equals(Welded.AngularVelocityRadiansPerSecond,1.e-6));
        TestTrue(TEXT("Weld preserves origin and COM"),Original.PositionCm.Equals(Welded.PositionCm,1.e-5)
            && Original.CenterOfMassPositionCm.Equals(Welded.CenterOfMassPositionCm,1.e-5));
        FProphecyJoltBodyState Two, Five;
        if (!Okay(*this,TEXT("Set attached inertia to 2 live"),World.SetWeldedBodyInertiaScale(Sword,2)) || !Impulse(Two)
            || !Okay(*this,TEXT("Set attached inertia to 5 live"),World.SetWeldedBodyInertiaScale(Sword,5)) || !Impulse(Five)) return false;
        TestTrue(TEXT("Higher attached inertia reduces angular response without adding mass"),
            Two.CenterOfMassVelocityCmPerSecond.Equals(Original.CenterOfMassVelocityCmPerSecond,1.e-6)
            && Five.CenterOfMassVelocityCmPerSecond.Equals(Original.CenterOfMassVelocityCmPerSecond,1.e-6)
            && Two.AngularVelocityRadiansPerSecond.Z<Original.AngularVelocityRadiansPerSecond.Z
            && Five.AngularVelocityRadiansPerSecond.Z<Two.AngularVelocityRadiansPerSecond.Z);
        TestEqual(TEXT("Negative scale rejected"),World.SetWeldedBodyInertiaScale(Sword,-1).Code,EProphecyJoltWorldResult::InvalidArgument);
        if (!Okay(*this,TEXT("Seed velocity before setting"),World.SetBodyVelocity(Hand,FVector(1,2,3),FVector(0.1,0.2,0.3),true))
            || !Okay(*this,TEXT("Restore original hand inertia at zero"),World.SetWeldedBodyInertiaScale(Sword,0))
            || !Okay(*this,TEXT("Inspect unchanged velocity"),World.ReadBody(Hand,HandState))) return false;
        TestTrue(TEXT("Setting preserves linear and angular velocity"),HandState.CenterOfMassVelocityCmPerSecond.Equals(FVector(1,2,3),1.e-5)
            && HandState.AngularVelocityRadiansPerSecond.Equals(FVector(0.1,0.2,0.3),1.e-5));
        if (!World.SetBodyVelocity(Hand,{},{},true).IsSuccess() || !Impulse(Welded)) return false;
        TestTrue(TEXT("Zero restores original inertia, not cumulative scaling"),Original.AngularVelocityRadiansPerSecond.Equals(Welded.AngularVelocityRadiansPerSecond,1.e-6));
        FProphecyJoltRayHit Hit; bool bHit=false;
        if (!Okay(*this,TEXT("Query welded sword"),World.RayCast(FVector(10,0,20),FVector(10,0,-20),Hit,bHit))) return false;
        TestTrue(TEXT("Sword leaf retains query identity"),bHit && Hit.Handle.WorldLifetime==Sword.WorldLifetime
            && Hit.Handle.Slot==Sword.Slot && Hit.Handle.Generation==Sword.Generation);
        const FProphecyJoltBodyPair Pair[]={{Sword,Thigh}};
        if (!Okay(*this,TEXT("Attack suppression"),World.UpdateBodySuppressedPairs(Sword,MakeArrayView(Pair)))
            || !Steps(*this,World,8) || !Okay(*this,TEXT("Read suppressed hand"),World.ReadBody(Hand,HandState))) return false;
        TestTrue(TEXT("Suppressed sword does not move hand"),HandState.PositionCm.IsNearlyZero(1.e-4));
        FProphecyJoltCollisionUpdate Channels; Channels.Handle=Sword; Channels.Responses.SetAllChannels(ECR_Ignore);
        if (!Okay(*this,TEXT("Sword channel ignore"),World.UpdateBodyCollision(MakeArrayView(&Channels,1)))
            || !Okay(*this,TEXT("Remove attack suppression"),World.UpdateBodySuppressedPairs(Sword,{}))
            || !Steps(*this,World,8) || !Okay(*this,TEXT("Read ignored hand"),World.ReadBody(Hand,HandState))) return false;
        TestTrue(TEXT("Sword channels remain independent"),HandState.PositionCm.IsNearlyZero(1.e-4));
        Channels.Responses.SetAllChannels(ECR_Block);
        if (!Okay(*this,TEXT("Restore sword channel blocking"),World.UpdateBodyCollision(MakeArrayView(&Channels,1)))
            || !Steps(*this,World,60)
            || !Okay(*this,TEXT("Read yielding hand"),World.ReadBody(Hand,HandState))
            || !Okay(*this,TEXT("Read attached sword"),World.ReadBody(Sword,SwordState))
            || !Okay(*this,TEXT("Read contacted thigh"),World.ReadBody(Thigh,ThighState))) return false;
        AddInfo(FString::Printf(TEXT("Weld contact: hand X=%.6f, thigh X=%.6f cm"),HandState.PositionCm.X,ThighState.PositionCm.X));
        TestTrue(TEXT("Sword contact pushes light hand away, not an infinite-mass wall"),HandState.PositionCm.X < -1.5
            && ThighState.PositionCm.X < 16.2);
        const FVector Expected=HandState.PositionCm+HandState.Rotation.RotateVector(FVector(10,0,0));
        TestTrue(TEXT("Sword cannot detach from hand"),SwordState.PositionCm.Equals(Expected,1.e-4));
        if (!Okay(*this,TEXT("Keep attack exclusions during endpoint teardown"),World.UpdateBodySuppressedPairs(Sword,MakeArrayView(Pair)))) return false;
        if (!Okay(*this,TEXT("Leave nonzero inertia during endpoint teardown"),World.SetWeldedBodyInertiaScale(Sword,2))) return false;
        if (!Okay(*this,TEXT("Destroy weld endpoint"),World.DestroyBody(DestroyParent ? Hand : Sword))) return false;
        TestFalse(TEXT("Weld retired on either endpoint removal"),World.IsBodyShapeWelded(Sword));
        if (DestroyParent)
        {
            if (!Okay(*this,TEXT("Source survives parent removal"),World.ReadBody(Sword,SwordState))) return false;
            TestTrue(TEXT("Released source resumes independent dynamics"),SwordState.bDynamic);
        }
        else
        {
            if (!World.SetBodyVelocity(Hand,{},{},true).IsSuccess() || !Impulse(Welded)) return false;
            TestTrue(TEXT("Unweld preserves original hand response"),Original.CenterOfMassVelocityCmPerSecond.Equals(Welded.CenterOfMassVelocityCmPerSecond,1.e-6)
                && Original.AngularVelocityRadiansPerSecond.Equals(Welded.AngularVelocityRadiansPerSecond,1.e-6));
        }
        if (!Counts(*this,World,0,DestroyParent ? 1 : 0) || !Steps(*this,World,4)) return false;
    }
    return !HasAnyErrors();
}

#endif
