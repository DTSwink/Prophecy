#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "ProphecyJoltStaticBody.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Chaos/TriangleMeshImplicitObject.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "UObject/Package.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/SubShapeID.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::StaticBodyTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
class FWorldFixture final
{
public:
    FWorldFixture()
    {
        const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
            .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
            .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
        World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (World && GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    }
    ~FWorldFixture()
    {
        if (!World) return;
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
        World->MarkAsGarbage();
    }
    AActor* SpawnActor()
    {
        FActorSpawnParameters Spawn;
        Spawn.ObjectFlags |= RF_Transient;
        Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return World ? World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn) : nullptr;
    }
    UWorld* World = nullptr;
};

bool Okay(FAutomationTestBase& Test, const TCHAR* Context, const FProphecyJoltWorldStatus& Status)
{
    if (Status.IsSuccess()) return true;
    Test.AddError(FString::Printf(TEXT("%s: %s"), Context, *Status.Message)); return false;
}

UProphecyJoltWorldSubsystem* Start(FAutomationTestBase& Test, FWorldFixture& Fixture)
{
    auto* Owner = Fixture.World ? Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Test.TestNotNull(TEXT("Real game world native owner"), Owner)) return nullptr;
    FProphecyJoltWorldSettings Settings;
    Settings.MaxBodies = 8; Settings.MaxBodyPairs = Settings.MaxContactConstraints = 64;
    return Okay(Test, TEXT("Initialize bounded static fixture"), Owner->InitializeSimulation(Settings)) ? Owner : nullptr;
}

UStaticMeshComponent* AddMesh(FWorldFixture& Fixture, UStaticMesh& Asset, const FTransform& Transform)
{
    AActor* Actor = Fixture.SpawnActor();
    if (!Actor) return nullptr;
    auto* Mesh = NewObject<UStaticMeshComponent>(Actor, NAME_None, RF_Transient);
    Actor->AddInstanceComponent(Mesh); Actor->SetRootComponent(Mesh);
    Mesh->SetStaticMesh(&Asset); Mesh->SetMobility(EComponentMobility::Static);
    Mesh->SetWorldTransform(Transform);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->SetCollisionObjectType(ECC_WorldStatic); Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetGenerateOverlapEvents(false); Mesh->RegisterComponent();
    return Mesh;
}

bool Import(FAutomationTestBase& Test, UProphecyJoltWorldSubsystem& Owner, UPrimitiveComponent& Component, int32 Instance,
    FProphecyJoltStaticBodySnapshot& Snapshot, FProphecyJoltPreparedStaticBody& Prepared, FProphecyJoltBodyHandle& Handle)
{
    FString Error;
    if (!StaticBody::CaptureStaticBody(Component, Instance, Snapshot, Error) || !Prepared.Build(Snapshot, Error))
    { Test.AddError(Error); return false; }
    TArray<FString> Notes;
    return Okay(Test, TEXT("Create static body from actual native capture"), Owner.CreateStaticBody(Snapshot, Prepared, Handle, Notes));
}

bool MatchingRay(FAutomationTestBase& Test, FWorldFixture& Fixture, UProphecyJoltWorldSubsystem& Owner,
    UPrimitiveComponent& ExpectedComponent, const FVector& StartPoint, const FVector& EndPoint, bool bComplex,
    FProphecyJoltRayHit& NativeHit)
{
    bool bNativeHit = false;
    if (!Okay(Test, TEXT("Trace prepared static geometry"), Owner.RayCast(StartPoint, EndPoint, NativeHit, bNativeHit))) return false;
    FHitResult UEHit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ProphecyJoltStaticBodyTest), bComplex);
    const bool bUEHit = Fixture.World->LineTraceSingleByChannel(UEHit, StartPoint, EndPoint, ECC_Visibility, Params);
    return Test.TestTrue(TEXT("UE query receiver remains present"), bUEHit && UEHit.GetComponent() == &ExpectedComponent)
        && Test.TestTrue(TEXT("Jolt static geometry is present"), bNativeHit)
        && Test.TestTrue(TEXT("Jolt matches the actual native surface"), NativeHit.PositionCm.Equals(UEHit.ImpactPoint, 0.05))
        && Test.TestTrue(TEXT("Imported winding retains the native outward normal"), FVector::DotProduct(NativeHit.Normal, UEHit.ImpactNormal) > 0.99);
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStaticSimpleTest,
    "Prophecy.Jolt.StaticBody.ActualSimpleFloorAndCleanup", ProphecyJolt::StaticBodyTests::Flags)

bool FProphecyJoltStaticSimpleTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StaticBodyTests;
    FWorldFixture Fixture;
    auto* Owner = Start(*this, Fixture);
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!Owner || !TestNotNull(TEXT("Actual simple collision asset"), Cube)) return false;
    auto* Mesh = AddMesh(Fixture, *Cube, FTransform(FRotator(0, 23, 0), FVector(0, 0, -10), FVector(10, 10, 0.2)));
    if (!TestNotNull(TEXT("Registered floor source"), Mesh)) return false;
    FProphecyJoltStaticBodySnapshot Snapshot;
    FProphecyJoltPreparedStaticBody Prepared;
    FProphecyJoltBodyHandle Floor;
    if (!Import(*this, *Owner, *Mesh, INDEX_NONE, Snapshot, Prepared, Floor)) return false;
    TestTrue(TEXT("Actual simple collision stays simple"), !Snapshot.SimpleShapes.IsEmpty() && Snapshot.MeshShapes.IsEmpty());
    TestTrue(TEXT("Ordinary simple-and-complex query triangles remain excluded from simulation"), !Snapshot.NonSimulationShapes.IsEmpty());
    FProphecyJoltBodyState State;
    if (!Okay(*this, TEXT("Read imported static state"), Owner->ReadBody(Floor, State))) return false;
    TestFalse(TEXT("Static import creates no dynamic body"), State.bDynamic || State.bActive);
    TestTrue(TEXT("Native body origin matches capture"), State.PositionCm.Equals(Snapshot.BodyOriginToWorld.GetLocation(), 0.002));
    UObject* Associated = nullptr;
    if (!Okay(*this, TEXT("Resolve original query component"), Owner->ResolveAssociatedObject(Floor, Associated))) return false;
    TestTrue(TEXT("Registry retains original component identity"), Associated == Mesh);
    FProphecyJoltRayHit Hit;
    if (!MatchingRay(*this, Fixture, *Owner, *Mesh, FVector(0, 0, 300), FVector(0, 0, -100), false, Hit)) return false;
    FProphecyJoltFixtureBodySettings Ball; Ball.PositionCm = FVector(0, 0, 120);
    FProphecyJoltBodyHandle BallHandle;
    if (!Okay(*this, TEXT("Create a dynamic counterpart in the same world"), Owner->CreateSphere(10.0, Ball, BallHandle))) return false;
    for (int32 Frame = 0; Frame < 180; ++Frame)
        if (!Okay(*this, TEXT("One shared solver step"), Owner->Step(1.0f / 120.0f, 1))) return false;
    if (!Okay(*this, TEXT("Read contact-supported sphere"), Owner->ReadBody(BallHandle, State))) return false;
    TestTrue(TEXT("Actual imported floor supports dynamic contact"), State.PositionCm.Z > 6.5 && State.PositionCm.Z < 11.0);
    auto Mismatch = Snapshot; Mismatch.CaptureId = FGuid::NewGuid();
    TArray<FString> Notes = {TEXT("sentinel")};
    FProphecyJoltBodyHandle Rejected = Floor;
    TestEqual(TEXT("Static creation rejects mismatched preparation"), Owner->CreateStaticBody(Mismatch, Prepared, Rejected, Notes).Code, EProphecyJoltWorldResult::InvalidArgument);
    TestFalse(TEXT("Failed static creation clears the output handle"), Rejected.IsSet());
    TestEqual(TEXT("Failed static creation clears the notes"), Notes.Num(), 0);
    TestEqual(TEXT("A static body cannot accept velocity writes"), Owner->SetBodyVelocity(Floor, FVector(1, 0, 0), FVector::ZeroVector, true).Code, EProphecyJoltWorldResult::InvalidArgument);
    if (!Okay(*this, TEXT("Retire imported static body"), Owner->DestroyBody(Floor))) return false;
    TestFalse(TEXT("Static removal invalidates native generation"), Owner->OwnsBody(Floor));
    TestTrue(TEXT("Static import/removal retains original UE collision"), Mesh->IsPhysicsStateCreated()
        && Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics && !Mesh->IsSimulatingPhysics());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStaticComplexTest,
    "Prophecy.Jolt.StaticBody.ActualComplexMeshSignedScale", ProphecyJolt::StaticBodyTests::Flags)

bool FProphecyJoltStaticComplexTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StaticBodyTests;
    FWorldFixture Fixture;
    auto* Owner = Start(*this, Fixture);
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!Owner || !TestNotNull(TEXT("Cooked mesh source"), Cube)) return false;
    // Instantiate the ordinary source to finish its normal native mesh loading, then give a
    // transient duplicate only the complex-as-simple policy. No source asset is edited or saved.
    if (!TestNotNull(TEXT("Native source collision load"), AddMesh(Fixture, *Cube, FTransform(FVector(0, 2000, 0))))) return false;
    UBodySetup* SourceSetup = Cube->GetBodySetup();
    if (!TestTrue(TEXT("Actual cooked triangles are available"), SourceSetup && !SourceSetup->TriMeshGeometries.IsEmpty())) return false;
    const auto OriginalPolicy = SourceSetup->CollisionTraceFlag;
    auto* ComplexAsset = DuplicateObject<UStaticMesh>(Cube, GetTransientPackage(),
        MakeUniqueObjectName(GetTransientPackage(), UStaticMesh::StaticClass(), TEXT("JoltStaticComplexFixture")));
    if (!TestNotNull(TEXT("Transient complex asset copy"), ComplexAsset)) return false;
    auto* ComplexSetup = DuplicateObject<UBodySetup>(SourceSetup, ComplexAsset,
        MakeUniqueObjectName(ComplexAsset, UBodySetup::StaticClass(), TEXT("JoltStaticComplexSetup")));
    if (!TestNotNull(TEXT("Transient complex body setup"), ComplexSetup)) return false;
    ComplexSetup->SetFlags(RF_Transient);
    ComplexSetup->CollisionTraceFlag = CTF_UseComplexAsSimple;
    ComplexSetup->TriMeshGeometries = SourceSetup->TriMeshGeometries;
    ComplexSetup->bCreatedPhysicsMeshes = true;
    ComplexAsset->SetBodySetup(ComplexSetup); ComplexAsset->SetFlags(RF_Transient);
    auto* Mesh = AddMesh(Fixture, *ComplexAsset, FTransform(FRotator(0, 17, 0), FVector(1000, 0, 0), FVector(-2, 1.5, 0.5)));
    if (!TestNotNull(TEXT("Actual mirrored complex-as-simple component"), Mesh)) return false;
    FProphecyJoltStaticBodySnapshot Snapshot;
    FProphecyJoltPreparedStaticBody Prepared;
    FProphecyJoltBodyHandle Handle;
    if (!Import(*this, *Owner, *Mesh, INDEX_NONE, Snapshot, Prepared, Handle)) return false;
    if (!TestTrue(TEXT("Complex-as-simple imports cooked mesh, not simple/render substitutes"), Snapshot.SimpleShapes.IsEmpty() && !Snapshot.MeshShapes.IsEmpty())) return false;
    TestTrue(TEXT("Native scale wrapper parity is recorded"), Snapshot.MeshShapes.ContainsByPredicate(
        [](const auto& Shape) { return Shape.bReversedWindingForNegativeScale; }));
    FProphecyJoltRayHit Hit;
    if (!MatchingRay(*this, Fixture, *Owner, *Mesh, FVector(1000, 0, 200), FVector(1000, 0, -200), true, Hit)) return false;
    JPH::SubShapeID Id; Id.SetValue(Hit.NativeSubShapeId);
    JPH::SubShapeID Remainder;
    const JPH::Shape* Leaf = Prepared.GetNativeShape()->GetLeafShape(Id, Remainder);
    if (!TestTrue(TEXT("Native hit resolves a real mesh leaf"), Leaf && Leaf->GetSubType() == JPH::EShapeSubType::Mesh)) return false;
    const auto* LeafMesh = static_cast<const JPH::MeshShape*>(Leaf);
    const int32 NativeIndex = int32(Leaf->GetUserData() - 1);
    const auto* Source = Snapshot.MeshShapes.FindByPredicate([NativeIndex](const auto& Shape) { return Shape.NativeShapeIndex == NativeIndex; });
    const uint32 Triangle = LeafMesh->GetTriangleUserData(Remainder);
    TestTrue(TEXT("Jolt reordered triangles preserve capture-local triangle metadata"), Source && Source->Triangles.IsValidIndex(int32(Triangle))
        && Source->ExternalFaceIndices.IsValidIndex(int32(Triangle)) && Source->MaterialIndices.IsValidIndex(int32(Triangle)));
    FProphecyJoltFixtureBodySettings Ball;
    Ball.PositionCm = FVector(1000, 0, 120);
    FProphecyJoltBodyHandle BallHandle;
    if (!Okay(*this, TEXT("Create dynamic counterpart above reflected complex surface"), Owner->CreateSphere(10.0, Ball, BallHandle))) return false;
    for (int32 Frame = 0; Frame < 180; ++Frame)
        if (!Okay(*this, TEXT("Advance real single-sided complex contacts"), Owner->Step(1.0f / 120.0f, 1))) return false;
    FProphecyJoltBodyState Landed;
    if (!Okay(*this, TEXT("Read complex-supported dynamic body"), Owner->ReadBody(BallHandle, Landed))) return false;
    TestTrue(TEXT("Reflected cooked front faces support dynamic collision"), Landed.PositionCm.Z > 31.5 && Landed.PositionCm.Z < 36.0);
    TestTrue(TEXT("Original collision asset policy is unchanged"), SourceSetup->CollisionTraceFlag == OriginalPolicy);
    return Okay(*this, TEXT("Destroy complex static body"), Owner->DestroyBody(Handle));
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStaticInstanceTest,
    "Prophecy.Jolt.StaticBody.ActualISMInstancesAndRefusals", ProphecyJolt::StaticBodyTests::Flags)

bool FProphecyJoltStaticInstanceTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::StaticBodyTests;
    FWorldFixture Fixture;
    auto* Owner = Start(*this, Fixture);
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    auto* Actor = Fixture.SpawnActor();
    if (!Owner || !TestNotNull(TEXT("ISM source asset"), Cube) || !TestNotNull(TEXT("ISM owner actor"), Actor)) return false;
    auto* ISM = NewObject<UInstancedStaticMeshComponent>(Actor, NAME_None, RF_Transient);
    Actor->AddInstanceComponent(ISM); Actor->SetRootComponent(ISM);
    ISM->SetStaticMesh(Cube); ISM->SetMobility(EComponentMobility::Static);
    ISM->SetWorldTransform(FTransform(FRotator(0, 19, 0), FVector(700, 500, 0)));
    ISM->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    ISM->SetCollisionObjectType(ECC_WorldStatic); ISM->SetCollisionResponseToAllChannels(ECR_Block);
    ISM->AddInstance(FTransform(FRotator(0, 11, 0), FVector(0, 0, 0), FVector(0.8, 1.2, 1.4)));
    ISM->AddInstance(FTransform(FRotator(0, -9, 0), FVector(400, 0, 100), FVector(1.3, 0.7, 0.6)));
    auto* Material = NewObject<UPhysicalMaterial>(ISM, NAME_None, RF_Transient);
    Material->bOverrideFrictionCombineMode = Material->bOverrideRestitutionCombineMode = true;
    Material->FrictionCombineMode = EFrictionCombineMode::Min;
    Material->RestitutionCombineMode = EFrictionCombineMode::Max;
    ISM->SetPhysMaterialOverride(Material);
    ISM->RegisterComponent();
    FProphecyJoltBodyHandle Handles[2];
    for (int32 Index = 0; Index < 2; ++Index)
    {
        Material->bOverrideFrictionCombineMode = Material->bOverrideRestitutionCombineMode = Index == 0;
        FProphecyJoltStaticBodySnapshot Snapshot;
        FProphecyJoltPreparedStaticBody Prepared;
        if (!Import(*this, *Owner, *ISM, Index, Snapshot, Prepared, Handles[Index])) return false;
        TestEqual(TEXT("ISM material friction mode resolves override or project default"), Snapshot.EffectiveFrictionCombineMode,
            uint8(Index == 0 ? EFrictionCombineMode::Min : UPhysicsSettings::Get()->FrictionCombineMode.GetValue()));
        TestEqual(TEXT("ISM material restitution mode resolves override or project default independently"), Snapshot.EffectiveRestitutionCombineMode,
            uint8(Index == 0 ? EFrictionCombineMode::Max : UPhysicsSettings::Get()->RestitutionCombineMode.GetValue()));
        TestTrue(TEXT("Instance capture keeps original component and capture-time instance identity"), Snapshot.SourceComponent.Get() == ISM && Snapshot.InstanceIndex == Index);
        FProphecyJoltRayHit Hit;
        const FVector Center = Snapshot.InstanceToWorld.GetLocation();
        if (!MatchingRay(*this, Fixture, *Owner, *ISM, Center + FVector(0, 0, 200), Center - FVector(0, 0, 200), false, Hit)) return false;
        TestTrue(TEXT("Each instance ray resolves its own native registry body"), Hit.Handle.Slot == Handles[Index].Slot && Hit.Handle.Generation == Handles[Index].Generation);
    }
    FProphecyJoltStaticBodySnapshot Rejected;
    FString Error;
    TestFalse(TEXT("ISM base BodyInstance is not substituted for an unspecified instance"), ProphecyJolt::StaticBody::CaptureStaticBody(*ISM, INDEX_NONE, Rejected, Error));
    TestFalse(TEXT("Out-of-range instance fails explicitly"), ProphecyJolt::StaticBody::CaptureStaticBody(*ISM, 2, Rejected, Error));
    if (!Okay(*this, TEXT("Retire one instance collider"), Owner->DestroyBody(Handles[0]))) return false;
    TestTrue(TEXT("Independent neighbor ownership remains live"), Owner->OwnsBody(Handles[1]));
    TestEqual(TEXT("Original ISM instances are never removed by native cleanup"), ISM->GetInstanceCount(), 2);
    auto* Moving = AddMesh(Fixture, *Cube, FTransform(FVector(0, 2000, 0)));
    if (!TestNotNull(TEXT("Moving refusal fixture"), Moving)) return false;
    Moving->SetMobility(EComponentMobility::Movable);
    TestFalse(TEXT("Movable native source is rejected"), ProphecyJolt::StaticBody::CaptureStaticBody(*Moving, INDEX_NONE, Rejected, Error));
    Moving->SetMobility(EComponentMobility::Static); Moving->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    TestFalse(TEXT("Query-only component cannot become static simulation collision"), ProphecyJolt::StaticBody::CaptureStaticBody(*Moving, INDEX_NONE, Rejected, Error));
    return Okay(*this, TEXT("Retire final instance collider"), Owner->DestroyBody(Handles[1]));
}

#endif
