#include "ProphecyAttackFists.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPoseAnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/Skeleton.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/ScopeLock.h"

namespace
{
	struct FFistState
	{
		FVector2D Start = FVector2D::ZeroVector, Target = FVector2D::ZeroVector;
		double StartTime = 0;
		float Duration = 0, EndSeconds = 1;
		bool bAttacking = false;
	};
	struct FFistBone { FName Name; FTransform Local; };
	struct FFistStorage
	{
		TMap<TWeakObjectPtr<const AProphecyAgent>, FFistState> States;
		TMap<TWeakObjectPtr<const AProphecyAgent>, FVector2D> ManualLevels;
		FCriticalSection SnapshotLock;
		TMap<const void*, TArray<FFistBone>> Snapshots;
	};
	FFistStorage& Storage()
	{
		// Deliberately process-lifetime. AnimInstance destruction can run during
		// Live Coding reinstancing or module/global teardown; its lock must still
		// exist then. Actor/proxy entries are removed through their lifecycle hooks.
		static FFistStorage* Instance = new FFistStorage();
		return *Instance;
	}

	double Now(const AProphecyAgent* Agent)
	{
		return Agent->GetWorld() ? double(Agent->GetWorld()->GetTimeSeconds()) : 0.0;
	}
	FVector2D Sample(const FFistState& S, double Time)
	{
		const float Alpha = S.Duration <= UE_SMALL_NUMBER ? 1.0f :
			FMath::Clamp(float((Time-S.StartTime)/S.Duration), 0.0f, 1.0f);
		return FMath::Lerp(S.Start, S.Target, Alpha);
	}
	FProphecyAttackFistSettings Sanitize(FProphecyAttackFistSettings S)
	{
		S.LeftClosedLevel = FMath::IsFinite(S.LeftClosedLevel) ? FMath::Clamp(S.LeftClosedLevel,0.f,1.f) : 1.f;
		S.RightClosedLevel = FMath::IsFinite(S.RightClosedLevel) ? FMath::Clamp(S.RightClosedLevel,0.f,1.f) : 1.f;
		S.ClosingStartSeconds = FMath::IsFinite(S.ClosingStartSeconds) ? FMath::Max(0.f,S.ClosingStartSeconds) : .4f;
		S.OpeningEndSeconds = FMath::IsFinite(S.OpeningEndSeconds) ? FMath::Max(0.f,S.OpeningEndSeconds) : 1.f;
		return S;
	}
	int32 HandSide(FName Name)
	{
		const FString S = Name.ToString();
		if (!(S.StartsWith(TEXT("index_")) || S.StartsWith(TEXT("middle_")) ||
			S.StartsWith(TEXT("ring_")) || S.StartsWith(TEXT("pinky_")) || S.StartsWith(TEXT("thumb_")))) return INDEX_NONE;
		return S.EndsWith(TEXT("_l")) ? 0 : S.EndsWith(TEXT("_r")) ? 1 : INDEX_NONE;
	}
}

bool AProphecyAgent::SetAttackFistSettings(FName Attack, FProphecyAttackFistSettings Settings)
{
	if (Attack.IsNone() || !FMath::IsFinite(Settings.LeftClosedLevel) || !FMath::IsFinite(Settings.RightClosedLevel) ||
		!FMath::IsFinite(Settings.ClosingStartSeconds) || !FMath::IsFinite(Settings.OpeningEndSeconds)) return false;
	AttackFistSettings.Add(Attack, Sanitize(Settings));
	return true;
}

FProphecyAttackFistSettings AProphecyAgent::GetAttackFistSettings(FName Attack) const
{
	const FProphecyAttackFistSettings* Found = AttackFistSettings.Find(Attack);
	return Sanitize(Found ? *Found : DefaultAttackFistSettings);
}

void AProphecyAgent::BeginAttackFists(FName Attack)
{
	check(IsInGameThread());
	ProphecyAttackFists::EnsureManualSimulation(this);
	FFistState& S = Storage().States.FindOrAdd(this);
	const double Time = Now(this);
	const FProphecyAttackFistSettings Settings = GetAttackFistSettings(Attack);
	S.Start = Sample(S, Time);
	S.Target = FVector2D(Settings.LeftClosedLevel, Settings.RightClosedLevel);
	S.StartTime = Time;
	S.Duration = Settings.ClosingStartSeconds;
	S.EndSeconds = Settings.OpeningEndSeconds;
	S.bAttacking = true;
}

bool AProphecyAgent::SetFistClosedLevels(float Left, float Right, float BlendSeconds)
{
	check(IsInGameThread());
	if (!FMath::IsFinite(Left) || !FMath::IsFinite(Right) || !FMath::IsFinite(BlendSeconds)) return false;
	ProphecyAttackFists::EnsureManualSimulation(this);
	const FVector2D Target(FMath::Clamp(Left,0.f,1.f), FMath::Clamp(Right,0.f,1.f));
	Storage().ManualLevels.Add(this,Target);
	FFistState& S = Storage().States.FindOrAdd(this);
	const float Duration = FMath::Max(0.f,BlendSeconds);
	// Repeating the same command must not keep restarting an in-progress blend.
	if (!S.bAttacking && S.Target.Equals(Target) && S.Duration == Duration) return true;
	S.Start = Sample(S,Now(this));
	S.Target = Target;
	S.StartTime = Now(this);
	S.Duration = Duration;
	S.bAttacking = false;
	return true;
}

void AProphecyAgent::EndAttackFists()
{
	check(IsInGameThread());
	FFistState* S = Storage().States.Find(this);
	if (!S || !S->bAttacking) return;
	S->Start = Sample(*S, Now(this));
	const FVector2D* Manual = Storage().ManualLevels.Find(this);
	S->Target = Manual ? *Manual : FVector2D::ZeroVector;
	S->StartTime = Now(this);
	S->Duration = S->EndSeconds;
	S->bAttacking = false;
}

void AProphecyAgent::GetFistClosedLevels(float& Left, float& Right) const
{
	check(IsInGameThread());
	const FFistState* S = Storage().States.Find(this);
	const FVector2D Value = bEnableAttackFists && S ? Sample(*S,Now(this)) : FVector2D::ZeroVector;
	Left = float(Value.X); Right = float(Value.Y);
}

void AProphecyAgent::ReleaseAttackFists()
{
	Storage().States.Remove(this);
	Storage().ManualLevels.Remove(this);
}

void ProphecyAttackFists::EnsureManualSimulation(AProphecyAgent* Agent)
{
	if (!Agent || !Agent->HasActorBegunPlay() ||
		!Agent->bManualNNPoseApplication || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical) return;
	USkeletalMeshComponent* Mesh = Agent->GetPoseReferenceMesh();
	if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return;
	// Sim also needs this proxy for mode-transition helper-bone continuity, even
	// when the optional finger layer is disabled. Physics owns body bones.
	Mesh->SetComponentTickEnabled(true);
	Mesh->bEnableUpdateRateOptimizations = false;
	Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	if (Mesh->GetAnimInstance()) return;
	// The physical manual path intentionally has no NN animation. Supply only
	// reference-local bones + fingers; simulated bodies still own the final pose.
	Mesh->SetAnimInstanceClass(UProphecyNNPoseAnimInstance::StaticClass());
	if (UProphecyNNPoseAnimInstance* Anim = Cast<UProphecyNNPoseAnimInstance>(Mesh->GetAnimInstance()))
	{
		Anim->bUseStoredPose = false;
		Anim->bEnableDebugMotion = false;
	}
}

void ProphecyAttackFists::PreUpdate(const void* Proxy, const AProphecyAgent* Agent)
{
	check(IsInGameThread());
	TArray<FFistBone> Bones;
	if (Agent && Agent->bEnableAttackFists)
	{
		float Left, Right;
		Agent->GetFistClosedLevels(Left,Right);
		// Zero still explicitly means the reference A-pose, overriding other finger overlays.
		UAnimSequence* Clip = Agent->ClosedFistAnimation.LoadSynchronous();
		const USkeletalMeshComponent* Component = Agent->GetPoseReferenceMesh();
		const USkeletalMesh* Mesh = Component ? Component->GetSkeletalMeshAsset() : nullptr;
		if (Clip && Clip->GetSkeleton() && Mesh && !Clip->IsValidAdditive())
		{
			const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
			const FReferenceSkeleton& ClipRef = Clip->GetSkeleton()->GetReferenceSkeleton();
			TArray<FTransform> SourceRefCS, SourceClosedCS, TargetRefCS;
			SourceRefCS.SetNum(ClipRef.GetNum());
			SourceClosedCS.SetNum(ClipRef.GetNum());
			TargetRefCS.SetNum(Ref.GetNum());
			for (int32 Index=0; Index<ClipRef.GetNum(); ++Index)
			{
				const int32 Parent = ClipRef.GetParentIndex(Index);
				FTransform Local = ClipRef.GetRefBonePose()[Index];
				Clip->GetBoneTransform(Local, FSkeletonPoseBoneIndex(Index), FAnimExtractContext(0.0), false);
				SourceRefCS[Index] = Parent == INDEX_NONE ? ClipRef.GetRefBonePose()[Index] :
					ClipRef.GetRefBonePose()[Index] * SourceRefCS[Parent];
				SourceClosedCS[Index] = Parent == INDEX_NONE ? Local : Local * SourceClosedCS[Parent];
			}
			for (int32 Index=0; Index<Ref.GetNum(); ++Index)
			{
				const int32 Parent = Ref.GetParentIndex(Index);
				TargetRefCS[Index] = Parent == INDEX_NONE ? Ref.GetRefBonePose()[Index] :
					Ref.GetRefBonePose()[Index] * TargetRefCS[Parent];
			}
			auto ConvertedCS = [&](int32 TargetIndex, int32 SourceIndex)
			{
				// Preserve the source's skinning deformation, not its local axes.
				// UE row convention: targetBind * inverse(sourceBind) * sourcePose.
				return TargetRefCS[TargetIndex].GetRelativeTransform(SourceRefCS[SourceIndex]) * SourceClosedCS[SourceIndex];
			};
			for (int32 Index=0; Index<Ref.GetNum(); ++Index)
			{
				const FName Name = Ref.GetBoneName(Index);
				const int32 Side = HandSide(Name), ClipIndex = ClipRef.FindBoneIndex(Name);
				if (Side == INDEX_NONE || ClipIndex == INDEX_NONE) continue;
				const FTransform& Open = Ref.GetRefBonePose()[Index];
				const int32 Parent = Ref.GetParentIndex(Index);
				const int32 ClipParent = Parent == INDEX_NONE ? INDEX_NONE : ClipRef.FindBoneIndex(Ref.GetBoneName(Parent));
				if (Parent == INDEX_NONE || ClipParent == INDEX_NONE) continue;
				const FTransform Closed = ConvertedCS(Index,ClipIndex).GetRelativeTransform(ConvertedCS(Parent,ClipParent));
				const float Level = Side == 0 ? Left : Right;
				FTransform Blended(FQuat::Slerp(Open.GetRotation(),Closed.GetRotation(),Level).GetNormalized(),
					FMath::Lerp(Open.GetTranslation(),Closed.GetTranslation(),Level),
					FMath::Lerp(Open.GetScale3D(),Closed.GetScale3D(),Level));
				if (!Blended.ContainsNaN()) Bones.Add({Name,Blended});
			}
		}
	}
	FScopeLock Lock(&Storage().SnapshotLock);
	Storage().Snapshots.Add(Proxy,MoveTemp(Bones));
}

void ProphecyAttackFists::Evaluate(const void* Proxy, FPoseContext& Output)
{
	FScopeLock Lock(&Storage().SnapshotLock);
	const TArray<FFistBone>* Bones = Storage().Snapshots.Find(Proxy);
	if (!Bones) return;
	const FBoneContainer& Container = Output.Pose.GetBoneContainer();
	for (const FFistBone& Bone : *Bones)
	{
		const int32 SkeletonIndex = Container.GetReferenceSkeleton().FindBoneIndex(Bone.Name);
		if (SkeletonIndex == INDEX_NONE) continue;
		const FCompactPoseBoneIndex Index = Container.GetCompactPoseIndexFromSkeletonIndex(SkeletonIndex);
		if (Index.IsValid() && Output.Pose.IsValidIndex(Index)) Output.Pose[Index] = Bone.Local;
	}
}

void ProphecyAttackFists::ReleaseProxy(const void* Proxy)
{
	FScopeLock Lock(&Storage().SnapshotLock);
	Storage().Snapshots.Remove(Proxy);
}
