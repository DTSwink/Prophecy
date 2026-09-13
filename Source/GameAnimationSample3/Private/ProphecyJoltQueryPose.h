#pragma once

#include "CoreMinimal.h"
#include "Physics/PhysicsInterfaceCore.h"

class USkeletalMeshComponent;
class UPhysicsAsset;
struct FBodyInstance;
namespace Chaos { class FImplicitObject; }

/** Game-thread publisher for the retained UE query bodies. Does not drive a Chaos kinematic trajectory. */
class FProphecyJoltQueryPose
{
public:
    bool Initialize(USkeletalMeshComponent& Mesh, FString& OutError);
    bool Publish(USkeletalMeshComponent& Mesh, TConstArrayView<FTransform> BoneWorldTransforms, FString& OutError);
    uint64 GetScaleUpdateCalls() const { return ScaleUpdateCalls; }

private:
    struct FBody
    {
        FBodyInstance* Instance = nullptr; // Compared with the live mesh slot before dereferencing.
        FPhysicsActorHandle Actor = nullptr;
        int32 BoneIndex = INDEX_NONE;
        bool bSkipScale = false;
        bool bHasScale = false;
        FVector RequestedScale = FVector::ZeroVector;
        FVector AppliedScale = FVector::ZeroVector;
        const Chaos::FImplicitObject* Geometry = nullptr;
    };
    bool ValidateMesh(USkeletalMeshComponent& Mesh, FString& OutError) const;
    TWeakObjectPtr<USkeletalMeshComponent> BoundMesh;
    TWeakObjectPtr<UPhysicsAsset> BoundAsset;
    TArray<FBody> Bodies;
    uint64 ScaleUpdateCalls = 0;
};
