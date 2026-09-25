#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "HAL/IConsoleManager.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltFootJointLibrary.h"
#include "ProphecyJoltPhysicsCommand.h"
#include <limits>

namespace ProphecyJolt::RigWorldTests
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
    ~FScopedWorld() { Destroy(); }
    void Destroy()
    {
        if (!World) return;
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
        World->MarkAsGarbage();
        World = nullptr;
    }
    UProphecyJoltWorldSubsystem* Get() const { return World ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr; }
    UWorld* World = nullptr;
};

bool Okay(FAutomationTestBase& Test, const TCHAR* Context, const FProphecyJoltWorldStatus& Status)
{
    if (Status.IsSuccess()) return true;
    Test.AddError(FString::Printf(TEXT("%s: result %u: %s"), Context, static_cast<uint32>(Status.Code), *Status.Message));
    return false;
}

FProphecyJoltWorldSettings SmallWorld(uint32 Capacity = 4)
{
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    Settings.MaxBodies = Capacity;
    Settings.MaxBodyPairs = 32;
    Settings.MaxContactConstraints = 32;
    return Settings;
}

FProphecyJoltRigSnapshot MakeRig()
{
    FProphecyJoltRigSnapshot Snapshot;
    Snapshot.CaptureId = FGuid::NewGuid();
    Snapshot.ComponentPath = TEXT("Synthetic two-body automation fixture; no source component or asset");
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FProphecyJoltRigBody& Body = Snapshot.Bodies.AddDefaulted_GetRef();
        Body.SourceBodyIndex = Body.BoneIndex = Index;
        Body.BodyName = Index == 0 ? FName(TEXT("parent")) : FName(TEXT("child"));
        Body.BodyOriginToWorld = FTransform(FQuat::Identity, FVector(0.0, 0.0, 100.0 + 40.0 * Index));
        Body.MassKg = 2.0;
        // Solid sphere: I = (2/5) * 2 kg * (10 cm)^2, explicitly supplied.
        Body.PrincipalInertiaKgCmSquared = FVector(80.0);
        Body.bSimulating = Body.bAwake = true;
        Body.bGravityEnabled = false;
        Body.MaxLinearVelocityCmPerSecond = 50000.0;
        Body.MaxAngularVelocityRadiansPerSecond = 15.0 * UE_DOUBLE_PI;
        Body.PositionSolverIterations = 4;
        Body.VelocitySolverIterations = 1;
        Body.ProjectionSolverIterations = 0;
        Body.CollisionEnabled = ECollisionEnabled::QueryAndPhysics;
        Body.ObjectType = ECC_PhysicsBody;
        Body.CollisionResponses.SetAllChannels(ECR_Ignore);
        Body.CollisionResponses.SetResponse(ECC_WorldStatic, ECR_Block);
        FProphecyJoltRigShape& Shape = Body.Shapes.AddDefaulted_GetRef();
        Shape.Kind = EProphecyJoltRigShape::Sphere;
        Shape.SourceElementIndex = 0;
        Shape.ElementName = TEXT("sphere");
        Shape.RadiusCm = 10.0;
        Shape.AuthoredCollisionEnabled = Shape.CurrentCollisionEnabled = ECollisionEnabled::QueryAndPhysics;
        Shape.bContributesToAuthoredMass = true;
    }
    FProphecyJoltRigJoint& Joint = Snapshot.Joints.AddDefaulted_GetRef();
    Joint.SourceConstraintIndex = 0;
    Joint.JointName = TEXT("child_to_parent");
    Joint.Body1Index = 1; // UE child; the adapter deliberately creates Jolt parent first.
    Joint.Body2Index = 0;
    Joint.Bone1 = Snapshot.Bodies[1].BodyName;
    Joint.Bone2 = Snapshot.Bodies[0].BodyName;
    Joint.Frame1 = FTransform(FQuat::Identity, FVector(0.0, 0.0, -20.0));
    Joint.Frame2 = FTransform(FQuat::Identity, FVector(0.0, 0.0, 20.0));
    FConstraintProfileProperties& Profile = Joint.CurrentProfile;
    Profile.LinearLimit.XMotion = Profile.LinearLimit.YMotion = Profile.LinearLimit.ZMotion = LCM_Locked;
    Profile.ConeLimit.Swing1Motion = Profile.ConeLimit.Swing2Motion = ACM_Limited;
    Profile.ConeLimit.Swing1LimitDegrees = 35.0f;
    Profile.ConeLimit.Swing2LimitDegrees = 20.0f;
    Profile.TwistLimit.TwistMotion = ACM_Limited;
    Profile.TwistLimit.TwistLimitDegrees = 15.0f;
    Profile.ConeLimit.bSoftConstraint = Profile.TwistLimit.bSoftConstraint = false;
    Profile.bDisableCollision = true;
    Profile.bEnableProjection = Profile.bEnableMassConditioning = Profile.bEnableShockPropagation = false;
    Profile.bParentDominates = Profile.bUseLinearJointSolver = false;
    Profile.LinearDrive.XDrive.bEnablePositionDrive = Profile.LinearDrive.XDrive.bEnableVelocityDrive = false;
    Profile.LinearDrive.YDrive.bEnablePositionDrive = Profile.LinearDrive.YDrive.bEnableVelocityDrive = false;
    Profile.LinearDrive.ZDrive.bEnablePositionDrive = Profile.LinearDrive.ZDrive.bEnableVelocityDrive = false;
    Profile.AngularDrive.AngularDriveMode = EAngularDriveMode::SLERP;
    Profile.AngularDrive.SlerpDrive.bEnablePositionDrive = Profile.AngularDrive.SlerpDrive.bEnableVelocityDrive = false;
    Profile.AngularDrive.SwingDrive.bEnablePositionDrive = Profile.AngularDrive.SwingDrive.bEnableVelocityDrive = false;
    Profile.AngularDrive.TwistDrive.bEnablePositionDrive = Profile.AngularDrive.TwistDrive.bEnableVelocityDrive = false;
    FProphecyJoltRigDisabledPair& Pair = Snapshot.DisabledPairs.AddDefaulted_GetRef();
    Pair.Body1Index = 0;
    Pair.Body2Index = 1;
    Pair.bFromCurrentJoint = true;
    return Snapshot;
}

bool Prepare(FAutomationTestBase& Test, const FProphecyJoltRigSnapshot& Snapshot, FProphecyJoltPreparedRig& Prepared)
{
    FString Error;
    const bool bBuilt = Prepared.Build(Snapshot, Error);
    return Test.TestTrue(FString(TEXT("Prepare complete synthetic rig: ")) + Error, bBuilt);
}

bool Counts(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& Owner, uint32 Bodies, uint32 Constraints)
{
    FProphecyJoltWorldDiagnostics Diagnostics;
    return Okay(Test, TEXT("Read rig owner diagnostics"), Owner.GetDiagnostics(Diagnostics))
        && Test.TestEqual(TEXT("Owner has exactly the expected bodies"), Diagnostics.BodyCount, Bodies)
        && Test.TestEqual(TEXT("Owner has exactly the expected constraints"), Diagnostics.ConstraintCount, Constraints);
}

bool SameHandle(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

TArray<FProphecyJoltRigVelocityTarget> MakeTargets(const FProphecyJoltRigSnapshot& Snapshot,
    const TArray<FProphecyJoltBodyHandle>& Handles)
{
    check(Handles.Num() == Snapshot.Bodies.Num());
    TArray<FProphecyJoltRigVelocityTarget> Targets;
    // Reverse publication order to test handle mapping independently of rig order.
    for (int32 Index = Handles.Num() - 1; Index >= 0; --Index)
    {
        FProphecyJoltRigVelocityTarget& Target = Targets.AddDefaulted_GetRef();
        Target.Handle = Handles[Index];
        Target.TargetPositionCm = Snapshot.Bodies[Index].BodyOriginToWorld.GetTranslation() + FVector(6.0, 0.0, 0.0);
        Target.TargetRotation = Snapshot.Bodies[Index].BodyOriginToWorld.GetRotation();
    }
    return Targets;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigWorldPreflightTest,
    "Prophecy.Jolt.RigWorld.AtomicPreflight", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigWorldPreflightTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    const int32 InitialWorlds = UProphecyJoltWorldSubsystem::GetLiveSimulationCount();
    const int32 InitialPrepared = FProphecyJoltPreparedRig::GetLivePreparedRigCount();
    {
        const FProphecyJoltRigSnapshot Snapshot = MakeRig();
        const FProphecyJoltRigSnapshot OtherSnapshot = MakeRig();
        FProphecyJoltPreparedRig Prepared, OtherPrepared;
        if (!Prepare(*this, Snapshot, Prepared) || !Prepare(*this, OtherSnapshot, OtherPrepared)) return false;
        FScopedWorld Scope;
        UProphecyJoltWorldSubsystem* Owner = Scope.Get();
        if (!TestNotNull(TEXT("Game rig owner"), Owner)
            || !Okay(*this, TEXT("Initialize bounded owner"), Owner->InitializeSimulation(SmallWorld(2)))) return false;
        FProphecyJoltFixtureBodySettings SentinelSettings;
        SentinelSettings.bDynamic = false;
        SentinelSettings.PositionCm = FVector(500.0, 0.0, 0.0);
        FProphecyJoltBodyHandle Sentinel;
        if (!Okay(*this, TEXT("Create preexisting sentinel"), Owner->CreateSphere(10.0, SentinelSettings, Sentinel))) return false;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FString> Notes;
        Handles.Add(Sentinel);
        Notes.Add(TEXT("Caller output must be cleared on failure"));
        TestTrue(TEXT("Different prepared capture is rejected before mutation"),
            Owner->CreateRigFixture(Snapshot, OtherPrepared, Handles, Notes).Code == EProphecyJoltWorldResult::InvalidArgument);
        TestTrue(TEXT("Failed preflight clears both output arrays"), Handles.IsEmpty() && Notes.IsEmpty());
        if (!Counts(*this, *Owner, 1, 0)) return false;
        TestTrue(TEXT("Complete two-body rig cannot partially fit one free slot"),
            Owner->CreateRigFixture(Snapshot, Prepared, Handles, Notes).Code == EProphecyJoltWorldResult::CapacityExceeded);
        TestTrue(TEXT("Capacity failure exposes no partial rig"), Handles.IsEmpty() && Notes.IsEmpty());
        if (!Counts(*this, *Owner, 1, 0)) return false;
        FProphecyJoltBodyState SentinelState;
        if (!Okay(*this, TEXT("Read sentinel after both failures"), Owner->ReadBody(Sentinel, SentinelState))) return false;
        TestNearlyEqual(TEXT("Failed creations preserve the existing body"), SentinelState.PositionCm, SentinelSettings.PositionCm, 1.0e-6f);

        // All body data prepares successfully, but the final joint is outside
        // the explicitly supported Locked/Free translation contract.
        FProphecyJoltRigSnapshot InvalidJoint = MakeRig();
        InvalidJoint.Joints[0].CurrentProfile.LinearLimit.XMotion = LCM_Limited;
        FProphecyJoltPreparedRig InvalidJointPrepared;
        if (!Prepare(*this, InvalidJoint, InvalidJointPrepared)
            || !Okay(*this, TEXT("Free capacity for late joint preflight"), Owner->DestroyBody(Sentinel))) return false;
        TestTrue(TEXT("Joint conversion failure occurs before any body is created"),
            Owner->CreateRigFixture(InvalidJoint, InvalidJointPrepared, Handles, Notes).Code == EProphecyJoltWorldResult::InvalidArgument);
        if (!Counts(*this, *Owner, 0, 0)) return false;
        TestTrue(TEXT("Rejected joint returns no handles or coverage claim"), Handles.IsEmpty() && Notes.IsEmpty());
        if (!Okay(*this, TEXT("Valid complete rig remains creatable after all failed preflights"), Owner->CreateRigFixture(Snapshot, Prepared, Handles, Notes))
            || !Counts(*this, *Owner, 2, 1)) return false;
        TestEqual(TEXT("One adapter handle per descriptor body"), Handles.Num(), 2);
        TestFalse(TEXT("Fixture limitations are reported"), Notes.IsEmpty());
        if (!Okay(*this, TEXT("Remove complete rig"), Owner->DestroyRigFixture()) || !Counts(*this, *Owner, 0, 0)) return false;
    }
    TestEqual(TEXT("Preflight fixture releases native worlds"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialWorlds);
    TestEqual(TEXT("Preflight fixture releases all prepared shapes"), FProphecyJoltPreparedRig::GetLivePreparedRigCount(), InitialPrepared);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigInitialVelocityCapsTest,
    "Prophecy.Jolt.RigWorld.InitialVelocityCaps", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigInitialVelocityCapsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    auto Snapshot = MakeRig();
    const FVector LinearDirection = FVector(3, -4, 0).GetSafeNormal();
    const FVector AngularDirection = FVector(-2, 1, 2).GetSafeNormal();
    for (auto& Body : Snapshot.Bodies)
    {
        Body.CenterOfMassVelocityCmPerSecond = LinearDirection * Body.MaxLinearVelocityCmPerSecond * 3.0;
        Body.AngularVelocityRadiansPerSecond = AngularDirection * Body.MaxAngularVelocityRadiansPerSecond * 4.0;
    }
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    FProphecyJoltPreparedRig Prepared;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FString> Notes;
    if (!TestNotNull(TEXT("Rig world owner"), Owner)
        || !Okay(*this, TEXT("Initialize overspeed rig world"), Owner->InitializeSimulation(SmallWorld()))
        || !Prepare(*this, Snapshot, Prepared)
        || !Okay(*this, TEXT("Create complete rig from captured overspeed"), Owner->CreateRigFixture(Snapshot, Prepared, Handles, Notes))
        || !TestEqual(TEXT("Both captured bodies are created"), Handles.Num(), Snapshot.Bodies.Num())) return false;
    // Before any step or servo packet, both bodies must already have safe native velocities.
    for (int32 Index = 0; Index < Handles.Num(); ++Index)
    {
        FProphecyJoltBodyState State;
        if (!Okay(*this, TEXT("Read clamped initial rig velocity"), Owner->ReadBody(Handles[Index], State))) return false;
        const auto& Body = Snapshot.Bodies[Index];
        TestNearlyEqual(TEXT("Initial rig linear speed uses the unchanged captured cap"),
            State.CenterOfMassVelocityCmPerSecond.Size(), Body.MaxLinearVelocityCmPerSecond, 0.02);
        TestNearlyEqual(TEXT("Initial rig angular speed uses the unchanged captured cap"),
            State.AngularVelocityRadiansPerSecond.Size(), Body.MaxAngularVelocityRadiansPerSecond, 0.001);
        TestTrue(TEXT("Rig linear clamping preserves captured world direction"),
            State.CenterOfMassVelocityCmPerSecond.GetSafeNormal().Equals(LinearDirection, 1.0e-6));
        TestTrue(TEXT("Rig angular clamping preserves captured world direction"),
            State.AngularVelocityRadiansPerSecond.GetSafeNormal().Equals(AngularDirection, 1.0e-6));
        TestTrue(TEXT("Creation retains the rig body's captured awake state"), State.bActive);
    }
    return Counts(*this, *Owner, 2, 1)
        && Okay(*this, TEXT("Destroy clamped rig"), Owner->DestroyRigFixture()) && !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigWorldHandlesTest,
    "Prophecy.Jolt.RigWorld.ServoHandlesAndWholeRigRemoval", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigWorldHandlesTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    const FProphecyJoltRigSnapshot Snapshot = MakeRig();
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld First, Second;
    UProphecyJoltWorldSubsystem* Owner = First.Get();
    UProphecyJoltWorldSubsystem* OtherOwner = Second.Get();
    if (!TestNotNull(TEXT("First Game rig owner"), Owner) || !TestNotNull(TEXT("Second Game rig owner"), OtherOwner)
        || !Okay(*this, TEXT("Initialize first owner"), Owner->InitializeSimulation(SmallWorld()))
        || !Okay(*this, TEXT("Initialize independent owner"), OtherOwner->InitializeSimulation(SmallWorld()))) return false;
    FProphecyJoltFixtureBodySettings SentinelSettings;
    SentinelSettings.bDynamic = false;
    SentinelSettings.PositionCm = FVector(500.0, 0.0, 0.0);
    FProphecyJoltBodyHandle Sentinel;
    if (!Okay(*this, TEXT("Create independent sentinel"), Owner->CreateSphere(10.0, SentinelSettings, Sentinel))) return false;
    TArray<FProphecyJoltBodyHandle> Handles, OtherHandles, RejectedHandles;
    TArray<FString> Notes;
    if (!Okay(*this, TEXT("Create first rig"), Owner->CreateRigFixture(Snapshot, Prepared, Handles, Notes))
        || !Okay(*this, TEXT("Reuse immutable preparation in another world"), OtherOwner->CreateRigFixture(Snapshot, Prepared, OtherHandles, Notes))
        || !TestEqual(TEXT("First rig has two handles"), Handles.Num(), 2)
        || !TestEqual(TEXT("Other rig has two handles"), OtherHandles.Num(), 2)) return false;
    TestTrue(TEXT("Exact ordered rig handles prove current ownership"), Owner->OwnsRigFixture(Handles));
    TestFalse(TEXT("Cross-world handles never prove rig ownership"), Owner->OwnsRigFixture(OtherHandles));
    TestFalse(TEXT("Empty handles never prove rig ownership"), Owner->OwnsRigFixture(RejectedHandles));
    TestFalse(TEXT("A partial handle set cannot own the complete rig"), Owner->OwnsRigFixture(MakeArrayView(Handles.GetData(), 1)));
    TArray<FProphecyJoltBodyHandle> WrongIdentity = Handles;
    Swap(WrongIdentity[0], WrongIdentity[1]);
    TestFalse(TEXT("Ownership requires captured order, not merely matching membership"), Owner->OwnsRigFixture(WrongIdentity));
    WrongIdentity = Handles;
    WrongIdentity[1] = WrongIdentity[0];
    TestFalse(TEXT("Duplicated handles cannot prove complete ownership"), Owner->OwnsRigFixture(WrongIdentity));
    WrongIdentity = Handles;
    WrongIdentity[1] = Sentinel;
    TestFalse(TEXT("A live non-rig body cannot stand in for a rig member"), Owner->OwnsRigFixture(WrongIdentity));
    WrongIdentity = Handles;
    ++WrongIdentity[0].Generation;
    TestFalse(TEXT("A wrong generation cannot prove rig ownership"), Owner->OwnsRigFixture(WrongIdentity));
    TestTrue(TEXT("A second whole rig requires explicit destruction"),
        Owner->CreateRigFixture(Snapshot, Prepared, RejectedHandles, Notes).Code == EProphecyJoltWorldResult::AlreadyInitialized);
    TestTrue(TEXT("Rejected second rig has no handles"), RejectedHandles.IsEmpty());
    TestTrue(TEXT("Individual rig-body deletion is rejected"), Owner->DestroyBody(Handles[0]).Code == EProphecyJoltWorldResult::InvalidArgument);
    if (!Counts(*this, *Owner, 3, 1)) return false;
    FProphecyJoltBodyState BodyState;
    TestTrue(TEXT("Cross-world rig body cannot be read"), Owner->ReadBody(OtherHandles[0], BodyState).Code == EProphecyJoltWorldResult::InvalidHandle);
    TArray<FProphecyJoltRigVelocityTarget> Targets = MakeTargets(Snapshot, Handles);
    if (!Okay(*this, TEXT("Publish reversed-order complete rig targets"), Owner->PublishRigFixtureVelocityTargets(Targets, 0.1f))) return false;
    const TArray<FProphecyJoltRigVelocityTarget> WrongWorldTargets = MakeTargets(Snapshot, OtherHandles);
    TestTrue(TEXT("Cross-world publication fails without replacing valid targets"),
        Owner->PublishRigFixtureVelocityTargets(WrongWorldTargets, 0.2f).Code == EProphecyJoltWorldResult::InvalidHandle);
    FProphecyJoltRigVelocityTarget NonRigTarget;
    NonRigTarget.Handle = Sentinel;
    TestTrue(TEXT("A live generic body is also invalid as a rig target"),
        Owner->PublishRigFixtureVelocityTargets(MakeArrayView(&NonRigTarget, 1), 0.1f).Code == EProphecyJoltWorldResult::InvalidHandle);
    Prepared.Reset(); // The two live native worlds must own their body shapes independently.
    if (!Okay(*this, TEXT("Step complete rig after preparation is released"), Owner->Step(1.0f / 60.0f, 1))) return false;
    FProphecyJoltRigServoState Servo;
    if (!Okay(*this, TEXT("Read real rig servo samples"), Owner->ReadRigFixtureServoSamples(Servo))
        || !TestEqual(TEXT("Both targets were consumed"), Servo.Samples.Num(), 2)) return false;
    TestEqual(TEXT("Exactly one real servo invocation"), Servo.InvocationCount, uint64(1));
    TestEqual(TEXT("No stale native bodies reached the callback"), Servo.InvalidBodyCount, uint64(0));
    TestNearlyEqual(TEXT("Failed publication preserved the original denominator"), Servo.DenominatorSeconds, 0.1f, 1.0e-8f);
    for (int32 Index = 0; Index < Servo.Samples.Num(); ++Index)
    {
        const auto& Sample = Servo.Samples[Index];
        TestTrue(TEXT("Sample maps to the published adapter handle, not descriptor order"), SameHandle(Sample.Handle, Targets[Index].Handle));
        TestTrue(TEXT("Rig callback has a valid before/after sample"), Sample.bValid);
        TestNearlyEqual(TEXT("Coherent translation writes 60 cm/s before joint solving"), Sample.LinearAfterCmPerSecond,
            FVector(60.0, 0.0, 0.0), 2.0e-3f);
        if (!Okay(*this, TEXT("Read stepped rig body"), Owner->ReadBody(Sample.Handle, BodyState))) return false;
        TestTrue(TEXT("The initial awake rig was actually simulated"), BodyState.bActive);
        TestNearlyEqual(TEXT("Constraint-preserving translation advances the current step"), BodyState.PositionCm,
            Sample.PositionCm + FVector(1.0, 0.0, 0.0), 2.0e-3f);
    }
    if (!Okay(*this, TEXT("Read untouched second world"), OtherOwner->ReadBody(OtherHandles[0], BodyState))) return false;
    TestNearlyEqual(TEXT("First-world stepping preserves independent rig"), BodyState.PositionCm,
        Snapshot.Bodies[0].BodyOriginToWorld.GetTranslation(), 1.0e-6f);
    if (!Okay(*this, TEXT("Destroy constraints and complete rig"), Owner->DestroyRigFixture())
        || !Okay(*this, TEXT("Whole-rig destruction is idempotent"), Owner->DestroyRigFixture())
        || !Counts(*this, *Owner, 1, 0)) return false;
    TestFalse(TEXT("Removed rig no longer belongs to its old handle set"), Owner->OwnsRigFixture(Handles));
    for (const auto& Handle : Handles)
        TestTrue(TEXT("Every removed rig handle is invalid"), Owner->ReadBody(Handle, BodyState).Code == EProphecyJoltWorldResult::InvalidHandle);
    if (!Okay(*this, TEXT("Read cleared listener"), Owner->ReadRigFixtureServoSamples(Servo))) return false;
    TestTrue(TEXT("Rig teardown clears listener samples"), Servo.Samples.IsEmpty());
    TestEqual(TEXT("Rig teardown clears invocation history"), Servo.InvocationCount, uint64(0));
    // The public API cannot expose the internal removal sequence. Zero remaining
    // constraints plus successful stepping/recreation checks its observable safety.
    if (!Okay(*this, TEXT("Step surviving world after rig removal"), Owner->Step(1.0f / 60.0f, 1))
        || !Okay(*this, TEXT("Sentinel survives whole-rig removal"), Owner->ReadBody(Sentinel, BodyState))
        || !Prepare(*this, Snapshot, Prepared)) return false;
    TestNearlyEqual(TEXT("Whole-rig removal preserved non-rig body"), BodyState.PositionCm, SentinelSettings.PositionCm, 1.0e-6f);
    TArray<FProphecyJoltBodyHandle> NewHandles;
    if (!Okay(*this, TEXT("Recreate complete rig in freed slots"), Owner->CreateRigFixture(Snapshot, Prepared, NewHandles, Notes))
        || !Counts(*this, *Owner, 3, 1)) return false;
    TestTrue(TEXT("Replacement rig belongs to its new complete handle set"), Owner->OwnsRigFixture(NewHandles));
    TestFalse(TEXT("Old owner cannot claim a replacement rig in reused slots"), Owner->OwnsRigFixture(Handles));
    for (const auto& OldHandle : Handles)
        TestTrue(TEXT("Slot reuse never revives an old rig generation"), Owner->ReadBody(OldHandle, BodyState).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Stale publication after slot reuse is rejected"),
        Owner->PublishRigFixtureVelocityTargets(Targets, 0.1f).Code == EProphecyJoltWorldResult::InvalidHandle);
    // Exercise cleanup while readiness is deliberately unavailable. This does not fault/inject a
    // solver failure: it checks the real world-ending gate that used to break ReadBody-based ownership.
    First.World->bIsTearingDown = true;
    TestTrue(TEXT("Readiness correctly rejects body access during teardown"),
        Owner->ReadBody(NewHandles[0], BodyState).Code == EProphecyJoltWorldResult::WorldEnding);
    TestTrue(TEXT("Identity remains available when world readiness ends"), Owner->OwnsRigFixture(NewHandles));
    const FProphecyJoltWorldStatus RemovedDuringTeardown = Owner->DestroyRigFixture();
    TestFalse(TEXT("Teardown cleanup invalidates ownership immediately"), Owner->OwnsRigFixture(NewHandles));
    First.World->bIsTearingDown = false;
    if (!Okay(*this, TEXT("Remove owned rig despite teardown readiness gate"), RemovedDuringTeardown)
        || !Counts(*this, *Owner, 1, 0)) return false;
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigWorldShutdownTest,
    "Prophecy.Jolt.RigWorld.LiveRigShutdownAndReinitialize", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigWorldShutdownTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    const int32 InitialWorlds = UProphecyJoltWorldSubsystem::GetLiveSimulationCount();
    const int32 InitialPrepared = FProphecyJoltPreparedRig::GetLivePreparedRigCount();
    {
        const FProphecyJoltRigSnapshot Snapshot = MakeRig();
        FProphecyJoltPreparedRig Prepared;
        if (!Prepare(*this, Snapshot, Prepared)) return false;
        FScopedWorld Scope;
        UProphecyJoltWorldSubsystem* Owner = Scope.Get();
        if (!TestNotNull(TEXT("Shutdown fixture Game owner"), Owner)
            || !Okay(*this, TEXT("Initialize live-rig shutdown fixture"), Owner->InitializeSimulation(SmallWorld()))) return false;
        TArray<FProphecyJoltBodyHandle> OldHandles, NewHandles;
        TArray<FString> Notes;
        if (!Okay(*this, TEXT("Create rig before shutdown"), Owner->CreateRigFixture(Snapshot, Prepared, OldHandles, Notes))
            || !TestEqual(TEXT("Shutdown rig has two handles"), OldHandles.Num(), 2)) return false;
        const TArray<FProphecyJoltRigVelocityTarget> Targets = MakeTargets(Snapshot, OldHandles);
        if (!Okay(*this, TEXT("Leave live servo targets for owner cleanup"), Owner->PublishRigFixtureVelocityTargets(Targets, 0.1f))
            || !Okay(*this, TEXT("Consume targets before shutdown"), Owner->Step(1.0f / 60.0f, 1))
            || !Okay(*this, TEXT("Shutdown owner with live joints, bodies and listener"), Owner->ShutdownSimulation())
            || !Okay(*this, TEXT("Repeated owner shutdown"), Owner->ShutdownSimulation())
            || !Okay(*this, TEXT("Rig destruction after owner shutdown"), Owner->DestroyRigFixture())) return false;
        TestEqual(TEXT("Explicit shutdown releases the entire native owner"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialWorlds);
        FProphecyJoltBodyState BodyState;
        TestTrue(TEXT("Body access while stopped requires initialization"), Owner->ReadBody(OldHandles[0], BodyState).Code == EProphecyJoltWorldResult::NotInitialized);
        TestFalse(TEXT("Shutdown native lifetime cannot still own the old rig"), Owner->OwnsRigFixture(OldHandles));
        FProphecyJoltWorldDiagnostics Diagnostics;
        if (!Okay(*this, TEXT("Read stopped diagnostics"), Owner->GetDiagnostics(Diagnostics))) return false;
        TestFalse(TEXT("Stopped owner reports no simulation"), Diagnostics.bInitialized);
        TestEqual(TEXT("Stopped diagnostics have no bodies"), Diagnostics.BodyCount, uint32(0));
        TestEqual(TEXT("Stopped diagnostics have no constraints"), Diagnostics.ConstraintCount, uint32(0));
        if (!Okay(*this, TEXT("Reinitialize same Game owner"), Owner->InitializeSimulation(SmallWorld()))
            || !Okay(*this, TEXT("Recreate from surviving immutable prepared rig"), Owner->CreateRigFixture(Snapshot, Prepared, NewHandles, Notes))
            || !TestEqual(TEXT("Reinitialized rig has two handles"), NewHandles.Num(), 2)) return false;
        TestTrue(TEXT("New native lifetime differs from the prior run"), OldHandles[0].WorldLifetime != NewHandles[0].WorldLifetime);
        TestTrue(TEXT("Reinitialized lifetime owns the new rig"), Owner->OwnsRigFixture(NewHandles));
        TestFalse(TEXT("Previous lifetime never claims the reinitialized rig"), Owner->OwnsRigFixture(OldHandles));
        for (const auto& OldHandle : OldHandles)
            TestTrue(TEXT("Previous-lifetime handles remain invalid"), Owner->ReadBody(OldHandle, BodyState).Code == EProphecyJoltWorldResult::InvalidHandle);
        TestTrue(TEXT("Previous-lifetime targets cannot bind to new bodies"),
            Owner->PublishRigFixtureVelocityTargets(Targets, 0.1f).Code == EProphecyJoltWorldResult::InvalidHandle);
        const auto NewTargets = MakeTargets(Snapshot, NewHandles);
        if (!Okay(*this, TEXT("Publish into new lifetime"), Owner->PublishRigFixtureVelocityTargets(NewTargets, 0.1f))
            || !Okay(*this, TEXT("Step reinitialized owner"), Owner->Step(1.0f / 60.0f, 1))) return false;
        // No BeginPlay and no explicit DestroyRigFixture: WorldSubsystem teardown
        // must unregister the active listener and remove live constraints/bodies.
        Scope.Destroy();
        TestEqual(TEXT("Game-world teardown releases a live rig without BeginPlay"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialWorlds);
        TestEqual(TEXT("World teardown preserves the separately owned preparation"), Prepared.GetBodyCount(), 2);
    }
    TestEqual(TEXT("All shutdown fixture worlds are released"), UProphecyJoltWorldSubsystem::GetLiveSimulationCount(), InitialWorlds);
    TestEqual(TEXT("All shutdown fixture preparations are released"), FProphecyJoltPreparedRig::GetLivePreparedRigCount(), InitialPrepared);
    return true;
}


IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltMultiRigPacketsTest,
    "Prophecy.Jolt.MultiRig.IndependentPacketsOneWorldStep", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltMultiRigPacketsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    const FProphecyJoltRigSnapshot A = MakeRig();
    FProphecyJoltRigSnapshot B = MakeRig();
    for (auto& Body : B.Bodies) Body.BodyOriginToWorld.AddToTranslation(FVector(0.0, 400.0, 0.0));
    FProphecyJoltPreparedRig PreparedA, PreparedB;
    if (!Prepare(*this, A, PreparedA) || !Prepare(*this, B, PreparedB)) return false;
    FScopedWorld Scope;
    UProphecyJoltWorldSubsystem* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Multi-rig Game owner"), Owner)
        || !Okay(*this, TEXT("Initialize one shared world"), Owner->InitializeSimulation(SmallWorld(4)))) return false;
    FProphecyJoltRigHandle RigA, RigB;
    TArray<FProphecyJoltBodyHandle> BodiesA, BodiesB;
    TArray<FString> Notes;
    if (!Okay(*this, TEXT("Create rig A"), Owner->CreateRig(A, PreparedA, RigA, BodiesA, Notes))
        || !Okay(*this, TEXT("Create rig B in the same world"), Owner->CreateRig(B, PreparedB, RigB, BodiesB, Notes))
        || !Counts(*this, *Owner, 4, 2)) return false;
    TestTrue(TEXT("Distinct rig identities share one world lifetime"), RigA.IsSet() && RigB.IsSet()
        && RigA.WorldLifetime == RigB.WorldLifetime && RigA.Slot != RigB.Slot);
    TestTrue(TEXT("Both independent rigs own their complete records"), Owner->OwnsRig(RigA) && Owner->OwnsRig(RigB));
    auto TargetsA = MakeTargets(A, BodiesA);
    const auto TargetsB = MakeTargets(B, BodiesB);
    if (!Okay(*this, TEXT("Publish A h=0.1"), Owner->PublishRigVelocityTargets(RigA, TargetsA, 0.1f))
        || !Okay(*this, TEXT("Publish B h=0.2 without replacing A"), Owner->PublishRigVelocityTargets(RigB, TargetsB, 0.2f))) return false;
    TestTrue(TEXT("Another rig's bodies cannot be published through A"),
        Owner->PublishRigVelocityTargets(RigA, TargetsB, 0.8f).Code == EProphecyJoltWorldResult::InvalidHandle);
    TArray<FProphecyJoltRigVelocityTarget> Duplicate = TargetsA;
    Duplicate.Add(TargetsA[0]);
    TestTrue(TEXT("Duplicate body in A packet is rejected atomically"),
        Owner->PublishRigVelocityTargets(RigA, Duplicate, 0.9f).Code == EProphecyJoltWorldResult::InvalidArgument);
    // SIMD IsNormalized alone is not a finite-quaternion check: unordered comparisons may pass it.
    const double NonFiniteRotations[] = { std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::infinity() };
    for (const double NonFinite : NonFiniteRotations)
    {
        auto Rejected = TargetsA;
        Rejected[0].TargetPositionCm.X += 1000.0;
        Rejected[1].TargetRotation.X = NonFinite;
        TestTrue(TEXT("Nonfinite rotation rejects the entire rig packet before replacing a valid prefix"),
            Owner->PublishRigVelocityTargets(RigA, Rejected, 0.7f).Code == EProphecyJoltWorldResult::InvalidArgument);
    }
    if (!Okay(*this, TEXT("One shared Update consumes both packets"), Owner->Step(1.0f / 60.0f, 1))) return false;
    FProphecyJoltRigServoState ServoA, ServoB;
    if (!Okay(*this, TEXT("Read A samples"), Owner->ReadRigServoSamples(RigA, ServoA))
        || !Okay(*this, TEXT("Read B samples"), Owner->ReadRigServoSamples(RigB, ServoB))
        || !TestEqual(TEXT("A exposes its two samples"), ServoA.Samples.Num(), 2)
        || !TestEqual(TEXT("B exposes its two samples"), ServoB.Samples.Num(), 2)) return false;
    TestEqual(TEXT("A consumed one collision step"), ServoA.InvocationCount, uint64(1));
    TestEqual(TEXT("B consumed the same collision step"), ServoB.InvocationCount, uint64(1));
    TestNearlyEqual(TEXT("A retains h=0.1"), ServoA.DenominatorSeconds, 0.1f, 1.0e-8f);
    TestNearlyEqual(TEXT("B retains h=0.2"), ServoB.DenominatorSeconds, 0.2f, 1.0e-8f);
    for (int32 Index = 0; Index < 2; ++Index)
    {
        TestTrue(TEXT("A preserves its publication order"), SameHandle(ServoA.Samples[Index].Handle, TargetsA[Index].Handle));
        TestTrue(TEXT("B preserves its publication order"), SameHandle(ServoB.Samples[Index].Handle, TargetsB[Index].Handle));
        TestTrue(TEXT("Both callbacks produced valid samples"), ServoA.Samples[Index].bValid && ServoB.Samples[Index].bValid);
        TestNearlyEqual(TEXT("A analytic velocity is 6/0.1=60 cm/s"), ServoA.Samples[Index].LinearAfterCmPerSecond,
            FVector(60.0, 0.0, 0.0), 2.0e-3f);
        TestNearlyEqual(TEXT("B analytic velocity is 6/0.2=30 cm/s"), ServoB.Samples[Index].LinearAfterCmPerSecond,
            FVector(30.0, 0.0, 0.0), 2.0e-3f);
        FProphecyJoltBodyState BodyA, BodyB;
        if (!Okay(*this, TEXT("Read A completed body"), Owner->ReadBody(TargetsA[Index].Handle, BodyA))
            || !Okay(*this, TEXT("Read B completed body"), Owner->ReadBody(TargetsB[Index].Handle, BodyB))) return false;
        TestNearlyEqual(TEXT("A moves one centimeter in the shared step"), BodyA.PositionCm,
            ServoA.Samples[Index].PositionCm + FVector(1.0, 0.0, 0.0), 2.0e-3f);
        TestNearlyEqual(TEXT("B moves half a centimeter in the shared step"), BodyB.PositionCm,
            ServoB.Samples[Index].PositionCm + FVector(0.5, 0.0, 0.0), 2.0e-3f);
    }
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Okay(*this, TEXT("Read shared step count"), Owner->GetDiagnostics(Diagnostics))) return false;
    TestEqual(TEXT("Two rigs advanced through exactly one world Step"), Diagnostics.CompletedSteps, uint64(1));

    for (auto& Target : TargetsA) Target.TargetPositionCm.X += 6.0;
    if (!Okay(*this, TEXT("Replace A packet only"), Owner->PublishRigVelocityTargets(RigA, TargetsA, 0.1f))
        || !Okay(*this, TEXT("Read B untouched diagnostic history"), Owner->ReadRigServoSamples(RigB, ServoB))) return false;
    TestEqual(TEXT("Publishing A did not clear B's history"), ServoB.InvocationCount, uint64(1));
    TestTrue(TEXT("Publishing A did not invalidate B's completed sample"), ServoB.Samples[0].bValid);
    if (!Okay(*this, TEXT("Second shared Update"), Owner->Step(1.0f / 60.0f, 1))
        || !Okay(*this, TEXT("Read replacement A sample"), Owner->ReadRigServoSamples(RigA, ServoA))
        || !Okay(*this, TEXT("Read persistent B sample"), Owner->ReadRigServoSamples(RigB, ServoB))) return false;
    TestNearlyEqual(TEXT("A new endpoint acts from its completed position"), ServoA.Samples[0].LinearAfterCmPerSecond,
        FVector(110.0, 0.0, 0.0), 3.0e-3f);
    TestNearlyEqual(TEXT("B continues old endpoint and its own h"), ServoB.Samples[0].LinearAfterCmPerSecond,
        FVector(27.5, 0.0, 0.0), 3.0e-3f);
    TestEqual(TEXT("A has two consumed steps"), ServoA.InvocationCount, uint64(2));
    TestEqual(TEXT("B has two consumed steps"), ServoB.InvocationCount, uint64(2));
    TestEqual(TEXT("A callback has no invalid body"), ServoA.InvalidBodyCount, uint64(0));
    TestEqual(TEXT("B callback has no invalid body"), ServoB.InvalidBodyCount, uint64(0));
    const TArray<FProphecyJoltRigVelocityTarget> EmptyPacket;
    if (!Okay(*this, TEXT("Clear A's servo without removing its rig"), Owner->PublishRigVelocityTargets(RigA, EmptyPacket, 0.3f))
        || !Okay(*this, TEXT("Two collision steps reuse B's packet"), Owner->Step(0.01f, 2))
        || !Okay(*this, TEXT("Read cleared A servo"), Owner->ReadRigServoSamples(RigA, ServoA))
        || !Okay(*this, TEXT("Read twice-consumed B servo"), Owner->ReadRigServoSamples(RigB, ServoB))) return false;
    TestTrue(TEXT("Empty A packet removes its targets only"), ServoA.Samples.IsEmpty());
    TestEqual(TEXT("Cleared A is not counted as consumed"), ServoA.InvocationCount, uint64(2));
    TestEqual(TEXT("B retains history and consumes both new collision steps"), ServoB.InvocationCount, uint64(4));
    TestNearlyEqual(TEXT("B h stays distinct from collision-step dt"), ServoB.DenominatorSeconds, 0.2f, 1.0e-8f);
    TestNearlyEqual(TEXT("B last integration interval is 0.005"), ServoB.LastIntegrationSeconds, 0.005f, 1.0e-8f);
    TestNearlyEqual(TEXT("B analytic second-substep velocity uses its persistent endpoint and h"),
        ServoB.Samples[0].LinearAfterCmPerSecond, FVector(24.578125, 0.0, 0.0), 4.0e-3f);
    FProphecyJoltBodyState ClearedA;
    if (!Okay(*this, TEXT("Read freely coasting A"), Owner->ReadBody(BodiesA[0], ClearedA))) return false;
    TestNearlyEqual(TEXT("Clearing A did not rewrite its existing velocity"),
        ClearedA.CenterOfMassVelocityCmPerSecond, FVector(110.0, 0.0, 0.0), 4.0e-3f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltMultiRigRemovalTest,
    "Prophecy.Jolt.MultiRig.RemovalGenerationAndWorldLifetime", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltMultiRigRemovalTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    const FProphecyJoltRigSnapshot Snapshot = MakeRig();
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld First, Second;
    UProphecyJoltWorldSubsystem* Owner = First.Get();
    UProphecyJoltWorldSubsystem* Other = Second.Get();
    if (!TestNotNull(TEXT("Removal owner"), Owner) || !TestNotNull(TEXT("Independent owner"), Other)
        || !Okay(*this, TEXT("Initialize removal owner"), Owner->InitializeSimulation(SmallWorld(5)))
        || !Okay(*this, TEXT("Initialize independent owner"), Other->InitializeSimulation(SmallWorld(2)))) return false;
    FProphecyJoltFixtureBodySettings FloorSettings;
    FloorSettings.bDynamic = false;
    FloorSettings.PositionCm = FVector(0.0, 0.0, -500.0);
    FProphecyJoltBodyHandle Floor;
    if (!Okay(*this, TEXT("Create non-rig sentinel"), Owner->CreateSphere(10.0, FloorSettings, Floor))) return false;
    FProphecyJoltRigHandle A, B, Foreign, Replacement;
    TArray<FProphecyJoltBodyHandle> ABodies, BBodies, ForeignBodies, ReplacementBodies;
    TArray<FString> Notes;
    if (!Okay(*this, TEXT("Create first explicit rig"), Owner->CreateRig(Snapshot, Prepared, A, ABodies, Notes))
        || !Okay(*this, TEXT("Clone capture in the same world"), Owner->CreateRig(Snapshot, Prepared, B, BBodies, Notes))
        || !Okay(*this, TEXT("Clone capture in another world"), Other->CreateRig(Snapshot, Prepared, Foreign, ForeignBodies, Notes))) return false;
    TestFalse(TEXT("Unset rig never proves ownership"), Owner->OwnsRig({}));
    TestFalse(TEXT("Foreign rig never proves ownership"), Owner->OwnsRig(Foreign));
    TestTrue(TEXT("Foreign destruction is rejected"), Owner->DestroyRig(Foreign).Code == EProphecyJoltWorldResult::InvalidHandle);
    const auto ATargets = MakeTargets(Snapshot, ABodies);
    const auto BTargets = MakeTargets(Snapshot, BBodies);
    if (!Okay(*this, TEXT("Publish removable rig"), Owner->PublishRigVelocityTargets(A, ATargets, 0.1f))
        || !Okay(*this, TEXT("Publish surviving rig"), Owner->PublishRigVelocityTargets(B, BTargets, 0.2f))
        || !Okay(*this, TEXT("Consume both packets"), Owner->Step(0.01f, 1))
        || !Okay(*this, TEXT("Destroy only A"), Owner->DestroyRig(A))
        || !Counts(*this, *Owner, 3, 1)) return false;
    TestFalse(TEXT("Removed A is not owned"), Owner->OwnsRig(A));
    TestTrue(TEXT("B remains owned"), Owner->OwnsRig(B));
    TestTrue(TEXT("Repeated stale destruction cannot affect B"), Owner->DestroyRig(A).Code == EProphecyJoltWorldResult::InvalidHandle);
    FProphecyJoltBodyState Body;
    for (const auto& Handle : ABodies)
        TestTrue(TEXT("Removed A body handles are stale"), Owner->ReadBody(Handle, Body).Code == EProphecyJoltWorldResult::InvalidHandle);
    FProphecyJoltRigServoState Servo;
    TestTrue(TEXT("Removed A sample identity is stale"), Owner->ReadRigServoSamples(A, Servo).Code == EProphecyJoltWorldResult::InvalidHandle);
    if (!Okay(*this, TEXT("Legacy teardown has no claim over explicit B"), Owner->DestroyRigFixture())
        || !Okay(*this, TEXT("Surviving B keeps its packet after A deletion"), Owner->Step(0.01f, 1))
        || !Okay(*this, TEXT("Read surviving B's history"), Owner->ReadRigServoSamples(B, Servo))) return false;
    TestEqual(TEXT("B history survived another rig's teardown"), Servo.InvocationCount, uint64(2));
    TestNearlyEqual(TEXT("B retained its denominator"), Servo.DenominatorSeconds, 0.2f, 1.0e-8f);
    TestNearlyEqual(TEXT("B retained its endpoint after A removal"), Servo.Samples[0].LinearAfterCmPerSecond,
        FVector(28.5, 0.0, 0.0), 3.0e-3f);
    if (!Okay(*this, TEXT("Recreate A's freed rig slot"), Owner->CreateRig(Snapshot, Prepared, Replacement, ReplacementBodies, Notes))) return false;
    TestEqual(TEXT("Available rig slot is reused"), Replacement.Slot, A.Slot);
    TestTrue(TEXT("Reused rig slot advances its 64-bit generation"), Replacement.Generation > A.Generation);
    TestFalse(TEXT("Old rig identity never revives"), Owner->OwnsRig(A));
    TestTrue(TEXT("Stale destruction cannot remove replacement"), Owner->DestroyRig(A).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Stale publication cannot control replacement"),
        Owner->PublishRigVelocityTargets(A, ATargets, 0.1f).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Current replacement remains owned"), Owner->OwnsRig(Replacement));
    if (!Okay(*this, TEXT("Read independent sentinel"), Owner->ReadBody(Floor, Body))) return false;
    TestNearlyEqual(TEXT("Rig removal preserves generic body"), Body.PositionCm, FloorSettings.PositionCm, 1.0e-6f);

    First.World->bIsTearingDown = true;
    TestTrue(TEXT("Explicit rig ownership remains available while ending"), Owner->OwnsRig(Replacement));
    const auto RemovedEnding = Owner->DestroyRig(Replacement);
    First.World->bIsTearingDown = false;
    if (!Okay(*this, TEXT("Explicit owned-rig cleanup while ending"), RemovedEnding)
        || !Okay(*this, TEXT("Shutdown with surviving B packet"), Owner->ShutdownSimulation())
        || !Okay(*this, TEXT("Reinitialize same subsystem"), Owner->InitializeSimulation(SmallWorld(2)))) return false;
    FProphecyJoltRigHandle NewLifetime;
    TArray<FProphecyJoltBodyHandle> NewBodies;
    if (!Okay(*this, TEXT("Create in new world lifetime"), Owner->CreateRig(Snapshot, Prepared, NewLifetime, NewBodies, Notes))) return false;
    TestTrue(TEXT("Reinitialization changes world identity"), NewLifetime.WorldLifetime != B.WorldLifetime);
    TestFalse(TEXT("Old B cannot own a new-lifetime rig"), Owner->OwnsRig(B));
    TestTrue(TEXT("Old B cannot destroy new-lifetime rig"), Owner->DestroyRig(B).Code == EProphecyJoltWorldResult::InvalidHandle);
    if (!Okay(*this, TEXT("Step new rig without any inherited packet"), Owner->Step(0.01f, 1))
        || !Okay(*this, TEXT("Read new lifetime body"), Owner->ReadBody(NewBodies[0], Body))) return false;
    TestNearlyEqual(TEXT("New lifetime inherits no old velocity target"), Body.PositionCm,
        Snapshot.Bodies[0].BodyOriginToWorld.GetTranslation(), 2.0e-3f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltMultiRigRollbackTest,
    "Prophecy.Jolt.MultiRig.FailedCreationPreservesExistingRig", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltMultiRigRollbackTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    const FProphecyJoltRigSnapshot Snapshot = MakeRig();
    FProphecyJoltRigSnapshot InvalidJoint = MakeRig();
    InvalidJoint.Joints[0].CurrentProfile.LinearLimit.XMotion = LCM_Limited;
    FProphecyJoltRigSnapshot TooLarge = MakeRig();
    FProphecyJoltRigBody Extra = TooLarge.Bodies[1];
    Extra.SourceBodyIndex = Extra.BoneIndex = 2;
    Extra.BodyName = TEXT("extra");
    Extra.BodyOriginToWorld.AddToTranslation(FVector(0.0, 0.0, 100.0));
    TooLarge.Bodies.Add(MoveTemp(Extra));
    FProphecyJoltPreparedRig Prepared, InvalidPrepared, LargePrepared;
    if (!Prepare(*this, Snapshot, Prepared) || !Prepare(*this, InvalidJoint, InvalidPrepared)
        || !Prepare(*this, TooLarge, LargePrepared)) return false;
    FScopedWorld Scope;
    UProphecyJoltWorldSubsystem* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Rollback owner"), Owner)
        || !Okay(*this, TEXT("Initialize rollback owner"), Owner->InitializeSimulation(SmallWorld(4)))) return false;
    FProphecyJoltRigHandle Existing, Output;
    TArray<FProphecyJoltBodyHandle> ExistingBodies, OutputBodies;
    TArray<FString> Notes;
    if (!Okay(*this, TEXT("Create existing rig"), Owner->CreateRig(Snapshot, Prepared, Existing, ExistingBodies, Notes))) return false;
    const auto Targets = MakeTargets(Snapshot, ExistingBodies);
    if (!Okay(*this, TEXT("Publish packet that must survive failed creation"), Owner->PublishRigVelocityTargets(Existing, Targets, 0.1f))
        || !Okay(*this, TEXT("Advance existing rig before failures"), Owner->Step(0.01f, 1))) return false;
    FProphecyJoltBodyState Before, After;
    if (!Okay(*this, TEXT("Capture existing body"), Owner->ReadBody(ExistingBodies[0], Before))) return false;
    Output = Existing;
    OutputBodies = ExistingBodies;
    Notes.Add(TEXT("clear me"));
    TestTrue(TEXT("Oversize creation fails before partially consuming remaining body capacity"),
        Owner->CreateRig(TooLarge, LargePrepared, Output, OutputBodies, Notes).Code == EProphecyJoltWorldResult::CapacityExceeded);
    TestTrue(TEXT("Capacity failure clears every creation output"), !Output.IsSet() && OutputBodies.IsEmpty() && Notes.IsEmpty());
    TestTrue(TEXT("Late unsupported joint conversion cannot remove existing rig"),
        Owner->CreateRig(InvalidJoint, InvalidPrepared, Output, OutputBodies, Notes).Code == EProphecyJoltWorldResult::InvalidArgument);
    TestTrue(TEXT("Prepared capture mismatch is rejected"),
        Owner->CreateRig(Snapshot, InvalidPrepared, Output, OutputBodies, Notes).Code == EProphecyJoltWorldResult::InvalidArgument);
    TestTrue(TEXT("Failed preflights expose no partial rig"), !Output.IsSet() && OutputBodies.IsEmpty() && Notes.IsEmpty());
    if (!Counts(*this, *Owner, 2, 1) || !Okay(*this, TEXT("Read existing body after failures"), Owner->ReadBody(ExistingBodies[0], After))) return false;
    TestTrue(TEXT("Existing identity survives every rejected creation"), Owner->OwnsRig(Existing));
    TestNearlyEqual(TEXT("Rejected creation never advances existing pose"), After.PositionCm, Before.PositionCm, 1.0e-6f);
    TestNearlyEqual(TEXT("Rejected creation never changes existing velocity"), After.CenterOfMassVelocityCmPerSecond,
        Before.CenterOfMassVelocityCmPerSecond, 1.0e-6f);
    if (!Okay(*this, TEXT("Valid second rig still fits after failed attempts"), Owner->CreateRig(Snapshot, Prepared, Output, OutputBodies, Notes))
        || !Counts(*this, *Owner, 4, 2)
        || !Okay(*this, TEXT("Existing accepted packet survives all creation attempts"), Owner->Step(0.01f, 1))) return false;
    FProphecyJoltRigServoState Servo;
    if (!Okay(*this, TEXT("Read surviving original servo"), Owner->ReadRigServoSamples(Existing, Servo))) return false;
    TestEqual(TEXT("Original servo retained invocation history"), Servo.InvocationCount, uint64(2));
    TestNearlyEqual(TEXT("Original target and h still determine its rewrite"), Servo.Samples[0].LinearAfterCmPerSecond,
        FVector(54.0, 0.0, 0.0), 3.0e-3f);
    TestTrue(TEXT("Both valid rigs remain independently owned"), Owner->OwnsRig(Existing) && Owner->OwnsRig(Output));
    return true;
}

namespace ProphecyJolt::CollisionDraftTests
{
using namespace ProphecyJolt::RigWorldTests;

bool StepFrames(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& Owner, int32 Frames = 60)
{
    for (int32 Frame = 0; Frame < Frames; ++Frame)
        if (!Okay(Test, TEXT("Advance bounded collision fixture"), Owner.Step(1.0f / 120.0f, 1))) return false;
    return true;
}

FProphecyJoltRigSnapshot ContactRig(bool bDisablePair, bool bApproach)
{
    FProphecyJoltRigSnapshot Snapshot = MakeRig();
    // No joint can itself stop these spheres. Only the collision filter may prevent their crossing.
    Snapshot.Joints.Reset();
    Snapshot.DisabledPairs.Reset();
    if (bDisablePair)
    {
        auto& Pair = Snapshot.DisabledPairs.AddDefaulted_GetRef();
        Pair.Body1Index = 0;
        Pair.Body2Index = 1;
        Pair.bFromPhysicsAsset = true;
    }
    for (int32 Index = 0; Index < Snapshot.Bodies.Num(); ++Index)
    {
        auto& Body = Snapshot.Bodies[Index];
        Body.BodyOriginToWorld = FTransform(FQuat::Identity, FVector(Index == 0 ? -30.0 : 30.0, 0.0, 0.0));
        Body.CenterOfMassVelocityCmPerSecond = bApproach ? FVector(Index == 0 ? 100.0 : -100.0, 0.0, 0.0) : FVector::ZeroVector;
        Body.LinearDamping = Body.AngularDamping = 0.0;
        Body.Friction = Body.Restitution = 0.0;
        Body.CollisionResponses.SetAllChannels(ECR_Ignore);
        Body.CollisionResponses.SetResponse(ECC_PhysicsBody, ECR_Block);
    }
    return Snapshot;
}

bool TranslateWithImpulses(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& Owner,
    TConstArrayView<FProphecyJoltBodyHandle> Handles)
{
    for (const auto& Handle : Handles)
    {
        FProphecyJoltBodyState Body;
        if (!Okay(Test, TEXT("Read body before translating collision fixture"), Owner.ReadBody(Handle, Body))
            || !Okay(Test, TEXT("Start 100 cm/s translation of 2 kg body"), Owner.AddPointImpulse(Handle, FVector(200.0, 0.0, 0.0), Body.CenterOfMassPositionCm))) return false;
    }
    if (!Okay(Test, TEXT("Translate existing rig ten centimeters before cloning"), Owner.Step(0.1f, 1))) return false;
    for (const auto& Handle : Handles)
    {
        FProphecyJoltBodyState Body;
        if (!Okay(Test, TEXT("Read translated collision fixture"), Owner.ReadBody(Handle, Body))
            || !Okay(Test, TEXT("Stop translated 2 kg body"), Owner.AddPointImpulse(Handle, Body.CenterOfMassVelocityCmPerSecond * -2.0, Body.CenterOfMassPositionCm))) return false;
    }
    return true;
}

bool SeparatedCounterparts(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& Owner,
    TConstArrayView<FProphecyJoltBodyHandle> A, TConstArrayView<FProphecyJoltBodyHandle> B)
{
    for (int32 Index = 0; Index < A.Num(); ++Index)
    {
        FProphecyJoltBodyState First, Second;
        if (!Okay(Test, TEXT("Read first rig counterpart"), Owner.ReadBody(A[Index], First))
            || !Okay(Test, TEXT("Read second rig counterpart"), Owner.ReadBody(B[Index], Second))) return false;
        // Starting center separation is 10 cm (and smaller after replacement), radii total 20 cm.
        // With shared group IDs these equal subgroup indices would remain overlapped indefinitely.
        // Pinned Jolt permits 2 cm penetration slop; allow that without retuning the solver.
        Test.TestTrue(TEXT("Different rig groups resolve the counterpart overlap"),
            FVector::Distance(First.PositionCm, Second.PositionCm) > 17.0);
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBilateralMaskTest,
    "Prophecy.Jolt.Collision.BilateralFixtureMasks", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltBilateralMaskTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    const ECollisionResponse FloorResponses[] = { ECR_Block, ECR_Ignore, ECR_Block, ECR_Block, ECR_Block };
    const ECollisionResponse SphereResponses[] = { ECR_Block, ECR_Block, ECR_Ignore, ECR_Overlap, ECR_Ignore };
    for (int32 Case = 0; Case < UE_ARRAY_COUNT(FloorResponses); ++Case)
    {
        FScopedWorld Scope;
        auto* Owner = Scope.Get();
        FProphecyJoltWorldSettings WorldSettings = SmallWorld(2);
        WorldSettings.GravityCmPerSecondSquared = FVector(0.0, 0.0, -1000.0);
        if (!TestNotNull(TEXT("Mask fixture owner"), Owner)
            || !Okay(*this, TEXT("Initialize mask fixture"), Owner->InitializeSimulation(WorldSettings))) return false;
        FProphecyJoltFixtureBodySettings SphereSettings;
        SphereSettings.PositionCm = FVector(0.0, 0.0, 50.0);
        SphereSettings.CollisionResponses.SetAllChannels(ECR_Ignore);
        SphereSettings.CollisionResponses.SetResponse(ECC_GameTraceChannel18, SphereResponses[Case]);
        // Case 2 retains an irrelevant block bit; case 4 has no block bits at all.
        if (Case == 2) SphereSettings.CollisionResponses.SetResponse(ECC_WorldDynamic, ECR_Block);
        FProphecyJoltBodyHandle Sphere, Floor;
        if (!Okay(*this, TEXT("Create default PhysicsBody sphere before static channel exists"), Owner->CreateSphere(10.0, SphereSettings, Sphere))
            || !Okay(*this, TEXT("Step before adding a previously unused channel"), Owner->Step(1.0f / 120.0f, 1))) return false;
        FProphecyJoltFixtureBodySettings FloorSettings;
        FloorSettings.bDynamic = false;
        FloorSettings.ObjectChannel = ECC_GameTraceChannel18; // Channel 31 tests unsigned masks, independent of static motion.
        FloorSettings.PositionCm = FVector(0.0, 0.0, -5.0);
        FloorSettings.CollisionResponses.SetAllChannels(ECR_Ignore);
        FloorSettings.CollisionResponses.SetResponse(ECC_PhysicsBody, FloorResponses[Case]);
        if (!Okay(*this, TEXT("Add high-channel static floor after an earlier Update"), Owner->CreateBox(FVector(100.0, 100.0, 5.0), 0.0, FloorSettings, Floor))
            || !StepFrames(*this, *Owner)) return false;
        FProphecyJoltBodyState Body;
        if (!Okay(*this, TEXT("Read mask fixture result"), Owner->ReadBody(Sphere, Body))) return false;
        if (Case == 0) TestTrue(TEXT("Bilateral Block sphere rests on the floor within native contact slop"), Body.PositionCm.Z > 7.5 && Body.PositionCm.Z < 12.5);
        else TestTrue(FString::Printf(TEXT("Nonblocking case %d passes through, without treating overlap as Block"), Case), Body.PositionCm.Z < -40.0);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPHATPairTest,
    "Prophecy.Jolt.Collision.ExactPHATDisabledPairs", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltPHATPairTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    for (bool bDisable : { false, true })
    {
        const auto Snapshot = ContactRig(bDisable, true);
        FProphecyJoltPreparedRig Prepared;
        if (!Prepare(*this, Snapshot, Prepared)) return false;
        FScopedWorld Scope;
        auto* Owner = Scope.Get();
        FProphecyJoltRigHandle Rig;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FString> Notes;
        if (!TestNotNull(TEXT("PHAT pair owner"), Owner)
            || !Okay(*this, TEXT("Initialize PHAT pair owner"), Owner->InitializeSimulation(SmallWorld(2)))
            || !Okay(*this, TEXT("Create unconstrained two-body rig"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))
            || !StepFrames(*this, *Owner)) return false;
        FProphecyJoltBodyState Left, Right;
        if (!Okay(*this, TEXT("Read left PHAT body"), Owner->ReadBody(Handles[0], Left))
            || !Okay(*this, TEXT("Read right PHAT body"), Owner->ReadBody(Handles[1], Right))) return false;
        if (bDisable)
        {
            TestTrue(TEXT("Only explicitly disabled pair crosses"), Left.PositionCm.X > 15.0 && Right.PositionCm.X < -15.0);
            TestNearlyEqual(TEXT("Excluded left body retains free-flight velocity"), Left.CenterOfMassVelocityCmPerSecond.X, 100.0, 0.01);
        }
        else TestTrue(TEXT("Enabled same-rig pair collides without any joint stopping it"), Left.PositionCm.X < -7.5 && Right.PositionCm.X > 7.5);
        if (!Counts(*this, *Owner, 2, 0)) return false;
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigGroupIdentityTest,
    "Prophecy.Jolt.Collision.IndependentRigGroupsAndReuse", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigGroupIdentityTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    const auto Snapshot = ContactRig(true, false);
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    FProphecyJoltRigHandle A, B, Replacement;
    TArray<FProphecyJoltBodyHandle> ABodies, BBodies, ReplacementBodies;
    TArray<FString> Notes;
    if (!TestNotNull(TEXT("Group identity owner"), Owner)
        || !Okay(*this, TEXT("Initialize group identity owner"), Owner->InitializeSimulation(SmallWorld(4)))
        || !Okay(*this, TEXT("Create first captured rig"), Owner->CreateRig(Snapshot, Prepared, A, ABodies, Notes))
        || !TranslateWithImpulses(*this, *Owner, ABodies)
        || !Okay(*this, TEXT("Create identical capture with independent live group identity"), Owner->CreateRig(Snapshot, Prepared, B, BBodies, Notes))
        || !StepFrames(*this, *Owner, 30)
        || !SeparatedCounterparts(*this, *Owner, ABodies, BBodies)) return false;
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Okay(*this, TEXT("Read shared profile count"), Owner->GetDiagnostics(Diagnostics))) return false;
    TestEqual(TEXT("Four identical body policies share one object-layer profile"), Diagnostics.CollisionProfileCount, uint32(1));
    if (!Okay(*this, TEXT("Remove first group while second group survives"), Owner->DestroyRig(A))
        || !Okay(*this, TEXT("Reuse adapter slots for a fresh group"), Owner->CreateRig(Snapshot, Prepared, Replacement, ReplacementBodies, Notes))) return false;
    TestEqual(TEXT("Rig adapter slot is reused"), Replacement.Slot, A.Slot);
    TestTrue(TEXT("Replacement preserves handle-generation safety"), Replacement.Generation > A.Generation);
    FProphecyJoltBodyState Ignored;
    TestTrue(TEXT("Destroyed group's body handle remains stale"), Owner->ReadBody(ABodies[0], Ignored).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Stale rig cannot destroy the replacement"), Owner->DestroyRig(A).Code == EProphecyJoltWorldResult::InvalidHandle);
    if (!StepFrames(*this, *Owner, 30)
        || !SeparatedCounterparts(*this, *Owner, ReplacementBodies, BBodies)
        || !Counts(*this, *Owner, 4, 0)) return false;
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigPropMaskTest,
    "Prophecy.Jolt.Collision.RigAndDynamicProp", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigPropMaskTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    for (bool bPropBlocks : { false, true })
    {
        auto Snapshot = ContactRig(true, false);
        Snapshot.Bodies[0].CenterOfMassVelocityCmPerSecond = FVector(100.0, 0.0, 0.0);
        Snapshot.Bodies[1].BodyOriginToWorld = FTransform(FQuat::Identity, FVector(0.0, 500.0, 0.0));
        FProphecyJoltPreparedRig Prepared;
        if (!Prepare(*this, Snapshot, Prepared)) return false;
        FScopedWorld Scope;
        auto* Owner = Scope.Get();
        FProphecyJoltRigHandle Rig;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FString> Notes;
        if (!TestNotNull(TEXT("Rig/prop owner"), Owner)
            || !Okay(*this, TEXT("Initialize rig/prop owner"), Owner->InitializeSimulation(SmallWorld(3)))
            || !Okay(*this, TEXT("Create rig before ungrouped prop"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))) return false;
        FProphecyJoltFixtureBodySettings PropSettings;
        PropSettings.PositionCm = FVector(30.0, 0.0, 0.0);
        PropSettings.MassKg = 2.0;
        PropSettings.CollisionResponses.SetAllChannels(bPropBlocks ? ECR_Block : ECR_Ignore);
        FProphecyJoltBodyHandle Prop;
        if (!Okay(*this, TEXT("Create ungrouped default PhysicsBody prop"), Owner->CreateSphere(10.0, PropSettings, Prop))
            || !Okay(*this, TEXT("Send prop toward rig"), Owner->AddPointImpulse(Prop, FVector(-200.0, 0.0, 0.0), PropSettings.PositionCm))
            || !StepFrames(*this, *Owner)) return false;
        FProphecyJoltBodyState RigBody, PropBody;
        if (!Okay(*this, TEXT("Read rig impact body"), Owner->ReadBody(Handles[0], RigBody))
            || !Okay(*this, TEXT("Read dynamic prop"), Owner->ReadBody(Prop, PropBody))) return false;
        if (bPropBlocks) TestTrue(TEXT("Ungrouped prop and rig stop each other on bilateral Block"), RigBody.PositionCm.X < -7.5 && PropBody.PositionCm.X > 7.5);
        else TestTrue(TEXT("One-sided prop Ignore permits passage through the rig"), RigBody.PositionCm.X > 15.0 && PropBody.PositionCm.X < -15.0);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltProfilePreflightTest,
    "Prophecy.Jolt.Collision.ProfileCapacityPreflight", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltProfilePreflightTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    FProphecyJoltWorldSettings Settings = SmallWorld(4);
    Settings.MaxCollisionProfiles = 2;
    if (!TestNotNull(TEXT("Profile capacity owner"), Owner)
        || !Okay(*this, TEXT("Initialize two-profile capacity"), Owner->InitializeSimulation(Settings))) return false;
    FProphecyJoltFixtureBodySettings SentinelSettings;
    SentinelSettings.bDynamic = false;
    SentinelSettings.PositionCm = FVector(1000.0, 0.0, 0.0);
    FProphecyJoltBodyHandle Sentinel, Failed;
    if (!Okay(*this, TEXT("Create default WorldStatic sentinel"), Owner->CreateSphere(10.0, SentinelSettings, Sentinel))) return false;
    auto Snapshot = ContactRig(true, false);
    Snapshot.Bodies[1].ObjectType = ECC_Pawn; // Two new profiles cannot fit in the one remaining row.
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FProphecyJoltRigHandle Rig;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FString> Notes;
    TestTrue(TEXT("Whole-rig profile capacity fails before creating any body"),
        Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes).Code == EProphecyJoltWorldResult::CapacityExceeded);
    TestTrue(TEXT("Profile failure exposes no partial ownership"), !Rig.IsSet() && Handles.IsEmpty() && Notes.IsEmpty());
    if (!Counts(*this, *Owner, 1, 0)) return false;
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Okay(*this, TEXT("Read failed profile preflight"), Owner->GetDiagnostics(Diagnostics))) return false;
    TestEqual(TEXT("Failed batch did not consume even the first requested new row"), Diagnostics.CollisionProfileCount, uint32(1));
    FProphecyJoltFixtureBodySettings DynamicSettings;
    if (!Okay(*this, TEXT("A single new default dynamic profile still fits"), Owner->CreateSphere(10.0, DynamicSettings, Failed))) return false;
    FProphecyJoltBodyHandle Rejected;
    DynamicSettings.ObjectChannel = ECC_Pawn;
    TestTrue(TEXT("Third fixture profile is rejected before body mutation"),
        Owner->CreateSphere(10.0, DynamicSettings, Rejected).Code == EProphecyJoltWorldResult::CapacityExceeded);
    TestFalse(TEXT("Rejected fixture has no handle"), Rejected.IsSet());
    DynamicSettings.ObjectChannel = ECC_MAX;
    TestTrue(TEXT("Channel sentinel is rejected instead of shifting outside the mask"),
        Owner->CreateSphere(10.0, DynamicSettings, Rejected).Code == EProphecyJoltWorldResult::InvalidArgument);
    if (!Counts(*this, *Owner, 2, 0)) return false;
    if (!Okay(*this, TEXT("Destroy generic dynamic body"), Owner->DestroyBody(Failed))) return false;
    DynamicSettings.ObjectChannel.Reset();
    if (!Okay(*this, TEXT("Retained identical profile can be reused at capacity"), Owner->CreateSphere(10.0, DynamicSettings, Failed))) return false;
    FProphecyJoltBodyState SentinelState;
    if (!Okay(*this, TEXT("Read sentinel after filter failures"), Owner->ReadBody(Sentinel, SentinelState))) return false;
    TestNearlyEqual(TEXT("Filter preflight failures never advance the sentinel"), SentinelState.PositionCm, SentinelSettings.PositionCm, 1.0e-6f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigAngularLimitUpdateTest,
    "Prophecy.Jolt.RigWorld.LiveAngularLimitsAtomic", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigAngularLimitUpdateTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    FProphecyJoltRigSnapshot Snapshot = MakeRig();
    auto Third = Snapshot.Bodies[1];
    Third.SourceBodyIndex = Third.BoneIndex = 2;
    Third.BodyName = TEXT("grandchild");
    Third.BodyOriginToWorld.AddToTranslation(FVector(0, 0, 40));
    Snapshot.Bodies.Add(Third);
    auto SecondJoint = Snapshot.Joints[0];
    SecondJoint.SourceConstraintIndex = 1;
    SecondJoint.JointName = TEXT("grandchild_to_child");
    SecondJoint.Body1Index = 2; SecondJoint.Body2Index = 1;
    SecondJoint.Bone1 = Third.BodyName; SecondJoint.Bone2 = Snapshot.Bodies[1].BodyName;
    Snapshot.Joints.Add(SecondJoint);
    auto SecondPair = Snapshot.DisabledPairs[0];
    SecondPair.Body1Index = 1; SecondPair.Body2Index = 2;
    Snapshot.DisabledPairs.Add(SecondPair);
    for (auto& Body : Snapshot.Bodies) Body.bAwake = false;
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Live angular update owner"), Owner)
        || !Okay(*this, TEXT("Initialize angular update world"), Owner->InitializeSimulation(SmallWorld(4)))) return false;
    FProphecyJoltRigHandle Rig;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FString> Notes;
    if (!Okay(*this, TEXT("Create sleeping three-body rig"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))) return false;
    const auto CheckSpeculativeCount = [&](int32 Expected) -> bool
    {
        TArray<FProphecyJoltRigJoint> Readback;
        int32 Count = -1;
        return Okay(*this, TEXT("Read registered joint types"), Owner->ReadRigAngularLimits(Rig, Readback, &Count))
            && TestEqual(TEXT("Only opted-in limited cones are wrapped"), Count, Expected);
    };
    if (!CheckSpeculativeCount(0)
        || !Okay(*this, TEXT("Player policy attaches to current limited cones"), Owner->SetRigPlayerSwingLimits(Rig, true))
        || !CheckSpeculativeCount(2)
        || !Okay(*this, TEXT("Losing player policy restores stock joints"), Owner->SetRigPlayerSwingLimits(Rig, false))
        || !CheckSpeculativeCount(0)
        || !Okay(*this, TEXT("Restore player policy"), Owner->SetRigPlayerSwingLimits(Rig, true))) return false;
    const auto ReadModes = [&](EAngularConstraintMotion Swing1, EAngularConstraintMotion Swing2, EAngularConstraintMotion Twist) -> bool
    {
        TArray<FProphecyJoltRigJoint> Readback;
        if (!Okay(*this, TEXT("Read actual native angular axes"), Owner->ReadRigAngularLimits(Rig, Readback))
            || !TestEqual(TEXT("Both native constraints read back"), Readback.Num(), 2)) return false;
        for (int32 Index = 0; Index < Readback.Num(); ++Index)
        {
            const auto& Joint = Readback[Index];
            TestTrue(TEXT("Requested modes reached native SixDOF axes"), Joint.CurrentProfile.ConeLimit.Swing1Motion == Swing1
                && Joint.CurrentProfile.ConeLimit.Swing2Motion == Swing2 && Joint.CurrentProfile.TwistLimit.TwistMotion == Twist);
            TestTrue(TEXT("Local anchors and identity remain captured"), Joint.Frame1.Equals(Snapshot.Joints[Index].Frame1, 0)
                && Joint.Frame2.Equals(Snapshot.Joints[Index].Frame2, 0) && Joint.JointName == Snapshot.Joints[Index].JointName
                && Joint.Body1Index == Snapshot.Joints[Index].Body1Index && Joint.Body2Index == Snapshot.Joints[Index].Body2Index);
            if (Swing1 == ACM_Limited) TestNearlyEqual(TEXT("Swing1 restored angle"), Joint.CurrentProfile.ConeLimit.Swing1LimitDegrees, 35.0f, 0.001f);
            if (Swing2 == ACM_Limited) TestNearlyEqual(TEXT("Swing2 restored angle"), Joint.CurrentProfile.ConeLimit.Swing2LimitDegrees, 20.0f, 0.001f);
            if (Twist == ACM_Limited) TestNearlyEqual(TEXT("Twist restored angle"), Joint.CurrentProfile.TwistLimit.TwistLimitDegrees, 15.0f, 0.001f);
        }
        return true;
    };
    if (!Okay(*this, TEXT("Identical limits are a no-op"), Owner->UpdateRigAngularLimits(Rig, Snapshot.Joints))) return false;
    auto Changed = Snapshot.Joints;
    for (auto& Joint : Changed)
    {
        Joint.CurrentProfile.ConeLimit.Swing1Motion = Joint.CurrentProfile.ConeLimit.Swing2Motion = ACM_Free;
        Joint.CurrentProfile.TwistLimit.TwistMotion = ACM_Free;
    }
    auto Bad = Changed;
    Bad.Last().CurrentProfile.ConeLimit.Swing1LimitDegrees = std::numeric_limits<float>::quiet_NaN();
    TestTrue(TEXT("A bad final joint rejects every update, including inactive angle fields"),
        Owner->UpdateRigAngularLimits(Rig, Bad).Code == EProphecyJoltWorldResult::InvalidArgument);
    Bad = Changed;
    Bad.Last().CurrentProfile.TwistLimit.TwistMotion = ACM_Limited;
    Bad.Last().CurrentProfile.TwistLimit.TwistLimitDegrees = 0.1f;
    TestTrue(TEXT("Existing hard-limit threshold is enforced atomically"),
        Owner->UpdateRigAngularLimits(Rig, Bad).Code == EProphecyJoltWorldResult::InvalidArgument);
    Bad = Changed;
    Bad.Last().Frame1.AddToTranslation(FVector(1, 0, 0));
    TestTrue(TEXT("Anchor mutation is rejected before angular changes"),
        Owner->UpdateRigAngularLimits(Rig, Bad).Code == EProphecyJoltWorldResult::InvalidArgument);
    if (!ReadModes(ACM_Limited, ACM_Limited, ACM_Limited)) return false;
    TArray<FProphecyJoltBodyState> Before;
    for (const auto& Handle : Handles)
    {
        auto& State = Before.AddDefaulted_GetRef();
        if (!Okay(*this, TEXT("Read unchanged sleeping body"), Owner->ReadBody(Handle, State))) return false;
        TestFalse(TEXT("No-op and failed batches never wake endpoints"), State.bActive);
    }

    // An independently registered fixed grip and exclusion must survive anatomical updates.
    FProphecyJoltFixtureBodySettings AnchorSettings;
    AnchorSettings.bDynamic = false;
    AnchorSettings.PositionCm = FVector(500, 0, 100);
    AnchorSettings.CollisionResponses.SetAllChannels(ECR_Ignore);
    FProphecyJoltBodyHandle Anchor;
    if (!Okay(*this, TEXT("Create independent grip anchor"), Owner->CreateSphere(2, AnchorSettings, Anchor))) return false;
    FProphecyJoltJointSettings GripSettings;
    GripSettings.BodyA = Anchor; GripSettings.BodyB = Handles[0];
    GripSettings.FrameA = FTransform(Before[0].PositionCm - AnchorSettings.PositionCm);
    FProphecyJoltJointHandle Grip;
    const TArray<FProphecyJoltBodyPair> Exclusions = { { Anchor, Handles[0] } };
    if (!Okay(*this, TEXT("Create external fixed grip and pair exclusion"), Owner->CreateJoint(GripSettings, Exclusions, Grip))) return false;
    const auto Targets = MakeTargets(Snapshot, Handles);
    if (!Okay(*this, TEXT("Publish retained servo packet"), Owner->PublishRigVelocityTargets(Rig, Targets, 1.0f / 60.0f))) return false;
    if (!Okay(*this, TEXT("Free all anatomical angular axes in place"), Owner->UpdateRigAngularLimits(Rig, Changed))
        || !ReadModes(ACM_Free, ACM_Free, ACM_Free) || !CheckSpeculativeCount(0)) return false;
    for (int32 Index = 0; Index < Handles.Num(); ++Index)
    {
        FProphecyJoltBodyState After;
        if (!Okay(*this, TEXT("Read original handle after limit change"), Owner->ReadBody(Handles[Index], After))) return false;
        TestTrue(TEXT("Limit changes preserve native positions, orientations and velocities"),
            After.PositionCm.Equals(Before[Index].PositionCm, 0) && After.Rotation.Equals(Before[Index].Rotation, 0)
            && After.CenterOfMassVelocityCmPerSecond.Equals(Before[Index].CenterOfMassVelocityCmPerSecond, 0)
            && After.AngularVelocityRadiansPerSecond.Equals(Before[Index].AngularVelocityRadiansPerSecond, 0));
        TestTrue(TEXT("Changed anatomical endpoints wake"), After.bActive);
    }
    auto Locked = Changed;
    for (auto& Joint : Locked) Joint.CurrentProfile.ConeLimit.Swing1Motion = ACM_Locked;
    if (!Okay(*this, TEXT("Mixed locked/free axes"), Owner->UpdateRigAngularLimits(Rig, Locked))
        || !ReadModes(ACM_Locked, ACM_Free, ACM_Free) || !CheckSpeculativeCount(0)
        || !Okay(*this, TEXT("Restore captured angular limits"), Owner->UpdateRigAngularLimits(Rig, Snapshot.Joints))
        || !ReadModes(ACM_Limited, ACM_Limited, ACM_Limited) || !CheckSpeculativeCount(2)) return false;
    TestTrue(TEXT("External grip remains registered"), Owner->OwnsJoint(Grip));
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Okay(*this, TEXT("Read preserved world inventory"), Owner->GetDiagnostics(Diagnostics))) return false;
    TestTrue(TEXT("No bodies, joints, exclusions or world steps were recreated"), Diagnostics.BodyCount == 4
        && Diagnostics.ConstraintCount == 3 && Diagnostics.GenericJointCount == 1
        && Diagnostics.SuppressedBodyPairCount == 1 && Diagnostics.CompletedSteps == 0);
    if (!Okay(*this, TEXT("Step with the retained servo packet"), Owner->Step(1.0f / 60.0f, 1))) return false;
    FProphecyJoltRigServoState Servo;
    if (!Okay(*this, TEXT("Read retained servo"), Owner->ReadRigServoSamples(Rig, Servo))) return false;
    TestTrue(TEXT("Angular update retains all published targets"), Servo.Samples.Num() == 3 && Servo.InvocationCount == 1 && Servo.InvalidBodyCount == 0);
    for (const auto& Sample : Servo.Samples) TestTrue(TEXT("Retained servo sample remains valid"), Sample.bValid);
    for (const auto& Joint : Snapshot.Joints)
    {
        FProphecyJoltBodyState A, B;
        if (!Okay(*this, TEXT("Read first native anchor endpoint"), Owner->ReadBody(Handles[Joint.Body1Index], A))
            || !Okay(*this, TEXT("Read second native anchor endpoint"), Owner->ReadBody(Handles[Joint.Body2Index], B))) return false;
        const FVector PointA = (Joint.Frame1 * FTransform(A.Rotation, A.PositionCm)).GetLocation();
        const FVector PointB = (Joint.Frame2 * FTransform(B.Rotation, B.PositionCm)).GetLocation();
        TestTrue(TEXT("Real stepped linear anchors remain locked after angular updates"), FVector::Distance(PointA, PointB) < 1.0);
    }
    if (!Okay(*this, TEXT("Destroy external grip"), Owner->DestroyJoint(Grip))
        || !Okay(*this, TEXT("Destroy original rig"), Owner->DestroyRig(Rig))
        || !Okay(*this, TEXT("Destroy independent anchor"), Owner->DestroyBody(Anchor))) return false;
    TestTrue(TEXT("Retired rig cannot be updated"), Owner->UpdateRigAngularLimits(Rig, Snapshot.Joints).Code == EProphecyJoltWorldResult::InvalidHandle);
    Counts(*this, *Owner, 0, 0);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltLiveSelfCollisionTest,
    "Prophecy.Jolt.Collision.LiveSelfCollisionContacts", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltLiveSelfCollisionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    for (int32 Control = 0; Control < 3; ++Control)
    {
        const auto Snapshot = ContactRig(false, true);
        FProphecyJoltPreparedRig Prepared;
        if (!Prepare(*this, Snapshot, Prepared)) return false;
        FScopedWorld Scope;
        auto* Owner = Scope.Get();
        FProphecyJoltRigHandle Rig;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FString> Notes;
        if (!TestNotNull(TEXT("Live self-collision owner"), Owner)
            || !Okay(*this, TEXT("Initialize live self-collision world"), Owner->InitializeSimulation(SmallWorld(2)))
            || !Okay(*this, TEXT("Create initially colliding rig"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))
            || !StepFrames(*this, *Owner)) return false;
        FProphecyJoltBodyState A, B;
        const auto Read = [&]() { return Okay(*this, TEXT("Read first live body"), Owner->ReadBody(Handles[0], A))
            && Okay(*this, TEXT("Read second live body"), Owner->ReadBody(Handles[1], B)); };
        const auto Toggle = [&](bool bEnabled)
        {
            const TArray<int32> Selected = { 0 };
            return Okay(*this, TEXT("Change live self-collision layer"), Control == 0 ? Owner->SetRigSelfCollisionEnabled(Rig, bEnabled)
                : Control == 1 ? Owner->SetRigBodiesSelfCollisionEnabled(Rig, Selected, bEnabled)
                : Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 1, 0, bEnabled));
        };
        const auto Velocities = [&](double Speed) { return Okay(*this, TEXT("Move first original body"),
                Owner->SetBodyVelocity(Handles[0], FVector(Speed, 0, 0), FVector::ZeroVector, true))
            && Okay(*this, TEXT("Move second original body"),
                Owner->SetBodyVelocity(Handles[1], FVector(-Speed, 0, 0), FVector::ZeroVector, true)); };
        if (!Read()) return false;
        TestTrue(TEXT("Initially enabled bodies establish a real contact"), A.PositionCm.X < -7.5 && B.PositionCm.X > 7.5);
        if (!Toggle(false) || !Velocities(100) || !StepFrames(*this, *Owner) || !Read()) return false;
        TestTrue(TEXT("Disabling each control invalidates cached contacts and permits crossing"), A.PositionCm.X > 25 && B.PositionCm.X < -25);
        if (!Toggle(true) || !Velocities(-100) || !StepFrames(*this, *Owner) || !Read()) return false;
        TestTrue(TEXT("Re-enabling each control restores collision on the original bodies"), A.PositionCm.X > 7.5 && B.PositionCm.X < -7.5);
        if (!Counts(*this, *Owner, 2, 0)) return false;
    }
    // Previously excluded overlaps can sleep with no contact. Re-enabling must rediscover them.
    auto Snapshot = ContactRig(false, false);
    Snapshot.Bodies[0].BodyOriginToWorld.SetTranslation(FVector(-5, 0, 0));
    Snapshot.Bodies[1].BodyOriginToWorld.SetTranslation(FVector(5, 0, 0));
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    FProphecyJoltRigHandle Rig;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FString> Notes;
    if (!TestNotNull(TEXT("Sleeping overlap owner"), Owner)
        || !Okay(*this, TEXT("Initialize sleeping overlap world"), Owner->InitializeSimulation(SmallWorld(2)))
        || !Okay(*this, TEXT("Create overlapping rig"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))
        || !Okay(*this, TEXT("Exclude overlap before stepping"), Owner->SetRigSelfCollisionEnabled(Rig, false))
        || !StepFrames(*this, *Owner, 180)) return false;
    if (!Okay(*this, TEXT("Repeated master-off is a no-op"), Owner->SetRigSelfCollisionEnabled(Rig, false))
        || !Okay(*this, TEXT("Hidden pair suppression is an effective no-op"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 0, 1, false))) return false;
    FProphecyJoltBodyState A, B;
    if (!Okay(*this, TEXT("Read sleeping excluded first body"), Owner->ReadBody(Handles[0], A))
        || !Okay(*this, TEXT("Read sleeping excluded second body"), Owner->ReadBody(Handles[1], B))) return false;
    TestFalse(TEXT("Effective no-op does not wake first body"), A.bActive);
    TestFalse(TEXT("Effective no-op does not wake second body"), B.bActive);
    TestNearlyEqual(TEXT("Suppressed overlap remains untouched"), FVector::Distance(A.PositionCm, B.PositionCm), 10.0, 0.01);
    if (!Okay(*this, TEXT("Reset clears both layers and wakes overlap"), Owner->ResetRigSelfCollision(Rig))
        || !Okay(*this, TEXT("Read wake after reset"), Owner->ReadBody(Handles[0], A))) return false;
    TestTrue(TEXT("Re-enabled sleeping endpoint wakes immediately"), A.bActive);
    if (!StepFrames(*this, *Owner, 30)
        || !Okay(*this, TEXT("Read resolved first body"), Owner->ReadBody(Handles[0], A))
        || !Okay(*this, TEXT("Read resolved second body"), Owner->ReadBody(Handles[1], B))) return false;
    TestTrue(TEXT("Re-enabled formerly sleeping overlap resolves"), FVector::Distance(A.PositionCm, B.PositionCm) > 17.0);
    return !HasAnyErrors();
}

#include "ProphecyJoltAttackCollisionLibrary.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSelfCollisionLayersTest,
    "Prophecy.Jolt.Collision.SelfCollisionLayersAtomic", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltSelfCollisionLayersTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    auto Snapshot = MakeRig();
    auto Third = Snapshot.Bodies[1];
    Third.BodyName = TEXT("third"); Third.SourceBodyIndex = Third.BoneIndex = 2;
    Third.BodyOriginToWorld.AddToTranslation(FVector(0, 0, 40));
    Snapshot.Bodies.Add(Third);
    for (auto& Body : Snapshot.Bodies) Body.bAwake = false;
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld Scope, OtherScope;
    auto* Owner = Scope.Get();
    auto* Other = OtherScope.Get();
    FProphecyJoltRigHandle Rig;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FString> Notes;
    if (!TestNotNull(TEXT("Layer fixture owner"), Owner) || !TestNotNull(TEXT("Cross-world fixture owner"), Other)
        || !Okay(*this, TEXT("Initialize layered world"), Owner->InitializeSimulation(SmallWorld(4)))
        || !Okay(*this, TEXT("Initialize second world"), Other->InitializeSimulation(SmallWorld(4)))
        || !Okay(*this, TEXT("Create authored rig"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))) return false;
    const auto Pair = [&](int32 A, int32 B, bool bExpected)
    {
        bool bEnabled = !bExpected;
        return Okay(*this, TEXT("Read effective self-collision pair"), Owner->ReadRigBodyPairSelfCollisionEnabled(Rig, A, B, bEnabled))
            && TestEqual(FString::Printf(TEXT("Effective pair %d/%d"), A, B), bEnabled, bExpected);
    };
    const TArray<int32> Empty, Invalid = { 2, -1 }, Selected = { 0, 0 };
    if (!Okay(*this, TEXT("Default master-on no-op"), Owner->SetRigSelfCollisionEnabled(Rig, true))
        || !Okay(*this, TEXT("Empty subset no-op"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, Empty, false))
        || !Okay(*this, TEXT("Enable cannot override authored pair"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 0, 1, true))) return false;
    TestTrue(TEXT("Invalid last subset member rejects whole request"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, Invalid, false).Code == EProphecyJoltWorldResult::InvalidArgument);
    TestTrue(TEXT("Same-body pair rejected"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 1, 1, false).Code == EProphecyJoltWorldResult::InvalidArgument);
    TestTrue(TEXT("Out-of-range pair rejected"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 0, 3, false).Code == EProphecyJoltWorldResult::InvalidArgument);
    TestTrue(TEXT("Cross-world mutation rejected"), Other->SetRigSelfCollisionEnabled(Rig, false).Code == EProphecyJoltWorldResult::InvalidHandle);
    bool bRead = true;
    TestTrue(TEXT("Bad read clears output"), Owner->ReadRigBodyPairSelfCollisionEnabled(Rig, -1, 0, bRead).Code == EProphecyJoltWorldResult::InvalidArgument && !bRead);
    if (!Pair(0, 1, false) || !Pair(0, 2, true) || !Pair(1, 2, true)) return false;
    for (const auto& Handle : Handles)
    {
        FProphecyJoltBodyState Body;
        if (!Okay(*this, TEXT("Read no-op sleeping body"), Owner->ReadBody(Handle, Body))) return false;
        TestFalse(TEXT("No-op and rejected requests leave bodies asleep"), Body.bActive);
    }
    FProphecyJoltFixtureBodySettings AnchorSettings;
    AnchorSettings.bDynamic = false; AnchorSettings.PositionCm = FVector(500, 0, 100);
    AnchorSettings.CollisionResponses.SetAllChannels(ECR_Ignore);
    FProphecyJoltBodyHandle Anchor;
    if (!Okay(*this, TEXT("Create independent grip anchor"), Owner->CreateSphere(2, AnchorSettings, Anchor))) return false;
    FProphecyJoltJointSettings GripSettings;
    GripSettings.BodyA = Anchor; GripSettings.BodyB = Handles[0];
    GripSettings.FrameA = FTransform(Snapshot.Bodies[0].BodyOriginToWorld.GetLocation() - AnchorSettings.PositionCm);
    FProphecyJoltJointHandle Grip;
    const TArray<FProphecyJoltBodyPair> Exclusions = { { Anchor, Handles[0] } };
    const auto RetainedTargets = MakeTargets(Snapshot, Handles);
    if (!Okay(*this, TEXT("Create retained grip/exclusion"), Owner->CreateJoint(GripSettings, Exclusions, Grip))
        || !Okay(*this, TEXT("Publish retained servo targets"), Owner->PublishRigVelocityTargets(Rig, RetainedTargets, 1.0f / 60.0f))) return false;
    TArray<FProphecyJoltBodyState> Before;
    for (const auto& Handle : Handles)
        if (!Okay(*this, TEXT("Capture original native body state"), Owner->ReadBody(Handle, Before.AddDefaulted_GetRef()))) return false;
    if (!Okay(*this, TEXT("Disable selected body against all others"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, Selected, false))
        || !Pair(0, 1, false) || !Pair(0, 2, false) || !Pair(1, 2, true)
        || !Okay(*this, TEXT("Add independent pair suppression"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 1, 2, false))
        || !Okay(*this, TEXT("Add master suppression"), Owner->SetRigSelfCollisionEnabled(Rig, false))
        || !Okay(*this, TEXT("Remove subset layer behind master"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, Selected, true))
        || !Pair(0, 2, false)
        || !Okay(*this, TEXT("Remove master retaining pair layer"), Owner->SetRigSelfCollisionEnabled(Rig, true))
        || !Pair(0, 1, false) || !Pair(0, 2, true) || !Pair(1, 2, false)
        || !Okay(*this, TEXT("Reversed pair removes same pair layer"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 2, 1, true))
        || !Pair(1, 2, true)) return false;
    const TArray<int32> TwoSelected = { 0, 2 };
    if (!Okay(*this, TEXT("Selected bodies also exclude one another"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, TwoSelected, false))
        || !Pair(0, 2, false) || !Pair(1, 2, false)
        || !Okay(*this, TEXT("Add reset master layer"), Owner->SetRigSelfCollisionEnabled(Rig, false))
        || !Okay(*this, TEXT("Add reset pair layer"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 1, 2, false))
        || !Okay(*this, TEXT("Reset all runtime layers"), Owner->ResetRigSelfCollision(Rig))
        || !Pair(0, 1, false) || !Pair(0, 2, true) || !Pair(1, 2, true)) return false;
    FString AttackError;
    const auto Attack = [&](bool Suppressed)
    {
        return TestTrue(TEXT("Set independent attack suppression"), UProphecyJoltAttackCollisionLibrary::SetSuppressed(
            Owner, Rig.WorldLifetime, Rig.Slot, int64(Rig.Generation), Suppressed, AttackError));
    };
    if (!Attack(true) || !Pair(0, 2, false) || !Pair(1, 2, false)
        || !Okay(*this, TEXT("BP enable during attack remains suppressed"), Owner->SetRigSelfCollisionEnabled(Rig, true))
        || !Pair(0, 2, false)
        || !Okay(*this, TEXT("Edit pair during attack"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 1, 2, false))
        || !Attack(false) || !Pair(0, 1, false) || !Pair(0, 2, true) || !Pair(1, 2, false)
        || !Attack(true)
        || !Okay(*this, TEXT("Reset configured exclusions cannot defeat attack suppression"), Owner->ResetRigSelfCollision(Rig))
        || !Pair(0, 2, false) || !Pair(1, 2, false)
        || !Okay(*this, TEXT("Global disable during attack persists after Hit"), Owner->SetRigSelfCollisionEnabled(Rig, false))
        || !Attack(false) || !Pair(0, 2, false) || !Pair(1, 2, false)
        || !Okay(*this, TEXT("Restore configured default"), Owner->ResetRigSelfCollision(Rig))
        || !Pair(0, 1, false) || !Pair(0, 2, true) || !Pair(1, 2, true)) return false;
    for (int32 Index = 0; Index < Handles.Num(); ++Index)
    {
        FProphecyJoltBodyState After;
        if (!Okay(*this, TEXT("Read original body after controls"), Owner->ReadBody(Handles[Index], After))) return false;
        TestTrue(TEXT("Controls preserve position, rotation and both velocities"), After.PositionCm.Equals(Before[Index].PositionCm, 0)
            && After.Rotation.Equals(Before[Index].Rotation, 0)
            && After.CenterOfMassVelocityCmPerSecond.Equals(Before[Index].CenterOfMassVelocityCmPerSecond, 0)
            && After.AngularVelocityRadiansPerSecond.Equals(Before[Index].AngularVelocityRadiansPerSecond, 0));
    }
    TArray<FProphecyJoltRigJoint> Joints;
    if (!Okay(*this, TEXT("Read retained anatomical joint"), Owner->ReadRigAngularLimits(Rig, Joints))) return false;
    TestTrue(TEXT("Anatomical limits and anchors retained"), Joints.Num() == 1 && Joints[0].Frame1.Equals(Snapshot.Joints[0].Frame1, 0)
        && Joints[0].Frame2.Equals(Snapshot.Joints[0].Frame2, 0) && Joints[0].CurrentProfile.ConeLimit.Swing1Motion == ACM_Limited
        && FMath::IsNearlyEqual(Joints[0].CurrentProfile.ConeLimit.Swing1LimitDegrees, 35.0f, 0.001f));
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Okay(*this, TEXT("Read unchanged inventory"), Owner->GetDiagnostics(Diagnostics))) return false;
    TestTrue(TEXT("Body, anatomical joint, grip and external suppression identities retained"), Owner->OwnsRig(Rig)
        && Owner->OwnsJoint(Grip) && Diagnostics.BodyCount == 4 && Diagnostics.ConstraintCount == 2
        && Diagnostics.GenericJointCount == 1 && Diagnostics.SuppressedBodyPairCount == 1 && Diagnostics.CompletedSteps == 0);
    if (!Okay(*this, TEXT("Step retained servo"), Owner->Step(1.0f / 60.0f, 1))) return false;
    FProphecyJoltRigServoState Servo;
    if (!Okay(*this, TEXT("Read retained servo"), Owner->ReadRigServoSamples(Rig, Servo))) return false;
    TestTrue(TEXT("All servo targets survive controls"), Servo.Samples.Num() == 3 && Servo.InvocationCount == 1 && Servo.InvalidBodyCount == 0);
    if (!Attack(true)
        || !Okay(*this, TEXT("Disable before destruction"), Owner->SetRigSelfCollisionEnabled(Rig, false))
        || !Okay(*this, TEXT("Destroy rig and its incident grip"), Owner->DestroyRig(Rig))) return false;
    FProphecyJoltRigHandle Replacement;
    TArray<FProphecyJoltBodyHandle> ReplacementBodies;
    if (!Okay(*this, TEXT("Reuse slot without stale suppression"), Owner->CreateRig(Snapshot, Prepared, Replacement, ReplacementBodies, Notes))) return false;
    TestTrue(TEXT("Replacement has fresh generation"), Replacement.Slot == Rig.Slot && Replacement.Generation > Rig.Generation);
    TestTrue(TEXT("Stale master rejected"), Owner->SetRigSelfCollisionEnabled(Rig, true).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Stale subset rejected"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, Selected, false).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Stale pair rejected"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 0, 2, false).Code == EProphecyJoltWorldResult::InvalidHandle);
    TestTrue(TEXT("Stale reset rejected"), Owner->ResetRigSelfCollision(Rig).Code == EProphecyJoltWorldResult::InvalidHandle);
    bRead = true;
    TestTrue(TEXT("Stale read rejected and cleared"), Owner->ReadRigBodyPairSelfCollisionEnabled(Rig, 0, 2, bRead).Code == EProphecyJoltWorldResult::InvalidHandle && !bRead);
    if (!Okay(*this, TEXT("Read fresh replacement pair"), Owner->ReadRigBodyPairSelfCollisionEnabled(Replacement, 0, 2, bRead))) return false;
    TestTrue(TEXT("Retired runtime suppression does not leak to replacement"), bRead);
    TestFalse(TEXT("Incident grip safely retired with destroyed rig"), Owner->OwnsJoint(Grip));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSelfCollisionExternalContactsTest,
    "Prophecy.Jolt.Collision.SelfCollisionPreservesExternalContacts", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltSelfCollisionExternalContactsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::CollisionDraftTests;
    // Each runtime layer remains scoped to one rig: another rig, a dynamic prop and static world
    // geometry must still block. Establish these contacts after the filter has actually changed.
    for (int32 ExternalKind = 0; ExternalKind < 3; ++ExternalKind)
    {
        auto Snapshot = ContactRig(false, false);
        Snapshot.Bodies[0].CenterOfMassVelocityCmPerSecond = FVector(100, 0, 0);
        Snapshot.Bodies[1].BodyOriginToWorld.SetTranslation(FVector(0, 500, 0));
        for (auto& Body : Snapshot.Bodies) Body.CollisionResponses.SetResponse(ECC_WorldStatic, ECR_Block);
        FProphecyJoltPreparedRig Prepared;
        if (!Prepare(*this, Snapshot, Prepared)) return false;
        FScopedWorld Scope;
        auto* Owner = Scope.Get();
        FProphecyJoltRigHandle Rig;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FString> Notes;
        const TArray<int32> Selected = { 0 };
        if (!TestNotNull(TEXT("External contact owner"), Owner)
            || !Okay(*this, TEXT("Initialize external contact world"), Owner->InitializeSimulation(SmallWorld(4)))
            || !Okay(*this, TEXT("Create contact rig"), Owner->CreateRig(Snapshot, Prepared, Rig, Handles, Notes))
            || !Okay(*this, TEXT("Disable whole self-collision"), Owner->SetRigSelfCollisionEnabled(Rig, false))
            || !Okay(*this, TEXT("Add selected-body suppression"), Owner->SetRigBodiesSelfCollisionEnabled(Rig, Selected, false))
            || !Okay(*this, TEXT("Add pair suppression"), Owner->SetRigBodyPairSelfCollisionEnabled(Rig, 0, 1, false))) return false;
        FProphecyJoltBodyHandle ExternalBody;
        if (ExternalKind == 0)
        {
            auto OtherSnapshot = ContactRig(false, false);
            OtherSnapshot.Bodies[0].BodyOriginToWorld.SetTranslation(FVector(30, 0, 0));
            OtherSnapshot.Bodies[0].CenterOfMassVelocityCmPerSecond = FVector(-100, 0, 0);
            OtherSnapshot.Bodies[1].BodyOriginToWorld.SetTranslation(FVector(0, 600, 0));
            FProphecyJoltPreparedRig OtherPrepared;
            if (!Prepare(*this, OtherSnapshot, OtherPrepared)) return false;
            FProphecyJoltRigHandle OtherRig;
            TArray<FProphecyJoltBodyHandle> OtherHandles;
            if (!Okay(*this, TEXT("Create independently filtered character"), Owner->CreateRig(OtherSnapshot, OtherPrepared, OtherRig, OtherHandles, Notes))
                || !Okay(*this, TEXT("Disable other character's self-collision"), Owner->SetRigSelfCollisionEnabled(OtherRig, false))) return false;
            ExternalBody = OtherHandles[0];
        }
        else
        {
            FProphecyJoltFixtureBodySettings Settings;
            Settings.bDynamic = ExternalKind == 1;
            Settings.PositionCm = FVector(30, 0, 0); Settings.MassKg = 2;
            Settings.CollisionResponses.SetAllChannels(ECR_Block);
            if (!Okay(*this, TEXT("Create colliding external prop/world body"), Owner->CreateSphere(10, Settings, ExternalBody))) return false;
            if (Settings.bDynamic && !Okay(*this, TEXT("Move external prop toward rig"),
                Owner->SetBodyVelocity(ExternalBody, FVector(-100, 0, 0), FVector::ZeroVector, true))) return false;
        }
        if (!StepFrames(*this, *Owner)) return false;
        FProphecyJoltBodyState First, External;
        if (!Okay(*this, TEXT("Read externally blocked rig"), Owner->ReadBody(Handles[0], First))
            || !Okay(*this, TEXT("Read external collision endpoint"), Owner->ReadBody(ExternalBody, External))) return false;
        TestTrue(TEXT("Disabled self-collision retains external collision separation"),
            External.PositionCm.X - First.PositionCm.X > 17);
        if (ExternalKind == 2)
            TestTrue(TEXT("Static world still stops the moving rig"), First.PositionCm.X < 12);
        else
            TestTrue(TEXT("Different rig/dynamic prop still stops the moving rig"), First.PositionCm.X < -7.5 && External.PositionCm.X > 7.5);
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRigTrajectoryLifetimeTest,
    "Prophecy.Jolt.MultiRig.TrajectoryLifetimeAndPreflight", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltRigTrajectoryLifetimeTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::RigWorldTests;
    auto Snapshot = MakeRig();
    Snapshot.Joints.Reset();
    Snapshot.DisabledPairs.Reset();
    for (auto& Body : Snapshot.Bodies)
    {
        Body.LinearDamping = Body.AngularDamping = 0.0f;
        Body.bAwake = false;
    }
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this, Snapshot, Prepared)) return false;
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    if (!TestNotNull(TEXT("Trajectory Game owner"), Owner)
        || !Okay(*this, TEXT("Initialize trajectory world"), Owner->InitializeSimulation(SmallWorld(4)))) return false;
    FProphecyJoltRigHandle RigA, RigB;
    TArray<FProphecyJoltBodyHandle> BodiesA, BodiesB;
    TArray<FString> Notes;
    if (!Okay(*this, TEXT("Create trajectory rig A"), Owner->CreateRig(Snapshot, Prepared, RigA, BodiesA, Notes))
        || !Okay(*this, TEXT("Create independent trajectory rig B"), Owner->CreateRig(Snapshot, Prepared, RigB, BodiesB, Notes))) return false;
    auto A = MakeTargets(Snapshot, BodiesA), B = MakeTargets(Snapshot, BodiesB);
    const auto Configure = [&](TArray<FProphecyJoltRigVelocityTarget>& Targets, float Duration)
    {
        for (int32 Index = 0; Index < Targets.Num(); ++Index)
        {
            auto& Target = Targets[Index];
            Target.StartPositionCm = Snapshot.Bodies[Targets.Num() - 1 - Index].BodyOriginToWorld.GetLocation();
            Target.TargetPositionCm = Target.StartPositionCm + FVector(180.0 * Duration, 0.0, 0.0);
            Target.TrajectoryDurationSeconds = Duration;
        }
    };
    Configure(A, 0.04f);
    Configure(B, 0.08f);
    // Deliberately unrelated legacy h: trajectory motion is timed by actual
    // integration seconds, while other static-target tests retain caller h.
    if (!Okay(*this, TEXT("Publish A trajectory"), Owner->PublishRigVelocityTargets(RigA, A, 0.7f))
        || !Okay(*this, TEXT("Publish B trajectory"), Owner->PublishRigVelocityTargets(RigB, B, 0.9f))
        || !Okay(*this, TEXT("Advance both trajectories by 10 ms"), Owner->Step(0.01f, 1))) return false;
    const auto CheckRig = [&](const FProphecyJoltRigHandle& Rig, const TArray<FProphecyJoltBodyHandle>& Bodies,
        double X, double Velocity)
    {
        FProphecyJoltRigServoState Servo;
        if (!Okay(*this, TEXT("Read independent trajectory samples"), Owner->ReadRigServoSamples(Rig, Servo))) return false;
        for (const auto& Handle : Bodies)
        {
            FProphecyJoltBodyState Body;
            if (!Okay(*this, TEXT("Read trajectory body"), Owner->ReadBody(Handle, Body))) return false;
            TestNearlyEqual(TEXT("Rig reaches its authored timestamp"), Body.PositionCm.X, X, 0.002);
            TestNearlyEqual(TEXT("Rig retains the corresponding physical velocity"), Body.CenterOfMassVelocityCmPerSecond.X, Velocity, 0.005);
        }
        TestEqual(TEXT("Every independent rig has its own complete samples"), Servo.Samples.Num(), Bodies.Num());
        return true;
    };
    if (!CheckRig(RigA, BodiesA, 1.8, 180.0) || !CheckRig(RigB, BodiesB, 1.8, 180.0)) return false;
    const float NaN = std::numeric_limits<float>::quiet_NaN();
    const float Infinity = std::numeric_limits<float>::infinity();
    for (int32 Case = 0; Case < 7; ++Case)
    {
        auto Rejected = A;
        Rejected[0].TargetPositionCm.X += 1000.0;
        switch (Case)
        {
        case 0: Rejected[1].TrajectoryDurationSeconds = -0.1f; break;
        case 1: Rejected[1].TrajectoryDurationSeconds = NaN; break;
        case 2: Rejected[1].TrajectoryDurationSeconds = Infinity; break;
        case 3: Rejected[1].StartPositionCm.X = NaN; break;
        case 4: Rejected[1].StartPositionCm.X = Infinity; break;
        case 5: Rejected[1].StartRotation.W = 2.0; break;
        case 6: Rejected[1].StartRotation.X = NaN; break;
        }
        TestTrue(TEXT("Malformed trajectory rejects the entire changed packet"),
            Owner->PublishRigVelocityTargets(RigA, Rejected, 0.3f).Code == EProphecyJoltWorldResult::InvalidArgument);
    }
    TestTrue(TEXT("Trajectory publication cannot replace a different rig's body"),
        Owner->PublishRigVelocityTargets(RigA, B, 0.3f).Code == EProphecyJoltWorldResult::InvalidHandle);
    if (!Okay(*this, TEXT("Rebuild flat packet without replay or rejected mutation"), Owner->Step(0.01f, 1))
        || !CheckRig(RigA, BodiesA, 3.6, 180.0) || !CheckRig(RigB, BodiesB, 3.6, 180.0)) return false;
    // Republishing B resets only B's timeline; A must retain its elapsed 20 ms.
    for (auto& Target : B)
    {
        Target.StartPositionCm.X = 3.6;
        Target.TargetPositionCm.X = 7.2;
        Target.TrajectoryDurationSeconds = 0.02f;
    }
    if (!Okay(*this, TEXT("Replace B trajectory independently"), Owner->PublishRigVelocityTargets(RigB, B, 0.5f))
        || !Okay(*this, TEXT("Finish both with two native substeps"), Owner->Step(0.02f, 2))
        || !CheckRig(RigA, BodiesA, 7.2, 180.0) || !CheckRig(RigB, BodiesB, 7.2, 180.0)
        || !Okay(*this, TEXT("Step again without either publication"), Owner->Step(0.01f, 1))
        || !CheckRig(RigA, BodiesA, 7.2, 0.0) || !CheckRig(RigB, BodiesB, 7.2, 0.0)) return false;
    for (auto& Target : A)
    {
        Target.StartPositionCm.X = 7.2;
        Target.TargetPositionCm.X = 10.8;
        Target.TrajectoryDurationSeconds = 0.02f;
    }
    if (!Okay(*this, TEXT("Start A's next accepted trajectory"), Owner->PublishRigVelocityTargets(RigA, A, 0.5f))
        || !Okay(*this, TEXT("Advance A while B keeps its completed endpoint"), Owner->Step(0.01f, 1))
        || !CheckRig(RigA, BodiesA, 9.0, 180.0) || !CheckRig(RigB, BodiesB, 7.2, 0.0)) return false;
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltCollisionUpdateTest,
    "Prophecy.Jolt.Collision.RuntimeUpdateAtomicityAndSleepingContact", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltCollisionUpdateTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::RigWorldTests;
    FScopedWorld Scope;
    auto* Owner = Scope.Get();
    auto Settings = SmallWorld();
    Settings.GravityCmPerSecondSquared = FVector(0, 0, -1000);
    if (!Okay(*this, TEXT("Initialize"), Owner->InitializeSimulation(Settings))) return false;
    FProphecyJoltFixtureBodySettings FloorSettings;
    FloorSettings.bDynamic = false;
    FloorSettings.PositionCm = FVector(0, 0, -10);
    FProphecyJoltBodyHandle Floor, Ball;
    FProphecyJoltFixtureBodySettings BallSettings;
    BallSettings.PositionCm = FVector(0, 0, 20);
    BallSettings.bAllowSleeping = true;
    if (!Okay(*this, TEXT("Create floor"), Owner->CreateBox(FVector(100, 100, 10), 0, FloorSettings, Floor))
        || !Okay(*this, TEXT("Create sphere"), Owner->CreateSphere(10, BallSettings, Ball))) return false;
    for (int32 Frame = 0; Frame < 240; ++Frame)
        if (!Okay(*this, TEXT("Settle contact"), Owner->Step(1.f / 60, 1))) return false;
    FProphecyJoltBodyState Before;
    Owner->ReadBody(Ball, Before);
    TestTrue(TEXT("Sphere rests on floor"), Before.PositionCm.Z > 7 && Before.PositionCm.Z < 13);
    TestFalse(TEXT("Counterpart is asleep before policy change"), Before.bActive);
    FProphecyJoltCollisionUpdate IgnoreFloor;
    IgnoreFloor.Handle = Floor; IgnoreFloor.ObjectChannel = ECC_WorldStatic;
    IgnoreFloor.Responses.SetAllChannels(ECR_Ignore);
    auto Invalid = IgnoreFloor;
    ++Invalid.Handle.Generation;
    TestFalse(TEXT("Stale second handle rejects entire update"), Owner->UpdateBodyCollision({ IgnoreFloor, Invalid }).IsSuccess());
    FProphecyJoltCollisionUpdate Policy;
    Owner->ReadBodyCollision(Floor, Policy);
    TestTrue(TEXT("Earlier valid entry was not changed by rejected batch"), Policy.Responses.GetResponse(ECC_PhysicsBody) == ECR_Block);
    if (!Okay(*this, TEXT("Change supporting static collider to Ignore"), Owner->UpdateBodyCollision({ IgnoreFloor }))) return false;
    FProphecyJoltBodyState After;
    Owner->ReadBody(Ball, After);
    TestTrue(TEXT("Changing static collision wakes sleeping counterpart"), After.bActive);
    TestNearlyEqual(TEXT("Policy update does not move bodies"), After.PositionCm, Before.PositionCm, 1.e-6f);
    TestNearlyEqual(TEXT("Policy update does not rewrite velocity"), After.CenterOfMassVelocityCmPerSecond, Before.CenterOfMassVelocityCmPerSecond, 1.e-6f);
    for (int32 Frame = 0; Frame < 30; ++Frame)
        if (!Okay(*this, TEXT("Step after removing support"), Owner->Step(1.f / 60, 1))) return false;
    Owner->ReadBody(Ball, After);
    TestTrue(TEXT("Cached contact no longer supports sphere"), After.PositionCm.Z < -50);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltImportedInertiaTest,
    "Prophecy.Jolt.RigWorld.AuthoredInertiaConditioning", ProphecyJolt::RigWorldTests::Flags)

bool FProphecyJoltImportedInertiaTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::RigWorldTests;
    TArray<TPair<IConsoleVariable*, FString>> Previous;
    auto Set = [&](const TCHAR* Name, const TCHAR* Value) {
        IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name);
        if (!TestNotNull(Name, Var)) return false;
        if (!Previous.ContainsByPredicate([&](const auto& Pair) { return Pair.Key == Var; })) Previous.Emplace(Var, Var->GetString());
        Var->SetWithCurrentPriority(Value);
        return true;
    };
    ON_SCOPE_EXIT { for (const auto& Pair : Previous) Pair.Key->SetWithCurrentPriority(*Pair.Value); };
    if (!Set(TEXT("p.Chaos.Solver.InertiaConditioning.Enabled"),TEXT("1"))
        || !Set(TEXT("p.Chaos.Solver.InertiaConditioning.Distance"),TEXT("20"))
        || !Set(TEXT("p.Chaos.Solver.InertiaConditioning.RotationRatio"),TEXT("2.5"))
        || !Set(TEXT("p.Chaos.Solver.InertiaConditioning.MaxInvInertiaComponentRatio"),TEXT("0"))
        || !Set(TEXT("p.Chaos.InertiaConditioning.InvMassTolerance"),TEXT("1e-20"))
        || !Set(TEXT("p.Chaos.InertiaConditioning.InvInertiaTolerance"),TEXT("1e-4"))
        || !Set(TEXT("p.Chaos.InertiaConditioning.ExtentTolerance"),TEXT("1e-8"))
        || !Set(TEXT("p.Chaos.ExcludeFreeJointForInertiaConditioning"),TEXT("1"))) return false;

    auto Check = [&](const TCHAR* Label, const FProphecyJoltRigSnapshot& Rig, const FVector& Expected) {
        FProphecyJoltPreparedRig Prepared;
        if (!Prepare(*this, Rig, Prepared)) return false;
        FScopedWorld Scope;
        auto* Owner = Scope.Get();
        if (!Owner || !Okay(*this, TEXT("Initialize inertia check"), Owner->InitializeSimulation(SmallWorld()))) return false;
        FProphecyJoltRigHandle Handle;
        TArray<FProphecyJoltBodyHandle> Bodies;
        TArray<FString> Notes;
        if (!Okay(*this, TEXT("Create conditioned native rig"), Owner->CreateRig(Rig,Prepared,Handle,Bodies,Notes))) return false;
        FProphecyJoltPhysicsCommand Command;
        Command.Operation = EProphecyJoltPhysicsCommand::AngularImpulse;
        Command.Value = FVector(1,1,1); // kg*cm^2/s, independent of the implementation's conditioning calculation.
        if (!Okay(*this, TEXT("Apply physical angular impulse"), Owner->ExecutePhysicsCommand(Bodies[0],Command))) return false;
        FProphecyJoltBodyState State;
        if (!Okay(*this, TEXT("Read angular response"), Owner->ReadBody(Bodies[0],State))) return false;
        TestNearlyEqual(Label, State.AngularVelocityRadiansPerSecond, FVector(1.0/Expected.X,1.0/Expected.Y,1.0/Expected.Z), 1.e-6f);
        Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
        Command.Value = FVector(2,0,0); // A 2 kg body must gain 1 cm/s.
        if (!Okay(*this, TEXT("Apply physical linear impulse"), Owner->ExecutePhysicsCommand(Bodies[0],Command))
            || !Okay(*this, TEXT("Read linear response"), Owner->ReadBody(Bodies[0],State))) return false;
        TestNearlyEqual(TEXT("Conditioning does not change body mass"), State.CenterOfMassVelocityCmPerSecond, FVector(1,0,0), 1.e-6f);
        TestNearlyEqual(TEXT("Raw captured inertia remains provenance"), Rig.Bodies[0].PrincipalInertiaKgCmSquared, FVector(80), 1.e-6f);
        return true;
    };
    auto Rig = MakeRig();
    if (!Check(TEXT("Body opt-out preserves raw inertia"), Rig, FVector(80))) return false;
    Rig.Bodies[0].bInertiaConditioning = true;
    // A 2 kg sphere with 10 cm radius and a joint arm 20 cm along Z.
    // Maximum rotation/translation ratio 2.5 requires Ixy=2*20^2/2.5=320.
    if (!Check(TEXT("Attached joint arm conditions perpendicular axes"), Rig, FVector(320,320,80))) return false;
    auto Free = Rig;
    Free.Joints[0].CurrentProfile.LinearLimit.XMotion = LCM_Free;
    Free.Joints[0].CurrentProfile.LinearLimit.YMotion = LCM_Free;
    Free.Joints[0].CurrentProfile.LinearLimit.ZMotion = LCM_Free;
    // Geometry radius 10 scales the allowed ratio to 1.25: I=2*10^2/1.25=160.
    if (!Check(TEXT("Free joint contributes no arm; geometry still conditions"), Free, FVector(160))) return false;
    auto Offset = Rig;
    Offset.Bodies[0].MassFrameToBodyOrigin.SetTranslation(FVector(0,0,5));
    // Joint arm is now 15 cm, allowed ratio is 1.875; the X/Y/Z moments differ.
    if (!Check(TEXT("Joint arm is measured from the captured COM"), Offset, FVector(240,240,200.0/1.875))) return false;
    auto Rotated = Rig;
    Rotated.Bodies[0].MassFrameToBodyOrigin.SetRotation(FQuat(FVector::RightVector,UE_DOUBLE_HALF_PI));
    if (!Check(TEXT("Conditioned principal tensor rotates back to body space"), Rotated, FVector(320,320,80))) return false;
    Set(TEXT("p.Chaos.Solver.InertiaConditioning.Enabled"),TEXT("0"));
    if (!Check(TEXT("Global opt-out preserves raw inertia"), Rig, FVector(80))) return false;
    Set(TEXT("p.Chaos.Solver.InertiaConditioning.Enabled"),TEXT("1"));
    FProphecyJoltPreparedRig Existing;
    if (!Prepare(*this, Rig, Existing)) return false;
    Set(TEXT("p.Chaos.Solver.InertiaConditioning.RotationRatio"),TEXT("0"));
    FString Error;
    TestFalse(TEXT("Invalid policy rejects before replacing prepared rig"), Existing.Build(Rig, Error));
    TestEqual(TEXT("Rejected policy preserves prepared body count"), Existing.GetBodyCount(), 2);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootExtensionLifecycleTest,"Prophecy.Jolt.RigWorld.FootExtension",
    ProphecyJolt::RigWorldTests::Flags)
bool FProphecyFootExtensionLifecycleTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::RigWorldTests;
    auto Snapshot=MakeRig();
    Snapshot.Bodies[0].BodyName=TEXT("calf_l"); Snapshot.Bodies[1].BodyName=TEXT("foot_l");
    Snapshot.Joints[0].Bone1=TEXT("foot_l"); Snapshot.Joints[0].Bone2=TEXT("calf_l");
    for (int I=0;I<2;++I)
    {
        auto Body=Snapshot.Bodies[I]; Body.SourceBodyIndex=Body.BoneIndex=I+2;
        Body.BodyName=I==0 ? TEXT("calf_r") : TEXT("foot_r");
        Body.BodyOriginToWorld.AddToTranslation(FVector(100,0,0)); Snapshot.Bodies.Add(Body);
    }
    auto Joint=Snapshot.Joints[0]; Joint.SourceConstraintIndex=1; Joint.JointName=TEXT("right_ankle");
    Joint.Body1Index=3; Joint.Body2Index=2; Joint.Bone1=TEXT("foot_r"); Joint.Bone2=TEXT("calf_r");
    Snapshot.Joints.Add(Joint);
    FProphecyJoltPreparedRig Prepared;
    if (!Prepare(*this,Snapshot,Prepared)) return false;
    FScopedWorld Scope; auto* Owner=Scope.Get();
    if (!TestNotNull(TEXT("Owner"),Owner) || !Okay(*this,TEXT("Initialize"),Owner->InitializeSimulation(SmallWorld()))) return false;
    FProphecyJoltRigHandle Rig; TArray<FProphecyJoltBodyHandle> Bodies; TArray<FString> Notes;
    if (!Okay(*this,TEXT("Create ankles"),Owner->CreateRig(Snapshot,Prepared,Rig,Bodies,Notes))) return false;
    const auto Set=[&](float Value)
    {
        FString Error; const auto& H=Bodies[0];
        const bool Result=UProphecyJoltFootJointLibrary::SetFootExtension(Scope.World,H.WorldLifetime,H.Slot,
            int64(H.Generation),Value,FVector(0,0,1),FVector(0,0,1),Error);
        return TestTrue(FString(TEXT("Set foot extension: "))+Error,Result);
    };
    if (!Set(10) || !Counts(*this,*Owner,4,4)) return false;
    if (!Set(5) || !Counts(*this,*Owner,4,4)) return false;
    const auto Range=[&](float Compression,float Extension)
    {
        FString Error;const auto& H=Bodies[0];
        return UProphecyJoltFootJointLibrary::SetFootRange(Scope.World,H.WorldLifetime,H.Slot,
            int64(H.Generation),Compression,Extension,FVector(0,0,1),FVector(0,0,1),Error);
    };
    TestTrue(TEXT("Locomotion supports symmetric calf leeway"),Range(2,2));
    TestTrue(TEXT("Unchanged range is repeatable"),Range(2,2));
    if (!Counts(*this,*Owner,4,4)) return false;
    TestTrue(TEXT("Kick return composes with locomotion floor"),Range(2,5));
    TestTrue(TEXT("Compression-only range is supported"),Range(2,0));
    TestFalse(TEXT("Negative compression rejected"),Range(-1,2));
    if (!Set(5)) return false; // Existing kick API restores extension-only semantics.
    if (!Okay(*this,TEXT("Keep angular update compatible"),Owner->UpdateRigAngularLimits(Rig,Snapshot.Joints))) return false;
    if (!Set(0) || !Counts(*this,*Owner,4,2)) return false;
    if (!Set(10) || !Okay(*this,TEXT("Destroy extended rig"),Owner->DestroyRig(Rig)) || !Counts(*this,*Owner,0,0)) return false;
    if (!Okay(*this,TEXT("Recreate rig"),Owner->CreateRig(Snapshot,Prepared,Rig,Bodies,Notes))) return false;
    if (!Counts(*this,*Owner,4,2) || !Set(6)) return false;
    Scope.Destroy(); // Teardown with an active extension must remove constraints before bodies.
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltAnchoredRigTest,
    "Prophecy.Jolt.RigWorld.KinematicAnchor", ProphecyJolt::RigWorldTests::Flags)
bool FProphecyJoltAnchoredRigTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::RigWorldTests;
    FScopedWorld Scope;
    auto* Owner=Scope.Get();
    if (!Owner || !Okay(*this,TEXT("Initialize"),Owner->InitializeSimulation(SmallWorld()))) return false;
    auto Snapshot=MakeRig();
    Snapshot.Bodies[0].bSimulating=false;
    Snapshot.Bodies[1].bGravityEnabled=true;
    auto& P=Snapshot.Joints[0].CurrentProfile;
    P.ConeLimit.Swing1Motion=P.ConeLimit.Swing2Motion=P.TwistLimit.TwistMotion=ACM_Locked;
    FProphecyJoltPreparedRig Prepared; FString Error;
    if (!TestTrue(TEXT("Prepare mixed rig"),Prepared.Build(Snapshot,Error))) { AddError(Error); return false; }
    FProphecyJoltRigHandle Rig; TArray<FProphecyJoltBodyHandle> Bodies; TArray<FString> Notes;
    if (!Okay(*this,TEXT("Create mixed kinematic/dynamic rig"),Owner->CreateRig(Snapshot,Prepared,Rig,Bodies,Notes))) return false;
    FProphecyJoltBodyState A,B;
    Owner->ReadBody(Bodies[0],A); Owner->ReadBody(Bodies[1],B);
    TestFalse(TEXT("Fixed top is not dynamic"),A.bDynamic);
    TestTrue(TEXT("Hanging body remains dynamic"),B.bDynamic);
    const FVector InitialA=A.PositionCm,InitialB=B.PositionCm;
    const FVector Shift(30,10,20);
    for (int32 I=0;I<60;++I)
    {
        const float Alpha=float(I+1)/60.f;
        if (!Okay(*this,TEXT("Move fixed top"),Owner->MoveKinematicBody(Bodies[0],
            FTransform(FQuat::Identity,InitialA+Shift*Alpha),1.f/60))) return false;
        if (!Okay(*this,TEXT("Step"),Owner->Step(1.f/60,1))) return false;
    }
    Owner->ReadBody(Bodies[0],A); Owner->ReadBody(Bodies[1],B);
    TestTrue(TEXT("Top follows its target exactly"),A.PositionCm.Equals(InitialA+Shift,.01));
    TestTrue(TEXT("Joint transports hanging body"),B.PositionCm.Equals(InitialB+Shift,.5));
    if (!Okay(*this,TEXT("Remove mixed rig"),Owner->DestroyRig(Rig))) return false;
    TestFalse(TEXT("Old top handle retired"),Owner->OwnsBody(Bodies[0]));
    TestFalse(TEXT("Old hanging handle retired"),Owner->OwnsBody(Bodies[1]));
    if (!Okay(*this,TEXT("Recreate mixed rig"),Owner->CreateRig(Snapshot,Prepared,Rig,Bodies,Notes))) return false;
    return Okay(*this,TEXT("Final cleanup"),Owner->DestroyRig(Rig)) && !HasAnyErrors();
}

#endif // WITH_DEV_AUTOMATION_TESTS
