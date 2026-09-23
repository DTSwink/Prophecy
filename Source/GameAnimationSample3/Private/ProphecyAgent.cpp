#include "ProphecyAgent.h"
#include "ProphecyAgentTime.h"
#include "ProphecyClampProfiles.h"
#include "ProphecyAngularLimitBlend.h"
#include "ProphecyAgentResetPhysics.h"
#include "ProphecyDefenseArmedGate.h"
#include "ProphecyDefenseControls.h"
#include "ProphecyRootFacing.h"
#include "ProphecyPelvisInertia.h"
#include "ProphecyHandInertia.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyPhysicalContext.h"
#include "ProphecyPhysicalBlendSubsystem.h"

#include "ProphecyManualServoCapture.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNInterpolation.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyNNPhysicalTargetPose.h"
#include "ProphecyAttackFists.h"
#include "ProphecyModeTransitions.h"
#include "ProphecyCrowdNameLookup.h"

#include "Chaos/ChaosConstraintSettings.h"
#include "Chaos/ChaosEngineInterface.h"
#include "PBDRigidsSolver.h"
#include "Chaos/SimCallbackObject.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/Volume.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "Misc/ScopeLock.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"
#include "UObject/UnrealType.h"

namespace
{
	DEFINE_LOG_CATEGORY_STATIC(LogProphecyAgentPhysical, Log, All);

	const TArray<FName>& PhysicalFeedbackBoneNames()
	{
		static const TArray<FName> Names = {
			TEXT("pelvis"),
			TEXT("spine_01"), TEXT("spine_02"), TEXT("spine_03"), TEXT("spine_04"), TEXT("spine_05"),
			TEXT("neck_01"), TEXT("neck_02"), TEXT("head"),
			TEXT("clavicle_l"), TEXT("upperarm_l"), TEXT("hand_l"),
			TEXT("clavicle_r"), TEXT("upperarm_r"), TEXT("hand_r"),
			TEXT("thigh_l"), TEXT("foot_l"), TEXT("ball_l"),
			TEXT("thigh_r"), TEXT("foot_r"), TEXT("ball_r")
		};
		return Names;
	}

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

	struct FNNPoseDataSource
	{
		int32 AgentId = INDEX_NONE;
		float PoseIntervalSeconds = 1.0f / 30.0f;
		bool bInterpolatePose = true;
	};

	static TMap<TWeakObjectPtr<AProphecyAgent>, FNNPoseDataSource> NNPoseDataSources;

	struct FManualFollowerSubstepBody
	{
		FPhysicsActorHandle Actor = nullptr;
		FVector TargetPosition = FVector::ZeroVector;
		FQuat TargetRotation = FQuat::Identity;
		float LinearStrengthScale = 1.0f;
		float AngularStrengthScale = 1.0f;
	};

	struct FManualFollowerSubstepTargets
	{
		TArray<FManualFollowerSubstepBody, TInlineAllocator<32>> Bodies;
		float MaximumSubstepSeconds = 1.0f / 60.0f;
		int32 InertiaBodyIndex = INDEX_NONE;
		FVector InertiaLinear = FVector::OneVector, InertiaAngular = FVector::OneVector;
	};

	class FManualFollowerSubstepCallback final : public Chaos::TSimCallbackObject<
		Chaos::FSimCallbackNoInput,
		Chaos::FSimCallbackNoOutput,
		Chaos::ESimCallbackOptions::PreIntegrate>
	{
	public:
		bool IsCapturing_External() const
		{
			check(IsInGameThread());
			// Only the game thread attaches or detaches this pointer. The worker
			// uses the already-existing target lock for its contents.
			return Capture.IsValid();
		}

		bool BeginCapture_External(int32 MaxPackets, int32 MaxSteps, FString& OutError)
		{
			check(IsInGameThread());
			if (Capture)
			{
				OutError = TEXT("This manual callback is already recording.");
				return false;
			}
			TUniquePtr<ProphecyManualServoCapture::FCapture> NewCapture =
				MakeUnique<ProphecyManualServoCapture::FCapture>();
			NewCapture->PacketCapacity = MaxPackets;
			NewCapture->StepCapacity = MaxSteps;
			NewCapture->Packets.SetNum(MaxPackets);
			NewCapture->Steps.SetNum(MaxSteps);
			FScopeLock ScopeLock(&TargetLock);
			Capture = MoveTemp(NewCapture);
			CurrentPacketSequence = 0;
			CurrentPacketAttemptSequence = 0;
			CurrentSourceSequence = 0;
			LastConsumedPacketSequence = 0;
			bCurrentPacketRecorded = false;
			return true;
		}

		bool ReadCapture_External(ProphecyManualServoCapture::FCapture& OutCapture, FString& OutError)
		{
			check(IsInGameThread());
			FScopeLock ScopeLock(&TargetLock);
			if (!Capture)
			{
				OutError = TEXT("This manual callback is not recording.");
				return false;
			}
			OutCapture = *Capture;
			OutCapture.Packets.SetNum(OutCapture.PacketsRecorded, EAllowShrinking::No);
			OutCapture.Steps.SetNum(OutCapture.StepsRecorded, EAllowShrinking::No);
			return true;
		}

		bool EndCapture_External(ProphecyManualServoCapture::FCapture& OutCapture, FString& OutError)
		{
			check(IsInGameThread());
			TUniquePtr<ProphecyManualServoCapture::FCapture> FinishedCapture;
			{
				FScopeLock ScopeLock(&TargetLock);
				if (!Capture)
				{
					OutError = TEXT("This manual callback is not recording.");
					return false;
				}
				FinishedCapture = MoveTemp(Capture);
			}
			OutCapture = MoveTemp(*FinishedCapture);
			OutCapture.Packets.SetNum(OutCapture.PacketsRecorded, EAllowShrinking::No);
			OutCapture.Steps.SetNum(OutCapture.StepsRecorded, EAllowShrinking::No);
			return true;
		}

		void RecordPublishFailure_External(ProphecyManualServoCapture::EPublishFailure Failure)
		{
			check(IsInGameThread());
			if (!Capture)
			{
				return;
			}
			FScopeLock ScopeLock(&TargetLock);
			++Capture->PublishAttempts;
			++Capture->FailedPublications;
			Capture->LastPublishFailure = Failure;
		}

		void PublishTargets_External(
			FManualFollowerSubstepTargets&& InTargets,
			const ProphecyManualServoCapture::FPacket* Packet = nullptr)
		{
			FScopeLock ScopeLock(&TargetLock);
			if (Capture)
			{
				CurrentPacketAttemptSequence = ++Capture->PublishAttempts;
				CurrentPacketSequence = ++Capture->PublishedPackets;
				CurrentSourceSequence = Packet ? Packet->SourceSequence : 0;
				bCurrentPacketRecorded = false;
				Capture->bBodyOverflow |= InTargets.Bodies.Num() > ProphecyManualServoCapture::MaxBodies;
				if (Packet && Capture->PacketsRecorded < Capture->PacketCapacity)
				{
					ProphecyManualServoCapture::FPacket& RecordedPacket =
						Capture->Packets[Capture->PacketsRecorded++];
					RecordedPacket = *Packet;
					RecordedPacket.Sequence = CurrentPacketSequence;
					RecordedPacket.AttemptSequence = CurrentPacketAttemptSequence;
					RecordedPacket.GameFrame = GFrameCounter;
					bCurrentPacketRecorded = true;
				}
				else
				{
					Capture->bPacketOverflow = true;
				}
			}
			Targets = MoveTemp(InTargets);
		}

	private:
		virtual void OnPreSimulate_Internal() override
		{
			// Registration always enters the frame callback path once. The follower
			// deliberately performs all work in the per-substep hook below.
		}

		virtual void OnPreIntegrate_Internal() override
		{
			FScopeLock ScopeLock(&TargetLock);
			const float StepSeconds = FMath::Max(Targets.MaximumSubstepSeconds, UE_SMALL_NUMBER);
			ProphecyManualServoCapture::FStep* RecordedStep = nullptr;
			if (Capture)
			{
				const uint64 ConsumedSequence = ++Capture->ConsumedCallbacks;
				const bool bRepeated = CurrentPacketSequence != 0 &&
					CurrentPacketSequence == LastConsumedPacketSequence;
				const bool bStale = Capture->PublishAttempts > CurrentPacketAttemptSequence;
				const bool bUnrecorded = !bCurrentPacketRecorded;
				Capture->RepeatedPacketConsumptions += bRepeated ? 1 : 0;
				Capture->StalePacketConsumptions += bStale ? 1 : 0;
				Capture->UnrecordedPacketConsumptions += bUnrecorded ? 1 : 0;
				LastConsumedPacketSequence = CurrentPacketSequence;
				if (Capture->StepsRecorded < Capture->StepCapacity)
				{
					RecordedStep = &Capture->Steps[Capture->StepsRecorded++];
					RecordedStep->Sequence = ConsumedSequence;
					RecordedStep->PacketSequence = CurrentPacketSequence;
					RecordedStep->SourceSequence = CurrentSourceSequence;
					RecordedStep->LatestAttemptSequence = Capture->PublishAttempts;
					RecordedStep->CallbackSimTimeSeconds = static_cast<double>(GetSimTime_Internal());
					RecordedStep->CallbackDeltaSeconds = static_cast<double>(GetDeltaTime_Internal());
					RecordedStep->DenominatorSeconds = StepSeconds;
					RecordedStep->BodyCount = FMath::Min(Targets.Bodies.Num(), ProphecyManualServoCapture::MaxBodies);
					RecordedStep->bRepeatedPacket = bRepeated;
					RecordedStep->bStaleAfterFailedPublish = bStale;
					RecordedStep->bUnrecordedPacket = bUnrecorded;
				}
				else
				{
					Capture->bStepOverflow = true;
				}
			}
			int32 BodyIndex = 0;
			for (const FManualFollowerSubstepBody& Body : Targets.Bodies)
			{
				ProphecyManualServoCapture::FBodyStep* BodyStep =
					RecordedStep && BodyIndex < ProphecyManualServoCapture::MaxBodies
						? &RecordedStep->Bodies[BodyIndex] : nullptr;
				const bool bPelvisInertia = BodyIndex++ == Targets.InertiaBodyIndex;
				Chaos::FRigidBodyHandle_Internal* Rigid = Body.Actor
					? Body.Actor->GetPhysicsThreadAPI()
					: nullptr;
				if (!Rigid)
				{
					if (Capture)
					{
						++Capture->MissingBodySamples;
					}
					continue;
				}
				if (BodyStep)
				{
					BodyStep->bValid = true;
					BodyStep->Position = FVector(Rigid->X());
					BodyStep->Rotation = FQuat(Rigid->R());
					BodyStep->LinearVelocityBefore = FVector(Rigid->V());
					BodyStep->AngularVelocityBefore = FVector(Rigid->W());
				}

				if (Body.LinearStrengthScale > 0.0f)
				{
					const FVector LinearVelocity =
						(Body.TargetPosition - FVector(Rigid->X())) / StepSeconds;
					const FVector CurrentVelocity(Rigid->V());
					FVector Correction=(LinearVelocity - CurrentVelocity) * Body.LinearStrengthScale;
					if (bPelvisInertia) Correction *= Targets.InertiaLinear;
					Rigid->SetV(Chaos::FVec3(CurrentVelocity + Correction));
				}

				if (Body.AngularStrengthScale > 0.0f)
				{
					FQuat RotationDelta = Body.TargetRotation * FQuat(Rigid->R()).Inverse();
					RotationDelta.Normalize();
					if (RotationDelta.W < 0.0f)
					{
						RotationDelta = RotationDelta * -1.0f;
					}
					FVector Axis = FVector::ForwardVector;
					float AngleRadians = 0.0f;
					RotationDelta.ToAxisAndAngle(Axis, AngleRadians);
					const FVector AngularVelocity =
						Axis.GetSafeNormal() * (AngleRadians / StepSeconds);
					const FVector CurrentAngularVelocity(Rigid->W());
					FVector Correction=(AngularVelocity - CurrentAngularVelocity) * Body.AngularStrengthScale;
					if (bPelvisInertia) Correction *= Targets.InertiaAngular;
					Rigid->SetW(Chaos::FVec3(CurrentAngularVelocity + Correction));
				}
				if (BodyStep)
				{
					BodyStep->LinearVelocityAfter = FVector(Rigid->V());
					BodyStep->AngularVelocityAfter = FVector(Rigid->W());
				}
			}
		}

		FCriticalSection TargetLock;
		FManualFollowerSubstepTargets Targets;
		TUniquePtr<ProphecyManualServoCapture::FCapture> Capture;
		uint64 CurrentPacketSequence = 0;
		uint64 CurrentPacketAttemptSequence = 0;
		uint64 CurrentSourceSequence = 0;
		uint64 LastConsumedPacketSequence = 0;
		bool bCurrentPacketRecorded = false;
	};

	struct FManualFollowerSubstepState
	{
		FManualFollowerSubstepCallback* Callback = nullptr;
		FPhysScene* PhysicsScene = nullptr;
	};

	static TMap<TWeakObjectPtr<AProphecyAgent>, FManualFollowerSubstepState> ManualFollowerSubstepStates;

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

	void ReleaseManualFollowerSubstepCallback(AProphecyAgent* Agent)
	{
		FManualFollowerSubstepState State;
		if (!ManualFollowerSubstepStates.RemoveAndCopyValue(Agent, State) || !State.Callback)
		{
			return;
		}
		if (State.PhysicsScene && State.PhysicsScene->GetSolver())
		{
			State.PhysicsScene->GetSolver()->UnregisterAndFreeSimCallbackObject_External(State.Callback);
		}
	}

	FManualFollowerSubstepCallback* GetOrCreateManualFollowerSubstepCallback(
		AProphecyAgent* Agent, FPhysScene* PhysicsScene)
	{
		FManualFollowerSubstepState* State = ManualFollowerSubstepStates.Find(Agent);
		if (!State || State->PhysicsScene != PhysicsScene)
		{
			ReleaseManualFollowerSubstepCallback(Agent);
			State = &ManualFollowerSubstepStates.FindOrAdd(Agent);
			State->PhysicsScene = PhysicsScene;
			State->Callback = PhysicsScene->GetSolver()->
				CreateAndRegisterSimCallbackObject_External<FManualFollowerSubstepCallback>();
		}
		else if (!State->Callback)
		{
			State->Callback = PhysicsScene->GetSolver()->
				CreateAndRegisterSimCallbackObject_External<FManualFollowerSubstepCallback>();
		}
		return State->Callback;
	}

	void PublishManualFollowerSubstepTarget(AProphecyAgent* Agent, float DeltaSeconds)
	{
		if (Agent && Agent->IsJoltPhysicalAnimationEnabled())
		{
			FString Error;
			if (!Agent->GetJoltCharacterComponent()->PublishAuthoredTargets(DeltaSeconds, Error))
				UE_LOG(LogProphecyAgentPhysical, Error, TEXT("Jolt target publication failed: %s"), *Error);
			return;
		}
		if (Agent->GetSimulationMode() == EProphecyAgentSimulationMode::HalfSim)
		{
			ReleaseManualFollowerSubstepCallback(Agent);
			return;
		}
		USkeletalMeshComponent* PhysicalMesh = FindManualPhysicalMesh(Agent);
		UWorld* World = Agent ? Agent->GetWorld() : nullptr;
		FPhysScene* PhysicsScene = World ? World->GetPhysicsScene() : nullptr;
		if (!PhysicalMesh || !PhysicalMesh->IsAnySimulatingPhysics() || !PhysicsScene || !PhysicsScene->GetSolver())
		{
			ReleaseManualFollowerSubstepCallback(Agent);
			return;
		}

		TArray<FName> BoneNames;
		TArray<FTransform> FutureWorldTransforms;
		TArray<FTransform> InterpolatedWorldTransforms;
		float InterpolationAlpha = 1.0f;
		if (!Agent->ReadNNFutureWorldPose(
			BoneNames,
			FutureWorldTransforms,
			InterpolatedWorldTransforms,
			InterpolationAlpha))
		{
			const FManualFollowerSubstepState* State = ManualFollowerSubstepStates.Find(Agent);
			if (State && State->Callback)
			{
				State->Callback->RecordPublishFailure_External(
					ProphecyManualServoCapture::EPublishFailure::PoseUnavailable);
			}
			return;
		}

		FManualFollowerSubstepCallback* Callback = GetOrCreateManualFollowerSubstepCallback(Agent, PhysicsScene);
		if (!Callback)
		{
			return;
		}

		TUniquePtr<ProphecyManualServoCapture::FPacket> CapturePacket;
		if (Callback->IsCapturing_External())
		{
			CapturePacket = MakeUnique<ProphecyManualServoCapture::FPacket>();
			CapturePacket->FrameDeltaSeconds = DeltaSeconds;
		}
		FManualFollowerSubstepTargets Targets;
		const bool bPelvisInertia=ProphecyPelvisInertia::GetBodyFollow(Agent,Targets.InertiaLinear,Targets.InertiaAngular);
		const UPhysicsSettings* Settings = UPhysicsSettings::Get();
		Targets.MaximumSubstepSeconds = FMath::Max(
			UE_SMALL_NUMBER,
			Settings && Settings->bSubstepping
				? FMath::Min(DeltaSeconds, Settings->MaxSubstepDeltaTime)
				: DeltaSeconds);
		Targets.Bodies.Reserve(BoneNames.Num());
		for (int32 BoneIndex = 0; BoneIndex < BoneNames.Num(); ++BoneIndex)
		{
			FProphecyBodyMagnetizationSettings BodySettings;
			Agent->GetBodyMagnetizationSettings(BoneNames[BoneIndex], BodySettings);
			if (!Agent->bWorldMagnetizationEnabled || !BodySettings.bSimulateBody ||
				!BodySettings.bMagnetizationEnabled)
			{
				continue;
			}
			FBodyInstance* Body = PhysicalMesh->GetBodyInstance(BoneNames[BoneIndex]);
			if (!Body || !Body->IsInstanceSimulatingPhysics() || !Body->GetPhysicsActor() ||
				!InterpolatedWorldTransforms.IsValidIndex(BoneIndex))
			{
				continue;
			}
			FManualFollowerSubstepBody& OutputBody = Targets.Bodies.AddDefaulted_GetRef();
			if (bPelvisInertia && BoneNames[BoneIndex] == TEXT("pelvis"))
				Targets.InertiaBodyIndex=Targets.Bodies.Num()-1;
			OutputBody.Actor = Body->GetPhysicsActor();
			OutputBody.LinearStrengthScale = FMath::Max(
				0.0f,
				Agent->WorldMagnetizationLinearStrengthScale * BodySettings.LinearStrengthScale);
			OutputBody.AngularStrengthScale = FMath::Max(
				0.0f,
				Agent->WorldMagnetizationAngularStrengthScale * BodySettings.AngularStrengthScale);
			// Chaos integrates the rigid body frame, not the skeletal bone frame.
			// Preserve the PhysicsAsset-authored bone-to-body offset when converting
			// this frame's finalized bone target to its exact rigid-body endpoint.
			const FTransform ActualBoneWorld = PhysicalMesh->GetSocketTransform(
				BoneNames[BoneIndex], RTS_World);
			const FTransform BodyFromBone = Body->GetUnrealWorldTransform().GetRelativeTransform(
				ActualBoneWorld);
			const FTransform TargetBodyWorld = BodyFromBone * InterpolatedWorldTransforms[BoneIndex];
			OutputBody.TargetPosition = TargetBodyWorld.GetLocation();
			OutputBody.TargetRotation = TargetBodyWorld.GetRotation();
			if (CapturePacket && CapturePacket->BodyCount < ProphecyManualServoCapture::MaxBodies)
			{
				ProphecyManualServoCapture::FBoneTarget& RecordedBody =
					CapturePacket->Bodies[CapturePacket->BodyCount++];
				RecordedBody.BoneName = BoneNames[BoneIndex];
				RecordedBody.ActualBoneWorld = ActualBoneWorld;
				RecordedBody.BodyFromBone = BodyFromBone;
				RecordedBody.TargetPosition = OutputBody.TargetPosition;
				RecordedBody.TargetRotation = OutputBody.TargetRotation;
				RecordedBody.LinearStrength = OutputBody.LinearStrengthScale;
				RecordedBody.AngularStrength = OutputBody.AngularStrengthScale;
			}
		}
		if (CapturePacket)
		{
			CapturePacket->MaximumSubstepSeconds = Targets.MaximumSubstepSeconds;
		}
		Callback->PublishTargets_External(MoveTemp(Targets), CapturePacket.Get());
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
		USkeletalMeshComponent* PhysicalMesh = FindManualPhysicalMesh(Agent);
		if (!PhysicalMesh || !PhysicalMesh->IsAnySimulatingPhysics())
		{
			return;
		}
		TArray<FName> BoneNames;
		TArray<FTransform> FutureWorldTransforms;
		TArray<FTransform> InterpolatedWorldTransforms;
		float InterpolationAlpha = 1.0f;
		if (!Agent->ReadNNFutureWorldPose(
			BoneNames,
			FutureWorldTransforms,
			InterpolatedWorldTransforms,
			InterpolationAlpha))
		{
			return;
		}

		FManualFollowerAuditState& State = ManualFollowerAuditStates.FindOrAdd(Agent);
		State.PreviousEndpointTargets.Reset();
		State.PreviousEndpointTargets.Reserve(UE_ARRAY_COUNT(ManualFollowerAuditBones));
		for (const FName BoneName : ManualFollowerAuditBones)
		{
			const int32 PoseIndex = BoneNames.IndexOfByKey(BoneName);
			if (!InterpolatedWorldTransforms.IsValidIndex(PoseIndex))
			{
				State.PreviousEndpointTargets.Reset();
				return;
			}
			State.PreviousEndpointTargets.Add(InterpolatedWorldTransforms[PoseIndex]);
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

	FTransform BlendAuthoredWorldTransform(const FProphecyNNPoseSnapshot& Pose, int32 Index,
		const FTransform& A, const FTransform& B, float Alpha)
	{
		return Pose.InterpolationMode == EProphecyNNInterpolationMode::HermiteSlerp
			? ProphecyNNInterpolation::Sample(Pose, Index, A, B, Alpha)
			: BlendAuthoredWorldTransform(A, B, Alpha);
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

	AProphecyNNLocomotionManager* FindOwningNNManager(const AProphecyAgent* Agent)
	{
		if (!Agent || !Agent->GetWorld() || !Agent->HasValidAgentHandle())
		{
			return nullptr;
		}
		for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld()); It; ++It)
		{
			if (It->ResolveAgent(Agent->GetAgentHandle()) == Agent)
			{
				return *It;
			}
		}
		return nullptr;
	}
}

UCameraComponent* AProphecyAgent::GetAgentCamera() const
{
	return Camera;
}

void AProphecyAgent::SetLocomotionInput(
	FVector WorldMoveInput, bool bRun, FVector FacingWorldDirection, float SpeedScale, float TurnScale)
{
	WorldMoveInput.Z = 0.0;
	FacingWorldDirection.Z = 0.0;
	LocomotionInput.WorldMoveInput = WorldMoveInput.ContainsNaN()
		? FVector::ZeroVector : WorldMoveInput.GetClampedToMaxSize(1.0);
	LocomotionInput.bRun = bRun;
	LocomotionInput.FacingWorldDirection = FacingWorldDirection.ContainsNaN()
		? FVector::ZeroVector : FacingWorldDirection.GetSafeNormal();
	// A repeated fixed vector is still an explicit steering command. Do not
	// confuse it with the facing vector written back by an angular impulse.
	if (!LocomotionInput.FacingWorldDirection.IsNearlyZero()) ProphecyRootFacing::Explicit(this);
	LocomotionInput.SpeedScale = FMath::IsFinite(SpeedScale) ? FMath::Clamp(SpeedScale, 0.0f, 1.0f) : 0.0f;
	LocomotionInput.TurnScale = FMath::IsFinite(TurnScale) ? FMath::Clamp(TurnScale, 0.0f, 1.0f) : 0.0f;
	bUseBlueprintLocomotionInput = true;
}

void AProphecyAgent::SetLocomotionRunning(bool bRun)
{
	LocomotionInput.bRun = bRun;
	bUseBlueprintLocomotionInput = true;
}

void AProphecyAgent::StopLocomotionInput()
{
	LocomotionInput.WorldMoveInput = FVector::ZeroVector;
	LocomotionInput.FacingWorldDirection = FVector::ZeroVector;
	LocomotionInput.bRun = false; // Request Walk through the normal policy blend, not a hard reset.
	bUseBlueprintLocomotionInput = true;
}

bool AProphecyAgent::GetLocomotionState(
	FVector& WorldVelocityCmPerSecond, FVector& FacingWorldDirection, bool& bRun) const
{
	WorldVelocityCmPerSecond = FVector::ZeroVector;
	FacingWorldDirection = FVector::ZeroVector;
	bRun = false;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentLocomotionState(
		AgentHandle, WorldVelocityCmPerSecond, FacingWorldDirection, bRun);
}

bool AProphecyAgent::GetLocomotionTarget(FVector& TargetWorldVelocityCmPerSecond,
	float& TargetSpeedCmPerSecond, FVector& TargetFacingWorldDirection, bool& bRun) const
{
	TargetWorldVelocityCmPerSecond = FVector::ZeroVector;
	TargetSpeedCmPerSecond = 0.0f;
	TargetFacingWorldDirection = FVector::ZeroVector;
	bRun = false;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentLocomotionTarget(AgentHandle,
		TargetWorldVelocityCmPerSecond, TargetSpeedCmPerSecond, TargetFacingWorldDirection, bRun);
}

bool AProphecyAgent::GetRootImpulseMassProperties(float& MassKg, float& YawInertiaKgCmSquared) const
{
	MassKg = YawInertiaKgCmSquared = 0.0f;
	const FBodyInstance* Body = Capsule ? Capsule->GetBodyInstance() : nullptr;
	if (!Body || !Body->IsValidBodyInstance()) return false;
	MassKg = Body->GetBodyMass();
	const FVector Inertia = Body->GetBodyInertiaTensor();
	const FTransform MassWorld = Body->GetMassSpaceLocal() * Body->GetUnrealWorldTransform();
	const FVector Axis = MassWorld.GetRotation().UnrotateVector(FVector::UpVector);
	YawInertiaKgCmSquared = float(FVector::DotProduct(Axis * Axis, Inertia));
	return FMath::IsFinite(MassKg) && FMath::IsFinite(YawInertiaKgCmSquared) &&
		MassKg > UE_SMALL_NUMBER && YawInertiaKgCmSquared > UE_SMALL_NUMBER;
}

bool AProphecyAgent::AddRootImpulse(FVector WorldLinearImpulse, FVector WorldAngularImpulseRadians, bool bVelocityChange)
{
	if (WorldLinearImpulse.ContainsNaN() || WorldAngularImpulseRadians.ContainsNaN()) return false;
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	if (!Manager || !bNNInferenceEnabled) return false;
	float Mass = 1.0f, Inertia = 1.0f;
	if (!bVelocityChange && !GetRootImpulseMassProperties(Mass, Inertia)) return false;
	return Manager->AddAgentRootVelocityImpulse(AgentHandle,
		FVector(WorldLinearImpulse.X, WorldLinearImpulse.Y, 0.0) / Mass,
		WorldAngularImpulseRadians.Z / Inertia);
}

bool AProphecyAgent::GetRootVelocity(FVector& Linear, FVector& Angular) const
{
	Linear = Angular = FVector::ZeroVector;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentRootVelocity(AgentHandle, Linear, Angular);
}

bool AProphecyAgent::SetGlobalHalfAttackTargetRadius(float RadiusCm)
{
	return AProphecyNNLocomotionManager::SetHalfAttackTargetRadius(GetWorld(), RadiusCm);
}

float AProphecyAgent::GetGlobalHalfAttackTargetRadius() const
{
	return AProphecyNNLocomotionManager::GetHalfAttackTargetRadius(GetWorld());
}

bool AProphecyAgent::GetNNAttackTarget(FVector& Requested, FVector& Effective, FVector& Ghost) const
{
	Requested = Effective = Ghost = FVector::ZeroVector;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentNNAttackTarget(AgentHandle, Requested, Effective, Ghost);
}

bool AProphecyAgent::GetMassWeightedPoseError(FVector& LinearErrorKgCm, FVector& AngularErrorKgRadians,
	float& TotalMassKg, int32& BodyCount) const
{
	LinearErrorKgCm = AngularErrorKgRadians = FVector::ZeroVector;
	TotalMassKg = 0.0f;
	BodyCount = 0;
	const USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	const bool bJolt = IsJoltPhysicalAnimationEnabled();
	if (!PhysicalMesh || (!bJolt && !PhysicalMesh->IsAnySimulatingPhysics())) return false;
	TArray<FName> Names;
	TArray<FTransform> Future, Presented;
	float Alpha;
	if (!ReadNNFutureWorldPose(Names, Future, Presented, Alpha)) return false;
	TSet<const FBodyInstance*> Seen;
	TSet<int32> SeenJoltBodies;
	for (int32 Index = 0; Index < Names.Num(); ++Index)
	{
		double Mass = 0.0;
		FTransform Actual;
		if (bJolt)
		{
			int32 BodyIndex = INDEX_NONE;
			if (!JoltCharacter->ReadPoseErrorBody(Names[Index], BodyIndex, Mass, Actual)
				|| SeenJoltBodies.Contains(BodyIndex)) continue;
			SeenJoltBodies.Add(BodyIndex);
		}
		else
		{
			FBodyInstance* Body = PhysicalMesh->GetBodyInstance(Names[Index]);
			if (!Body || !Body->IsValidBodyInstance() || !Body->IsInstanceSimulatingPhysics() || Seen.Contains(Body)) continue;
			Seen.Add(Body);
			Mass = Body->GetBodyMass();
			Actual = Body->GetUnrealWorldTransform();
		}
		if (!FMath::IsFinite(Mass) || Mass <= 0.0 || Actual.ContainsNaN()) continue;
		const FTransform& Target = Presented[Index];
		LinearErrorKgCm += Mass * (Actual.GetLocation() - Target.GetLocation());
		FQuat Error = (Actual.GetRotation() * Target.GetRotation().Inverse()).GetNormalized();
		if (Error.W < 0.0) Error = Error * -1.0; // shortest arc, independent of quaternion sign
		const FVector Imaginary(Error.X, Error.Y, Error.Z);
		const double SinHalfAngle = Imaginary.Size();
		const double RotationScale = SinHalfAngle > 1.0e-12
			? 2.0 * FMath::Atan2(SinHalfAngle, Error.W) / SinHalfAngle : 2.0;
		AngularErrorKgRadians += Mass * RotationScale * Imaginary;
		TotalMassKg += float(Mass);
		++BodyCount;
	}
	return BodyCount > 0;
}

bool AProphecyAgent::SetAllPhysicalFeedbackTolerances(
	float LinearToleranceCm,
	float AngularToleranceDegrees)
{
	CancelPhysicalFeedbackToleranceBlend();
	const float Linear = FMath::Max(0.0f, LinearToleranceCm);
	const float Angular = FMath::Max(0.0f, AngularToleranceDegrees);
	for (const FName BoneName : PhysicalFeedbackBoneNames())
	{
		if (ProphecyPhysicalContext::IsManaged(this,BoneName,ProphecyPhysicalContext::EKind::Feedback))
		{
			ProphecyPhysicalContext::Set(*this,BoneName,ProphecyPhysicalContext::EKind::Feedback,true,{Linear,Angular},0);
			continue;
		}
		FProphecyPhysicalFeedbackToleranceSettings& Settings =
			PhysicalFeedbackTolerances.FindOrAdd(BoneName);
		Settings.LinearToleranceCm = Linear;
		Settings.AngularToleranceDegrees = Angular;
	}
	if (auto* Manager = FindOwningNNManager(this); Manager && !IsSwordAttackActive())
		Manager->SetAgentAllPhysicalFeedbackTolerances(AgentHandle, Linear, Angular);
	return true;
}

bool AProphecyAgent::SetPhysicalFeedbackTolerance(
	FName BoneName,
	float LinearToleranceCm,
	float AngularToleranceDegrees,EProphecyLocomotionSelection Locomotion,EProphecyEquipmentSelection Equipment)
{
	if (Locomotion!=EProphecyLocomotionSelection::Both || Equipment!=EProphecyEquipmentSelection::Both
		|| ProphecyPhysicalContext::IsManaged(this,BoneName,ProphecyPhysicalContext::EKind::Feedback))
		return ProphecyPhysicalContext::Set(*this,BoneName,ProphecyPhysicalContext::EKind::Feedback,true,
			{LinearToleranceCm,AngularToleranceDegrees},0,Locomotion,Equipment);
	if (BoneName.IsNone() || !PhysicalFeedbackBoneNames().Contains(BoneName))
	{
		return false;
	}
	CancelPhysicalFeedbackToleranceBlend(BoneName);
	FProphecyPhysicalFeedbackToleranceSettings& Settings =
		PhysicalFeedbackTolerances.FindOrAdd(BoneName);
	Settings.LinearToleranceCm = FMath::Max(0.0f, LinearToleranceCm);
	Settings.AngularToleranceDegrees = FMath::Max(0.0f, AngularToleranceDegrees);
	if (auto* Manager = FindOwningNNManager(this))
		Manager->SetAgentPhysicalFeedbackTolerance(AgentHandle, BoneName,
			Settings.LinearToleranceCm, Settings.AngularToleranceDegrees);
	return true;
}

int32 AProphecyAgent::SetPhysicalFeedbackToleranceBelow(
	FName ParentBone,
	bool bIncludeParent,
	float LinearToleranceCm,
	float AngularToleranceDegrees,EProphecyLocomotionSelection Locomotion,EProphecyEquipmentSelection Equipment)
{
	if (!ProphecyPhysicalContext::Valid(Locomotion,Equipment)) return 0;
	const USkeletalMeshComponent* PoseMesh = GetPoseReferenceMesh();
	const USkeletalMesh* SkeletalMesh = PoseMesh ? PoseMesh->GetSkeletalMeshAsset() : nullptr;
	if (!SkeletalMesh || ParentBone.IsNone())
	{
		return 0;
	}
	const FReferenceSkeleton& ReferenceSkeleton = SkeletalMesh->GetRefSkeleton();
	const int32 ParentIndex = ReferenceSkeleton.FindBoneIndex(ParentBone);
	if (ParentIndex == INDEX_NONE)
	{
		return 0;
	}

	int32 ChangedBones = 0;
	for (const FName BoneName : PhysicalFeedbackBoneNames())
	{
		int32 BoneIndex = ReferenceSkeleton.FindBoneIndex(BoneName);
		bool bDescendant = false;
		for (int32 Cursor = BoneIndex; Cursor != INDEX_NONE; Cursor = ReferenceSkeleton.GetParentIndex(Cursor))
		{
			if (Cursor == ParentIndex)
			{
				bDescendant = BoneIndex != ParentIndex || bIncludeParent;
				break;
			}
		}
		if (bDescendant && ProphecyPhysicalContext::Set(*this,BoneName,ProphecyPhysicalContext::EKind::Feedback,true,
			{LinearToleranceCm,AngularToleranceDegrees},0,Locomotion,Equipment))
		{
			++ChangedBones;
		}
	}
	return ChangedBones;
}

bool AProphecyAgent::GetPhysicalFeedbackTolerance(
	FName BoneName,
	FProphecyPhysicalFeedbackToleranceSettings& Settings) const
{
	if (const FProphecyPhysicalFeedbackToleranceSettings* Found =
		PhysicalFeedbackTolerances.Find(BoneName))
	{
		Settings = *Found;
		return true;
	}
	Settings = FProphecyPhysicalFeedbackToleranceSettings{};
	return PhysicalFeedbackBoneNames().Contains(BoneName);
}

AProphecyAgent::AProphecyAgent()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	PrimaryActorTick.EndTickGroup = TG_PrePhysics;
	AutoPossessAI = EAutoPossessAI::Disabled;
	AutoPossessPlayer = EAutoReceiveInput::Disabled;
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

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
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> DefaultMesh(
		TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	if (DefaultMesh.Succeeded())
	{
		Mesh->SetSkeletalMesh(DefaultMesh.Object);
	}

	SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
	SpringArm->SetupAttachment(Capsule);
	SpringArm->SetRelativeLocation(FVector(0.0, 0.0, 29.0));
	SpringArm->SetRelativeRotation(FRotator(-12.0, 0.0, 0.0));
	SpringArm->TargetArmLength = 420.0f;
	SpringArm->bUsePawnControlRotation = false;
	SpringArm->bDoCollisionTest = true;
	SpringArm->bEnableCameraLag = false;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(SpringArm, USpringArmComponent::SocketName);
	Camera->bUsePawnControlRotation = false;
	Camera->SetFieldOfView(72.0f);

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

	static const FName DefaultMagnetizedBodies[] = {
		TEXT("pelvis"),
		TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"), TEXT("ball_l"),
		TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r")
	};
	for (const FName BoneName : DefaultMagnetizedBodies)
	{
		BodyMagnetizationSettings.Add(BoneName, FProphecyBodyMagnetizationSettings{});
	}

	ApplyCollisionMode(EProphecyAgentSimulationMode::Kinematic);
}

void AProphecyAgent::BeginPlay()
{
	Super::BeginPlay();
	if (bAutoInitializeAgentRuntime)
	{
		InitializeAgentRuntime();
	}
	if (bAutoEnsureStandaloneNNManager)
	{
		EnsureStandaloneNNManager();
	}
}

void AProphecyAgent::InitializeAgentRuntime()
{
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
	SetGeneratePhysicalHitEvents(bGeneratePhysicalHitEvents);
}

bool AProphecyAgent::EnsureStandaloneNNManager()
{
	// Placed manual agents share one runtime, whether or not they are possessed.
	// The manager discovers all opted-in placed shells before initializing lanes.
	if (!GetWorld() || (!bManualNNPoseApplication && AutoPossessPlayer == EAutoReceiveInput::Disabled))
	{
		return false;
	}

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
			Manager->PlayerAgent = AutoPossessPlayer != EAutoReceiveInput::Disabled ? this : nullptr;
			Manager->ConfigureSimpleLocomotionTest();
			Manager->FinishSpawning(FTransform::Identity);
		}
	}
	return IsValid(Manager);
}

void AProphecyAgent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (const auto* Manager=FindOwningNNManager(this))
		ProphecyAgentTime::RemoveLane(Manager,AgentHandle.Index);
	ProphecyAngularLimitBlend::Cancel(this);
	ProphecyAgentResetPhysics::Remove(this);
    ProphecyDefenseArmedGate::RemoveAgent(this);
    ProphecyDefenseControls::Remove(this);
    ProphecyPhysicalContext::Remove(this);
    ProphecyRootFacing::Explicit(this);
    ProphecyPelvisInertia::Remove(this);
    ProphecyHandInertia::Remove(this);
    ProphecyHandRecovery::Remove(this);
	if (auto* Blends = GetWorld()->GetSubsystem<UProphecyPhysicalBlendSubsystem>()) Blends->RemoveAgent(*this);
	bResumeChaosPhysicalAfterJoltRestore = false;
	bUseJoltForPhysicalMode = false;
	DisableJoltPhysicalAnimationForModeChange();
	ProphecyModeTransitions::ReleaseAgent(this);
	ReleaseAttackFists();
	ReleaseHalfSimulationState();
	ReleaseManualFollowerSubstepCallback(this);
	NNPoseDataSources.Remove(this);
	ManualFollowerAuditStates.Remove(this);
	Super::EndPlay(EndPlayReason);
}

UPoseableMeshComponent* AProphecyAgent::GetKinematicDebugMesh() const
{
	if (!bShowKinematicDebugMesh || !IsValid(Capsule) || !AgentHandle.IsValid()) return nullptr;
	const FName ExpectedName = ProphecyCrowd::KinematicDebugMeshName(AgentHandle.Index);
	for (USceneComponent* Child : Capsule->GetAttachChildren())
	{
		auto* DebugMesh = Cast<UPoseableMeshComponent>(Child);
		if (IsValid(DebugMesh) && DebugMesh->IsRegistered() && DebugMesh->GetFName() == ExpectedName
			&& IsValid(Cast<AProphecyNNLocomotionManager>(DebugMesh->GetOwner())))
		{
			return DebugMesh;
		}
	}
	return nullptr;
}

USkeletalMeshComponent* AProphecyAgent::GetPoseReferenceMesh() const
{
	if (bManualNNPoseApplication)
	{
		TInlineComponentArray<USkeletalMeshComponent*, 4> SkeletalMeshes;
		GetComponents(SkeletalMeshes);
		for (USkeletalMeshComponent* Candidate : SkeletalMeshes)
		{
			if (Candidate && Candidate != Mesh && Candidate->GetFName() == TEXT("PhysicalMesh"))
			{
				return Candidate;
			}
		}
	}
	return Mesh;
}

UProphecyNNLocomotionAnimInstance* AProphecyAgent::GetProphecyAnimInstance() const
{
	const USkeletalMeshComponent* PoseReferenceMesh = GetPoseReferenceMesh();
	return PoseReferenceMesh
		? Cast<UProphecyNNLocomotionAnimInstance>(PoseReferenceMesh->GetAnimInstance())
		: nullptr;
}

bool AProphecyAgent::PlayAnimationOverlay(
	UAnimSequenceBase* Animation,
	EProphecyAnimationOverlayMode Mode,
	float BlendSeconds,
	float PlayRate,
	bool bLoop,
	bool bRestart)
{
	UProphecyNNLocomotionAnimInstance* AnimInstance = GetProphecyAnimInstance();
	if (!AnimInstance || !Animation)
	{
		return false;
	}
	AnimInstance->OverlayAnimation = Animation;
	AnimInstance->OverlayMode = Mode;
	AnimInstance->OverlayBlendSeconds = FMath::Max(0.0f, BlendSeconds);
	AnimInstance->OverlayPlayRate = PlayRate;
	AnimInstance->bLoopOverlay = bLoop;
	AnimInstance->bOverlayEnabled = true;
	if (bRestart)
	{
		AnimInstance->RestartOverlayPlayback();
	}
	return true;
}

bool AProphecyAgent::StopAnimationOverlay(float BlendOutSeconds)
{
	UProphecyNNLocomotionAnimInstance* AnimInstance = GetProphecyAnimInstance();
	if (!AnimInstance)
	{
		return false;
	}
	AnimInstance->OverlayBlendSeconds = FMath::Max(0.0f, BlendOutSeconds);
	AnimInstance->bOverlayEnabled = false;
	return true;
}

bool AProphecyAgent::RestartAnimationOverlay()
{
	UProphecyNNLocomotionAnimInstance* AnimInstance = GetProphecyAnimInstance();
	if (!AnimInstance || !AnimInstance->OverlayAnimation)
	{
		return false;
	}
	AnimInstance->RestartOverlayPlayback();
	return true;
}

bool AProphecyAgent::PlayNNAnimationLayer(
	UAnimSequenceBase* Animation,
	FName FirstBlendedBone,
	float BlendInSeconds,
	float BlendOutSeconds,
	float PlayRate,
	bool bLoop)
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->PlayAgentAnimationLayer(
		AgentHandle,
		Animation,
		FirstBlendedBone,
		BlendInSeconds,
		BlendOutSeconds,
		PlayRate,
		bLoop);
}

bool AProphecyAgent::StopNNAnimationLayer(float BlendOutSeconds)
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->StopAgentAnimationLayer(AgentHandle, BlendOutSeconds);
}

bool AProphecyAgent::IsNNAnimationLayerActive() const
{
	float PlaybackTimeSeconds = 0.0f;
	float BlendWeight = 0.0f;
	return GetNNAnimationLayerState(PlaybackTimeSeconds, BlendWeight);
}

bool AProphecyAgent::TriggerNNAttack(FName Attack, FVector TargetWorldLocation, bool bHalfAttack, AProphecyAgent* Victim)
{
	if (Victim && (!IsValid(Victim) || Victim==this || Victim->GetWorld()!=GetWorld())) return false;
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	if (!Manager || !Manager->TriggerAgentNNAttack(AgentHandle, Attack, TargetWorldLocation, bHalfAttack)) return false;
	ProphecyDefenseArmedGate::SetVictim(this,Victim);return true;
}

AProphecyAgent* AProphecyAgent::GetNNAttackVictim() const { return ProphecyDefenseArmedGate::GetVictim(this); }
void AProphecyAgent::GetNNAttackDefenseState(bool& bBeingParried,bool& bBeingDodged) const
{
	bBeingParried=bBeingDodged=false;
	if (const auto* Manager=FindOwningNNManager(this)) Manager->GetAgentAttackDefenseState(AgentHandle,bBeingParried,bBeingDodged);
}

bool AProphecyAgent::SetNNHalfAttackEnabled(bool bEnabled)
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->SetAgentNNHalfAttack(AgentHandle, bEnabled);
}

bool AProphecyAgent::SetNNAttackTarget(FVector TargetWorldLocation)
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->SetAgentNNAttackTarget(AgentHandle, TargetWorldLocation);
}

bool AProphecyAgent::StopNNAttack()
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->StopAgentNNAttack(AgentHandle);
}

bool AProphecyAgent::GetNNAttackState(FName& Attack, bool& bHalfAttack, bool& bArmed, bool& bHit, int32& PolicyFrame) const
{
	Attack = NAME_None; bHalfAttack = bArmed = bHit = false; PolicyFrame = 0;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentNNAttackState(AgentHandle, Attack, bHalfAttack, bArmed, bHit, PolicyFrame);
}

bool AProphecyAgent::GetNNAnimationLayerState(
	float& PlaybackTimeSeconds,
	float& BlendWeight) const
{
	PlaybackTimeSeconds = 0.0f;
	BlendWeight = 0.0f;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentAnimationLayerState(
		AgentHandle,
		PlaybackTimeSeconds,
		BlendWeight);
}

void AProphecyAgent::SetNNInterpolationMode(EProphecyNNInterpolationMode Mode)
{
	if (Mode != EProphecyNNInterpolationMode::Current && Mode != EProphecyNNInterpolationMode::HermiteSlerp) return;
	NNInterpolationMode = Mode;
	if (const FNNPoseDataSource* Source = NNPoseDataSources.Find(this))
		FProphecyNNPoseStore::SetInterpolationMode(Source->AgentId, Mode);
	else if (const auto* Anim = GetProphecyAnimInstance())
		FProphecyNNPoseStore::SetInterpolationMode(Anim->AgentId, Mode);
}

void AProphecyAgent::ConfigureNNPoseDataSource(
	int32 AgentId,
	float PoseIntervalSeconds,
	bool bInterpolatePose)
{
	FNNPoseDataSource& Source = NNPoseDataSources.FindOrAdd(this);
	Source.AgentId = AgentId;
	Source.PoseIntervalSeconds = FMath::Max(0.001f, PoseIntervalSeconds);
	Source.bInterpolatePose = bInterpolatePose;
	FProphecyNNPoseStore::SetInterpolationMode(AgentId, NNInterpolationMode);
}

void AProphecyAgent::ClearNNPoseDataSource()
{
	NNPoseDataSources.Remove(this);
}

bool AProphecyAgent::GetNNPoseDataSource(
	int32& AgentId,
	float& PoseIntervalSeconds,
	bool& bInterpolatePose) const
{
	const FNNPoseDataSource* Source = NNPoseDataSources.Find(this);
	if (!Source)
	{
		AgentId = INDEX_NONE;
		PoseIntervalSeconds = 0.0f;
		bInterpolatePose = false;
		return false;
	}
	AgentId = Source->AgentId;
	PoseIntervalSeconds = Source->PoseIntervalSeconds;
	bInterpolatePose = Source->bInterpolatePose;
	return true;
}

bool AProphecyAgent::GetAuthoredBodyWorldTarget(
	FName BoneName,
	FTransform& PreviousWorldTransform,
	FTransform& CurrentWorldTransform,
	FTransform& InterpolatedWorldTransform,
	float& InterpolationAlpha) const
{
	PreviousWorldTransform = FTransform::Identity;
	CurrentWorldTransform = FTransform::Identity;
	InterpolatedWorldTransform = FTransform::Identity;
	InterpolationAlpha = 1.0f;

	const FNNPoseDataSource* DataSource = NNPoseDataSources.Find(this);
	const UProphecyNNLocomotionAnimInstance* AnimInstance = DataSource
		? nullptr
		: GetProphecyAnimInstance();
	const int32 PoseAgentId = DataSource
		? DataSource->AgentId
		: (AnimInstance ? AnimInstance->AgentId : INDEX_NONE);
	FProphecyNNPoseSnapshot Pose;
	if (PoseAgentId == INDEX_NONE || !FProphecyNNPoseStore::GetAgentLocalPose(PoseAgentId, Pose) ||
		!Pose.bHasComponentWorldTransform)
	{
		return false;
	}

	const int32 PoseIndex = Pose.BoneNames.IndexOfByKey(BoneName);
	if (!Pose.PreviousComponentTransforms.IsValidIndex(PoseIndex) ||
		!Pose.ComponentTransforms.IsValidIndex(PoseIndex))
	{
		return false;
	}

	const float PoseInterval = DataSource
		? DataSource->PoseIntervalSeconds
		: FMath::Max(0.001f, AnimInstance->NNPoseIntervalSeconds);
	const bool bInterpolate = DataSource
		? DataSource->bInterpolatePose
		: AnimInstance->bInterpolateNNPose;
	const float FrameDeltaSeconds = GetWorld() ? GetWorld()->GetDeltaSeconds() : PoseInterval;
	InterpolationAlpha = ProphecyNNPresentation::Resolve(PoseAgentId, Pose.SourceTimeSeconds,
		GetWorld() ? double(GetWorld()->GetTimeSeconds()) : Pose.SourceTimeSeconds,
		FrameDeltaSeconds, PoseInterval, bInterpolate);

	PreviousWorldTransform = Pose.PreviousComponentTransforms[PoseIndex] *
		Pose.PreviousComponentWorldTransform;
	CurrentWorldTransform = Pose.ComponentTransforms[PoseIndex] *
		Pose.ComponentWorldTransform;
	InterpolatedWorldTransform = BlendAuthoredWorldTransform(Pose, PoseIndex,
		PreviousWorldTransform, CurrentWorldTransform, InterpolationAlpha);
	// A recovery corrects the connected knee after interpolation while preserving
	// the ankle. Single-bone reads must expose the same target as full-pose users.
	if ((BoneName==TEXT("thigh_l") || BoneName==TEXT("thigh_r") ||
		BoneName==TEXT("calf_l") || BoneName==TEXT("calf_r") ||
		BoneName==TEXT("foot_l") || BoneName==TEXT("foot_r") ||
		BoneName==TEXT("ball_l") || BoneName==TEXT("ball_r"))
		&& ProphecyNNPresentation::HasRecoveryCalfLengths(PoseAgentId))
	{
		const bool Left=BoneName==TEXT("thigh_l") || BoneName==TEXT("calf_l") || BoneName==TEXT("foot_l") || BoneName==TEXT("ball_l");
		const FName Names[]={Left?TEXT("thigh_l"):TEXT("thigh_r"),Left?TEXT("calf_l"):TEXT("calf_r"),
			Left?TEXT("foot_l"):TEXT("foot_r"),Left?TEXT("ball_l"):TEXT("ball_r")};
		FTransform Transforms[4];int32 Selected=INDEX_NONE;bool Complete=true;
		for (int32 Part=0;Part<4;++Part)
		{
			const int32 Index=Pose.BoneNames.IndexOfByKey(Names[Part]);
			if (!Pose.ComponentTransforms.IsValidIndex(Index) || !Pose.PreviousComponentTransforms.IsValidIndex(Index))
			{ Complete=false;break; }
			Transforms[Part]=BlendAuthoredWorldTransform(Pose,Index,
				Pose.PreviousComponentTransforms[Index]*Pose.PreviousComponentWorldTransform,
				Pose.ComponentTransforms[Index]*Pose.ComponentWorldTransform,InterpolationAlpha);
			if (Names[Part]==BoneName) Selected=Part;
		}
		if (Complete && Selected!=INDEX_NONE)
		{
			FProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId,Pose,Names,Transforms);
			InterpolatedWorldTransform=Transforms[Selected];
			return true;
		}
	}
	if (BoneName == TEXT("hand_l") || BoneName == TEXT("hand_r"))
	{
		const FName ParentName = BoneName == TEXT("hand_l") ? TEXT("lowerarm_l") : TEXT("lowerarm_r");
		const int32 Parent = Pose.BoneNames.IndexOfByKey(ParentName);
		if (Pose.ComponentTransforms.IsValidIndex(Parent) && Pose.PreviousComponentTransforms.IsValidIndex(Parent))
		{
			const FName Names[] = { ParentName, BoneName };
			FTransform Transforms[] = { BlendAuthoredWorldTransform(Pose, Parent,
				Pose.PreviousComponentTransforms[Parent] * Pose.PreviousComponentWorldTransform,
				Pose.ComponentTransforms[Parent] * Pose.ComponentWorldTransform, InterpolationAlpha),
				InterpolatedWorldTransform };
			FProphecyNNPoseStore::ApplyRigidForearms(PoseAgentId, Pose, Names, Transforms);
			InterpolatedWorldTransform = Transforms[1];
		}
	}
	if (BoneName == TEXT("foot_l") || BoneName == TEXT("foot_r") ||
		BoneName == TEXT("ball_l") || BoneName == TEXT("ball_r"))
	{
		const bool bLeft = BoneName == TEXT("foot_l") || BoneName == TEXT("ball_l");
		const FName Names[] = { bLeft ? TEXT("calf_l") : TEXT("calf_r"),
			bLeft ? TEXT("foot_l") : TEXT("foot_r"), bLeft ? TEXT("ball_l") : TEXT("ball_r") };
		FTransform Transforms[3];
		bool bComplete = true;
		for (int32 Part = 0; Part < 3; ++Part)
		{
			const int32 Index = Pose.BoneNames.IndexOfByKey(Names[Part]);
			if (!Pose.ComponentTransforms.IsValidIndex(Index) || !Pose.PreviousComponentTransforms.IsValidIndex(Index))
			{ bComplete = false; break; }
			Transforms[Part] = BlendAuthoredWorldTransform(Pose, Index,
				Pose.PreviousComponentTransforms[Index] * Pose.PreviousComponentWorldTransform,
				Pose.ComponentTransforms[Index] * Pose.ComponentWorldTransform, InterpolationAlpha);
		}
		if (bComplete)
		{
			FProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, Names, Transforms);
			InterpolatedWorldTransform = Transforms[BoneName == Names[1] ? 1 : 2];
		}
	}
	return true;
}

void AProphecyAgent::SetAttackFootPinningIterations(int32 Iterations)
{
	AttackFootPinningIterations = FMath::Clamp(Iterations, 1, 60);
}

bool AProphecyAgent::SetFootPinningDebugEnabled(bool bEnabled)
{
	auto* Manager = FindOwningNNManager(this);
	return Manager && Manager->SetAgentFootPinningDebug(AgentHandle, bEnabled);
}

bool AProphecyAgent::GetLocomotionFootPinning(FProphecyFootPinningSample& Sample) const
{
	Sample = FProphecyFootPinningSample();
	const auto* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentFootPinning(AgentHandle, false, false, Sample);
}

bool AProphecyAgent::GetAttackFootPinning(FProphecyFootPinningSample& Sample, bool bFrozenStage) const
{
	Sample = FProphecyFootPinningSample();
	const auto* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentFootPinning(AgentHandle, true, bFrozenStage, Sample);
}

bool AProphecyAgent::SetLocomotionFootPinningThreshold(float ThresholdCm, float FadeRangeCm)
{
	if (!FMath::IsFinite(ThresholdCm) || !FMath::IsFinite(FadeRangeCm) || ThresholdCm < 0 || FadeRangeCm < 0) return false;
	bOverrideLocomotionPinThreshold = true;
	LocomotionPinThresholdM = ThresholdCm * .01f;
	LocomotionFullPinHeightM = FMath::Max(0.f, ThresholdCm-FadeRangeCm) * .01f;
	return true;
}

bool AProphecyAgent::SetAttackHandClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Attack,int32(ProphecyClampProfiles::ELimb::Hand));
	bAttackHandClamp = bEnabled;
	AttackHandClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::SetAttackFootClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Attack,int32(ProphecyClampProfiles::ELimb::Foot));
	bOverrideAttackFootClamp = true;
	bAttackFootClamp = bEnabled;
	AttackFootClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::SetAttackCalfClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Attack,int32(ProphecyClampProfiles::ELimb::Calf));
	bOverrideAttackCalfClamp = true;
	bAttackCalfClamp = bEnabled;
	AttackCalfClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::SetLocomotionPolicyBlendTimes(float WalkToRunSeconds, float RunToWalkSeconds)
{
	if (!FMath::IsFinite(WalkToRunSeconds) || !FMath::IsFinite(RunToWalkSeconds) ||
		WalkToRunSeconds < 0.f || RunToWalkSeconds < 0.f) return false;
	LocomotionWalkToRunBlendSeconds = WalkToRunSeconds;
	LocomotionRunToWalkBlendSeconds = RunToWalkSeconds;
	return true;
}

bool AProphecyAgent::SetLocomotionWalkCheckpointSpeedThreshold(float SpeedCmPerSecond)
{
	if (!FMath::IsFinite(SpeedCmPerSecond)) return false;
	LocomotionWalkCheckpointSpeedThreshold = SpeedCmPerSecond < 0.f ? -1.f : SpeedCmPerSecond;
	return true;
}

bool AProphecyAgent::GetLocomotionCheckpointWeights(float& WalkWeight, float& RunWeight) const
{
	WalkWeight = RunWeight = 0.f;
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentLocomotionCheckpointWeights(AgentHandle, WalkWeight, RunWeight);
}

bool AProphecyAgent::GetLocomotionRegionalWeights(float& PelvisWalkWeight,FVector2f& LegWalkWeights) const
{
	PelvisWalkWeight=1;LegWalkWeights=FVector2f(1,1);float Run=0;
	const auto* Manager=FindOwningNNManager(this);
	return Manager && Manager->GetAgentLocomotionCheckpointWeights(AgentHandle,PelvisWalkWeight,Run,&LegWalkWeights);
}

void AProphecyAgent::GetLocomotionPolicyBlendTimes(float& WalkToRunSeconds, float& RunToWalkSeconds) const
{
	WalkToRunSeconds = LocomotionWalkToRunBlendSeconds;
	RunToWalkSeconds = LocomotionRunToWalkBlendSeconds;
}

bool AProphecyAgent::SetLocomotionFootClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Locomotion,int32(ProphecyClampProfiles::ELimb::Foot));
	bOverrideLocomotionFootClamp = true;
	bLocomotionFootClamp = bEnabled;
	LocomotionFootClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::SetLocomotionCalfClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Locomotion,int32(ProphecyClampProfiles::ELimb::Calf));
	bOverrideLocomotionCalfClamp = true;
	bLocomotionCalfClamp = bEnabled;
	LocomotionCalfClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::SetLocomotionForearmClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Locomotion,int32(ProphecyClampProfiles::ELimb::Forearm));
	bLocomotionForearmClamp = bEnabled;
	LocomotionForearmClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::SetLocomotionHandClamp(bool bEnabled, float LeewayCm)
{
	if (!FMath::IsFinite(LeewayCm) || LeewayCm < 0) return false;
	ProphecyClampProfiles::Cancel(this,ProphecyClampProfiles::EMode::Locomotion,int32(ProphecyClampProfiles::ELimb::Hand));
	bOverrideLocomotionHandClamp = true;
	bLocomotionHandClamp = bEnabled;
	LocomotionHandClampLeewayCm = LeewayCm;
	return true;
}

bool AProphecyAgent::GetLocomotionRootWindow(TArray<FTransform>& WorldRoots, TArray<float>& TimeOffsetsSeconds) const
{
	WorldRoots.Reset(); TimeOffsetsSeconds.Reset();
	const AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager && Manager->GetAgentLocomotionRootWindow(AgentHandle, WorldRoots, TimeOffsetsSeconds);
}

UPoseableMeshComponent* AProphecyAgent::SetShowNNPreviousPoseDebugMesh(bool bEnabled, bool bPreferAttack)
{
	AProphecyNNLocomotionManager* Manager = FindOwningNNManager(this);
	return Manager ? Manager->SetAgentPreviousPoseDebug(AgentHandle, bEnabled, bPreferAttack) : nullptr;
}

void AProphecyAgent::PublishManualFollowerSubstepTargets(float DeltaSeconds)
{
	PublishManualFollowerSubstepTarget(this, FMath::Max(0.0f, DeltaSeconds));
}

void AProphecyAgent::ReleaseManualFollowerSubstepTargets()
{
	ReleaseManualFollowerSubstepCallback(this);
}

void AProphecyAgent::Tick(float DeltaSeconds)
{
	ProphecyJolt::CharacterProfiling::FScope JoltAgentTiming(ProphecyJolt::CharacterProfiling::EPhase::AgentTick);
	const bool bAuditManualFollower =
		CVarProphecyAuditManualPhysicalFollower.GetValueOnGameThread() != 0;
	if (bAuditManualFollower)
	{
		// This is deliberately before Super: Blueprint ReceiveTick has not authored
		// a new target yet, so the comparison closes the preceding Chaos step.
		AuditManualPhysicalFollowerBeforeTick(this);
	}

	Super::Tick(DeltaSeconds);
	ProphecyPhysicalContext::Update(this);
	{
		ProphecyJolt::CharacterProfiling::FScope JoltFistTiming(ProphecyJolt::CharacterProfiling::EPhase::EnsureFists);
		ProphecyAttackFists::EnsureManualSimulation(this);
	}
	if (bPendingHalfSimulation) EnterHalfSimulation();

	if (bManualNNPoseApplication && bAutoPublishManualFollowerSubstepTargets &&
		SimulationMode != EProphecyAgentSimulationMode::HalfSim)
	{
		// Blueprint has finalized this frame's data-only kinematic target. Publish it
		// now so every Chaos substep in the same frame converges to that same instant.
		PublishManualFollowerSubstepTarget(this, DeltaSeconds);
	}

	if (bAuditManualFollower)
	{
		// ReceiveTick has now evaluated the NN endpoint and applied this step's
		// velocity correction. Save the exact endpoint for next PrePhysics tick.
		CaptureManualPhysicalFollowerEndpointAfterTick(this, DeltaSeconds);
	}
	if (SimulationMode == EProphecyAgentSimulationMode::Physical &&
		PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque &&
		bAutoApplyWorldMagnetization && !IsJoltPhysicalAnimationEnabled())
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
	FProphecyNNPoseSnapshot SourceSnapshot;
	return ReadNNFutureWorldPoseWithSnapshot(BoneNames, FutureWorldTransforms,
		InterpolatedWorldTransforms, InterpolationAlpha, SourceSnapshot);
}

bool AProphecyAgent::ReadNNFutureWorldPoseWithSnapshot(TArray<FName>& BoneNames,
	TArray<FTransform>& FutureWorldTransforms, TArray<FTransform>& InterpolatedWorldTransforms,
	float& InterpolationAlpha, FProphecyNNPoseSnapshot& Pose) const
{
	BoneNames.Reset();
	FutureWorldTransforms.Reset();
	InterpolatedWorldTransforms.Reset();
	InterpolationAlpha = 1.0f;

	const FNNPoseDataSource* DataSource = NNPoseDataSources.Find(this);
	const UProphecyNNLocomotionAnimInstance* AnimInstance = DataSource
		? nullptr
		: Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance());
	const int32 PoseAgentId = DataSource ? DataSource->AgentId : (AnimInstance ? AnimInstance->AgentId : INDEX_NONE);
	if (PoseAgentId == INDEX_NONE || !FProphecyNNPoseStore::GetAgentLocalPose(PoseAgentId, Pose) ||
		!Pose.bHasComponentWorldTransform ||
		Pose.PreviousComponentTransforms.Num() != Pose.BoneNames.Num() ||
		Pose.ComponentTransforms.Num() != Pose.BoneNames.Num())
	{
		return false;
	}

	const float PoseInterval = DataSource
		? DataSource->PoseIntervalSeconds
		: FMath::Max(0.001f, AnimInstance->NNPoseIntervalSeconds);
	const float FrameDeltaSeconds = GetWorld() ? GetWorld()->GetDeltaSeconds() : PoseInterval;
	const bool bInterpolatePose = DataSource ? DataSource->bInterpolatePose : AnimInstance->bInterpolateNNPose;
	InterpolationAlpha = ProphecyNNPresentation::Resolve(PoseAgentId, Pose.SourceTimeSeconds,
		GetWorld() ? double(GetWorld()->GetTimeSeconds()) : Pose.SourceTimeSeconds,
		FrameDeltaSeconds, PoseInterval, bInterpolatePose);

	const bool bPhysicalFollowerData = bManualNNPoseApplication && DataSource;
	if (bPhysicalFollowerData)
	{
		const USkeletalMeshComponent* PoseReferenceMesh = GetPoseReferenceMesh();
		const USkeletalMesh* SkeletalMesh = PoseReferenceMesh
			? PoseReferenceMesh->GetSkeletalMeshAsset()
			: nullptr;
		const UPhysicsAsset* PhysicsAsset = PoseReferenceMesh
			? PoseReferenceMesh->GetPhysicsAsset()
			: nullptr;
		if (!SkeletalMesh || !PhysicsAsset)
		{
			return false;
		}

		if (!ProphecyNNPhysicalTargets::BuildWorldPoses(*SkeletalMesh, *PhysicsAsset, Pose,
			BoneNames, FutureWorldTransforms, InterpolatedWorldTransforms))
		{
			return false;
		}
		for (int32 Index = 0; Index < BoneNames.Num(); ++Index)
		{
			InterpolatedWorldTransforms[Index] = BlendAuthoredWorldTransform(Pose,
				Pose.InterpolationMode == EProphecyNNInterpolationMode::HermiteSlerp ? Pose.BoneNames.IndexOfByKey(BoneNames[Index]) : INDEX_NONE,
				InterpolatedWorldTransforms[Index], FutureWorldTransforms[Index], InterpolationAlpha);
		}
		FProphecyNNPoseStore::ApplyRigidForearms(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);
		FProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);
		return BoneNames.Num() > 0;
	}

	BoneNames.Reserve(Pose.BoneNames.Num());
	FutureWorldTransforms.Reserve(Pose.BoneNames.Num());
	InterpolatedWorldTransforms.Reserve(Pose.BoneNames.Num());
	for (int32 Index = 0; Index < Pose.BoneNames.Num(); ++Index)
	{
		const FTransform PreviousWorld = Pose.PreviousComponentTransforms[Index] *
			Pose.PreviousComponentWorldTransform;
		const FTransform FutureWorld = Pose.ComponentTransforms[Index] *
			Pose.ComponentWorldTransform;
		BoneNames.Add(Pose.BoneNames[Index]);
		FutureWorldTransforms.Add(FutureWorld);
		InterpolatedWorldTransforms.Add(BlendAuthoredWorldTransform(Pose, Index,
			PreviousWorld, FutureWorld, InterpolationAlpha));
	}
	FProphecyNNPoseStore::ApplyRigidForearms(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);
	FProphecyNNPoseStore::ApplyRigidCalves(PoseAgentId, Pose, BoneNames, InterpolatedWorldTransforms);
	return true;
}

bool AProphecyAgent::ApplyNNPoseKinematically(float DeltaSeconds)
{
	if (IsJoltPhysicalAnimationEnabled()) return true;
	// Half Sim evaluates once on the mesh's PrePhysics tick, before native drives.
	if (SimulationMode == EProphecyAgentSimulationMode::HalfSim) return true;
	USkeletalMeshComponent* PoseReferenceMesh = GetPoseReferenceMesh();
	if (!PoseReferenceMesh || !PoseReferenceMesh->GetSkeletalMeshAsset() ||
		!Cast<UProphecyNNLocomotionAnimInstance>(PoseReferenceMesh->GetAnimInstance()))
	{
		return false;
	}

	PoseReferenceMesh->TickAnimation(FMath::Max(0.0f, DeltaSeconds), false);
	PoseReferenceMesh->RefreshBoneTransforms();
	return true;
}

EProphecyAgentSimulationMode AProphecyAgent::GetSimulationMode() const
{
	if (IsJoltPhysicalAnimationEnabled()) return EProphecyAgentSimulationMode::Physical;
	if (SimulationMode == EProphecyAgentSimulationMode::HalfSim) return SimulationMode;
	const USkeletalMeshComponent* PoseReferenceMesh = GetPoseReferenceMesh();
	if (bManualNNPoseApplication && PoseReferenceMesh && PoseReferenceMesh != Mesh &&
		PoseReferenceMesh->IsAnySimulatingPhysics())
	{
		return EProphecyAgentSimulationMode::Physical;
	}
	return SimulationMode;
}

void AProphecyAgent::ConfigureRootAndJointTorquePhysics(
	USkeletalMeshComponent* InPhysicalMesh,
	UPhysicsAsset* PhysicsAsset)
{
	if (!InPhysicalMesh || !PhysicsAsset)
	{
		return;
	}

	for (const USkeletalBodySetup* BodySetup : PhysicsAsset->SkeletalBodySetups)
	{
		if (!BodySetup || IsBodyConfiguredForSimulation(BodySetup->BoneName))
		{
			continue;
		}
		InPhysicalMesh->SetBodySimulatePhysics(BodySetup->BoneName, false);
		if (FBodyInstance* Body = InPhysicalMesh->GetBodyInstance(BodySetup->BoneName))
		{
			Body->PhysicsBlendWeight = 0.0f;
		}
	}
	ApplyPhysicalSolverSettings();
	for (FConstraintInstance* Constraint : InPhysicalMesh->Constraints)
	{
		if (!Constraint)
		{
			continue;
		}
		const FName ChildBone = Constraint->ConstraintBone1;
		const bool bDrivenConstraint = IsBodyConfiguredForSimulation(ChildBone) &&
			ChildBone != PhysicalRootBodyName;
		if (!bDrivenConstraint)
		{
			Constraint->TermConstraint();
			continue;
		}
		const float AngularLimit = FMath::Clamp(PhysicalAngularLimitDegrees, 0.0f, 179.0f);
		Constraint->SetAngularSwing1Limit(ACM_Limited, AngularLimit);
		Constraint->SetAngularSwing2Limit(ACM_Limited, AngularLimit);
		Constraint->SetAngularTwistLimit(ACM_Limited, AngularLimit);
		if (bEnablePhysicalMassConditioning)
		{
			Constraint->EnableMassConditioning();
		}
		else
		{
			Constraint->DisableMassConditioning();
		}
		Constraint->SetOrientationDriveSLERP(false);
		Constraint->SetAngularVelocityDriveSLERP(false);
	}
	if (bDisablePhysicalConstraintMotors)
	{
		InPhysicalMesh->SetAllMotorsAngularPositionDrive(false, false, false);
		InPhysicalMesh->SetAllMotorsAngularVelocityDrive(false, false, false);
	}
	// Constraints retain articulation and impact propagation. Absolute-world
	// magnetization, not a constraint motor, tracks the authored pose.
	InPhysicalMesh->bUpdateJointsFromAnimation = bUpdatePhysicalJointsFromAnimation;
}

bool AProphecyAgent::SetSimulationMode(EProphecyAgentSimulationMode NewMode)
{
    if (!IsInGameThread() || IsActorBeingDestroyed()) return false;
    // An explicit later mode request wins over an in-flight backend restoration.
    bResumeChaosPhysicalAfterJoltRestore = false;
    // Finish ordinary body/pose restoration before Jolt captures a HalfSim-to-Sim handoff.
    // Read the choice afterwards so an explicit Disable from a transition callback still wins.
    if (!SetSimulationModeInternal(NewMode)) return false;
    if (NewMode == EProphecyAgentSimulationMode::Physical && bUseJoltForPhysicalMode
        && !IsJoltPhysicalAnimationEnabled())
    {
        if (GetSimulationMode() != EProphecyAgentSimulationMode::Physical) return false;
        return EnableJoltPhysicalAnimation();
    }
    return true;
}

bool AProphecyAgent::SetSimulationModeInternal(EProphecyAgentSimulationMode NewMode)
{
    if (JoltCharacter && JoltCharacter->IsKinematicRestorePending())
    {
        // A finalization callback can request another mode before the detached Jolt mesh is restored.
        // Preserve the accepted kinematic transition until that same call boundary has unwound.
        if (NewMode != EProphecyAgentSimulationMode::Kinematic) return false;
        SimulationMode = EProphecyAgentSimulationMode::Kinematic;
        return true;
    }
    if (JoltCharacter && JoltCharacter->IsEnablePending()
        && (NewMode == EProphecyAgentSimulationMode::Kinematic || NewMode == EProphecyAgentSimulationMode::HalfSim))
    {
        // A queued handoff must not reactivate Jolt after a later explicit mode request.
        JoltCharacter->DisablePhysicalAnimation();
    }
	if (IsJoltPhysicalAnimationEnabled())
	{
		if (NewMode == EProphecyAgentSimulationMode::Physical) return true;
		if (NewMode == EProphecyAgentSimulationMode::Kinematic)
		{
			DisableJoltPhysicalAnimationForModeChange();
			return true;
		}
		UE_LOG(LogProphecyAgentPhysical, Warning, TEXT("Half Sim is not yet connected to the opt-in Jolt character binding."));
		return false;
	}
	ProphecyModeTransitions::FScope Transition(this);
	if (NewMode != EProphecyAgentSimulationMode::Kinematic &&
		NewMode != EProphecyAgentSimulationMode::Physical &&
		NewMode != EProphecyAgentSimulationMode::HalfSim) return false;
	bPendingHalfSimulation = false;
	const EProphecyAgentSimulationMode CurrentMode = GetSimulationMode();
	if (NewMode == CurrentMode)
	{
		SimulationMode = CurrentMode;
		return true;
	}
	if (NewMode == EProphecyAgentSimulationMode::HalfSim)
	{
		USkeletalMeshComponent* TargetMesh = GetPoseReferenceMesh();
		if (!TargetMesh || !TargetMesh->GetSkeletalMeshAsset() || !TargetMesh->GetPhysicsAsset() ||
			TargetMesh->GetPhysicsAsset()->FindBodyIndex(PhysicalRootBodyName) == INDEX_NONE) return false;
		// Blueprint BeginPlay precedes standalone manager initialization.
		bPendingHalfSimulation = !EnterHalfSimulation();
		SetActorTickEnabled(true);
		return true;
	}
	if (CurrentMode == EProphecyAgentSimulationMode::HalfSim) return LeaveHalfSimulation(NewMode);

	USkeletalMeshComponent* PoseReferenceMesh = GetPoseReferenceMesh();
	if (bManualNNPoseApplication && PoseReferenceMesh && PoseReferenceMesh != Mesh)
	{
		if (!PoseReferenceMesh->GetSkeletalMeshAsset() || !PoseReferenceMesh->GetPhysicsAsset())
		{
			return false;
		}
		if (NewMode == EProphecyAgentSimulationMode::Physical)
		{
			PoseReferenceMesh->TickAnimation(0.0f, false);
			PoseReferenceMesh->RefreshBoneTransforms();
			PhysicalTargetComponentRelativeTransform = PoseReferenceMesh->GetRelativeTransform();
			PoseReferenceMesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, true, true);
			PoseReferenceMesh->SetAllBodiesBelowPhysicsBlendWeight(
				PhysicalRootBodyName, 1.0f, false, true);
			PoseReferenceMesh->SetAnimInstanceClass(nullptr);
			PoseReferenceMesh->WakeAllRigidBodies();
			SetMACDEnabled(bMACDEnabled);
			ApplyPhysicalSolverSettings();
		}
		else
		{
			ReleaseManualFollowerSubstepCallback(this);
			PoseReferenceMesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, false, true);
			PoseReferenceMesh->SetAllBodiesBelowPhysicsBlendWeight(
				PhysicalRootBodyName, 0.0f, false, true);
			PoseReferenceMesh->SetRelativeTransform(
				Mesh->GetRelativeTransform(),
				false,
				nullptr,
				ETeleportType::TeleportPhysics);
			PoseReferenceMesh->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
			if (UProphecyNNLocomotionAnimInstance* AnimInstance =
				Cast<UProphecyNNLocomotionAnimInstance>(PoseReferenceMesh->GetAnimInstance()))
			{
				int32 PoseAgentId = INDEX_NONE;
				float PoseIntervalSeconds = 1.0f / 30.0f;
				bool bInterpolatePose = true;
				if (GetNNPoseDataSource(PoseAgentId, PoseIntervalSeconds, bInterpolatePose))
				{
					AnimInstance->AgentId = PoseAgentId;
					AnimInstance->NNPoseIntervalSeconds = PoseIntervalSeconds;
					AnimInstance->bInterpolateNNPose = bInterpolatePose;
				}
			}
			PoseReferenceMesh->TickAnimation(0.0f, false);
			PoseReferenceMesh->RefreshBoneTransforms();
		}
		SimulationMode = NewMode;
		SetActorTickEnabled(true);
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
			ConfigureRootAndJointTorquePhysics(Mesh, PhysicsAsset);
		}
		else
		{
			Mesh->bUpdateJointsFromAnimation = bUpdatePhysicalJointsFromAnimation;
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

bool AProphecyAgent::MySetPhysicsAsset(UPhysicsAsset* NewPhysicsAsset)
{
	if (IsJoltPhysicalAnimationEnabled())
	{
		UE_LOG(LogProphecyAgentPhysical, Warning, TEXT("Disable the opt-in Jolt binding before replacing its Physics Asset."));
		return false;
	}
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	if (!PhysicalMesh || !PhysicalMesh->GetSkeletalMeshAsset() || !NewPhysicsAsset ||
		NewPhysicsAsset->FindBodyIndex(PhysicalRootBodyName) == INDEX_NONE)
	{
		return false;
	}

	struct FBodyRuntimeState
	{
		FName BoneName = NAME_None;
		FTransform WorldTransform = FTransform::Identity;
		FVector LinearVelocity = FVector::ZeroVector;
		FVector AngularVelocity = FVector::ZeroVector;
		float PhysicsBlendWeight = 0.0f;
		bool bSimulating = false;
		bool bGravityEnabled = false;
		bool bAwake = false;
	};

	TArray<FBodyRuntimeState, TInlineAllocator<32>> SavedBodies;
	SavedBodies.Reserve(PhysicalMesh->Bodies.Num());
	for (FBodyInstance* Body : PhysicalMesh->Bodies)
	{
		const UBodySetupCore* BodySetup = Body ? Body->BodySetup.Get() : nullptr;
		if (!Body || !BodySetup || !Body->IsValidBodyInstance())
		{
			continue;
		}
		FBodyRuntimeState& Saved = SavedBodies.AddDefaulted_GetRef();
		Saved.BoneName = BodySetup->BoneName;
		Saved.WorldTransform = Body->GetUnrealWorldTransform();
		Saved.LinearVelocity = Body->GetUnrealWorldVelocity();
		Saved.AngularVelocity = Body->GetUnrealWorldAngularVelocityInRadians();
		Saved.PhysicsBlendWeight = Body->PhysicsBlendWeight;
		Saved.bSimulating = Body->IsInstanceSimulatingPhysics();
		Saved.bGravityEnabled = Body->bEnableGravity;
		Saved.bAwake = Saved.bSimulating && Body->IsInstanceAwake();
	}

	const EProphecyAgentSimulationMode CurrentMode = GetSimulationMode();
	const bool bWasPhysical = CurrentMode != EProphecyAgentSimulationMode::Kinematic;
	const bool bWasHalfSim = CurrentMode == EProphecyAgentSimulationMode::HalfSim;
	const bool bUsesSeparateManualMesh = bManualNNPoseApplication && PhysicalMesh != Mesh;
	ReleaseManualFollowerSubstepCallback(this);
	ManualFollowerAuditStates.Remove(this);

	// UE tears down and recreates the entire articulation here, even when the
	// requested asset is the current one. Everything below restores runtime state.
	PhysicalMesh->SetPhysicsAsset(NewPhysicsAsset, true);
	if (PhysicalMesh->GetPhysicsAsset() != NewPhysicsAsset)
	{
		return false;
	}

	if (!bWasHalfSim) ApplyCollisionMode(CurrentMode);
	PhysicalMesh->SetNotifyRigidBodyCollision(bWasPhysical && bGeneratePhysicalHitEvents);
	if (bWasHalfSim)
	{
		RefreshHalfSimulationDrives();
	}
	else if (bWasPhysical && !bUsesSeparateManualMesh)
	{
		if (PhysicalAnimation->GetSkeletalMesh() != PhysicalMesh)
		{
			PhysicalAnimation->SetSkeletalMeshComponent(PhysicalMesh);
		}
		PhysicalMesh->SetAllBodiesBelowSimulatePhysics(PhysicalRootBodyName, true, true);
		PhysicalMesh->SetAllBodiesBelowPhysicsBlendWeight(
			PhysicalRootBodyName, 1.0f, false, true);
		if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque)
		{
			ConfigureRootAndJointTorquePhysics(PhysicalMesh, NewPhysicsAsset);
			PhysicalAnimation->SetStrengthMultiplyer(0.0f);
			PhysicalAnimation->SetComponentTickEnabled(false);
		}
		else
		{
			PhysicalAnimation->ApplyPhysicalAnimationSettingsBelow(
				PhysicalRootBodyName,
				PhysicalDriveSettings,
				true);
			PhysicalAnimation->SetStrengthMultiplyer(PhysicalDriveStrengthMultiplier);
			PhysicalAnimation->SetComponentTickEnabled(true);
		}
		bPhysicalDriveConfigured = true;
	}

	for (const FBodyRuntimeState& Saved : SavedBodies)
	{
		FBodyInstance* Body = PhysicalMesh->GetBodyInstance(Saved.BoneName);
		if (!Body || !Body->IsValidBodyInstance())
		{
			continue;
		}
		Body->SetInstanceSimulatePhysics(Saved.bSimulating, true, true);
		Body->PhysicsBlendWeight = Saved.PhysicsBlendWeight;
		Body->SetBodyTransform(Saved.WorldTransform, ETeleportType::TeleportPhysics, false);
		Body->SetEnableGravity(Saved.bGravityEnabled);
		if (Saved.bSimulating)
		{
			Body->SetLinearVelocity(Saved.LinearVelocity, false, false);
			Body->SetAngularVelocityInRadians(Saved.AngularVelocity, false, false);
			if (Saved.bAwake)
			{
				Body->WakeInstance();
			}
			else
			{
				Body->PutInstanceToSleep();
			}
		}
	}

	SetMACDEnabled(bMACDEnabled);
	ApplyPhysicalSolverSettings();
	if (bWasPhysical && bUsesSeparateManualMesh && bAutoPublishManualFollowerSubstepTargets)
	{
		PublishManualFollowerSubstepTarget(
			this,
			GetWorld() ? FMath::Max(GetWorld()->GetDeltaSeconds(), 1.0f / 120.0f) : 1.0f / 60.0f);
	}
	return true;
}

void AProphecyAgent::ApplyAbsoluteWorldMagnetization(float DeltaSeconds)
{
	if (SimulationMode == EProphecyAgentSimulationMode::HalfSim) return;
	if (!bWorldMagnetizationEnabled || DeltaSeconds <= UE_SMALL_NUMBER || !Mesh->GetSkeletalMeshAsset())
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
	const float PoseAlpha = ProphecyNNPresentation::Resolve(AnimInstance->AgentId, AuthoredPose.SourceTimeSeconds,
		GetWorld() ? double(GetWorld()->GetTimeSeconds()) : AuthoredPose.SourceTimeSeconds,
		GetWorld() ? DeltaSeconds : PoseInterval, PoseInterval, AnimInstance->bInterpolateNNPose);

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
		const FProphecyBodyMagnetizationSettings* BodySettings = BodySetup
			? BodyMagnetizationSettings.Find(BodySetup->BoneName)
			: nullptr;
		if (!Body || !Body->IsInstanceSimulatingPhysics() || !BodySetup ||
			!BodySettings || !BodySettings->bSimulateBody || !BodySettings->bMagnetizationEnabled)
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
		FTransform BodyTarget = BlendAuthoredWorldTransform(AuthoredPose, PoseIndex,
			PreviousBodyTarget, CurrentBodyTarget, PoseAlpha);
		if (AuthoredPose.ForearmClamp.bEnabled && (BodySetup->BoneName == TEXT("hand_l") || BodySetup->BoneName == TEXT("hand_r")))
		{
			const bool bLeft = BodySetup->BoneName == TEXT("hand_l");
			const int32 Parent = AuthoredPose.BoneNames.IndexOfByKey(bLeft ? FName(TEXT("lowerarm_l")) : FName(TEXT("lowerarm_r")));
			if (AuthoredPose.ComponentTransforms.IsValidIndex(Parent) && AuthoredPose.PreviousComponentTransforms.IsValidIndex(Parent))
			{
				const FTransform Forearm = BlendAuthoredWorldTransform(AuthoredPose, Parent,
					AuthoredPose.PreviousComponentTransforms[Parent] * AuthoredPose.PreviousComponentWorldTransform,
					AuthoredPose.ComponentTransforms[Parent] * AuthoredPose.ComponentWorldTransform, PoseAlpha);
				BodyTarget.SetTranslation(AuthoredPose.ForearmClamp.ClampHand(BodyTarget.GetTranslation(), Forearm,
					AuthoredPose.LocalTransforms[PoseIndex].GetTranslation(), bLeft ? 0 : 1));
			}
		}
		const FTransform ActualBody = Body->GetUnrealWorldTransform();

		ApplyBodyWorldMagnetization(
			BodySetup->BoneName,
			BodyTarget,
			DeltaSeconds,
			WorldMagnetizationLinearStrengthScale * BodySettings->LinearStrengthScale,
			WorldMagnetizationAngularStrengthScale * BodySettings->AngularStrengthScale,
			BodySettings->bCancelGravity);

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

	PreviousPhysicalRootTarget = BlendAuthoredWorldTransform(AuthoredPose, PelvisPoseIndex,
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

bool AProphecyAgent::ApplyPhysicalDriveSettingsNow()
{
	if (SimulationMode == EProphecyAgentSimulationMode::HalfSim) return RefreshHalfSimulationDrives();
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	if (!PhysicalAnimation || !PhysicalMesh || !PhysicalMesh->GetPhysicsAsset() ||
		PhysicalMesh->GetPhysicsAsset()->FindBodyIndex(PhysicalRootBodyName) == INDEX_NONE)
	{
		return false;
	}
	PhysicalAnimation->SetSkeletalMeshComponent(PhysicalMesh);
	if (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::PerBodyWorld)
	{
		PhysicalAnimation->ApplyPhysicalAnimationSettingsBelow(
			PhysicalRootBodyName,
			PhysicalDriveSettings,
			true);
		PhysicalAnimation->SetStrengthMultiplyer(PhysicalDriveStrengthMultiplier);
		PhysicalAnimation->SetComponentTickEnabled(
			SimulationMode == EProphecyAgentSimulationMode::Physical);
	}
	else
	{
		PhysicalAnimation->SetStrengthMultiplyer(0.0f);
		PhysicalAnimation->SetComponentTickEnabled(false);
	}
	bPhysicalDriveConfigured = true;
	return true;
}

void AProphecyAgent::SetPhysicalDriveStrengthMultiplier(float NewMultiplier)
{
	PhysicalDriveStrengthMultiplier = FMath::Max(0.0f, NewMultiplier);
	if (SimulationMode == EProphecyAgentSimulationMode::HalfSim)
		if (auto* Driver = FindComponentByClass<UProphecyHalfSimDriveComponent>()) Driver->SetStrength(PhysicalDriveStrengthMultiplier);
	if (PhysicalAnimation && (PhysicalDriveMode == EProphecyAgentPhysicalDriveMode::PerBodyWorld ||
		SimulationMode == EProphecyAgentSimulationMode::HalfSim))
	{
		PhysicalAnimation->SetStrengthMultiplyer(PhysicalDriveStrengthMultiplier);
	}
}

void AProphecyAgent::SetGeneratePhysicalHitEvents(bool bEnabled)
{
	bGeneratePhysicalHitEvents = bEnabled;
	if (JoltCharacter) JoltCharacter->SetHitEventsEnabled(bEnabled);
	if (USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh())
	{
		if (Mesh && Mesh != PhysicalMesh) Mesh->OnComponentHit.RemoveDynamic(this, &AProphecyAgent::HandleMeshHit);
		PhysicalMesh->OnComponentHit.AddUniqueDynamic(this, &AProphecyAgent::HandleMeshHit);
		PhysicalMesh->SetNotifyRigidBodyCollision(
			bEnabled && GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic);
	}
}

void AProphecyAgent::ApplyPhysicalSolverSettings()
{
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	if (!PhysicalMesh)
	{
		return;
	}
	for (FBodyInstance* Body : PhysicalMesh->Bodies)
	{
		if (!Body || !Body->IsValidBodyInstance())
		{
			continue;
		}
		FPhysicsCommand::ExecuteWrite(Body->GetPhysicsActor(), [this](const FPhysicsActorHandle& Actor)
		{
			FChaosEngineInterface::SetPositionSolverIterationCount_AssumesLocked(
				Actor, FMath::Max(1, PhysicalPositionSolverIterations));
			FChaosEngineInterface::SetVelocitySolverIterationCount_AssumesLocked(
				Actor, FMath::Max(1, PhysicalVelocitySolverIterations));
			FChaosEngineInterface::SetProjectionSolverIterationCount_AssumesLocked(
				Actor, FMath::Max(0, PhysicalProjectionSolverIterations));
		});
	}
}

void AProphecyAgent::ApplyAgentCollisionMode(EProphecyAgentSimulationMode Mode)
{
	if (IsJoltPhysicalAnimationEnabled()) return; // The live binding owns QueryOnly presentation.
	ApplyCollisionMode(Mode);
}

bool AProphecyAgent::SetPhysicalBodySimulating(FName BoneName, bool bSimulate, bool bWake)
{
	if (IsJoltPhysicalAnimationEnabled())
	{
		UE_LOG(LogProphecyAgentPhysical, Warning, TEXT("Per-body simulation changes are not yet connected to the Jolt binding; disable the binding before changing solver ownership."));
		return false;
	}
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	FBodyInstance* Body = PhysicalMesh ? PhysicalMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Body)
	{
		return false;
	}
	PhysicalMesh->SetBodySimulatePhysics(BoneName, bSimulate);
	if (bSimulate && bWake)
	{
		Body = PhysicalMesh->GetBodyInstance(BoneName);
		if (Body)
		{
			Body->WakeInstance();
		}
	}
	return true;
}

bool AProphecyAgent::SetPhysicalBodyGravityEnabled(FName BoneName, bool bEnabled)
{
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	FBodyInstance* Body = PhysicalMesh ? PhysicalMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Body)
	{
		return false;
	}
	Body->SetEnableGravity(bEnabled);
	return true;
}

bool AProphecyAgent::WakePhysicalBody(FName BoneName)
{
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	FBodyInstance* Body = PhysicalMesh ? PhysicalMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Body)
	{
		return false;
	}
	Body->WakeInstance();
	return true;
}

void AProphecyAgent::WakeAllPhysicalBodies()
{
	if (USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh())
	{
		PhysicalMesh->WakeAllRigidBodies();
	}
}

bool AProphecyAgent::ClearPhysicalBodyForces(FName BoneName)
{
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	FBodyInstance* Body = PhysicalMesh ? PhysicalMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Body)
	{
		return false;
	}
	Body->ClearForces(false);
	Body->ClearTorques(false);
	return true;
}

bool AProphecyAgent::GetPhysicalBodyState(
	FName BoneName,
	FTransform& WorldTransform,
	FVector& LinearVelocityCmPerSecond,
	FVector& AngularVelocityRadiansPerSecond,
	bool& bIsSimulating) const
{
	if (IsJoltPhysicalAnimationEnabled())
		return JoltCharacter->GetBodyState(BoneName, WorldTransform, LinearVelocityCmPerSecond, AngularVelocityRadiansPerSecond, bIsSimulating);
	WorldTransform = FTransform::Identity;
	LinearVelocityCmPerSecond = FVector::ZeroVector;
	AngularVelocityRadiansPerSecond = FVector::ZeroVector;
	bIsSimulating = false;
	const USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	FBodyInstance* Body = PhysicalMesh ? PhysicalMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Body)
	{
		return false;
	}
	WorldTransform = Body->GetUnrealWorldTransform();
	LinearVelocityCmPerSecond = Body->GetUnrealWorldVelocity();
	AngularVelocityRadiansPerSecond = Body->GetUnrealWorldAngularVelocityInRadians();
	bIsSimulating = Body->IsInstanceSimulatingPhysics();
	return true;
}

bool AProphecyAgent::IsBodyConfiguredForSimulation(FName BoneName) const
{
	const FProphecyBodyMagnetizationSettings* Settings = BodyMagnetizationSettings.Find(BoneName);
	return Settings && Settings->bSimulateBody;
}

void AProphecyAgent::SetAllBodyMagnetization(
	bool bEnabled,
	float LinearStrengthScale,
	float AngularStrengthScale)
{
	ProphecyPhysicalContext::Discard(this,ProphecyPhysicalContext::EKind::Magnetization);
	CancelBodyMagnetizationBlend();
	const USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	const UPhysicsAsset* PhysicsAsset = PhysicalMesh ? PhysicalMesh->GetPhysicsAsset() : nullptr;
	if (PhysicsAsset)
	{
		for (const USkeletalBodySetup* BodySetup : PhysicsAsset->SkeletalBodySetups)
		{
			if (BodySetup)
			{
				BodyMagnetizationSettings.FindOrAdd(BodySetup->BoneName);
			}
		}
	}
	for (TPair<FName, FProphecyBodyMagnetizationSettings>& Pair : BodyMagnetizationSettings)
	{
		if (ProphecyPhysicalContext::IsManaged(this,Pair.Key,ProphecyPhysicalContext::EKind::Magnetization))
		{
			ProphecyPhysicalContext::Set(*this,Pair.Key,ProphecyPhysicalContext::EKind::Magnetization,bEnabled,
				{LinearStrengthScale,AngularStrengthScale},0);
			continue;
		}
		Pair.Value.bMagnetizationEnabled = bEnabled;
		Pair.Value.LinearStrengthScale = FMath::Max(0.0f, LinearStrengthScale);
		Pair.Value.AngularStrengthScale = FMath::Max(0.0f, AngularStrengthScale);
		ApplyHalfSimulationBodyStrength(Pair.Key);
	}
}

void AProphecyAgent::SetBodyMagnetization(
	FName BoneName,
	bool bEnabled,
	float LinearStrengthScale,
	float AngularStrengthScale,EProphecyLocomotionSelection Locomotion,EProphecyEquipmentSelection Equipment)
{
	if (Locomotion!=EProphecyLocomotionSelection::Both || Equipment!=EProphecyEquipmentSelection::Both
		|| ProphecyPhysicalContext::IsManaged(this,BoneName,ProphecyPhysicalContext::EKind::Magnetization))
	{
		ProphecyPhysicalContext::Set(*this,BoneName,ProphecyPhysicalContext::EKind::Magnetization,bEnabled,
			{LinearStrengthScale,AngularStrengthScale},0,Locomotion,Equipment);
		return;
	}
	CancelBodyMagnetizationBlend(BoneName);
	FProphecyBodyMagnetizationSettings& Settings = BodyMagnetizationSettings.FindOrAdd(BoneName);
	Settings.bMagnetizationEnabled = bEnabled;
	Settings.LinearStrengthScale = FMath::Max(0.0f, LinearStrengthScale);
	Settings.AngularStrengthScale = FMath::Max(0.0f, AngularStrengthScale);
	ApplyHalfSimulationBodyStrength(BoneName);
}

int32 AProphecyAgent::SetBodyMagnetizationBelow(
	FName ParentBone,
	bool bIncludeParent,
	bool bEnabled,
	float LinearStrengthScale,
	float AngularStrengthScale,EProphecyLocomotionSelection Locomotion,EProphecyEquipmentSelection Equipment)
{
	if (!ProphecyPhysicalContext::Valid(Locomotion,Equipment)) return 0;
	const USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	const USkeletalMesh* SkeletalMesh = PhysicalMesh ? PhysicalMesh->GetSkeletalMeshAsset() : nullptr;
	const UPhysicsAsset* PhysicsAsset = PhysicalMesh ? PhysicalMesh->GetPhysicsAsset() : nullptr;
	if (!SkeletalMesh || !PhysicsAsset)
	{
		return 0;
	}
	const FReferenceSkeleton& ReferenceSkeleton = SkeletalMesh->GetRefSkeleton();
	const int32 ParentIndex = ReferenceSkeleton.FindBoneIndex(ParentBone);
	if (ParentIndex == INDEX_NONE)
	{
		return 0;
	}

	int32 ChangedBodies = 0;
	for (const USkeletalBodySetup* BodySetup : PhysicsAsset->SkeletalBodySetups)
	{
		if (!BodySetup)
		{
			continue;
		}
		int32 BoneIndex = ReferenceSkeleton.FindBoneIndex(BodySetup->BoneName);
		const bool bIsParent = BoneIndex == ParentIndex;
		bool bIsBelow = false;
		while (BoneIndex != INDEX_NONE && BoneIndex != 0)
		{
			BoneIndex = ReferenceSkeleton.GetParentIndex(BoneIndex);
			if (BoneIndex == ParentIndex)
			{
				bIsBelow = true;
				break;
			}
		}
		if ((bIncludeParent && bIsParent) || bIsBelow)
		{
			ChangedBodies+=ProphecyPhysicalContext::Set(*this,BodySetup->BoneName,
				ProphecyPhysicalContext::EKind::Magnetization,bEnabled,{LinearStrengthScale,AngularStrengthScale},
				0,Locomotion,Equipment) ? 1 : 0;
		}
	}
	return ChangedBodies;
}

bool AProphecyAgent::SetBodyIncludedInPhysicalSimulation(FName BoneName, bool bSimulateBody)
{
	if (IsJoltPhysicalAnimationEnabled())
	{
		UE_LOG(LogProphecyAgentPhysical, Warning, TEXT("Changing rig membership is not yet connected to the opt-in Jolt binding; use drive strength to release a limb."));
		return false;
	}
	FProphecyBodyMagnetizationSettings& Settings = BodyMagnetizationSettings.FindOrAdd(BoneName);
	Settings.bSimulateBody = bSimulateBody;
	const USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	return PhysicalMesh && PhysicalMesh->GetPhysicsAsset() &&
		PhysicalMesh->GetPhysicsAsset()->FindBodyIndex(BoneName) != INDEX_NONE;
}

bool AProphecyAgent::GetBodyMagnetizationSettings(
	FName BoneName,
	FProphecyBodyMagnetizationSettings& Settings) const
{
	const FProphecyBodyMagnetizationSettings* Found = BodyMagnetizationSettings.Find(BoneName);
	if (!Found)
	{
		Settings = FProphecyBodyMagnetizationSettings{};
		return false;
	}
	Settings = *Found;
	return true;
}

void AProphecyAgent::ApplyConfiguredWorldMagnetization(float DeltaSeconds)
{
	ApplyAbsoluteWorldMagnetization(DeltaSeconds);
}

bool AProphecyAgent::ApplyBodyWorldMagnetization(
	FName BoneName,
	const FTransform& TargetWorldTransform,
	float DeltaSeconds,
	float LinearStrengthScale,
	float AngularStrengthScale,
	bool bCancelGravity)
{
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	FBodyInstance* Body = PhysicalMesh ? PhysicalMesh->GetBodyInstance(BoneName) : nullptr;
	if (!Body || !Body->IsInstanceSimulatingPhysics() || DeltaSeconds <= UE_SMALL_NUMBER)
	{
		return false;
	}

	// Shared exact native Sim rule: the headless comparison uses this same math,
	// without the production Blueprint or NN target-generation path.
	if (ProphecyPelvisInertia::ApplyChaosDrive(this, BoneName, Body, TargetWorldTransform,
		DeltaSeconds, LinearStrengthScale, AngularStrengthScale, bCancelGravity,
		GetWorld() ? GetWorld()->GetGravityZ() : 0.f)) return true;
	return UProphecyHalfSimDriveComponent::ApplyOneStepBody(Body, TargetWorldTransform,
		DeltaSeconds, LinearStrengthScale, AngularStrengthScale, bCancelGravity,
		GetWorld() ? GetWorld()->GetGravityZ() : 0.f);
}

void AProphecyAgent::SetMACDEnabled(bool bEnabled)
{
	bMACDEnabled = bEnabled;

	// UPrimitiveComponent::SetAllUseMACD does not iterate USkeletalMeshComponent::Bodies
	// in UE 5.7, so apply the runtime flag to every rigid body explicitly.
	USkeletalMeshComponent* PhysicalMesh = GetPoseReferenceMesh();
	if (!PhysicalMesh)
	{
		return;
	}
	for (FBodyInstance* BodyInstance : PhysicalMesh->Bodies)
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
	if (IsJoltPhysicalAnimationEnabled())
		return JoltCharacter->SampleCompletedComponentPose(BoneNames, OutComponentTransforms);
	const USkeletalMeshComponent* PoseMesh = GetPoseReferenceMesh();
	if (BoneNames.Num() != OutComponentTransforms.Num() || !PoseMesh || !PoseMesh->IsRegistered())
	{
		return false;
	}

	const TArray<FTransform>& ComponentSpaceTransforms = PoseMesh->GetComponentSpaceTransforms();
	const USceneComponent* FeedbackReference = Mesh && Mesh->IsRegistered() ? Mesh : PoseMesh;
	const bool bNeedsReferenceConversion = PoseMesh != FeedbackReference;
	for (int32 Index = 0; Index < BoneNames.Num(); ++Index)
	{
		const int32 BoneIndex = PoseMesh->GetBoneIndex(BoneNames[Index]);
		if (!ComponentSpaceTransforms.IsValidIndex(BoneIndex))
		{
			return false;
		}
		OutComponentTransforms[Index] = bNeedsReferenceConversion
			? PoseMesh->GetSocketTransform(BoneNames[Index], RTS_World)
				.GetRelativeTransform(FeedbackReference->GetComponentTransform())
			: ComponentSpaceTransforms[BoneIndex];
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
	if (SimulationMode != EProphecyAgentSimulationMode::Kinematic && bGeneratePhysicalHitEvents
		&& HitComponent == GetPoseReferenceMesh())
	{
		OnPhysicalHit.Broadcast(this, OtherActor, OtherComponent, NormalImpulse, Hit);
	}
}

namespace ProphecyManualServoCapture
{
namespace
{
	FManualFollowerSubstepCallback* FindCaptureCallback(AProphecyAgent* Agent, FString& OutError)
	{
		OutError.Reset();
		if (!IsInGameThread())
		{
			OutError = TEXT("Manual servo capture APIs require the game thread.");
			return nullptr;
		}
		if (!IsValid(Agent))
		{
			OutError = TEXT("Manual servo capture requires a valid agent.");
			return nullptr;
		}
		const FManualFollowerSubstepState* State = ManualFollowerSubstepStates.Find(Agent);
		if (!State || !State->Callback)
		{
			OutError = TEXT("The manual callback is unavailable or was released. End capture before changing mode or destroying its actor/world.");
			return nullptr;
		}
		return State->Callback;
	}

	bool ResolveManualCaptureScene(
		AProphecyAgent* Agent, USkeletalMeshComponent*& OutMesh, FPhysScene*& OutScene, FString& OutError)
	{
		OutError.Reset();
		if (!IsInGameThread())
		{
			OutError = TEXT("Manual servo capture APIs require the game thread.");
			return false;
		}
		if (!IsValid(Agent) || !Agent->bManualNNPoseApplication ||
			Agent->GetSimulationMode() == EProphecyAgentSimulationMode::HalfSim)
		{
			OutError = TEXT("Capture/replay requires a valid manual agent outside HalfSim.");
			return false;
		}
		OutMesh = FindManualPhysicalMesh(Agent);
		UWorld* World = Agent->GetWorld();
		OutScene = World ? World->GetPhysicsScene() : nullptr;
		if (!OutMesh || !OutMesh->IsAnySimulatingPhysics() || !OutScene || !OutScene->GetSolver())
		{
			OutError = TEXT("Capture/replay requires a live simulating PhysicalMesh and Chaos solver.");
			return false;
		}
		return true;
	}
}

bool BeginCapture(AProphecyAgent* Agent, int32 MaxPackets, int32 MaxSteps, FString& OutError)
{
	USkeletalMeshComponent* PhysicalMesh = nullptr;
	FPhysScene* PhysicsScene = nullptr;
	if (!ResolveManualCaptureScene(Agent, PhysicalMesh, PhysicsScene, OutError))
	{
		return false;
	}
	constexpr uint64 MaximumCaptureBytes = 256ull * 1024ull * 1024ull;
	if (MaxPackets <= 0 || MaxSteps <= 0 ||
		static_cast<uint64>(MaxPackets) * sizeof(FPacket) +
		static_cast<uint64>(MaxSteps) * sizeof(FStep) > MaximumCaptureBytes)
	{
		OutError = TEXT("Capture capacities must be positive and their combined packet/step storage must not exceed 256 MiB.");
		return false;
	}
	const FManualFollowerSubstepState* ExistingState = ManualFollowerSubstepStates.Find(Agent);
	if (ExistingState && ExistingState->Callback && ExistingState->Callback->IsCapturing_External())
	{
		OutError = TEXT("This agent is already recording; end its capture before starting another.");
		return false;
	}
	FManualFollowerSubstepCallback* Callback = GetOrCreateManualFollowerSubstepCallback(Agent, PhysicsScene);
	if (!Callback)
	{
		OutError = TEXT("Could not create the existing manual follower callback.");
		return false;
	}
	return Callback->BeginCapture_External(MaxPackets, MaxSteps, OutError);
}

bool ReadCapture(AProphecyAgent* Agent, FCapture& OutCapture, FString& OutError)
{
	FManualFollowerSubstepCallback* Callback = FindCaptureCallback(Agent, OutError);
	return Callback && Callback->ReadCapture_External(OutCapture, OutError);
}

bool EndCapture(AProphecyAgent* Agent, FCapture& OutCapture, FString& OutError)
{
	FManualFollowerSubstepCallback* Callback = FindCaptureCallback(Agent, OutError);
	return Callback && Callback->EndCapture_External(OutCapture, OutError);
}

bool PublishReplayPacket(AProphecyAgent* Agent, const FPacket& Packet, FString& OutError)
{
	USkeletalMeshComponent* PhysicalMesh = nullptr;
	FPhysScene* PhysicsScene = nullptr;
	if (!ResolveManualCaptureScene(Agent, PhysicalMesh, PhysicsScene, OutError))
	{
		if (IsInGameThread() && IsValid(Agent))
		{
			const FManualFollowerSubstepState* State = ManualFollowerSubstepStates.Find(Agent);
			if (State && State->Callback)
			{
				State->Callback->RecordPublishFailure_External(EPublishFailure::CallbackUnavailable);
			}
		}
		return false;
	}
	auto FailPublication = [Agent, &OutError](EPublishFailure Failure, const TCHAR* Message)
	{
		const FManualFollowerSubstepState* State = ManualFollowerSubstepStates.Find(Agent);
		if (State && State->Callback)
		{
			State->Callback->RecordPublishFailure_External(Failure);
		}
		OutError = Message;
		return false;
	};
	if (Agent->bAutoPublishManualFollowerSubstepTargets)
	{
		return FailPublication(EPublishFailure::InvalidReplayPacket,
			TEXT("Disable automatic manual target publication explicitly before replay, so Tick cannot overwrite sealed packets."));
	}
	if (Packet.Sequence == 0 || Packet.BodyCount < 0 || Packet.BodyCount > MaxBodies ||
		!FMath::IsFinite(Packet.MaximumSubstepSeconds) || Packet.MaximumSubstepSeconds <= 0.0f ||
		!FMath::IsFinite(Packet.FrameDeltaSeconds) || Packet.FrameDeltaSeconds < 0.0f)
	{
		return FailPublication(EPublishFailure::InvalidReplayPacket,
			TEXT("Replay requires a sealed nonzero-sequence packet, a bounded body count, and finite valid timing values."));
	}
	FManualFollowerSubstepTargets Targets;
	Targets.MaximumSubstepSeconds = Packet.MaximumSubstepSeconds;
	Targets.Bodies.Reserve(Packet.BodyCount);
	for (int32 BodyIndex = 0; BodyIndex < Packet.BodyCount; ++BodyIndex)
	{
		const FBoneTarget& RecordedBody = Packet.Bodies[BodyIndex];
		if (RecordedBody.BoneName.IsNone() || RecordedBody.ActualBoneWorld.ContainsNaN() ||
			RecordedBody.BodyFromBone.ContainsNaN() || RecordedBody.TargetPosition.ContainsNaN() ||
			RecordedBody.TargetRotation.ContainsNaN() || !RecordedBody.TargetRotation.IsNormalized() ||
			!FMath::IsFinite(RecordedBody.LinearStrength) || RecordedBody.LinearStrength < 0.0f ||
			!FMath::IsFinite(RecordedBody.AngularStrength) || RecordedBody.AngularStrength < 0.0f)
		{
			return FailPublication(EPublishFailure::InvalidReplayPacket,
				TEXT("Replay packet has an invalid bone name, transform, endpoint, or strength."));
		}
		for (int32 PreviousIndex = 0; PreviousIndex < BodyIndex; ++PreviousIndex)
		{
			if (Packet.Bodies[PreviousIndex].BoneName == RecordedBody.BoneName)
			{
				return FailPublication(EPublishFailure::InvalidReplayPacket,
					TEXT("Replay packet contains a duplicate body bone name."));
			}
		}
		FBodyInstance* Body = PhysicalMesh->GetBodyInstance(RecordedBody.BoneName);
		if (!Body || !Body->IsInstanceSimulatingPhysics() || !Body->GetPhysicsActor())
		{
			return FailPublication(EPublishFailure::ReplayBodyUnavailable,
				TEXT("A recorded replay bone does not resolve to a live simulating body on PhysicalMesh."));
		}
		FManualFollowerSubstepBody& OutputBody = Targets.Bodies.AddDefaulted_GetRef();
		OutputBody.Actor = Body->GetPhysicsActor();
		OutputBody.TargetPosition = RecordedBody.TargetPosition;
		OutputBody.TargetRotation = RecordedBody.TargetRotation;
		OutputBody.LinearStrengthScale = RecordedBody.LinearStrength;
		OutputBody.AngularStrengthScale = RecordedBody.AngularStrength;
	}
	FManualFollowerSubstepCallback* Callback = GetOrCreateManualFollowerSubstepCallback(Agent, PhysicsScene);
	if (!Callback)
	{
		return FailPublication(EPublishFailure::CallbackUnavailable,
			TEXT("Could not create the existing manual callback for replay."));
	}
	FPacket ReplayMetadata = Packet;
	ReplayMetadata.SourceSequence = Packet.SourceSequence != 0 ? Packet.SourceSequence : Packet.Sequence;
	Callback->PublishTargets_External(MoveTemp(Targets), &ReplayMetadata);
	return true;
}
}
