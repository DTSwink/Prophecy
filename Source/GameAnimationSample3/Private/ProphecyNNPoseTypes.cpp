#include "ProphecyNNPoseTypes.h"

#include "Misc/ScopeRWLock.h"

namespace
{
	FRWLock GProphecyNNPoseLock;
	TMap<int32, FProphecyNNPoseSnapshot> GProphecyNNPoses;
	uint32 GProphecyNNNextRevision = 1;

	uint32 AllocatePoseRevision()
	{
		const uint32 Revision = GProphecyNNNextRevision++;
		if (GProphecyNNNextRevision == 0)
		{
			GProphecyNNNextRevision = 1;
		}
		return Revision;
	}
}

void FProphecyNNPoseStore::SetAgentLocalPose(
	int32 AgentId,
	TConstArrayView<FName> BoneNames,
	TConstArrayView<FTransform> LocalTransforms,
	double SourceTimeSeconds)
{
	check(BoneNames.Num() == LocalTransforms.Num());

	FWriteScopeLock Lock(GProphecyNNPoseLock);
	FProphecyNNPoseSnapshot& Snapshot = GProphecyNNPoses.FindOrAdd(AgentId);

	Snapshot.BoneNames.Reset(BoneNames.Num());
	Snapshot.BoneNames.Append(BoneNames.GetData(), BoneNames.Num());

	Snapshot.LocalTransforms.Reset(LocalTransforms.Num());
	Snapshot.LocalTransforms.Append(LocalTransforms.GetData(), LocalTransforms.Num());
	for (FTransform& LocalTransform : Snapshot.LocalTransforms)
	{
		LocalTransform.NormalizeRotation();
	}

	Snapshot.Revision = AllocatePoseRevision();
	Snapshot.SourceTimeSeconds = SourceTimeSeconds;
}

void FProphecyNNPoseStore::SetAgentLocalPose(
	int32 AgentId,
	TConstArrayView<FProphecyNNBonePose> BonePoses,
	double SourceTimeSeconds)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	FProphecyNNPoseSnapshot& Snapshot = GProphecyNNPoses.FindOrAdd(AgentId);

	Snapshot.BoneNames.Reset(BonePoses.Num());
	Snapshot.LocalTransforms.Reset(BonePoses.Num());

	for (const FProphecyNNBonePose& BonePose : BonePoses)
	{
		Snapshot.BoneNames.Add(BonePose.BoneName);

		FTransform LocalTransform = BonePose.LocalTransform;
		LocalTransform.NormalizeRotation();
		Snapshot.LocalTransforms.Add(LocalTransform);
	}

	Snapshot.Revision = AllocatePoseRevision();
	Snapshot.SourceTimeSeconds = SourceTimeSeconds;
}

bool FProphecyNNPoseStore::GetAgentLocalPose(int32 AgentId, FProphecyNNPoseSnapshot& OutSnapshot)
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	if (const FProphecyNNPoseSnapshot* Snapshot = GProphecyNNPoses.Find(AgentId))
	{
		OutSnapshot = *Snapshot;
		return OutSnapshot.IsValid();
	}

	OutSnapshot.Reset();
	return false;
}

void FProphecyNNPoseStore::ClearAgentPose(int32 AgentId)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	GProphecyNNPoses.Remove(AgentId);
}

void FProphecyNNPoseStore::ClearAllPoses()
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	GProphecyNNPoses.Reset();
}

int32 FProphecyNNPoseStore::NumPoses()
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	return GProphecyNNPoses.Num();
}
