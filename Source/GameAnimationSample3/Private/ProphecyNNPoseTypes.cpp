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

	uint32 HashBoneLayout(TConstArrayView<FName> BoneNames)
	{
		uint32 Hash = GetTypeHash(BoneNames.Num());
		for (const FName BoneName : BoneNames)
		{
			Hash = HashCombineFast(Hash, GetTypeHash(BoneName));
		}
		return Hash;
	}

	bool BoneLayoutMatches(const FProphecyNNPoseSnapshot& Snapshot, TConstArrayView<FName> BoneNames, uint32 LayoutHash)
	{
		if (Snapshot.BoneLayoutHash != LayoutHash || Snapshot.BoneNames.Num() != BoneNames.Num())
		{
			return false;
		}
		for (int32 Index = 0; Index < BoneNames.Num(); ++Index)
		{
			if (Snapshot.BoneNames[Index] != BoneNames[Index])
			{
				return false;
			}
		}
		return true;
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
	const uint32 LayoutHash = HashBoneLayout(BoneNames);

	if (!BoneLayoutMatches(Snapshot, BoneNames, LayoutHash))
	{
		Snapshot.BoneNames.Reset(BoneNames.Num());
		Snapshot.BoneNames.Append(BoneNames.GetData(), BoneNames.Num());
		Snapshot.BoneLayoutHash = LayoutHash;
	}

	Snapshot.LocalTransforms.SetNumUninitialized(LocalTransforms.Num());
	for (int32 Index = 0; Index < LocalTransforms.Num(); ++Index)
	{
		FTransform& LocalTransform = Snapshot.LocalTransforms[Index];
		LocalTransform = LocalTransforms[Index];
		LocalTransform.NormalizeRotation();
	}

	Snapshot.Revision = AllocatePoseRevision();
	Snapshot.SourceTimeSeconds = SourceTimeSeconds;
	Snapshot.PreviousComponentTransforms.Reset();
	Snapshot.ComponentTransforms.Reset();
	Snapshot.PreviousComponentWorldTransform = FTransform::Identity;
	Snapshot.ComponentWorldTransform = FTransform::Identity;
	Snapshot.bHasComponentWorldTransform = false;
}

void FProphecyNNPoseStore::SetAgentLocalPose(
	int32 AgentId,
	TConstArrayView<FName> BoneNames,
	TConstArrayView<FTransform> LocalTransforms,
	const FTransform& ComponentWorldTransform,
	double SourceTimeSeconds)
{
	check(BoneNames.Num() == LocalTransforms.Num());

	FWriteScopeLock Lock(GProphecyNNPoseLock);
	FProphecyNNPoseSnapshot& Snapshot = GProphecyNNPoses.FindOrAdd(AgentId);
	const uint32 LayoutHash = HashBoneLayout(BoneNames);

	if (!BoneLayoutMatches(Snapshot, BoneNames, LayoutHash))
	{
		Snapshot.BoneNames.Reset(BoneNames.Num());
		Snapshot.BoneNames.Append(BoneNames.GetData(), BoneNames.Num());
		Snapshot.BoneLayoutHash = LayoutHash;
	}

	Snapshot.LocalTransforms.SetNumUninitialized(LocalTransforms.Num());
	for (int32 Index = 0; Index < LocalTransforms.Num(); ++Index)
	{
		FTransform& LocalTransform = Snapshot.LocalTransforms[Index];
		LocalTransform = LocalTransforms[Index];
		LocalTransform.NormalizeRotation();
	}

	Snapshot.ComponentWorldTransform = ComponentWorldTransform;
	Snapshot.ComponentWorldTransform.NormalizeRotation();
	Snapshot.PreviousComponentTransforms.Reset();
	Snapshot.ComponentTransforms.Reset();
	Snapshot.PreviousComponentWorldTransform = FTransform::Identity;
	Snapshot.bHasComponentWorldTransform = true;
	Snapshot.Revision = AllocatePoseRevision();
	Snapshot.SourceTimeSeconds = SourceTimeSeconds;
}

void FProphecyNNPoseStore::SetAgentLocalPose(
	int32 AgentId,
	TConstArrayView<FName> BoneNames,
	TConstArrayView<FTransform> LocalTransforms,
	TConstArrayView<FTransform> PreviousComponentTransforms,
	TConstArrayView<FTransform> ComponentTransforms,
	const FTransform& PreviousComponentWorldTransform,
	const FTransform& ComponentWorldTransform,
	double SourceTimeSeconds)
{
	check(BoneNames.Num() == LocalTransforms.Num());
	check(BoneNames.Num() == PreviousComponentTransforms.Num());
	check(BoneNames.Num() == ComponentTransforms.Num());

	FWriteScopeLock Lock(GProphecyNNPoseLock);
	FProphecyNNPoseSnapshot& Snapshot = GProphecyNNPoses.FindOrAdd(AgentId);
	const uint32 LayoutHash = HashBoneLayout(BoneNames);
	if (!BoneLayoutMatches(Snapshot, BoneNames, LayoutHash))
	{
		Snapshot.BoneNames.Reset(BoneNames.Num());
		Snapshot.BoneNames.Append(BoneNames.GetData(), BoneNames.Num());
		Snapshot.BoneLayoutHash = LayoutHash;
	}

	auto CopyNormalized = [](TArray<FTransform>& Destination, TConstArrayView<FTransform> Source)
	{
		Destination.SetNumUninitialized(Source.Num());
		for (int32 Index = 0; Index < Source.Num(); ++Index)
		{
			Destination[Index] = Source[Index];
			Destination[Index].NormalizeRotation();
		}
	};
	CopyNormalized(Snapshot.LocalTransforms, LocalTransforms);
	CopyNormalized(Snapshot.PreviousComponentTransforms, PreviousComponentTransforms);
	CopyNormalized(Snapshot.ComponentTransforms, ComponentTransforms);
	Snapshot.PreviousComponentWorldTransform = PreviousComponentWorldTransform;
	Snapshot.PreviousComponentWorldTransform.NormalizeRotation();
	Snapshot.ComponentWorldTransform = ComponentWorldTransform;
	Snapshot.ComponentWorldTransform.NormalizeRotation();
	Snapshot.bHasComponentWorldTransform = true;
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
	TArray<FName, TInlineAllocator<64>> IncomingBoneNames;
	IncomingBoneNames.Reserve(BonePoses.Num());
	for (const FProphecyNNBonePose& BonePose : BonePoses)
	{
		IncomingBoneNames.Add(BonePose.BoneName);
	}
	const uint32 LayoutHash = HashBoneLayout(IncomingBoneNames);

	if (!BoneLayoutMatches(Snapshot, IncomingBoneNames, LayoutHash))
	{
		Snapshot.BoneNames.Reset(IncomingBoneNames.Num());
		Snapshot.BoneNames.Append(IncomingBoneNames.GetData(), IncomingBoneNames.Num());
		Snapshot.BoneLayoutHash = LayoutHash;
	}
	Snapshot.LocalTransforms.SetNumUninitialized(BonePoses.Num());

	for (int32 Index = 0; Index < BonePoses.Num(); ++Index)
	{
		FTransform& LocalTransform = Snapshot.LocalTransforms[Index];
		LocalTransform = BonePoses[Index].LocalTransform;
		LocalTransform.NormalizeRotation();
	}

	Snapshot.Revision = AllocatePoseRevision();
	Snapshot.SourceTimeSeconds = SourceTimeSeconds;
	Snapshot.PreviousComponentTransforms.Reset();
	Snapshot.ComponentTransforms.Reset();
	Snapshot.PreviousComponentWorldTransform = FTransform::Identity;
	Snapshot.ComponentWorldTransform = FTransform::Identity;
	Snapshot.bHasComponentWorldTransform = false;
}

bool FProphecyNNPoseStore::GetAgentLocalPose(int32 AgentId, FProphecyNNPoseSnapshot& OutSnapshot)
{
	if (GetAgentLocalPoseIfNewer(AgentId, 0, OutSnapshot))
	{
		return true;
	}
	OutSnapshot.Reset();
	return false;
}

bool FProphecyNNPoseStore::GetAgentLocalPoseIfNewer(
	int32 AgentId,
	uint32 KnownRevision,
	FProphecyNNPoseSnapshot& OutSnapshot)
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	if (const FProphecyNNPoseSnapshot* Snapshot = GProphecyNNPoses.Find(AgentId))
	{
		if (!Snapshot->IsValid() || Snapshot->Revision == KnownRevision)
		{
			return false;
		}
		OutSnapshot = *Snapshot;
		return true;
	}
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
