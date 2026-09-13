#include "ProphecyModeTransitions.h"
#include "ProphecyAgent.h"
#include "ProphecyAttackFists.h"
#include "ProphecySwordComponent.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNodeBase.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "Misc/ScopeLock.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#endif

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
	FStorage& ModeTransitionStorage() { static FStorage* S = new FStorage; return *S; }
	struct FFinalizeRegistration { TWeakObjectPtr<USkeletalMeshComponent> Mesh; FDelegateHandle Handle; };
	auto& FinalizeRegistrations()
	{
		static auto* Registrations = new TMap<TWeakObjectPtr<const AProphecyAgent>, FFinalizeRegistration>;
		return *Registrations;
	}
	FTransform WithParentTranslationCorrection(const FTransform& OriginalChild,
		const FTransform& OriginalParent, const FTransform& CorrectedParent)
	{
		FTransform CorrectedChild = OriginalChild;
		CorrectedChild.AddToTranslation(CorrectedParent.GetTranslation() - OriginalParent.GetTranslation());
		return CorrectedChild;
	}
	void CorrectScaledPhysicsPose(const AProphecyAgent* Agent)
	{
		// This repair addresses Chaos physics blending. Jolt already publishes the complete
		// physical pose and its query proxies before this callback; retain that authoritative
		// result without a second local/parent round trip on its finalized render buffer.
		if (!IsValid(Agent) || Agent->IsJoltPhysicalAnimationEnabled()
			|| Agent->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic) return;
		const FPose* Blend = ModeTransitionStorage().Blends.Find(Agent);
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
				// Every parent correction above changes translation only. Propagate
				// that displacement while preserving the evaluated rotation and scale;
				// a relative/parent round trip needlessly compounds quaternion error.
				Final[I] = WithParentTranslationCorrection(Original[I], Original[Parent], Final[Parent]);
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
	FPose& S = ModeTransitionStorage().Captures.FindOrAdd(A);
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
	FPose* Found = ModeTransitionStorage().Captures.Find(Agent);
	if (!Found || --Found->Depth != 0) return;
	FPose S = MoveTemp(*Found);
	ModeTransitionStorage().Captures.Remove(Agent);
	USkeletalMeshComponent* M = S.Mesh.Get();
	if (!M || S.World.IsEmpty() || Agent->GetSimulationMode() == S.Mode) return;
	const auto NewMode = Agent->GetSimulationMode();
	S.Start = Agent->GetWorld()->GetTimeSeconds();
	// Mode switches can restore a different mesh carrier. Non-root local bones
	// are invariant under that change; the root local transform is not.
	S.Local[0] = S.World[0].GetRelativeTransform(M->GetComponentTransform());
	ModeTransitionStorage().Blends.Add(Agent, S);
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
		const FPose* S = ModeTransitionStorage().Blends.Find(A);
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
	FScopeLock Lock(&ModeTransitionStorage().Lock);
	ModeTransitionStorage().Snapshots.Add(Proxy, MoveTemp(Snapshot));
}

void ProphecyModeTransitions::Evaluate(const void* Proxy, FPoseContext& Output)
{
	FScopeLock Lock(&ModeTransitionStorage().Lock);
	const FSnapshot* S = ModeTransitionStorage().Snapshots.Find(Proxy);
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
	FScopeLock Lock(&ModeTransitionStorage().Lock);
	ModeTransitionStorage().Snapshots.Remove(P);
}
void ProphecyModeTransitions::ReleaseAgent(const AProphecyAgent* A)
{
	FFinalizeRegistration Registration;
	if (FinalizeRegistrations().RemoveAndCopyValue(A, Registration))
		if (auto* Mesh = Registration.Mesh.Get()) Mesh->UnregisterOnBoneTransformsFinalizedDelegate(Registration.Handle);
	ModeTransitionStorage().Blends.Remove(A);
	ModeTransitionStorage().Captures.Remove(A);
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyModeTranslationCorrectionTest,
	"Prophecy.Agent.ModeTransitions.TranslationOnlyDescendants",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyModeTranslationCorrectionTest::RunTest(const FString& Parameters)
{
	const int32 Parents[] = { INDEX_NONE, 0, 1, 2, 1, 4 };
	const FVector MainDisplacement(0.125, -0.25, 0.375);
	const FVector BranchDisplacement(-0.5, 0.125, 0.25);
	constexpr int32 Frames = 300;
	for (const double RotationSizeSquared : { 1.0, 1.004 })
	{
		TArray<FTransform> Initial;
		for (int32 Bone = 0; Bone < UE_ARRAY_COUNT(Parents); ++Bone)
		{
			// Both cases satisfy UE's rotation contract. The second deliberately
			// retains a small existing error that this translation repair must not amplify.
			const FQuat Rotation = FQuat(FRotator(7.0 * Bone, 19.0 * Bone, -11.0 * Bone))
				* FMath::Sqrt(RotationSizeSquared);
			Initial.Emplace(Rotation, FVector(13.0 * Bone, -9.0 * Bone, 17.0 * Bone),
				FVector(1.0 + 0.25 * Bone, 0.5 + 0.125 * Bone, 1.5 + 0.125 * Bone));
			TestTrue(TEXT("Input rotation satisfies UE normalization tolerance"), Initial.Last().IsRotationNormalized());
		}

		FTransform CorrectedParent = Initial[1];
		CorrectedParent.AddToTranslation(MainDisplacement);
		const FTransform RoundTrip = Initial[2].GetRelativeTransform(Initial[1]) * CorrectedParent;
		const FTransform Translated = WithParentTranslationCorrection(Initial[2], Initial[1], CorrectedParent);
		if (RotationSizeSquared == 1.0)
		{
			TestTrue(TEXT("Unit rotations and nonuniform scales retain the original repair's pose"),
				Translated.Equals(RoundTrip, 1.e-8));
		}
		else
		{
			TestFalse(TEXT("Former round trip can turn valid inputs into an invalid rotation"),
				RoundTrip.IsRotationNormalized());
		}

		TArray<FTransform> Current = Initial;
		for (int32 Frame = 0; Frame < Frames; ++Frame)
		{
			const TArray<FTransform> Previous = Current;
			// A second simulated body owns its own correction. Its descendants
			// must inherit that displacement, not the correction above it in the hierarchy.
			Current[1].AddToTranslation(MainDisplacement);
			Current[4].AddToTranslation(BranchDisplacement);
			for (const int32 Bone : { 2, 3, 5 })
				Current[Bone] = WithParentTranslationCorrection(Previous[Bone],
					Previous[Parents[Bone]], Current[Parents[Bone]]);
		}
		for (int32 Bone = 0; Bone < Current.Num(); ++Bone)
		{
			const FVector Displacement = Bone == 0 ? FVector::ZeroVector
				: Bone < 4 ? MainDisplacement : BranchDisplacement;
			TestTrue(TEXT("Descendants inherit the nearest corrected parent's translation"),
				Current[Bone].GetTranslation().Equals(Initial[Bone].GetTranslation() + Frames * Displacement, 1.e-9));
			const FQuat BeforeRotation = Initial[Bone].GetRotation(), AfterRotation = Current[Bone].GetRotation();
			const FVector BeforeScale = Initial[Bone].GetScale3D(), AfterScale = Current[Bone].GetScale3D();
			TestTrue(TEXT("Rotation bits remain unchanged across repeated hierarchy corrections"),
				FMemory::Memcmp(&BeforeRotation, &AfterRotation, sizeof(FQuat)) == 0);
			TestTrue(TEXT("Nonuniform scale bits remain unchanged"),
				FMemory::Memcmp(&BeforeScale, &AfterScale, sizeof(FVector)) == 0);
		}
	}
	return true;
}
#endif
