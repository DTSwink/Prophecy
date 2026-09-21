#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyNNInterpolation.h"

#include "Misc/ScopeRWLock.h"

namespace
{
	FRWLock GProphecyNNPoseLock;
	TMap<int32, FProphecyNNPoseSnapshot> GProphecyNNPoses;
	TMap<int32, EProphecyNNInterpolationMode> GInterpolationModes;
	TSet<int32> GProphecyNNRigidForearms;
	TSet<int32> GProphecyNNRigidCalves;
	struct FKickFootExtension { float Leeway=0; FVector Reference[2]; };
	TMap<int32,FKickFootExtension> GKickFootExtensions;
	TMap<int32,FVector2D> GKickFootReturns;
	void ApplyKickExtension(const FKickFootExtension& Kick,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,
		const FVector2D* Returning=nullptr)
	{
		const FName Feet[]={TEXT("foot_l"),TEXT("foot_r")},Calves[]={TEXT("calf_l"),TEXT("calf_r")},Toes[]={TEXT("ball_l"),TEXT("ball_r")};
		for (int Side=0;Side<2;++Side)
		{
			const int32 F=Names.IndexOfByKey(Feet[Side]),C=Names.IndexOfByKey(Calves[Side]),T=Names.IndexOfByKey(Toes[Side]);
			if (!Pose.IsValidIndex(F) || !Pose.IsValidIndex(C)) continue;
			const FVector Nominal=Pose[C].TransformVector(Kick.Reference[Side]),Axis=Nominal.GetSafeNormal();
			const FVector Origin=Pose[C].GetTranslation()+Nominal;
			const double Extension=FMath::Clamp(Returning ? (*Returning)[Side]
				: FVector::DotProduct(Pose[F].GetTranslation()-Origin,Axis),0.,double(Kick.Leeway));
			const FVector End=Origin+Axis*Extension,Shift=End-Pose[F].GetTranslation();
			Pose[F].SetTranslation(End);
			if (Pose.IsValidIndex(T)) Pose[T].AddToTranslation(Shift);
		}
	}
	struct FPresentationSample
	{
		double SourceTimeSeconds = 0.0;
		float Alpha = 0.0f;
	};
	TMap<int32, FPresentationSample> GProphecyNNPresentation;
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

void FProphecyNNPoseStore::SetInterpolationMode(int32 AgentId, EProphecyNNInterpolationMode Mode)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (Mode == EProphecyNNInterpolationMode::HermiteSlerp) GInterpolationModes.Add(AgentId, Mode);
	else GInterpolationModes.Remove(AgentId);
}

void FProphecyNNPoseStore::TranslateAgentWorldPose(int32 AgentId, const FVector& WorldDelta)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (auto* Snapshot = GProphecyNNPoses.Find(AgentId))
	{
		Snapshot->PreviousComponentWorldTransform.AddToTranslation(WorldDelta);
		Snapshot->ComponentWorldTransform.AddToTranslation(WorldDelta);
		Snapshot->Revision = AllocatePoseRevision();
	}
}

void ProphecyNNPresentation::Publish(int32 AgentId, double SourceTimeSeconds, float Alpha)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	FPresentationSample& Sample = GProphecyNNPresentation.FindOrAdd(AgentId);
	Sample.SourceTimeSeconds = SourceTimeSeconds;
	Sample.Alpha = Alpha;
}

void ProphecyNNPresentation::SetKickFootExtension(int32 AgentId,float LeewayCm,
	const FVector& LeftReference,const FVector& RightReference)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (LeewayCm>0)
	{
		GKickFootExtensions.Add(AgentId,FKickFootExtension{LeewayCm,{LeftReference,RightReference}});
		return;
	}
	GKickFootReturns.Remove(AgentId);
	const auto* Previous=GKickFootExtensions.Find(AgentId);
	if (!Previous) return;
	// The 60 Hz return can finish between two 30 Hz publications. A hard clamp
	// must not use the last slightly stretched local offset as its new rest length.
	if (auto* Pose=GProphecyNNPoses.Find(AgentId); Pose && GProphecyNNRigidCalves.Contains(AgentId)
		&& Pose->CalfClampLeewayCm==0)
	{
		const FName Feet[]={TEXT("foot_l"),TEXT("foot_r")};
		for (int Side=0;Side<2;++Side)
		{
			const int32 Index=Pose->BoneNames.IndexOfByKey(Feet[Side]);
			if (Pose->LocalTransforms.IsValidIndex(Index)) Pose->LocalTransforms[Index].SetTranslation(
				Pose->CalfClampLengths[Side]>0 ? Previous->Reference[Side].GetSafeNormal()*Pose->CalfClampLengths[Side] : Previous->Reference[Side]);
		}
		Pose->Revision=AllocatePoseRevision();
	}
	GKickFootExtensions.Remove(AgentId);
}

bool ProphecyNNPresentation::ApplyKickFootExtension(int32 AgentId,TConstArrayView<FName> Names,TArrayView<FTransform> Pose)
{
	FKickFootExtension Kick;
	FVector2D Returning; bool HasReturn=false;
	{
		FReadScopeLock Lock(GProphecyNNPoseLock);
		const auto* Value=GKickFootExtensions.Find(AgentId);
		if (!Value) return false;
		Kick=*Value;
		if (const auto* R=GKickFootReturns.Find(AgentId)) { Returning=*R; HasReturn=true; }
	}
	ApplyKickExtension(Kick,Names,Pose,HasReturn ? &Returning : nullptr); return true;
}

void ProphecyNNPresentation::SetKickFootReturn(int32 AgentId,bool Returning,const FVector2D& ExtensionCm)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (Returning && GKickFootExtensions.Contains(AgentId)) GKickFootReturns.Add(AgentId,ExtensionCm);
	else GKickFootReturns.Remove(AgentId);
}

float ProphecyNNPresentation::Resolve(int32 AgentId, double SourceTimeSeconds, double WorldTimeSeconds,
	float /*FrameDeltaSeconds*/, float PoseIntervalSeconds, bool bInterpolate)
{
	if (!bInterpolate) return 1.0f;
	{
		FReadScopeLock Lock(GProphecyNNPoseLock);
		if (const FPresentationSample* Sample = GProphecyNNPresentation.Find(AgentId))
		{
			if (Sample->SourceTimeSeconds == SourceTimeSeconds) return Sample->Alpha;
		}
	}
	// Unmanaged sources use their source clock with the same continuous timing.
	// Explicit bInterpolate=false above remains an intentional exact-pose override.
	return FromRemainder(float(WorldTimeSeconds - SourceTimeSeconds), PoseIntervalSeconds);
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
	double SourceTimeSeconds,
	bool bRigidForearms, bool bRigidCalves, float CalfClampLeewayCm, FVector2D CalfClampLengths,
	const FProphecyNNAttackHandClamp& HandClamp, const FProphecyNNForearmClamp& ForearmClamp)
{
	check(BoneNames.Num() == LocalTransforms.Num());
	check(BoneNames.Num() == PreviousComponentTransforms.Num());
	check(BoneNames.Num() == ComponentTransforms.Num());

	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (bRigidForearms) GProphecyNNRigidForearms.Add(AgentId);
	else GProphecyNNRigidForearms.Remove(AgentId);
	if (bRigidCalves) GProphecyNNRigidCalves.Add(AgentId);
	else GProphecyNNRigidCalves.Remove(AgentId);
	FProphecyNNPoseSnapshot& Snapshot = GProphecyNNPoses.FindOrAdd(AgentId);
	ProphecyNNInterpolation::Prepare(Snapshot, GInterpolationModes.FindRef(AgentId), BoneNames,
		PreviousComponentTransforms, ComponentTransforms, PreviousComponentWorldTransform, ComponentWorldTransform, SourceTimeSeconds);
	Snapshot.CalfClampLeewayCm = CalfClampLeewayCm;
	Snapshot.AttackHandClamp = HandClamp;
	Snapshot.ForearmClamp = ForearmClamp;
	Snapshot.CalfClampLengths = CalfClampLengths;
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
	GInterpolationModes.Remove(AgentId);
	GProphecyNNRigidForearms.Remove(AgentId);
	GProphecyNNRigidCalves.Remove(AgentId);
	GKickFootExtensions.Remove(AgentId);
	GKickFootReturns.Remove(AgentId);
	GProphecyNNPresentation.Remove(AgentId);
}

void FProphecyNNPoseStore::ClearAllPoses()
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	GProphecyNNPoses.Reset();
	GInterpolationModes.Reset();
	GProphecyNNRigidForearms.Reset();
	GProphecyNNRigidCalves.Reset();
	GKickFootExtensions.Reset();
	GKickFootReturns.Reset();
	GProphecyNNPresentation.Reset();
}

bool FProphecyNNPoseStore::UsesAttackPresentation(int32 AgentId)
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	return GProphecyNNRigidForearms.Contains(AgentId);
}

void FProphecyNNPoseStore::ApplyRigidForearms(int32 AgentId, const FProphecyNNPoseSnapshot& Snapshot,
	TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms)
{
	if (!Snapshot.ForearmClamp.bEnabled)
	{
		if (!Snapshot.AttackHandClamp.bEnabled) return;
		FReadScopeLock Lock(GProphecyNNPoseLock);
		if (!GProphecyNNRigidForearms.Contains(AgentId)) return;
	}
	static const FName Hands[] = { TEXT("hand_l"), TEXT("hand_r") };
	static const FName Forearms[] = { TEXT("lowerarm_l"), TEXT("lowerarm_r") };
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const int32 Hand = BoneNames.IndexOfByKey(Hands[Side]);
		const int32 Forearm = BoneNames.IndexOfByKey(Forearms[Side]);
		const int32 SourceHand = Snapshot.BoneNames.IndexOfByKey(Hands[Side]);
		if (Transforms.IsValidIndex(Hand) && Transforms.IsValidIndex(Forearm) &&
			Snapshot.LocalTransforms.IsValidIndex(SourceHand))
		{
			if (Snapshot.ForearmClamp.bEnabled)
			{
				Transforms[Hand].SetTranslation(Snapshot.ForearmClamp.ClampHand(Transforms[Hand].GetTranslation(),
					Transforms[Forearm], Snapshot.LocalTransforms[SourceHand].GetTranslation(), Side));
				continue;
			}
			const FVector Offset = Snapshot.AttackHandClamp.LeewayCm > 0
				? Snapshot.AttackHandClamp.ReferenceOffsets[Side]
				: Snapshot.LocalTransforms[SourceHand].GetTranslation();
			Transforms[Hand].SetTranslation(FProphecyNNAttackHandClamp::ClampPosition(
				Transforms[Hand].GetTranslation(), Transforms[Forearm].TransformPosition(Offset),
				Snapshot.AttackHandClamp.LeewayCm));
		}
	}
}

void FProphecyNNPoseStore::ApplyRigidCalves(int32 AgentId, const FProphecyNNPoseSnapshot& Snapshot,
	TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms)
{
	FKickFootExtension Kick;
	FVector2D Returning; bool HasReturn=false;
	{
		FReadScopeLock Lock(GProphecyNNPoseLock);
		if (const auto* Value=GKickFootExtensions.Find(AgentId)) Kick=*Value;
		if (const auto* R=GKickFootReturns.Find(AgentId)) { Returning=*R; HasReturn=true; }
		if (Kick.Leeway<=0 && !GProphecyNNRigidCalves.Contains(AgentId)) return;
	}
	if (Kick.Leeway>0) { ApplyKickExtension(Kick,BoneNames,Transforms,HasReturn ? &Returning : nullptr); return; }
	static const FName Feet[] = { TEXT("foot_l"), TEXT("foot_r") };
	static const FName Calves[] = { TEXT("calf_l"), TEXT("calf_r") };
	static const FName Toes[] = { TEXT("ball_l"), TEXT("ball_r") };
	for (int32 Side = 0; Side < 2; ++Side)
	{
		const int32 Foot = BoneNames.IndexOfByKey(Feet[Side]);
		const int32 Calf = BoneNames.IndexOfByKey(Calves[Side]);
		const int32 SourceFoot = Snapshot.BoneNames.IndexOfByKey(Feet[Side]);
		if (!Transforms.IsValidIndex(Foot) || !Transforms.IsValidIndex(Calf)
			|| !Snapshot.LocalTransforms.IsValidIndex(SourceFoot)) continue;
		FVector End;
		if (Snapshot.CalfClampLeewayCm > 0 && Snapshot.CalfClampLengths[Side] > 0)
		{
			const FVector Reference = Snapshot.LocalTransforms[SourceFoot].GetTranslation().GetSafeNormal() * Snapshot.CalfClampLengths[Side];
			const FVector Nominal = Transforms[Calf].TransformVector(Reference);
			const FVector Delta = Transforms[Foot].GetTranslation()-Transforms[Calf].GetTranslation();
			const double Radius = Delta.Length(), Length = Nominal.Length();
			const double Allowed = FMath::Clamp(Radius, FMath::Max(0.,Length-Snapshot.CalfClampLeewayCm),Length+Snapshot.CalfClampLeewayCm);
			if (Allowed == Radius) continue;
			End = Transforms[Calf].GetTranslation() + Delta.GetSafeNormal(UE_SMALL_NUMBER,Nominal.GetSafeNormal()) * Allowed;
		}
		else End = Transforms[Calf].TransformPosition(Snapshot.LocalTransforms[SourceFoot].GetTranslation());
		const FVector Shift = End - Transforms[Foot].GetTranslation();
		Transforms[Foot].SetTranslation(End);
		const int32 Toe = BoneNames.IndexOfByKey(Toes[Side]);
		if (Transforms.IsValidIndex(Toe)) Transforms[Toe].AddToTranslation(Shift);
	}
}

int32 FProphecyNNPoseStore::NumPoses()
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	return GProphecyNNPoses.Num();
}
