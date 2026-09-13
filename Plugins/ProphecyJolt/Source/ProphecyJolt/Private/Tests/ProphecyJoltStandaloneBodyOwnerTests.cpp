#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyJoltPhysicsCommand.h"
#include <limits>

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "ProphecyJoltBody.h"
#include "ProphecyJoltStaticBody.h"
#include "ProphecyJoltMaterial.h"
#include "ProphecyJoltWorldSubsystem.h"
#include <limits>

namespace ProphecyJolt::StandaloneBodyOwnerTests
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
    Result.MaxBodies = 8;
    Result.MaxBodyPairs = Result.MaxContactConstraints = 64;
    return Result;
}

bool Start(FAutomationTestBase& Test, FScopedWorld& Scope, const FProphecyJoltWorldSettings& In = Settings())
{
    return Test.TestNotNull(TEXT("Transient game world owner"), Scope.Get())
        && Okay(Test, TEXT("Initialize standalone owner world"), Scope.Get()->InitializeSimulation(In));
}

FProphecyJoltBodySnapshot Capture()
{
    FProphecyJoltBodySnapshot Result;
    Result.CaptureId = FGuid::NewGuid();
    Result.ComponentToWorld.SetScale3D(FVector(1.3, 0.7, 2.1));
    auto& Body = Result.Body;
    Body.bSimulating = true;
    Body.bAwake = false;
    Body.bCCD = true;
    Body.bGravityEnabled = false;
    Body.MassKg = 2.0;
    Body.PrincipalInertiaKgCmSquared = FVector(200.0, 500.0, 650.0);
    Body.MassFrameToBodyOrigin = FTransform(FRotator(17, -31, 23), FVector(-4, 8, 3));
    Body.BodyOriginToWorld = FTransform(FRotator(13, 7, -9), FVector(1000, -500, 80));
    Body.SourceBodyScale3D = FVector(4, 5, 6);
    Body.SourceBuildScale3D = FVector(3, 7, 2);
    Body.MaxLinearVelocityCmPerSecond = 10000.0;
    Body.MaxAngularVelocityRadiansPerSecond = 100.0;
    Body.CenterOfMassVelocityCmPerSecond = FVector(17, -23, 11);
    Body.AngularVelocityRadiansPerSecond = FVector(0.2, -0.5, 0.7);
    Body.CollisionEnabled = ECollisionEnabled::QueryAndPhysics;
    Body.ObjectType = ECC_PhysicsBody;
    Body.CollisionResponses.SetAllChannels(ECR_Block);
    Body.LinearDamping = Body.AngularDamping = Body.Friction = Body.Restitution = 0.0;
    auto& Shape = Body.Shapes.AddDefaulted_GetRef();
    Shape.Kind = EProphecyJoltRigShape::Sphere;
    Shape.SourceElementIndex = 0;
    Shape.RadiusCm = 10.0;
    Shape.AuthoredCollisionEnabled = Shape.CurrentCollisionEnabled = ECollisionEnabled::QueryAndPhysics;
    return Result;
}

bool Prepare(FAutomationTestBase& Test, const FProphecyJoltBodySnapshot& Snapshot, FProphecyJoltPreparedBody& Prepared)
{
    FString Error;
    const bool bPrepared = Prepared.Build(Snapshot, Error);
    return Test.TestTrue(FString(TEXT("Prepare captured standalone geometry and mass: ")) + Error, bPrepared);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStandaloneMassVelocityTest,
    "Prophecy.Jolt.BodyOwner.CapturedMassPoseAndVelocity", ProphecyJolt::StandaloneBodyOwnerTests::Flags)

bool FProphecyJoltStandaloneMassVelocityTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StandaloneBodyOwnerTests;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    const auto Snapshot = Capture();
    FProphecyJoltPreparedBody Prepared;
    FProphecyJoltBodyHandle Handle;
    TArray<FString> Notes;
    FProphecyJoltBodyState State;
    if (!Prepare(*this, Snapshot, Prepared)
        || !Okay(*this, TEXT("Create exact prepared standalone body"), World.CreateBody(Snapshot, Prepared, Handle, Notes))
        || !Okay(*this, TEXT("Read initial standalone state"), World.ReadBody(Handle, State))) return false;
    TestTrue(TEXT("Independent body ownership is live"), World.OwnsBody(Handle));
    TestTrue(TEXT("Body origin remains separate from COM"), State.PositionCm.Equals(Snapshot.Body.BodyOriginToWorld.GetTranslation(), 0.002));
    TestTrue(TEXT("Captured body rotation is preserved"), State.Rotation.AngularDistance(Snapshot.Body.BodyOriginToWorld.GetRotation()) < 1.0e-5);
    const FVector ExpectedCOM = Snapshot.Body.BodyOriginToWorld.TransformPosition(Snapshot.Body.MassFrameToBodyOrigin.GetTranslation());
    TestTrue(TEXT("Captured COM offset is transformed exactly once"), State.CenterOfMassPositionCm.Equals(ExpectedCOM, 0.002));
    TestTrue(TEXT("Initial COM velocity is preserved"), State.CenterOfMassVelocityCmPerSecond.Equals(Snapshot.Body.CenterOfMassVelocityCmPerSecond, 0.002));
    TestTrue(TEXT("Initial angular velocity is preserved"), State.AngularVelocityRadiansPerSecond.Equals(Snapshot.Body.AngularVelocityRadiansPerSecond, 1.0e-5));
    TestFalse(TEXT("Creation honors captured sleeping state"), State.bActive);
    FProphecyJoltRayHit Hit;
    bool bHit = false;
    if (!Okay(*this, TEXT("Ray tests actual prepared geometry"), World.RayCast(
        Snapshot.Body.BodyOriginToWorld.TransformPosition(FVector(-20, 0, 0)),
        Snapshot.Body.BodyOriginToWorld.TransformPosition(FVector(20, 0, 0)), Hit, bHit))) return false;
    TestTrue(TEXT("Prepared sphere is present at its body origin"), bHit);
    TestNearlyEqual(TEXT("Visual/source scales do not resize native geometry again"), Hit.Fraction, 0.25f, 0.0001f);

    const FVector Linear(31, -11, 23), Angular(-0.3, 0.7, 0.2);
    if (!Okay(*this, TEXT("Store velocities without waking"), World.SetBodyVelocity(Handle, Linear, Angular, false))
        || !Okay(*this, TEXT("Read sleeping stored velocities"), World.ReadBody(Handle, State))) return false;
    TestFalse(TEXT("False wake policy preserves sleep"), State.bActive);
    TestTrue(TEXT("COM velocity write uses cm/s"), State.CenterOfMassVelocityCmPerSecond.Equals(Linear, 0.002));
    TestTrue(TEXT("Angular velocity write uses world radians/s"), State.AngularVelocityRadiansPerSecond.Equals(Angular, 1.0e-5));
    TestEqual(TEXT("Nonfinite velocity is rejected before either write"), World.SetBodyVelocity(Handle,
        FVector(std::numeric_limits<double>::quiet_NaN(), 0, 0), FVector::ZeroVector, true).Code, EProphecyJoltWorldResult::InvalidArgument);
    TestEqual(TEXT("Finite components with overflowing native norm are rejected"), World.SetBodyVelocity(Handle,
        FVector(1.0e30, 0, 0), FVector::ZeroVector, true).Code, EProphecyJoltWorldResult::InvalidArgument);
    if (!Okay(*this, TEXT("Read after rejected velocity writes"), World.ReadBody(Handle, State))) return false;
    TestFalse(TEXT("Rejected write does not wake"), State.bActive);
    TestTrue(TEXT("Rejected request does not partially clear COM velocity"), State.CenterOfMassVelocityCmPerSecond.Equals(Linear, 0.002));
    TestTrue(TEXT("Rejected request does not partially clear angular velocity"), State.AngularVelocityRadiansPerSecond.Equals(Angular, 1.0e-5));
    if (!Okay(*this, TEXT("Explicitly wake body"), World.SetBodyVelocity(Handle, Linear, Angular, true))) return false;

    const FVector Impulse(7, -5, 11), Lever(9, 4, -6);
    const FQuat PrincipalToWorld = State.Rotation * Snapshot.Body.MassFrameToBodyOrigin.GetRotation();
    const FVector AngularImpulsePrincipal = PrincipalToWorld.UnrotateVector(FVector::CrossProduct(Lever, Impulse));
    const FVector ExpectedAngular = Angular + PrincipalToWorld.RotateVector(AngularImpulsePrincipal / Snapshot.Body.PrincipalInertiaKgCmSquared);
    if (!Okay(*this, TEXT("Apply impulse about captured COM"), World.AddPointImpulse(Handle, Impulse, State.CenterOfMassPositionCm + Lever))
        || !Okay(*this, TEXT("Read full captured inertia response"), World.ReadBody(Handle, State))) return false;
    TestTrue(TEXT("Explicit wake policy activates"), State.bActive);
    TestTrue(TEXT("Impulse uses captured mass"), State.CenterOfMassVelocityCmPerSecond.Equals(Linear + Impulse / Snapshot.Body.MassKg, 0.002));
    TestTrue(TEXT("Off-center impulse uses rotated full captured inertia"), State.AngularVelocityRadiansPerSecond.Equals(ExpectedAngular, 0.0002));
    if (!Okay(*this, TEXT("Apply captured speed caps"), World.SetBodyVelocity(Handle, FVector(20000, 0, 0), FVector(0, 200, 0), false))
        || !Okay(*this, TEXT("Read speed-capped velocities"), World.ReadBody(Handle, State))) return false;
    TestNearlyEqual(TEXT("Captured linear cap is applied"), State.CenterOfMassVelocityCmPerSecond.Size(), Snapshot.Body.MaxLinearVelocityCmPerSecond, 0.01);
    TestNearlyEqual(TEXT("Captured angular cap is applied"), State.AngularVelocityRadiansPerSecond.Size(), Snapshot.Body.MaxAngularVelocityRadiansPerSecond, 0.001);
    return Okay(*this, TEXT("Destroy standalone owner"), World.DestroyBody(Handle));
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStandaloneInitialVelocityCapsTest,
    "Prophecy.Jolt.BodyOwner.InitialVelocityCaps", ProphecyJolt::StandaloneBodyOwnerTests::Flags)

bool FProphecyJoltStandaloneInitialVelocityCapsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StandaloneBodyOwnerTests;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto Snapshot = Capture();
    const FVector LinearDirection = FVector(3, -4, 0).GetSafeNormal();
    const FVector AngularDirection = FVector(-2, 1, 2).GetSafeNormal();
    Snapshot.Body.CenterOfMassVelocityCmPerSecond = LinearDirection * Snapshot.Body.MaxLinearVelocityCmPerSecond * 3.0;
    Snapshot.Body.AngularVelocityRadiansPerSecond = AngularDirection * Snapshot.Body.MaxAngularVelocityRadiansPerSecond * 4.0;
    FProphecyJoltPreparedBody Prepared;
    FProphecyJoltBodyHandle Handle;
    FProphecyJoltBodyState State;
    TArray<FString> Notes;
    auto& World = *Scope.Get();
    // Read immediately after creation: no solver step may hide an unsafe initial velocity assignment.
    if (!Prepare(*this, Snapshot, Prepared)
        || !Okay(*this, TEXT("Create sleeping standalone body from captured overspeed"), World.CreateBody(Snapshot, Prepared, Handle, Notes))
        || !Okay(*this, TEXT("Read clamped initial standalone velocity"), World.ReadBody(Handle, State))) return false;
    TestNearlyEqual(TEXT("Initial standalone linear speed uses the unchanged captured cap"),
        State.CenterOfMassVelocityCmPerSecond.Size(), Snapshot.Body.MaxLinearVelocityCmPerSecond, 0.01);
    TestNearlyEqual(TEXT("Initial standalone angular speed uses the unchanged captured cap"),
        State.AngularVelocityRadiansPerSecond.Size(), Snapshot.Body.MaxAngularVelocityRadiansPerSecond, 0.001);
    TestTrue(TEXT("Linear clamping preserves captured world direction"),
        State.CenterOfMassVelocityCmPerSecond.GetSafeNormal().Equals(LinearDirection, 1.0e-6));
    TestTrue(TEXT("Angular clamping preserves captured world direction"),
        State.AngularVelocityRadiansPerSecond.GetSafeNormal().Equals(AngularDirection, 1.0e-6));
    TestFalse(TEXT("Clamping initial velocity does not wake a captured sleeping body"), State.bActive);
    return Okay(*this, TEXT("Destroy overspeed standalone body"), World.DestroyBody(Handle)) && !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStandaloneAdmissionTest,
    "Prophecy.Jolt.BodyOwner.AdmissionGenerationAndEndingCleanup", ProphecyJolt::StandaloneBodyOwnerTests::Flags)

bool FProphecyJoltStandaloneAdmissionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StandaloneBodyOwnerTests;
    FScopedWorld Scope, Other;
    auto In = Settings(); In.MaxBodies = 1;
    if (!Start(*this, Scope, In) || !Start(*this, Other)) return false;
    auto& World = *Scope.Get();
    auto Snapshot = Capture();
    FProphecyJoltPreparedBody Prepared;
    FProphecyJoltBodyHandle Handle, Rejected;
    TArray<FString> Notes;
    if (!Prepare(*this, Snapshot, Prepared)
        || !Okay(*this, TEXT("Admit first standalone body"), World.CreateBody(Snapshot, Prepared, Handle, Notes))) return false;
    FProphecyJoltWorldDiagnostics Before, After;
    World.GetDiagnostics(Before);
    auto Mismatch = Snapshot; Mismatch.CaptureId = FGuid::NewGuid();
    Rejected = Handle; Notes.Add(TEXT("Sentinel"));
    TestEqual(TEXT("Prepared identity mismatch is rejected"), World.CreateBody(Mismatch, Prepared, Rejected, Notes).Code, EProphecyJoltWorldResult::InvalidArgument);
    TestFalse(TEXT("Rejected creation clears previous output handle"), Rejected.IsSet());
    TestEqual(TEXT("Rejected creation clears coverage output"), Notes.Num(), 0);
    auto Foreign = Snapshot; Foreign.SourceWorld = Other.World;
    TestEqual(TEXT("Foreign live source world is rejected"), World.CreateBody(Foreign, Prepared, Rejected, Notes).Code, EProphecyJoltWorldResult::InvalidArgument);
    TestFalse(TEXT("Another world does not own the native handle"), Other.Get()->OwnsBody(Handle));
    TestEqual(TEXT("Another world cannot write this body's velocity"), Other.Get()->SetBodyVelocity(Handle, FVector::ZeroVector, FVector::ZeroVector, true).Code, EProphecyJoltWorldResult::InvalidHandle);
    auto Extra = Capture(); Extra.Body.ObjectType = ECC_WorldDynamic;
    FProphecyJoltPreparedBody ExtraPrepared;
    if (!Prepare(*this, Extra, ExtraPrepared)) return false;
    TestEqual(TEXT("Body capacity rejects a distinct pending collision profile"), World.CreateBody(Extra, ExtraPrepared, Rejected, Notes).Code, EProphecyJoltWorldResult::CapacityExceeded);
    World.GetDiagnostics(After);
    TestEqual(TEXT("Failed admissions leave the original body intact"), After.BodyCount, Before.BodyCount);
    TestEqual(TEXT("Failed admissions do not intern pending profiles"), After.CollisionProfileCount, Before.CollisionProfileCount);
    TestTrue(TEXT("Original ownership survives admission failures"), World.OwnsBody(Handle));
    if (!Okay(*this, TEXT("Destroy original body generation"), World.DestroyBody(Handle))
        || !Okay(*this, TEXT("Reuse native registry slot safely"), World.CreateBody(Snapshot, Prepared, Rejected, Notes))) return false;
    TestFalse(TEXT("Retired generation is no longer owned"), World.OwnsBody(Handle));
    TestTrue(TEXT("Replacement generation is owned"), World.OwnsBody(Rejected));
    TestEqual(TEXT("Stale destroy cannot remove replacement"), World.DestroyBody(Handle).Code, EProphecyJoltWorldResult::InvalidHandle);
    Scope.World->bIsTearingDown = true;
    TestEqual(TEXT("Ending world rejects new velocity work"), World.SetBodyVelocity(Rejected, FVector::ZeroVector, FVector::ZeroVector, false).Code, EProphecyJoltWorldResult::WorldEnding);
    TestTrue(TEXT("Ending world still exposes exact owner identity"), World.OwnsBody(Rejected));
    const auto Removed = World.DestroyBody(Rejected);
    Scope.World->bIsTearingDown = false;
    if (!Okay(*this, TEXT("Idle cleanup succeeds while world is ending"), Removed)) return false;
    TestFalse(TEXT("Ending cleanup invalidates the handle"), World.OwnsBody(Rejected));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltMaterialContactsTest,
    "Prophecy.Jolt.MaterialCombine.ImportedContactMatrix", ProphecyJolt::StandaloneBodyOwnerTests::Flags)

bool FProphecyJoltMaterialContactsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StandaloneBodyOwnerTests;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    FString Error;
    TArray<FString> Notes;
    // All sixteen mixed-mode pairs, for standalone AND rig bodies against imported static
    // geometry. Reuse slots to catch stale material bits. Friction and bounce use opposite
    // mode matrices so accidentally reading the wrong two bits fails this physical test.
    for (int32 RigPath = 0; RigPath < 2; ++RigPath)
    for (uint8 A = 0; A < 4; ++A)
    for (uint8 B = 0; B < 4; ++B)
    {
        FProphecyJoltStaticBodySnapshot Floor;
        Floor.CaptureId = FGuid::NewGuid();
        Floor.BodyOriginToWorld.SetTranslation(FVector(0, 0, -10));
        Floor.CollisionEnabled = ECollisionEnabled::QueryAndPhysics;
        Floor.CollisionResponses.SetAllChannels(ECR_Block);
        Floor.Friction = Floor.Restitution = 0.2f;
        Floor.EffectiveFrictionCombineMode = 3 - A;
        Floor.EffectiveRestitutionCombineMode = A;
        auto& Box = Floor.SimpleShapes.AddDefaulted_GetRef();
        Box.Kind = EProphecyJoltRigShape::Box;
        Box.SourceElementIndex = Box.SourceNativeShapeIndex = 0;
        Box.BoxHalfExtentCm = FVector(1000, 1000, 10);
        Box.AuthoredCollisionEnabled = Box.CurrentCollisionEnabled = ECollisionEnabled::QueryAndPhysics;
        FProphecyJoltPreparedStaticBody PreparedFloor;
        FProphecyJoltBodyHandle FloorHandle, BallHandle;
        if (!TestTrue(*Error, PreparedFloor.Build(Floor, Error))
            || !Okay(*this, TEXT("Import material floor"), World.CreateStaticBody(Floor, PreparedFloor, FloorHandle, Notes))) return false;

        FProphecyJoltBodySnapshot Ball = Capture();
        auto& Body = Ball.Body;
        Body.BodyOriginToWorld = FTransform(FVector(0, 0, 11));
        Body.MassFrameToBodyOrigin = FTransform::Identity;
        Body.MassKg = 1;
        Body.PrincipalInertiaKgCmSquared = FVector(1.0e12); // Suppress rolling for analytic sliding impulse.
        Body.CenterOfMassVelocityCmPerSecond = FVector(1000, 0, -400);
        Body.AngularVelocityRadiansPerSecond = FVector::ZeroVector;
        Body.bAwake = true; Body.bCCD = false;
        Body.Friction = Body.Restitution = 0.8f;
        Body.EffectiveFrictionCombineMode = 3 - B;
        Body.EffectiveRestitutionCombineMode = B;
        FProphecyJoltRigHandle RigHandle;
        if (RigPath)
        {
            FProphecyJoltRigSnapshot Rig;
            Rig.CaptureId = FGuid::NewGuid();
            auto& RigBody = Rig.Bodies.AddDefaulted_GetRef();
            static_cast<FProphecyJoltBodyData&>(RigBody) = Body;
            RigBody.SourceBodyIndex = RigBody.BoneIndex = 0;
            RigBody.BodyName = TEXT("contact_sphere");
            FProphecyJoltPreparedRig Prepared;
            TArray<FProphecyJoltBodyHandle> Handles;
            if (!TestTrue(*Error, Prepared.Build(Rig, Error))
                || !Okay(*this, TEXT("Import material rig"), World.CreateRig(Rig, Prepared, RigHandle, Handles, Notes))) return false;
            BallHandle = Handles[0];
        }
        else
        {
            FProphecyJoltPreparedBody Prepared;
            if (!Prepare(*this, Ball, Prepared)
                || !Okay(*this, TEXT("Import material body"), World.CreateBody(Ball, Prepared, BallHandle, Notes))) return false;
        }
        FProphecyJoltBodyState State;
        for (int32 Step = 0; Step < 12; ++Step)
        {
            if (!Okay(*this, TEXT("Contact step"), World.Step(1.0f / 240.0f, 1))
                || !Okay(*this, TEXT("Read contact response"), World.ReadBody(BallHandle, State))) return false;
            if (State.CenterOfMassVelocityCmPerSecond.Z > 0) break;
        }
        // Independent expected values for coefficients 0.2/0.8 and UE mode precedence.
        const double Expected[] = {0.5, 0.2, 0.16, 0.8};
        const double E = Expected[FMath::Max(A, B)];
        const double Mu = Expected[FMath::Max(3 - A, 3 - B)];
        const FString Context = FString::Printf(TEXT("path=%d modes=%u/%u actual Vx/Vz=%.4f/%.4f expected=%.4f/%.4f"),
            RigPath, A, B, State.CenterOfMassVelocityCmPerSecond.X, State.CenterOfMassVelocityCmPerSecond.Z,
            1000 - Mu * 400 * (1 + E), 400 * E);
        TestTrue(Context + TEXT(" restitution impulse"), FMath::Abs(State.CenterOfMassVelocityCmPerSecond.Z - 400 * E) < 0.1);
        TestTrue(Context + TEXT(" friction impulse"), FMath::Abs(State.CenterOfMassVelocityCmPerSecond.X - (1000 - Mu * 400 * (1 + E))) < 0.2);
        if (RigPath) { if (!Okay(*this, TEXT("Retire material rig"), World.DestroyRig(RigHandle))) return false; }
        else if (!Okay(*this, TEXT("Retire material body"), World.DestroyBody(BallHandle))) return false;
        if (!Okay(*this, TEXT("Retire material floor"), World.DestroyBody(FloorHandle))) return false;
    }
    // Bad serialized/caller modes must fail before reaching the bit-packed native contract.
    auto Bad = Capture();
    Bad.Body.EffectiveFrictionCombineMode = 4;
    TestFalse(TEXT("Reject invalid standalone combine mode"), ProphecyJolt::Body::ValidateSnapshot(Bad, Error));
    TestTrue(TEXT("Huge multiplied coefficients remain finite"),
        FMath::IsFinite(ProphecyJolt::Material::Combine(MAX_flt, MAX_flt, 2, 2)));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPhysicsCommandsTest,
    "Prophecy.Jolt.PhysicsCommands.UnitsMassInertiaAndLifetime", ProphecyJolt::StandaloneBodyOwnerTests::Flags)

bool FProphecyJoltPhysicsCommandsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StandaloneBodyOwnerTests;
    using EOp = EProphecyJoltPhysicsCommand;
    FScopedWorld Scope;
    if (!Start(*this, Scope)) return false;
    auto& World = *Scope.Get();
    for (int32 Case = 0; Case < 14; ++Case)
    {
        auto Snapshot = Capture();
        Snapshot.Body.CenterOfMassVelocityCmPerSecond = Snapshot.Body.AngularVelocityRadiansPerSecond = FVector::ZeroVector;
        Snapshot.Body.LinearDamping = Snapshot.Body.AngularDamping = 0;
        FProphecyJoltPreparedBody Prepared;
        FProphecyJoltBodyHandle Handle;
        TArray<FString> Notes;
        if (!Prepare(*this, Snapshot, Prepared) || !Okay(*this, TEXT("Create command body"), World.CreateBody(Snapshot, Prepared, Handle, Notes))) return false;
        FProphecyJoltBodyState Before, After;
        if (!Okay(*this, TEXT("Read body"), World.ReadBody(Handle, Before))) return false;
        const FQuat Principal = Snapshot.Body.BodyOriginToWorld.GetRotation() * Snapshot.Body.MassFrameToBodyOrigin.GetRotation();
        auto InvInertia = [&](FVector V) { return Principal.RotateVector(Principal.UnrotateVector(V) / Snapshot.Body.PrincipalInertiaKgCmSquared); };
        const FVector Value(12, -17, 23);
        FVector ExpectedLinear = FVector::ZeroVector, ExpectedAngular = FVector::ZeroVector;
        FProphecyJoltPhysicsCommand Command;
        Command.Value = Value;
        const float H = 0.001f;
        bool bStep = false;
        switch (Case)
        {
        case 0: case 1:
            Command.Operation = EOp::Force; Command.bMassIndependent = Case == 1; bStep = true;
            ExpectedLinear = Value * H / (Command.bMassIndependent ? 1.0 : Snapshot.Body.MassKg); break;
        case 2: case 3:
            Command.Operation = EOp::Torque; Command.bMassIndependent = Case == 3; bStep = true;
            ExpectedAngular = (Command.bMassIndependent ? Value : InvInertia(Value)) * H; break;
        case 4: case 5:
            Command.Operation = EOp::Impulse; Command.bMassIndependent = Case == 5;
            ExpectedLinear = Value / (Command.bMassIndependent ? 1.0 : Snapshot.Body.MassKg); break;
        case 6: case 7:
            Command.Operation = EOp::AngularImpulse; Command.bMassIndependent = Case == 7;
            ExpectedAngular = Command.bMassIndependent ? Value : InvInertia(Value); break;
        case 8: case 9:
            Command.Operation = Case == 8 ? EOp::Force : EOp::Impulse; bStep = Case == 8;
            Command.bAtPosition = true; Command.Position = Before.CenterOfMassPositionCm + FVector(10, -5, 3);
            ExpectedLinear = Value / Snapshot.Body.MassKg;
            ExpectedAngular = InvInertia(FVector(10, -5, 3).Cross(Value));
            if (bStep) { ExpectedLinear *= H; ExpectedAngular *= H; } break;
        case 10:
            Command.Operation = EOp::Force; Command.bAtPosition = Command.bLocalSpace = true;
            Command.Position = FVector(4, 9, -2); bStep = true;
            {
                const FVector V = Before.Rotation.RotateVector(Value);
                const FVector P = Before.PositionCm + Before.Rotation.RotateVector(Command.Position);
                ExpectedLinear = V * H / Snapshot.Body.MassKg;
                ExpectedAngular = InvInertia((P - Before.CenterOfMassPositionCm).Cross(V)) * H;
            } break;
        case 11: Command.Operation = EOp::LinearVelocity; ExpectedLinear = Value; break;
        case 12: Command.Operation = EOp::AngularVelocity; ExpectedAngular = Value; break;
        case 13:
            Command.Operation = EOp::LinearVelocity; Command.bAddToCurrent = true;
            if (!Okay(*this, TEXT("Initial velocity"), World.SetBodyVelocity(Handle, FVector(1,2,3), FVector(0.1,0.2,0.3), false))) return false;
            ExpectedLinear = Value + FVector(1,2,3); ExpectedAngular = FVector(0.1,0.2,0.3); break;
        }
        if (!Okay(*this, TEXT("Apply standard command"), World.ExecutePhysicsCommand(Handle, Command))) return false;
        if (bStep && !Okay(*this, TEXT("Integrate force once"), World.Step(H, 1))) return false;
        if (!Okay(*this, TEXT("Read commanded body"), World.ReadBody(Handle, After))) return false;
        TestTrue(*FString::Printf(TEXT("Case %d linear cm/s"), Case), After.CenterOfMassVelocityCmPerSecond.Equals(ExpectedLinear, 0.003));
        TestTrue(*FString::Printf(TEXT("Case %d angular rad/s"), Case), After.AngularVelocityRadiansPerSecond.Equals(ExpectedAngular, 0.003));
        TestTrue(TEXT("Nonzero command wakes sleeping body"), After.bActive);
        if (Case == 0)
        {
            if (!Okay(*this, TEXT("Next step has no residual force"), World.Step(H,1)) || !Okay(*this,TEXT("Read second step"),World.ReadBody(Handle,Before))) return false;
            TestTrue(TEXT("Force lasts one Update, not forever"), Before.CenterOfMassVelocityCmPerSecond.Equals(After.CenterOfMassVelocityCmPerSecond,0.001));
            Command.Value.X = std::numeric_limits<double>::infinity();
            TestFalse(TEXT("Nonfinite force rejected"),World.ExecutePhysicsCommand(Handle,Command).IsSuccess());
            Command.Value = FVector(1e300);
            TestFalse(TEXT("Overflow force rejected"),World.ExecutePhysicsCommand(Handle,Command).IsSuccess());
        }
        if (!Okay(*this, TEXT("Destroy command body"), World.DestroyBody(Handle))) return false;
        TestFalse(TEXT("Retired handle cannot receive commands"), World.ExecutePhysicsCommand(Handle,Command).IsSuccess());
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRuntimeMaterialTest,
    "Prophecy.Jolt.MaterialCombine.RuntimeContactsAndAtomicity", ProphecyJolt::StandaloneBodyOwnerTests::Flags)

bool FProphecyJoltRuntimeMaterialTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StandaloneBodyOwnerTests;
    FScopedWorld Scope;
    auto Config = Settings(); Config.GravityCmPerSecondSquared.Z = -980;
    if (!Start(*this, Scope, Config)) return false;
    auto& World = *Scope.Get();
    FProphecyJoltFixtureBodySettings Floor;
    Floor.bDynamic = false; Floor.PositionCm.Z = -10; Floor.Friction = 0.8f;
    FProphecyJoltFixtureBodySettings Cube;
    Cube.PositionCm.Z = 10; Cube.Friction = 0.8f; Cube.bAllowSleeping = true;
    Cube.LinearDamping = Cube.AngularDamping = 0;
    FProphecyJoltBodyHandle FloorId, CubeId;
    if (!Okay(*this, TEXT("Create contact floor"), World.CreateBox(FVector(1000,1000,10), 0, Floor, FloorId))
        || !Okay(*this, TEXT("Create resting cube"), World.CreateBox(FVector(10), 0, Cube, CubeId))) return false;
    for (int32 I=0; I<240; ++I) if (!Okay(*this,TEXT("Settle"),World.Step(1.0f/60,1))) return false;
    FProphecyJoltBodyState Before, After;
    World.ReadBody(CubeId, Before);
    TestFalse(TEXT("Contact body sleeps before material change"), Before.bActive);
    FProphecyJoltBodyMaterial Original;
    World.ReadBodyMaterial(CubeId, Original);
    FProphecyJoltMaterialUpdate Change{CubeId, {0,0,1,0}};
    if (!Okay(*this,TEXT("Remove friction on sleeping contact"),World.UpdateBodyMaterials(MakeArrayView(&Change,1)))) return false;
    World.ReadBody(CubeId, After);
    TestTrue(TEXT("Material update wakes body without replacing or moving it"), After.bActive && Before.PositionCm.Equals(After.PositionCm,1e-6));
    World.SetBodyVelocity(CubeId,FVector(100,0,0),FVector::ZeroVector,true);
    for (int32 I=0; I<30; ++I) World.Step(1.0f/60,1);
    World.ReadBody(CubeId, After);
    TestTrue(TEXT("Existing floor contact becomes frictionless"), FMath::Abs(After.CenterOfMassVelocityCmPerSecond.X-100)<0.1);
    FProphecyJoltBodyMaterial Current;
    FProphecyJoltMaterialUpdate Invalid[] = {{CubeId, Original}, {{}, Original}};
    TestFalse(TEXT("Invalid later handle rejects entire batch"),World.UpdateBodyMaterials(Invalid).IsSuccess());
    World.ReadBodyMaterial(CubeId,Current);
    TestEqual(TEXT("Failed batch preserves frictionless material"),Current.Friction,0.0f);
    Invalid[1].Handle=FloorId; Invalid[1].Material.Restitution=2;
    TestFalse(TEXT("Invalid later coefficient rejects entire batch"),World.UpdateBodyMaterials(Invalid).IsSuccess());
    World.ReadBodyMaterial(CubeId,Current);
    TestEqual(TEXT("Bad coefficient causes no partial reset"),Current.Friction,0.0f);
    Change.Material=Original;
    if (!Okay(*this,TEXT("Restore friction during sliding"),World.UpdateBodyMaterials(MakeArrayView(&Change,1)))) return false;
    for (int32 I=0; I<60; ++I) World.Step(1.0f/60,1);
    World.ReadBody(CubeId,After);
    TestTrue(TEXT("Restored friction stops the same body on the same floor"),FMath::Abs(After.CenterOfMassVelocityCmPerSecond.X)<1);
    World.ReadBodyMaterial(FloorId,Current);
    TestEqual(TEXT("Neighbor material remains unchanged"),Current.Friction,Floor.Friction);
    return !HasAnyErrors();
}

#endif
