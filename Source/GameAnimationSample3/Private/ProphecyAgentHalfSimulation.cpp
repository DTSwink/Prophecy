#include "ProphecyAgent.h"
#include "ProphecyModeTransitions.h"
#include "ProphecyAttackFists.h"

#include "ProphecyNNPoseTypes.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

namespace
{
	// External storage: do not change the layout of any existing live native allocation.
	struct FHalfSimulationState
	{
		TWeakObjectPtr<USkeletalMeshComponent> Mesh;
		TEnumAsByte<EPhysicsTransformUpdateMode::Type> TransformUpdateMode;
		TEnumAsByte<EKinematicBonesUpdateToPhysics::Type> BonesUpdateMode;
		EVisibilityBasedAnimTickOption VisibilityTick;
		ECollisionEnabled::Type Collision;
		ECollisionChannel ObjectType;
		FCollisionResponseContainer Responses;
		FCollisionResponseContainer CapsuleResponses;
		FTransform RelativeTransform;
		bool bGravity, bURO, bMeshTick, bUpdateJoints, bDriveConfigured;
		TMap<FName, FConstraintProfileProperties> JointProfiles;
	};
	TMap<TWeakObjectPtr<AProphecyAgent>, FHalfSimulationState> HalfSimulationStates;

	struct FHalfTransitionBody
	{
		FName Name;
		FTransform World;
		FVector Linear, Angular;
	};
	using FHalfTransitionBodies = TArray<FHalfTransitionBody, TInlineAllocator<32>>;

	FHalfTransitionBodies CaptureHalfTransitionBodies(USkeletalMeshComponent* Mesh)
	{
		FHalfTransitionBodies Result;
		for (const FBodyInstance* Body : Mesh->Bodies)
		{
			if (Body && Body->BodySetup.IsValid() && Body->IsInstanceSimulatingPhysics())
			{
				Result.Add({Body->BodySetup->BoneName, Body->GetUnrealWorldTransform(),
					Body->GetUnrealWorldVelocity(), Body->GetUnrealWorldAngularVelocityInRadians()});
			}
		}
		return Result;
	}

	void RestoreHalfTransitionBodies(USkeletalMeshComponent* Mesh, const FHalfTransitionBodies& Bodies)
	{
		// Only the mode transition restores state; there is no per-frame body correction.
		for (const FHalfTransitionBody& Saved : Bodies)
		{
			if (FBodyInstance* Body = Mesh->GetBodyInstance(Saved.Name);
				Body && Body->IsInstanceSimulatingPhysics())
			{
				Body->SetBodyTransform(Saved.World, ETeleportType::TeleportPhysics, false);
				Body->SetLinearVelocity(Saved.Linear, false, false);
				Body->SetAngularVelocityInRadians(Saved.Angular, false, false);
			}
		}
	}
}

bool AProphecyAgent::EnterHalfSimulation()
{
	ProphecyModeTransitions::FScope Transition(this);
	USkeletalMeshComponent* PoseMesh = GetPoseReferenceMesh();
	int32 PoseId;
	float Interval;
	bool bInterpolate;
	FProphecyNNPoseSnapshot Pose;
	if (!PoseMesh || !PhysicalAnimation || !PoseMesh->GetSkeletalMeshAsset() ||
		!PoseMesh->GetPhysicsAsset() ||
		PoseMesh->GetPhysicsAsset()->FindBodyIndex(PhysicalRootBodyName) == INDEX_NONE ||
		!GetNNPoseDataSource(PoseId, Interval, bInterpolate) ||
		!FProphecyNNPoseStore::GetAgentLocalPose(PoseId, Pose) || !Pose.IsValid())
	{
		return false;
	}

	const FHalfTransitionBodies Bodies = CaptureHalfTransitionBodies(PoseMesh);
	const bool bAlreadySimulating = GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic;
	ReleaseManualFollowerSubstepTargets();
	FHalfSimulationState& Saved = HalfSimulationStates.FindOrAdd(this);
	Saved.Mesh = PoseMesh;
	Saved.TransformUpdateMode = PoseMesh->PhysicsTransformUpdateMode;
	Saved.BonesUpdateMode = PoseMesh->KinematicBonesUpdateType;
	Saved.VisibilityTick = PoseMesh->VisibilityBasedAnimTickOption;
	Saved.Collision = PoseMesh->GetCollisionEnabled();
	Saved.ObjectType = PoseMesh->GetCollisionObjectType();
	Saved.Responses = PoseMesh->GetCollisionResponseToChannels();
	Saved.CapsuleResponses = Capsule->GetCollisionResponseToChannels();
	Saved.RelativeTransform = PoseMesh->GetRelativeTransform();
	Saved.bGravity = PoseMesh->IsGravityEnabled();
	Saved.bURO = PoseMesh->bEnableUpdateRateOptimizations;
	Saved.bMeshTick = PoseMesh->IsComponentTickEnabled();
	Saved.bUpdateJoints = PoseMesh->bUpdateJointsFromAnimation;
	Saved.bDriveConfigured = bPhysicalDriveConfigured;
	for (const FConstraintInstance* Joint : PoseMesh->Constraints)
	{
		if (Joint) Saved.JointProfiles.Add(Joint->JointName, Joint->ProfileInstance);
	}

	// Keep the carrier on the mover, but simulate all of its named PHAT bodies.
	SimulationMode = EProphecyAgentSimulationMode::HalfSim;
	PhysicalTargetComponentRelativeTransform = Saved.RelativeTransform;
	PoseMesh->PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::ComponentTransformIsKinematic;
	PoseMesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
	PoseMesh->bEnableUpdateRateOptimizations = false;
	PoseMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	PoseMesh->SetComponentTickEnabled(true);
	PoseMesh->bUpdateJointsFromAnimation = false;
	PoseMesh->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
	if (UProphecyNNLocomotionAnimInstance* Anim = GetProphecyAnimInstance())
	{
		Anim->AgentId = PoseId;
		Anim->NNPoseIntervalSeconds = Interval;
		Anim->bInterpolateNNPose = bInterpolate;
		Anim->bUseViewerGlobalPoseInterpolation = bInterpolate;
	}
	PoseMesh->TickAnimation(0.0f, false);
	PoseMesh->RefreshBoneTransforms();
	PoseMesh->SetCollisionObjectType(ECC_PhysicsBody);
	PoseMesh->SetCollisionResponseToAllChannels(ECR_Ignore);
	PoseMesh->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
	PoseMesh->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
	PoseMesh->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Block);
	PoseMesh->SetCollisionResponseToChannel(ECC_GameTraceChannel9, ECR_Block);
	Capsule->SetCollisionResponseToChannel(ECC_PhysicsBody, ECR_Ignore);
	PoseMesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	PoseMesh->SetEnableGravity(true);
	PoseMesh->SetNotifyRigidBodyCollision(bGeneratePhysicalHitEvents);
	if (!bAlreadySimulating) PoseMesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, true, true);
	PoseMesh->SetAllBodiesBelowPhysicsBlendWeight(PhysicalRootBodyName, 1.0f, false, true);
	SetMACDEnabled(bMACDEnabled);
	ApplyPhysicalSolverSettings();
	RefreshHalfSimulationDrives();
	RestoreHalfTransitionBodies(PoseMesh, Bodies);
	PoseMesh->WakeAllRigidBodies();
	bPendingHalfSimulation = false;
	SetActorTickEnabled(true);
	return true;
}

void AProphecyAgent::ApplyHalfSimulationBodyStrength(FName BoneName)
{
	if (SimulationMode != EProphecyAgentSimulationMode::HalfSim || !PhysicalAnimation) return;
	FPhysicalAnimationData Data = PhysicalDriveSettings;
	Data.bIsLocalSimulation = false;
	if (const FProphecyBodyMagnetizationSettings* Settings = BodyMagnetizationSettings.Find(BoneName))
	{
		const float Linear = Settings->bMagnetizationEnabled ? Settings->LinearStrengthScale : 0.0f;
		const float Angular = Settings->bMagnetizationEnabled ? Settings->AngularStrengthScale : 0.0f;
		Data.PositionStrength *= Linear;
		Data.VelocityStrength *= Linear;
		Data.MaxLinearForce *= Linear;
		Data.OrientationStrength *= Angular;
		Data.AngularVelocityStrength *= Angular;
		Data.MaxAngularForce *= Angular;
	}
	PhysicalAnimation->ApplyPhysicalAnimationSettings(BoneName, Data);
}

bool AProphecyAgent::RefreshHalfSimulationDrives()
{
	USkeletalMeshComponent* PoseMesh = GetPoseReferenceMesh();
	if (!PoseMesh || !PoseMesh->GetPhysicsAsset() || !PhysicalAnimation) return false;
	PhysicalAnimation->SetSkeletalMeshComponent(PoseMesh);
	const FReferenceSkeleton& Skeleton = PoseMesh->GetSkeletalMeshAsset()->GetRefSkeleton();
	const int32 Root = Skeleton.FindBoneIndex(PhysicalRootBodyName);
	for (const USkeletalBodySetup* Body : PoseMesh->GetPhysicsAsset()->SkeletalBodySetups)
	{
		if (!Body) continue;
		const int32 Index = Skeleton.FindBoneIndex(Body->BoneName);
		if (Index == Root || (Index != INDEX_NONE && Skeleton.BoneIsChildOf(Index, Root)))
		{
			ApplyHalfSimulationBodyStrength(Body->BoneName);
		}
	}
	// Same calibration as the accepted native test: free angular axes, rigid anchors.
	for (FConstraintInstance* Joint : PoseMesh->Constraints)
	{
		if (!Joint) continue;
		Joint->SetAngularSwing1Limit(ACM_Free, 0.0f);
		Joint->SetAngularSwing2Limit(ACM_Free, 0.0f);
		Joint->SetAngularTwistLimit(ACM_Free, 0.0f);
		Joint->SetOrientationDriveSLERP(false);
		Joint->SetAngularVelocityDriveSLERP(false);
	}
	PhysicalAnimation->SetStrengthMultiplyer(PhysicalDriveStrengthMultiplier);
	PhysicalAnimation->SetComponentTickEnabled(true);
	return true;
}

bool AProphecyAgent::LeaveHalfSimulation(EProphecyAgentSimulationMode NextMode)
{
	FHalfSimulationState Saved;
	if (!HalfSimulationStates.RemoveAndCopyValue(this, Saved)) return false;
	USkeletalMeshComponent* PoseMesh = Saved.Mesh.Get();
	if (!PoseMesh) return false;
	const FHalfTransitionBodies Bodies = CaptureHalfTransitionBodies(PoseMesh);
	PhysicalAnimation->SetStrengthMultiplyer(0.0f);
	PhysicalAnimation->SetComponentTickEnabled(false);
	PhysicalAnimation->RemoveTickPrerequisiteComponent(PoseMesh);
	PhysicalAnimation->SetSkeletalMeshComponent(nullptr);
	if (NextMode == EProphecyAgentSimulationMode::Physical && bManualNNPoseApplication)
	{
		// Both modes use the same dynamic bodies. Do not bounce them through
		// Kinematic: that queues animation targets/state changes inside Chaos,
		// which can replace restored rotations on the following physics step.
		PoseMesh->PhysicsTransformUpdateMode = Saved.TransformUpdateMode;
		PoseMesh->KinematicBonesUpdateType = Saved.BonesUpdateMode;
		PoseMesh->bUpdateJointsFromAnimation = Saved.bUpdateJoints;
		PoseMesh->SetEnableGravity(Saved.bGravity);
		PoseMesh->SetCollisionObjectType(Saved.ObjectType);
		PoseMesh->SetCollisionResponseToChannels(Saved.Responses);
		PoseMesh->SetCollisionEnabled(Saved.Collision);
		Capsule->SetCollisionResponseToChannels(Saved.CapsuleResponses);
		for (FConstraintInstance* Joint : PoseMesh->Constraints)
		{
			if (!Joint) continue;
			if (const FConstraintProfileProperties* Profile = Saved.JointProfiles.Find(Joint->JointName))
				Joint->CopyProfilePropertiesFrom(*Profile);
		}
		SimulationMode = EProphecyAgentSimulationMode::Physical;
		bPhysicalDriveConfigured = Saved.bDriveConfigured;
		PhysicalTargetComponentRelativeTransform = PoseMesh->GetRelativeTransform();
		PoseMesh->SetAnimInstanceClass(nullptr);
		ProphecyAttackFists::EnsureManualSimulation(this);
		RestoreHalfTransitionBodies(PoseMesh, Bodies);
		ApplyPhysicalSolverSettings();
		SetMACDEnabled(bMACDEnabled);
		SetActorTickEnabled(true);
		return true;
	}
	PoseMesh->SetAllBodiesSimulatePhysics(false);
	PoseMesh->SetAllBodiesPhysicsBlendWeight(0.0f);
	PoseMesh->PhysicsTransformUpdateMode = Saved.TransformUpdateMode;
	PoseMesh->KinematicBonesUpdateType = Saved.BonesUpdateMode;
	PoseMesh->bEnableUpdateRateOptimizations = Saved.bURO;
	PoseMesh->VisibilityBasedAnimTickOption = Saved.VisibilityTick;
	PoseMesh->bUpdateJointsFromAnimation = Saved.bUpdateJoints;
	PoseMesh->SetEnableGravity(Saved.bGravity);
	PoseMesh->SetCollisionObjectType(Saved.ObjectType);
	PoseMesh->SetCollisionResponseToChannels(Saved.Responses);
	PoseMesh->SetCollisionEnabled(Saved.Collision);
	Capsule->SetCollisionResponseToChannels(Saved.CapsuleResponses);
	for (FConstraintInstance* Joint : PoseMesh->Constraints)
	{
		if (!Joint) continue;
		if (const FConstraintProfileProperties* Profile = Saved.JointProfiles.Find(Joint->JointName))
		{
			Joint->CopyProfilePropertiesFrom(*Profile);
		}
	}
	PoseMesh->SetRelativeTransform(Saved.RelativeTransform, false, nullptr, ETeleportType::TeleportPhysics);
	SimulationMode = EProphecyAgentSimulationMode::Kinematic;
	bPhysicalDriveConfigured = Saved.bDriveConfigured;
	PoseMesh->TickAnimation(0.0f, false);
	PoseMesh->RefreshBoneTransforms();
	PoseMesh->SetComponentTickEnabled(Saved.bMeshTick);
	PoseMesh->SetNotifyRigidBodyCollision(false);
	if (NextMode == EProphecyAgentSimulationMode::Physical)
	{
		// Rebuild native drives if this nonmanual pawn previously used PerBodyWorld.
		if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::PerBodyWorld) bPhysicalDriveConfigured = false;
		if (!SetSimulationMode(NextMode)) return false;
		RestoreHalfTransitionBodies(PoseMesh, Bodies);
	}
	SetActorTickEnabled(true);
	return true;
}

void AProphecyAgent::ReleaseHalfSimulationState()
{
	HalfSimulationStates.Remove(this);
	bPendingHalfSimulation = false;
}
