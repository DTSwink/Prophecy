#include "ProphecyJoltBodyComponent.h"
#include "ProphecyPhysicsStaticMeshComponent.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Physics/PhysicsFiltering.h"
#include "Misc/ScopeExit.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/EngineBaseTypes.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "Physics/PhysicsInterfaceCore.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"

namespace ProphecyJolt::BodyComponentTests
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
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBodyComponentHandoffTest,
    "Prophecy.Jolt.BodyComponent.SharedStepQueryAndCleanup",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltBodyComponentHandoffTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::BodyComponentTests;
    if (!TestFalse(TEXT("Fixture uses the supported synchronous Chaos scene"), UPhysicsSettings::Get()->bTickPhysicsAsync)) return false;
    FWorldFixture Fixture;
    if (!TestNotNull(TEXT("Transient game world"), Fixture.World)) return false;
    // DispatchBeginPlay alone does not initialize actors; RouteEndPlay requires both states.
    Fixture.World->InitializeActorsForPlay(FURL());
    if (!TestTrue(TEXT("Fixture initializes actors for the real EndPlay route"), Fixture.World->AreActorsInitialized())) return false;
    auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!TestNotNull(TEXT("Native world owner"), Owner) || !TestNotNull(TEXT("Shared step coordinator"), Coordinator)
        || !TestNotNull(TEXT("Real Cube collision asset"), Cube)) return false;
    FProphecyJoltWorldSettings Settings;
    Settings.MaxBodies = 8;
    Settings.MaxBodyPairs = 32;
    Settings.MaxContactConstraints = 32;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    const FProphecyJoltWorldStatus Initialized = Owner->InitializeSimulation(Settings);
    if (!Initialized.IsSuccess()) { AddError(Initialized.Message); return false; }

    AActor* Actors[2] = {};
    UStaticMeshComponent* Meshes[2] = {};
    UProphecyJoltBodyComponent* Bodies[2] = {};
    FTransform InitialVisual[2];
    FVector InitialCOM[2];
    FProphecyJoltBodyState InitialNative[2];
    FProphecyJoltBodyHandle Handles[2];
    uint64 Revisions[2] = {};
    FString Error;
    for (int32 Index = 0; Index < 2; ++Index)
    {
        FActorSpawnParameters Spawn;
        Spawn.ObjectFlags |= RF_Transient;
        Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        Actors[Index] = Fixture.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn);
        if (!TestNotNull(TEXT("Cube owner"), Actors[Index])) return false;
        if (!TestTrue(TEXT("Spawned actor completed initialization"), Actors[Index]->IsActorInitialized())) return false;
        Actors[Index]->SetActorTickEnabled(false);
        auto* Mesh = Meshes[Index] = NewObject<UProphecyPhysicsStaticMeshComponent>(Actors[Index], NAME_None, RF_Transient);
        Actors[Index]->AddInstanceComponent(Mesh);
        Actors[Index]->SetRootComponent(Mesh);
        Mesh->SetStaticMesh(Cube);
        Mesh->SetMobility(EComponentMobility::Movable);
        InitialVisual[Index] = FTransform(FRotator(17.0, 31.0, -8.0), FVector(0.0, Index * 500.0, 300.0), FVector(1.5, 0.75, 1.2));
        Mesh->SetWorldTransform(InitialVisual[Index]);
        Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
        Mesh->SetGenerateOverlapEvents(false);
        Mesh->SetEnableGravity(false);
        Mesh->SetLinearDamping(0.0f);
        Mesh->SetAngularDamping(0.0f);
        Mesh->SetMassOverrideInKg(NAME_None, 2.0f, true);
        Mesh->RegisterComponent();
        Mesh->SetSimulatePhysics(true);
        Mesh->SetCenterOfMass(FVector(13.0, -7.0, 9.0));
        if (!TestTrue(TEXT("Fixture starts as an actual Chaos dynamic body"), Mesh->IsSimulatingPhysics())) return false;
        InitialCOM[Index] = Mesh->GetCenterOfMass();
        TestTrue(TEXT("COM offset makes origin-versus-COM publication observable"),
            FVector::Distance(InitialCOM[Index], Mesh->GetComponentLocation()) > 5.0);
        auto* Body = Bodies[Index] = NewObject<UProphecyJoltBodyComponent>(Actors[Index], NAME_None, RF_Transient);
        Actors[Index]->AddInstanceComponent(Body);
        Body->bAutomaticStep = false;
        Body->RegisterComponent();
        Actors[Index]->DispatchBeginPlay();
        if (!TestTrue(TEXT("Body component entered play through its actor"), Body->HasBegunPlay())) return false;
        if (!Body->EnableBody(*Mesh, Error)) { AddError(Error); return false; }
        if (!TestTrue(TEXT("Immediate handoff owns a native body"), Body->IsJoltBody())
            || !TestTrue(TEXT("Native handle available"), Body->GetBodyHandle(Handles[Index]))
            || !TestTrue(TEXT("Initial native state available"), Body->GetBodyState(InitialNative[Index]))) return false;
        TestFalse(TEXT("Admission outside a world tick is not pending"), Body->IsEnablePending());
        TestTrue(TEXT("Original root, mesh asset and receiver are retained"), Actors[Index]->GetRootComponent() == Mesh
            && Mesh->GetStaticMesh() == Cube && Body->GetSourceComponent() == Mesh && Body->GetWorldOwner() == Owner);
        TestTrue(TEXT("Handoff retains full visual transform including nonuniform scale"),
            Mesh->GetComponentTransform().Equals(InitialVisual[Index], 1.0e-4));
        TestNearlyEqual(TEXT("Native COM retains the original Chaos mass offset"), InitialNative[Index].CenterOfMassPositionCm, InitialCOM[Index], 1.0e-3f);
        TestTrue(TEXT("Jolt is dynamic"), InitialNative[Index].bDynamic);
        TestFalse(TEXT("Original component has no Chaos simulation"), Mesh->IsAnySimulatingPhysics());
        TestTrue(TEXT("Original receiver is QueryOnly"), Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryOnly);
        FBodyInstance* Query = Mesh->GetBodyInstance();
        if (!TestTrue(TEXT("Actual Chaos query actor is kinematic"), Query && Query->GetPhysicsActor()
            && FPhysicsInterface::IsKinematic(Query->GetPhysicsActor()))) return false;
        Revisions[Index] = Body->GetRevision();
        const FVector BeforeImpulse = InitialNative[Index].CenterOfMassVelocityCmPerSecond;
        Mesh->AddImpulse(FVector(10,-5,3),NAME_None,true);
        FProphecyJoltBodyState Commanded;
        if (!Body->GetBodyState(Commanded)) return false;
        TestTrue(TEXT("Standard static-mesh impulse reaches Jolt with Vel Change"),Commanded.CenterOfMassVelocityCmPerSecond.Equals(BeforeImpulse+FVector(10,-5,3),0.002));
        Mesh->SetPhysicsLinearVelocity(FVector(4,5,6),false,NAME_None);
        if (!Body->GetBodyState(Commanded)) return false;
        TestTrue(TEXT("Standard static-mesh velocity setter reaches Jolt"),Commanded.CenterOfMassVelocityCmPerSecond.Equals(FVector(4,5,6),0.002));
        if (!Body->SetBodyVelocity(FVector(6000.0, 0.0, 0.0), FVector(0.0, 0.0, 2.0), true, Error))
        { AddError(Error); return false; }
    }
    TestEqual(TEXT("Both bodies register with the same coordinator"), Coordinator->GetRegisteredStepClientCount(), 2);
    TestFalse(TEXT("Explicit clients do not request automatic steps"), Coordinator->HasAutomaticStepOwners());
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Owner->GetDiagnostics(Diagnostics).IsSuccess()) return false;
    TestEqual(TEXT("Handoff creates exactly two native bodies"), Diagnostics.BodyCount, uint32(2));
    const uint64 StepsBefore = Diagnostics.CompletedSteps;
    constexpr float DeltaSeconds = 1.0f / 30.0f;
    if (!Bodies[0]->StepAndPublish(DeltaSeconds, Error)) { AddError(Error); return false; }
    if (!Owner->GetDiagnostics(Diagnostics).IsSuccess()) return false;
    TestEqual(TEXT("One client request advances the shared world exactly once"), Diagnostics.CompletedSteps, StepsBefore + 1);
    for (int32 Index = 0; Index < 2; ++Index)
    {
        auto* Mesh = Meshes[Index];
        auto* Body = Bodies[Index];
        FProphecyJoltBodyState Completed;
        if (!TestTrue(TEXT("Completed body state available"), Body->GetBodyState(Completed))) return false;
        TestEqual(TEXT("Both clients publish exactly once for the shared step"), Body->GetRevision(), Revisions[Index] + 1);
        TestNearlyEqual(TEXT("Each COM advances from its captured position at the requested velocity"),
            Completed.CenterOfMassPositionCm, InitialCOM[Index] + FVector(6000.0 * DeltaSeconds, 0.0, 0.0), 0.02f);
        const FVector LocalCOM = InitialNative[Index].Rotation.UnrotateVector(InitialCOM[Index] - InitialNative[Index].PositionCm);
        TestNearlyEqual(TEXT("Rotating offset COM remains distinct from the published body origin"),
            Completed.PositionCm + Completed.Rotation.RotateVector(LocalCOM), Completed.CenterOfMassPositionCm, 0.02f);
        TestFalse(TEXT("Angular velocity produces a new orientation"), Completed.Rotation.Equals(InitialNative[Index].Rotation, 1.0e-4));
        FTransform OriginToComponent;
        if (!TestTrue(TEXT("Captured origin mapping remains available"), Body->GetBodyOriginToComponent(OriginToComponent))) return false;
        FTransform ExpectedVisual = OriginToComponent.Inverse() * FTransform(Completed.Rotation, Completed.PositionCm);
        ExpectedVisual.SetScale3D(InitialVisual[Index].GetScale3D());
        TestTrue(TEXT("Completed visual frame retains scale and the body-origin mapping"), Mesh->GetComponentTransform().Equals(ExpectedVisual, 1.0e-4));
        TestFalse(TEXT("Publishing never reactivates Chaos"), Mesh->IsAnySimulatingPhysics());
        const FVector Center = Mesh->GetComponentLocation();
        const FVector RayOffset(0.0, 0.0, 200.0);
        FHitResult Hit;
        if (!TestTrue(TEXT("Immediate UE trace finds the moved query receiver"), Fixture.World->LineTraceSingleByChannel(
            Hit, Center + RayOffset, Center - RayOffset, ECC_Visibility))) return false;
        TestTrue(TEXT("UE hit retains the original actor/component identity"), Hit.GetActor() == Actors[Index] && Hit.GetComponent() == Mesh);
        FHitResult OldHit;
        TestFalse(TEXT("Immediate query tree no longer contains the old pose"), Fixture.World->LineTraceSingleByChannel(
            OldHit, InitialVisual[Index].GetLocation() + RayOffset, InitialVisual[Index].GetLocation() - RayOffset, ECC_Visibility));
        FProphecyJoltRayHit NativeHit;
        bool bNativeHit = false;
        if (!Owner->RayCast(Center + RayOffset, Center - RayOffset, NativeHit, bNativeHit).IsSuccess()) return false;
        FHitResult ConvertedHit;
        TestTrue(TEXT("Native hit maps to the same original receiver without inventing a triangle"), bNativeHit
            && Body->MakeHitResult(NativeHit, ConvertedHit) && ConvertedHit.GetActor() == Actors[Index]
            && ConvertedHit.GetComponent() == Mesh && ConvertedHit.FaceIndex == INDEX_NONE);
    }

    FTransform LastVisual = Meshes[0]->GetComponentTransform();
    // Gameplay may release ownership from a transform callback while completed poses are publishing.
    // The shared step must still publish the other body and restore this receiver after the callback.
    bool bRemovedDuringPublication = false;
    const FDelegateHandle Removal = Meshes[0]->TransformUpdated.AddLambda(
        [&](USceneComponent*, EUpdateTransformFlags, ETeleportType)
        {
            if (bRemovedDuringPublication) return;
            bRemovedDuringPublication = true;
            LastVisual = Meshes[0]->GetComponentTransform();
            Bodies[0]->DisableBody();
            TestTrue(TEXT("Receiver restoration waits for publication to unwind"), Bodies[0]->IsReceiverRestorePending());
            TestFalse(TEXT("Callback removal retires native ownership immediately"), Owner->OwnsBody(Handles[0]));
        });
    const bool bStepAfterRemoval = Bodies[1]->StepAndPublish(DeltaSeconds, Error);
    Meshes[0]->TransformUpdated.Remove(Removal);
    if (!bStepAfterRemoval) { AddError(Error); return false; }
    TestTrue(TEXT("Live publication reached the removal callback"), bRemovedDuringPublication);
    TestFalse(TEXT("Receiver restoration completes before the shared step returns"), Bodies[0]->IsReceiverRestorePending());
    TestEqual(TEXT("Other body still consumes the shared step"), Bodies[1]->GetRevision(), Revisions[1] + 2);
    TestFalse(TEXT("Explicit disable retires native ownership"), Bodies[0]->IsJoltBody() || Owner->OwnsBody(Handles[0]));
    TestEqual(TEXT("Disable retires only its registration"), Coordinator->GetRegisteredStepClientCount(), 1);
    TestTrue(TEXT("Disable restores the original collision mode"), Meshes[0]->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics);
    TestFalse(TEXT("Disable does not revive Chaos simulation"), Meshes[0]->IsAnySimulatingPhysics());
    TestTrue(TEXT("Disable preserves the last completed visual pose"), Meshes[0]->GetComponentTransform().Equals(LastVisual, 1.0e-4));
    TestFalse(TEXT("Retired body cannot request another step"), Bodies[0]->StepAndPublish(DeltaSeconds, Error));
    Actors[1]->RouteEndPlay(EEndPlayReason::RemovedFromWorld);
    TestFalse(TEXT("Routed EndPlay reaches actor and component lifecycle"), Actors[1]->HasActorBegunPlay() || Bodies[1]->HasBegunPlay());
    TestFalse(TEXT("Routed EndPlay retires the other body"), Bodies[1]->IsJoltBody() || Owner->OwnsBody(Handles[1]));
    TestEqual(TEXT("EndPlay retires the final shared registration"), Coordinator->GetRegisteredStepClientCount(), 0);
    TestFalse(TEXT("EndPlay does not revive Chaos simulation"), Meshes[1]->IsAnySimulatingPhysics());
    TestTrue(TEXT("EndPlay restores original collision mode"), Meshes[1]->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics);
    Bodies[0]->DisableBody();
    if (!Owner->GetDiagnostics(Diagnostics).IsSuccess()) return false;
    TestEqual(TEXT("Both native bodies are destroyed; repeated disable is harmless"), Diagnostics.BodyCount, uint32(0));
    TestEqual(TEXT("Cleanup never adds a native step"), Diagnostics.CompletedSteps, StepsBefore + 2);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBodyComponentTransformPublicationTest,
    "Prophecy.Jolt.BodyComponent.TinyPoseAndCallbackMutation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltBodyComponentTransformPublicationTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::BodyComponentTests;
    if (!TestFalse(TEXT("Fixture uses synchronous Chaos"), UPhysicsSettings::Get()->bTickPhysicsAsync)) return false;
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!TestNotNull(TEXT("Real Cube collision asset"), Cube)) return false;
    constexpr float DeltaSeconds = 1.0f / 30.0f;
    // Fresh worlds isolate the two deliberately faulted publications from the tiny-motion case.
    for (int32 Scenario = 0; Scenario < 3; ++Scenario)
    {
        FWorldFixture Fixture;
        if (!TestNotNull(TEXT("Transient publication world"), Fixture.World)) return false;
        Fixture.World->InitializeActorsForPlay(FURL());
        auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
        auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
        if (!TestNotNull(TEXT("Native world"), Owner) || !TestNotNull(TEXT("Coordinator"), Coordinator)) return false;
        FProphecyJoltWorldSettings Settings;
        Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
        const auto Initialized = Owner->InitializeSimulation(Settings);
        if (!Initialized.IsSuccess()) { AddError(Initialized.Message); return false; }

        FActorSpawnParameters Spawn;
        Spawn.ObjectFlags |= RF_Transient;
        Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        AActor* Actor = Fixture.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn);
        if (!TestNotNull(TEXT("Cube actor"), Actor)) return false;
        Actor->SetActorTickEnabled(false);
        auto* Mesh = NewObject<UStaticMeshComponent>(Actor, NAME_None, RF_Transient);
        Actor->AddInstanceComponent(Mesh);
        Actor->SetRootComponent(Mesh);
        Mesh->SetStaticMesh(Cube);
        Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetEnableGravity(false);
        Mesh->SetLinearDamping(0.0f);
        Mesh->SetAngularDamping(0.0f);
        Mesh->SetGenerateOverlapEvents(false);
        Mesh->RegisterComponent();
        Mesh->SetSimulatePhysics(true);
        auto* Body = NewObject<UProphecyJoltBodyComponent>(Actor, NAME_None, RF_Transient);
        Actor->AddInstanceComponent(Body);
        Body->bAutomaticStep = false;
        Body->RegisterComponent();
        Actor->DispatchBeginPlay();
        FString Error;
        if (!Body->EnableBody(*Mesh, Error)) { AddError(Error); return false; }
        FBodyInstance* Query = Mesh->GetBodyInstance();
        if (!TestTrue(TEXT("Retained native Chaos query actor"), Query && Query->GetPhysicsActor())) return false;
        const FVector VisualBefore = Mesh->GetComponentLocation();
        const FVector QueryBefore = Query->GetPhysicsActor()->GetGameThreadAPI().X();
        const uint64 RevisionBefore = Body->GetRevision();
        FProphecyJoltBodyHandle Handle;
        FProphecyJoltBodyState Before;
        if (!Body->GetBodyHandle(Handle) || !Body->GetBodyState(Before)) return false;
        // This creates real solver motion; it does not call or reproduce the publication tolerance helper.
        const double SpeedCmPerSecond = Scenario == 0 ? 0.0015 : 30.0;
        if (!Body->SetBodyVelocity(FVector(SpeedCmPerSecond, 0, 0), FVector::ZeroVector, true, Error))
        { AddError(Error); return false; }
        bool bCallbackChangedPose = false;
        FDelegateHandle Mutation;
        if (Scenario != 0)
        {
            Mutation = Mesh->TransformUpdated.AddLambda(
                [&](USceneComponent*, EUpdateTransformFlags, ETeleportType)
                {
                    if (bCallbackChangedPose) return;
                    bCallbackChangedPose = true;
                    FTransform Changed = Mesh->GetComponentTransform();
                    if (Scenario == 1) Changed.AddToTranslation(FVector(0, 1, 0));
                    else Changed.SetRotation(FRotator(0, 1, 0).Quaternion() * Changed.GetRotation());
                    Mesh->SetWorldTransform(Changed, false, nullptr, ETeleportType::TeleportPhysics);
                });
        }
        const bool bPublished = Body->StepAndPublish(DeltaSeconds, Error);
        if (Mutation.IsValid()) Mesh->TransformUpdated.Remove(Mutation);
        if (Scenario == 0)
        {
            if (!TestTrue(*FString::Printf(TEXT("Tiny native motion publishes successfully: %s"), *Error), bPublished)) return false;
            FProphecyJoltBodyState Completed;
            if (!Body->GetBodyState(Completed)) return false;
            const double NativeTravelCm = FVector::Distance(Completed.PositionCm, Before.PositionCm);
            TestTrue(TEXT("The native body really moved below UE's visual update threshold"),
                NativeTravelCm > 1.0e-6 && NativeTravelCm < 1.0e-4);
            TestTrue(TEXT("UE legitimately keeps the prior component location for this tiny move"),
                Mesh->GetComponentLocation().Equals(VisualBefore, 1.0e-9));
            const FVector QueryAfter = Query->GetPhysicsActor()->GetGameThreadAPI().X();
            TestTrue(TEXT("The query actor advances even when the visual update is skipped"),
                FVector::Distance(QueryAfter, QueryBefore) > 1.0e-6);
            TestTrue(TEXT("Same-frame query origin equals the actual completed native origin"),
                QueryAfter.Equals(Completed.PositionCm, 1.0e-9));
            TestEqual(TEXT("Tiny motion completes one publication"), Body->GetRevision(), RevisionBefore + 1);
            TestFalse(TEXT("Tiny motion does not stop the client"), Body->IsSteppingStopped());
        }
        else
        {
            TestTrue(TEXT("Publication reaches the pose-replacing callback"), bCallbackChangedPose);
            TestFalse(Scenario == 1 ? TEXT("A callback adding one centimetre is rejected")
                : TEXT("A callback adding one degree is rejected"), bPublished);
            TestFalse(TEXT("Rejected publication provides a diagnostic"), Error.IsEmpty());
            TestEqual(TEXT("Rejected callback pose does not commit a publication"), Body->GetRevision(), RevisionBefore);
            TestTrue(TEXT("Rejected callback pose stops the client"), Body->IsSteppingStopped());
            TestTrue(TEXT("Failure retains native ownership for explicit cleanup"), Owner->OwnsBody(Handle));
        }
        TestFalse(TEXT("Publication never revives Chaos dynamics"), Mesh->IsAnySimulatingPhysics());
        TestTrue(TEXT("The original receiver stays QueryOnly"), Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryOnly);
        Body->DisableBody();
        TestFalse(TEXT("Explicit cleanup retires the native handle after either result"), Owner->OwnsBody(Handle));
        TestEqual(TEXT("Explicit cleanup retires the shared client"), Coordinator->GetRegisteredStepClientCount(), 0);
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRuntimeChannelsTest,
    "Prophecy.Jolt.BodyComponent.RuntimeChannels",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltRuntimeChannelsTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::BodyComponentTests;
    FWorldFixture Fixture;
    Fixture.World->InitializeActorsForPlay(FURL());
    auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    if (!TestTrue(TEXT("Initialize isolated channel world"), Owner->InitializeSimulation(Settings).IsSuccess())) return false;
    auto* Actor = Fixture.World->SpawnActor<AActor>();
    auto* Mesh = NewObject<UStaticMeshComponent>(Actor);
    Actor->AddInstanceComponent(Mesh); Actor->SetRootComponent(Mesh);
    Mesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
    Mesh->SetWorldLocation(FVector(-150, 0, 0));
    Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
    Mesh->SetEnableGravity(false); Mesh->SetLinearDamping(0); Mesh->SetAngularDamping(0);
    Mesh->RegisterComponent(); Mesh->SetSimulatePhysics(true);
    auto* Adapter = NewObject<UProphecyJoltBodyComponent>(Actor);
    Actor->AddInstanceComponent(Adapter); Adapter->bAutomaticStep = false; Adapter->RegisterComponent();
    Actor->DispatchBeginPlay();
    FString Error;
    if (!TestTrue(TEXT("Admit real component"), Adapter->EnableBody(*Mesh, Error))) { AddError(Error); return false; }
    FProphecyJoltBodyHandle Handle, Wall;
    Adapter->GetBodyHandle(Handle);
    FProphecyJoltFixtureBodySettings WallSettings;
    WallSettings.bDynamic = false; WallSettings.ObjectChannel = ECC_WorldStatic;
    WallSettings.CollisionResponses.SetAllChannels(ECR_Ignore);
    WallSettings.CollisionResponses.SetResponse(ECC_PhysicsBody, ECR_Block);
    if (!TestTrue(TEXT("Create blocking wall"), Owner->CreateBox(FVector(5, 300, 300), 0, WallSettings, Wall).IsSuccess())) return false;
    auto Advance = [&](float Velocity)
    {
        if (!Owner->SetBodyVelocity(Handle, FVector(Velocity, 0, 0), FVector::ZeroVector, true).IsSuccess()) return false;
        for (int32 Frame = 0; Frame < 60; ++Frame)
        {
            if (!Adapter->PrepareJoltWorldStep(1.f / 60, false, Error)
                || !Owner->Step(1.f / 60, 1).IsSuccess() || !Adapter->ConsumeCompletedJoltWorldStep(Error))
            { AddError(Error); return false; }
        }
        FProphecyJoltBodyHandle Current;
        Adapter->GetBodyHandle(Current);
        TestTrue(TEXT("Channel edits retain native body identity"), Current.Generation == Handle.Generation && Current.Slot == Handle.Slot);
        TestFalse(TEXT("Channel edits never stop simulation"), Adapter->IsSteppingStopped());
        return true;
    };
    if (!Advance(200)) return false;
    TestTrue(TEXT("Bilateral block stops left of wall"), Mesh->GetComponentLocation().X < -50);
    Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
    if (!Advance(200)) return false;
    TestTrue(TEXT("Set All Ignore removes an existing contact"), Mesh->GetComponentLocation().X > 100);
    Mesh->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    if (!Advance(-200)) return false;
    TestTrue(TEXT("Set Channel Block restores collision from the other side"), Mesh->GetComponentLocation().X > 50);
    Mesh->SetCollisionObjectType(ECC_GameTraceChannel18);
    if (!Advance(-200)) return false;
    TestTrue(TEXT("Runtime custom object channel obeys other body's ignore mask"), Mesh->GetComponentLocation().X < -100);
    FProphecyJoltCollisionUpdate WallUpdate;
    WallUpdate.Handle = Wall; WallUpdate.ObjectChannel = ECC_WorldStatic;
    WallUpdate.Responses.SetAllChannels(ECR_Block);
    if (!TestTrue(TEXT("Update static wall filters in place"), Owner->UpdateBodyCollision({ WallUpdate }).IsSuccess())) return false;
    Mesh->SetCollisionProfileName(TEXT("BlockAllDynamic"));
    if (!Advance(200)) return false;
    TestTrue(TEXT("Preset restores native collision without readmission"), Mesh->GetComponentLocation().X < -50);
    TestFalse(TEXT("Preset did not start Chaos simulation"), Mesh->IsAnySimulatingPhysics());
    TestTrue(TEXT("Preset keeps the UE query proxy"), Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryOnly);
    const FVector Center = Mesh->GetComponentLocation();
    FHitResult Hit;
    Mesh->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
    TestFalse(TEXT("Visibility ignore also updates UE traces"), Fixture.World->LineTraceSingleByChannel(Hit,
        Center + FVector(0, -100, 0), Center + FVector(0, 100, 0), ECC_Visibility));
    Mesh->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    TestTrue(TEXT("Visibility block also updates UE traces"), Fixture.World->LineTraceSingleByChannel(Hit,
        Center + FVector(0, -100, 0), Center + FVector(0, 100, 0), ECC_Visibility));
    Adapter->DisableBody();
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltCharacterChannelsTest,
    "Prophecy.Jolt.BodyComponent.CharacterRuntimeChannels",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltCharacterChannelsTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::BodyComponentTests;
    FWorldFixture Fixture;
    Fixture.World->InitializeActorsForPlay(FURL());
    auto* Owner = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    if (!TestTrue(TEXT("Initialize character channel world"), Owner->InitializeSimulation(Settings).IsSuccess())) return false;
    auto* Asset = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    auto* PHAT = LoadObject<UPhysicsAsset>(nullptr, TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Actual mannequin"), Asset) || !TestNotNull(TEXT("Actual PHAT"), PHAT)) return false;
    auto* Agent = Fixture.World->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(), FTransform::Identity,
        nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    Agent->bManualNNPoseApplication = true;
    Agent->bAutoEnsureStandaloneNNManager = false;
    Agent->bAutoPublishManualFollowerSubstepTargets = false;
    Agent->bEnableAttackFists = false;
    Agent->AutoPossessAI = EAutoPossessAI::Disabled;
    Agent->AutoPossessPlayer = EAutoReceiveInput::Disabled;
    auto* Mesh = NewObject<USkeletalMeshComponent>(Agent, TEXT("PhysicalMesh"));
    Agent->AddInstanceComponent(Mesh); Mesh->SetupAttachment(Agent->GetAgentCapsule());
    Mesh->SetSkeletalMesh(Asset); Mesh->SetPhysicsAsset(PHAT);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->SetCollisionObjectType(ECC_PhysicsBody); Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetGenerateOverlapEvents(false); Mesh->RegisterComponent();
    Agent->GetAgentMesh()->SetSkeletalMesh(nullptr);
    Agent->FinishSpawning(FTransform::Identity);
    Agent->DispatchBeginPlay();
    constexpr int32 PoseID = 998731;
    ON_SCOPE_EXIT { FProphecyNNPoseStore::ClearAgentPose(PoseID); };
    TArray<FName> Names;
    TArray<FTransform> ComponentPose;
    ComponentPose.SetNum(Asset->GetRefSkeleton().GetNum());
    for (int32 Index = 0; Index < Asset->GetRefSkeleton().GetNum(); ++Index)
    {
        Names.Add(Asset->GetRefSkeleton().GetBoneName(Index));
        const int32 Parent = Asset->GetRefSkeleton().GetParentIndex(Index);
        const auto& Local = Asset->GetRefSkeleton().GetRefBonePose()[Index];
        ComponentPose[Index] = Parent == INDEX_NONE ? Local : Local * ComponentPose[Parent];
    }
    FProphecyNNPoseStore::SetAgentLocalPose(PoseID, Names, Asset->GetRefSkeleton().GetRefBonePose(),
        ComponentPose, ComponentPose, Mesh->GetComponentTransform(), Mesh->GetComponentTransform(), Fixture.World->GetTimeSeconds());
    Agent->ConfigureNNPoseDataSource(PoseID, 1.f / 30, true);
    Mesh->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
    auto* Anim = Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());
    Anim->AgentId = PoseID; Anim->NNPoseIntervalSeconds = 1.f / 30; Anim->bInterpolateNNPose = true;
    Mesh->TickAnimation(0, false); Mesh->RefreshBoneTransforms();
    Agent->SetMACDEnabled(false);
    if (!TestTrue(TEXT("Select Jolt while kinematic"), Agent->EnableJoltPhysicalAnimation())) return false;
    TestTrue(TEXT("Backend selection preserves Kinematic"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic);
    TestTrue(TEXT("Jolt selection is visible without a rig"), Agent->IsJoltPhysicalAnimationSelected());
    TestFalse(TEXT("Kinematic selection creates no simulation"), Agent->IsJoltPhysicalAnimationEnabled() || Mesh->IsAnySimulatingPhysics());
    Agent->DisableJoltPhysicalAnimation();
    TestTrue(TEXT("Select Chaos preserves Kinematic"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic);
    TestFalse(TEXT("Chaos clears selection"), Agent->IsJoltPhysicalAnimationSelected());
    if (!TestTrue(TEXT("Enter HalfSim"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim))) return false;
    if (!TestTrue(TEXT("Select Jolt in HalfSim"), Agent->EnableJoltPhysicalAnimation())) return false;
    TestTrue(TEXT("Jolt selection preserves HalfSim"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::HalfSim);
    TestTrue(TEXT("HalfSim keeps Chaos ownership"), Mesh->IsAnySimulatingPhysics() && !Agent->IsJoltPhysicalAnimationEnabled());
    Agent->DisableJoltPhysicalAnimation();
    TestTrue(TEXT("Select Chaos preserves HalfSim"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::HalfSim);
    if (!TestTrue(TEXT("Enter physical mode"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))) return false;
    Agent->GetAgentCapsule()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    for (auto* Body : Mesh->Bodies) if (Body) { Body->SetUseCCD(false); Body->SetUseMACD(false); }
    if (!TestTrue(TEXT("Enable real Jolt character"), Agent->EnableJoltPhysicalAnimation())) return false;
    auto* Adapter = Agent->GetJoltCharacterComponent();
    Adapter->bAutomaticStep = false;
    FString Error;
    TArray<FProphecyJoltBodyHandle> Original;
    for (const auto& Setup : PHAT->SkeletalBodySetups)
    {
        FProphecyJoltBodyHandle Handle;
        if (!Adapter->GetBodyHandle(Setup->BoneName, Handle)) return false;
        Original.Add(Handle);
    }
    auto Verify = [&]()
    {
        if (!Adapter->PrepareJoltWorldStep(1.f / 60, false, Error)) { AddError(Error); return false; }
        for (int32 Index = 0; Index < Original.Num(); ++Index)
        {
            auto* Body = Mesh->GetBodyInstance(PHAT->SkeletalBodySetups[Index]->BoneName);
            FBodyCollisionFilterData Expected;
            Body->BuildBodyFilterData(Expected);
            const auto Responses = ExtractSimCollisionResponseContainer(Expected.SimFilter);
            FProphecyJoltCollisionUpdate Actual;
            if (!Owner->ReadBodyCollision(Original[Index], Actual).IsSuccess()) return false;
            TestEqual(TEXT("Character object channel matches UE"), int32(Actual.ObjectChannel), int32(GetCollisionChannel(Expected.SimFilter.Word3)));
            for (int32 Channel = 0; Channel < 32; ++Channel)
                TestEqual(TEXT("PHAT/component block response matches UE"),
                    Actual.Responses.GetResponse(static_cast<ECollisionChannel>(Channel)) == ECR_Block,
                    Responses.GetResponse(static_cast<ECollisionChannel>(Channel)) == ECR_Block);
        }
        return true;
    };
    if (!Verify()) return false;
    Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
    if (!Verify()) return false;
    Mesh->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Mesh->SetCollisionResponseToChannel(ECC_GameTraceChannel18, ECR_Block);
    if (!Verify()) return false;
    Mesh->SetCollisionObjectType(ECC_GameTraceChannel18);
    if (!Verify()) return false;
    Mesh->SetCollisionProfileName(TEXT("Ragdoll"));
    if (!Verify()) return false;
    TestTrue(TEXT("Character remains Jolt physical"), Adapter->IsJoltPhysical());
    TestFalse(TEXT("Character never latched a failure"), Adapter->IsSteppingStopped());
    Agent->DisableJoltPhysicalAnimation();
    TestTrue(TEXT("Disabling Jolt preserves full Sim"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Physical);
    TestTrue(TEXT("Chaos owns simulation after backend switch"), Mesh->IsAnySimulatingPhysics());
    TestFalse(TEXT("Chaos switch releases native rig"), Adapter->IsJoltPhysical());
    // Repeat the user's toggle sequence, then change mode independently of the backend.
    for (int32 Cycle = 0; Cycle < 2; ++Cycle)
    {
        for (auto* Body : Mesh->Bodies) if (Body) { Body->SetUseCCD(false); Body->SetUseMACD(false); }
        if (!TestTrue(TEXT("Switch Sim back to Jolt"), Agent->EnableJoltPhysicalAnimation())) return false;
        TestTrue(TEXT("Enable preserves full Sim"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Physical);
        TestFalse(TEXT("Jolt alone owns simulation"), Mesh->IsAnySimulatingPhysics());
        Agent->DisableJoltPhysicalAnimation();
        TestTrue(TEXT("Repeated Disable preserves full Sim"), Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Physical);
        TestTrue(TEXT("Repeated switch restores Chaos simulation"), Mesh->IsAnySimulatingPhysics());
    }
    if (!TestTrue(TEXT("Explicit Kinematic still works"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))) return false;
    if (!TestTrue(TEXT("Select Jolt without changing Kinematic"), Agent->EnableJoltPhysicalAnimation())) return false;
    for (auto* Body : Mesh->Bodies) if (Body) { Body->SetUseCCD(false); Body->SetUseMACD(false); }
    if (!TestTrue(TEXT("Later Sim uses selected Jolt backend"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))) return false;
    TestTrue(TEXT("Selected Jolt admits on later Sim"), Agent->IsJoltPhysicalAnimationEnabled());
    if (!TestTrue(TEXT("Explicit Kinematic from Jolt remains Kinematic"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic))) return false;
    TestFalse(TEXT("Explicit Kinematic does not restore Chaos Sim"), Mesh->IsAnySimulatingPhysics());
    TestTrue(TEXT("Mode changes retain backend selection"), Agent->IsJoltPhysicalAnimationSelected());
    Agent->DisableJoltPhysicalAnimation();
    return !HasAnyErrors();
}
#endif
