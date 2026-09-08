#include "ProphecyModeTransitions.h"
#include "ProphecyAgent.h"
#include "ProphecyAttackFists.h"
#include "ProphecySwordComponent.h"
#include "Animation/AnimInstanceProxy.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "Misc/ScopeLock.h"

namespace
{
	constexpr double BlendSeconds = 0.25;
	struct FBody
	{
		FName Name;
		FTransform World;
		FVector Linear, Angular;
	};
	struct FPose
	{
		TArray<FName> Names;
		TArray<FTransform> World, Local;
		TArray<FBody> Bodies;
		TWeakObjectPtr<USkeletalMeshComponent> Mesh;
		EProphecyAgentSimulationMode Mode;
		double Start = 0;
		int32 Depth = 0;
	};
	struct FSnapshot
	{
		TArray<FName> Names;
		TArray<FTransform> FromCS, FromLocal;
		TSet<FName> PhysicalBones;
		float Alpha = 1;
		bool bLocal = false, bManualSim = false;
	};
	struct FStorage
	{
		TMap<TWeakObjectPtr<const AProphecyAgent>, FPose> Captures, Blends;
		FCriticalSection Lock;
		TMap<const void*, FSnapshot> Snapshots;
	};
	FStorage& Storage() { static FStorage* S = new FStorage; return *S; }
	struct FFinalizeRegistration { TWeakObjectPtr<USkeletalMeshComponent> Mesh; FDelegateHandle Handle; };
	auto& FinalizeRegistrations()
	{
		static auto* Registrations = new TMap<TWeakObjectPtr<const AProphecyAgent>, FFinalizeRegistration>;
		return *Registrations;
	}
	void CorrectScaledPhysicsPose(const AProphecyAgent* Agent)
	{
		if (!IsValid(Agent) || Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic) return;
		const FPose* Blend = Storage().Blends.Find(Agent);
		if (!Blend || Agent->GetWorld()->GetTimeSeconds() <= Blend->Start) return;
		USkeletalMeshComponent* Mesh = Agent->GetPoseReferenceMesh();
		if (!Mesh || !Mesh->GetSkeletalMeshAsset()) return;
		const auto& Ref = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
		const TArray<FTransform> Original = Mesh->GetComponentSpaceTransforms();
		// Finalized callback runs on the game thread, after the physics worker and
		// buffer flip, before render data is submitted. The editable-buffer accessor
		// refers to NEXT frame here, so correct the finalized read buffer itself.
		auto& Final = const_cast<TArray<FTransform>&>(Mesh->GetComponentSpaceTransforms());
		for (int32 I = 0; I < Final.Num(); ++I)
		{
			const int32 Parent = Ref.GetParentIndex(I);
			if (Parent == INDEX_NONE) continue;
			FBodyInstance* Body = Mesh->GetBodyInstance(Ref.GetBoneName(I));
			if (Body && Body->IsInstanceSimulatingPhysics() && Body->PhysicsBlendWeight >= 1.f && !Body->IsPhysicsDisabled())
			{
				// PhysAnim builds relative physical translations with an unscaled
				// parent, then composes them with the animated calf scale a second
				// time. Preserve the scale but use the actual rigid body's position.
				if (!Original[Parent].GetScale3D().Equals(FVector::OneVector, 1.e-5))
					Final[I].SetLocation(Mesh->GetComponentTransform().InverseTransformPosition(Body->GetUnrealWorldTransform().GetLocation()));
			}
			else
			{
				// Non-physical descendants (toes/fingers/helpers) retain their
				// evaluated local transform when their physical parent is corrected.
				Final[I] = Original[I].GetRelativeTransform(Original[Parent]) * Final[Parent];
			}
		}
	}
	void RegisterFinalizer(AProphecyAgent* Agent, USkeletalMeshComponent* Mesh)
	{
		auto& Registration = FinalizeRegistrations().FindOrAdd(Agent);
		if (Registration.Mesh == Mesh) return;
		if (auto* Old = Registration.Mesh.Get()) Old->UnregisterOnBoneTransformsFinalizedDelegate(Registration.Handle);
		Registration.Mesh = Mesh;
		Registration.Handle = Mesh->RegisterOnBoneTransformsFinalizedDelegate(
			FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateWeakLambda(Agent, [Agent]() { CorrectScaledPhysicsPose(Agent); }));
	}
	bool IsFinger(FName Name)
	{
		const FString N = Name.ToString();
		return N.StartsWith(TEXT("index_")) || N.StartsWith(TEXT("middle_")) || N.StartsWith(TEXT("ring_")) ||
			N.StartsWith(TEXT("pinky_")) || N.StartsWith(TEXT("thumb_"));
	}
}

ProphecyModeTransitions::FScope::FScope(AProphecyAgent* A) : Agent(A)
{
	check(IsInGameThread());
	FPose& S = Storage().Captures.FindOrAdd(A);
	if (S.Depth++ != 0) return;
	S.Mode = A->GetSimulationMode();
	S.Mesh = A->GetPoseReferenceMesh();
	USkeletalMeshComponent* M = S.Mesh.Get();
	if (!M || !M->GetSkeletalMeshAsset()) return;
	// Finish any worker evaluation before reading the visible pose.
	M->HandleExistingParallelEvaluationTask(true, true);
	const FReferenceSkeleton& Ref = M->GetSkeletalMeshAsset()->GetRefSkeleton();
	const auto& CS = M->GetComponentSpaceTransforms();
	for (int32 I = 0; I < CS.Num(); ++I)
	{
		S.Names.Add(Ref.GetBoneName(I));
		S.World.Add(CS[I] * M->GetComponentTransform());
		const int32 Parent = Ref.GetParentIndex(I);
		S.Local.Add(Parent == INDEX_NONE ? CS[I] : CS[I].GetRelativeTransform(CS[Parent]));
	}
	for (FBodyInstance* B : M->Bodies)
	{
		if (!B || !B->BodySetup.IsValid() || !B->IsValidBodyInstance()) continue;
		const int32 I = S.Names.IndexOfByKey(B->BodySetup->BoneName);
		if (I == INDEX_NONE) continue;
		// Dynamic bodies own their state. New dynamic bodies start at the visible
		// bone, never at a stale kinematic target left in the physics scene.
		S.Bodies.Add({B->BodySetup->BoneName,
			B->IsInstanceSimulatingPhysics() ? B->GetUnrealWorldTransform() : S.World[I],
			B->GetUnrealWorldVelocity(), B->GetUnrealWorldAngularVelocityInRadians()});
	}
}

ProphecyModeTransitions::FScope::~FScope()
{
	FPose* Found = Storage().Captures.Find(Agent);
	if (!Found || --Found->Depth != 0) return;
	FPose S = MoveTemp(*Found);
	Storage().Captures.Remove(Agent);
	USkeletalMeshComponent* M = S.Mesh.Get();
	if (!M || S.World.IsEmpty() || Agent->GetSimulationMode() == S.Mode) return;
	const auto NewMode = Agent->GetSimulationMode();
	S.Start = Agent->GetWorld()->GetTimeSeconds();
	// Mode switches can restore a different mesh carrier. Non-root local bones
	// are invariant under that change; the root local transform is not.
	S.Local[0] = S.World[0].GetRelativeTransform(M->GetComponentTransform());
	Storage().Blends.Add(Agent, S);
	RegisterFinalizer(Agent, M);
	ProphecyAttackFists::EnsureManualSimulation(Agent);
	// Publish exactly the captured visible pose in the new component frame.
	// Both animation proxies apply the transition snapshot after the fist layer.
	M->TickAnimation(0, false);
	M->RefreshBoneTransforms();
	// SetRelativeTransform/Refresh inside a mode switch can queue a TELEPORT
	// kinematic update. Chaos would execute that on the next frame using the
	// next animation pose, overwriting even the restored simulated bodies.
	// Consume only this mesh's pending update now, without teleporting dynamics.
	if (FPhysScene* Scene = Agent->GetWorld()->GetPhysicsScene()) Scene->ClearPreSimKinematicUpdate(M);
	M->UpdateKinematicBonesToAnim(M->GetComponentSpaceTransforms(), ETeleportType::None, false,
		EAllowKinematicDeferral::DisallowDeferral);
	if (NewMode != EProphecyAgentSimulationMode::Kinematic)
	{
		for (const FBody& Saved : S.Bodies)
		{
			FBodyInstance* B = M->GetBodyInstance(Saved.Name);
			if (!B || !B->IsInstanceSimulatingPhysics()) continue;
			B->SetBodyTransform(Saved.World, ETeleportType::TeleportPhysics, false);
			B->SetLinearVelocity(Saved.Linear, false, false);
			B->SetAngularVelocityInRadians(Saved.Angular, false, false);
		}
		// Rebase the component-to-physics-root offset *after* restoring bodies.
		// Otherwise EndPhysics applies the pre-restore cache on the next frame.
		M->SetRootBodyIndex(M->FindRootBodyIndex());
	}
	if (auto* Sword = Agent->FindComponentByClass<UProphecySwordComponent>()) Sword->RefreshHandConstraint();
}

void ProphecyModeTransitions::PreUpdate(const void* Proxy, const AProphecyAgent* A)
{
	FSnapshot Snapshot;
	if (A)
	{
		const FPose* S = Storage().Blends.Find(A);
		USkeletalMeshComponent* M = A->GetPoseReferenceMesh();
		if (S && M && S->Mesh == M)
		{
			const double T = FMath::Clamp((A->GetWorld()->GetTimeSeconds() - S->Start) / BlendSeconds, 0., 1.);
			Snapshot.Alpha = float(T*T*(3-2*T));
			Snapshot.bManualSim = A->bManualNNPoseApplication && A->GetSimulationMode() == EProphecyAgentSimulationMode::Physical;
			Snapshot.bLocal = A->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic && T > 0;
			Snapshot.Names = S->Names;
			Snapshot.FromLocal = S->Local;
			for (const FBody& B : S->Bodies) Snapshot.PhysicalBones.Add(B.Name);
			for (const FTransform& W : S->World) Snapshot.FromCS.Add(W.GetRelativeTransform(M->GetComponentTransform()));
		}
	}
	FScopeLock Lock(&Storage().Lock);
	Storage().Snapshots.Add(Proxy, MoveTemp(Snapshot));
}

void ProphecyModeTransitions::Evaluate(const void* Proxy, FPoseContext& Output)
{
	FScopeLock Lock(&Storage().Lock);
	const FSnapshot* S = Storage().Snapshots.Find(Proxy);
	if (!S || S->Names.IsEmpty()) return;
	const FBoneContainer& Container = Output.Pose.GetBoneContainer();
	TArray<FTransform> Desired;
	Desired.SetNum(Output.Pose.GetNumBones());
	TArray<FTransform> Original;
	Original.SetNum(Output.Pose.GetNumBones());
	for (const FCompactPoseBoneIndex I : Output.Pose.ForEachBoneIndex())
	{
		const int32 Source = S->Names.IndexOfByKey(Container.GetReferenceSkeleton().GetBoneName(Container.GetSkeletonIndex(I)));
		const FCompactPoseBoneIndex P = Container.GetParentBoneIndex(I);
		if (S->bLocal)
		{
			if (Source != INDEX_NONE)
			{
				// The manual Sim proxy has no body animation. Preserve the local
				// frame of its non-physical root/IK/twist helpers instead of resetting
				// them to a differently oriented reference pose on the following tick.
				const bool bKeep = S->bManualSim && !S->PhysicalBones.Contains(S->Names[Source]) && !IsFinger(S->Names[Source]);
				FTransform T;
				T.Blend(S->FromLocal[Source], Output.Pose[I], bKeep ? 0.f : S->Alpha);
				Output.Pose[I] = T;
			}
			continue;
		}
		FTransform Current = P.IsValid() ? Output.Pose[I] * Original[P.GetInt()] : Output.Pose[I];
		Original[I.GetInt()] = Current;
		Desired[I.GetInt()] = Current;
		if (Source != INDEX_NONE) Desired[I.GetInt()].Blend(S->FromCS[Source], Current, S->Alpha);
	}
	if (!S->bLocal)
	{
		for (const FCompactPoseBoneIndex I : Output.Pose.ForEachBoneIndex())
		{
			const FCompactPoseBoneIndex P = Container.GetParentBoneIndex(I);
			Output.Pose[I] = P.IsValid() ? Desired[I.GetInt()].GetRelativeTransform(Desired[P.GetInt()]) : Desired[I.GetInt()];
		}
	}
}

void ProphecyModeTransitions::ReleaseProxy(const void* P)
{
	FScopeLock Lock(&Storage().Lock);
	Storage().Snapshots.Remove(P);
}
void ProphecyModeTransitions::ReleaseAgent(const AProphecyAgent* A)
{
	FFinalizeRegistration Registration;
	if (FinalizeRegistrations().RemoveAndCopyValue(A, Registration))
		if (auto* Mesh = Registration.Mesh.Get()) Mesh->UnregisterOnBoneTransformsFinalizedDelegate(Registration.Handle);
	Storage().Blends.Remove(A);
	Storage().Captures.Remove(A);
}
