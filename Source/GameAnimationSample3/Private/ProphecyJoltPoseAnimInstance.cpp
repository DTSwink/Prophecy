#include "ProphecyJoltPoseAnimInstance.h"

#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeBase.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "ProphecyJoltPose.h"
#include "ProphecyJoltCharacterProfiling.h"

class FProphecyJoltPoseAnimInstanceProxy final : public FAnimInstanceProxy
{
public:
    explicit FProphecyJoltPoseAnimInstanceProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

protected:
    virtual void UpdateAnimationNode(const FAnimationUpdateContext& InContext) override
    {
        if (HasRootNode())
        {
            FAnimInstanceProxy::UpdateAnimationNode(InContext);
            return;
        }
        // The native snapshot graph has no FAnimNode root. Record its actual update
        // here, as native UE proxies do, so Refresh does not repeat TickAnimation.
        UpdateCounter.Increment();
    }

    virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override
    {
        ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ProxyPreUpdate);
        FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
        check(IsInGameThread());
        const auto* Instance = Cast<UProphecyJoltPoseAnimInstance>(InAnimInstance);
        const USkeletalMeshComponent* MeshComponent = Instance ? Instance->GetSkelMeshComponent() : nullptr;
        const USkeletalMesh* Mesh = MeshComponent ? MeshComponent->GetSkeletalMeshAsset() : nullptr;
        if (!Instance || !Mesh || Instance->PublishedMesh.Get() != Mesh || Instance->CompletedRevision == 0
            || Instance->CompletedLocalTransforms.Num() != Mesh->GetRefSkeleton().GetNum())
        {
            Snapshot.Reset();
            SnapshotSerial = 0;
            return;
        }
        if (SnapshotSerial != Instance->PublicationSerial)
        {
            Snapshot = Instance->CompletedLocalTransforms;
            SnapshotSerial = Instance->PublicationSerial;
        }
    }

    virtual void PostEvaluate(UAnimInstance* InAnimInstance) override
    {
        { ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ProxyPostEvaluateBase);
          FAnimInstanceProxy::PostEvaluate(InAnimInstance); }
        check(IsInGameThread());
        if (auto* Instance = Cast<UProphecyJoltPoseAnimInstance>(InAnimInstance)) Instance->CommitPostEvaluateQueries();
    }

    virtual bool Evaluate(FPoseContext& Output) override
    {
        ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ProxyEvaluate);
        // UE initializes this evaluation context to the reference pose before dispatching the proxy.
        if (Snapshot.IsEmpty()) return true;

        // RequiredBones belongs to the evaluation context. This reads no UObject or physics state.
        // Compact indices map to MESH reference indices, not USkeleton animation indices. Iterating
        // the supplied compact layout handles LOD changes and does not allocate on the worker thread.
        const FBoneContainer& EvaluationBones = Output.Pose.GetBoneContainer();
        const TArray<FBoneIndexType>& MeshBoneIndices = EvaluationBones.GetBoneIndicesArray();
        for (int32 CompactIndex = 0; CompactIndex < MeshBoneIndices.Num(); ++CompactIndex)
        {
            const int32 MeshBoneIndex = MeshBoneIndices[CompactIndex];
            const FCompactPoseBoneIndex CompactBone(CompactIndex);
            if (Snapshot.IsValidIndex(MeshBoneIndex) && Output.Pose.IsValidIndex(CompactBone))
                Output.Pose[CompactBone] = Snapshot[MeshBoneIndex];
        }
        Output.Pose.NormalizeRotations();
        return true;
    }

private:
    virtual void PreEvaluateAnimation(UAnimInstance* InAnimInstance) override
    {
        ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ProxyPreEvaluate);
        FAnimInstanceProxy::PreEvaluateAnimation(InAnimInstance);
    }

    TArray<FTransform> Snapshot;
    uint64 SnapshotSerial = 0;
};

bool UProphecyJoltPoseAnimInstance::PublishCompletedLocalPose(TConstArrayView<FTransform> LocalTransforms,
    uint64 Revision, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread())
    {
        OutError = TEXT("Completed pose publication requires the game thread.");
        return false;
    }
    USkeletalMeshComponent* MeshComponent = GetSkelMeshComponent();
    USkeletalMesh* Mesh = MeshComponent ? MeshComponent->GetSkeletalMeshAsset() : nullptr;
    if (!Mesh || LocalTransforms.Num() != Mesh->GetRefSkeleton().GetNum())
    {
        OutError = TEXT("Completed pose must match every bone in the owning skeletal mesh's reference skeleton.");
        return false;
    }
    if (Revision == 0 || (PublishedMesh.Get() == Mesh && Revision <= CompletedRevision)
        || PublicationSerial == MAX_uint64)
    {
        OutError = TEXT("Completed pose revision must increase and be nonzero; publication serial must not wrap.");
        return false;
    }
    if (!ProphecyJolt::Pose::ValidateLocalPose(LocalTransforms, OutError)) return false;
    CompletedLocalTransforms.Reset(LocalTransforms.Num());
    CompletedLocalTransforms.Append(LocalTransforms.GetData(), LocalTransforms.Num());
    PublishedMesh = Mesh;
    CompletedRevision = Revision;
    ++PublicationSerial;
    return true;
}

bool UProphecyJoltPoseAnimInstance::ArmPostEvaluateQueryCommit(
    FProphecyJoltPostEvaluateQueryCommit Commit, uint64 Revision, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread())
    {
        OutError = TEXT("The query commit hook requires the game thread.");
        return false;
    }
    USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
    if (GetClass() != StaticClass() || !Mesh || !static_cast<const USkeletalMeshComponent*>(Mesh)->GetLinkedAnimInstances().IsEmpty()
        || (Mesh->GetPostProcessInstance() && !Mesh->GetDisablePostProcessBlueprint()) || QueryCommit.IsBound() || !Commit.IsBound()
        || Revision == 0 || Revision != CompletedRevision)
    {
        OutError = TEXT("The query hook requires this exact native pose instance, no linked or enabled postprocess evaluator, and its current revision.");
        return false;
    }
    QueryCommit = MoveTemp(Commit);
    QueryCommitRevision = Revision;
    bQueryCommitAttempted = bQueryCommitSucceeded = false;
    QueryCommitError.Reset();
    return true;
}

void UProphecyJoltPoseAnimInstance::CommitPostEvaluateQueries()
{
    check(IsInGameThread());
    if (!QueryCommit.IsBound()) return;
    FProphecyJoltPostEvaluateQueryCommit Commit = MoveTemp(QueryCommit);
    QueryCommit.Unbind();
    bQueryCommitAttempted = true;
    if (QueryCommitRevision != CompletedRevision)
    {
        QueryCommitError = TEXT("The pose revision changed before its query commit.");
        bQueryCommitSucceeded = false;
        return;
    }
    // Arm ran before Refresh; the intervening post-evaluation callbacks can change eligibility.
    USkeletalMeshComponent* Mesh = GetSkelMeshComponent();
    if (!IsValid(this) || !IsValid(Mesh) || GetClass() != StaticClass()
        || !static_cast<const USkeletalMeshComponent*>(Mesh)->GetLinkedAnimInstances().IsEmpty()
        || (Mesh->GetPostProcessInstance() && !Mesh->GetDisablePostProcessBlueprint()))
    {
        QueryCommitError = TEXT("The native pose or disabled-postprocess query contract changed during post-evaluation.");
        bQueryCommitSucceeded = false;
        return;
    }
    bQueryCommitSucceeded = Commit.Execute(QueryCommitError);
}

void UProphecyJoltPoseAnimInstance::ClearPostEvaluateQueryCommit()
{
    check(IsInGameThread());
    QueryCommit.Unbind();
}

bool UProphecyJoltPoseAnimInstance::GetPostEvaluateQueryCommitResult(uint64 Revision, FString& OutError) const
{
    OutError.Reset();
    if (!IsInGameThread() || !bQueryCommitAttempted || QueryCommitRevision != Revision)
    {
        OutError = TEXT("The completed pose did not invoke its synchronous query commit.");
        return false;
    }
    OutError = QueryCommitError;
    return bQueryCommitSucceeded;
}

void UProphecyJoltPoseAnimInstance::ClearCompletedLocalPose()
{
    check(IsInGameThread());
    ClearPostEvaluateQueryCommit();
    CompletedLocalTransforms.Reset();
    PublishedMesh.Reset();
    CompletedRevision = 0;
    if (PublicationSerial < MAX_uint64) ++PublicationSerial;
}

FAnimInstanceProxy* UProphecyJoltPoseAnimInstance::CreateAnimInstanceProxy()
{
    return new FProphecyJoltPoseAnimInstanceProxy(this);
}

void UProphecyJoltPoseAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
    delete InProxy;
}
