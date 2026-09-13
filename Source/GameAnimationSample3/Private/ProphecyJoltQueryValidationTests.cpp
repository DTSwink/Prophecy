#include "ProphecyJoltQueryPose.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltQueryValidationTest,
    "Prophecy.Jolt.QueryPose.RejectsChangedBodiesBeforeMutation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltQueryValidationTest::RunTest(const FString&)
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
    } Fixture;
    if (!TestNotNull(TEXT("Actual query world"), Fixture.World)) return false;
    USkeletalMesh* Asset = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Actual mannequin"), Asset)) return false;
    AActor* Actor = Fixture.World->SpawnActor<AActor>();
    auto* Mesh = NewObject<USkeletalMeshComponent>(Actor);
    Actor->AddInstanceComponent(Mesh);
    Actor->SetRootComponent(Mesh);
    Mesh->SetSkeletalMeshAsset(Asset);
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;
    Mesh->RegisterComponent();
    Mesh->SetAllBodiesSimulatePhysics(false);
    Mesh->SetSimulatePhysics(false);
    Mesh->SetComponentTickEnabled(false);
    if (!TestEqual(TEXT("Actual body count"), Mesh->Bodies.Num(), 22)) return false;
    FProphecyJoltQueryPose Publisher;
    FString Error;
    if (!Publisher.Initialize(*Mesh, Error)) { AddError(Error); return false; }
    const FReferenceSkeleton& Skeleton = Asset->GetRefSkeleton();
    TArray<FTransform> WorldPose = Skeleton.GetRefBonePose();
    for (int32 Bone = 0; Bone < WorldPose.Num(); ++Bone)
    {
        const int32 Parent = Skeleton.GetParentIndex(Bone);
        if (Parent != INDEX_NONE) WorldPose[Bone] *= WorldPose[Parent];
        WorldPose[Bone].NormalizeRotation();
    }
    if (!Publisher.Publish(*Mesh, WorldPose, Error)) { AddError(Error); return false; }
    const uint64 BaselineScaleCalls = Publisher.GetScaleUpdateCalls();
    TArray<FTransform> Baseline;
    for (FBodyInstance* Body : Mesh->Bodies) Baseline.Add(Body->GetUnrealWorldTransform());
    // Every otherwise-valid transform would move. A late malformed slot must prevent all writes.
    for (FTransform& Transform : WorldPose) Transform.AddToTranslation(FVector(777.0, 0.0, 0.0));
    const auto CheckUnchanged = [&]()
    {
        bool bValid = TestEqual(TEXT("Rejected publication performs no scale mutation"), Publisher.GetScaleUpdateCalls(), BaselineScaleCalls);
        for (int32 Index = 0; Index < Mesh->Bodies.Num(); ++Index)
            bValid &= TestTrue(TEXT("Rejected publication leaves every native body transform unchanged"),
                Mesh->Bodies[Index]->GetUnrealWorldTransform().Equals(Baseline[Index], 0.0));
        return bValid;
    };
    FBodyInstance* First = Mesh->Bodies[0];
    const bool OriginalSim = First->bSimulatePhysics;
    const auto NativeActor = First->GetPhysicsActor();
    const Chaos::EObjectStateType OriginalState = NativeActor->GetGameThreadAPI().ObjectState();
    ON_SCOPE_EXIT
    {
        Mesh->Bodies[0] = First;
        First->bSimulatePhysics = OriginalSim;
        NativeActor->GetGameThreadAPI().SetObjectState(OriginalState);
    };

    // Preserve BOTH checks: the authored effective simulation flag and native object state are
    // intentionally independent. A partial external edit must not bypass either preflight.
    First->bSimulatePhysics = true;
    const bool bFlagIsSimulating = First->ShouldInstanceSimulatingPhysics();
    const bool bFlagRejected = !Publisher.Publish(*Mesh, WorldPose, Error);
    First->bSimulatePhysics = OriginalSim;
    if (!TestTrue(TEXT("Actual simple body recognizes the authored simulation flag"), bFlagIsSimulating)
        || !TestTrue(TEXT("Authored sim flag is rejected even while native actor stays kinematic"), bFlagRejected)
        || !CheckUnchanged()) return false;

    NativeActor->GetGameThreadAPI().SetObjectState(Chaos::EObjectStateType::Dynamic);
    const bool bNativeRejected = !Publisher.Publish(*Mesh, WorldPose, Error);
    NativeActor->GetGameThreadAPI().SetObjectState(OriginalState);
    if (!TestTrue(TEXT("Native dynamic state is rejected even with authored simulation disabled"), bNativeRejected)
        || !CheckUnchanged()) return false;

    Mesh->Bodies[0] = nullptr;
    const bool bNullRejected = !Publisher.Publish(*Mesh, WorldPose, Error);
    Mesh->Bodies[0] = First;
    if (!TestTrue(TEXT("A missing live body slot is rejected without a premature mesh-wide dereference"), bNullRejected)
        || !CheckUnchanged()) return false;

    const int32 FinalBone = Mesh->Bodies.Last()->InstanceBoneIndex;
    const FTransform ValidFinal = WorldPose[FinalBone];
#if !ENABLE_NAN_DIAGNOSTIC
    // UE's Debug NaN diagnostics intentionally sanitize this setter and emit an ensure; such a
    // build cannot preserve the deliberately invalid input through this supported public API.
    WorldPose[FinalBone].SetTranslation(FVector(std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0));
    if (!TestFalse(TEXT("Nonfinite completed transform rejected before any body write"), Publisher.Publish(*Mesh, WorldPose, Error))
        || !CheckUnchanged()) return false;
    WorldPose[FinalBone] = ValidFinal;
#else
    AddInfo(TEXT("NaN input case omitted because ENABLE_NAN_DIAGNOSTIC sanitizes FTransform setters; the Development target exercises this case."));
#endif
    WorldPose[FinalBone].SetScale3D(FVector(1.0, 0.0, 1.0));
    if (!TestFalse(TEXT("Nonpositive completed scale remains rejected"), Publisher.Publish(*Mesh, WorldPose, Error))
        || !CheckUnchanged()) return false;
    WorldPose[FinalBone] = ValidFinal;
    if (!Publisher.Publish(*Mesh, WorldPose, Error)) { AddError(Error); return false; }
    return TestTrue(TEXT("Valid publication still commits after rejected attempts"),
        Mesh->Bodies[0]->GetUnrealWorldTransform().GetTranslation().Equals(Baseline[0].GetTranslation() + FVector(777.0, 0.0, 0.0), 0.02));
}
#endif
