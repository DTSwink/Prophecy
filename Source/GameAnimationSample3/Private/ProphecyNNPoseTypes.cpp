#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyNNInterpolation.h"
#include "ProphecyRecoveryLegLength.h"
#include "ProphecyKneePopSmoothing.h"
#include "ProphecyAttackStartInertia.h"
#include "HAL/IConsoleManager.h"

#include "Misc/ScopeRWLock.h"

namespace
{
#if WITH_EDITOR
    TAutoConsoleVariable<int32> CVarRecoveryLengthInterpolation(TEXT("Prophecy.Recovery.LengthInterpolation"),1,
        TEXT("Editor comparison: sample returning calf length with the pose interpolation instead of the latest live value."));
#endif
    bool UseRecoveryLengthInterpolation()
    {
#if WITH_EDITOR
        return CVarRecoveryLengthInterpolation.GetValueOnAnyThread()!=0;
#else
        return true;
#endif
    }
	FRWLock GProphecyNNPoseLock;
	TMap<int32, FProphecyNNPoseSnapshot> GProphecyNNPoses;
	TMap<int32, EProphecyNNInterpolationMode> GInterpolationModes;
	TSet<int32> GProphecyNNRigidForearms;
	TSet<int32> GProphecyNNRigidCalves;
	struct FRecoveryLegLengths { FVector2D Upper,Lower; };
	TMap<int32,FRecoveryLegLengths> GRecoveryLegLengths;
	TMap<int32,float> GKneePopSmoothing;
	struct FKneeBendFrames { FVector LocalPole[2]={FVector::ZeroVector,FVector::ZeroVector}; };
	TMap<int32,FKneeBendFrames> GKneeBendFrames;
	// Called only on publication/configuration under the pose-store write lock.
	// Remember a reliable bend in thigh space; near extension the point-derived
	// plane is ill-conditioned and must not replace this anatomical reference.
	void CaptureKneeBendFrames(int32 AgentId,const FProphecyNNPoseSnapshot& Pose,float Zone)
	{
		auto& Frames=GKneeBendFrames.FindOrAdd(AgentId);
		for (int32 Side=0;Side<2;++Side)
		{
			const int32 H=Pose.BoneNames.IndexOfByKey(Side==0?FName(TEXT("thigh_l")):FName(TEXT("thigh_r")));
			const int32 K=Pose.BoneNames.IndexOfByKey(Side==0?FName(TEXT("calf_l")):FName(TEXT("calf_r")));
			const int32 F=Pose.BoneNames.IndexOfByKey(Side==0?FName(TEXT("foot_l")):FName(TEXT("foot_r")));
			for (const auto* Transforms:{&Pose.PreviousComponentTransforms,&Pose.ComponentTransforms})
			{
				if (!Transforms->IsValidIndex(H)||!Transforms->IsValidIndex(K)||!Transforms->IsValidIndex(F)) continue;
				const FVector Upper=(*Transforms)[K].GetLocation()-(*Transforms)[H].GetLocation();
				const FVector Lower=(*Transforms)[F].GetLocation()-(*Transforms)[K].GetLocation(),Delta=Upper+Lower;
				const double Reach=Upper.Length()+Lower.Length();
				if (!Frames.LocalPole[Side].IsNearlyZero() && Delta.Length()>Reach-FMath::Min(double(Zone),Reach*.25)) continue;
				const FVector Axis=Delta.GetSafeNormal();
				const FVector Pole=(Upper-Axis*FVector::DotProduct(Upper,Axis)).GetSafeNormal();
				if (!Pole.IsNearlyZero()) Frames.LocalPole[Side]=(*Transforms)[H].InverseTransformVectorNoScale(Pole);
			}
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

void ProphecyNNPresentation::SetRecoveryCalfLengths(int32 AgentId,const FVector2D& UpperCm,const FVector2D& LowerCm)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (LowerCm.X>0 && LowerCm.Y>0) GRecoveryLegLengths.Add(AgentId,{UpperCm,LowerCm});
	else GRecoveryLegLengths.Remove(AgentId);
}
bool ProphecyNNPresentation::HasRecoveryCalfLengths(int32 AgentId)
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	return !GRecoveryLegLengths.IsEmpty() && GRecoveryLegLengths.Contains(AgentId);
}

#if WITH_EDITOR
static TAutoConsoleVariable<int32> CVarSpecialKneeSmoothingOrder(
    TEXT("Prophecy.KneeSmoothing.SpecialOrder"),1,
    TEXT("Editor A/B only: 0=legacy all-mode pre-inertia smoothing; 1=locomotion plus post-entry-inertia exception."));
#endif
bool ProphecyNNPresentation::UseSpecialKneeSmoothingOrder()
{
#if WITH_EDITOR
    return CVarSpecialKneeSmoothingOrder.GetValueOnAnyThread()!=0;
#else
    return true;
#endif
}

void ProphecyNNPresentation::SetKneePopSmoothing(int32 AgentId,float SoftZoneCm)
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	if (FMath::IsFinite(SoftZoneCm) && SoftZoneCm>0)
	{
		GKneePopSmoothing.Add(AgentId,SoftZoneCm);
		if (const auto* Pose=GProphecyNNPoses.Find(AgentId)) CaptureKneeBendFrames(AgentId,*Pose,SoftZoneCm);
	}
	else { GKneePopSmoothing.Remove(AgentId);GKneeBendFrames.Remove(AgentId); }
}
bool ProphecyNNPresentation::HasKneePopSmoothing(int32 AgentId)
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	return !GKneePopSmoothing.IsEmpty() && GKneePopSmoothing.Contains(AgentId);
}

bool ProphecyNNPresentation::ReadKneePopReference(int32 Id,int32 Side,float& Zone,FVector& LocalPole)
{
    FReadScopeLock Lock(GProphecyNNPoseLock);
    if(Side<0 || Side>1 || GKneePopSmoothing.IsEmpty())return false;
    const auto* Z=GKneePopSmoothing.Find(Id);const auto* F=GKneeBendFrames.Find(Id);
    if(!Z || !F || F->LocalPole[Side].IsNearlyZero())return false;
    Zone=*Z;LocalPole=F->LocalPole[Side];return true;
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
	if (!GKneePopSmoothing.IsEmpty()) if (const float* Zone=GKneePopSmoothing.Find(AgentId))
		CaptureKneeBendFrames(AgentId,Snapshot,*Zone);
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
	GProphecyNNPresentation.Remove(AgentId);
	GRecoveryLegLengths.Remove(AgentId);
	GKneePopSmoothing.Remove(AgentId);
	GKneeBendFrames.Remove(AgentId);
}

void FProphecyNNPoseStore::ClearAllPoses()
{
	FWriteScopeLock Lock(GProphecyNNPoseLock);
	GProphecyNNPoses.Reset();
	GInterpolationModes.Reset();
	GProphecyNNRigidForearms.Reset();
	GProphecyNNRigidCalves.Reset();
	GProphecyNNPresentation.Reset();
	GRecoveryLegLengths.Reset();
	GKneePopSmoothing.Reset();
	GKneeBendFrames.Reset();
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
	TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms, float InterpolationAlpha)
{
	FRecoveryLegLengths Recovery;
	bool bRecovery=false,bRigid=false;
	float SoftZone=0;
	bool Special=false;
	FKneeBendFrames BendFrames;
	{
		FReadScopeLock Lock(GProphecyNNPoseLock);
		if (!GRecoveryLegLengths.IsEmpty()) if (const auto* Value=GRecoveryLegLengths.Find(AgentId))
		{ Recovery=*Value;bRecovery=true; }
		bRigid=GProphecyNNRigidCalves.Contains(AgentId);
		if (!GKneePopSmoothing.IsEmpty()) if (const float* Value=GKneePopSmoothing.Find(AgentId)) SoftZone=*Value;
		if (SoftZone>0)
        {
            Special=GProphecyNNRigidForearms.Contains(AgentId);
            if (const auto* Value=GKneeBendFrames.Find(AgentId)) BendFrames=*Value;
        }
		if (!bRecovery && !bRigid && SoftZone<=0) return;
	}

	static const FName Feet[] = { TEXT("foot_l"), TEXT("foot_r") };
	static const FName Calves[] = { TEXT("calf_l"), TEXT("calf_r") };
	static const FName Toes[] = { TEXT("ball_l"), TEXT("ball_r") };
	for (int32 Side = 0; (bRecovery || bRigid) && Side < 2; ++Side)
	{
		const int32 Foot = BoneNames.IndexOfByKey(Feet[Side]);
		const int32 Calf = BoneNames.IndexOfByKey(Calves[Side]);
		const int32 SourceFoot = Snapshot.BoneNames.IndexOfByKey(Feet[Side]);
		if (!Transforms.IsValidIndex(Foot) || !Transforms.IsValidIndex(Calf)
			|| !Snapshot.LocalTransforms.IsValidIndex(SourceFoot)) continue;
		if (bRecovery)
		{
			const int32 Thigh=BoneNames.IndexOfByKey(Side==0 ? FName(TEXT("thigh_l")) : FName(TEXT("thigh_r")));
			double Lower=Recovery.Lower[Side];
			// The return curve authors each policy endpoint. Sample those lengths
			// with the pose, rather than applying the newest live curve value to
			// a knee/ankle still interpolating from the previous policy frame.
			const int32 SourceCalf=Snapshot.BoneNames.IndexOfByKey(Calves[Side]);
			if (UseRecoveryLengthInterpolation() && Snapshot.PreviousComponentTransforms.IsValidIndex(SourceCalf)
				&& Snapshot.PreviousComponentTransforms.IsValidIndex(SourceFoot)
				&& Snapshot.ComponentTransforms.IsValidIndex(SourceCalf)
				&& Snapshot.ComponentTransforms.IsValidIndex(SourceFoot))
			{
				const double A=(Snapshot.PreviousComponentTransforms[SourceFoot].GetLocation()-Snapshot.PreviousComponentTransforms[SourceCalf].GetLocation()).Size();
				const double B=(Snapshot.ComponentTransforms[SourceFoot].GetLocation()-Snapshot.ComponentTransforms[SourceCalf].GetLocation()).Size();
				Lower=FMath::Lerp(A,B,double(FMath::Clamp(InterpolationAlpha,0.f,1.f)));
			}
			if (Transforms.IsValidIndex(Thigh)) ProphecyRecoveryLegLength::Resolve(
				Transforms[Thigh],Transforms[Calf],Transforms[Foot],Recovery.Upper[Side],Lower);
			continue;
		}
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
	if (SoftZone<=0) return;
    if (ProphecyNNPresentation::UseSpecialKneeSmoothingOrder() &&
        (Special || ProphecyAttackStartInertia::Active(AgentId))) return;
	for (int32 Side=0;Side<2;++Side)
	{
		const FName ThighName=Side==0 ? FName(TEXT("thigh_l")) : FName(TEXT("thigh_r"));
		const int32 Thigh=BoneNames.IndexOfByKey(ThighName),Calf=BoneNames.IndexOfByKey(Calves[Side]);
		const int32 Foot=BoneNames.IndexOfByKey(Feet[Side]),Toe=BoneNames.IndexOfByKey(Toes[Side]);
		if (!Transforms.IsValidIndex(Thigh) || !Transforms.IsValidIndex(Calf) || !Transforms.IsValidIndex(Foot)) continue;
		const FVector Fallback=Transforms[Thigh].TransformVectorNoScale(BendFrames.LocalPole[Side]);
		ProphecyKneePopSmoothing::Apply(Transforms[Thigh],Transforms[Calf],Transforms[Foot],
			Transforms.IsValidIndex(Toe)?&Transforms[Toe]:nullptr,SoftZone,Fallback);
	}
}

void ProphecyNNPresentation::ApplyKneePopSmoothing(int32 AgentId,TConstArrayView<FName> Names,TArrayView<FTransform> Pose)
{
    float Zone;FKneeBendFrames Frames;
    {
        FReadScopeLock Lock(GProphecyNNPoseLock);
        const auto* Value=GKneePopSmoothing.Find(AgentId);if(!Value)return;
        Zone=*Value;
        if(const auto* F=GKneeBendFrames.Find(AgentId))Frames=*F;
    }
    for(int32 Side=0;Side<2;++Side)
    {
        const int32 H=Names.IndexOfByKey(Side?FName(TEXT("thigh_r")):FName(TEXT("thigh_l")));
        const int32 K=Names.IndexOfByKey(Side?FName(TEXT("calf_r")):FName(TEXT("calf_l")));
        const int32 F=Names.IndexOfByKey(Side?FName(TEXT("foot_r")):FName(TEXT("foot_l")));
        const int32 T=Names.IndexOfByKey(Side?FName(TEXT("ball_r")):FName(TEXT("ball_l")));
        if(!Pose.IsValidIndex(H)||!Pose.IsValidIndex(K)||!Pose.IsValidIndex(F))continue;
        ProphecyKneePopSmoothing::Apply(Pose[H],Pose[K],Pose[F],Pose.IsValidIndex(T)?&Pose[T]:nullptr,
            Zone,Pose[H].TransformVectorNoScale(Frames.LocalPole[Side]));
    }
}

int32 FProphecyNNPoseStore::NumPoses()
{
	FReadScopeLock Lock(GProphecyNNPoseLock);
	return GProphecyNNPoses.Num();
}

bool ProphecyNNPresentation::ReadPelvisWorld(int32 Id,FTransform& Out)
{
    FReadScopeLock Lock(GProphecyNNPoseLock);
    const auto* Found=GProphecyNNPoses.Find(Id);if(!Found)return false;
    const auto& P=*Found;
    const int32 I=P.BoneNames.IndexOfByKey(FName(TEXT("pelvis")));
    if(!P.ComponentTransforms.IsValidIndex(I)||!P.PreviousComponentTransforms.IsValidIndex(I))return false;
    const auto* Presentation=GProphecyNNPresentation.Find(Id);
    const float Alpha=Presentation && Presentation->SourceTimeSeconds==P.SourceTimeSeconds?Presentation->Alpha:1.f;
    const FTransform A=P.PreviousComponentTransforms[I]*P.PreviousComponentWorldTransform;
    const FTransform B=P.ComponentTransforms[I]*P.ComponentWorldTransform;
    if(P.InterpolationMode==EProphecyNNInterpolationMode::HermiteSlerp) Out=ProphecyNNInterpolation::Sample(P,I,A,B,Alpha);
    else
    {
        // Same matrix-lerp polar rotation as the physical and animation readers.
        FQuat Start=A.GetRotation().GetNormalized(),End=B.GetRotation().GetNormalized();
        float Cos=Start|End;if(Cos<0){End=End*-1.;Cos=-Cos;}
        const float Angle=2.f*FMath::Acos(FMath::Clamp(Cos,0.f,1.f));
        const FQuat Q=Angle<=1.e-6f?Start:FQuat::Slerp(Start,End,
            FMath::Atan2(Alpha*FMath::Sin(Angle),(1.f-Alpha)+Alpha*FMath::Cos(Angle))/Angle).GetNormalized();
        Out=FTransform(Q,FMath::Lerp(A.GetLocation(),B.GetLocation(),Alpha));
    }
    return true;
}

void FProphecyNNPoseStore::UpdateTickPinningLegs(int32 Id,TConstArrayView<int32> Indices,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current)
{
    FWriteScopeLock Lock(GProphecyNNPoseLock);
    auto* P=GProphecyNNPoses.Find(Id);
    if(!P || Indices.Num()!=8 || Previous.Num()!=8 || Current.Num()!=8)return;
    for(int32 J=0;J<8;++J)
    {
        const int32 I=Indices[J];
        if(!P->ComponentTransforms.IsValidIndex(I) || !P->PreviousComponentTransforms.IsValidIndex(I))return;
    }
    for(int32 J=0;J<8;++J)
    {
        const int32 I=Indices[J];
        // Adding a linear endpoint correction to Hermite adds its world delta to
        // both tangents. Preserve the existing curve and make restoration reversible.
        if(P->InterpolationStartTangents.IsValidIndex(I) && P->InterpolationEndTangents.IsValidIndex(I))
        {
            const FVector Old=(P->ComponentTransforms[I]*P->ComponentWorldTransform).GetLocation()
                -(P->PreviousComponentTransforms[I]*P->PreviousComponentWorldTransform).GetLocation();
            const FVector New=(Current[J]*P->ComponentWorldTransform).GetLocation()
                -(Previous[J]*P->PreviousComponentWorldTransform).GetLocation();
            P->InterpolationStartTangents[I]+=New-Old;P->InterpolationEndTangents[I]+=New-Old;
        }
        P->PreviousComponentTransforms[I]=Previous[J];P->ComponentTransforms[I]=Current[J];
        const int32 Parent=J%4 ? Indices[J-1] : P->BoneNames.IndexOfByKey(FName(TEXT("pelvis")));
        if(P->LocalTransforms.IsValidIndex(I) && P->ComponentTransforms.IsValidIndex(Parent))
            P->LocalTransforms[I]=Current[J].GetRelativeTransform(P->ComponentTransforms[Parent]);
    }
    P->Revision=AllocatePoseRevision();
}
