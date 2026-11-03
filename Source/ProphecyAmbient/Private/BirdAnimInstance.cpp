#include "BirdAnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"

void UBirdAnimInstance::SetClips(UAnimSequence* Perch, UAnimSequence* Walk, UAnimSequence* Glide, UAnimSequence* Flap, UAnimSequence* Hover)
{
	Clips.SetNum(5);
	Clips[0] = Perch;
	Clips[1] = Walk;
	Clips[2] = Glide;
	Clips[3] = Flap;
	Clips[4] = Hover;
}

void FBirdAnimProxy::Initialize(UAnimInstance* Instance)
{
	FAnimInstanceProxy::Initialize(Instance);
	Jaw = Head = Neck2 = Neck3 = Neck1 = Spine1 = Spine2 = Tail = INDEX_NONE;
	RefCS.Reset();
	RefParent.Reset();
	const USkeletalMeshComponent* Comp = Instance ? Instance->GetSkelMeshComponent() : nullptr;
	const USkeletalMesh* Mesh = Comp ? Comp->GetSkeletalMeshAsset() : nullptr;
	if (!Mesh) return;
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	Jaw = Ref.FindBoneIndex(TEXT("jaw"));
	Head = Ref.FindBoneIndex(TEXT("head"));
	Neck2 = Ref.FindBoneIndex(TEXT("neck_02"));
	Neck3 = Ref.FindBoneIndex(TEXT("neck_03"));
	Neck1 = Ref.FindBoneIndex(TEXT("neck_01"));
	Spine1 = Ref.FindBoneIndex(TEXT("spine_01"));
	Spine2 = Ref.FindBoneIndex(TEXT("spine_02"));
	Tail = Ref.FindBoneIndex(TEXT("tail"));
	const TArray<FTransform>& Local = Ref.GetRefBonePose();
	RefCS.SetNum(Local.Num());
	RefParent.SetNum(Local.Num());
	for (int32 i = 0; i < Local.Num(); ++i)
	{
		const int32 Parent = Ref.GetParentIndex(i);
		RefParent[i] = Parent;
		RefCS[i] = Parent == INDEX_NONE ? Local[i].GetRotation() : RefCS[Parent] * Local[i].GetRotation();
	}
}

void FBirdAnimProxy::PreUpdate(UAnimInstance* Instance, float DeltaSeconds)
{
	FAnimInstanceProxy::PreUpdate(Instance, DeltaSeconds);
	if (const UBirdAnimInstance* B = Cast<UBirdAnimInstance>(Instance))
	{
		P = B->Params;
		for (int32 i = 0; i < 5; ++i) Clips[i] = B->Clips.IsValidIndex(i) ? B->Clips[i].Get() : nullptr;
	}
}

void FBirdAnimProxy::Sample(const UAnimSequence* Seq, float Phase01, FPoseContext& Ctx) const
{
	if (!Seq)
	{
		Ctx.ResetToRefPose();
		return;
	}
	const float Len = Seq->GetPlayLength();
	const double T = Len > KINDA_SMALL_NUMBER ? double(FMath::Frac(Phase01) * Len) : 0.0;
	FAnimationPoseData Data(Ctx);
	Seq->GetAnimationPose(Data, FAnimExtractContext(T, false));
}

void FBirdAnimProxy::SampleStatic(int32 Slot, const UAnimSequence* Seq, FPoseContext& Ctx)
{
	FStaticPose& C = StaticPoses[Slot];
	const FBoneContainer& BC = Ctx.Pose.GetBoneContainer();
	if (Seq && C.Seq == Seq && C.Serial == BC.GetSerialNumber() && C.NumBones == Ctx.Pose.GetNumBones())
	{
		Ctx.Pose.CopyBonesFrom(C.Bones);
		return;
	}
	Sample(Seq, 0.f, Ctx);
	if (!Seq) { C.Seq = nullptr; return; }
	C.Bones.Reset(Ctx.Pose.GetNumBones());
	C.Bones.Append(Ctx.Pose.GetBones());
	C.Seq = Seq;
	C.Serial = BC.GetSerialNumber();
	C.NumBones = Ctx.Pose.GetNumBones();
}

void FBirdAnimProxy::BlendInto(FPoseContext& A, FPoseContext& B, float AlphaB)
{
	if (AlphaB <= 0.001f) return;
	if (AlphaB >= 0.999f)
	{
		A.Pose = B.Pose;
		A.Curve = B.Curve;
		return;
	}
	FPoseContext R(this);
	FAnimationPoseData DA(A), DB(B), DR(R);
	FAnimationRuntime::BlendTwoPosesTogether(DA, DB, 1.f - AlphaB, DR);
	A.Pose = R.Pose;
	A.Curve = R.Curve;
}

FQuat FBirdAnimProxy::CSRotation(const FCompactPose& Pose, FCompactPoseBoneIndex Bone) const
{
	// component-space rotation of a bone in the current local pose (child CS = parent CS * local)
	TArray<FCompactPoseBoneIndex, TInlineAllocator<64>> Chain;
	const FBoneContainer& BC = Pose.GetBoneContainer();
	for (FCompactPoseBoneIndex I = Bone; I.IsValid() && Chain.Num() < 64; I = BC.GetParentBoneIndex(I)) Chain.Add(I);
	FQuat Q = FQuat::Identity;
	for (int32 k = Chain.Num() - 1; k >= 0; --k) Q = Q * Pose[Chain[k]].GetRotation();
	return Q;
}

void FBirdAnimProxy::RotateCS(FCompactPose& Pose, int32 MeshBone, const FVector& RefAxisCS, float Radians) const
{
	if (MeshBone == INDEX_NONE || FMath::Abs(Radians) < 1e-5f || !RefCS.IsValidIndex(MeshBone)) return;
	const FBoneContainer& BC = Pose.GetBoneContainer();
	const FCompactPoseBoneIndex CI = BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshBone));
	if (!CI.IsValid()) return;
	// the axis rides with the bone: ref-pose component axis -> current component axis
	const FQuat Cur = CSRotation(Pose, CI);
	const FVector Axis = (Cur * RefCS[MeshBone].Inverse()).RotateVector(RefAxisCS).GetSafeNormal();
	const FCompactPoseBoneIndex ParentCI = BC.GetParentBoneIndex(CI);
	const FQuat Parent = ParentCI.IsValid() ? CSRotation(Pose, ParentCI) : FQuat::Identity;
	const FQuat Delta(Axis, Radians);
	FTransform& L = Pose[CI];
	L.SetRotation((Parent.Inverse() * Delta * Parent * L.GetRotation()).GetNormalized());
}

FQuat FBirdAnimProxy::CurrentCS(const FCompactPose& Pose, int32 MeshBone) const
{
	if (MeshBone == INDEX_NONE) return FQuat::Identity;
	const FCompactPoseBoneIndex CI = Pose.GetBoneContainer().MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshBone));
	return CI.IsValid() ? CSRotation(Pose, CI) : FQuat::Identity;
}

void FBirdAnimProxy::ApplyCS(FCompactPose& Pose, int32 MeshBone, const FQuat& DeltaCS) const
{
	if (MeshBone == INDEX_NONE) return;
	const FBoneContainer& BC = Pose.GetBoneContainer();
	const FCompactPoseBoneIndex CI = BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshBone));
	if (!CI.IsValid()) return;
	const FCompactPoseBoneIndex ParentCI = BC.GetParentBoneIndex(CI);
	const FQuat Parent = ParentCI.IsValid() ? CSRotation(Pose, ParentCI) : FQuat::Identity;
	FTransform& L = Pose[CI];
	L.SetRotation((Parent.Inverse() * DeltaCS * Parent * L.GetRotation()).GetNormalized());
}

bool FBirdAnimProxy::Evaluate(FPoseContext& Output)
{
	const float Flight = FMath::Clamp(P.Flight, 0.f, 1.f);
	FPoseContext Ground(this), Air(this), Tmp(this);
	// only the clips that contribute are sampled (a full walk / full flap replaces the static pose under it)
	if (Flight < 0.999f)
	{
		if (P.Walk >= 0.999f && Clips[1]) Sample(Clips[1], P.WalkPhase, Ground);
		else
		{
			SampleStatic(0, Clips[0], Ground);
			if (P.Walk > 0.001f)
			{
				Sample(Clips[1], P.WalkPhase, Tmp);
				BlendInto(Ground, Tmp, P.Walk);
			}
		}
	}
	if (Flight > 0.001f)
	{
		if (P.Flap >= 0.999f && Clips[3]) Sample(Clips[3], P.FlapPhase, Air);
		else
		{
			SampleStatic(1, Clips[2], Air);
			if (P.Flap > 0.001f)
			{
				Sample(Clips[3], P.FlapPhase, Tmp);
				BlendInto(Air, Tmp, P.Flap);
			}
		}
		if (P.Hover > 0.001f)
		{
			Sample(Clips[4], P.FlapPhase, Tmp);
			BlendInto(Air, Tmp, P.Hover);
		}
	}
	if (Flight <= 0.001f)
	{
		Output.Pose = Ground.Pose;
		Output.Curve = Ground.Curve;
	}
	else if (Flight >= 0.999f)
	{
		Output.Pose = Air.Pose;
		Output.Curve = Air.Curve;
	}
	else
	{
		BlendInto(Ground, Air, Flight);
		Output.Pose = Ground.Pose;
		Output.Curve = Ground.Curve;
	}

	// walking / stepping: the body is not one block. It twists a little with each step, the tail swings against it and bobs,
	// and the head is held level (the waddle's roll is cancelled at the head) with a small nod per step
	if (P.Walk > 0.01f)
	{
		const float W = FMath::Clamp(P.Walk, 0.f, 1.f);
		const float Ph = 2.f * PI * P.WalkPhase;
		const FVector UpCS(0, 0, 1);
		ApplyCS(Output.Pose, Spine1, FQuat(UpCS, FMath::DegreesToRadians(3.f) * FMath::Sin(Ph + 0.6f) * W));
		ApplyCS(Output.Pose, Tail, FQuat(UpCS, FMath::DegreesToRadians(-8.f) * FMath::Sin(Ph + 0.6f) * W));
		RotateCS(Output.Pose, Tail, FVector(0, 1, 0), FMath::DegreesToRadians(3.f) * FMath::Sin(2.f * Ph) * W);
		if (Head != INDEX_NONE && RefCS.IsValidIndex(Head))
		{
			// measure the head's roll about the forward axis relative to its reference pose and take 85 % of it out
			const FQuat Delta = CurrentCS(Output.Pose, Head) * RefCS[Head].Inverse();
			FQuat Swing, Twist;
			Delta.ToSwingTwist(FVector(1, 0, 0), Swing, Twist);
			ApplyCS(Output.Pose, Head, FQuat::Slerp(FQuat::Identity, Twist.Inverse(), 0.85f * W));
		}
		RotateCS(Output.Pose, Head, FVector(0, 1, 0), FMath::DegreesToRadians(2.f) * FMath::Sin(2.f * Ph + 0.5f) * W);
	}

	// head look (yaw about component up, spread over the neck), pitch about the head's own lateral axis
	const float Yaw = FMath::DegreesToRadians(FMath::Clamp(P.LookYaw, -110.f, 110.f));
	// down to -100 deg: a hover-hunting kingfisher holds its bill ~76 deg below the horizon with the body tilted up
	const float Pitch = FMath::DegreesToRadians(FMath::Clamp(P.LookPitch, -100.f, 45.f));
	if (FMath::Abs(Yaw) > 1e-4f)
	{
		const FVector Up(0, 0, 1);
		// world-up yaw: apply in component space directly (axis does not ride with the bone)
		auto YawBone = [&](int32 MeshBone, float Rad)
		{
			if (MeshBone == INDEX_NONE) return;
			const FBoneContainer& BC = Output.Pose.GetBoneContainer();
			const FCompactPoseBoneIndex CI = BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshBone));
			if (!CI.IsValid()) return;
			const FCompactPoseBoneIndex ParentCI = BC.GetParentBoneIndex(CI);
			const FQuat Parent = ParentCI.IsValid() ? CSRotation(Output.Pose, ParentCI) : FQuat::Identity;
			FTransform& L = Output.Pose[CI];
			L.SetRotation((Parent.Inverse() * FQuat(Up, Rad) * Parent * L.GetRotation()).GetNormalized());
		};
		YawBone(Neck2, Yaw * 0.25f);
		YawBone(Neck3, Yaw * 0.30f);
		YawBone(Head, Yaw * 0.45f);
	}
	// +angle about +Y (component) drops the bill tip; looking up is the opposite sign
	// pitch: small looks are made with the head and upper neck; reaching further down (pecking, drinking, picking food up)
	// curls the lower neck and the front of the back too, so the bird bends instead of tipping over as one piece
	if (Neck2 != INDEX_NONE && Neck3 != INDEX_NONE)
	{
		const float Pc = FMath::Max(Pitch, FMath::DegreesToRadians(-40.f));
		const float Ex = Pitch - Pc;	// <= 0
		RotateCS(Output.Pose, Spine2, FVector(0, 1, 0), -Ex * 0.35f);
		RotateCS(Output.Pose, Neck1, FVector(0, 1, 0), -Ex * 0.35f);
		RotateCS(Output.Pose, Neck2, FVector(0, 1, 0), -(Pc * 0.2f + Ex * 0.3f));
		RotateCS(Output.Pose, Neck3, FVector(0, 1, 0), -Pc * 0.3f);
		RotateCS(Output.Pose, Head, FVector(0, 1, 0), -Pc * 0.5f);
	}
	else RotateCS(Output.Pose, Head, FVector(0, 1, 0), -Pitch);
	RotateCS(Output.Pose, Jaw, FVector(0, 1, 0), FMath::DegreesToRadians(P.BeakOpenDeg) * FMath::Clamp(P.Beak, 0.f, 1.f));
	return true;
}
