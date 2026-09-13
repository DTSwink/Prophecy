#include "ProphecyJoltQueryPose.h"
#include "ProphecyJoltCharacterProfiling.h"

#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "Chaos/KinematicTargets.h"

namespace
{
bool Reject(FString& Error, const TCHAR* Message) { Error = Message; return false; }
}

bool FProphecyJoltQueryPose::ValidateMesh(USkeletalMeshComponent& Mesh, FString& OutError) const
{
    if (!IsInGameThread() || !IsValid(&Mesh) || !Mesh.IsRegistered() || !Mesh.IsPhysicsStateCreated()
        || !Mesh.GetWorld() || !Mesh.GetWorld()->GetPhysicsScene() || UPhysicsSettings::Get()->bTickPhysicsAsync
        || Mesh.bEnablePerPolyCollision
        || Mesh.GetCollisionEnabled() != ECollisionEnabled::QueryOnly || !Mesh.GetSkeletalMeshAsset()
        || !Mesh.GetPhysicsAsset() || Mesh.Bodies.Num() == 0
        || Mesh.Bodies.Num() != Mesh.GetPhysicsAsset()->SkeletalBodySetups.Num())
        return Reject(OutError, TEXT("Bulk query publication needs a synchronous, live, PHAT-backed QueryOnly kinematic mesh."));
    return true;
}

bool FProphecyJoltQueryPose::Initialize(USkeletalMeshComponent& Mesh, FString& OutError)
{
    OutError.Reset();
    BoundMesh.Reset();
    BoundAsset.Reset();
    Bodies.Reset();
    ScaleUpdateCalls = 0;
    if (!ValidateMesh(Mesh, OutError)) return false;
    FPhysScene* Scene = Mesh.GetWorld()->GetPhysicsScene();
    const UPhysicsAsset* Asset = Mesh.GetPhysicsAsset();
    for (int32 Index = 0; Index < Mesh.Bodies.Num(); ++Index)
    {
        FBodyInstance* Instance = Mesh.Bodies[Index];
        const FPhysicsActorHandle Actor = Instance ? Instance->GetPhysicsActor() : nullptr;
        if (!Instance || !Actor || Instance->ShouldInstanceSimulatingPhysics()
            || FPhysicsInterface::GetCurrentScene(Actor) != Scene
            || !FPhysicsInterface::IsKinematic(Actor) || Actor->GetMarkedDeleted() || !Actor->GetSyncTimestamp()
            || !Mesh.GetSkeletalMeshAsset()->GetRefSkeleton().GetRefBonePose().IsValidIndex(Instance->InstanceBoneIndex))
        { Bodies.Reset(); return Reject(OutError, TEXT("Bulk query publication found an invalid or nonkinematic native body.")); }
        FBody& Cached = Bodies.AddDefaulted_GetRef();
        Cached.Instance = Instance;
        Cached.Actor = Actor;
        Cached.BoneIndex = Instance->InstanceBoneIndex;
        Cached.bSkipScale = Asset->SkeletalBodySetups[Index]->bSkipScaleFromAnimation;
    }
    // SetSimulatePhysics(false) already resets this on dynamic->kinematic transition, but an earlier
    // animation update may have installed a position target. Clear it once before owning publication.
    for (const FBody& Cached : Bodies)
    {
        auto& External = Cached.Actor->GetGameThreadAPI();
        External.SetKinematicTarget(Chaos::FKinematicTarget());
        External.SetV(Chaos::FVec3(0));
        External.SetW(Chaos::FVec3(0));
    }
    BoundMesh = &Mesh;
    BoundAsset = Mesh.GetPhysicsAsset();
    return true;
}

bool FProphecyJoltQueryPose::Publish(USkeletalMeshComponent& Mesh,
    TConstArrayView<FTransform> BoneWorldTransforms, FString& OutError)
{
    namespace Profile = ProphecyJolt::CharacterProfiling;
    const double ValidateStarted = Profile::Timestamp();
    OutError.Reset();
    if (!ValidateMesh(Mesh, OutError)) return false;
    const UPhysicsAsset* Asset = Mesh.GetPhysicsAsset();
    if (BoundMesh.Get() != &Mesh || BoundAsset.Get() != Asset || Bodies.Num() != Mesh.Bodies.Num()
        || Mesh.KinematicBonesUpdateType != EKinematicBonesUpdateToPhysics::SkipAllBones)
        return Reject(OutError, TEXT("The bound mesh/PHAT/query ownership changed; re-enable the Jolt binding."));
    const FVector MeshScale = Mesh.GetComponentTransform().GetScale3D();
    const bool bUniformMeshScale = MeshScale.IsUniform();
    FPhysScene* Scene = Mesh.GetWorld()->GetPhysicsScene();
    // Validate every slot before the first mutation. Cached pointers are identities, never lifetime owners.
    for (int32 Index = 0; Index < Bodies.Num(); ++Index)
    {
        const FBody& Cached = Bodies[Index];
        FBodyInstance* Instance = Mesh.Bodies[Index];
        if (!Instance || Instance != Cached.Instance || Instance->GetPhysicsActor() != Cached.Actor
            || Instance->ShouldInstanceSimulatingPhysics() || Instance->InstanceBoneIndex != Cached.BoneIndex
            || FPhysicsInterface::GetCurrentScene(Cached.Actor) != Scene || !FPhysicsInterface::IsKinematic(Cached.Actor)
            || Cached.Actor->GetMarkedDeleted() || !Cached.Actor->GetSyncTimestamp()
            || !BoneWorldTransforms.IsValidIndex(Cached.BoneIndex)
            || Asset->SkeletalBodySetups[Index]->bSkipScaleFromAnimation != Cached.bSkipScale)
            return Reject(OutError, TEXT("A retained query body identity, bone mapping or scale policy changed."));
        const FTransform& World = BoneWorldTransforms[Cached.BoneIndex];
        if (World.ContainsNaN() || !World.GetRotation().IsNormalized() || World.GetScale3D().GetMin() <= 0.0)
            return Reject(OutError, TEXT("Completed query bone transform is invalid."));
    }

    Profile::RecordElapsed(Profile::EPhase::QueryValidate, ValidateStarted);
    const double ScaleStarted = Profile::Timestamp();
    for (FBody& Cached : Bodies)
    {
        const FTransform& World = BoneWorldTransforms[Cached.BoneIndex];
        auto& External = Cached.Actor->GetGameThreadAPI();
        if (!Cached.bSkipScale)
        {
            const FVector Requested = bUniformMeshScale ? World.GetScale3D() : MeshScale;
            // UE UpdateBodyScale stores a shape-adjusted scale. Comparing only that to the original
            // requested scale can rebuild unchanged locked/uniform primitives on every animation update.
            // Reuse only with the EXACT same request, applied scale and native geometry identity.
            if (!Cached.bHasScale || !Cached.RequestedScale.Equals(Requested, 0.0)
                || !Cached.AppliedScale.Equals(Cached.Instance->Scale3D, 0.0) || Cached.Geometry != External.GetGeometry())
            {
                const bool bAlreadyApplied = Cached.Instance->Scale3D.Equals(Requested); // Same tolerance as UE.
                ++ScaleUpdateCalls;
                if (!Cached.Instance->UpdateBodyScale(Requested) && !bAlreadyApplied)
                    return Reject(OutError, TEXT("UE failed to update the retained query body's requested scale."));
                Cached.RequestedScale = Requested;
                Cached.AppliedScale = Cached.Instance->Scale3D;
                Cached.Geometry = External.GetGeometry();
                Cached.bHasScale = true;
            }
        }
    }
    Profile::RecordElapsed(Profile::EPhase::QueryScale, ScaleStarted);
    const double BodyWriteStarted = Profile::Timestamp();
    TArray<FPhysicsActorHandle, TInlineAllocator<32>> Actors;
    Actors.Reserve(Bodies.Num());
    for (const FBody& Cached : Bodies)
    {
        const FTransform& World = BoneWorldTransforms[Cached.BoneIndex];
        auto& External = Cached.Actor->GetGameThreadAPI();
        // Source contract: PhysScene_Chaos.cpp ProcessTeleportActors. No new kinematic target,
        // no velocity computation, and only one dirty notification for the position/rotation pair.
        External.SetX(World.GetTranslation(), false);
        External.SetR(World.GetRotation());
        External.UpdateShapeBounds();
        Actors.Add(Cached.Actor);
    }
    Profile::RecordElapsed(Profile::EPhase::QueryBodyWrite, BodyWriteStarted);
    Profile::FScope SceneTiming(Profile::EPhase::QuerySceneUpdate);
    // Public UE batch holds the acceleration lock once and updates the immediate query scene plus
    // the solver's pending spatial operations. Never write only the GT tree or skip its native mirror.
    Scene->UpdateActorsInAccelerationStructure(MakeArrayView(Actors));
    return true;
}
