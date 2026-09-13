#pragma once

#include "Animation/AnimInstance.h"
#include "Containers/ArrayView.h"
#include "ProphecyJoltPoseAnimInstance.generated.h"

class USkeletalMesh;
class FProphecyJoltPoseAnimInstanceProxy;

DECLARE_DELEGATE_RetVal_OneParam(bool, FProphecyJoltPostEvaluateQueryCommit, FString&);

/** Presents completed physics data through normal skeletal evaluation. Does not step or query physics. */
UCLASS(Transient, Blueprintable, BlueprintType)
class GAMEANIMATIONSAMPLE3_API UProphecyJoltPoseAnimInstance : public UAnimInstance
{
    GENERATED_BODY()

public:
    /**
     * Game-thread publication in the owning mesh reference-skeleton order. The pose must include all
     * mesh bones, independently of the current LOD. Revision must increase and be nonzero. Failure
     * preserves the last valid published frame. PreUpdate copies the frame for worker-only evaluation.
     */
    bool PublishCompletedLocalPose(TConstArrayView<FTransform> LocalTransforms, uint64 Revision, FString& OutError);
    // Game-thread clear permits a new revision sequence; evaluation returns reference pose until publication.
    void ClearCompletedLocalPose();
    uint64 GetCompletedPoseRevision() const { return CompletedRevision; }
    // GT synchronous one-shot after this native proxy's PostEvaluate, before bone finalization.
    // Caller clears it after RefreshBoneTransforms on every path.
    bool ArmPostEvaluateQueryCommit(FProphecyJoltPostEvaluateQueryCommit Commit, uint64 Revision, FString& OutError);
    void ClearPostEvaluateQueryCommit();
    bool GetPostEvaluateQueryCommitResult(uint64 Revision, FString& OutError) const;

protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;

private:
    friend class FProphecyJoltPoseAnimInstanceProxy;
    void CommitPostEvaluateQueries();
    FProphecyJoltPostEvaluateQueryCommit QueryCommit;
    uint64 QueryCommitRevision = 0;
    bool bQueryCommitAttempted = false;
    bool bQueryCommitSucceeded = false;
    FString QueryCommitError;
    TArray<FTransform> CompletedLocalTransforms;
    TWeakObjectPtr<USkeletalMesh> PublishedMesh;
    uint64 CompletedRevision = 0;
    // Separate serial invalidates proxy snapshots when Clear is followed by reuse of a source revision.
    uint64 PublicationSerial = 0;
};
