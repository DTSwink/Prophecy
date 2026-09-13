#include "ProphecyJoltSceneCollisionComponent.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyJoltBlueprintLibrary.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/EngineBaseTypes.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "PhysicsEngine/PhysicsSettings.h"

namespace ProphecyJolt::SceneCollisionTests
{
struct FWorldFixture
{
    UWorld* World = nullptr;
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
        return World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn);
    }
};

bool SameBody(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

UStaticMeshComponent* AddMesh(FWorldFixture& Fixture, UStaticMesh& Asset, const FTransform& Transform, bool bDynamic)
{
    auto* Actor = Fixture.SpawnActor();
    if (!Actor) return nullptr;
    auto* Mesh = NewObject<UStaticMeshComponent>(Actor, NAME_None, RF_Transient);
    Actor->AddInstanceComponent(Mesh); Actor->SetRootComponent(Mesh);
    Mesh->SetStaticMesh(&Asset);
    Mesh->SetMobility(bDynamic ? EComponentMobility::Movable : EComponentMobility::Static);
    Mesh->SetWorldTransform(Transform);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->SetCollisionObjectType(bDynamic ? ECC_PhysicsBody : ECC_WorldStatic);
    Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetGenerateOverlapEvents(false);
    Mesh->SetEnableGravity(false);
    if (bDynamic) Mesh->SetMassOverrideInKg(NAME_None, 2.0f, true);
    Mesh->RegisterComponent();
    if (bDynamic) Mesh->SetSimulatePhysics(true);
    return Mesh;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSceneCollisionPromotionTest,
    "Prophecy.Jolt.SceneCollision.ISMPromotionAndCleanup",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltSceneCollisionPromotionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SceneCollisionTests;
    if (!TestFalse(TEXT("Fixture uses supported synchronous Chaos"), UPhysicsSettings::Get()->bTickPhysicsAsync)) return false;
    FWorldFixture Fixture;
    if (!TestNotNull(TEXT("Transient game world"), Fixture.World)) return false;
    Fixture.World->InitializeActorsForPlay(FURL());
    auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!TestNotNull(TEXT("Native world owner"), Owner) || !TestNotNull(TEXT("Shared coordinator"), Coordinator)
        || !TestNotNull(TEXT("Real native collision asset"), Cube)) return false;
    FString Error;
    if (!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(Fixture.World, Error, 16, 0))
    { AddError(Error); return false; }
    TestTrue(TEXT("Blueprint startup exposes the initialized gameplay world"),
        UProphecyJoltBlueprintLibrary::IsJoltWorldReady(Fixture.World));

    auto* Floor = AddMesh(Fixture, *Cube, FTransform(FRotator::ZeroRotator, FVector(0, 0, -10), FVector(10, 10, 0.2)), false);
    auto* InstanceActor = Fixture.SpawnActor();
    auto* SceneActor = Fixture.SpawnActor();
    if (!TestNotNull(TEXT("Actual static floor"), Floor) || !TestNotNull(TEXT("Instance actor"), InstanceActor)
        || !TestNotNull(TEXT("Scene collision actor"), SceneActor)) return false;
    auto* ISM = NewObject<UInstancedStaticMeshComponent>(InstanceActor, NAME_None, RF_Transient);
    InstanceActor->AddInstanceComponent(ISM); InstanceActor->SetRootComponent(ISM);
    ISM->SetStaticMesh(Cube); ISM->SetMobility(EComponentMobility::Static);
    ISM->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    ISM->SetCollisionObjectType(ECC_WorldStatic); ISM->SetCollisionResponseToAllChannels(ECR_Block);
    ISM->SetGenerateOverlapEvents(false);
    const FTransform PromotedTransform(FRotator(0, 23, 0), FVector(1000, 0, 200), FVector(1.0, 0.8, 1.2));
    const FTransform NeighborTransform(FRotator(0, -31, 0), FVector(1000, 400, 200), FVector(0.8, 1.2, 1.0));
    ISM->AddInstance(PromotedTransform, true); ISM->AddInstance(NeighborTransform, true);
    ISM->RegisterComponent();
    auto* Scene = NewObject<UProphecyJoltSceneCollisionComponent>(SceneActor, NAME_None, RF_Transient);
    SceneActor->AddInstanceComponent(Scene); Scene->RegisterComponent(); SceneActor->DispatchBeginPlay();
    if (!Scene->EnableSceneCollision(Error)) { AddError(Error); return false; }
    TestFalse(TEXT("Admission outside a world tick is immediate"), Scene->IsEnablePending());
    TestFalse(TEXT("Static scene ownership does not request independent steps"), Coordinator->HasAutomaticStepOwners());
    TestEqual(TEXT("Loaded scene contains one floor and two native instances"), Scene->GetImportedBodyCount(), 3);
    FProphecyJoltBodyHandle FloorHandle, Retired, Neighbor;
    if (!TestTrue(TEXT("Floor is imported"), Scene->GetBodyHandle(*Floor, INDEX_NONE, FloorHandle))
        || !TestTrue(TEXT("First instance is imported"), Scene->GetBodyHandle(*ISM, 0, Retired))
        || !TestTrue(TEXT("Neighbor instance is imported"), Scene->GetBodyHandle(*ISM, 1, Neighbor))) return false;

    // The passive scene owner registers first; the later dynamic owner drives their shared step.
    auto* DynamicMesh = AddMesh(Fixture, *Cube, FTransform(FVector(3000, 0, 300)), true);
    if (!TestNotNull(TEXT("Actual dynamic prop source"), DynamicMesh)) return false;
    auto* Body = NewObject<UProphecyJoltBodyComponent>(DynamicMesh->GetOwner(), NAME_None, RF_Transient);
    DynamicMesh->GetOwner()->AddInstanceComponent(Body); Body->bAutomaticStep = false; Body->RegisterComponent();
    DynamicMesh->GetOwner()->DispatchBeginPlay();
    if (!Body->EnableBody(*DynamicMesh, Error)) { AddError(Error); return false; }
    FProphecyJoltBodyHandle DynamicHandle;
    if (!Body->GetBodyHandle(DynamicHandle)) return false;
    FProphecyJoltWorldDiagnostics Before;
    if (!Owner->GetDiagnostics(Before).IsSuccess()) return false;
    TestEqual(TEXT("Static and dynamic owners share four native bodies"), Before.BodyCount, uint32(4));

    FTransform ZeroScale = PromotedTransform; ZeroScale.SetScale3D(FVector::ZeroVector);
    if (!TestTrue(TEXT("Blood-style instance removal updates actual UE physics"), ISM->UpdateInstanceTransform(0, ZeroScale, true, true, true))) return false;
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    auto* PromotedActor = Fixture.World->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), PromotedTransform, Spawn);
    if (!TestNotNull(TEXT("Actual promoted StaticMeshActor"), PromotedActor)) return false;
    auto* Promoted = PromotedActor->GetStaticMeshComponent();
    Promoted->SetMobility(EComponentMobility::Movable);
    Promoted->SetStaticMesh(Cube); Promoted->SetWorldTransform(PromotedTransform);
    Promoted->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Promoted->SetCollisionObjectType(ECC_WorldStatic); Promoted->SetCollisionResponseToAllChannels(ECR_Block);
    Promoted->SetMobility(EComponentMobility::Static);
    if (!Body->StepAndPublish(1.0f / 60.0f, Error)) { AddError(Error); return false; }
    FProphecyJoltWorldDiagnostics After;
    if (!Owner->GetDiagnostics(After).IsSuccess()) return false;
    TestEqual(TEXT("Promotion is reconciled in exactly one shared native step"), After.CompletedSteps, Before.CompletedSteps + 1);
    TestEqual(TEXT("Replacement retains the native body count"), After.BodyCount, uint32(4));
    TestEqual(TEXT("Scene still owns floor, neighbor and promoted receiver"), Scene->GetImportedBodyCount(), 3);
    FProphecyJoltBodyHandle Absent, CurrentNeighbor, Replacement;
    TestFalse(TEXT("Zero-scale original has no native ownership"), Owner->OwnsBody(Retired) || Scene->GetBodyHandle(*ISM, 0, Absent));
    TestTrue(TEXT("Unchanged neighbor retains its exact generation"), Scene->GetBodyHandle(*ISM, 1, CurrentNeighbor)
        && SameBody(CurrentNeighbor, Neighbor) && Owner->OwnsBody(Neighbor));
    if (!TestTrue(TEXT("Spawned final static receiver is imported before the step"), Scene->GetBodyHandle(*Promoted, INDEX_NONE, Replacement))) return false;
    const FVector Center = PromotedTransform.GetLocation();
    FProphecyJoltRayHit NativeHit; bool bNativeHit = false;
    if (!Owner->RayCast(Center + FVector(0, 0, 200), Center - FVector(0, 0, 200), NativeHit, bNativeHit).IsSuccess()) return false;
    TestTrue(TEXT("Native ray hits replacement, not a ghost of the old instance"), bNativeHit && SameBody(NativeHit.Handle, Replacement));
    FHitResult UEHit;
    TestTrue(TEXT("UE trace retains promoted blood receiver identity"), Fixture.World->LineTraceSingleByChannel(
        UEHit, Center + FVector(0, 0, 200), Center - FVector(0, 0, 200), ECC_Visibility) && UEHit.GetComponent() == Promoted);

    if (!TestTrue(TEXT("Actual instance removal reindexes the survivor"), ISM->RemoveInstance(0))) return false;
    if (!Body->StepAndPublish(1.0f / 60.0f, Error)) { AddError(Error); return false; }
    FProphecyJoltBodyHandle Reindexed;
    TestFalse(TEXT("A reindex invalidates the old index generation"), Owner->OwnsBody(Neighbor));
    TestTrue(TEXT("Survivor has current index provenance and fresh ownership"), Scene->GetBodyHandle(*ISM, 0, Reindexed)
        && !SameBody(Reindexed, Neighbor) && Owner->OwnsBody(Reindexed));
    TestFalse(TEXT("Removed index has no lingering binding"), Scene->GetBodyHandle(*ISM, 1, Absent));

    Scene->DisableSceneCollision(); Scene->DisableSceneCollision();
    TestFalse(TEXT("Scene cleanup retires all three current static handles"), Owner->OwnsBody(FloorHandle)
        || Owner->OwnsBody(Replacement) || Owner->OwnsBody(Reindexed));
    TestTrue(TEXT("Scene cleanup leaves the dynamic owner intact"), Owner->OwnsBody(DynamicHandle) && Body->IsJoltBody());
    TestEqual(TEXT("Scene cleanup removes only its coordinator registration"), Coordinator->GetRegisteredStepClientCount(), 1);
    TestTrue(TEXT("Original floor and promoted UE query bodies remain"), Floor->IsPhysicsStateCreated() && Promoted->IsPhysicsStateCreated()
        && Floor->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics && Promoted->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics);
    FTransform Remaining;
    TestTrue(TEXT("Cleanup preserves the remaining UE instance"), ISM->GetInstanceCount() == 1
        && ISM->GetInstanceTransform(0, Remaining, true) && Remaining.Equals(NeighborTransform, 1.0e-4));
    Body->DisableBody();
    if (!Owner->GetDiagnostics(After).IsSuccess()) return false;
    TestEqual(TEXT("Final owner cleanup leaves no native bodies"), After.BodyCount, uint32(0));
    TestEqual(TEXT("Cleanup adds no native step"), After.CompletedSteps, Before.CompletedSteps + 2);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltDefaultWorldFirstStepTest,
    "Prophecy.Jolt.SceneCollision.DefaultWorldFirstStep",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltDefaultWorldFirstStepTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SceneCollisionTests;
    FWorldFixture Fixture;
    if (!TestNotNull(TEXT("Default startup world"), Fixture.World)) return false;
    FString Error;
    if (!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(Fixture.World, Error))
    { AddError(Error); return false; }
    auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldDiagnostics D;
    if (!TestTrue(TEXT("Default startup diagnostics"), Owner && Owner->GetDiagnostics(D).IsSuccess())) return false;
    TestEqual(TEXT("Exercise the actual Blueprint body-capacity default"), D.Settings.MaxBodies, uint32(16384));
    FProphecyJoltFixtureBodySettings Floor, Falling;
    Floor.bDynamic = false;
    Floor.PositionCm = FVector(0, 0, -10);
    Falling.PositionCm = FVector(0, 0, 100);
    FProphecyJoltBodyHandle FloorHandle, FallingHandle;
    if (!TestTrue(TEXT("Static contact surface"), Owner->CreateBox(FVector(200, 200, 10), 0, Floor, FloorHandle).IsSuccess())
        || !TestTrue(TEXT("Active body triggers full scratch reservation"), Owner->CreateSphere(20, Falling, FallingHandle).IsSuccess())) return false;
    for (int32 Frame = 0; Frame < 120; ++Frame)
    {
        const auto Step = Owner->Step(1.0f / 60.0f, 1);
        if (!Step.IsSuccess()) { AddError(Step.Message); return false; }
    }
    FProphecyJoltBodyState Body;
    if (!TestTrue(TEXT("Read completed default-world body"), Owner->ReadBody(FallingHandle, Body).IsSuccess())
        || !TestTrue(TEXT("Read post-step memory diagnostics"), Owner->GetDiagnostics(D).IsSuccess())) return false;
    TestTrue(TEXT("Body falls onto the floor under default gravity"), Body.PositionCm.Z > 15 && Body.PositionCm.Z < 25);
    TestFalse(TEXT("No native fault"), D.bFaulted);
    TestEqual(TEXT("All default-world steps completed"), D.CompletedSteps, uint64(120));
    TestTrue(TEXT("Workspace fits and is released after the update"), D.TempPeakBytes <= D.Settings.TempAllocatorBytes && D.TempCurrentBytes == 0);
    AddInfo(FString::Printf(TEXT("Default startup scratch: peak=%llu bytes, capacity=%u bytes."), D.TempPeakBytes, D.Settings.TempAllocatorBytes));
    TestTrue(TEXT("Falling body cleanup"), Owner->DestroyBody(FallingHandle).IsSuccess());
    TestTrue(TEXT("Floor cleanup"), Owner->DestroyBody(FloorHandle).IsSuccess());
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltSceneChannelsTest,
    "Prophecy.Jolt.SceneCollision.RuntimeChannels",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltSceneChannelsTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::SceneCollisionTests;
    FWorldFixture Fixture;
    Fixture.World->InitializeActorsForPlay(FURL());
    auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FString Error;
    if (!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(Fixture.World, Error, 32, 0)) { AddError(Error); return false; }
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    TArray<UPrimitiveComponent*> Sources;
    TArray<int32> InstanceIndices;
    Sources.Add(AddMesh(Fixture, *Cube, FTransform(FVector(0, 0, 0)), false));
    InstanceIndices.Add(INDEX_NONE);
    for (bool bHierarchical : { false, true })
    {
        auto* Actor = Fixture.SpawnActor();
        UInstancedStaticMeshComponent* Mesh = bHierarchical
            ? NewObject<UHierarchicalInstancedStaticMeshComponent>(Actor)
            : NewObject<UInstancedStaticMeshComponent>(Actor);
        Actor->AddInstanceComponent(Mesh); Actor->SetRootComponent(Mesh);
        Mesh->SetStaticMesh(Cube); Mesh->SetMobility(EComponentMobility::Static);
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetCollisionObjectType(ECC_WorldStatic); Mesh->SetCollisionResponseToAllChannels(ECR_Block);
        Mesh->SetGenerateOverlapEvents(false); Mesh->RegisterComponent();
        Mesh->AddInstance(FTransform(FVector(bHierarchical ? 1000 : 500, 0, 0)), false);
        Mesh->AddInstance(FTransform(FVector(bHierarchical ? 1000 : 500, 200, 0)), false);
        if (auto* HISM = Cast<UHierarchicalInstancedStaticMeshComponent>(Mesh)) HISM->BuildTreeIfOutdated(false, true);
        for (int32 Index = 0; Index < 2; ++Index) { Sources.Add(Mesh); InstanceIndices.Add(Index); }
    }
    auto* Actor = Fixture.SpawnActor();
    auto* Scene = NewObject<UProphecyJoltSceneCollisionComponent>(Actor);
    Actor->AddInstanceComponent(Scene); Scene->RegisterComponent(); Actor->DispatchBeginPlay();
    if (!Scene->EnableSceneCollision(Error)) { AddError(Error); return false; }
    TArray<FProphecyJoltBodyHandle> Original;
    for (int32 Index = 0; Index < Sources.Num(); ++Index)
    {
        FProphecyJoltBodyHandle Handle;
        if (!TestTrue(TEXT("Import actual static/ISM/HISM body"), Scene->GetBodyHandle(*Sources[Index], InstanceIndices[Index], Handle))) return false;
        Original.Add(Handle);
    }
    for (int32 Stage = 0; Stage < 4; ++Stage)
    {
        for (auto* Source : Sources)
        {
            if (Stage == 0) Source->SetCollisionResponseToAllChannels(ECR_Ignore);
            if (Stage == 1) Source->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
            if (Stage == 2) Source->SetCollisionObjectType(ECC_GameTraceChannel18);
            if (Stage == 3) Source->SetCollisionProfileName(TEXT("BlockAll"));
        }
        if (!Scene->PrepareJoltWorldStep(1.f / 60, false, Error)) { AddError(Error); return false; }
        for (int32 Index = 0; Index < Sources.Num(); ++Index)
        {
            FProphecyJoltBodyHandle Handle;
            if (!Scene->GetBodyHandle(*Sources[Index], InstanceIndices[Index], Handle)) return false;
            TestTrue(TEXT("Channel changes retain static/instance collider identity"), SameBody(Original[Index], Handle));
            FProphecyJoltCollisionUpdate Policy;
            if (!Owner->ReadBodyCollision(Handle, Policy).IsSuccess()) return false;
            TestEqual(TEXT("Static/instance object channel follows source"), int32(Policy.ObjectChannel), int32(Sources[Index]->GetCollisionObjectType()));
            TestEqual(TEXT("Static/instance block response follows source"), Policy.Responses.GetResponse(ECC_PhysicsBody) == ECR_Block, Stage != 0);
        }
    }
    Scene->DisableSceneCollision();
    return !HasAnyErrors();
}
#endif
