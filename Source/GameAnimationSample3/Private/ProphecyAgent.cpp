#include "ProphecyAgent.h"

#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"

#include "Chaos/ChaosConstraintSettings.h"
#include "Chaos/ChaosEngineInterface.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Volume.h"
#include "HAL/IConsoleManager.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	DEFINE_LOG_CATEGORY_STATIC(LogProphecyAgentPhysical, Log, All);
	TAutoConsoleVariable<int32> CVarProphecyPhysicalLogTrackingError(
		TEXT("prophecy.Physical.LogTrackingError"),
		0,
		TEXT("Log authored-target versus actual Chaos joint error for one Physical agent."));
	TAutoConsoleVariable<int32> CVarProphecyPhysicalLogPelvisError(
		TEXT("prophecy.Physical.LogPelvisError"),
		0,
		TEXT("Log authored-target versus physical pelvis orientation and angular velocity."));
	TAutoConsoleVariable<int32> CVarProphecyAuditManualPhysicalFollower(
		TEXT("prophecy.Physical.AuditManualFollower"),
		0,
		TEXT("At the start of each ProphecyAgent PrePhysics tick, measure the Blueprint PhysicalMesh against the exact kinematic targets saved after the preceding tick."));

	struct FManualFollowerErrorAggregate
	{
		int32 Samples = 0;
		double SumPositionCm = 0.0;
		double SumSquaredPositionCm = 0.0;
		double MaximumPositionCm = 0.0;
		double SumRotationDegrees = 0.0;
		double SumSquaredRotationDegrees = 0.0;
		double MaximumRotationDegrees = 0.0;

		void Add(double PositionCm, double RotationDegrees)
		{
			++Samples;
			SumPositionCm += PositionCm;
			SumSquaredPositionCm += PositionCm * PositionCm;
			MaximumPositionCm = FMath::Max(MaximumPositionCm, PositionCm);
			SumRotationDegrees += RotationDegrees;
			SumSquaredRotationDegrees += RotationDegrees * RotationDegrees;
			MaximumRotationDegrees = FMath::Max(MaximumRotationDegrees, RotationDegrees);
		}

		void Reset()
		{
			*this = FManualFollowerErrorAggregate();
		}
	};

	struct FManualFollowerAuditState
	{
		TArray<FTransform, TInlineAllocator<9>> PreviousEndpointTargets;
		uint64 TargetFrame = MAX_uint64;
		float PreviousStepDeltaSeconds = 0.0f;
		FVector PreviousTargetPelvisLocation = FVector::ZeroVector;
		bool bHasPreviousTargetPelvisLocation = false;
		int32 WindowSteps = 0;
		double SumTargetSpeedCmPerSecond = 0.0;
		FManualFollowerErrorAggregate RootWorldError;
		FManualFollowerErrorAggregate PelvisRelativeLimbError;
		TArray<FManualFollowerErrorAggregate, TInlineAllocator<7>> PerBoneRelativeError;
	};

	static const FName ManualFollowerAuditBones[] = {
		TEXT("pelvis"),
		TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"),
		TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r") };
	static TMap<TWeakObjectPtr<AProphecyAgent>, FManualFollowerAuditState> ManualFollowerAuditStates;

	USkeletalMeshComponent* FindManualPhysicalMesh(AProphecyAgent* Agent)
	{
		TArray<USkeletalMeshComponent*> SkeletalMeshes;
		Agent->GetComponents(SkeletalMeshes);
		for (USkeletalMeshComponent* Candidate : SkeletalMeshes)
		{
			if (Candidate && Candidate->GetFName() == TEXT("PhysicalMesh"))
			{
				return Candidate;
			}
		}
		return nullptr;
	}

	void AuditManualPhysicalFollowerBeforeTick(AProphecyAgent* Agent)
	{
		FManualFollowerAuditState* State = ManualFollowerAuditStates.Find(Agent);
		if (!State || State->TargetFrame + 1 != GFrameCounter ||
			State->PreviousEndpointTargets.Num() != UE_ARRAY_COUNT(ManualFollowerAuditBones))
		{
			return;
		}

		USkeletalMeshComponent* PhysicalMesh = FindManualPhysicalMesh(Agent);
		if (!PhysicalMesh || !PhysicalMesh->IsAnySimulatingPhysics())
		{
			return;
		}

		TArray<FTransform, TInlineAllocator<9>> ActualTransforms;
		ActualTransforms.Reserve(UE_ARRAY_COUNT(ManualFollowerAuditBones));
		for (const FName BoneName : ManualFollowerAuditBones)
		{
			ActualTransforms.Add(PhysicalMesh->GetSocketTransform(BoneName, RTS_World));
		}

		const FTransform& TargetPelvis = State->PreviousEndpointTargets[0];
		const FTransform& ActualPelvis = ActualTransforms[0];
		const double RootPositionErrorCm = FVector::Distance(
			TargetPelvis.GetLocation(), ActualPelvis.GetLocation());
		const double RootRotationErrorDegrees = FMath::RadiansToDegrees(
			TargetPelvis.GetRotation().AngularDistance(ActualPelvis.GetRotation()));
		State->RootWorldError.Add(RootPositionErrorCm, RootRotationErrorDegrees);

		for (int32 BoneIndex = 1; BoneIndex < ActualTransforms.Num(); ++BoneIndex)
		{
			if (State->PerBoneRelativeError.Num() != ActualTransforms.Num())
			{
				State->PerBoneRelativeError.SetNum(ActualTransforms.Num());
			}
			const FTransform TargetRelative =
				State->PreviousEndpointTargets[BoneIndex].GetRelativeTransform(TargetPelvis);
			const FTransform ActualRelative =
				ActualTransforms[BoneIndex].GetRelativeTransform(ActualPelvis);
			const double PositionErrorCm = FVector::Distance(
				TargetRelative.GetLocation(), ActualRelative.GetLocation());
			const double RotationErrorDegrees = FMath::RadiansToDegrees(
				TargetRelative.GetRotation().AngularDistance(ActualRelative.GetRotation()));
			State->PelvisRelativeLimbError.Add(PositionErrorCm, RotationErrorDegrees);
			State->PerBoneRelativeError[BoneIndex].Add(PositionErrorCm, RotationErrorDegrees);
		}

		double TargetSpeedCmPerSecond = 0.0;
		if (State->bHasPreviousTargetPelvisLocation && State->PreviousStepDeltaSeconds > UE_SMALL_NUMBER)
		{
			TargetSpeedCmPerSecond = FVector::Distance(
				TargetPelvis.GetLocation(), State->PreviousTargetPelvisLocation) /
				State->PreviousStepDeltaSeconds;
		}
		State->PreviousTargetPelvisLocation = TargetPelvis.GetLocation();
		State->bHasPreviousTargetPelvisLocation = true;
		State->SumTargetSpeedCmPerSecond += TargetSpeedCmPerSecond;
		++State->WindowSteps;

		constexpr int32 ReportIntervalSteps = 60;
		if (State->WindowSteps < ReportIntervalSteps)
		{
			return;
		}

		auto Mean = [](double Sum, int32 Count)
		{
			return Count > 0 ? Sum / double(Count) : 0.0;
		};
		auto Rms = [](double SumSquares, int32 Count)
		{
			return Count > 0 ? FMath::Sqrt(SumSquares / double(Count)) : 0.0;
		};
		FString PerBoneErrors;
		for (int32 BoneIndex = 1; BoneIndex < State->PerBoneRelativeError.Num(); ++BoneIndex)
		{
			const FManualFollowerErrorAggregate& BoneError = State->PerBoneRelativeError[BoneIndex];
			PerBoneErrors += FString::Printf(
				TEXT(" %s_cm=%.4f/%.4f/%.4f %s_deg=%.4f/%.4f/%.4f"),
				*ManualFollowerAuditBones[BoneIndex].ToString(),
				Mean(BoneError.SumPositionCm, BoneError.Samples),
				Rms(BoneError.SumSquaredPositionCm, BoneError.Samples),
				BoneError.MaximumPositionCm,
				*ManualFollowerAuditBones[BoneIndex].ToString(),
				Mean(BoneError.SumRotationDegrees, BoneError.Samples),
				Rms(BoneError.SumSquaredRotationDegrees, BoneError.Samples),
				BoneError.MaximumRotationDegrees);
		}
		UE_LOG(LogProphecyAgentPhysical, Display,
			TEXT("MANUAL_FOLLOW_PREPHYSICS_AUDIT actor=%s previous_steps=%d target_speed_mean_cm_s=%.3f root_world_cm(mean/rms/max)=%.4f/%.4f/%.4f root_world_deg(mean/rms/max)=%.4f/%.4f/%.4f limb_relative_cm(mean/rms/max)=%.4f/%.4f/%.4f limb_relative_deg(mean/rms/max)=%.4f/%.4f/%.4f%s"),
			*Agent->GetName(),
			State->WindowSteps,
			Mean(State->SumTargetSpeedCmPerSecond, State->WindowSteps),
			Mean(State->RootWorldError.SumPositionCm, State->RootWorldError.Samples),
			Rms(State->RootWorldError.SumSquaredPositionCm, State->RootWorldError.Samples),
			State->RootWorldError.MaximumPositionCm,
			Mean(State->RootWorldError.SumRotationDegrees, State->RootWorldError.Samples),
			Rms(State->RootWorldError.SumSquaredRotationDegrees, State->RootWorldError.Samples),
			State->RootWorldError.MaximumRotationDegrees,
			Mean(State->PelvisRelativeLimbError.SumPositionCm, State->PelvisRelativeLimbError.Samples),
			Rms(State->PelvisRelativeLimbError.SumSquaredPositionCm, State->PelvisRelativeLimbError.Samples),
			State->PelvisRelativeLimbError.MaximumPositionCm,
			Mean(State->PelvisRelativeLimbError.SumRotationDegrees, State->PelvisRelativeLimbError.Samples),
			Rms(State->PelvisRelativeLimbError.SumSquaredRotationDegrees, State->PelvisRelativeLimbError.Samples),
			State->PelvisRelativeLimbError.MaximumRotationDegrees,
			*PerBoneErrors);

		State->WindowSteps = 0;
		State->SumTargetSpeedCmPerSecond = 0.0;
		State->RootWorldError.Reset();
		State->PelvisRelativeLimbError.Reset();
		for (FManualFollowerErrorAggregate& BoneError : State->PerBoneRelativeError)
		{
			BoneError.Reset();
		}
	}

	void CaptureManualPhysicalFollowerEndpointAfterTick(AProphecyAgent* Agent, float DeltaSeconds)
	{
		USkeletalMeshComponent* TargetMesh = Agent->GetAgentMesh();
		USkeletalMeshComponent* PhysicalMesh = FindManualPhysicalMesh(Agent);
		if (!TargetMesh || !PhysicalMesh || !PhysicalMesh->IsAnySimulatingPhysics())
		{
			return;
		}

		FManualFollowerAuditState& State = ManualFollowerAuditStates.FindOrAdd(Agent);
		State.PreviousEndpointTargets.Reset();
		State.PreviousEndpointTargets.Reserve(UE_ARRAY_COUNT(ManualFollowerAuditBones));
		for (const FName BoneName : ManualFollowerAuditBones)
		{
			State.PreviousEndpointTargets.Add(TargetMesh->GetSocketTransform(BoneName, RTS_World));
		}
		State.TargetFrame = GFrameCounter;
		State.PreviousStepDeltaSeconds = DeltaSeconds;
	}

	struct FOneFrameParityBody
	{
		FName BoneName;
		FTransform KinematicWorldTransform;
	};

	void RunOneFramePhysicalParity(UWorld* World)
	{
		if (!World || !World->IsGameWorld())
		{
			UE_LOG(LogProphecyAgentPhysical, Error, TEXT("ONE_FRAME_PARITY requires a PIE game world"));
			return;
		}

		AProphecyAgent* Agent = nullptr;
		for (TActorIterator<AProphecyAgent> It(World); It; ++It)
		{
			Agent = *It;
			break;
		}
		if (!Agent)
		{
			UE_LOG(LogProphecyAgentPhysical, Error, TEXT("ONE_FRAME_PARITY found no ProphecyAgent"));
			return;
		}

		// Freeze the policy and select one exact authored 30 Hz frame. This leaves
		// only one Chaos step between the before/after measurements.
		for (TActorIterator<AProphecyNNLocomotionManager> It(World); It; ++It)
		{
			It->SetActorTickEnabled(false);
		}
		USkeletalMeshComponent* Mesh = Agent->GetAgentMesh();
		UProphecyNNLocomotionAnimInstance* Anim =
			Cast<UProphecyNNLocomotionAnimInstance>(Mesh ? Mesh->GetAnimInstance() : nullptr);
		UPhysicsAsset* PhysicsAsset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
		if (!Mesh || !Anim || !PhysicsAsset)
		{
			UE_LOG(LogProphecyAgentPhysical, Error, TEXT("ONE_FRAME_PARITY missing mesh, anim instance, or PhysicsAsset"));
			return;
		}
		if (Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic)
		{
			Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
		}
		Anim->bInterpolateNNPose = false;
		Mesh->TickAnimation(0.0f, false);
		Mesh->RefreshBoneTransforms();

		TArray<FOneFrameParityBody> Bodies;
		Bodies.Reserve(PhysicsAsset->SkeletalBodySetups.Num());
		for (const USkeletalBodySetup* BodySetup : PhysicsAsset->SkeletalBodySetups)
		{
			if (BodySetup)
			{
				Bodies.Add({ BodySetup->BoneName,
					Mesh->GetSocketTransform(BodySetup->BoneName, RTS_World) });
			}
		}
		if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))
		{
			UE_LOG(LogProphecyAgentPhysical, Error, TEXT("ONE_FRAME_PARITY could not enter Physical mode"));
			return;
		}
		Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
		Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		// Constraint-only isolation: no controller, motor, gravity, or collision may
		// alter the captured pose during the single measured Chaos frame.
		Agent->SetActorTickEnabled(false);
		Mesh->SetEnableGravity(false);
		Mesh->SetAllMotorsAngularPositionDrive(false, false, false);
		Mesh->SetAllMotorsAngularVelocityDrive(false, false, false);
		for (FConstraintInstance* Constraint : Mesh->Constraints)
		{
			if (Constraint)
			{
				Constraint->SetOrientationDriveSLERP(false);
				Constraint->SetAngularVelocityDriveSLERP(false);
			}
		}
		IConsoleVariable* DynamicBodyFilterHacks = IConsoleManager::Get().FindConsoleVariable(
			TEXT("p.EnableDynamicPerBodyFilterHacks"));
		const int32 PreviousDynamicBodyFilterHacks = DynamicBodyFilterHacks
			? DynamicBodyFilterHacks->GetInt() : 0;
		if (DynamicBodyFilterHacks)
		{
			DynamicBodyFilterHacks->Set(1, ECVF_SetByCode);
		}
		for (FBodyInstance* Body : Mesh->Bodies)
		{
			if (Body)
			{
				Body->bHACK_DisableCollisionResponse = true;
				Body->UpdatePhysicsFilterData();
			}
		}
		// Retain the production PhysicsAsset limits. A parity result is only valid
		// when the authored pose itself survives the real articulation unchanged.
		if (IConsoleVariable* ParityAngularLimits = IConsoleManager::Get().FindConsoleVariable(
			TEXT("prophecy.Physical.OneFrameAngularLimits")))
		{
			const int32 LimitMode = ParityAngularLimits->GetInt();
			for (FConstraintInstance* Constraint : Mesh->Constraints)
			{
				if (!Constraint)
				{
					continue;
				}
				const bool bLegConstraint =
					Constraint->ConstraintBone1 == TEXT("thigh_l") ||
					Constraint->ConstraintBone1 == TEXT("calf_l") ||
					Constraint->ConstraintBone1 == TEXT("foot_l") ||
					Constraint->ConstraintBone1 == TEXT("thigh_r") ||
					Constraint->ConstraintBone1 == TEXT("calf_r") ||
					Constraint->ConstraintBone1 == TEXT("foot_r");
				if (LimitMode == 3 || (LimitMode == 4 && bLegConstraint))
				{
					Constraint->SetAngularSwing1Limit(ACM_Limited, 179.0f);
					Constraint->SetAngularSwing2Limit(ACM_Limited, 179.0f);
					Constraint->SetAngularTwistLimit(ACM_Limited, 179.0f);
				}
				else if (LimitMode == 0 || (LimitMode == 2 &&
					Constraint->ConstraintBone1 == TEXT("calf_l")) ||
					(LimitMode == 5 && bLegConstraint))
				{
					Constraint->SetAngularSwing1Motion(ACM_Free);
					Constraint->SetAngularSwing2Motion(ACM_Free);
					Constraint->SetAngularTwistMotion(ACM_Free);
				}
			}
		}
		float InitialMaxPositionErrorCm = 0.0f;
		float InitialMaxRotationErrorDegrees = 0.0f;
		for (const FOneFrameParityBody& BodyTarget : Bodies)
		{
			if (FBodyInstance* Body = Mesh->GetBodyInstance(BodyTarget.BoneName))
			{
				Body->SetEnableGravity(false);
				Body->SetBodyTransform(BodyTarget.KinematicWorldTransform, ETeleportType::TeleportPhysics, false);
				Body->SetLinearVelocity(FVector::ZeroVector, false, false);
				Body->SetAngularVelocityInRadians(FVector::ZeroVector, false, false);
				Body->ClearForces(false);
				Body->ClearTorques(false);
				const FTransform Actual = Body->GetUnrealWorldTransform();
				InitialMaxPositionErrorCm = FMath::Max(InitialMaxPositionErrorCm,
					FVector::Distance(BodyTarget.KinematicWorldTransform.GetLocation(), Actual.GetLocation()));
				InitialMaxRotationErrorDegrees = FMath::Max(InitialMaxRotationErrorDegrees,
					FMath::RadiansToDegrees(BodyTarget.KinematicWorldTransform.GetRotation().AngularDistance(
						Actual.GetRotation())));
			}
		}
		FString InitialJointAnchors;
		float InitialMaximumJointAnchorErrorCm = 0.0f;
		for (FConstraintInstance* Constraint : Mesh->Constraints)
		{
			if (!Constraint)
			{
				continue;
			}
			FBodyInstance* ChildBody = Mesh->GetBodyInstance(Constraint->ConstraintBone1);
			FBodyInstance* ParentBody = Mesh->GetBodyInstance(Constraint->ConstraintBone2);
			if (!ChildBody || !ParentBody)
			{
				continue;
			}
			const FVector ChildAnchor = (Constraint->GetRefFrame(EConstraintFrame::Frame1) *
				ChildBody->GetUnrealWorldTransform()).GetLocation();
			const FVector ParentAnchor = (Constraint->GetRefFrame(EConstraintFrame::Frame2) *
				ParentBody->GetUnrealWorldTransform()).GetLocation();
			const float AnchorErrorCm = FVector::Distance(ChildAnchor, ParentAnchor);
			InitialMaximumJointAnchorErrorCm = FMath::Max(InitialMaximumJointAnchorErrorCm, AnchorErrorCm);
			if (Constraint->ConstraintBone1 == TEXT("thigh_l") || Constraint->ConstraintBone1 == TEXT("calf_l") ||
				Constraint->ConstraintBone1 == TEXT("foot_l") || Constraint->ConstraintBone1 == TEXT("thigh_r") ||
				Constraint->ConstraintBone1 == TEXT("calf_r") || Constraint->ConstraintBone1 == TEXT("foot_r"))
			{
				InitialJointAnchors += FString::Printf(TEXT(" %s=%.4fcm"),
					*Constraint->ConstraintBone1.ToString(), AnchorErrorCm);
			}
		}
		Mesh->WakeAllRigidBodies();
		const uint64 StartFrame = GFrameCounter;
		UE_LOG(LogProphecyAgentPhysical, Display,
			TEXT("ONE_FRAME_PARITY initialized bodies=%d max_cm=%.6f max_deg=%.6f max_anchor_cm=%.6f frame=%llu%s"),
			Bodies.Num(), InitialMaxPositionErrorCm, InitialMaxRotationErrorDegrees,
			InitialMaximumJointAnchorErrorCm, StartFrame, *InitialJointAnchors);

		TWeakObjectPtr<AProphecyAgent> WeakAgent = Agent;
		World->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateLambda(
			[WeakAgent, Bodies = MoveTemp(Bodies), PreviousDynamicBodyFilterHacks, StartFrame]()
			{
				AProphecyAgent* TestAgent = WeakAgent.Get();
				if (!TestAgent || !TestAgent->GetWorld())
				{
					return;
				}
				USkeletalMeshComponent* TestMesh = TestAgent->GetAgentMesh();
				float MaxPositionErrorCm = 0.0f;
				float MaxRotationErrorDegrees = 0.0f;
				FString Errors;
				FString PelvisMotion;
				for (const FOneFrameParityBody& BodyTarget : Bodies)
				{
					if (FBodyInstance* Body = TestMesh->GetBodyInstance(BodyTarget.BoneName))
					{
						const FTransform Actual = Body->GetUnrealWorldTransform();
						const float PositionErrorCm = FVector::Distance(
							BodyTarget.KinematicWorldTransform.GetLocation(), Actual.GetLocation());
						const float RotationErrorDegrees = FMath::RadiansToDegrees(
							BodyTarget.KinematicWorldTransform.GetRotation().AngularDistance(Actual.GetRotation()));
						MaxPositionErrorCm = FMath::Max(MaxPositionErrorCm, PositionErrorCm);
						MaxRotationErrorDegrees = FMath::Max(MaxRotationErrorDegrees, RotationErrorDegrees);
						Errors += FString::Printf(TEXT(" %s=%.4fcm/%.3fdeg"),
							*BodyTarget.BoneName.ToString(), PositionErrorCm, RotationErrorDegrees);
						if (BodyTarget.BoneName == TEXT("pelvis"))
						{
							const FVector Delta = Actual.GetLocation() - BodyTarget.KinematicWorldTransform.GetLocation();
							PelvisMotion = FString::Printf(TEXT(" pelvis_delta=(%.6f,%.6f,%.6f)cm pelvis_v=(%.6f,%.6f,%.6f)cm/s"),
								Delta.X, Delta.Y, Delta.Z,
								Body->GetUnrealWorldVelocity().X, Body->GetUnrealWorldVelocity().Y,
								Body->GetUnrealWorldVelocity().Z);
						}
					}
				}
				UE_LOG(LogProphecyAgentPhysical, Display,
					TEXT("ONE_FRAME_PARITY result frames=%llu max_cm=%.6f max_deg=%.6f%s%s"),
					GFrameCounter - StartFrame, MaxPositionErrorCm, MaxRotationErrorDegrees, *PelvisMotion, *Errors);
				for (FBodyInstance* Body : TestMesh->Bodies)
				{
					if (Body)
					{
						Body->bHACK_DisableCollisionResponse = false;
						Body->UpdatePhysicsFilterData();
					}
				}
				if (IConsoleVariable* DynamicBodyFilterHacks = IConsoleManager::Get().FindConsoleVariable(
					TEXT("p.EnableDynamicPerBodyFilterHacks")))
				{
					DynamicBodyFilterHacks->Set(PreviousDynamicBodyFilterHacks, ECVF_SetByCode);
				}
				TestAgent->GetWorld()->bDebugPauseExecution = true;
			}));
	}

	FAutoConsoleCommandWithWorld GRunOneFramePhysicalParity(
		TEXT("prophecy.Physical.OneFrameParity"),
		TEXT("Copy one exact kinematic pose into Chaos, advance one frame, and report every body error."),
		FConsoleCommandWithWorldDelegate::CreateStatic(&RunOneFramePhysicalParity));
	TAutoConsoleVariable<int32> CVarOneFrameAngularLimits(
		TEXT("prophecy.Physical.OneFrameAngularLimits"),
		1,
		TEXT("One-frame angular limits: 0=free all, 1=production, 2=free left knee, 3=wide all, 4=wide legs, 5=free legs."));
	// These object channels are declared by name in DefaultEngine.ini.
	constexpr ECollisionChannel ProphecyAgentCapsuleChannel = ECC_GameTraceChannel8;
	constexpr ECollisionChannel ProphecyAgentLimbChannel = ECC_GameTraceChannel9;
	// Joint drives are constraint-space accelerations. Keep them near critical
	// damping; the former 10x/3.33x multipliers injected enough angular energy to
	// spin the pelvis and throw the feet tens of centimetres off target.
	TAutoConsoleVariable<float> CVarProphecyPhysicalJointSpring(
		TEXT("prophecy.Physical.JointSpring"),
		250000.0f,
		TEXT("Acceleration-drive stiffness for the temporary pelvis-and-legs physical controller."));
	TAutoConsoleVariable<float> CVarProphecyPhysicalJointDamping(
		TEXT("prophecy.Physical.JointDamping"),
		1000.0f,
		TEXT("Acceleration-drive damping for the temporary pelvis-and-legs physical controller."));
	constexpr int32 PhysicalPositionSolverIterations = 4;
	constexpr int32 PhysicalVelocitySolverIterations = 1;
	constexpr int32 PhysicalProjectionSolverIterations = 0;

	bool IsTemporarySimulatedLowerBody(FName BoneName)
	{
		return BoneName == TEXT("pelvis") ||
			BoneName == TEXT("thigh_l") || BoneName == TEXT("calf_l") ||
			BoneName == TEXT("foot_l") || BoneName == TEXT("ball_l") ||
			BoneName == TEXT("thigh_r") || BoneName == TEXT("calf_r") ||
			BoneName == TEXT("foot_r") || BoneName == TEXT("ball_r");
	}

	FQuat BlendAuthoredRotation(const FQuat& A, const FQuat& B, float Alpha)
	{
		FQuat Start = A.GetNormalized();
		FQuat End = B.GetNormalized();
		float CosHalfAngle = Start | End;
		if (CosHalfAngle < 0.0f)
		{
			End = End * -1.0f;
			CosHalfAngle = -CosHalfAngle;
		}
		CosHalfAngle = FMath::Clamp(CosHalfAngle, 0.0f, 1.0f);
		const float Angle = 2.0f * FMath::Acos(CosHalfAngle);
		if (Angle <= 1.0e-6f)
		{
			return Start;
		}

		// Match the Stepper viewer / kinematic proxy's matrix-lerp polar factor.
		const float WeightedAngle = FMath::Atan2(
			Alpha * FMath::Sin(Angle),
			(1.0f - Alpha) + Alpha * FMath::Cos(Angle));
		FQuat Result = FQuat::Slerp(Start, End, WeightedAngle / Angle);
		Result.Normalize();
		return Result;
	}

	FTransform BlendAuthoredWorldTransform(const FTransform& A, const FTransform& B, float Alpha)
	{
		return FTransform(
			BlendAuthoredRotation(A.GetRotation(), B.GetRotation(), Alpha),
			FMath::Lerp(A.GetLocation(), B.GetLocation(), Alpha),
			FVector::OneVector);
	}

	bool IsIgnoredNavigationBlocker(const AActor* Actor)
	{
		if (!Actor)
		{
			return false;
		}

		const FString ClassName = Actor->GetClass()->GetName();
		if (ClassName.StartsWith(TEXT("BP_Door")) ||
			ClassName.StartsWith(TEXT("BP_LogCabins_Shutter")) ||
			ClassName.StartsWith(TEXT("BP_StickHolder")))
		{
			return true;
		}

		const AStaticMeshActor* StaticMeshActor = Cast<AStaticMeshActor>(Actor);
		const UStaticMeshComponent* StaticMeshComponent = StaticMeshActor
			? StaticMeshActor->GetStaticMeshComponent()
			: nullptr;
		const UStaticMesh* StaticMesh = StaticMeshComponent
			? StaticMeshComponent->GetStaticMesh()
			: nullptr;
		if (!StaticMesh)
		{
			return false;
		}

		const FString MeshName = StaticMesh->GetName();
		return MeshName.StartsWith(TEXT("SM_Bench")) || MeshName.StartsWith(TEXT("SM_Barrel"));
	}
}

AProphecyAgent::AProphecyAgent()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	PrimaryActorTick.EndTickGroup = TG_PrePhysics;
	AutoPossessAI = EAutoPossessAI::Disabled;
	AutoPossessPlayer = EAutoReceiveInput::Disabled;

	Capsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Capsule"));
	Capsule->InitCapsuleSize(30.0f, 86.0f);
	Capsule->SetCollisionObjectType(ProphecyAgentCapsuleChannel);
	Capsule->SetGenerateOverlapEvents(false);
	Capsule->SetCanEverAffectNavigation(false);
	SetRootComponent(Capsule);

	Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Capsule);
	Mesh->SetRelativeLocation(FVector(0.0, 0.0, -86.0));
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetCanEverAffectNavigation(false);
	Mesh->SetNotifyRigidBodyCollision(false);
	Mesh->OnComponentHit.AddDynamic(this, &AProphecyAgent::HandleMeshHit);
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> DefaultMesh(
		TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	if (DefaultMesh.Succeeded())
	{
		Mesh->SetSkeletalMesh(DefaultMesh.Object);
	}

	PhysicalAnimation = CreateDefaultSubobject<UPhysicalAnimationComponent>(TEXT("PhysicalAnimation"));
	PhysicalAnimation->SetComponentTickEnabled(false);

	PhysicalDriveSettings.bIsLocalSimulation = false;
	// The pelvis is the external rotational anchor for every articulated joint.
	// Match the joint drive scale so their reaction torque cannot spin the root.
	PhysicalDriveSettings.OrientationStrength = 60000.0f;
	PhysicalDriveSettings.AngularVelocityStrength = 500.0f;
	PhysicalDriveSettings.PositionStrength = 40000.0f;
	PhysicalDriveSettings.VelocityStrength = 400.0f;
	PhysicalDriveSettings.MaxLinearForce = 0.0f;
	PhysicalDriveSettings.MaxAngularForce = 0.0f;

	ApplyCollisionMode(EProphecyAgentSimulationMode::Kinematic);
}

void AProphecyAgent::BeginPlay()
{
	Super::BeginPlay();
	// Editor/gameplay volumes describe regions; they are not physical walls.
	// The project's custom capsule channel defaults to Block, so explicitly
	// exclude every AVolume from swept agent movement.
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		if (It->IsA<AVolume>() || IsIgnoredNavigationBlocker(*It))
		{
			Capsule->IgnoreActorWhenMoving(*It, true);
		}
	}
	PhysicalAnimation->SetSkeletalMeshComponent(Mesh);
	PhysicalAnimation->SetStrengthMultiplyer(0.0f);
	PhysicalAnimation->SetComponentTickEnabled(false);
	AddTickPrerequisiteComponent(Mesh);
	ApplyCollisionMode(SimulationMode);

	// A manually placed pose agent with Auto Possess enabled is a complete
	// single-agent test by itself. Create the same runtime used by the locomotion
	// test map and register this placed pawn as lane zero instead of spawning a
	// second shell.
	if (GetWorld() && AutoPossessPlayer != EAutoReceiveInput::Disabled)
	{
		AProphecyNNLocomotionManager* Manager = nullptr;
		for (TActorIterator<AProphecyNNLocomotionManager> It(GetWorld()); It; ++It)
		{
			Manager = *It;
			break;
		}
		if (!Manager)
		{
			Manager = GetWorld()->SpawnActorDeferred<AProphecyNNLocomotionManager>(
				AProphecyNNLocomotionManager::StaticClass(),
				FTransform::Identity,
				nullptr,
				nullptr,
				ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
			if (Manager)
			{
				Manager->PlayerAgent = this;
				Manager->ConfigureSimpleLocomotionTest();
				Manager->FinishSpawning(FTransform::Identity);
			}
		}
	}
}

void AProphecyAgent::Tick(float DeltaSeconds)
{
	const bool bAuditManualFollower =
		CVarProphecyAuditManualPhysicalFollower.GetValueOnGameThread() != 0;
	if (bAuditManualFollower)
	{
		// This is deliberately before Super: Blueprint ReceiveTick has not authored
		// a new target yet, so the comparison closes the preceding Chaos step.
		AuditManualPhysicalFollowerBeforeTick(this);
	}

	Super::Tick(DeltaSeconds);

	if (bAuditManualFollower)
	{
		// ReceiveTick has now evaluated the NN endpoint and applied this step's
		// velocity correction. Save the exact endpoint for next PrePhysics tick.
		CaptureManualPhysicalFollowerEndpointAfterTick(this, DeltaSeconds);
	}
	if (SimulationMode == EProphecyAgentSimulationMode::Physical &&
		PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
	{
		static bool bLoggedPhysicalDriveTick = false;
		if (!bLoggedPhysicalDriveTick && CVarProphecyPhysicalLogPelvisError.GetValueOnGameThread() != 0)
		{
			bLoggedPhysicalDriveTick = true;
			UE_LOG(LogProphecyAgentPhysical, Display, TEXT("PHYSICAL_DRIVE_TICK dt=%.6f"), DeltaSeconds);
		}
		ApplyAbsoluteWorldMagnetization(DeltaSeconds);
	}
}

bool AProphecyAgent::ReadNNFutureWorldPose(
	TArray<FName>& BoneNames,
	TArray<FTransform>& FutureWorldTransforms,
	TArray<FTransform>& InterpolatedWorldTransforms,
	float& InterpolationAlpha) const
{
	BoneNames.Reset();
	FutureWorldTransforms.Reset();
	InterpolatedWorldTransforms.Reset();
	InterpolationAlpha = 1.0f;

	const UProphecyNNLocomotionAnimInstance* AnimInstance =
		Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());
	FProphecyNNPoseSnapshot Pose;
	if (!AnimInstance || !FProphecyNNPoseStore::GetAgentLocalPose(AnimInstance->AgentId, Pose) ||
		!Pose.bHasComponentWorldTransform ||
		Pose.PreviousComponentTransforms.Num() != Pose.BoneNames.Num() ||
		Pose.ComponentTransforms.Num() != Pose.BoneNames.Num())
	{
		return false;
	}

	const float PoseInterval = FMath::Max(0.001f, AnimInstance->NNPoseIntervalSeconds);
	const float FrameDeltaSeconds = GetWorld() ? GetWorld()->GetDeltaSeconds() : PoseInterval;
	if (AnimInstance->bInterpolateNNPose && FrameDeltaSeconds < PoseInterval && GetWorld())
	{
		InterpolationAlpha = FMath::Clamp(
			float((double(GetWorld()->GetTimeSeconds()) - Pose.SourceTimeSeconds) / double(PoseInterval)),
			0.0f,
			1.0f);
	}

	BoneNames = Pose.BoneNames;
	FutureWorldTransforms.SetNumUninitialized(Pose.BoneNames.Num());
	InterpolatedWorldTransforms.SetNumUninitialized(Pose.BoneNames.Num());
	for (int32 Index = 0; Index < Pose.BoneNames.Num(); ++Index)
	{
		const FTransform PreviousWorld = Pose.PreviousComponentTransforms[Index] *
			Pose.PreviousComponentWorldTransform;
		const FTransform FutureWorld = Pose.ComponentTransforms[Index] *
			Pose.ComponentWorldTransform;
		FutureWorldTransforms[Index] = FutureWorld;
		InterpolatedWorldTransforms[Index] = BlendAuthoredWorldTransform(
			PreviousWorld, FutureWorld, InterpolationAlpha);
	}
	return true;
}

bool AProphecyAgent::ApplyNNPoseKinematically(float DeltaSeconds)
{
	if (!Mesh->GetSkeletalMeshAsset() ||
		!Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance()))
	{
		return false;
	}

	Mesh->TickAnimation(FMath::Max(0.0f, DeltaSeconds), false);
	Mesh->RefreshBoneTransforms();
	return true;
}

bool AProphecyAgent::SetSimulationMode(EProphecyAgentSimulationMode NewMode)
{
	if (NewMode == SimulationMode)
	{
		return true;
	}

	if (NewMode == EProphecyAgentSimulationMode::Physical)
	{
		UPhysicsAsset* PhysicsAsset = Mesh->GetPhysicsAsset();
		if (!Mesh->GetSkeletalMeshAsset() || !PhysicsAsset || PhysicsAsset->FindBodyIndex(PhysicalRootBodyName) == INDEX_NONE)
		{
			return false;
		}

		if (PhysicalAnimation->GetSkeletalMesh() != Mesh)
		{
			PhysicalAnimation->SetSkeletalMeshComponent(Mesh);
		}

		// Kinematic presentation may scale the calf so its rendered segment reaches
		// the predicted foot endpoint. Chaos must never be initialized from that
		// presentation-only scale. Let the anim proxy publish one unscaled Physical
		// pose before the skeletal bodies start simulating.
		SimulationMode = EProphecyAgentSimulationMode::Physical;
		Mesh->TickAnimation(0.0f, false);
		Mesh->RefreshBoneTransforms();
		PhysicalTargetComponentRelativeTransform = Mesh->GetRelativeTransform();
		bHasPreviousPhysicalRootTarget = false;
		bSavedUpdateRateOptimizations = Mesh->bEnableUpdateRateOptimizations;
		SavedVisibilityBasedAnimTickOption = Mesh->VisibilityBasedAnimTickOption;
		Mesh->bEnableUpdateRateOptimizations = false;
		Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;

		// Named body iteration requires a created physics state in UE 5.7.
		ApplyCollisionMode(EProphecyAgentSimulationMode::Physical);
		Mesh->SetNotifyRigidBodyCollision(bGeneratePhysicalHitEvents);
		SetMACDEnabled(bMACDEnabled);

		if (!bPhysicalDriveConfigured)
		{
			if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::PerBodyWorld)
			{
				PhysicalAnimation->ApplyPhysicalAnimationSettingsBelow(
					PhysicalRootBodyName,
					PhysicalDriveSettings,
					true);
			}
			bPhysicalDriveConfigured = true;
		}

		Mesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, true, true);
		Mesh->SetAllBodiesBelowPhysicsBlendWeight(PhysicalRootBodyName, 1.0f, false, true);
		if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
		{
			// Until upper-body targets are authored, keep those bones animation-driven
			// and remove their constraints from this temporary controller. Otherwise
			// their uncontrolled rigid bodies inject torque into the driven pelvis.
			for (const USkeletalBodySetup* BodySetup : PhysicsAsset->SkeletalBodySetups)
			{
				if (!BodySetup || IsTemporarySimulatedLowerBody(BodySetup->BoneName))
				{
					continue;
				}
				Mesh->SetBodySimulatePhysics(BodySetup->BoneName, false);
				if (FBodyInstance* Body = Mesh->GetBodyInstance(BodySetup->BoneName))
				{
					Body->PhysicsBlendWeight = 0.0f;
				}
			}
			for (FBodyInstance* Body : Mesh->Bodies)
			{
				if (!Body || !Body->IsValidBodyInstance())
				{
					continue;
				}
				FPhysicsCommand::ExecuteWrite(Body->GetPhysicsActor(), [](const FPhysicsActorHandle& Actor)
				{
					FChaosEngineInterface::SetPositionSolverIterationCount_AssumesLocked(
						Actor, PhysicalPositionSolverIterations);
					FChaosEngineInterface::SetVelocitySolverIterationCount_AssumesLocked(
						Actor, PhysicalVelocitySolverIterations);
					FChaosEngineInterface::SetProjectionSolverIterationCount_AssumesLocked(
						Actor, PhysicalProjectionSolverIterations);
				});
			}
			for (FConstraintInstance* Constraint : Mesh->Constraints)
			{
				if (Constraint)
				{
					const FName ChildBone = Constraint->ConstraintBone1;
					const bool bLegConstraint = IsTemporarySimulatedLowerBody(ChildBone) &&
						ChildBone != PhysicalRootBodyName;
					if (!bLegConstraint)
					{
						Constraint->TermConstraint();
						continue;
					}
					// The NN was authored across this whole articulation range. The
					// stock mannequin's narrow leg limits project valid walk poses.
					Constraint->SetAngularSwing1Limit(ACM_Limited, 179.0f);
					Constraint->SetAngularSwing2Limit(ACM_Limited, 179.0f);
					Constraint->SetAngularTwistLimit(ACM_Limited, 179.0f);
					Constraint->EnableMassConditioning();
					Constraint->SetOrientationDriveSLERP(false);
					Constraint->SetAngularVelocityDriveSLERP(false);
				}
			}
			Mesh->SetAllMotorsAngularPositionDrive(false, false, false);
			Mesh->SetAllMotorsAngularVelocityDrive(false, false, false);
			// The retained Physics Asset constraints transmit impacts and preserve
			// articulation. They do not track animation: the PrePhysics agent tick
			// magnetizes every simulated body to its authored absolute world pose.
			Mesh->bUpdateJointsFromAnimation = false;
		}
		else
		{
			Mesh->bUpdateJointsFromAnimation = false;
		}
		PhysicalAnimation->SetStrengthMultiplyer(
			PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::PerBodyWorld
				? PhysicalDriveStrengthMultiplier
				: 0.0f);
		PhysicalAnimation->SetComponentTickEnabled(
			PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::PerBodyWorld);
		Mesh->WakeAllRigidBodies();
		SimulationMode = NewMode;
		const bool bUsesRootAndJointTorque =
			PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque;
		SetActorTickEnabled(bUsesRootAndJointTorque);
		if (bUsesRootAndJointTorque)
		{
			ApplyAbsoluteWorldMagnetization(
				GetWorld() ? FMath::Max(GetWorld()->GetDeltaSeconds(), 1.0f / 60.0f) : 1.0f / 60.0f);
		}
		return true;
	}

	SetActorTickEnabled(false);
	PhysicalAnimation->SetStrengthMultiplyer(0.0f);
	if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
	{
		Mesh->bUpdateJointsFromAnimation = false;
		for (FConstraintInstance* Constraint : Mesh->Constraints)
		{
			if (Constraint)
			{
				Constraint->SetOrientationDriveSLERP(false);
				Constraint->SetAngularVelocityDriveSLERP(false);
			}
		}
	}
	Mesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, false, true);
	Mesh->SetAllBodiesBelowPhysicsBlendWeight(PhysicalRootBodyName, 0.0f, false, true);
	Mesh->SetRelativeTransform(
		PhysicalTargetComponentRelativeTransform,
		false,
		nullptr,
		ETeleportType::TeleportPhysics);
	Mesh->TickAnimation(0.0f, false);
	Mesh->RefreshBoneTransforms();
	Mesh->SetNotifyRigidBodyCollision(false);
	ApplyCollisionMode(EProphecyAgentSimulationMode::Kinematic);
	PhysicalAnimation->SetComponentTickEnabled(false);
	Mesh->bEnableUpdateRateOptimizations = bSavedUpdateRateOptimizations;
	Mesh->VisibilityBasedAnimTickOption = SavedVisibilityBasedAnimTickOption;
	bHasPreviousPhysicalRootTarget = false;
	SimulationMode = NewMode;
	return true;
}

void AProphecyAgent::ApplyAbsoluteWorldMagnetization(float DeltaSeconds)
{
	if (DeltaSeconds <= UE_SMALL_NUMBER || !Mesh->GetSkeletalMeshAsset())
	{
		return;
	}

	FBodyInstance* PelvisBody = Mesh->GetBodyInstance(PhysicalRootBodyName);
	const UProphecyNNLocomotionAnimInstance* AnimInstance =
		Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());
	FProphecyNNPoseSnapshot AuthoredPose;
	if (!PelvisBody || !PelvisBody->IsInstanceSimulatingPhysics() || !AnimInstance ||
		!FProphecyNNPoseStore::GetAgentLocalPose(AnimInstance->AgentId, AuthoredPose) ||
		!AuthoredPose.bHasComponentWorldTransform)
	{
		UE_CLOG(CVarProphecyPhysicalLogPelvisError.GetValueOnGameThread() != 0,
			LogProphecyAgentPhysical, Warning,
			TEXT("PHYSICAL_DRIVE_MISSING pelvis=%d sim=%d anim=%d pose=%d world=%d agent_id=%d"),
			PelvisBody ? 1 : 0,
			PelvisBody && PelvisBody->IsInstanceSimulatingPhysics() ? 1 : 0,
			AnimInstance ? 1 : 0,
			AnimInstance && FProphecyNNPoseStore::GetAgentLocalPose(AnimInstance->AgentId, AuthoredPose) ? 1 : 0,
			AuthoredPose.bHasComponentWorldTransform ? 1 : 0,
			AnimInstance ? AnimInstance->AgentId : INDEX_NONE);
		return;
	}

	const int32 PelvisPoseIndex = AuthoredPose.BoneNames.IndexOfByKey(PhysicalRootBodyName);
	if (!AuthoredPose.ComponentTransforms.IsValidIndex(PelvisPoseIndex) ||
		!AuthoredPose.PreviousComponentTransforms.IsValidIndex(PelvisPoseIndex))
	{
		UE_CLOG(CVarProphecyPhysicalLogPelvisError.GetValueOnGameThread() != 0,
			LogProphecyAgentPhysical, Warning,
			TEXT("PHYSICAL_DRIVE_INVALID_POSE pelvis_index=%d current=%d previous=%d"),
			PelvisPoseIndex, AuthoredPose.ComponentTransforms.Num(),
			AuthoredPose.PreviousComponentTransforms.Num());
		return;
	}

	// The pose store owns the authored world target. The skeletal component's
	// transform belongs to the ragdoll once simulation starts and must never be
	// used to rebuild this target.
	const FTransform PreviousTarget = AuthoredPose.PreviousComponentTransforms[PelvisPoseIndex] *
		AuthoredPose.PreviousComponentWorldTransform;
	const FTransform CurrentTarget = AuthoredPose.ComponentTransforms[PelvisPoseIndex] *
		AuthoredPose.ComponentWorldTransform;
	const float PoseInterval = FMath::Max(0.001f, AnimInstance->NNPoseIntervalSeconds);
	const float PoseAlpha = AnimInstance->bInterpolateNNPose && DeltaSeconds < PoseInterval && GetWorld()
		? FMath::Clamp(float((double(GetWorld()->GetTimeSeconds()) - AuthoredPose.SourceTimeSeconds) /
			double(PoseInterval)), 0.0f, 1.0f)
		: 1.0f;

	float MaximumPositionErrorCm = 0.0f;
	float MaximumRotationErrorDegrees = 0.0f;
	FName MaximumPositionErrorBone = NAME_None;
	FName MaximumRotationErrorBone = NAME_None;
	float PositionErrorSumCm = 0.0f;
	float RotationErrorSumDegrees = 0.0f;
	int32 DrivenBodyCount = 0;
	for (FBodyInstance* Body : Mesh->Bodies)
	{
		const UBodySetupCore* BodySetup = Body ? Body->BodySetup.Get() : nullptr;
		if (!Body || !Body->IsInstanceSimulatingPhysics() || !BodySetup ||
			!IsTemporarySimulatedLowerBody(BodySetup->BoneName))
		{
			continue;
		}

		const int32 PoseIndex = AuthoredPose.BoneNames.IndexOfByKey(BodySetup->BoneName);
		if (!AuthoredPose.PreviousComponentTransforms.IsValidIndex(PoseIndex) ||
			!AuthoredPose.ComponentTransforms.IsValidIndex(PoseIndex))
		{
			continue;
		}

		const FTransform PreviousBodyTarget = AuthoredPose.PreviousComponentTransforms[PoseIndex] *
			AuthoredPose.PreviousComponentWorldTransform;
		const FTransform CurrentBodyTarget = AuthoredPose.ComponentTransforms[PoseIndex] *
			AuthoredPose.ComponentWorldTransform;
		const FTransform BodyTarget = BlendAuthoredWorldTransform(
			PreviousBodyTarget, CurrentBodyTarget, PoseAlpha);
		const FTransform ActualBody = Body->GetUnrealWorldTransform();

		FVector LinearAcceleration =
			(BodyTarget.GetLocation() - ActualBody.GetLocation() -
				Body->GetUnrealWorldVelocity() * DeltaSeconds) /
			FMath::Square(DeltaSeconds);
		if (GetWorld())
		{
			LinearAcceleration.Z -= GetWorld()->GetGravityZ();
		}
		Body->AddForce(LinearAcceleration, true, true);

		FQuat RotationError = BodyTarget.GetRotation() * ActualBody.GetRotation().Inverse();
		RotationError.Normalize();
		if (RotationError.W < 0.0f)
		{
			RotationError = RotationError * -1.0f;
		}
		FVector ErrorAxis = FVector::ForwardVector;
		float ErrorAngle = 0.0f;
		RotationError.ToAxisAndAngle(ErrorAxis, ErrorAngle);
		const FVector DesiredAngularVelocity = ErrorAxis * (ErrorAngle / DeltaSeconds);
		const FVector AngularAcceleration =
			(DesiredAngularVelocity - Body->GetUnrealWorldAngularVelocityInRadians()) /
			DeltaSeconds;
		Body->AddTorqueInRadians(AngularAcceleration, true, true);

		const float PositionErrorCm =
			FVector::Distance(BodyTarget.GetLocation(), ActualBody.GetLocation());
		const float RotationErrorDegrees = FMath::RadiansToDegrees(
			BodyTarget.GetRotation().AngularDistance(ActualBody.GetRotation()));
		PositionErrorSumCm += PositionErrorCm;
		RotationErrorSumDegrees += RotationErrorDegrees;
		if (PositionErrorCm > MaximumPositionErrorCm)
		{
			MaximumPositionErrorCm = PositionErrorCm;
			MaximumPositionErrorBone = BodySetup->BoneName;
		}
		if (RotationErrorDegrees > MaximumRotationErrorDegrees)
		{
			MaximumRotationErrorDegrees = RotationErrorDegrees;
			MaximumRotationErrorBone = BodySetup->BoneName;
		}
		++DrivenBodyCount;
	}

	if ((CVarProphecyPhysicalLogTrackingError.GetValueOnGameThread() != 0 ||
		CVarProphecyPhysicalLogPelvisError.GetValueOnGameThread() != 0) && GetWorld())
	{
		static double LastWorldMagnetLogSeconds = -DBL_MAX;
		const double NowSeconds = GetWorld()->GetTimeSeconds();
		if (NowSeconds < LastWorldMagnetLogSeconds ||
			NowSeconds - LastWorldMagnetLogSeconds >= 0.5)
		{
			LastWorldMagnetLogSeconds = NowSeconds;
			UE_LOG(LogProphecyAgentPhysical, Display,
				TEXT("WORLD_MAGNET_TRACKING bodies=%d mean_cm=%.4f max_cm=%.4f max_pos_bone=%s mean_deg=%.4f max_deg=%.4f max_rot_bone=%s"),
				DrivenBodyCount,
				DrivenBodyCount > 0 ? PositionErrorSumCm / float(DrivenBodyCount) : 0.0f,
				MaximumPositionErrorCm, *MaximumPositionErrorBone.ToString(),
				DrivenBodyCount > 0 ? RotationErrorSumDegrees / float(DrivenBodyCount) : 0.0f,
				MaximumRotationErrorDegrees, *MaximumRotationErrorBone.ToString());
		}
	}

	PreviousPhysicalRootTarget = BlendAuthoredWorldTransform(
		PreviousTarget, CurrentTarget, PoseAlpha);
	bHasPreviousPhysicalRootTarget = true;
	return;

#if 0
	// Drive every Physics Asset joint from the authored target, never from the
	// post-physics skeletal buffer. The lower body uses the exact consecutive
	// component-space frames and interpolation used by the kinematic renderer;
	// the current no-overlay upper body uses its reference local pose.
	if (const UPhysicsAsset* PhysicsAsset = Mesh->GetPhysicsAsset();
		PhysicsAsset && PhysicsAsset->ConstraintSetup.Num() == Mesh->Constraints.Num())
	{
		const FReferenceSkeleton& ReferenceSkeleton = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
		for (int32 ConstraintIndex = 0; ConstraintIndex < Mesh->Constraints.Num(); ++ConstraintIndex)
		{
			const UPhysicsConstraintTemplate* Template = PhysicsAsset->ConstraintSetup[ConstraintIndex];
			FConstraintInstance* Constraint = Mesh->Constraints[ConstraintIndex];
			if (!Template || !Constraint ||
				!IsTemporarySimulatedLowerBody(Template->DefaultInstance.GetChildBoneName()) ||
				!Constraint->IsAngularOrientationDriveEnabled())
			{
				continue;
			}

			const FName ChildBone = Template->DefaultInstance.GetChildBoneName();
			const FName ParentBody = Template->DefaultInstance.ConstraintBone2;
			const int32 ChildBoneIndex = ReferenceSkeleton.FindBoneIndex(ChildBone);
			if (ChildBoneIndex == INDEX_NONE || ChildBoneIndex == 0)
			{
				continue;
			}

			FQuat PreviousLocalRotation = ReferenceSkeleton.GetRefBonePose()[ChildBoneIndex].GetRotation();
			FQuat CurrentLocalRotation = PreviousLocalRotation;
			const int32 ChildPoseIndex = AuthoredPose.BoneNames.IndexOfByKey(ChildBone);
			const int32 ParentPoseIndex = AuthoredPose.BoneNames.IndexOfByKey(ParentBody);
			if (AuthoredPose.PreviousComponentTransforms.IsValidIndex(ChildPoseIndex) &&
				AuthoredPose.ComponentTransforms.IsValidIndex(ChildPoseIndex) &&
				AuthoredPose.PreviousComponentTransforms.IsValidIndex(ParentPoseIndex) &&
				AuthoredPose.ComponentTransforms.IsValidIndex(ParentPoseIndex))
			{
				const FTransform PreviousChildWorld = AuthoredPose.PreviousComponentTransforms[ChildPoseIndex] *
					AuthoredPose.PreviousComponentWorldTransform;
				const FTransform CurrentChildWorld = AuthoredPose.ComponentTransforms[ChildPoseIndex] *
					AuthoredPose.ComponentWorldTransform;
				const FTransform PreviousParentWorld = AuthoredPose.PreviousComponentTransforms[ParentPoseIndex] *
					AuthoredPose.PreviousComponentWorldTransform;
				const FTransform CurrentParentWorld = AuthoredPose.ComponentTransforms[ParentPoseIndex] *
					AuthoredPose.ComponentWorldTransform;
				const FTransform ChildTarget = BlendAuthoredWorldTransform(
					PreviousChildWorld, CurrentChildWorld, PoseAlpha);
				const FTransform ParentTarget = BlendAuthoredWorldTransform(
					PreviousParentWorld, CurrentParentWorld, PoseAlpha);
				PreviousLocalRotation = PreviousChildWorld.GetRelativeTransform(
					PreviousParentWorld).GetRotation();
				CurrentLocalRotation = CurrentChildWorld.GetRelativeTransform(
					CurrentParentWorld).GetRotation();
			}

			FMatrix ControlBodyToParentBone = FMatrix::Identity;
			int32 TestBoneIndex = ReferenceSkeleton.GetParentIndex(ChildBoneIndex);
			bool bFoundControlBody = ReferenceSkeleton.GetBoneName(TestBoneIndex) == ParentBody;
			while (!bFoundControlBody && TestBoneIndex > 0)
			{
				FMatrix RelativeMatrix = ReferenceSkeleton.GetRefBonePose()[TestBoneIndex].ToMatrixNoScale();
				RelativeMatrix.SetOrigin(FVector::ZeroVector);
				ControlBodyToParentBone = ControlBodyToParentBone * RelativeMatrix;
				TestBoneIndex = ReferenceSkeleton.GetParentIndex(TestBoneIndex);
				bFoundControlBody = ReferenceSkeleton.GetBoneName(TestBoneIndex) == ParentBody;
			}
			if (!bFoundControlBody)
			{
				continue;
			}

			FMatrix ChildBodyToJoint = Template->DefaultInstance.GetRefFrame(
				EConstraintFrame::Frame1).ToMatrixNoScale();
			ChildBodyToJoint.SetOrigin(FVector::ZeroVector);
			FMatrix ParentBodyToJoint = Template->DefaultInstance.GetRefFrame(
				EConstraintFrame::Frame2).ToMatrixNoScale();
			ParentBodyToJoint.SetOrigin(FVector::ZeroVector);
			auto BuildJointTarget = [&](const FQuat& LocalRotation)
			{
				FQuatRotationTranslationMatrix LocalRotationMatrix(LocalRotation, FVector::ZeroVector);
				const FMatrix JointRotation = ChildBodyToJoint *
					(LocalRotationMatrix * ControlBodyToParentBone) * ParentBodyToJoint.InverseFast();
				return FQuat(JointRotation).GetNormalized();
			};
			const FQuat PreviousJointTarget = BuildJointTarget(PreviousLocalRotation);
			const FQuat CurrentJointTarget = BuildJointTarget(CurrentLocalRotation);
			Constraint->SetAngularOrientationTarget(BlendAuthoredRotation(
				PreviousJointTarget, CurrentJointTarget, PoseAlpha));

			FQuat JointDelta = PreviousJointTarget.Inverse() * CurrentJointTarget;
			JointDelta.Normalize();
			if (JointDelta.W < 0.0f)
			{
				JointDelta = JointDelta * -1.0f;
			}
			FVector JointVelocityAxis = FVector::ForwardVector;
			float JointVelocityAngle = 0.0f;
			JointDelta.ToAxisAndAngle(JointVelocityAxis, JointVelocityAngle);
			// FConstraintInstance exposes angular velocity in revolutions/second.
			Constraint->SetAngularVelocityTarget(
				JointVelocityAxis * (JointVelocityAngle / (PoseInterval * 2.0f * UE_PI)));
		}
	}

	if ((CVarProphecyPhysicalLogTrackingError.GetValueOnGameThread() != 0 ||
		CVarProphecyPhysicalLogPelvisError.GetValueOnGameThread() != 0) && GetWorld())
	{
		static double LastTrackingLogSeconds = -DBL_MAX;
		const double NowSeconds = GetWorld()->GetTimeSeconds();
		if (NowSeconds < LastTrackingLogSeconds || NowSeconds - LastTrackingLogSeconds >= 0.5)
		{
			LastTrackingLogSeconds = NowSeconds;
			FString Errors;
			float MaximumErrorDegrees = 0.0f;
			if (const UPhysicsAsset* PhysicsAsset = Mesh->GetPhysicsAsset();
				PhysicsAsset && PhysicsAsset->ConstraintSetup.Num() == Mesh->Constraints.Num())
			{
				for (int32 ConstraintIndex = 0; ConstraintIndex < Mesh->Constraints.Num(); ++ConstraintIndex)
				{
					const UPhysicsConstraintTemplate* Template = PhysicsAsset->ConstraintSetup[ConstraintIndex];
					FConstraintInstance* Constraint = Mesh->Constraints[ConstraintIndex];
					if (!Template || !Constraint)
					{
						continue;
					}
					const FName ChildBone = Template->DefaultInstance.GetChildBoneName();
					if (ChildBone != TEXT("thigh_l") && ChildBone != TEXT("calf_l") && ChildBone != TEXT("foot_l") &&
						ChildBone != TEXT("thigh_r") && ChildBone != TEXT("calf_r") && ChildBone != TEXT("foot_r"))
					{
						continue;
					}
					FBodyInstance* ChildBody = Mesh->GetBodyInstance(ChildBone);
					FBodyInstance* ParentBody = Mesh->GetBodyInstance(Template->DefaultInstance.ConstraintBone2);
					if (!ChildBody || !ParentBody)
					{
						continue;
					}
					const FTransform ChildJointWorld = Constraint->GetRefFrame(EConstraintFrame::Frame1) *
						ChildBody->GetUnrealWorldTransform();
					const FTransform ParentJointWorld = Constraint->GetRefFrame(EConstraintFrame::Frame2) *
						ParentBody->GetUnrealWorldTransform();
					const FQuat ActualJointRotation = ChildJointWorld.GetRelativeTransform(
						ParentJointWorld).GetRotation().GetNormalized();
					const FQuat TargetJointRotation = Constraint->GetAngularOrientationTarget().Quaternion().GetNormalized();
					const float ErrorDegrees = FMath::RadiansToDegrees(
						TargetJointRotation.AngularDistance(ActualJointRotation));
					MaximumErrorDegrees = FMath::Max(MaximumErrorDegrees, ErrorDegrees);
					Errors += FString::Printf(TEXT(" %s=%.2f"), *ChildBone.ToString(), ErrorDegrees);
				}
			}
			UE_LOG(LogProphecyAgentPhysical, Display,
				TEXT("PHYSICAL_TRACKING max_deg=%.2f%s"), MaximumErrorDegrees, *Errors);
		}
	}

	FTransform Target;
	Target = BlendAuthoredWorldTransform(PreviousTarget, CurrentTarget, PoseAlpha);

	const FTransform Current = PelvisBody->GetUnrealWorldTransform();
	const FVector TargetLinearVelocity =
		(CurrentTarget.GetLocation() - PreviousTarget.GetLocation()) / PoseInterval;
	// Semi-implicit Chaos integrates x1 = x0 + (v0 + a*dt)*dt. Solve that
	// equation for the acceleration which places the pelvis on the next authored
	// target, rather than using a soft spring which necessarily trails the route.
	const FVector NextTargetLocation = Target.GetLocation() + TargetLinearVelocity * DeltaSeconds;
	FVector LinearAcceleration =
		(NextTargetLocation - Current.GetLocation() -
			PelvisBody->GetUnrealWorldVelocity() * DeltaSeconds) /
		FMath::Square(DeltaSeconds);
	// The pelvis drive supports the entire articulated mass. Feed forward exactly
	// that weight so position error is reserved for tracking, not static sag.
	float TotalSimulatedMass = 0.0f;
	for (const FBodyInstance* Body : Mesh->Bodies)
	{
		if (Body && Body->IsInstanceSimulatingPhysics())
		{
			TotalSimulatedMass += Body->GetBodyMass();
		}
	}
	const float PelvisMass = FMath::Max(PelvisBody->GetBodyMass(), UE_SMALL_NUMBER);
	if (GetWorld() && TotalSimulatedMass > 0.0f)
	{
		LinearAcceleration.Z -= GetWorld()->GetGravityZ() * TotalSimulatedMass / PelvisMass;
	}
	PelvisBody->AddForce(LinearAcceleration, true, true);

	FQuat RotationError = Target.GetRotation() * Current.GetRotation().Inverse();
	RotationError.Normalize();
	if (RotationError.W < 0.0f)
	{
		RotationError = RotationError * -1.0f;
	}
	FVector ErrorAxis = FVector::ForwardVector;
	float ErrorAngle = 0.0f;
	RotationError.ToAxisAndAngle(ErrorAxis, ErrorAngle);

	FVector TargetAngularVelocity = FVector::ZeroVector;
	{
		FQuat TargetDelta = CurrentTarget.GetRotation() * PreviousTarget.GetRotation().Inverse();
		TargetDelta.Normalize();
		if (TargetDelta.W < 0.0f)
		{
			TargetDelta = TargetDelta * -1.0f;
		}
		FVector TargetAxis = FVector::ForwardVector;
		float TargetAngle = 0.0f;
		TargetDelta.ToAxisAndAngle(TargetAxis, TargetAngle);
		TargetAngularVelocity = TargetAxis * (TargetAngle / PoseInterval);
	}
	FQuat NextTargetRotation = FQuat(
		TargetAngularVelocity.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector),
		TargetAngularVelocity.Length() * DeltaSeconds) * Target.GetRotation();
	NextTargetRotation.Normalize();
	FQuat NextRotationError = NextTargetRotation * Current.GetRotation().Inverse();
	NextRotationError.Normalize();
	if (NextRotationError.W < 0.0f)
	{
		NextRotationError = NextRotationError * -1.0f;
	}
	FVector NextErrorAxis = FVector::ForwardVector;
	float NextErrorAngle = 0.0f;
	NextRotationError.ToAxisAndAngle(NextErrorAxis, NextErrorAngle);
	const FVector DesiredNextAngularVelocity = NextErrorAxis * (NextErrorAngle / DeltaSeconds);
	const FVector AngularAcceleration =
		(DesiredNextAngularVelocity - PelvisBody->GetUnrealWorldAngularVelocityInRadians()) /
		DeltaSeconds;
	PelvisBody->AddTorqueInRadians(AngularAcceleration, true, true);
	if (GetWorld())
	{
		// Cancel the external gravity moment of the articulated mass about the
		// driven pelvis. Joint reactions remain fully physical; this only supplies
		// the world torque that a standing character's support would provide.
		const FVector GravityForcePerKg(0.0f, 0.0f, GetWorld()->GetGravityZ());
		FVector GravityMoment = FVector::ZeroVector;
		for (const FBodyInstance* Body : Mesh->Bodies)
		{
			if (Body && Body != PelvisBody && Body->IsInstanceSimulatingPhysics())
			{
				const FVector LeverArm = Body->GetUnrealWorldTransform().GetLocation() - Current.GetLocation();
				GravityMoment += FVector::CrossProduct(LeverArm, GravityForcePerKg * Body->GetBodyMass());
			}
		}
		PelvisBody->AddTorqueInRadians(-GravityMoment, true, false);
	}

	if (CVarProphecyPhysicalLogPelvisError.GetValueOnGameThread() != 0 && GetWorld())
	{
		static double LastPelvisLogSeconds = -DBL_MAX;
		const double NowSeconds = GetWorld()->GetTimeSeconds();
		if (NowSeconds < LastPelvisLogSeconds || NowSeconds - LastPelvisLogSeconds >= 0.25)
		{
			LastPelvisLogSeconds = NowSeconds;
			const float ErrorDegrees = FMath::RadiansToDegrees(
				Target.GetRotation().AngularDistance(Current.GetRotation()));
			const float PositionErrorCm = FVector::Distance(
				Target.GetLocation(), Current.GetLocation());
			FString BodyErrors;
			float MaximumBodyRotationErrorDegrees = 0.0f;
			float MaximumBodyPositionErrorCm = 0.0f;
			static const FName TrackedBodyNames[] = {
				TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"),
				TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r") };
			for (const FName BodyName : TrackedBodyNames)
			{
				const int32 PoseIndex = AuthoredPose.BoneNames.IndexOfByKey(BodyName);
				FBodyInstance* Body = Mesh->GetBodyInstance(BodyName);
				if (!Body || !AuthoredPose.PreviousComponentTransforms.IsValidIndex(PoseIndex) ||
					!AuthoredPose.ComponentTransforms.IsValidIndex(PoseIndex))
				{
					continue;
				}
				const FTransform PreviousBodyTarget = AuthoredPose.PreviousComponentTransforms[PoseIndex] *
					AuthoredPose.PreviousComponentWorldTransform;
				const FTransform CurrentBodyTarget = AuthoredPose.ComponentTransforms[PoseIndex] *
					AuthoredPose.ComponentWorldTransform;
				const FTransform BodyTarget = BlendAuthoredWorldTransform(
					PreviousBodyTarget, CurrentBodyTarget, PoseAlpha);
				const FTransform ActualBody = Body->GetUnrealWorldTransform();
				const float RotationErrorDegrees = FMath::RadiansToDegrees(
					BodyTarget.GetRotation().AngularDistance(ActualBody.GetRotation()));
				const float BodyPositionErrorCm = FVector::Distance(
					BodyTarget.GetLocation(), ActualBody.GetLocation());
				MaximumBodyRotationErrorDegrees = FMath::Max(
					MaximumBodyRotationErrorDegrees, RotationErrorDegrees);
				MaximumBodyPositionErrorCm = FMath::Max(
					MaximumBodyPositionErrorCm, BodyPositionErrorCm);
				BodyErrors += FString::Printf(TEXT(" %s=%.1fdeg/%.1fcm"),
					*BodyName.ToString(), RotationErrorDegrees, BodyPositionErrorCm);
			}
			UE_LOG(LogProphecyAgentPhysical, Display,
				TEXT("PELVIS_TRACKING error_cm=%.2f error_deg=%.2f current_w_deg_s=%.2f target_w_deg_s=%.2f limb_max_deg=%.2f limb_max_cm=%.2f%s"),
				PositionErrorCm, ErrorDegrees,
				FMath::RadiansToDegrees(PelvisBody->GetUnrealWorldAngularVelocityInRadians().Length()),
				FMath::RadiansToDegrees(TargetAngularVelocity.Length()),
				MaximumBodyRotationErrorDegrees,
				MaximumBodyPositionErrorCm,
				*BodyErrors);
		}
	}

	PreviousPhysicalRootTarget = Target;
	bHasPreviousPhysicalRootTarget = true;
#endif
}

void AProphecyAgent::ApplyCollisionMode(EProphecyAgentSimulationMode Mode)
{
	Capsule->SetCollisionObjectType(ProphecyAgentCapsuleChannel);
	Capsule->SetGenerateOverlapEvents(false);
	Mesh->SetCollisionObjectType(ProphecyAgentLimbChannel);
	Mesh->SetGenerateOverlapEvents(false);

	if (Mode == EProphecyAgentSimulationMode::Physical)
	{
		// The managed root capsule supports the agent on static ground, but never
		// participates in agent-agent collision. The actual limbs own those contacts.
		Capsule->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Capsule->SetCollisionResponseToAllChannels(ECR_Ignore);
		Capsule->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);

		// Drive validation: create the skeletal physics state with contact filters
		// already disabled. NoCollision also removes the bodies and constraints,
		// whereas QueryAndPhysics + Ignore keeps joint simulation but no contacts.
		Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
		Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		return;
	}

	// Kinematic agents use one cheap capsule. It blocks other kinematic capsules
	// and Physical limbs. A Physical capsule ignores this channel from its side.
	Capsule->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Capsule->SetCollisionResponseToAllChannels(ECR_Block);
	Capsule->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
	Capsule->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetCollisionResponseToAllChannels(ECR_Block);
}

bool AProphecyAgent::SetPhysicalDriveMode(EProphecyAgentPhysicalDriveMode NewMode)
{
	if (SimulationMode != EProphecyAgentSimulationMode::Kinematic || bPhysicalDriveConfigured)
	{
		return false;
	}

	PhysicalDriveMode = NewMode;
	return true;
}

void AProphecyAgent::SetMACDEnabled(bool bEnabled)
{
	bMACDEnabled = bEnabled;

	// UPrimitiveComponent::SetAllUseMACD does not iterate USkeletalMeshComponent::Bodies
	// in UE 5.7, so apply the runtime flag to every rigid body explicitly.
	for (FBodyInstance* BodyInstance : Mesh->Bodies)
	{
		if (BodyInstance)
		{
			BodyInstance->SetUseMACD(bEnabled);
		}
	}
}

FVector AProphecyAgent::GetRootLowPoint() const
{
	return Capsule->GetComponentLocation() - Capsule->GetUpVector() * Capsule->GetScaledCapsuleHalfHeight();
}

bool AProphecyAgent::SetManagedRootLowPoint(
	const FVector& LowPoint,
	float YawDegrees,
	FVector& OutAppliedLowPoint,
	FVector& OutBlockingNormal,
	bool& bOutWorldStaticBlocked)
{
	SetActorRotation(FRotator(0.0, YawDegrees, 0.0), ETeleportType::None);
	const FVector TargetLocation = LowPoint + FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight();
	FHitResult Hit;
	SetActorLocation(
		TargetLocation,
		true,
		&Hit,
		ETeleportType::None);
	OutBlockingNormal = FVector::ZeroVector;
	bOutWorldStaticBlocked = false;
	if (Hit.bBlockingHit)
	{
		bOutWorldStaticBlocked = Hit.Component.IsValid() &&
			Hit.Component->GetCollisionObjectType() == ECC_WorldStatic;
		OutBlockingNormal = Hit.Normal.GetSafeNormal2D();
		if (Hit.bStartPenetrating && !OutBlockingNormal.IsNearlyZero())
		{
			// Standard minimal-translation depenetration: move only far enough to
			// leave the blocking surface, then preserve the tangential intent.
			SetActorLocation(
				GetActorLocation() + OutBlockingNormal * (Hit.PenetrationDepth + 0.5f),
				false,
				nullptr,
				ETeleportType::None);
		}

		const FVector RemainingDelta = TargetLocation - GetActorLocation();
		const FVector SlideDelta = FVector::VectorPlaneProject(RemainingDelta, OutBlockingNormal);
		if (!SlideDelta.IsNearlyZero())
		{
			FHitResult SlideHit;
			SetActorLocation(GetActorLocation() + SlideDelta, true, &SlideHit, ETeleportType::None);
			if (SlideHit.bBlockingHit)
			{
				const FVector SlideNormal = SlideHit.Normal.GetSafeNormal2D();
				if (!SlideNormal.IsNearlyZero()) OutBlockingNormal = SlideNormal;
			}
		}
	}
	OutAppliedLowPoint = GetRootLowPoint();
	return Hit.bBlockingHit;
}

void AProphecyAgent::TeleportManagedRootLowPoint(const FVector& LowPoint, float YawDegrees)
{
	SetActorRotation(FRotator(0.0, YawDegrees, 0.0), ETeleportType::TeleportPhysics);
	SetActorLocation(
		LowPoint + FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight(),
		false,
		nullptr,
		ETeleportType::TeleportPhysics);
}

bool AProphecyAgent::SampleActualComponentPose(
	TConstArrayView<FName> BoneNames,
	TArrayView<FTransform> OutComponentTransforms) const
{
	if (BoneNames.Num() != OutComponentTransforms.Num() || !Mesh->IsRegistered())
	{
		return false;
	}

	const TArray<FTransform>& ComponentSpaceTransforms = Mesh->GetComponentSpaceTransforms();
	for (int32 Index = 0; Index < BoneNames.Num(); ++Index)
	{
		const int32 BoneIndex = Mesh->GetBoneIndex(BoneNames[Index]);
		if (!ComponentSpaceTransforms.IsValidIndex(BoneIndex))
		{
			return false;
		}
		OutComponentTransforms[Index] = ComponentSpaceTransforms[BoneIndex];
	}
	return true;
}

void AProphecyAgent::HandleMeshHit(
	UPrimitiveComponent* HitComponent,
	AActor* OtherActor,
	UPrimitiveComponent* OtherComponent,
	FVector NormalImpulse,
	const FHitResult& Hit)
{
	if (SimulationMode == EProphecyAgentSimulationMode::Physical && bGeneratePhysicalHitEvents)
	{
		OnPhysicalHit.Broadcast(this, OtherActor, OtherComponent, NormalImpulse, Hit);
	}
}
