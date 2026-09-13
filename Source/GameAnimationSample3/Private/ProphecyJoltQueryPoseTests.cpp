#include "ProphecyJoltQueryPose.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyJoltPoseAnimInstance.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "Animation/AnimTypes.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/HitResult.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"

namespace ProphecyJolt::QueryPoseTests
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

void Compose(const FReferenceSkeleton& Skeleton, const TArray<FTransform>& Local, const FTransform& MeshWorld,
    TArray<FTransform>& OutComponent, TArray<FTransform>& OutWorld)
{
    OutComponent.SetNum(Local.Num());
    OutWorld.SetNum(Local.Num());
    for (int32 Index = 0; Index < Local.Num(); ++Index)
    {
        const int32 Parent = Skeleton.GetParentIndex(Index);
        OutComponent[Index] = Parent == INDEX_NONE ? Local[Index] : Local[Index] * OutComponent[Parent];
        OutWorld[Index] = OutComponent[Index] * MeshWorld;
    }
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltImmediateQueryPoseTest,
    "Prophecy.Jolt.QueryPose.ImmediateFinalizeTraceAndScaleCache",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltImmediateQueryPoseTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::QueryPoseTests;
    FWorldFixture Fixture;
    if (!TestNotNull(TEXT("Game query world"), Fixture.World)) return false;
    USkeletalMesh* Asset = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Actual project mannequin asset"), Asset)) return false;
    AActor* Actor = Fixture.World->SpawnActor<AActor>();
    USkeletalMeshComponent* Mesh = NewObject<USkeletalMeshComponent>(Actor);
    Actor->AddInstanceComponent(Mesh);
    Actor->SetRootComponent(Mesh);
    Mesh->SetSkeletalMeshAsset(Asset);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;
    Mesh->bDeferKinematicBoneUpdate = false;
    Mesh->bEnableUpdateRateOptimizations = false;
    Mesh->RegisterComponent();
    Mesh->SetAllBodiesSimulatePhysics(false);
    Mesh->SetSimulatePhysics(false);
    Mesh->SetAllBodiesPhysicsBlendWeight(0.0f);
    Mesh->SetDisablePostProcessBlueprint(true);
    Mesh->SetAnimInstanceClass(UProphecyJoltPoseAnimInstance::StaticClass());
    Mesh->SetComponentTickEnabled(false);
    auto* Anim = Cast<UProphecyJoltPoseAnimInstance>(Mesh->GetAnimInstance());
    if (!TestNotNull(TEXT("Native completed pose instance"), Anim)
        || !TestEqual(TEXT("Actual PHAT has all bodies"), Mesh->Bodies.Num(), 22)
        || !TestTrue(TEXT("Fixture postprocess pose evaluation is disabled"), Mesh->GetDisablePostProcessBlueprint())) return false;

    FProphecyJoltQueryPose QueryPose;
    FString Error;
    if (!TestTrue(*FString::Printf(TEXT("Initialize query adapter: %s"), *Error), QueryPose.Initialize(*Mesh, Error)))
    { AddError(Error); return false; }
    const auto& Skeleton = Asset->GetRefSkeleton();
    TArray<FTransform> Local = Skeleton.GetRefBonePose();
    TestEqual(TEXT("Full project skeleton retained"), Local.Num(), 88);
    Local[0].SetTranslation(FVector(1000.0, 0.0, 200.0));
    Local[0].SetScale3D(FVector(1.03, 1.11, 0.94));
    const int32 Head = Skeleton.FindBoneIndex(TEXT("head"));
    if (!TestTrue(TEXT("Head bone exists"), Head != INDEX_NONE)) return false;
    Local[Head].SetRotation(FQuat(FVector::UpVector, FMath::DegreesToRadians(17.0)) * Local[Head].GetRotation());
    TArray<FTransform> Component, World;
    int32 Finalized = 0;
    bool bCallbacksCorrect = true;
    const auto Delegate = Mesh->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
    {
        ++Finalized;
        double MaxPositionError = 0.0, MaxAngleError = 0.0;
        FName WorstBone;
        const TArray<FTransform>& PublishedComponent = Mesh->GetComponentSpaceTransforms();
        if (PublishedComponent.Num() != Component.Num()) bCallbacksCorrect = false;
        else for (int32 BoneIndex = 0; BoneIndex < Component.Num(); ++BoneIndex)
        {
            const FTransform& Actual = PublishedComponent[BoneIndex];
            const FTransform& Expected = Component[BoneIndex];
            if (!Actual.GetTranslation().Equals(Expected.GetTranslation(), 0.02)
                || !Actual.GetScale3D().Equals(Expected.GetScale3D(), 1.0e-4)
                || !Actual.GetRotation().IsNormalized()
                || Actual.GetRotation().AngularDistance(Expected.GetRotation().GetNormalized()) > FMath::DegreesToRadians(0.02))
                bCallbacksCorrect = false;
        }
        // Runs inside UE finalization, before the publisher returns or performs any second update.
        for (FBodyInstance* Body : Mesh->Bodies)
        {
            const FTransform Native = Body->GetUnrealWorldTransform();
            const FTransform Socket = Mesh->GetBoneTransform(Body->InstanceBoneIndex);
            const double PositionError = FVector::Distance(Native.GetTranslation(), Socket.GetTranslation());
            if (PositionError > MaxPositionError) { MaxPositionError = PositionError; WorstBone = Body->BodySetup->BoneName; }
            const double AngleError = Native.GetRotation().GetNormalized().AngularDistance(Socket.GetRotation().GetNormalized());
            MaxAngleError = FMath::Max(MaxAngleError, double(FMath::RadiansToDegrees(AngleError)));
            if (!Native.GetTranslation().Equals(Socket.GetTranslation(), 0.02)
                || !Native.GetRotation().IsNormalized() || !Socket.GetRotation().IsNormalized()
                || AngleError > FMath::DegreesToRadians(0.02))
                bCallbacksCorrect = false;
        }
        FBodyInstance* HeadBody = Mesh->GetBodyInstance(TEXT("head"));
        if (!HeadBody) { bCallbacksCorrect = false; return; }
        const auto& External = HeadBody->GetPhysicsActor()->GetGameThreadAPI();
        const FVector Center = FTransform(External.R(), External.X()).TransformPosition(
            FVector(External.GetGeometry()->BoundingBox().Center()));
        FHitResult Hit;
        const bool bHit = Fixture.World->LineTraceSingleByChannel(Hit, Center - FVector(300.0, 0.0, 0.0),
            Center + FVector(300.0, 0.0, 0.0), ECC_Visibility);
        if (!bHit || Hit.GetComponent() != Mesh || Hit.BoneName.IsNone()) bCallbacksCorrect = false;
        AddInfo(FString::Printf(TEXT("Finalization %d: max position %.9f cm (%s), angle %.9f deg; trace=%d component=%s bone=%s center=%s"),
            Finalized, MaxPositionError, *WorstBone.ToString(), MaxAngleError, bHit,
            *GetNameSafe(Hit.GetComponent()), *Hit.BoneName.ToString(), *Center.ToString()));
    }));
    ON_SCOPE_EXIT
    {
        Mesh->UnregisterOnBoneTransformsFinalizedDelegate(Delegate);
        Anim->ClearPostEvaluateQueryCommit();
    };

    const auto Publish = [&](uint64 Revision)
    {
        Compose(Skeleton, Local, Mesh->GetComponentTransform(), Component, World);
        if (!Anim->PublishCompletedLocalPose(Local, Revision, Error)) return false;
        namespace Profile = ProphecyJolt::CharacterProfiling;
        Profile::BeginFrame();
        ON_SCOPE_EXIT { Profile::Disable(); };
        const int16 BeforeUpdate = Anim->GetUpdateCounter().Get();
        Mesh->TickAnimation(0.0f, false);
        const int16 AfterUpdate = Anim->GetUpdateCounter().Get();
        TestTrue(TEXT("Explicit zero-delta tick performs a native graph update"), AfterUpdate != BeforeUpdate);
        TestTrue(TEXT("Native graph traversal is recognized before Refresh"), Anim->GetUpdateCounter().HasEverBeenUpdated());
        if (!Anim->ArmPostEvaluateQueryCommit(FProphecyJoltPostEvaluateQueryCommit::CreateLambda(
            [&](FString& QueryError) { return QueryPose.Publish(*Mesh, World, QueryError); }), Revision, Error)) return false;
        Mesh->RefreshBoneTransforms(nullptr);
        const Profile::FFrame Frame = Profile::EndFrame();
        TestEqual(TEXT("Refresh retains the explicit update without repeating it"), Anim->GetUpdateCounter().Get(), AfterUpdate);
        TestEqual(TEXT("One actual PreUpdate per publication"), Frame.Calls[int32(Profile::EPhase::ProxyPreUpdate)], uint32(1));
        TestEqual(TEXT("One pre-evaluation per publication"), Frame.Calls[int32(Profile::EPhase::ProxyPreEvaluate)], uint32(1));
        TestEqual(TEXT("One full pose evaluation per publication"), Frame.Calls[int32(Profile::EPhase::ProxyEvaluate)], uint32(1));
        TestEqual(TEXT("One post-evaluation per publication"), Frame.Calls[int32(Profile::EPhase::ProxyPostEvaluateBase)], uint32(1));
        Anim->ClearPostEvaluateQueryCommit();
        return Anim->GetPostEvaluateQueryCommitResult(Revision, Error);
    };
    if (!Publish(1)) { AddError(Error); return false; }
    const uint64 InitialCalls = QueryPose.GetScaleUpdateCalls();
    TestTrue(TEXT("Initial requested scales were applied through UE"), InitialCalls > 0);
    TArray<const Chaos::FImplicitObject*> Geometry;
    for (const FBodyInstance* Body : Mesh->Bodies) Geometry.Add(Body->GetPhysicsActor()->GetGameThreadAPI().GetGeometry());

    Local[0].AddToTranslation(FVector(400.0, 0.0, 0.0));
    if (!Publish(2)) { AddError(Error); return false; }
    TestEqual(TEXT("Unchanged nonuniform requests do not rebuild body scales"), QueryPose.GetScaleUpdateCalls(), InitialCalls);
    for (int32 Index = 0; Index < Mesh->Bodies.Num(); ++Index)
        TestTrue(TEXT("Unchanged requested scale retains actual native geometry identity"),
            Geometry[Index] == Mesh->Bodies[Index]->GetPhysicsActor()->GetGameThreadAPI().GetGeometry());

    // Change a request, then perturb native scale externally. Both must invalidate the cache.
    Local[0].SetScale3D(FVector(1.08, 1.16, 0.98));
    if (!Publish(3)) { AddError(Error); return false; }
    const uint64 ChangedCalls = QueryPose.GetScaleUpdateCalls();
    TestTrue(TEXT("Changed authored scale uses UE scaling again"), ChangedCalls > InitialCalls);
    FBodyInstance* Perturbed = nullptr;
    for (int32 Index = 0; Index < Mesh->Bodies.Num(); ++Index)
        if (!Mesh->GetPhysicsAsset()->SkeletalBodySetups[Index]->bSkipScaleFromAnimation)
        { Perturbed = Mesh->Bodies[Index]; break; }
    if (!TestNotNull(TEXT("A scale-updated body exists"), Perturbed)) return false;
    if (!TestTrue(TEXT("Deliberate native scale change"), Perturbed->UpdateBodyScale(Perturbed->Scale3D * 1.15))) return false;
    if (!Publish(4)) { AddError(Error); return false; }
    TestTrue(TEXT("Changed applied scale/geometry invalidates the cache"), QueryPose.GetScaleUpdateCalls() > ChangedCalls);
    // Reinitialize the native graph and reuse source revision 1 with a changed pose.
    // This runs in the same engine frame as the earlier publications: source serial,
    // graph traversal and actual evaluated bones must all advance independently.
    Anim->ClearCompletedLocalPose();
    Anim->InitializeAnimation();
    TestFalse(TEXT("Reinitialization resets native graph traversal"), Anim->GetUpdateCounter().HasEverBeenUpdated());
    Local[0].AddToTranslation(FVector(0.0, 500.0, 50.0));
    Local[Head].SetRotation(FQuat(FVector::ForwardVector, FMath::DegreesToRadians(-31.0)) * Local[Head].GetRotation());
    if (!Publish(1)) { AddError(Error); return false; }
    TestEqual(TEXT("One finalization per full publication including clear/reinitialize"), Finalized, 5);
    TestTrue(TEXT("Every finalization sees all 88 current bones, sockets AND immediate native query hits"), bCallbacksCorrect);

    // Compare the final geometry and frame with the original engine update for the exact same pose.
    TArray<FBox> BeforeBounds;
    TArray<FVector> BeforeScale;
    for (FBodyInstance* Body : Mesh->Bodies)
    {
        const auto Bounds = Body->GetPhysicsActor()->GetGameThreadAPI().GetGeometry()->BoundingBox();
        BeforeBounds.Add(FBox(FVector(Bounds.Min()), FVector(Bounds.Max())));
        BeforeScale.Add(Body->Scale3D);
    }
    Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
    Mesh->UpdateKinematicBonesToAnim(Component, ETeleportType::TeleportPhysics, true, EAllowKinematicDeferral::DisallowDeferral);
    for (int32 Index = 0; Index < Mesh->Bodies.Num(); ++Index)
    {
        FBodyInstance* Body = Mesh->Bodies[Index];
        const auto Bounds = Body->GetPhysicsActor()->GetGameThreadAPI().GetGeometry()->BoundingBox();
        TestNearlyEqual(TEXT("Cached applied scale equals stock UE result"), BeforeScale[Index], Body->Scale3D, 1.0e-6f);
        TestNearlyEqual(TEXT("Cached geometry lower bound equals stock UE result"), BeforeBounds[Index].Min, FVector(Bounds.Min()), 1.0e-3f);
        TestNearlyEqual(TEXT("Cached geometry upper bound equals stock UE result"), BeforeBounds[Index].Max, FVector(Bounds.Max()), 1.0e-3f);
    }
    return !HasAnyErrors();
}
#endif
