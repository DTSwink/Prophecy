#include "ProphecyNNLocomotionManager.h"
#include "ProphecyAttackStartInertia.h"
#include "ProphecyRootFacing.h"
#include "ProphecyAgentTime.h"
#include "ProphecySwordAttackCollision.h"
#include "ProphecyLimbCollision.h"
#include "ProphecyNNDefenseRuntime.h"
#include "ProphecyDefenseArmedGate.h"
#include "ProphecyDefenseControls.h"
#include "ProphecyNNLegClamps.h"
#include "ProphecyNNPolicyBlend.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyBlendClock.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyNNRootWindowSmoothing.h"
#include "ProphecyRootBalance.h"
#include "ProphecyKickFootLeeway.h"
#include "ProphecyRootPelvisBounds.h"
#include "ProphecyRootMagic.h"
#include "ProphecyRootSpeedLimits.h"
#include "ProphecyUpperIdleSeed.h"
#include "ProphecyPelvisInertia.h"
#include "ProphecyHandInertia.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyCoreTempering.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecySlashReturn.h"
#include "ProphecyHandChainMath.h"
#include "ProphecyPhysicalContext.h"
#include "ProphecyWalkPinning.h"
#include "ProphecyWalkTickPinning.h"
#include "ProphecyUpperRootHorizon.h"
#include "Async/ParallelFor.h"
#include "ProphecyCrowdNameLookup.h"

#include "ProphecyAgent.h"
#include "ProphecyAttackCamera.h"
#include "ProphecyAttackControls.h"
#include "ProphecyAttackTrim.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNPresentation.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "ProphecyJoltCharacterComponent.h"

#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AttributesRuntime.h"
#include "Animation/AnimCurveTypes.h"
#include "Animation/Skeleton.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "DrawDebugHelpers.h"
#include "Engine/Engine.h"
#include "Engine/EngineTypes.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputKeyEventArgs.h"
#include "UObject/UnrealType.h"
#include "UObject/Package.h"
#include "UObject/StrongObjectPtr.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#endif
#include "Modules/ModuleManager.h"
#if WITH_EDITOR
#include "Misc/SecureHash.h"
#include "Misc/CoreDelegates.h"
#endif
#include "NNE.h"
#include "NNEModelData.h"
#include "NNERuntimeCPU.h"
#include "NNERuntimeGPU.h"
#include "NNERuntimeRunSync.h"
#include "NNETypes.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#include "prophecy/sim/locomotion.h"

#include "../../../StandaloneSim/bridge/sim_bridge_protocol.h"

#include "HAL/PlatformAtomics.h"
#include "HAL/PlatformMemory.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"

namespace
{
	DEFINE_LOG_CATEGORY_STATIC(LogProphecyNNLocomotion, Log, All);

	constexpr int32 BatchSize = 100;

	struct FResolvedMoverTarget
	{
		prophecy::sim::LocomotionTarget Target;
		bool bRun = false;
		bool bValid = false;
	};
	// One small contiguous readback buffer per live manager. Keep it outside the
	// pre-existing non-UObject allocation layout so Live Coding needs no migration.
	TMap<const AProphecyNNLocomotionManager*, TArray<FResolvedMoverTarget>> ResolvedMoverTargets;
	// Event-only full-attack handoff state; no change to live FImpl allocation layout.
	TMap<const AProphecyAgent*, FVector> SlashRootMinusStartPelvis;
	TSet<TWeakObjectPtr<const AProphecyAgent>> RootYawImpulseAgents;
	// Only external linear impulses need world-space transport of the otherwise
	// root-relative direction-smoothing history. Value is its last training yaw.
	TMap<TWeakObjectPtr<const AProphecyAgent>, float> RootImpulseSmoothingYaw;
	TMap<TWeakObjectPtr<const UWorld>, float> HalfAttackTargetRadii;
	constexpr int32 InputDim = 152;
	constexpr int32 StateDim = 41;
	constexpr int32 PolicyOutputDim = 43;
	constexpr int32 UpperInputDim = 281;
	constexpr int32 UpperStateDim = 90;
	constexpr int32 SlashInputDim = 272;
	constexpr int32 SlashOutputDim = 437;
	constexpr int32 FullBodyBoneCount = 25;
	constexpr int32 FutureWindow = 8;
	constexpr int32 PoseStoreAgentBase = 100000;
	constexpr int32 MaxCatchUpStepsPerTick = 32;
	constexpr float MetersToCentimeters = 100.0f;
	constexpr float ToeAlphaRadians = UE_PI * 0.5f;

	struct FPhysicalFeedbackTolerance
	{
		float LinearCm = 0.0f;
		float AngularDegrees = 0.0f;
	};

	const TArray<FName>& ControlledFeedbackBoneNames()
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

	struct FMat3f
	{
		FVector3f Rows[3] = {
			FVector3f(1.0f, 0.0f, 0.0f),
			FVector3f(0.0f, 1.0f, 0.0f),
			FVector3f(0.0f, 0.0f, 1.0f)
		};
	};

	FVector3f SafeNormal(const FVector3f& Value, const FVector3f& Fallback = FVector3f(1.0f, 0.0f, 0.0f))
	{
		const float SizeSquared = Value.SizeSquared();
		return SizeSquared > 1.0e-16f ? Value * FMath::InvSqrt(SizeSquared) : Fallback;
	}

	FVector3f StablePerpendicular(const FVector3f& Axis)
	{
		const FVector3f N = SafeNormal(Axis);
		const FVector3f Reference = FMath::Abs(N.Z) < 0.8f ? FVector3f(0.0f, 0.0f, 1.0f) : FVector3f(1.0f, 0.0f, 0.0f);
		return SafeNormal(FVector3f::CrossProduct(N, Reference), FVector3f(0.0f, 1.0f, 0.0f));
	}

	FVector3f ProjectToPlane(const FVector3f& Value, const FVector3f& Normal)
	{
		const FVector3f N = SafeNormal(Normal);
		return SafeNormal(Value - N * FVector3f::DotProduct(Value, N), StablePerpendicular(N));
	}

	FMat3f Transpose(const FMat3f& Matrix)
	{
		FMat3f Out;
		for (int32 Row = 0; Row < 3; ++Row)
		{
			for (int32 Col = 0; Col < 3; ++Col)
			{
				Out.Rows[Row][Col] = Matrix.Rows[Col][Row];
			}
		}
		return Out;
	}

	FMat3f Multiply(const FMat3f& A, const FMat3f& B)
	{
		FMat3f Out;
		for (int32 Row = 0; Row < 3; ++Row)
		{
			for (int32 Col = 0; Col < 3; ++Col)
			{
				Out.Rows[Row][Col] =
					A.Rows[Row].X * B.Rows[0][Col] +
					A.Rows[Row].Y * B.Rows[1][Col] +
					A.Rows[Row].Z * B.Rows[2][Col];
			}
		}
		return Out;
	}

	FMat3f MirrorYBasis(const FMat3f& Matrix)
	{
		// The accepted policy uses the same X/Z axes as the Unreal skeleton but
		// the opposite local Y axis. Rotations therefore cross the boundary as
		// S * R * S, where S = diag(1,-1,1). Applying only the raw matrix made
		// the policy legs face opposite the reference-pose torso.
		FMat3f Out = Matrix;
		for (int32 Row = 0; Row < 3; ++Row)
		{
			for (int32 Col = 0; Col < 3; ++Col)
			{
				if ((Row == 1) != (Col == 1)) Out.Rows[Row][Col] *= -1.0f;
			}
		}
		return Out;
	}

	FVector3f TransformRow(const FVector3f& Vector, const FMat3f& Matrix)
	{
		return FVector3f(
			Vector.X * Matrix.Rows[0].X + Vector.Y * Matrix.Rows[1].X + Vector.Z * Matrix.Rows[2].X,
			Vector.X * Matrix.Rows[0].Y + Vector.Y * Matrix.Rows[1].Y + Vector.Z * Matrix.Rows[2].Y,
			Vector.X * Matrix.Rows[0].Z + Vector.Y * Matrix.Rows[1].Z + Vector.Z * Matrix.Rows[2].Z);
	}

	FMat3f YawMatrix(float YawRadians)
	{
		const float C = FMath::Cos(YawRadians);
		const float S = FMath::Sin(YawRadians);
		FMat3f Out;
		Out.Rows[0] = FVector3f(C, 0.0f, S);
		Out.Rows[1] = FVector3f(0.0f, 1.0f, 0.0f);
		Out.Rows[2] = FVector3f(-S, 0.0f, C);
		return Out;
	}

	FVector3f RotateAroundAxis(const FVector3f& Value, const FVector3f& AxisValue, float Angle)
	{
		const FVector3f Axis = SafeNormal(AxisValue);
		const float C = FMath::Cos(Angle);
		const float S = FMath::Sin(Angle);
		return Value * C + FVector3f::CrossProduct(Axis, Value) * S + Axis * FVector3f::DotProduct(Axis, Value) * (1.0f - C);
	}

	FMat3f AxisAngleMatrix(const FVector3f& Axis, float Angle)
	{
		FMat3f Out;
		Out.Rows[0] = RotateAroundAxis(FVector3f(1.0f, 0.0f, 0.0f), Axis, Angle);
		Out.Rows[1] = RotateAroundAxis(FVector3f(0.0f, 1.0f, 0.0f), Axis, Angle);
		Out.Rows[2] = RotateAroundAxis(FVector3f(0.0f, 0.0f, 1.0f), Axis, Angle);
		return Out;
	}

	FMat3f CalfRotationFromHinge(
		const FVector3f& LocalThighAxis,
		const FVector3f& LocalCalfAxis,
		const FVector3f& LocalThighPole,
		const FVector3f& LocalCalfPole,
		const FMat3f& ThighRotation,
		const FVector3f& KneeToFoot)
	{
		// A knee transports a signed hinge NORMAL, not a forward pole ray.
		// Projecting the ray onto the calf flips its sign when the leg folds
		// past it. Keep the same hinge side through straight and bent poses.
		const FVector3f LocalMain = SafeNormal(LocalCalfAxis);
		const FVector3f LocalHinge = SafeNormal(
			FVector3f::CrossProduct(LocalMain, LocalCalfPole), StablePerpendicular(LocalMain));
		const FVector3f ThighMain = SafeNormal(LocalThighAxis);
		const FVector3f WorldHinge = TransformRow(SafeNormal(
			FVector3f::CrossProduct(ThighMain, LocalThighPole), StablePerpendicular(ThighMain)), ThighRotation);
		const FVector3f WorldMain = SafeNormal(KneeToFoot, TransformRow(LocalMain, ThighRotation));

		// Cross products avoid subtractive pole projection cancellation. Rebuild
		// both transverse axes so MatrixToQuat always receives a proper rotation.
		// The degenerate off-hinge case has a deterministic thigh-based fallback;
		// there is no previous-frame state, iteration, allocation or angle solve.
		const FVector3f WorldSideRaw = FVector3f::CrossProduct(WorldHinge, WorldMain);
		FVector3f WorldSide;
		if (WorldSideRaw.SizeSquared() > 1.0e-12f)
		{
			WorldSide = SafeNormal(WorldSideRaw);
		}
		else
		{
			const FVector3f Reference = TransformRow(ThighMain, ThighRotation);
			WorldSide = SafeNormal(FVector3f::CrossProduct(Reference, WorldMain), StablePerpendicular(WorldMain));
		}
		const FVector3f WorldNormal = SafeNormal(FVector3f::CrossProduct(WorldMain, WorldSide));
		WorldSide = SafeNormal(FVector3f::CrossProduct(WorldNormal, WorldMain));
		const FVector3f LocalSide = SafeNormal(FVector3f::CrossProduct(LocalHinge, LocalMain));
		FMat3f LocalBasis;
		LocalBasis.Rows[0] = LocalMain;
		LocalBasis.Rows[1] = LocalSide;
		LocalBasis.Rows[2] = SafeNormal(FVector3f::CrossProduct(LocalMain, LocalSide));
		FMat3f WorldBasis;
		WorldBasis.Rows[0] = WorldMain;
		WorldBasis.Rows[1] = WorldSide;
		WorldBasis.Rows[2] = WorldNormal;
		return Multiply(Transpose(LocalBasis), WorldBasis);
	}

	FMat3f MatrixFromRot6(const float* Values)
	{
		FVector3f First(Values[0], Values[1], Values[2]);
		FVector3f Second(Values[3], Values[4], Values[5]);
		if (First.SizeSquared() <= 1.0e-16f)
		{
			First = FVector3f(1.0f, 0.0f, 0.0f);
		}
		else
		{
			First = SafeNormal(First);
		}
		Second -= First * FVector3f::DotProduct(First, Second);
		if (Second.SizeSquared() <= 1.0e-16f)
		{
			int32 SmallestAxis = 0;
			if (FMath::Abs(First.Y) < FMath::Abs(First[SmallestAxis])) SmallestAxis = 1;
			if (FMath::Abs(First.Z) < FMath::Abs(First[SmallestAxis])) SmallestAxis = 2;
			FVector3f Fallback = FVector3f::ZeroVector;
			Fallback[SmallestAxis] = 1.0f;
			Second = Fallback - First * FVector3f::DotProduct(First, Fallback);
		}
		Second = SafeNormal(Second, StablePerpendicular(First));
		FMat3f Out;
		Out.Rows[0] = First;
		Out.Rows[1] = Second;
		Out.Rows[2] = FVector3f::CrossProduct(First, Second);
		return Out;
	}

	void WriteRot6(const FMat3f& Matrix, float* Values)
	{
		for (int32 Axis = 0; Axis < 3; ++Axis)
		{
			Values[Axis] = Matrix.Rows[0][Axis];
			Values[Axis + 3] = Matrix.Rows[1][Axis];
		}
	}

	FVector3f RotationVectorBetween(const FMat3f& From, const FMat3f& To)
	{
		const FMat3f Relative = Multiply(To, Transpose(From));
		const FVector3f Vee(
			Relative.Rows[1].Z - Relative.Rows[2].Y,
			Relative.Rows[2].X - Relative.Rows[0].Z,
			Relative.Rows[0].Y - Relative.Rows[1].X);
		const float VeeNorm = Vee.Size();
		const float CosAngle = FMath::Clamp((Relative.Rows[0].X + Relative.Rows[1].Y + Relative.Rows[2].Z - 1.0f) * 0.5f, -1.0f, 1.0f);
		const float Angle = FMath::Atan2(VeeNorm * 0.5f, CosAngle);
		const float Scale = VeeNorm > 1.0e-7f ? Angle / FMath::Max(VeeNorm, 1.0e-7f) : 0.5f;
		return Vee * Scale;
	}

	FQuat MatrixToQuat(const FMat3f& Matrix)
	{
		const FMatrix UnrealMatrix(
			FPlane(Matrix.Rows[0].X, Matrix.Rows[0].Y, Matrix.Rows[0].Z, 0.0f),
			FPlane(Matrix.Rows[1].X, Matrix.Rows[1].Y, Matrix.Rows[1].Z, 0.0f),
			FPlane(Matrix.Rows[2].X, Matrix.Rows[2].Y, Matrix.Rows[2].Z, 0.0f),
			FPlane(0.0f, 0.0f, 0.0f, 1.0f));
		return FQuat(UnrealMatrix).GetNormalized();
	}

	FMat3f QuatToMatrix(const FQuat& Quaternion)
	{
		const FMatrix Matrix = FTransform(Quaternion.GetNormalized()).ToMatrixNoScale();
		FMat3f Out;
		for (int32 Row = 0; Row < 3; ++Row)
		{
			Out.Rows[Row] = FVector3f(float(Matrix.M[Row][0]), float(Matrix.M[Row][1]), float(Matrix.M[Row][2]));
		}
		return Out;
	}

	FMat3f ForearmRotationFromHand(const FVector3f& LocalAxisValue,
		const FVector3f& ElbowToHand, const FVector3f& LocalPole, const FMat3f& HandRotation)
	{
		// The upper-body contract uses a shared neutral hand/forearm basis (as in
		// SeedUpperState). Carry the hand's roll, removing only wrist swing needed
		// to point the forearm from elbow to hand. Never use simulated forearm roll
		// or the upper-arm pole to choose this target's axial rotation.
		const FQuat Hand = MatrixToQuat(HandRotation);
		const FVector LocalAxis(SafeNormal(LocalAxisValue));
		const FVector From = Hand.RotateVector(LocalAxis);
		const FVector To = FVector(ElbowToHand).GetSafeNormal(1.0e-16, From);
		const double Dot = FMath::Clamp(FVector::DotProduct(From, To), -1.0, 1.0);
		FQuat Swing;
		if (1.0 + Dot > 1.0e-12)
		{
			const FVector Cross = FVector::CrossProduct(From, To);
			Swing = FQuat(Cross.X, Cross.Y, Cross.Z, 1.0 + Dot).GetNormalized();
		}
		else
		{
			// At exactly opposite directions a shortest swing has no unique axis.
			// Resolve that degenerate pose in the hand frame, not against world axes.
			const FVector Axis = Hand.RotateVector(FVector(ProjectToPlane(LocalPole, FVector3f(LocalAxis))));
			Swing = FQuat(Axis, UE_DOUBLE_PI);
		}
		return QuatToMatrix(Swing * Hand);
	}

    // UE boundary for every special: same wrist-derived roll as locomotion.
    // Twist is reconstructed, not an independent NN output. Keep every position
    // and the hand's complete transform untouched.
    void SetForearmRollFromHand(const FVector3f& LocalAxis,const FVector3f& LocalPole,
        FTransform& Forearm,const FTransform& Hand)
    {
        const FVector Delta=Hand.GetLocation()-Forearm.GetLocation();
        const auto Rotation=ForearmRotationFromHand(LocalAxis,FVector3f(Delta.X,-Delta.Y,Delta.Z),
            LocalPole,MirrorYBasis(QuatToMatrix(Hand.GetRotation())));
        Forearm.SetRotation(MatrixToQuat(MirrorYBasis(Rotation)));
    }

    // As with forearms, calf twist is reconstructed rather than a reduced NN
    // state output. Carry the signed knee hinge used by locomotion instead of
    // the attack decoder's discontinuous projected-pole/hemisphere rule.
    void SetCalfRollFromThigh(const FVector3f& ThighAxis,const FVector3f& CalfAxis,
        const FVector3f& ThighPole,const FVector3f& CalfPole,
        const FTransform& Thigh,FTransform& Calf,const FTransform& Foot)
    {
        const FVector Delta=Foot.GetLocation()-Calf.GetLocation();
        const auto Rotation=CalfRotationFromHinge(ThighAxis,CalfAxis,ThighPole,CalfPole,
            MirrorYBasis(QuatToMatrix(Thigh.GetRotation())),FVector3f(Delta.X,-Delta.Y,Delta.Z));
        Calf.SetRotation(MatrixToQuat(MirrorYBasis(Rotation)));
    }

#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyNNForearmTargetTests.inl"
#endif

	class FSampledTrainingRotations
	{
	public:
		explicit FSampledTrainingRotations(TConstArrayView<FTransform> InTransforms)
			: Transforms(InTransforms)
		{
			static_assert(FullBodyBoneCount <= 32);
			check(Transforms.Num() == FullBodyBoneCount);
		}

		const FMat3f& Get(int32 Index)
		{
			check(Transforms.IsValidIndex(Index));
			const uint32 Bit = uint32(1) << Index;
			if ((ReadyMask & Bit) == 0)
			{
				Matrices[Index] = MirrorYBasis(QuatToMatrix(Transforms[Index].GetRotation()));
				ReadyMask |= Bit;
			}
			return Matrices[Index];
		}

#if WITH_DEV_AUTOMATION_TESTS
		uint32 CachedMaskForTests() const { return ReadyMask; }
#endif

	private:
		TConstArrayView<FTransform> Transforms;
		FMat3f Matrices[FullBodyBoneCount];
		uint32 ReadyMask = 0;
	};

	FVector ApplyLinearFeedbackTolerance(
		const FVector& Kinematic,
		const FVector& Simulated,
		float ToleranceCm)
	{
		const FVector Error = Simulated - Kinematic;
		const float ErrorSize = Error.Size();
		const float Tolerance = FMath::Max(0.0f, ToleranceCm);
		if (ErrorSize <= Tolerance || ErrorSize <= UE_SMALL_NUMBER)
		{
			return Kinematic;
		}
		return Kinematic + Error * ((ErrorSize - Tolerance) / ErrorSize);
	}

	FQuat ApplyAngularFeedbackTolerance(
		const FQuat& KinematicValue,
		const FQuat& SimulatedValue,
		float ToleranceDegrees)
	{
		FQuat Kinematic = KinematicValue.GetNormalized();
		FQuat Simulated = SimulatedValue.GetNormalized();
		float Dot = Kinematic | Simulated;
		if (Dot < 0.0f)
		{
			Simulated = Simulated * -1.0f;
			Dot = -Dot;
		}
		const float ErrorRadians = 2.0f * FMath::Acos(FMath::Clamp(Dot, 0.0f, 1.0f));
		const float ToleranceRadians = FMath::DegreesToRadians(FMath::Max(0.0f, ToleranceDegrees));
		if (ErrorRadians <= ToleranceRadians || ErrorRadians <= UE_SMALL_NUMBER)
		{
			return Kinematic;
		}
		return FQuat::Slerp(Kinematic, Simulated,
			(ErrorRadians - ToleranceRadians) / ErrorRadians).GetNormalized();
	}

	void ApplyPhysicalFeedbackTolerance(
		FTransform& Simulated,
		const FTransform& Kinematic,
		const FPhysicalFeedbackTolerance& Tolerance)
	{
		Simulated.SetTranslation(ApplyLinearFeedbackTolerance(
			Kinematic.GetTranslation(), Simulated.GetTranslation(), Tolerance.LinearCm));
		Simulated.SetRotation(ApplyAngularFeedbackTolerance(
			Kinematic.GetRotation(), Simulated.GetRotation(), Tolerance.AngularDegrees));
	}

	void CachePhysicalFeedbackSettings(
		const AProphecyAgent* Agent,
		TMap<FName, FPhysicalFeedbackTolerance>& OutTolerances)
	{
		OutTolerances.Reset();
		if (!Agent)
		{
			return;
		}
		for (const FName BoneName : ControlledFeedbackBoneNames())
		{
			const FProphecyPhysicalFeedbackToleranceSettings* Source =
				Agent->PhysicalFeedbackTolerances.Find(BoneName);
			FPhysicalFeedbackTolerance& Target = OutTolerances.FindOrAdd(BoneName);
			Target.LinearCm = Source ? FMath::Max(0.0f, Source->LinearToleranceCm) : 0.0f;
			Target.AngularDegrees = Source ?
				FMath::Max(0.0f, Source->AngularToleranceDegrees) : 0.0f;
		}
	}

#if WITH_DEV_AUTOMATION_TESTS
	IMPLEMENT_SIMPLE_AUTOMATION_TEST(
		FProphecyPhysicalFeedbackToleranceTest,
		"Prophecy.NN.PhysicalFeedbackTolerance",
		EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

	bool FProphecyPhysicalFeedbackToleranceTest::RunTest(const FString& Parameters)
	{
		const FTransform Kinematic(
			FQuat(FVector::UpVector, FMath::DegreesToRadians(10.0f)),
			FVector(10.0f, 20.0f, 30.0f));
		const FTransform Simulated(
			FQuat(FVector::UpVector, FMath::DegreesToRadians(40.0f)),
			FVector(13.0f, 24.0f, 30.0f));

		FTransform ZeroResult = Simulated;
		ApplyPhysicalFeedbackTolerance(ZeroResult, Kinematic, FPhysicalFeedbackTolerance{});
		TestTrue(TEXT("Zero linear tolerance returns the simulated position"),
			ZeroResult.GetTranslation().Equals(Simulated.GetTranslation(), 1.0e-4f));
		TestTrue(TEXT("Zero angular tolerance returns the simulated rotation"),
			ZeroResult.GetRotation().AngularDistance(Simulated.GetRotation()) <= 1.0e-5f);

		FPhysicalFeedbackTolerance LargeTolerance;
		LargeTolerance.LinearCm = 100000.0f;
		LargeTolerance.AngularDegrees = 360.0f;
		FTransform LargeResult = Simulated;
		ApplyPhysicalFeedbackTolerance(LargeResult, Kinematic, LargeTolerance);
		TestTrue(TEXT("Oversized linear tolerance returns the kinematic position"),
			LargeResult.GetTranslation().Equals(Kinematic.GetTranslation(), 1.0e-4f));
		TestTrue(TEXT("Oversized angular tolerance returns the kinematic rotation"),
			LargeResult.GetRotation().AngularDistance(Kinematic.GetRotation()) <= 1.0e-5f);
		TestTrue(TEXT("The two extremes differ under the same start"),
			!ZeroResult.GetTranslation().Equals(LargeResult.GetTranslation(), 1.0e-4f) &&
			ZeroResult.GetRotation().AngularDistance(LargeResult.GetRotation()) > 1.0e-3f);

		FPhysicalFeedbackTolerance PartialTolerance;
		PartialTolerance.LinearCm = 1.0f;
		PartialTolerance.AngularDegrees = 5.0f;
		FTransform PartialResult = Simulated;
		ApplyPhysicalFeedbackTolerance(PartialResult, Kinematic, PartialTolerance);
		TestTrue(TEXT("Partial linear tolerance subtracts exactly one centimetre"),
			FMath::IsNearlyEqual(
				float(FVector::Distance(Kinematic.GetTranslation(), PartialResult.GetTranslation())),
				4.0f,
				1.0e-4f));
		TestTrue(TEXT("Partial angular tolerance subtracts exactly five degrees"),
			FMath::IsNearlyEqual(
				FMath::RadiansToDegrees(PartialResult.GetRotation().AngularDistance(Kinematic.GetRotation())),
				25.0f,
				1.0e-3f));
		return true;
	}
#endif

	FVector TrainingToUnreal(const FVector3f& ValueMeters)
	{
		return FVector(ValueMeters.X, ValueMeters.Z, ValueMeters.Y) * MetersToCentimeters;
	}

	FVector LocalTrainingToUnreal(const FVector3f& ValueMeters)
	{
		return FVector(ValueMeters.X, -ValueMeters.Y, ValueMeters.Z) * MetersToCentimeters;
	}

	FVector3f LocalUnrealToTraining(const FVector& ValueCentimeters)
	{
		return FVector3f(float(ValueCentimeters.X), float(-ValueCentimeters.Y), float(ValueCentimeters.Z)) / MetersToCentimeters;
	}

	FVector3f UnrealToTraining(const FVector& ValueCentimeters)
	{
		return FVector3f(float(ValueCentimeters.X), float(ValueCentimeters.Z), float(ValueCentimeters.Y)) / MetersToCentimeters;
	}

	FVector3f BridgeToTraining(const float ValueMeters[3])
	{
		return FVector3f(ValueMeters[0], ValueMeters[2], ValueMeters[1]);
	}

	void WriteBridgeActorState(const AProphecyAgent& Actor, prophecy::bridge::AgentState& State)
	{
		const FVector LowPointMeters = Actor.GetRootLowPoint() / MetersToCentimeters;
		State.position[0] = float(LowPointMeters.X);
		State.position[1] = float(LowPointMeters.Y);
		State.position[2] = float(LowPointMeters.Z);
		State.velocity[0] = 0.0f;
		State.velocity[1] = 0.0f;
		State.velocity[2] = 0.0f;
		State.physical_world_blocked = 0U;
		// The accepted skeleton faces local +Y. Unreal positive yaw rotates +Y in
		// the opposite sign to the mover's [sin(yaw), cos(yaw)] convention.
		State.facing_radians = -FMath::DegreesToRadians(float(Actor.GetActorRotation().Yaw));
		State.active = 1U;
	}

	float WrapAngle(float Angle)
	{
		return FMath::Atan2(FMath::Sin(Angle), FMath::Cos(Angle));
	}

	FString ResolveProjectPath(const FString& Path)
	{
		return FPaths::IsRelative(Path) ? FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), Path) : Path;
	}

	bool JsonFloatArray(const TArray<TSharedPtr<FJsonValue>>& Values, TArray<float>& Out)
	{
		Out.Reset(Values.Num());
		for (const TSharedPtr<FJsonValue>& Value : Values)
		{
			if (!Value.IsValid() || Value->Type != EJson::Number) return false;
			Out.Add(float(Value->AsNumber()));
		}
		return true;
	}

	bool JsonVec3(const TArray<TSharedPtr<FJsonValue>>& Values, FVector3f& Out)
	{
		if (Values.Num() != 3) return false;
		Out = FVector3f(float(Values[0]->AsNumber()), float(Values[1]->AsNumber()), float(Values[2]->AsNumber()));
		return true;
	}

	class FPolicyModel
	{
	public:
		bool CreateGpu(TObjectPtr<UNNEModelData> InModelData, const FString& RuntimeName)
		{
			TWeakInterfacePtr<INNERuntimeGPU> Runtime = UE::NNE::GetRuntime<INNERuntimeGPU>(RuntimeName);
			if (!Runtime.IsValid() || Runtime->CanCreateModelGPU(InModelData) != UE::NNE::EResultStatus::Ok) return false;
			TSharedPtr<UE::NNE::IModelGPU> Model = Runtime->CreateModelGPU(InModelData);
			GpuInstance = Model.IsValid() ? Model->CreateModelInstanceGPU() : nullptr;
			if (!GpuInstance.IsValid() || !SetShape(GpuInstance.Get())) return false;
			RuntimeUsed = RuntimeName;
			bGpu = true;
			return true;
		}

		bool CreateCpu(TObjectPtr<UNNEModelData> InModelData, const FString& RuntimeName)
		{
			TWeakInterfacePtr<INNERuntimeCPU> Runtime = UE::NNE::GetRuntime<INNERuntimeCPU>(RuntimeName);
			if (!Runtime.IsValid() || Runtime->CanCreateModelCPU(InModelData) != UE::NNE::EResultStatus::Ok) return false;
			TSharedPtr<UE::NNE::IModelCPU> Model = Runtime->CreateModelCPU(InModelData);
			CpuInstance = Model.IsValid() ? Model->CreateModelInstanceCPU() : nullptr;
			if (!CpuInstance.IsValid() || !SetShape(CpuInstance.Get())) return false;
			RuntimeUsed = RuntimeName;
			bGpu = false;
			return true;
		}

		bool Run(TArray<float>& Input, TArray<float>& Output)
		{
			UE::NNE::IModelInstanceRunSync* Instance = nullptr;
			if (GpuInstance.IsValid())
			{
				Instance = GpuInstance.Get();
			}
			else if (CpuInstance.IsValid())
			{
				Instance = CpuInstance.Get();
			}
			if (!Instance) return false;
			const UE::NNE::FTensorBindingCPU InputBinding{ Input.GetData(), uint64(Input.Num() * sizeof(float)) };
			const UE::NNE::FTensorBindingCPU OutputBinding{ Output.GetData(), uint64(Output.Num() * sizeof(float)) };
			return Instance->RunSync(MakeArrayView(&InputBinding, 1), MakeArrayView(&OutputBinding, 1)) == UE::NNE::EResultStatus::Ok;
		}

		FString RuntimeUsed;
		bool bGpu = false;
		bool ResizeBatch(int32 Count)
		{
			if (Count == InputBatchSize) return true;
			InputBatchSize = Count;
			return SetShape(bGpu ? static_cast<UE::NNE::IModelInstanceRunSync*>(GpuInstance.Get()) : CpuInstance.Get());
		}

	private:
		bool SetShape(UE::NNE::IModelInstanceRunSync* Instance)
		{
			const uint32 ShapeData[] = { uint32(InputBatchSize), uint32(InputWidth) };
			const UE::NNE::FTensorShape Shape = UE::NNE::FTensorShape::Make(MakeArrayView(ShapeData, 2));
			return Instance->SetInputTensorShapes(MakeArrayView(&Shape, 1)) == UE::NNE::EResultStatus::Ok;
		}

		TSharedPtr<UE::NNE::IModelInstanceCPU> CpuInstance;
		TSharedPtr<UE::NNE::IModelInstanceGPU> GpuInstance;
	public:
		int32 InputWidth = InputDim;
		int32 InputBatchSize = BatchSize;
	};

	struct FFootAxes
	{
		FVector3f FootCenter;
		FVector3f FootForward;
		FVector3f FootSide;
		FVector3f FootUp;
		FVector3f ToeCenter;
		FVector3f ToeForward;
		FVector3f ToeSide;
		FVector3f ToeUp;
	};

	float SupportSign(float AxisUp)
	{
		return AxisUp > 1.0e-5f ? -1.0f : (AxisUp < -1.0e-5f ? 1.0f : 0.0f);
	}

	FVector3f BoxContact(
		const FVector3f& Center,
		const FVector3f& Forward,
		const FVector3f& Side,
		const FVector3f& Up,
		const FVector3f& HalfDims,
		float SideBlendRadians,
		FVector3f* OutSupport = nullptr)
	{
		const float ForwardSign = SupportSign(Forward.Z);
		const float SideSign = SupportSign(Side.Z);
		const float SideTilt = FMath::Asin(FMath::Clamp(FMath::Abs(Side.Z), 0.0f, 1.0f));
		const float SideScale = FMath::Clamp(SideTilt / FMath::Max(SideBlendRadians, 1.0e-6f), 0.0f, 1.0f);
		const FVector3f Support(
			ForwardSign * HalfDims.X * (ForwardSign != 0.0f ? 1.0f : 0.0f),
			SideSign * HalfDims.Y * SideScale,
			-HalfDims.Z);
		if (OutSupport) *OutSupport = Support;
		return Center + Forward * Support.X + Side * Support.Y + Up * Support.Z;
	}

	FVector3f BoxPointWithSupport(
		const FVector3f& Center,
		const FVector3f& Forward,
		const FVector3f& Side,
		const FVector3f& Up,
		const FVector3f& Support)
	{
		return Center + Forward * Support.X + Side * Support.Y + Up * Support.Z;
	}

FVector3f ReadStateVec3(const float* State, int32 Offset);
void WriteStateVec3(float* State, int32 Offset, const FVector3f& Value);
#include "ProphecyPelvisLowerCorrection.inl"
#include "ProphecySlashNative.h"
}

struct AProphecyNNLocomotionManager::FImpl
{
	struct FLimb
	{
		int32 Start = INDEX_NONE;
		int32 Mid = INDEX_NONE;
		int32 End = INDEX_NONE;
		int32 Toe = INDEX_NONE;
		FVector2f Lengths = FVector2f::ZeroVector;
		FVector3f LocalPoleAxes[2];
		FVector3f ToeOffset;
		FVector3f ToeAxis;
	};

	struct FUpperArm
	{
		int32 Start = INDEX_NONE;
		int32 Mid = INDEX_NONE;
		int32 End = INDEX_NONE;
		FVector2f Lengths = FVector2f::ZeroVector;
		FVector3f LocalPoleAxes[2];
	};

	struct FAgent
	{
		// Event-only pointer into the optional shared defense runtime.
		FProphecyLiveDefensePose* DefensePose=nullptr;
		float UpperRootRotationHorizon = 1.0f;
		struct FSlashAttack
		{
			FName Family;
			FVector TargetWorld = FVector::ZeroVector;
			FTransform AnchorWorld;
			// Half attacks follow pelvis translation, never locomotion pelvis/root rotation.
			FQuat HalfMountWorldRotation = FQuat::Identity;
			FVector2D CalfClampLengths = FVector2D::ZeroVector;
			FProphecyNNAttackHandClamp HandClamp;
			FSlashNative::FPreparationPose PreparationEntry;
			float PreparationBlendSeconds = 0.1f;
			bool bHeadbuttPreparation = false;
			TArray<float> State;
			TArray<FTransform> GhostPose;
			TArray<FTransform> PreviousVisibleWorldPose;
			TArray<FTransform> VisibleWorldPose;
			bool bActive = false;
			bool bHalf = false;
			bool bHasPose = false;
			bool bNeedsFeedback = false;
			int32 Frame = 1;
			int32 HitFrame = INDEX_NONE;
			int32 TailSteps = 0;
		};
		struct FAnimationLayer
		{
			TWeakObjectPtr<UAnimSequenceBase> Animation;
			uint32 BoneMask = 0;
			float PlaybackTimeSeconds = 0.0f;
			float ElapsedSeconds = 0.0f;
			float BlendWeight = 0.0f;
			float BlendInSeconds = 0.0f;
			float BlendOutSeconds = 0.0f;
			float PlayRate = 1.0f;
			float StopElapsedSeconds = 0.0f;
			float StopDurationSeconds = 0.0f;
			float StopStartWeight = 0.0f;
			bool bLoop = false;
			bool bStopping = false;
			bool bNaturalCompletion = false;
			bool bBlendingOutEventSent = false;

			bool IsActive() const
			{
				return Animation.IsValid();
			}

			void Reset()
			{
				*this = FAnimationLayer{};
			}
		};

		FVector3f PrevRootPos = FVector3f::ZeroVector;
		FVector3f CurRootPos = FVector3f::ZeroVector;
		FVector3f PreviousPublishedRoot = FVector3f::ZeroVector;
		FVector3f PublishedRoot = FVector3f::ZeroVector;
		double PublishedPoseTimeSeconds = 0.0;
		float PrevRootYaw = 0.0f;
		float CurRootYaw = 0.0f;
		float PreviousPublishedYaw = 0.0f;
		float PublishedYaw = 0.0f;
		FVector3f FedInputRoot = FVector3f::ZeroVector;
		float FedInputYaw = 0.0f;
		FVector3f WindowPreviousRoot = FVector3f::ZeroVector;
		float WindowPreviousYaw = 0, WindowStepSeconds = 0;
		float WindowVerticalVelocity = 0;
		FVector3f FedFutureRootPositions[FutureWindow]{};
		float FedFutureRootYaws[FutureWindow]{};
		FVector3f RouteA = FVector3f::ZeroVector;
		FVector3f RouteB = FVector3f::ZeroVector;
		int32 TargetIndex = 1;
		FVector2f PinProbability = FVector2f::ZeroVector;
		prophecy::sim::LocomotionState MoverState;
		prophecy::sim::LocomotionIntent MoverIntent;
		FVector3f LastBridgeActualRoot = FVector3f::ZeroVector;
		double LastBridgePublishSeconds = 0.0;
		int32 Generation = 1;
		bool bHasPhysicalSample = false;
		TMap<FName, FPhysicalFeedbackTolerance> PhysicalFeedbackTolerances;
		bool bHasBridgeIntent = false;
		bool bHasBridgeActualRoot = false;
		bool bPhysicalWorldBlockedPending = false;
		bool bHasAppliedVisualRoot = false;
		bool bHasFedFutureRoots = false;
		bool bPreviousPublishedUseWalkPolicy = false;
		bool bPublishedUseWalkPolicy = false;
		bool bUseWalkPolicy = false;
		FProphecyNNPolicyBlend PolicyBlend;
		float PublishedWalkWeight = 1.f, PreviousPublishedWalkWeight = 1.f;
		ProphecyAttackRecovery::FWeights RecoveryWeights;
		FVector2f PublishedLegWalkWeights=FVector2f(1,1), PreviousPublishedLegWalkWeights=FVector2f(1,1);
		FAnimationLayer AnimationLayer;
		FSlashAttack Slash;
	};

	struct FAnimationSamplingContext
	{
		TWeakObjectPtr<USkeletalMesh> Mesh;
		TArray<FBoneIndexType> RequiredBoneIndices;
		FBoneContainer RequiredBones;
		TArray<FTransform> CompactComponentTransforms;
		int32 BodyCompactPoseIndices[FullBodyBoneCount]{};
	};

	struct FStats
	{
		double Elapsed = 0.0;
		double WarmedSeconds = 0.0;
		double WallStartSeconds = 0.0;
		double BuildSeconds = 0.0;
		double InferenceSeconds = 0.0;
		double OutputSeconds = 0.0;
		double StoreSeconds = 0.0;
		int64 Frames = 0;
		int64 NNSteps = 0;
		bool bCollecting = false;
		bool bLogged = false;
	};

	TUniquePtr<FProphecyLiveDefenseRuntime> Defense;
	TArray<FName> BodyNames;
	TArray<int32> Parents;
	TArray<FVector3f> LocalOffsets;
	TArray<FVector3f> UpperLocalOffsets;
	TArray<FVector3f> RestOffsetsFromPelvis;
	TArray<TArray<float>> SeedPhaseStates;
	TArray<FVector3f> WalkLocalOffsets;
	TArray<TArray<float>> WalkSeedPhaseStates;
	TArray<FName> PublishedBoneNames;
	TArray<FName> UpperCoreBoneNames;
	FLimb Limbs[2];
	FLimb WalkLimbs[2];
	FUpperArm UpperArms[2];
	FMat3f SeedRootRot;
	FVector3f FootHalfDims = FVector3f::ZeroVector;
	FVector3f ToeHalfDims = FVector3f::ZeroVector;
	float SoleVerticalOffset = -0.006f;
	float SideBlendRadians = FMath::DegreesToRadians(8.0f);
	float PinScale = 8.0f;
	float GroundHeight = 0.0f;
	float NearFloorFullHeight = 0.015f;
	float NearFloorFadeHeight = 0.020f;
	float NearFloorMinPin = 1.0f;
	int32 FootRollSteps = 4;
	float MaxSpeedScaleFinal = 1.0f / 6.0f;
	float MaxTurnRateScaleFinal = 0.41887902f;
	float PoseDeltaScaleFinal = 1.0f / 15.0f;
	FVector3f EndpointA = FVector3f::ZeroVector;
	FVector3f EndpointB = FVector3f::ZeroVector;
	TArray<FAgent> Agents;
	TMap<int32, bool> PreviousPoseDebugAgents; // value: prefer active attack input
	TArray<float> PrevStateBuffer;
	TArray<float> CurStateBuffer;
	TArray<float> PreviousPublishedStateBuffer;
	TArray<float> PublishedStateBuffer;
	TArray<float> NextStateBuffer;
	TArray<float> PhysicalStateBuffer;
	TArray<float> PreviousPhysicalStateBuffer;
	TArray<float> UpperPreviousStateBuffer;
	TArray<float> UpperCurrentStateBuffer;
	TArray<float> UpperCurrentBaseBuffer;
	TArray<float> UpperNextBaseBuffer;
	TArray<float> UpperPreviousPublishedStateBuffer;
	TArray<float> UpperPublishedStateBuffer;
	TArray<float> UpperPhysicalStateBuffer;
	TArray<float> UpperPreviousPhysicalStateBuffer;
	TArray<float> PreviousPelvisHeadingBuffer;
	TArray<float> CurrentPelvisHeadingBuffer;
	TArray<FTransform> LocalTransformBuffer;
	TArray<FTransform> PreviousComponentTransformBuffer;
	TArray<FTransform> ComponentTransformBuffer;
	TArray<FTransform> PhysicalTransformBuffer;
	TArray<FTransform> AnimationTransformBuffer;
	TArray<float> AnimationLowerStateBuffer;
	TArray<float> AnimationUpperStateBuffer;
	TArray<float> AnimationFrozenBaseLowerStateBuffer;
	TArray<float> AnimationFrozenBaseUpperStateBuffer;
	TArray<TUniquePtr<FAnimationSamplingContext>> AnimationSamplingContexts;
	TArray<float> InputBuffer;
	TArray<float> OutputBuffer;
	TArray<float> WalkOutputBuffer;
	TArray<float> UpperInputBuffer;
	TArray<float> UpperOutputBuffer;
	FPolicyModel Model;
	FPolicyModel WalkModel;
	FPolicyModel UpperModel;
	TUniquePtr<FSlashNative> SlashModel;
	TArray<float> SlashInputBuffer;
	TArray<float> SlashOutputBuffer;
	TArray<float> SlashSeedInput;
	TArray<int32> SlashBodyIndices;
	TMap<FName, TArray<float>> SlashLabels;
	TMap<FName, int32> SlashTailSteps;
	FMat3f SlashRootRotation;
	FVector3f SlashRootPosition = FVector3f::ZeroVector;
	bool bSlashInitialized = false;
	FStats Stats;
	uint64 CompletedPhysicalSamples = 0;
	uint64 FailedPhysicalSamples = 0;
	// Native work records are prepared on GT. Workers touch only their own record
	// and fixed agent-index output slices; the model/layout data is read-only.
	struct FPhysicalFeedbackWorkItem
	{
		TConstArrayView<FTransform> ActualTransforms;
		float* Sample = nullptr;
		float* Previous = nullptr;
		float* Current = nullptr;
		float* PreviousPhysical = nullptr;
		float* UpperSample = nullptr;
		float* UpperCurrent = nullptr;
		float* UpperPrevious = nullptr;
		float* UpperPreviousPhysical = nullptr;
		float* UpperCurrentBase = nullptr;
		float* PreviousPelvisHeading = nullptr;
		float* CurrentPelvisHeading = nullptr;
		FPhysicalFeedbackTolerance LowerTolerances[7];
		FPhysicalFeedbackTolerance UpperCoreTolerances[10];
		FPhysicalFeedbackTolerance UpperEndTolerances[2];
		FPhysicalFeedbackTolerance UpperStartTolerances[2];
		bool bUseWalkPolicy = false;
		bool bHasPhysicalSample = false;
		bool bSucceeded = false;
	};
	TArray<FPhysicalFeedbackWorkItem> PhysicalFeedbackWorkItems;
	TArray<int32> PhysicalFeedbackIndices;
	uint64 PreparedPhysicalSamples = 0;
	uint64 PreparedPhysicalBatches = 0;

	struct FPinningDebug
	{
		TWeakObjectPtr<AProphecyAgent> Owner;
		FProphecyFootPinningSample Locomotion, Attack, Frozen;
	};
	TMap<int32, FPinningDebug> PinningDebug;
	float AccumulatedStepSeconds = 0.0f;
	float VisualPoseAlpha = 0.0f;
	bool bInitialized = false;
	bool bLastOverlayEnabled = false;
	TWeakObjectPtr<UAnimSequenceBase> LastOverlayAnimation;
	TWeakObjectPtr<APlayerController> SimpleTestPlayerController;
	float LastOverlayBlendSeconds = -1.0f;
	float LastOverlayPlayRate = -1.0f;
	FPlatformMemory::FSharedMemoryRegion* BridgeRegion = nullptr;
	FProcHandle BridgeProcess;
	prophecy::bridge::SharedState* BridgeState = nullptr;
	TArray<prophecy::bridge::AgentState> BridgeFrame;
	int32 LastSimSequence = 0;
	bool bReceivedBridgeFrame = false;
	bool bBridgeFailureLogged = false;
	int32 PlayerGeneration = 1;
	bool bWalkPinLegacy = true;
	bool bSimpleLocomotionTest = false;
	bool bSimpleUsesPlacedAgent = false;
	bool bAbsoluteMotionAudit = false;
	bool bAbsoluteMotionAuditWalk = false;
	bool bAbsoluteMotionAuditExit = false;
	bool bAbsoluteMotionAuditCanCapture = false;
	bool bAbsoluteMotionAuditWritten = false;
	int32 AbsoluteMotionReferenceFrame = 1;
	int32 AbsoluteMotionSampleCount = 0;
	float AbsoluteMotionLastRenderedPhase = 1.0f;
	float AbsoluteMotionRenderHz = 120.0f;
	FString AbsoluteMotionCsv;

	FLimb BlendLimb(int32 I,float W) const
	{
		if (W>=1.f) return WalkLimbs[I];
		auto L=Limbs[I];
		if (W>0.f)
		{
			for (int32 A=0;A<2;++A) L.LocalPoleAxes[A]=SafeNormal(FMath::Lerp(L.LocalPoleAxes[A],WalkLimbs[I].LocalPoleAxes[A],W));
			L.ToeOffset=FMath::Lerp(L.ToeOffset,WalkLimbs[I].ToeOffset,W);
			L.ToeAxis=SafeNormal(FMath::Lerp(L.ToeAxis,WalkLimbs[I].ToeAxis,W));
		}
		return L;
	}
	FFootAxes BuildFootAxes(int32 LimbIndex, const FVector3f& FootPos, const FMat3f& FootRot, float ToeFloat, bool bWalkPolicy = false) const
	{
		const FLimb& Limb = bWalkPolicy ? WalkLimbs[LimbIndex] : Limbs[LimbIndex];
		return BuildFootAxes(Limb, FootPos, FootRot, ToeFloat);
	}

	FFootAxes BuildFootAxes(const FLimb& Limb, const FVector3f& FootPos, const FMat3f& FootRot, float ToeFloat) const
	{
		const FVector3f ToePos = FootPos + TransformRow(Limb.ToeOffset, FootRot);
		FVector3f FootUp = FootRot.Rows[0];
		FVector3f FootForward = FootRot.Rows[1];
		const FVector3f FootSide = FootRot.Rows[2];
		const FVector3f ToeVector = ToePos - FootPos;
		if (FVector3f::DotProduct(FootForward, ToeVector) < 0.0f) FootForward *= -1.0f;
		if (FootUp.Z < 0.0f) FootUp *= -1.0f;

		const FVector3f FootCenter = ToePos - FootForward * FootHalfDims.X + FootUp * SoleVerticalOffset;
		const FMat3f ToeHinge = AxisAngleMatrix(Limb.ToeAxis, FMath::Clamp(ToeFloat, -1.0f, 1.0f) * ToeAlphaRadians);
		const FMat3f ToeRot = Multiply(ToeHinge, FootRot);
		FVector3f ToeForward = ToeRot.Rows[0];
		FVector3f ToeUp = ToeRot.Rows[1];
		const FVector3f ToeSide = ToeRot.Rows[2];
		if (FVector3f::DotProduct(ToeForward, ToeVector) < 0.0f) ToeForward *= -1.0f;
		if (ToeUp.Z < 0.0f) ToeUp *= -1.0f;
		const FVector3f ToeCenter = ToePos + ToeForward * ToeHalfDims.X + ToeUp * SoleVerticalOffset;

		return { FootCenter, FootForward, FootSide, FootUp, ToeCenter, ToeForward, ToeSide, ToeUp };
	}

	float LowestFootPointZ(int32 LimbIndex, const FVector3f& FootPos, const FMat3f& FootRot, float ToeFloat, bool bWalkPolicy = false) const
	{
		const FFootAxes Axes = BuildFootAxes(LimbIndex, FootPos, FootRot, ToeFloat, bWalkPolicy);
		const FVector3f FootPoint = BoxContact(Axes.FootCenter, Axes.FootForward, Axes.FootSide, Axes.FootUp, FootHalfDims, SideBlendRadians);
		const FVector3f ToePoint = BoxContact(Axes.ToeCenter, Axes.ToeForward, Axes.ToeSide, Axes.ToeUp, ToeHalfDims, SideBlendRadians);
		return FMath::Min(FootPoint.Z, ToePoint.Z);
	}

	float LowestFootHeight(int32 LimbIndex, const FVector3f& FootPos, const FMat3f& FootRot, float ToeFloat, bool bWalkPolicy = false) const
	{
		return FMath::Max(0.0f, LowestFootPointZ(LimbIndex, FootPos, FootRot, ToeFloat, bWalkPolicy) - GroundHeight);
	}

	FVector3f IntegratedFootRollDelta(
		int32 LimbIndex,
		const FMat3f& CurRot,
		float CurToe,
		const FMat3f& PredRot,
		float PredToe,
		bool bWalkPolicy = false) const
	{
		const FVector3f RotationVector = RotationVectorBetween(CurRot, PredRot);
		const float RotationAngle = RotationVector.Size();
		const FVector3f RotationAxis = SafeNormal(RotationVector);
		FVector3f TotalDelta = FVector3f::ZeroVector;
		FMat3f PreviousRot = CurRot;
		float PreviousToe = CurToe;

		for (int32 Step = 1; Step <= FootRollSteps; ++Step)
		{
			const float T = float(Step) / float(FootRollSteps);
			const FMat3f StepRot = Multiply(AxisAngleMatrix(RotationAxis, RotationAngle * T), CurRot);
			const float StepToe = FMath::Lerp(CurToe, PredToe, T);
			const FFootAxes NextAxes = BuildFootAxes(LimbIndex, FVector3f::ZeroVector, StepRot, StepToe, bWalkPolicy);
			FVector3f NextFootSupport;
			FVector3f NextToeSupport;
			const FVector3f NextFootPoint = BoxContact(NextAxes.FootCenter, NextAxes.FootForward, NextAxes.FootSide, NextAxes.FootUp, FootHalfDims, SideBlendRadians, &NextFootSupport);
			const FVector3f NextToePoint = BoxContact(NextAxes.ToeCenter, NextAxes.ToeForward, NextAxes.ToeSide, NextAxes.ToeUp, ToeHalfDims, SideBlendRadians, &NextToeSupport);

			const FFootAxes PreviousAxes = BuildFootAxes(LimbIndex, FVector3f::ZeroVector, PreviousRot, PreviousToe, bWalkPolicy);
			const FVector3f PreviousFootPoint = BoxPointWithSupport(PreviousAxes.FootCenter, PreviousAxes.FootForward, PreviousAxes.FootSide, PreviousAxes.FootUp, NextFootSupport);
			const FVector3f PreviousToePoint = BoxPointWithSupport(PreviousAxes.ToeCenter, PreviousAxes.ToeForward, PreviousAxes.ToeSide, PreviousAxes.ToeUp, NextToeSupport);
			TotalDelta += NextToePoint.Z < NextFootPoint.Z ? PreviousToePoint - NextToePoint : PreviousFootPoint - NextFootPoint;
			PreviousRot = StepRot;
			PreviousToe = StepToe;
		}
		return TotalDelta;
	}
};

#include "ProphecyEditorAttackCache.inl"
#include "ProphecyAttackCheckpointState.inl"

namespace
{
	FVector3f ReadStateVec3(const float* State, int32 Offset)
	{
		return FVector3f(State[Offset], State[Offset + 1], State[Offset + 2]);
	}

	void WriteStateVec3(float* State, int32 Offset, const FVector3f& Value)
	{
		State[Offset] = Value.X;
		State[Offset + 1] = Value.Y;
		State[Offset + 2] = Value.Z;
	}

	FVector LowerPointToWorld(const FVector3f& Point, const FMat3f& SeedRootRotation,
		const FVector3f& Root, float Yaw)
	{
		// Lower pose coordinates are Z-up; root trajectories are training Y-up.
		// Match LowerTransformToHeading before applying the root's world yaw.
		return TrainingToUnreal(Root + TransformRow(TransformRow(Point, SeedRootRotation), Transpose(YawMatrix(Yaw))));
	}

	void CleanState(float* State, const AProphecyNNLocomotionManager::FImpl& Impl)
	{
		for (const int32 RotOffset : { 3, 12, 18, 28, 34 })
		{
			const FMat3f Rot = MatrixFromRot6(State + RotOffset);
			WriteRot6(Rot, State + RotOffset);
		}
		State[24] = FMath::Clamp(State[24], -1.0f, 1.0f);
		State[40] = FMath::Clamp(State[40], -1.0f, 1.0f);
	}

	void RebaseStateRoot(
		float* State,
		const AProphecyNNLocomotionManager::FImpl& Impl,
		const FVector3f& ToRootDeltaInFromRoot,
		float ToRootYawDelta)
	{
		const FMat3f FromRoot = Impl.SeedRootRot;
		const FMat3f ToRoot = Multiply(FromRoot, YawMatrix(-ToRootYawDelta));
		const FMat3f ToRootInverse = Transpose(ToRoot);
		for (const int32 PosOffset : { 0, 9, 25 })
		{
			const FVector3f World = TransformRow(ReadStateVec3(State, PosOffset), FromRoot);
			WriteStateVec3(State, PosOffset, TransformRow(World - ToRootDeltaInFromRoot, ToRootInverse));
		}
		for (const int32 RotOffset : { 3, 12, 18, 28, 34 })
		{
			const FMat3f Rebased = Multiply(Multiply(MatrixFromRot6(State + RotOffset), FromRoot), ToRootInverse);
			WriteRot6(Rebased, State + RotOffset);
		}
		CleanState(State, Impl);
	}

	void ConfigureAgentAnimUpdateRate(FAnimUpdateRateParameters* Parameters)
	{
		if (Parameters)
		{
			// UE's default is 4 and its interpolation test is strict (<), so a
			// visible rate-4 mesh freezes for three frames. Preserve URO's skipped
			// evaluations but interpolate those cached poses on the skipped frames.
			Parameters->MaxEvalRateForInterpolation = FMath::Max(
				Parameters->MaxEvalRateForInterpolation,
				5);
		}
	}

	float* StateSlice(TArray<float>& Buffer, int32 AgentIndex)
	{
		return Buffer.GetData() + AgentIndex * StateDim;
	}

	const float* StateSlice(const TArray<float>& Buffer, int32 AgentIndex)
	{
		return Buffer.GetData() + AgentIndex * StateDim;
	}

	float* UpperStateSlice(TArray<float>& Buffer, int32 AgentIndex)
	{
		return Buffer.GetData() + AgentIndex * UpperStateDim;
	}

	const float* UpperStateSlice(const TArray<float>& Buffer, int32 AgentIndex)
	{
		return Buffer.GetData() + AgentIndex * UpperStateDim;
	}

	float* TransformStateSlice(TArray<float>& Buffer, int32 AgentIndex)
	{
		return Buffer.GetData() + AgentIndex * 9;
	}

	const float* TransformStateSlice(const TArray<float>& Buffer, int32 AgentIndex)
	{
		return Buffer.GetData() + AgentIndex * 9;
	}

	TArrayView<FTransform> TransformSlice(TArray<FTransform>& Buffer, int32 AgentIndex)
	{
		return MakeArrayView(
			Buffer.GetData() + AgentIndex * FullBodyBoneCount,
			FullBodyBoneCount);
	}

	void CleanUpperState(float* State)
	{
		for (int32 Offset = 0; Offset < 60; Offset += 6)
		{
			WriteRot6(MatrixFromRot6(State + Offset), State + Offset);
		}
		for (const int32 Offset : { 63, 69, 78, 84 })
		{
			WriteRot6(MatrixFromRot6(State + Offset), State + Offset);
		}
	}

	void LowerTransformToHeading(
		const float* LowerState,
		int32 PositionOffset,
		int32 RotationOffset,
		const AProphecyNNLocomotionManager::FImpl& Impl,
		float* OutTransform)
	{
		WriteStateVec3(
			OutTransform,
			0,
			TransformRow(ReadStateVec3(LowerState, PositionOffset), Impl.SeedRootRot));
		WriteRot6(
			Multiply(MatrixFromRot6(LowerState + RotationOffset), Impl.SeedRootRot),
			OutTransform + 3);
	}

	void BuildUpperBaseFromLower(
		const float* LowerState,
		const AProphecyNNLocomotionManager::FImpl& Impl,
		float* OutUpper)
	{
		FMemory::Memzero(OutUpper, UpperStateDim * sizeof(float));
		for (int32 Offset = 0; Offset < 60; Offset += 6)
		{
			OutUpper[Offset] = 1.0f;
			OutUpper[Offset + 4] = 1.0f;
		}
		const FVector3f PelvisPosition = ReadStateVec3(LowerState, 0);
		const FMat3f PelvisRotation = MatrixFromRot6(LowerState + 3);
		const FMat3f PelvisHeadingRotation = Multiply(PelvisRotation, Impl.SeedRootRot);
		for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
		{
			const int32 Offset = 60 + ArmIndex * 15;
			const int32 HandIndex = Impl.UpperArms[ArmIndex].End;
			const FVector3f HandPositionRoot = PelvisPosition +
				TransformRow(Impl.RestOffsetsFromPelvis[HandIndex], PelvisRotation);
			WriteStateVec3(OutUpper, Offset, TransformRow(HandPositionRoot, Impl.SeedRootRot));
			WriteRot6(PelvisHeadingRotation, OutUpper + Offset + 3);
			WriteRot6(PelvisHeadingRotation, OutUpper + Offset + 9);
		}
		CleanUpperState(OutUpper);
	}

	// Startup only. Keep the network's neutral FK base unchanged: this authored
	// idle is the initial recurrent pose, not a change to the checkpoint's features.
	void SeedUpperIdleFromLower(const float* LowerState,
		const AProphecyNNLocomotionManager::FImpl& Impl, float* OutUpper)
	{
		const float* Idle = ProphecyUpperIdleSeed::PelvisLocal;
		FMemory::Memcpy(OutUpper, Idle, 60 * sizeof(float));
		const FVector3f PelvisPosition = TransformRow(ReadStateVec3(LowerState, 0), Impl.SeedRootRot);
		const FMat3f PelvisRotation = Multiply(MatrixFromRot6(LowerState + 3), Impl.SeedRootRot);
		for (int32 Offset : {60, 75})
		{
			WriteStateVec3(OutUpper, Offset, PelvisPosition + TransformRow(ReadStateVec3(Idle, Offset), PelvisRotation));
			WriteRot6(Multiply(MatrixFromRot6(Idle + Offset + 3), PelvisRotation), OutUpper + Offset + 3);
			WriteRot6(Multiply(MatrixFromRot6(Idle + Offset + 9), PelvisRotation), OutUpper + Offset + 9);
		}
		CleanUpperState(OutUpper);
	}

	void RebaseUpperHeadingState(
		float* State,
		const FVector3f& ToRootDeltaInFromHeading,
		float ToRootYawDelta)
	{
		const FMat3f ToHeading = YawMatrix(-ToRootYawDelta);
		const FMat3f ToHeadingInverse = Transpose(ToHeading);
		for (const int32 Offset : { 60, 75 })
		{
			WriteStateVec3(
				State,
				Offset,
				TransformRow(
					ReadStateVec3(State, Offset) - ToRootDeltaInFromHeading,
					ToHeadingInverse));
			WriteRot6(
				Multiply(MatrixFromRot6(State + Offset + 3), ToHeadingInverse),
				State + Offset + 3);
			WriteRot6(
				Multiply(MatrixFromRot6(State + Offset + 9), ToHeadingInverse),
				State + Offset + 9);
		}
		CleanUpperState(State);
	}

	const FPhysicalFeedbackTolerance& FeedbackToleranceForBone(
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		FName BoneName)
	{
		static const FPhysicalFeedbackTolerance ZeroTolerance;
		const FPhysicalFeedbackTolerance* Found = Agent.PhysicalFeedbackTolerances.Find(BoneName);
		return Found ? *Found : ZeroTolerance;
	}

	AProphecyNNLocomotionManager::FImpl::FAnimationSamplingContext*
	FindOrCreateAnimationSamplingContext(
		AProphecyNNLocomotionManager::FImpl& Impl,
		USkeletalMesh* Mesh)
	{
		if (!Mesh)
		{
			return nullptr;
		}
		for (const TUniquePtr<AProphecyNNLocomotionManager::FImpl::FAnimationSamplingContext>& Context :
			Impl.AnimationSamplingContexts)
		{
			if (Context && Context->Mesh.Get() == Mesh)
			{
				return Context.Get();
			}
		}

		TUniquePtr<AProphecyNNLocomotionManager::FImpl::FAnimationSamplingContext> Context =
			MakeUnique<AProphecyNNLocomotionManager::FImpl::FAnimationSamplingContext>();
		Context->Mesh = Mesh;
		const int32 BoneCount = Mesh->GetRefSkeleton().GetNum();
		Context->RequiredBoneIndices.SetNumUninitialized(BoneCount);
		for (int32 BoneIndex = 0; BoneIndex < BoneCount; ++BoneIndex)
		{
			Context->RequiredBoneIndices[BoneIndex] = BoneIndex;
		}
		Context->RequiredBones.InitializeTo(
			Context->RequiredBoneIndices,
			UE::Anim::FCurveFilterSettings(UE::Anim::ECurveFilterMode::DisallowAll),
			*Mesh);
		Context->CompactComponentTransforms.SetNumUninitialized(
			Context->RequiredBones.GetCompactPoseNumBones());
		for (int32 BodyIndex = 0; BodyIndex < FullBodyBoneCount; ++BodyIndex)
		{
			const int32 MeshBoneIndex = Context->RequiredBones.GetPoseBoneIndexForBoneName(
				Impl.BodyNames[BodyIndex]);
			if (MeshBoneIndex == INDEX_NONE)
			{
				return nullptr;
			}
			const FCompactPoseBoneIndex CompactIndex = Context->RequiredBones.MakeCompactPoseIndex(
				FMeshPoseBoneIndex(MeshBoneIndex));
			if (!CompactIndex.IsValid())
			{
				return nullptr;
			}
			Context->BodyCompactPoseIndices[BodyIndex] = CompactIndex.GetInt();
		}
		return Impl.AnimationSamplingContexts.Add_GetRef(MoveTemp(Context)).Get();
	}

	bool SampleAnimationComponentPose(
		AProphecyNNLocomotionManager::FImpl& Impl,
		USkeletalMesh* Mesh,
		UAnimSequenceBase* Animation,
		float PlaybackTimeSeconds,
		bool bLoop,
		TArrayView<FTransform> OutBodyComponentTransforms)
	{
		if (!Mesh || !Animation || OutBodyComponentTransforms.Num() != FullBodyBoneCount ||
			Animation->GetSkeleton() != Mesh->GetSkeleton())
		{
			return false;
		}
		AProphecyNNLocomotionManager::FImpl::FAnimationSamplingContext* Context =
			FindOrCreateAnimationSamplingContext(Impl, Mesh);
		if (!Context)
		{
			return false;
		}

		FCompactPose Pose;
		Pose.SetBoneContainer(&Context->RequiredBones);
		FBlendedCurve Curve;
		Curve.InitFrom(Context->RequiredBones);
		UE::Anim::FStackAttributeContainer Attributes;
		FAnimationPoseData PoseData(Pose, Curve, Attributes);
		Animation->GetAnimationPose(
			PoseData,
			FAnimExtractContext(double(PlaybackTimeSeconds), false, {}, bLoop));

		const int32 CompactBoneCount = Context->RequiredBones.GetCompactPoseNumBones();
		for (int32 CompactIndexValue = 0; CompactIndexValue < CompactBoneCount; ++CompactIndexValue)
		{
			const FCompactPoseBoneIndex CompactIndex(CompactIndexValue);
			const FCompactPoseBoneIndex ParentIndex =
				Context->RequiredBones.GetParentBoneIndex(CompactIndex);
			FTransform& Component = Context->CompactComponentTransforms[CompactIndexValue];
			Component = ParentIndex.IsValid()
				? Pose[CompactIndex] * Context->CompactComponentTransforms[ParentIndex.GetInt()]
				: Pose[CompactIndex];
			Component.NormalizeRotation();
		}

		const FTransform RootComponent = Context->CompactComponentTransforms[0];
		for (int32 BodyIndex = 0; BodyIndex < FullBodyBoneCount; ++BodyIndex)
		{
			OutBodyComponentTransforms[BodyIndex] =
				Context->CompactComponentTransforms[Context->BodyCompactPoseIndices[BodyIndex]]
					.GetRelativeTransform(RootComponent);
			OutBodyComponentTransforms[BodyIndex].NormalizeRotation();
		}
		return true;
	}

	void EncodeComponentPoseToNNStates(
		const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		TArrayView<const FTransform> ComponentTransforms,
		float* OutLowerState,
		float* OutUpperState)
	{
		const FTransform& Pelvis = ComponentTransforms[0];
		WriteStateVec3(OutLowerState, 0, LocalUnrealToTraining(Pelvis.GetTranslation()));
		WriteRot6(MirrorYBasis(QuatToMatrix(Pelvis.GetRotation())), OutLowerState + 3);
		const int32 PositionOffsets[2] = { 9, 25 };
		const int32 RotationOffsets[2] = { 12, 28 };
		const int32 StartRotationOffsets[2] = { 18, 34 };
		const int32 ToeOffsets[2] = { 24, 40 };
		for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
		{
			const AProphecyNNLocomotionManager::FImpl::FLimb& Limb = Agent.bUseWalkPolicy
				? Impl.WalkLimbs[LimbIndex]
				: Impl.Limbs[LimbIndex];
			const FMat3f ThighRotation = MirrorYBasis(
				QuatToMatrix(ComponentTransforms[Limb.Start].GetRotation()));
			const FMat3f FootRotation = MirrorYBasis(
				QuatToMatrix(ComponentTransforms[Limb.End].GetRotation()));
			const FMat3f ToeRotation = MirrorYBasis(
				QuatToMatrix(ComponentTransforms[Limb.Toe].GetRotation()));
			WriteStateVec3(
				OutLowerState,
				PositionOffsets[LimbIndex],
				LocalUnrealToTraining(ComponentTransforms[Limb.End].GetTranslation()));
			WriteRot6(FootRotation, OutLowerState + RotationOffsets[LimbIndex]);
			WriteRot6(ThighRotation, OutLowerState + StartRotationOffsets[LimbIndex]);
			const FVector3f ToeRotationVector = RotationVectorBetween(
				FMat3f(),
				Multiply(ToeRotation, Transpose(FootRotation)));
			OutLowerState[ToeOffsets[LimbIndex]] = FMath::Clamp(
				FVector3f::DotProduct(ToeRotationVector, SafeNormal(Limb.ToeAxis)) /
					ToeAlphaRadians,
				-1.0f,
				1.0f);
		}
		CleanState(OutLowerState, Impl);

		FMemory::Memzero(OutUpperState, UpperStateDim * sizeof(float));
		for (int32 CoreIndex = 0; CoreIndex < Impl.UpperCoreBoneNames.Num(); ++CoreIndex)
		{
			const int32 BodyIndex = Impl.BodyNames.IndexOfByKey(Impl.UpperCoreBoneNames[CoreIndex]);
			const int32 ParentIndex = Impl.Parents[BodyIndex];
			const FMat3f BodyRotation = MirrorYBasis(
				QuatToMatrix(ComponentTransforms[BodyIndex].GetRotation()));
			const FMat3f ParentRotation = MirrorYBasis(
				QuatToMatrix(ComponentTransforms[ParentIndex].GetRotation()));
			WriteRot6(
				Multiply(BodyRotation, Transpose(ParentRotation)),
				OutUpperState + CoreIndex * 6);
		}
		for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
		{
			const AProphecyNNLocomotionManager::FImpl::FUpperArm& Arm = Impl.UpperArms[ArmIndex];
			const int32 Offset = 60 + ArmIndex * 15;
			WriteStateVec3(
				OutUpperState,
				Offset,
				TransformRow(
					LocalUnrealToTraining(ComponentTransforms[Arm.End].GetTranslation()),
					Impl.SeedRootRot));
			WriteRot6(
				Multiply(
					MirrorYBasis(QuatToMatrix(ComponentTransforms[Arm.End].GetRotation())),
					Impl.SeedRootRot),
				OutUpperState + Offset + 3);
			WriteRot6(
				Multiply(
					MirrorYBasis(QuatToMatrix(ComponentTransforms[Arm.Start].GetRotation())),
					Impl.SeedRootRot),
				OutUpperState + Offset + 9);
		}
		CleanUpperState(OutUpperState);
	}

	// These raw encoders stay at their original positions around the unchanged tolerance stages.
	void EncodePhysicalLowerSample(const AProphecyNNLocomotionManager::FImpl& Impl,
		bool bUseWalkPolicy,
		TConstArrayView<FTransform> ActualTransforms, FSampledTrainingRotations& TrainingRotations, float* Sample)
	{
		using FImpl = AProphecyNNLocomotionManager::FImpl;
		const FTransform& Pelvis = ActualTransforms[0];
		WriteStateVec3(Sample, 0, LocalUnrealToTraining(Pelvis.GetTranslation()));
		WriteRot6(TrainingRotations.Get(0), Sample + 3);

		const int32 PosOffsets[2] = { 9, 25 };
		const int32 RotOffsets[2] = { 12, 28 };
		const int32 StartRotOffsets[2] = { 18, 34 };
		const int32 ToeOffsets[2] = { 24, 40 };
		for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
		{
			const FImpl::FLimb& RuntimeLimb = bUseWalkPolicy ? Impl.WalkLimbs[LimbIndex] : Impl.Limbs[LimbIndex];
			const FMat3f ThighRotation = TrainingRotations.Get(RuntimeLimb.Start);
			const FMat3f FootRotation = TrainingRotations.Get(RuntimeLimb.End);
			const FMat3f ToeRotation = TrainingRotations.Get(RuntimeLimb.Toe);
			WriteStateVec3(Sample, PosOffsets[LimbIndex], LocalUnrealToTraining(ActualTransforms[RuntimeLimb.End].GetTranslation()));
			WriteRot6(FootRotation, Sample + RotOffsets[LimbIndex]);
			WriteRot6(ThighRotation, Sample + StartRotOffsets[LimbIndex]);

			const FMat3f ToeRelative = Multiply(ToeRotation, Transpose(FootRotation));
			const FVector3f ToeRotationVector = RotationVectorBetween(FMat3f(), ToeRelative);
			Sample[ToeOffsets[LimbIndex]] = FMath::Clamp(
				FVector3f::DotProduct(ToeRotationVector, SafeNormal(RuntimeLimb.ToeAxis)) / ToeAlphaRadians,
				-1.0f,
				1.0f);
		}
		CleanState(Sample, Impl);
	}

	void EncodePhysicalLowerSample(const AProphecyNNLocomotionManager::FImpl& Impl,
		const AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		TConstArrayView<FTransform> ActualTransforms, FSampledTrainingRotations& TrainingRotations, float* Sample)
	{
		EncodePhysicalLowerSample(Impl, Agent.bUseWalkPolicy, ActualTransforms, TrainingRotations, Sample);
	}

	void EncodePhysicalUpperSample(const AProphecyNNLocomotionManager::FImpl& Impl,
		TConstArrayView<FTransform> ActualTransforms, FSampledTrainingRotations& TrainingRotations, float* UpperSample)
	{
		using FImpl = AProphecyNNLocomotionManager::FImpl;
		FMemory::Memzero(UpperSample, UpperStateDim * sizeof(float));
		for (int32 CoreIndex = 0; CoreIndex < Impl.UpperCoreBoneNames.Num(); ++CoreIndex)
		{
			const int32 BodyIndex = Impl.BodyNames.IndexOfByKey(Impl.UpperCoreBoneNames[CoreIndex]);
			const int32 ParentIndex = Impl.Parents[BodyIndex];
			const FMat3f BodyRotation = TrainingRotations.Get(BodyIndex);
			const FMat3f ParentRotation = TrainingRotations.Get(ParentIndex);
			WriteRot6(Multiply(BodyRotation, Transpose(ParentRotation)), UpperSample + CoreIndex * 6);
		}
		for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
		{
			const FImpl::FUpperArm& Arm = Impl.UpperArms[ArmIndex];
			const int32 Offset = 60 + ArmIndex * 15;
			WriteStateVec3(
				UpperSample,
				Offset,
				TransformRow(
					LocalUnrealToTraining(ActualTransforms[Arm.End].GetTranslation()),
					Impl.SeedRootRot));
			WriteRot6(
				Multiply(
					TrainingRotations.Get(Arm.End),
					Impl.SeedRootRot),
				UpperSample + Offset + 3);
			WriteRot6(
				Multiply(
					TrainingRotations.Get(Arm.Start),
					Impl.SeedRootRot),
				UpperSample + Offset + 9);
		}
		CleanUpperState(UpperSample);
	}

#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyNNPhysicalRotationCacheTests.inl"
#include "Tests/ProphecyWalkPinningSpaceTests.inl"
#endif

#include "ProphecyNNLowerFeedbackAlignment.inl"
#include "ProphecyNNPhysicalFeedbackBatch.inl"
#if WITH_DEV_AUTOMATION_TESTS
#include "Tests/ProphecyNNPhysicalFeedbackBatchTests.inl"
#endif

	void BlendStateVector(float* State, const float* Target, int32 Offset, float Weight)
	{
		WriteStateVec3(
			State,
			Offset,
			FMath::Lerp(ReadStateVec3(State, Offset), ReadStateVec3(Target, Offset), Weight));
	}

	void BlendStateRotation(float* State, const float* Target, int32 Offset, float Weight)
	{
		FQuat From = MatrixToQuat(MatrixFromRot6(State + Offset)).GetNormalized();
		FQuat To = MatrixToQuat(MatrixFromRot6(Target + Offset)).GetNormalized();
		if ((From | To) < 0.0f)
		{
			To = To * -1.0f;
		}
		WriteRot6(QuatToMatrix(FQuat::Slerp(From, To, Weight).GetNormalized()), State + Offset);
	}

	void BlendLowerPolicyRegion(float* State,const float* Walk,int32 Offset,float W)
	{
		if (W==0.f) return;
		if (W==1.f)
		{ FMemory::Memcpy(State+Offset,Walk+Offset,(Offset==0 ? 9 : 16)*sizeof(float));return; }
		BlendStateVector(State,Walk,Offset,W);BlendStateRotation(State,Walk,Offset+3,W);
		if (Offset!=0)
		{
			BlendStateRotation(State,Walk,Offset+9,W);
			State[Offset+15]=FMath::Lerp(State[Offset+15],Walk[Offset+15],W);
		}
	}

    void OverrideRecoveryFootRotations(const float* Current,const float* RunRaw,const float* WalkRaw,
        const FVector2f& Weights,float* State)
    {
        for (int32 I=0;I<2;++I)
        {
            const float W=Weights[I];if (W<0) continue;
            const int32 O=12+16*I;
            float Walk[6],Run[6];
            for (int32 J=0;J<6;++J) Walk[J]=Current[O+J]+WalkRaw[O+J];
            if (W>=1.f) { FMemory::Memcpy(State+O,Walk,sizeof(Walk));continue; }
            for (int32 J=0;J<6;++J) Run[J]=Current[O+J]+RunRaw[O+J];
            const FQuat R=MatrixToQuat(MatrixFromRot6(Run)),Q=MatrixToQuat(MatrixFromRot6(Walk));
            WriteRot6(QuatToMatrix(FQuat::Slerp(R,Q,W).GetNormalized()),State+O);
        }
    }

#include "Tests/ProphecyNNRecoveryFootRotationTests.inl"
	float SmoothUnitAlpha(float Alpha)
	{
		return FMath::SmoothStep(0.0f, 1.0f, FMath::Clamp(Alpha, 0.0f, 1.0f));
	}

#include "ProphecyLowerTempering.inl"
#include "ProphecyKneeStanceTests.inl"
#include "Tests/ProphecyKneeSourceHeadingTests.inl"

	void UpdateRouteIntent(
		AProphecyNNLocomotionManager::FImpl::FAgent& Agent,
		float SpeedMetersPerSecond,
		float ArrivalRadiusMeters)
	{
		const FVector3f Target = Agent.TargetIndex == 0 ? Agent.RouteA : Agent.RouteB;
		FVector3f ToTarget = Target - Agent.CurRootPos;
		ToTarget.Y = 0.0f;
		if (ToTarget.SizeSquared() <= ArrivalRadiusMeters * ArrivalRadiusMeters)
		{
			Agent.TargetIndex = 1 - Agent.TargetIndex;
			ToTarget = (Agent.TargetIndex == 0 ? Agent.RouteA : Agent.RouteB) - Agent.CurRootPos;
			ToTarget.Y = 0.0f;
		}

		const double DesiredYaw = FMath::Atan2(ToTarget.X, ToTarget.Z);
		const double RelativeDirection = prophecy::sim::SignedAngleDelta(
			Agent.MoverState.yaw_radians, DesiredYaw);
		Agent.MoverIntent.mode = SpeedMetersPerSecond > 2.01f
			? prophecy::sim::LocomotionMode::Run
			: prophecy::sim::LocomotionMode::Walk;
		Agent.MoverIntent.speed_direction_radians = RelativeDirection;
		Agent.MoverIntent.speed_amplitude = FMath::Clamp(
			double(SpeedMetersPerSecond) /
				prophecy::sim::DirectionalSpeedCap(Agent.MoverIntent.mode, RelativeDirection),
			0.0,
			1.0);
		Agent.MoverIntent.orientation_yaw_radians = DesiredYaw;
		Agent.MoverIntent.speed_scale = 1.0;
		Agent.MoverIntent.turn_scale = 1.0;
	}
}

AProphecyNNLocomotionManager::AProphecyNNLocomotionManager()
{
	PrimaryActorTick.bCanEverTick = true;
	AgentClass = AProphecyAgent::StaticClass();
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	Impl = new FImpl();
}

AProphecyNNLocomotionManager::~AProphecyNNLocomotionManager()
{
	delete Impl;
	Impl = nullptr;
}

void AProphecyNNLocomotionManager::ConfigureSimpleLocomotionTest()
{
	Impl->bSimpleLocomotionTest = true;
	bSimBridge = false;
	bClampCalf = true;
	CalfClampLengthMultiplier = 1.0f;
	CrowdSize = 1;
	InitialPhysicalAgentCount = 0;
	AgentSpeedCmPerSecond = 200.0f;
}

bool AProphecyNNLocomotionManager::SetPhysicalFeedbackExecutionMode(int32 Mode)
{
	if (!IsInGameThread() || HasActorBegunPlay() || Mode < 0 || Mode > 2) return false;
	PhysicalFeedbackExecutionMode = Mode;
	return true;
}

void AProphecyNNLocomotionManager::BeginPlay()
{
	Super::BeginPlay();
	if (GetWorld() && GetWorld()->GetMapName().Contains(TEXT("locomotion"), ESearchCase::IgnoreCase))
	{
		ConfigureSimpleLocomotionTest();
	}
	// Collect once at startup, before seed/root initialization. Reuse the existing
	// actor array so each placed pawn gets its own batch lane and pose-store ID.
	if (Impl->bSimpleLocomotionTest)
	{
		if (IsValid(PlayerAgent) && PlayerAgent->GetWorld() == GetWorld())
		{
			AgentActors.Add(PlayerAgent);
		}
		for (TActorIterator<AProphecyAgent> It(GetWorld()); It; ++It)
		{
			AProphecyAgent* Candidate = *It;
			if (Candidate->bManualNNPoseApplication && Candidate->bAutoEnsureStandaloneNNManager &&
				!Candidate->HasValidAgentHandle() && Candidate->GetOwner() != this)
			{
				AgentActors.AddUnique(Candidate);
				if (!IsValid(PlayerAgent) && Candidate->AutoPossessPlayer != EAutoReceiveInput::Disabled)
				{
					PlayerAgent = Candidate;
				}
			}
		}
		if (IsValid(PlayerAgent))
		{
			const int32 PlayerIndex = AgentActors.IndexOfByKey(PlayerAgent);
			if (PlayerIndex != INDEX_NONE) AgentActors.Swap(0, PlayerIndex);
		}
		if (AgentActors.Num() > BatchSize)
		{
			UE_LOG(LogProphecyNNLocomotion, Error,
				TEXT("Only %d placed agents fit in the NN batch; %d cannot be registered."),
				BatchSize, AgentActors.Num() - BatchSize);
			AgentActors.SetNum(BatchSize);
		}
	}
	Impl->bSimpleUsesPlacedAgent = !AgentActors.IsEmpty();
	const AProphecyAgent* WalkPolicyAgent = IsValid(PlayerAgent) ? PlayerAgent.Get() : nullptr;
	if (!WalkPolicyAgent && !AgentActors.IsEmpty()) WalkPolicyAgent = AgentActors[0];
	if (!WalkPolicyAgent && AgentClass)
	{
		WalkPolicyAgent = AgentClass->GetDefaultObject<AProphecyAgent>();
	}
	bool bUseJuly5WalkFineTune = false;
	bool bUseJuly5WalkBestCheckpoint = false;
	if (WalkPolicyAgent)
	{
		if (const FBoolProperty* PolicyProperty = FindFProperty<FBoolProperty>(
			WalkPolicyAgent->GetClass(), TEXT("UseJuly5WalkFineTune")))
		{
			bUseJuly5WalkFineTune = PolicyProperty->GetPropertyValue_InContainer(WalkPolicyAgent);
		}
		if (const FBoolProperty* BestProperty = FindFProperty<FBoolProperty>(
			WalkPolicyAgent->GetClass(), TEXT("UseJuly5WalkBestCheckpoint")))
		{
			bUseJuly5WalkBestCheckpoint = BestProperty->GetPropertyValue_InContainer(WalkPolicyAgent);
		}
	}
	if (bUseJuly5WalkFineTune)
	{
		WalkOnnxModelPath = bUseJuly5WalkBestCheckpoint
			? TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_best_b100.onnx")
			: TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_b100.onnx");
		WalkRuntimeContractPath = bUseJuly5WalkBestCheckpoint
			? TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_best_runtime.json")
			: TEXT("Content/locomotion/NN/prophecy_lower_body_walk_july5_runtime.json");
	}
	Impl->bAbsoluteMotionAudit = Impl->bSimpleLocomotionTest &&
		FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNAbsoluteMotionAudit"));
	Impl->bAbsoluteMotionAuditWalk = Impl->bAbsoluteMotionAudit &&
		FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNAuditWalk"));
	Impl->bAbsoluteMotionAuditExit = Impl->bAbsoluteMotionAudit &&
		FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNAuditExit"));
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNAuditRenderHz="), Impl->AbsoluteMotionRenderHz);
	Impl->AbsoluteMotionRenderHz = FMath::Max(1.0f, Impl->AbsoluteMotionRenderHz);
	if (Impl->bAbsoluteMotionAudit)
	{
		AgentSpeedCmPerSecond = Impl->bAbsoluteMotionAuditWalk ? 200.0f : 500.0f;
	}
	// Normal play keeps the project's fixed game clock. Only the explicit motion
	// audit selects its own rate; disabling fixed time here made physics stiffness
	// change with render-frame duration despite the configured 60 Hz game clock.
	if (GEngine && Impl->bAbsoluteMotionAudit)
	{
		GEngine->bSmoothFrameRate = false;
		GEngine->bUseFixedFrameRate = true;
		GEngine->FixedFrameRate = Impl->AbsoluteMotionRenderHz;
		GEngine->SetMaxFPS(0.0f);
	}
	if (IConsoleVariable* VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync")))
	{
		VSync->Set(0, ECVF_SetByCode);
	}
	if (IConsoleVariable* SyncInterval = IConsoleManager::Get().FindConsoleVariable(TEXT("rhi.SyncInterval")))
	{
		SyncInterval->Set(0, ECVF_SetByCode);
	}
	if (IConsoleVariable* IdleWhenNotForeground = IConsoleManager::Get().FindConsoleVariable(TEXT("t.IdleWhenNotForeground")))
	{
		IdleWhenNotForeground->Set(0, ECVF_SetByCode);
	}
	CrowdSize = FMath::Clamp(CrowdSize, 1, BatchSize);
	NNUpdateHz = FMath::Max(1.0f, NNUpdateHz);
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNLocomotionCrowd="), CrowdSize);
	CrowdSize = FMath::Clamp(FMath::Max(CrowdSize, AgentActors.Num()), 1, BatchSize);
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNLocomotionRuntime="), PreferredRuntime);
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNAgentSpeedCmPerSecond="), AgentSpeedCmPerSecond);
	if (Impl->bAbsoluteMotionAudit)
	{
		AgentSpeedCmPerSecond = Impl->bAbsoluteMotionAuditWalk ? 200.0f : 500.0f;
	}
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNPhysicalAgents="), InitialPhysicalAgentCount);
	InitialPhysicalAgentCount = FMath::Clamp(InitialPhysicalAgentCount, 0, CrowdSize);
	int32 InitialPhysicalMACD = bInitialPhysicalAgentsUseMACD ? 1 : 0;
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNPhysicalMACD="), InitialPhysicalMACD);
	bInitialPhysicalAgentsUseMACD = InitialPhysicalMACD != 0;
	FString PhysicalDriveOverride;
	if (FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNPhysicalDrive="), PhysicalDriveOverride))
	{
		if (PhysicalDriveOverride.Equals(TEXT("Torque"), ESearchCase::IgnoreCase) ||
			PhysicalDriveOverride.Equals(TEXT("RootAndJointTorque"), ESearchCase::IgnoreCase))
		{
			InitialPhysicalDriveMode = EProphecyAgentPhysicalDriveMode::RootAndJointTorque;
		}
		else if (PhysicalDriveOverride.Equals(TEXT("World"), ESearchCase::IgnoreCase) ||
			PhysicalDriveOverride.Equals(TEXT("PerBodyWorld"), ESearchCase::IgnoreCase))
		{
			InitialPhysicalDriveMode = EProphecyAgentPhysicalDriveMode::PerBodyWorld;
		}
		else
		{
			UE_LOG(LogProphecyNNLocomotion, Warning,
				TEXT("Unknown ProphecyNNPhysicalDrive='%s'; retaining configured drive mode."),
				*PhysicalDriveOverride);
		}
	}

	FString OverlayPath;
	if (FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNOverlayAnimation="), OverlayPath))
	{
		OverlayAnimation = LoadObject<UAnimSequenceBase>(nullptr, *OverlayPath);
		bOverlayEnabled = OverlayAnimation != nullptr;
	}

	ResolveRouteEndpoints();
	// Route endpoint lookup must not change authored collision settings. The legacy
	// default names (Cube/Cube2) also match ordinary obstacles placed in the level.
	if (!LoadRuntimeContract())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("NN locomotion manager failed to initialize."));
		SetActorTickEnabled(false);
		return;
	}
	if (!LoadWalkRuntimeContract())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Walk NN locomotion contract failed to load."));
		SetActorTickEnabled(false);
		return;
	}
	if (!LoadUpperRuntimeContract())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Upper NN locomotion contract failed to load."));
		SetActorTickEnabled(false);
		return;
	}
	int32 FootRollStepsOverride = FootRollIntegrationSteps;
	if (FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNFootRollSteps="), FootRollStepsOverride))
	{
		FootRollIntegrationSteps = FMath::Clamp(FootRollStepsOverride, 0, 1024);
	}
	Impl->FootRollSteps = FMath::Clamp(FootRollIntegrationSteps, 0, 1024);
	if (!InitializeNNE())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("NN locomotion manager failed to initialize."));
		SetActorTickEnabled(false);
		return;
	}
	if (!InitializeWalkNNE())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Walk NN locomotion model failed to initialize."));
		SetActorTickEnabled(false);
		return;
	}
	if (!InitializeUpperNNE())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Upper NN locomotion model failed to initialize."));
		SetActorTickEnabled(false);
		return;
	}
	if (!ValidateUpperNNE())
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Upper NN locomotion startup parity audit failed."));
		SetActorTickEnabled(false);
		return;
	}

#if WITH_EDITOR
	// Debug Play pays cold model creation before gameplay, never on the first hit.
	if (ProphecyEditorAttackCache::Uses(this) && !InitializeSlashNNE())
		UE_LOG(LogProphecyNNLocomotion, Warning, TEXT("Editor attack warmup failed; attacks retain their normal validation path."));
#endif
	InitializeAgents();
	if (bSpawnVisuals) SpawnVisualComponents();
	if (Impl->bSimpleLocomotionTest) InitializeSimpleTestPlayerView();
	if (IsValid(PlayerAgent) && Impl->bSimpleUsesPlacedAgent)
	{
		PlayerAgent->bIsPlayer = true;
	}
	else if (IsValid(PlayerAgent))
	{
		PlayerAgent->bIsPlayer = true;
		FProphecyAgentHandle PlayerHandle;
		PlayerHandle.Index = CrowdSize;
		PlayerHandle.Generation = Impl->PlayerGeneration;
		PlayerAgent->SetAgentHandle(PlayerHandle);
	}
	const double Now = GetWorld() ? double(GetWorld()->GetTimeSeconds()) : 0.0;
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex) PublishAgentPose(AgentIndex, Now);
	const bool bBridgeStarted = bSimBridge && StartSimBridge();
	if (bBridgeStarted)
	{
		for (AProphecyAgent* AgentActor : AgentActors)
		{
			if (IsValid(AgentActor)) AgentActor->SetActorHiddenInGame(true);
		}
	}
	else
	{
		UpdateVisualRoots();
	}
	if (InitialPhysicalAgentCount > AgentActors.Num())
	{
		UE_LOG(LogProphecyNNLocomotion, Warning,
			TEXT("Requested %d Physical agents, but only %d valid agent shells were spawned."),
			InitialPhysicalAgentCount, AgentActors.Num());
		InitialPhysicalAgentCount = AgentActors.Num();
	}
	for (int32 AgentIndex = 0; AgentIndex < InitialPhysicalAgentCount; ++AgentIndex)
	{
		AgentActors[AgentIndex]->SetMACDEnabled(bInitialPhysicalAgentsUseMACD);
		if (!SetAgentSimulationMode(GetAgentHandle(AgentIndex), EProphecyAgentSimulationMode::Physical))
		{
			UE_LOG(LogProphecyNNLocomotion, Warning, TEXT("Agent %d could not enter physical mode."), AgentIndex);
		}
	}
	UpdateOverlaySettings();
	Impl->bInitialized = true;
	if (Impl->bAbsoluteMotionAudit)
	{
		Impl->AbsoluteMotionReferenceFrame = 1;
		Impl->AbsoluteMotionSampleCount = 0;
		Impl->AbsoluteMotionLastRenderedPhase = 1.0f;
		Impl->bAbsoluteMotionAuditCanCapture = false;
		Impl->bAbsoluteMotionAuditWritten = false;
		Impl->AbsoluteMotionCsv = TEXT("phase,game_time_s,root_x_cm,root_y_cm,root_z_cm");
		for (const FName BoneName : Impl->PublishedBoneNames)
		{
			const FString Name = BoneName.ToString();
			Impl->AbsoluteMotionCsv += FString::Printf(
				TEXT(",%s_x_cm,%s_y_cm,%s_z_cm"),
				*Name, *Name, *Name);
		}
		Impl->AbsoluteMotionCsv += LINE_TERMINATOR;
	}

	UE_LOG(LogProphecyNNLocomotion, Display,
		TEXT("NN locomotion started: crowd=%d rate=%.1fHz run_runtime=%s walk_runtime=%s upper_runtime=%s gpu=%d foot_roll_steps=%d physical_agents=%d physical_macd=%d physical_drive=%s endpoints=(%.0f,%.0f)->(%.0f,%.0f)"),
		CrowdSize, NNUpdateHz, *Impl->Model.RuntimeUsed, *Impl->WalkModel.RuntimeUsed,
		*Impl->UpperModel.RuntimeUsed,
		(Impl->Model.bGpu || Impl->WalkModel.bGpu || Impl->UpperModel.bGpu) ? 1 : 0,
		Impl->FootRollSteps, InitialPhysicalAgentCount, bInitialPhysicalAgentsUseMACD ? 1 : 0,
		InitialPhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque ? TEXT("torque") : TEXT("world"),
		EndpointAFallback.X, EndpointAFallback.Y, EndpointBFallback.X, EndpointBFallback.Y);
}

void AProphecyNNLocomotionManager::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	ProphecyAgentTime::Remove(this);
    ProphecyDefenseArmedGate::RemoveManager(this);
    AlignedLowerFeedbackBatches.Remove(this);
	ProphecyAttackCamera::End(this);
	ResolvedMoverTargets.Remove(this);
	ClearInitialAgentResetState();
	StopSimBridge();
	Impl->SimpleTestPlayerController.Reset();
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		FProphecyNNPoseStore::ClearAgentPose(PoseStoreAgentBase + AgentIndex);
	}
	for (AProphecyAgent* AgentActor : AgentActors)
	{
		ProphecySwordAttackCollision::End(AgentActor);
		ProphecyDefenseControls::Remove(AgentActor);
		SlashRootMinusStartPelvis.Remove(AgentActor);
		ProphecyNNRootWindow::Remove(AgentActor);
		ProphecyUpperRootHorizon::Remove(AgentActor);
		ProphecyRootBalance::Remove(AgentActor);
		ProphecyRootPelvisBounds::Remove(AgentActor);
		ProphecyRootMagic::Remove(AgentActor);
		ProphecyAutoRun::Remove(AgentActor);
		ProphecyAttackRecovery::Remove(AgentActor);
		ProphecyHandRecovery::Remove(AgentActor);
		ProphecyCoreTempering::Remove(AgentActor);
		ProphecySlashReturn::Remove(AgentActor);
		ProphecyUpperBodyInertia::Remove(AgentActor);
		ProphecyAttackStartInertia::Remove(AgentActor);
		ProphecyLowerTempering::ForgetProfiles(AgentActor);
		ProphecyLegChainDebug::Remove(AgentActor);
		ProphecyRootSpeedLimits::Remove(AgentActor);
		RootYawImpulseAgents.Remove(AgentActor);
		ProphecyRootFacing::Explicit(AgentActor);
		RootImpulseSmoothingYaw.Remove(AgentActor);
		if (IsValid(AgentActor) &&
			AgentActor->GetOwner() == this &&
			!AgentActor->IsActorBeingDestroyed())
		{
			AgentActor->Destroy();
		}
	}
	AgentActors.Reset();
	MeshComponents.Reset();
	ProphecyAttackCheckpoint::Clear(this);
#if WITH_EDITOR
	ProphecyEditorAttackCache::Release(this,Impl->SlashModel,Impl->bSlashInitialized);
	Impl->bSlashInitialized=false;
#endif
	Super::EndPlay(EndPlayReason);
}

void AProphecyNNLocomotionManager::Tick(float DeltaSeconds)
{
	ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerTick);
	Super::Tick(DeltaSeconds);
	if (!Impl->bInitialized) return;
	if (Impl->bAbsoluteMotionAudit) CaptureAbsoluteMotionAuditFrame();
	if (Impl->bAbsoluteMotionAudit)
	{
		AgentSpeedCmPerSecond = Impl->bAbsoluteMotionAuditWalk ? 200.0f : 500.0f;
	}
	// Camera setup is independent of locomotion input. A controller may arrive
	// after BeginPlay; do not restore native keyboard polling to handle that case.
	if (Impl->bSimpleLocomotionTest && !Impl->SimpleTestPlayerController.IsValid())
	{
		InitializeSimpleTestPlayerView();
	}
	if (IsSimBridgeActive())
	{
		ConsumeSimBridgeFrame();
		if (IsSimBridgeActive() && !Impl->bReceivedBridgeFrame)
		{
			Impl->AccumulatedStepSeconds = 0.0f;
			UpdateOverlaySettings();
			return;
		}
	}

	const float StepSeconds = 1.0f / NNUpdateHz;
	if (ProphecyAgentTime::HasClocks(this) && !IsSimBridgeActive())
	{
		ProphecyAgentTime::Advance(this,DeltaSeconds,StepSeconds,BatchSize,MaxCatchUpStepsPerTick,
			Impl->AccumulatedStepSeconds,GetWorld()?double(GetWorld()->GetTimeSeconds()):0.,
			[&](ProphecyAgentTime::FStep& Event)
		{
			StepSimulation(StepSeconds);
			for (int32 I=0;I<CrowdSize;++I) if (Event.Due[I])
				PublishAgentPose(I,FMath::Max(Event.SourceTimeSeconds,Impl->Agents[I].PublishedPoseTimeSeconds+1.e-6));
		});
		Impl->VisualPoseAlpha=ProphecyNNPresentation::FromRemainder(Impl->AccumulatedStepSeconds,StepSeconds);
	}
	else
	{
	Impl->AccumulatedStepSeconds += DeltaSeconds;
	int32 Steps = 0;
	while (Impl->AccumulatedStepSeconds >= StepSeconds && Steps < MaxCatchUpStepsPerTick)
	{
		StepSimulation(StepSeconds);
		Impl->AccumulatedStepSeconds -= StepSeconds;
		++Steps;
	}
	if (Steps == MaxCatchUpStepsPerTick && Impl->AccumulatedStepSeconds >= StepSeconds)
	{
		Impl->AccumulatedStepSeconds = FMath::Fmod(Impl->AccumulatedStepSeconds, StepSeconds);
	}
	Impl->VisualPoseAlpha = ProphecyNNPresentation::FromRemainder(Impl->AccumulatedStepSeconds, StepSeconds);
	if (Steps > 0)
	{
		const bool bWarmed = Impl->Stats.bCollecting;
		const double Start = FPlatformTime::Seconds();
		const double PoseSourceTime = GetWorld()
			? double(GetWorld()->GetTimeSeconds()) - double(Impl->AccumulatedStepSeconds)
			: 0.0;
		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			PublishAgentPose(AgentIndex, PoseSourceTime);
		}
		if (bWarmed) Impl->Stats.StoreSeconds += FPlatformTime::Seconds() - Start;
	}
	}
	UpdateVisualRoots();
    if(ProphecyWalkPinning::AnyTickPinning()) UpdateWalkTickPinning(DeltaSeconds);
	ProphecyRootPelvisBounds::Apply(*this);
	const APlayerController* CameraController = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
	AProphecyAgent* CameraPawn = CameraController ? Cast<AProphecyAgent>(CameraController->GetPawn()) : nullptr;
	const FProphecyAgentHandle CameraHandle = CameraPawn ? CameraPawn->GetAgentHandle() : FProphecyAgentHandle{};
	const bool bOwnsCameraPawn = CameraPawn && ResolveAgent(CameraHandle) == CameraPawn;
	const bool bFollowAttack = bOwnsCameraPawn && ((Impl->Agents[CameraHandle.Index].Slash.bActive &&
		!Impl->Agents[CameraHandle.Index].Slash.bHalf) || Impl->Agents[CameraHandle.Index].DefensePose);
	ProphecyAttackCamera::Update(this, CameraPawn, bFollowAttack);
	// Debug meshes are passive poseable renderers owned by the manager. Update
	// them only after the authoritative pose/root publication is complete; they
	// have no AnimInstance, component tick, collision, or dependency edge back to
	// the agent that authors PrePhysics forces.
	for (int32 AgentIndex = 0; AgentIndex < AgentActors.Num(); ++AgentIndex)
	{
		AProphecyAgent* AgentActor = AgentActors[AgentIndex];
		if (!AgentActor)
		{
			continue;
		}
		const FName DebugMeshName = ProphecyCrowd::KinematicDebugMeshName(AgentIndex);
		UPoseableMeshComponent* DebugMesh = FindObjectFast<UPoseableMeshComponent>(
			this, DebugMeshName);
		if (!AgentActor->bShowKinematicDebugMesh)
		{
			if (IsValid(DebugMesh))
			{
				RemoveInstanceComponent(DebugMesh);
				DebugMesh->Rename(
					nullptr,
					GetTransientPackage(),
					REN_DontCreateRedirectors | REN_ForceNoResetLoaders);
				DebugMesh->DestroyComponent();
			}
			continue;
		}
		if (!IsValid(DebugMesh))
		{
			USkeletalMeshComponent* PoseReferenceMesh = AgentActor->GetPoseReferenceMesh();
			USkeletalMeshComponent* AgentMesh = AgentActor->GetAgentMesh();
			if (!PoseReferenceMesh || !PoseReferenceMesh->GetSkeletalMeshAsset() || !AgentMesh)
			{
				continue;
			}
			DebugMesh = NewObject<UPoseableMeshComponent>(this, DebugMeshName);
			AddInstanceComponent(DebugMesh);
			DebugMesh->SetupAttachment(AgentActor->GetAgentCapsule());
			DebugMesh->SetRelativeTransform(AgentMesh->GetRelativeTransform());
			DebugMesh->SetSkinnedAssetAndUpdate(PoseReferenceMesh->GetSkeletalMeshAsset(), false);
			DebugMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			DebugMesh->SetGenerateOverlapEvents(false);
			DebugMesh->SetCanEverAffectNavigation(false);
			DebugMesh->SetCastShadow(false);
			DebugMesh->SetReceivesDecals(false);
			DebugMesh->SetAffectDistanceFieldLighting(false);
			DebugMesh->SetAffectDynamicIndirectLighting(false);
			DebugMesh->SetVisibleInRayTracing(false);
			DebugMesh->RegisterComponent();
			DebugMesh->SetComponentTickEnabled(false);
		}

		TArray<FName> BoneNames;
		TArray<FTransform> FutureWorldTransforms;
		TArray<FTransform> InterpolatedWorldTransforms;
		float InterpolationAlpha = 1.0f;
		if (!AgentActor->ReadNNFutureWorldPose(
			BoneNames, FutureWorldTransforms, InterpolatedWorldTransforms,
			InterpolationAlpha))
		{
			continue;
		}
		const USkinnedAsset* DebugAsset = DebugMesh->GetSkinnedAsset();
		if (!DebugAsset)
		{
			continue;
		}
		const FReferenceSkeleton& ReferenceSkeleton = DebugAsset->GetRefSkeleton();
		const TArray<FTransform>& ReferenceLocalPose = ReferenceSkeleton.GetRefBonePose();
		if (DebugMesh->BoneSpaceTransforms.Num() != ReferenceSkeleton.GetNum())
		{
			continue;
		}
		TArray<FTransform, TInlineAllocator<128>> ComponentPose;
		ComponentPose.SetNumUninitialized(ReferenceSkeleton.GetNum());
		const FTransform DebugComponentWorld = DebugMesh->GetComponentTransform();
		for (int32 BoneIndex = 0; BoneIndex < ReferenceSkeleton.GetNum(); ++BoneIndex)
		{
			const int32 ParentIndex = ReferenceSkeleton.GetParentIndex(BoneIndex);
			const int32 TargetIndex = BoneNames.IndexOfByKey(
				ReferenceSkeleton.GetBoneName(BoneIndex));
			if (InterpolatedWorldTransforms.IsValidIndex(TargetIndex))
			{
				ComponentPose[BoneIndex] = InterpolatedWorldTransforms[TargetIndex]
					.GetRelativeTransform(DebugComponentWorld);
			}
			else
			{
				ComponentPose[BoneIndex] = ParentIndex != INDEX_NONE
					? ReferenceLocalPose[BoneIndex] * ComponentPose[ParentIndex]
					: ReferenceLocalPose[BoneIndex];
			}
			DebugMesh->BoneSpaceTransforms[BoneIndex] = ParentIndex != INDEX_NONE
				? ComponentPose[BoneIndex].GetRelativeTransform(ComponentPose[ParentIndex])
				: ComponentPose[BoneIndex];
		}
		DebugMesh->RefreshBoneTransforms();
	}
	if (bShowFutureRootDebug) DrawFutureRootDebug();
	if (IsSimBridgeActive() && Impl->bReceivedBridgeFrame)
	{
		PublishUnrealBridgeFrame();
	}
	UpdateOverlaySettings();
	LogBenchmark(DeltaSeconds);
	if (Impl->bAbsoluteMotionAudit) UpdateAbsoluteMotionAuditPhase();
}

bool AProphecyNNLocomotionManager::LoadRuntimeContract()
{
	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *ResolveProjectPath(RuntimeContractPath))) return false;
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid()) return false;

	double Number = 0.0;
	if (!Root->TryGetNumberField(TEXT("batch_size"), Number) || int32(Number) != BatchSize ||
		!Root->TryGetNumberField(TEXT("input_dim"), Number) || int32(Number) != InputDim ||
		!Root->TryGetNumberField(TEXT("model_output_dim"), Number) || int32(Number) != PolicyOutputDim ||
		!Root->TryGetNumberField(TEXT("state_dim"), Number) || int32(Number) != StateDim)
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Runtime contract dimensions do not match the native lower-body runtime."));
		return false;
	}

	Root->TryGetNumberField(TEXT("max_speed_scale_final"), Impl->MaxSpeedScaleFinal);
	Root->TryGetNumberField(TEXT("max_turn_rate_scale_final"), Impl->MaxTurnRateScaleFinal);
	Root->TryGetNumberField(TEXT("pose_delta_scale_final"), Impl->PoseDeltaScaleFinal);

	const TArray<TSharedPtr<FJsonValue>>* BodyValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ParentValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* OffsetValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* PhaseValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("body_names"), BodyValues) || !Root->TryGetArrayField(TEXT("parents_body"), ParentValues) ||
		!Root->TryGetArrayField(TEXT("local_offsets_m"), OffsetValues) || !Root->TryGetArrayField(TEXT("seed_phase_states"), PhaseValues)) return false;

	Impl->BodyNames.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *BodyValues) Impl->BodyNames.Add(FName(Value->AsString()));
	Impl->Parents.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *ParentValues) Impl->Parents.Add(int32(Value->AsNumber()));
	Impl->LocalOffsets.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *OffsetValues)
	{
		FVector3f Vec;
		if (!JsonVec3(Value->AsArray(), Vec)) return false;
		Impl->LocalOffsets.Add(Vec);
	}
	Impl->SeedPhaseStates.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *PhaseValues)
	{
		TArray<float> State;
		if (!JsonFloatArray(Value->AsArray(), State) || State.Num() != StateDim) return false;
		Impl->SeedPhaseStates.Add(MoveTemp(State));
	}

	const TArray<TSharedPtr<FJsonValue>>* RootRotValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("seed_root_rotation_rows"), RootRotValues) || RootRotValues->Num() != 3) return false;
	for (int32 Row = 0; Row < 3; ++Row)
	{
		if (!JsonVec3((*RootRotValues)[Row]->AsArray(), Impl->SeedRootRot.Rows[Row])) return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* LimbValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* LengthValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* PoleValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ToeOffsetValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ToeAxisValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("ik_limb_specs"), LimbValues) || LimbValues->Num() != 2 ||
		!Root->TryGetArrayField(TEXT("ik_limb_lengths_m"), LengthValues) || !Root->TryGetArrayField(TEXT("ik_local_pole_axes"), PoleValues) ||
		!Root->TryGetArrayField(TEXT("ik_toe_offsets_m"), ToeOffsetValues) || !Root->TryGetArrayField(TEXT("ik_toe_axes"), ToeAxisValues)) return false;

	for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
	{
		const TSharedPtr<FJsonObject> LimbObject = (*LimbValues)[LimbIndex]->AsObject();
		FImpl::FLimb& Limb = Impl->Limbs[LimbIndex];
		Limb.Start = int32(LimbObject->GetNumberField(TEXT("start")));
		Limb.Mid = int32(LimbObject->GetNumberField(TEXT("mid")));
		Limb.End = int32(LimbObject->GetNumberField(TEXT("end")));
		Limb.Toe = int32(LimbObject->GetNumberField(TEXT("toe")));
		const TArray<TSharedPtr<FJsonValue>>& Lengths = (*LengthValues)[LimbIndex]->AsArray();
		Limb.Lengths = FVector2f(float(Lengths[0]->AsNumber()), float(Lengths[1]->AsNumber()));
		const TArray<TSharedPtr<FJsonValue>>& Poles = (*PoleValues)[LimbIndex]->AsArray();
		if (!JsonVec3(Poles[0]->AsArray(), Limb.LocalPoleAxes[0]) || !JsonVec3(Poles[1]->AsArray(), Limb.LocalPoleAxes[1]) ||
			!JsonVec3((*ToeOffsetValues)[LimbIndex]->AsArray(), Limb.ToeOffset) || !JsonVec3((*ToeAxisValues)[LimbIndex]->AsArray(), Limb.ToeAxis)) return false;
	}

	const TSharedPtr<FJsonObject>* FootRoll = nullptr;
	if (!Root->TryGetObjectField(TEXT("foot_roll"), FootRoll)) return false;
	if (!JsonVec3((*FootRoll)->GetArrayField(TEXT("foot_half_dims_m")), Impl->FootHalfDims) ||
		!JsonVec3((*FootRoll)->GetArrayField(TEXT("toe_half_dims_m")), Impl->ToeHalfDims)) return false;
	(*FootRoll)->TryGetNumberField(TEXT("sole_vertical_offset_m"), Impl->SoleVerticalOffset);
	float SideBlendDegrees = 8.0f;
	(*FootRoll)->TryGetNumberField(TEXT("side_blend_deg"), SideBlendDegrees);
	Impl->SideBlendRadians = FMath::DegreesToRadians(SideBlendDegrees);
	(*FootRoll)->TryGetNumberField(TEXT("pin_ste_scale"), Impl->PinScale);
	(*FootRoll)->TryGetNumberField(TEXT("ground_y"), Impl->GroundHeight);
	(*FootRoll)->TryGetNumberField(TEXT("near_floor_full_height_m"), Impl->NearFloorFullHeight);
	(*FootRoll)->TryGetNumberField(TEXT("near_floor_fade_height_m"), Impl->NearFloorFadeHeight);
	(*FootRoll)->TryGetNumberField(TEXT("near_floor_minimum_pin_probability"), Impl->NearFloorMinPin);
	if ((*FootRoll)->TryGetNumberField(TEXT("integration_steps"), Number)) Impl->FootRollSteps = FMath::Max(1, int32(Number));

	Impl->PublishedBoneNames = Impl->BodyNames;
	return Impl->BodyNames.Num() == 25 && Impl->Parents.Num() == 25 && Impl->LocalOffsets.Num() == 25 && Impl->SeedPhaseStates.Num() >= 2;
}

bool AProphecyNNLocomotionManager::LoadWalkRuntimeContract()
{
	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *ResolveProjectPath(WalkRuntimeContractPath))) return false;
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid()) return false;

	double Number = 0.0;
	if (!Root->TryGetNumberField(TEXT("batch_size"), Number) || int32(Number) != BatchSize ||
		!Root->TryGetNumberField(TEXT("input_dim"), Number) || int32(Number) != InputDim ||
		!Root->TryGetNumberField(TEXT("model_output_dim"), Number) || int32(Number) != PolicyOutputDim ||
		!Root->TryGetNumberField(TEXT("state_dim"), Number) || int32(Number) != StateDim)
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* BodyValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ParentValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* OffsetValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* PhaseValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("body_names"), BodyValues) ||
		!Root->TryGetArrayField(TEXT("parents_body"), ParentValues) ||
		!Root->TryGetArrayField(TEXT("local_offsets_m"), OffsetValues) ||
		!Root->TryGetArrayField(TEXT("seed_phase_states"), PhaseValues) ||
		BodyValues->Num() != Impl->BodyNames.Num() || ParentValues->Num() != Impl->Parents.Num()) return false;
	for (int32 Index = 0; Index < BodyValues->Num(); ++Index)
	{
		if (FName((*BodyValues)[Index]->AsString()) != Impl->BodyNames[Index] ||
			int32((*ParentValues)[Index]->AsNumber()) != Impl->Parents[Index]) return false;
	}

	Impl->WalkLocalOffsets.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *OffsetValues)
	{
		FVector3f Vec;
		if (!JsonVec3(Value->AsArray(), Vec)) return false;
		Impl->WalkLocalOffsets.Add(Vec);
	}
	Impl->WalkSeedPhaseStates.Reset();
	for (const TSharedPtr<FJsonValue>& Value : *PhaseValues)
	{
		TArray<float> State;
		if (!JsonFloatArray(Value->AsArray(), State) || State.Num() != StateDim) return false;
		Impl->WalkSeedPhaseStates.Add(MoveTemp(State));
	}

	const TArray<TSharedPtr<FJsonValue>>* LimbValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* LengthValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* PoleValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ToeOffsetValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ToeAxisValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("ik_limb_specs"), LimbValues) || LimbValues->Num() != 2 ||
		!Root->TryGetArrayField(TEXT("ik_limb_lengths_m"), LengthValues) ||
		!Root->TryGetArrayField(TEXT("ik_local_pole_axes"), PoleValues) ||
		!Root->TryGetArrayField(TEXT("ik_toe_offsets_m"), ToeOffsetValues) ||
		!Root->TryGetArrayField(TEXT("ik_toe_axes"), ToeAxisValues)) return false;
	for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
	{
		const TSharedPtr<FJsonObject> LimbObject = (*LimbValues)[LimbIndex]->AsObject();
		FImpl::FLimb& Limb = Impl->WalkLimbs[LimbIndex];
		Limb.Start = int32(LimbObject->GetNumberField(TEXT("start")));
		Limb.Mid = int32(LimbObject->GetNumberField(TEXT("mid")));
		Limb.End = int32(LimbObject->GetNumberField(TEXT("end")));
		Limb.Toe = int32(LimbObject->GetNumberField(TEXT("toe")));
		const TArray<TSharedPtr<FJsonValue>>& Lengths = (*LengthValues)[LimbIndex]->AsArray();
		Limb.Lengths = FVector2f(float(Lengths[0]->AsNumber()), float(Lengths[1]->AsNumber()));
		const TArray<TSharedPtr<FJsonValue>>& Poles = (*PoleValues)[LimbIndex]->AsArray();
		if (!JsonVec3(Poles[0]->AsArray(), Limb.LocalPoleAxes[0]) ||
			!JsonVec3(Poles[1]->AsArray(), Limb.LocalPoleAxes[1]) ||
			!JsonVec3((*ToeOffsetValues)[LimbIndex]->AsArray(), Limb.ToeOffset) ||
			!JsonVec3((*ToeAxisValues)[LimbIndex]->AsArray(), Limb.ToeAxis)) return false;
	}

	const TSharedPtr<FJsonObject>* FootRoll = nullptr;
	if (!Root->TryGetObjectField(TEXT("foot_roll"), FootRoll)) return false;
	FString PinMode;
	if (!(*FootRoll)->TryGetStringField(TEXT("pin_mode"), PinMode)) return false;
	Impl->bWalkPinLegacy = PinMode.Equals(TEXT("legacy_logit_selected"), ESearchCase::CaseSensitive);
	return Impl->bWalkPinLegacy && Impl->WalkLocalOffsets.Num() == 25 && Impl->WalkSeedPhaseStates.Num() >= 2;
}

bool AProphecyNNLocomotionManager::LoadUpperRuntimeContract()
{
	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *ResolveProjectPath(UpperRuntimeContractPath)))
	{
		return false;
	}
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid())
	{
		return false;
	}

	double Number = 0.0;
	if (!Root->TryGetNumberField(TEXT("batch_size"), Number) || int32(Number) != BatchSize ||
		!Root->TryGetNumberField(TEXT("input_dim"), Number) || int32(Number) != UpperInputDim ||
		!Root->TryGetNumberField(TEXT("output_dim"), Number) || int32(Number) != UpperStateDim)
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* BodyValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ParentValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* OffsetValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* CoreValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ArmValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* LengthValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* PoleValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("body_names"), BodyValues) ||
		!Root->TryGetArrayField(TEXT("parents_body"), ParentValues) ||
		!Root->TryGetArrayField(TEXT("local_offsets_m"), OffsetValues) ||
		!Root->TryGetArrayField(TEXT("core_bones"), CoreValues) ||
		!Root->TryGetArrayField(TEXT("arm_specs"), ArmValues) ||
		!Root->TryGetArrayField(TEXT("arm_limb_lengths_m"), LengthValues) ||
		!Root->TryGetArrayField(TEXT("arm_local_pole_axes"), PoleValues) ||
		BodyValues->Num() != FullBodyBoneCount || ParentValues->Num() != FullBodyBoneCount ||
		OffsetValues->Num() != FullBodyBoneCount || CoreValues->Num() != 10 ||
		ArmValues->Num() != 2 || LengthValues->Num() != 2 || PoleValues->Num() != 2)
	{
		return false;
	}
	Impl->UpperLocalOffsets.SetNumUninitialized(FullBodyBoneCount);
	for (int32 Index = 0; Index < FullBodyBoneCount; ++Index)
	{
		FVector3f Offset = FVector3f::ZeroVector;
		if (FName((*BodyValues)[Index]->AsString()) != Impl->BodyNames[Index] ||
			int32((*ParentValues)[Index]->AsNumber()) != Impl->Parents[Index] ||
			!JsonVec3((*OffsetValues)[Index]->AsArray(), Offset))
		{
			return false;
		}
		Impl->UpperLocalOffsets[Index] = Offset;
	}
	Impl->RestOffsetsFromPelvis.SetNumUninitialized(FullBodyBoneCount);
	for (int32 Index = 0; Index < FullBodyBoneCount; ++Index)
	{
		Impl->RestOffsetsFromPelvis[Index] = Index == 0
			? FVector3f::ZeroVector
			: Impl->RestOffsetsFromPelvis[Impl->Parents[Index]] + Impl->UpperLocalOffsets[Index];
	}

	Impl->UpperCoreBoneNames.Reset(10);
	for (const TSharedPtr<FJsonValue>& Value : *CoreValues)
	{
		const FName Name(Value->AsString());
		if (!Impl->BodyNames.Contains(Name))
		{
			return false;
		}
		Impl->UpperCoreBoneNames.Add(Name);
	}
	for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
	{
		const TSharedPtr<FJsonObject> ArmObject = (*ArmValues)[ArmIndex]->AsObject();
		if (!ArmObject.IsValid())
		{
			return false;
		}
		FImpl::FUpperArm& Arm = Impl->UpperArms[ArmIndex];
		Arm.Start = int32(ArmObject->GetNumberField(TEXT("start")));
		Arm.Mid = int32(ArmObject->GetNumberField(TEXT("mid")));
		Arm.End = int32(ArmObject->GetNumberField(TEXT("end")));
		const TArray<TSharedPtr<FJsonValue>>& Lengths = (*LengthValues)[ArmIndex]->AsArray();
		const TArray<TSharedPtr<FJsonValue>>& Poles = (*PoleValues)[ArmIndex]->AsArray();
		if (Lengths.Num() != 2 || Poles.Num() != 2 ||
			!JsonVec3(Poles[0]->AsArray(), Arm.LocalPoleAxes[0]) ||
			!JsonVec3(Poles[1]->AsArray(), Arm.LocalPoleAxes[1]))
		{
			return false;
		}
		Arm.Lengths = FVector2f(float(Lengths[0]->AsNumber()), float(Lengths[1]->AsNumber()));
	}
	return true;
}

bool AProphecyNNLocomotionManager::InitializeNNE()
{
	FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));
	TArray64<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *ResolveProjectPath(OnnxModelPath))) return false;
	ModelData = NewObject<UNNEModelData>(this);
	ModelData->Init(TEXT("onnx"), TConstArrayView64<uint8>(Bytes.GetData(), Bytes.Num()));
	const FString Requested = PreferredRuntime.TrimStartAndEnd();
	if ((Requested.Equals(TEXT("gpu"), ESearchCase::IgnoreCase) || Requested.Equals(TEXT("dml"), ESearchCase::IgnoreCase) || Requested.Equals(TEXT("NNERuntimeORTDml"), ESearchCase::IgnoreCase)) &&
		Impl->Model.CreateGpu(ModelData, TEXT("NNERuntimeORTDml"))) return true;
	if ((Requested.Equals(TEXT("cpu"), ESearchCase::IgnoreCase) || Requested.Equals(TEXT("NNERuntimeORTCpu"), ESearchCase::IgnoreCase)))
		return Impl->Model.CreateCpu(ModelData, TEXT("NNERuntimeORTCpu"));
	if (Impl->Model.CreateGpu(ModelData, Requested) || Impl->Model.CreateCpu(ModelData, Requested)) return true;
	return Impl->Model.CreateCpu(ModelData, TEXT("NNERuntimeORTCpu"));
}

bool AProphecyNNLocomotionManager::InitializeWalkNNE()
{
	FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));
	TArray64<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *ResolveProjectPath(WalkOnnxModelPath))) return false;
	WalkModelData = NewObject<UNNEModelData>(this);
	WalkModelData->Init(TEXT("onnx"), TConstArrayView64<uint8>(Bytes.GetData(), Bytes.Num()));
	const FString Requested = PreferredRuntime.TrimStartAndEnd();
	if ((Requested.Equals(TEXT("gpu"), ESearchCase::IgnoreCase) ||
		Requested.Equals(TEXT("dml"), ESearchCase::IgnoreCase) ||
		Requested.Equals(TEXT("NNERuntimeORTDml"), ESearchCase::IgnoreCase)) &&
		Impl->WalkModel.CreateGpu(WalkModelData, TEXT("NNERuntimeORTDml"))) return true;
	if (Requested.Equals(TEXT("cpu"), ESearchCase::IgnoreCase) ||
		Requested.Equals(TEXT("NNERuntimeORTCpu"), ESearchCase::IgnoreCase))
	{
		return Impl->WalkModel.CreateCpu(WalkModelData, TEXT("NNERuntimeORTCpu"));
	}
	if (Impl->WalkModel.CreateGpu(WalkModelData, Requested) ||
		Impl->WalkModel.CreateCpu(WalkModelData, Requested)) return true;
	return Impl->WalkModel.CreateCpu(WalkModelData, TEXT("NNERuntimeORTCpu"));
}

bool AProphecyNNLocomotionManager::InitializeUpperNNE()
{
	FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));
	TArray64<uint8> Bytes;
	if (!FFileHelper::LoadFileToArray(Bytes, *ResolveProjectPath(UpperOnnxModelPath)))
	{
		return false;
	}
	UpperModelData = NewObject<UNNEModelData>(this);
	UpperModelData->Init(TEXT("onnx"), TConstArrayView64<uint8>(Bytes.GetData(), Bytes.Num()));
	Impl->UpperModel.InputWidth = UpperInputDim;
	const FString Requested = PreferredRuntime.TrimStartAndEnd();
	if ((Requested.Equals(TEXT("gpu"), ESearchCase::IgnoreCase) ||
		Requested.Equals(TEXT("dml"), ESearchCase::IgnoreCase) ||
		Requested.Equals(TEXT("NNERuntimeORTDml"), ESearchCase::IgnoreCase)) &&
		Impl->UpperModel.CreateGpu(UpperModelData, TEXT("NNERuntimeORTDml")))
	{
		return true;
	}
	if (Requested.Equals(TEXT("cpu"), ESearchCase::IgnoreCase) ||
		Requested.Equals(TEXT("NNERuntimeORTCpu"), ESearchCase::IgnoreCase))
	{
		return Impl->UpperModel.CreateCpu(UpperModelData, TEXT("NNERuntimeORTCpu"));
	}
	if (Impl->UpperModel.CreateGpu(UpperModelData, Requested) ||
		Impl->UpperModel.CreateCpu(UpperModelData, Requested))
	{
		return true;
	}
	return Impl->UpperModel.CreateCpu(UpperModelData, TEXT("NNERuntimeORTCpu"));
}

bool AProphecyNNLocomotionManager::ValidateUpperNNE()
{
	FString JsonText;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(JsonText, *ResolveProjectPath(UpperRuntimeContractPath)) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) ||
		!Root.IsValid())
	{
		return false;
	}
	const TSharedPtr<FJsonObject>* Audit = nullptr;
	if (!Root->TryGetObjectField(TEXT("startup_audit"), Audit) || !Audit || !Audit->IsValid())
	{
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* InputValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ExpectedValues = nullptr;
	double MaximumAbsoluteError = 0.0;
	if (!(*Audit)->TryGetArrayField(TEXT("input"), InputValues) ||
		!(*Audit)->TryGetArrayField(TEXT("expected_output"), ExpectedValues) ||
		!(*Audit)->TryGetNumberField(TEXT("maximum_absolute_error"), MaximumAbsoluteError) ||
		InputValues->Num() != UpperInputDim || ExpectedValues->Num() != UpperStateDim)
	{
		return false;
	}
	TArray<float> Input;
	TArray<float> Output;
	Input.SetNumUninitialized(BatchSize * UpperInputDim);
	Output.SetNumZeroed(BatchSize * UpperStateDim);
	for (int32 AgentIndex = 0; AgentIndex < BatchSize; ++AgentIndex)
	{
		float* Row = Input.GetData() + AgentIndex * UpperInputDim;
		for (int32 InputIndex = 0; InputIndex < UpperInputDim; ++InputIndex)
		{
			Row[InputIndex] = float((*InputValues)[InputIndex]->AsNumber());
		}
	}
	if (!Impl->UpperModel.Run(Input, Output))
	{
		return false;
	}
	float MaxError = 0.0f;
	for (int32 OutputIndex = 0; OutputIndex < UpperStateDim; ++OutputIndex)
	{
		const float Expected = float((*ExpectedValues)[OutputIndex]->AsNumber());
		if (!FMath::IsFinite(Output[OutputIndex]) || !FMath::IsFinite(Expected))
		{
			return false;
		}
		MaxError = FMath::Max(MaxError, FMath::Abs(Output[OutputIndex] - Expected));
	}
	if (MaxError > float(MaximumAbsoluteError))
	{
		UE_LOG(LogProphecyNNLocomotion, Error,
			TEXT("Upper NNE startup parity max_abs=%.9g exceeds %.9g."),
			MaxError, MaximumAbsoluteError);
		return false;
	}
	UE_LOG(LogProphecyNNLocomotion, Display,
		TEXT("Upper NNE startup parity passed: max_abs=%.9g tolerance=%.9g."),
		MaxError, MaximumAbsoluteError);
	return true;
}

void AProphecyNNLocomotionManager::ResolveRouteEndpoints()
{
	FVector A = EndpointAFallback;
	FVector B = EndpointBFallback;
	bool bFoundA = false;
	bool bFoundB = false;
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* Actor = *It;
		bool bMatchesA = Actor->GetName().Equals(EndpointAActorName.ToString(), ESearchCase::IgnoreCase);
		bool bMatchesB = Actor->GetName().Equals(EndpointBActorName.ToString(), ESearchCase::IgnoreCase);
#if WITH_EDITOR
		bMatchesA = bMatchesA || Actor->GetActorLabel().Equals(EndpointAActorName.ToString(), ESearchCase::IgnoreCase);
		bMatchesB = bMatchesB || Actor->GetActorLabel().Equals(EndpointBActorName.ToString(), ESearchCase::IgnoreCase);
#endif
		if (bMatchesA && !bFoundA)
		{
			A = Actor->GetActorLocation();
			bFoundA = true;
		}
		if (bMatchesB && !bFoundB)
		{
			B = Actor->GetActorLocation();
			bFoundB = true;
		}
	}
	A.Z = 0.0;
	B.Z = 0.0;
	EndpointAFallback = A;
	EndpointBFallback = B;
	Impl->EndpointA = UnrealToTraining(A);
	Impl->EndpointB = UnrealToTraining(B);
}

void AProphecyNNLocomotionManager::InitializeAgents()
{
	ResolvedMoverTargets.FindOrAdd(this).Init(FResolvedMoverTarget{}, BatchSize);
	Impl->Agents.SetNum(BatchSize);
	Impl->PrevStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->CurStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PreviousPublishedStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PublishedStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->NextStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PhysicalStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PreviousPhysicalStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->UpperPreviousStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperCurrentStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperCurrentBaseBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperNextBaseBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperPreviousPublishedStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperPublishedStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperPhysicalStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->UpperPreviousPhysicalStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->PreviousPelvisHeadingBuffer.SetNumUninitialized(BatchSize * 9);
	Impl->CurrentPelvisHeadingBuffer.SetNumUninitialized(BatchSize * 9);
	Impl->LocalTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);
	Impl->PreviousComponentTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);
	Impl->ComponentTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);
	Impl->PhysicalTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);
	if (PhysicalFeedbackExecutionMode != 0)
	{
		Impl->PhysicalFeedbackWorkItems.SetNum(BatchSize);
		Impl->PhysicalFeedbackIndices.Reserve(BatchSize);
	}
	Impl->AnimationTransformBuffer.SetNumUninitialized(BatchSize * FullBodyBoneCount);
	Impl->AnimationLowerStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->AnimationUpperStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->AnimationFrozenBaseLowerStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->AnimationFrozenBaseUpperStateBuffer.SetNumUninitialized(BatchSize * UpperStateDim);
	Impl->InputBuffer.SetNumZeroed(BatchSize * InputDim);
	Impl->OutputBuffer.SetNumZeroed(BatchSize * PolicyOutputDim);
	Impl->WalkOutputBuffer.SetNumZeroed(BatchSize * PolicyOutputDim);
	Impl->UpperInputBuffer.SetNumZeroed(BatchSize * UpperInputDim);
	Impl->UpperOutputBuffer.SetNumZeroed(BatchSize * UpperStateDim);
	const float StepSeconds = 1.0f / NNUpdateHz;
	const int32 LaneCount = Impl->bSimpleLocomotionTest ? 1 : 10;
	const int32 Rows = FMath::DivideAndRoundUp(BatchSize, LaneCount);
	const FVector3f RouteDirection = SafeNormal(Impl->EndpointB - Impl->EndpointA, FVector3f(0.0f, 0.0f, 1.0f));
	const FVector3f RouteSide = SafeNormal(FVector3f(RouteDirection.Z, 0.0f, -RouteDirection.X), FVector3f(1.0f, 0.0f, 0.0f));

	for (int32 AgentIndex = 0; AgentIndex < BatchSize; ++AgentIndex)
	{
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		const AProphecyAgent* PlacedAgent = AgentActors.IsValidIndex(AgentIndex)
			? AgentActors[AgentIndex].Get() : nullptr;
		Agent.UpperRootRotationHorizon = ProphecyUpperRootHorizon::Configured(PlacedAgent);
		const int32 Lane = AgentIndex % LaneCount;
		const int32 Row = AgentIndex / LaneCount;
		const float LaneOffset = (float(Lane) - float(LaneCount - 1) * 0.5f) * 1.15f;
		const FVector3f Offset = RouteSide * LaneOffset;
		Agent.RouteA = Impl->EndpointA + Offset;
		Agent.RouteB = Impl->EndpointB + Offset;
		const float Phase = Rows > 1 ? float(Row) / float(Rows - 1) : 0.0f;
		Agent.CurRootPos = PlacedAgent
			? UnrealToTraining(PlacedAgent->GetRootLowPoint())
			: FMath::Lerp(Agent.RouteA, Agent.RouteB, Phase);
		Agent.TargetIndex = Row % 2 == 0 ? 1 : 0;
		const FVector3f ToTarget = (Agent.TargetIndex == 0 ? Agent.RouteA : Agent.RouteB) - Agent.CurRootPos;
		Agent.CurRootYaw = PlacedAgent
			? -FMath::DegreesToRadians(float(PlacedAgent->GetActorRotation().Yaw))
			: FMath::Atan2(ToTarget.X, ToTarget.Z);
		const FVector3f Forward(FMath::Sin(Agent.CurRootYaw), 0.0f, FMath::Cos(Agent.CurRootYaw));
		const bool bManualSimpleInput = Impl->bSimpleLocomotionTest && !Impl->bAbsoluteMotionAudit;
		Agent.PrevRootPos = bManualSimpleInput
			? Agent.CurRootPos
			: Agent.CurRootPos - Forward * (AgentSpeedCmPerSecond / MetersToCentimeters) * StepSeconds;
		Agent.PrevRootYaw = Agent.CurRootYaw;
		Agent.PublishedRoot = Agent.CurRootPos;
		Agent.PreviousPublishedRoot = Agent.CurRootPos;
		Agent.PublishedYaw = Agent.CurRootYaw;
		Agent.PreviousPublishedYaw = Agent.CurRootYaw;
		Agent.MoverState.position = { Agent.CurRootPos.X, Agent.CurRootPos.Z };
		const prophecy::sim::Vec2 InitialDirection = prophecy::sim::DirectionFromAngle(Agent.CurRootYaw);
		const double InitialSpeed = bManualSimpleInput
			? 0.0
			: AgentSpeedCmPerSecond / MetersToCentimeters;
		Agent.MoverState.velocity = { InitialDirection.x * InitialSpeed, InitialDirection.z * InitialSpeed };
		Agent.MoverState.previous_yaw_radians = Agent.CurRootYaw;
		Agent.MoverState.yaw_radians = Agent.CurRootYaw;
		if (bManualSimpleInput)
		{
			Agent.MoverIntent.mode = prophecy::sim::LocomotionMode::Walk;
			Agent.MoverIntent.speed_direction_radians = 0.0;
			Agent.MoverIntent.speed_amplitude = 0.0;
			Agent.MoverIntent.orientation_yaw_radians = Agent.CurRootYaw;
			Agent.MoverIntent.speed_scale = 1.0;
			Agent.MoverIntent.turn_scale = 1.0;
		}
		else
		{
			UpdateRouteIntent(Agent, float(InitialSpeed), ArrivalRadiusCm / MetersToCentimeters);
		}

		Agent.bUseWalkPolicy = ProphecySelectWalkCheckpoint(
			Agent.MoverIntent.mode == prophecy::sim::LocomotionMode::Run,
			Agent.MoverState.velocity.x, Agent.MoverState.velocity.z,
			PlacedAgent ? PlacedAgent->LocomotionWalkCheckpointSpeedThreshold : -1.f);
		Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);
		Agent.PublishedWalkWeight = Agent.PreviousPublishedWalkWeight = Agent.PolicyBlend.WalkWeight;
		Agent.RecoveryWeights=ProphecyAttackRecovery::FWeights(Agent.PolicyBlend.WalkWeight);
		Agent.PublishedLegWalkWeights=Agent.PreviousPublishedLegWalkWeights=Agent.RecoveryWeights.Legs();
		Agent.bPreviousPublishedUseWalkPolicy = Agent.bUseWalkPolicy;
		Agent.bPublishedUseWalkPolicy = Agent.bUseWalkPolicy;
		const TArray<TArray<float>>& SeedStates = Agent.bUseWalkPolicy
			? Impl->WalkSeedPhaseStates
			: Impl->SeedPhaseStates;
		const int32 CurPhase = 1 + (AgentIndex * 7) % (SeedStates.Num() - 1);
		const int32 PrevPhase = FMath::Max(0, CurPhase - 1);
		FMemory::Memcpy(StateSlice(Impl->PrevStateBuffer, AgentIndex), SeedStates[PrevPhase].GetData(), StateDim * sizeof(float));
		FMemory::Memcpy(StateSlice(Impl->CurStateBuffer, AgentIndex), SeedStates[CurPhase].GetData(), StateDim * sizeof(float));
		FMemory::Memcpy(StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex), StateSlice(Impl->CurStateBuffer, AgentIndex), StateDim * sizeof(float));
		FMemory::Memcpy(StateSlice(Impl->PublishedStateBuffer, AgentIndex), StateSlice(Impl->CurStateBuffer, AgentIndex), StateDim * sizeof(float));
		FMemory::Memcpy(StateSlice(Impl->PreviousPhysicalStateBuffer, AgentIndex), StateSlice(Impl->CurStateBuffer, AgentIndex), StateDim * sizeof(float));

		float* PreviousUpper = UpperStateSlice(Impl->UpperPreviousStateBuffer, AgentIndex);
		float* CurrentUpper = UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex);
		float* CurrentBase = UpperStateSlice(Impl->UpperCurrentBaseBuffer, AgentIndex);
		BuildUpperBaseFromLower(StateSlice(Impl->CurStateBuffer, AgentIndex), *Impl, CurrentBase);
		SeedUpperIdleFromLower(StateSlice(Impl->PrevStateBuffer, AgentIndex), *Impl, PreviousUpper);
		SeedUpperIdleFromLower(StateSlice(Impl->CurStateBuffer, AgentIndex), *Impl, CurrentUpper);
		FMemory::Memcpy(
			UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer, AgentIndex),
			CurrentUpper, // Both initial published lower frames are the current seed.
			UpperStateDim * sizeof(float));
		FMemory::Memcpy(
			UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex),
			CurrentUpper,
			UpperStateDim * sizeof(float));
		FMemory::Memcpy(
			UpperStateSlice(Impl->UpperPreviousPhysicalStateBuffer, AgentIndex),
			CurrentUpper,
			UpperStateDim * sizeof(float));
		LowerTransformToHeading(
			StateSlice(Impl->PrevStateBuffer, AgentIndex), 0, 3, *Impl,
			TransformStateSlice(Impl->PreviousPelvisHeadingBuffer, AgentIndex));
		LowerTransformToHeading(
			StateSlice(Impl->CurStateBuffer, AgentIndex), 0, 3, *Impl,
			TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex));
	}
}

void AProphecyNNLocomotionManager::SpawnVisualComponents()
{
	const TArray<TObjectPtr<AProphecyAgent>> PlacedAgents = MoveTemp(AgentActors);
	MeshComponents.Reset(CrowdSize);
	AgentActors.Reset(CrowdSize);
	UClass* SpawnClass = AgentClass ? AgentClass.Get() : AProphecyAgent::StaticClass();
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		const bool bUsePlacedAgent = PlacedAgents.IsValidIndex(AgentIndex) && IsValid(PlacedAgents[AgentIndex]);
		AProphecyAgent* AgentActor = bUsePlacedAgent ? PlacedAgents[AgentIndex].Get() : nullptr;
		if (!AgentActor)
		{
			FActorSpawnParameters SpawnParameters;
			SpawnParameters.Owner = this;
			SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			SpawnParameters.ObjectFlags |= RF_Transient;
			AgentActor = GetWorld()->SpawnActor<AProphecyAgent>(
				SpawnClass,
				FTransform::Identity,
				SpawnParameters);
		}
		if (!AgentActor)
		{
			UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Could not spawn agent shell %d."), AgentIndex);
			break;
		}
		// Spawned Blueprint shells can retain the native constructor value for a
		// native property even when their Blueprint CDO overrides it. Copy this
		// opt-in explicitly so the class default always governs manual evaluation.
		if (!bUsePlacedAgent)
		{
			if (const AProphecyAgent* SpawnDefaults = SpawnClass->GetDefaultObject<AProphecyAgent>())
			{
				AgentActor->bManualNNPoseApplication = SpawnDefaults->bManualNNPoseApplication;
				AgentActor->bShowKinematicDebugMesh = SpawnDefaults->bShowKinematicDebugMesh;
			}
		}
		// The manager publishes the complete 30 Hz authored pose first. Both the
		// animation evaluation and the Physical controller consume that same pose;
		// neither is allowed to predict a private frame ahead.
		AgentActor->AddTickPrerequisiteActor(this);

		FProphecyAgentHandle Handle;
		Handle.Index = AgentIndex;
		Handle.Generation = Impl->Agents[AgentIndex].Generation;
		AgentActor->SetAgentHandle(Handle);
		Impl->Agents[AgentIndex].UpperRootRotationHorizon = ProphecyUpperRootHorizon::Configured(AgentActor);
		// Resolve Blueprint settings once. The 30 Hz loop reads only cached POD.
		CachePhysicalFeedbackSettings(
			AgentActor,
			Impl->Agents[AgentIndex].PhysicalFeedbackTolerances);
		// Publish the current authored pose/root before this agent applies its
		// PrePhysics forces. Without this dependency their order was scheduler-
		// dependent and the physical drive intermittently consumed a stale frame.
		AgentActor->AddTickPrerequisiteActor(this);
		AgentActor->TeleportManagedRootLowPoint(
			TrainingToUnreal(Impl->Agents[AgentIndex].CurRootPos),
			-FMath::RadiansToDegrees(Impl->Agents[AgentIndex].CurRootYaw));

		USkeletalMeshComponent* Component = AgentActor->GetAgentMesh();
		USkeletalMeshComponent* PoseReferenceMesh = AgentActor->GetPoseReferenceMesh();
		if (!PoseReferenceMesh || !PoseReferenceMesh->GetSkeletalMeshAsset())
		{
			UE_LOG(LogProphecyNNLocomotion, Error,
				TEXT("Agent class %s has no pose-reference skeletal mesh (agent %d)."), *GetNameSafe(SpawnClass), AgentIndex);
			if (!bUsePlacedAgent) AgentActor->Destroy();
			break;
		}
		const int32 PoseAgentId = PoseStoreAgentBase + AgentIndex;
		// Manual agents render on PhysicalMesh, not the empty inherited Mesh.
		// Its automatic kinematic evaluation must see this frame's published data too.
		PoseReferenceMesh->AddTickPrerequisiteActor(this);
		const float PoseIntervalSeconds = 1.0f / FMath::Max(1.0f, NNUpdateHz);
		const bool bInterpolatePose =
			!FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNDisableViewerGlobalInterpolation"));
		AgentActor->ConfigureNNPoseDataSource(PoseAgentId, PoseIntervalSeconds, bInterpolatePose);
		if (AgentActor->bManualNNPoseApplication)
		{
			Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Component->SetGenerateOverlapEvents(false);
			// The inherited Mesh is an agent tick prerequisite. It must remain empty
			// even in debug builds, otherwise merely visualizing the target changes
			// when the PrePhysics Blueprint force pass runs.
			Component->SetComponentTickEnabled(false);
			Component->SetVisibility(false, true);
			Component->SetHiddenInGame(true, true);
			Component->SetAnimInstanceClass(nullptr);
			Component->SetSkeletalMesh(nullptr, false);
			if (AgentActor->bShowKinematicDebugMesh)
			{
				// A separate visualization-only component consumes the finalized pose
				// store independently. Nothing in the agent or physical controller has
				// this component as a tick prerequisite.
				const FName DebugMeshName = ProphecyCrowd::KinematicDebugMeshName(AgentIndex);
				UPoseableMeshComponent* DebugMesh = NewObject<UPoseableMeshComponent>(
					this, DebugMeshName);
				AddInstanceComponent(DebugMesh);
				DebugMesh->SetupAttachment(AgentActor->GetAgentCapsule());
				DebugMesh->SetRelativeTransform(Component->GetRelativeTransform());
				DebugMesh->SetSkinnedAssetAndUpdate(PoseReferenceMesh->GetSkeletalMeshAsset(), false);
				DebugMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
				DebugMesh->SetGenerateOverlapEvents(false);
				DebugMesh->SetCanEverAffectNavigation(false);
				DebugMesh->SetCastShadow(false);
				DebugMesh->SetReceivesDecals(false);
				DebugMesh->SetAffectDistanceFieldLighting(false);
				DebugMesh->SetAffectDynamicIndirectLighting(false);
				DebugMesh->SetVisibleInRayTracing(false);
				DebugMesh->RegisterComponent();
				DebugMesh->SetComponentTickEnabled(false);
			}
			AgentActor->SetActorTickEnabled(true);
		}
		else
		{
			Component->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
			Component->AddTickPrerequisiteActor(this);
			Component->SetGenerateOverlapEvents(false);
			Component->SetCastShadow(bCastShadows);
			Component->SetReceivesDecals(false);
			Component->SetAffectDistanceFieldLighting(false);
			Component->SetAffectDynamicIndirectLighting(false);
			Component->SetVisibleInRayTracing(false);
			Component->SetForcedLOD(FMath::Max(0, ForcedMeshLOD));
			Component->SetDisablePostProcessBlueprint(true);
			// /Game/locomotion is the exact single-agent Stepper-viewer parity surface. Do not let
			// visibility or URO insert a second, engine-owned sampling/interpolation
			// layer there; the NN anim proxy already renders the 30 Hz publications.
			Component->VisibilityBasedAnimTickOption = Impl->bSimpleLocomotionTest
				? EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones
				: EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
			Component->OnAnimUpdateRateParamsCreated.BindStatic(&ConfigureAgentAnimUpdateRate);
			ConfigureAgentAnimUpdateRate(Component->AnimUpdateRateParams);
			Component->bEnableUpdateRateOptimizations = !Impl->bSimpleLocomotionTest;
			Component->bComponentUseFixedSkelBounds = true;
		}
		AgentActor->SetPhysicalDriveMode(InitialPhysicalDriveMode);
		if (UProphecyNNLocomotionAnimInstance* Anim = Cast<UProphecyNNLocomotionAnimInstance>(Component->GetAnimInstance()))
		{
			Anim->AgentId = PoseAgentId;
			Anim->NNPoseIntervalSeconds = PoseIntervalSeconds;
			Anim->bUseViewerGlobalPoseInterpolation = bInterpolatePose;
		}
		AgentActors.Add(AgentActor);
		MeshComponents.Add(Component);
	}
}

void AProphecyNNLocomotionManager::StepSimulation(float StepSeconds)
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	const bool SharedStep=!Clock || Clock->Step->SharedBoundary;
	// Commit the completed attack's carrier before locomotion builds its inputs.
	// Doing this in AdvanceSlashAttacks would be one locomotion inference too late.
	for (int32 Index = 0; Index < AgentActors.Num(); ++Index)
	{
		if (Clock && !Clock->Step->Due[Index]) continue;
		if (Impl->Agents[Index].DefensePose && !Impl->Agents[Index].DefensePose->Status.Active)
		{
			StopAgentNNDefense(GetAgentHandle(Index));
		}
		const auto& Slash = Impl->Agents[Index].Slash;
		if (AgentActors[Index] && AgentActors[Index]->bNNInferenceEnabled && Slash.bActive &&
			Slash.HitFrame != INDEX_NONE && Slash.Frame + 1 >= Slash.HitFrame + Slash.TailSteps)
		{
			if (Slash.Frame >= Slash.HitFrame + Slash.TailSteps)
				StopAgentNNAttack(GetAgentHandle(Index));
			else
				ProphecyAttackTrim::QueueHalfFrame(this,AgentActors[Index],Slash.Family,Slash.Frame+1);
		}
	}
	const bool bWarmed = Impl->Stats.bCollecting;
	double Start = FPlatformTime::Seconds();
	if (SharedStep) ProphecyDefenseArmedGate::Capture(this,[&](AProphecyAgent* Defender,ProphecyDefenseArmedGate::FHistory& H)
	{
		if (ResolveAgent(Defender->GetAgentHandle())!=Defender) return;
		const int32 Index=Defender->GetAgentHandle().Index;auto& Agent=Impl->Agents[Index];
		PublishAgentPose(Index,Agent.PublishedPoseTimeSeconds);
		H.Root[0]=Agent.PreviousPublishedRoot;H.Root[1]=Agent.PublishedRoot;
		H.Yaw[0]=Agent.PreviousPublishedYaw;H.Yaw[1]=Agent.PublishedYaw;
		for (int32 I=0;I<2;++I)
		{
			const auto Pose=TransformSlice(I?Impl->ComponentTransformBuffer:Impl->PreviousComponentTransformBuffer,Index);
			for (int32 Bone=0;Bone<25;++Bone) H.Pose[I][Bone]=Pose[Bone];
		}
		H.bValid=true;
	});
    if(ProphecyWalkPinning::AnyTickPinning()) CommitWalkTickPinning();
	ResamplePhysicalAgents();
	BuildInputBatch(StepSeconds);
	if (bWarmed) Impl->Stats.BuildSeconds += FPlatformTime::Seconds() - Start;
	Start = FPlatformTime::Seconds();
	if (!RunModelBatch()) return;
	if (bWarmed) Impl->Stats.InferenceSeconds += FPlatformTime::Seconds() - Start;
	Start = FPlatformTime::Seconds();
	ApplyOutputBatch(StepSeconds);
	if (bWarmed) Impl->Stats.OutputSeconds += FPlatformTime::Seconds() - Start;
	Start = FPlatformTime::Seconds();
	BuildUpperInputBatch();
	if (!Impl->PreviousPoseDebugAgents.IsEmpty()) UpdatePreviousPoseDebug(false);
	if (bWarmed) Impl->Stats.BuildSeconds += FPlatformTime::Seconds() - Start;
	Start = FPlatformTime::Seconds();
	if (!RunUpperModelBatch()) return;
	if (bWarmed) Impl->Stats.InferenceSeconds += FPlatformTime::Seconds() - Start;
	Start = FPlatformTime::Seconds();
	ApplyUpperOutputBatch();
	TraceNNHandoff();
	ApplyAnimationLayers(StepSeconds);
	if (SharedStep) AdvanceSlashAttacks();
	// Predict on Armed itself using the history from before this completed step.
	if (SharedStep) ProphecyDefenseArmedGate::Advance(this);
	if (SharedStep && Impl->Defense && Impl->Defense->ActiveCount) { AdvanceNNDefenses();AdvanceNNDodges(); }
	if (bWarmed) Impl->Stats.OutputSeconds += FPlatformTime::Seconds() - Start;
	if (Impl->bAbsoluteMotionAudit)
	{
		++Impl->AbsoluteMotionReferenceFrame;
	}
	if (bWarmed) ++Impl->Stats.NNSteps;
}

void AProphecyNNLocomotionManager::ResamplePhysicalAgents()
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerPhysicalResample);
	Impl->PhysicalFeedbackIndices.Reset();
    TArray<FAlignedLowerFeedback>* Alignment = nullptr;
	for (int32 AgentIndex = 0; AgentIndex < AgentActors.Num(); ++AgentIndex)
	{
		// One completed physics observation must not be fed back repeatedly when
		// this agent takes several local NN steps before the shared world steps.
		if (Clock && (!Clock->Step->Due[AgentIndex] || !Clock->Step->SamplePhysics[AgentIndex])) continue;
		AProphecyAgent* AgentActor = AgentActors[AgentIndex];
		if (AgentActor && !AgentActor->bNNInferenceEnabled)
		{
			continue;
		}
		if (!AgentActor) continue;
		ProphecyPhysicalContext::Update(AgentActor);
		if (Impl->Agents[AgentIndex].DefensePose && Impl->Agents[AgentIndex].DefensePose->bDodge) continue;
		bool bNeedsPhysicalSample = AgentActor->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic;
		if (!bNeedsPhysicalSample && AgentActor->bManualNNPoseApplication)
		{
			const USkeletalMeshComponent* PoseMesh = AgentActor->GetPoseReferenceMesh();
			bNeedsPhysicalSample = PoseMesh && PoseMesh->IsAnySimulatingPhysics();
		}
		if (bNeedsPhysicalSample)
		{
			if (PhysicalFeedbackExecutionMode == 0)
			{
				if (ResamplePhysicalAgentState(AgentIndex)) ++Impl->CompletedPhysicalSamples;
				else ++Impl->FailedPhysicalSamples;
				continue;
			}
			if (!Impl->Agents.IsValidIndex(AgentIndex))
			{
				++Impl->FailedPhysicalSamples;
				continue;
			}
			bool bSampled = false;
			{
				ProphecyJolt::CharacterProfiling::FScope SampleTiming(ProphecyJolt::CharacterProfiling::EPhase::PhysicalSampleRead);
				bSampled = AgentActor->SampleActualComponentPose(Impl->PublishedBoneNames,
					TransformSlice(Impl->PhysicalTransformBuffer, AgentIndex));
			}
			bool bPrepared = false;
			if (bSampled)
			{
				ProphecyJolt::CharacterProfiling::FScope PrepareTiming(ProphecyJolt::CharacterProfiling::EPhase::PhysicalFeedbackPrepare);
				bPrepared = PreparePhysicalFeedbackWork(*Impl, AgentIndex);
				if (bPrepared)
				{
					if (!Alignment)
					{
						Alignment = &AlignedLowerFeedbackBatches.FindOrAdd(this);
						Alignment->SetNum(AgentActors.Num());
					}
					PrepareAlignedLowerFeedback(*Impl, AgentIndex, *AgentActor, (*Alignment)[AgentIndex]);
				}
			}
			if (bPrepared) Impl->PhysicalFeedbackIndices.Add(AgentIndex);
			else ++Impl->FailedPhysicalSamples;
		}
	}
	if (PhysicalFeedbackExecutionMode != 0 && !Impl->PhysicalFeedbackIndices.IsEmpty())
	{
		{
			ProphecyJolt::CharacterProfiling::FScope JoinedTiming(ProphecyJolt::CharacterProfiling::EPhase::PhysicalFeedbackBatch);
			ExecutePhysicalFeedbackBatch(*Impl, Impl->PhysicalFeedbackWorkItems, Impl->PhysicalFeedbackIndices,
				PhysicalFeedbackExecutionMode == 1, Alignment ? MakeArrayView(*Alignment) : TArrayView<FAlignedLowerFeedback>());
		}
		++Impl->PreparedPhysicalBatches;
		for (const int32 AgentIndex : Impl->PhysicalFeedbackIndices)
		{
			const auto& Work = Impl->PhysicalFeedbackWorkItems[AgentIndex];
			if (Work.bSucceeded)
			{
				Impl->Agents[AgentIndex].bHasPhysicalSample = Work.bHasPhysicalSample;
				++Impl->CompletedPhysicalSamples;
				++Impl->PreparedPhysicalSamples;
			}
			else ++Impl->FailedPhysicalSamples;
		}
	}

}

bool AProphecyNNLocomotionManager::ResamplePhysicalAgentState(int32 AgentIndex)
{
	if (!AgentActors.IsValidIndex(AgentIndex) || !Impl->Agents.IsValidIndex(AgentIndex) || !AgentActors[AgentIndex])
	{
		return false;
	}

	TArrayView<FTransform> ActualTransforms = TransformSlice(Impl->PhysicalTransformBuffer, AgentIndex);
	{
		ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::PhysicalSampleRead);
		if (!AgentActors[AgentIndex]->SampleActualComponentPose(Impl->PublishedBoneNames, ActualTransforms))
		{
			return false;
		}
	}
	FAlignedLowerFeedback Alignment;
	PrepareAlignedLowerFeedback(*Impl, AgentIndex, *AgentActors[AgentIndex], Alignment);
	return CommitPhysicalSampleSerial(*Impl, AgentIndex, ActualTransforms, Alignment.bAligned ? Alignment.State : nullptr);
}

void AProphecyNNLocomotionManager::BuildInputBatch(float StepSeconds)
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	const float Speed = AgentSpeedCmPerSecond / MetersToCentimeters;
	const float Arrival = ArrivalRadiusCm / MetersToCentimeters;
	const bool bBridgeDriving = IsSimBridgeActive() && Impl->bReceivedBridgeFrame;
	for (int32 AgentIndex = 0; AgentIndex < BatchSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		if (AgentActors.IsValidIndex(AgentIndex) && AgentActors[AgentIndex] &&
			!AgentActors[AgentIndex]->bNNInferenceEnabled)
		{
			continue;
		}
		const bool bManualSimpleAgent = Impl->bSimpleLocomotionTest &&
			!Impl->bAbsoluteMotionAudit && AgentIndex < CrowdSize;
		const AProphecyAgent* InputActor = AgentActors.IsValidIndex(AgentIndex) ? AgentActors[AgentIndex] : nullptr;
		const bool bBlueprintInput = InputActor && InputActor->bUseBlueprintLocomotionInput &&
			!Impl->bAbsoluteMotionAudit;
		if (bBlueprintInput)
		{
			const FProphecyLocomotionInput& Input = InputActor->LocomotionInput;
			const FVector Move = Input.WorldMoveInput.ContainsNaN()
				? FVector::ZeroVector : FVector(Input.WorldMoveInput.X, Input.WorldMoveInput.Y, 0.0);
			const FVector Facing = Input.FacingWorldDirection.ContainsNaN()
				? FVector::ZeroVector : FVector(Input.FacingWorldDirection.X, Input.FacingWorldDirection.Y, 0.0);
			Agent.MoverIntent.mode = Input.bRun ? prophecy::sim::LocomotionMode::Run : prophecy::sim::LocomotionMode::Walk;
			Agent.MoverIntent.speed_amplitude = FMath::Min(Move.Size(), 1.0);
			Agent.MoverIntent.speed_direction_radians = Move.IsNearlyZero() ? 0.0 : prophecy::sim::SignedAngleDelta(
				Agent.MoverState.yaw_radians, FMath::Atan2(Move.X, Move.Y));
			if (!Facing.IsNearlyZero())
			{
				const double RequestedYaw = FMath::Atan2(Facing.X, Facing.Y);
				// Explicit steering chooses the nearest equivalent heading. Stop input
				// has no facing vector and retains an impulse's unwrapped stopping target.
				if (!RootYawImpulseAgents.Contains(InputActor))
					Agent.MoverIntent.orientation_yaw_radians = RequestedYaw;
				else if (!ProphecyRootFacing::IsImpulseOwned(InputActor) ||
					FMath::Abs(prophecy::sim::SignedAngleDelta(
						Agent.MoverIntent.orientation_yaw_radians, RequestedYaw)) > 1.e-6)
				{
					// Re-anchor explicit steering every step, even for an unchanged
					// vector. Otherwise crossing 360 degrees makes it unwind whole turns.
					// A direct Blueprint property edit can also supersede impulse ownership.
					ProphecyRootFacing::Explicit(InputActor);
					Agent.MoverIntent.orientation_yaw_radians = Agent.MoverState.yaw_radians +
						prophecy::sim::SignedAngleDelta(Agent.MoverState.yaw_radians, RequestedYaw);
				}
			}
			Agent.MoverIntent.speed_scale = FMath::IsFinite(Input.SpeedScale) ? FMath::Clamp(double(Input.SpeedScale), 0.0, 1.0) : 0.0;
			Agent.MoverIntent.turn_scale = FMath::IsFinite(Input.TurnScale) ? FMath::Clamp(double(Input.TurnScale), 0.0, 1.0) : 0.0;
		}
		else if ((!bBridgeDriving || AgentIndex >= CrowdSize) && !bManualSimpleAgent)
		{
			UpdateRouteIntent(Agent, Speed, Arrival);
		}
		else if (bManualSimpleAgent && !bBridgeDriving)
		{
			// An unwired manual pawn idles; disabling its Blueprint override must
			// not leave a stale nonzero stick from the previous input owner.
			Agent.MoverIntent.speed_amplitude = 0.0;
		}
		if (Agent.Slash.bActive && !Agent.Slash.bHalf)
		{
			// Full attacks own the lower pose. Stop locomotion through its normal
			// intent path; half attacks retain the caller's movement/orientation.
			Agent.MoverIntent.speed_amplitude = 0.0;
			Agent.MoverIntent.orientation_yaw_radians = Agent.CurRootYaw;
		}
		Agent.FedInputRoot = Agent.CurRootPos;
		Agent.FedInputYaw = Agent.CurRootYaw;
		Agent.WindowPreviousRoot = Agent.PrevRootPos;
		Agent.WindowPreviousYaw = Agent.PrevRootYaw;
		Agent.WindowStepSeconds = StepSeconds;
		const auto* Magic = !bBridgeDriving && (!Agent.Slash.bActive || Agent.Slash.bHalf)
			? ProphecyRootMagic::Find(InputActor) : nullptr;
		Agent.WindowVerticalVelocity = Magic ? Magic->Linear.Y : 0.f;
		auto* SpeedLimits = !bBridgeDriving && (!Agent.Slash.bActive || Agent.Slash.bHalf)
			? ProphecyRootSpeedLimits::Find(InputActor) : nullptr;
		double LimitedWindowYaw[FutureWindow];
		const float* CurrentState = StateSlice(Impl->CurStateBuffer, AgentIndex);
		const float* PreviousState = StateSlice(Impl->PrevStateBuffer, AgentIndex);
		float* Write = Impl->InputBuffer.GetData() + AgentIndex * InputDim;
		FMemory::Memcpy(Write, CurrentState, StateDim * sizeof(float));
		Write += StateDim;
		FMemory::Memcpy(Write, PreviousState, StateDim * sizeof(float));
		Write += StateDim;
		for (int32 Index = 0; Index < 3; ++Index) *Write++ = (CurrentState[Index] - PreviousState[Index]) / Impl->PoseDeltaScaleFinal;
		for (int32 Index = 9; Index < StateDim; ++Index) *Write++ = (CurrentState[Index] - PreviousState[Index]) / Impl->PoseDeltaScaleFinal;

		const FVector3f RootDeltaWorld = Agent.CurRootPos - Agent.PrevRootPos;
		const FVector3f RootDeltaLocal = TransformRow(RootDeltaWorld, YawMatrix(Agent.PrevRootYaw));
		*Write++ = RootDeltaLocal.X / Impl->MaxSpeedScaleFinal;
		*Write++ = RootDeltaLocal.Z / Impl->MaxSpeedScaleFinal;
		*Write++ = WrapAngle(Agent.CurRootYaw - Agent.PrevRootYaw) / Impl->MaxTurnRateScaleFinal;

		const auto* PreparedBalance = ProphecyRootBalance::Prepare(InputActor, Agent.MoverState, Agent.MoverIntent,
			!Agent.Slash.bActive || Agent.Slash.bHalf);
		const prophecy::sim::FutureRootWindow FutureRoots = prophecy::sim::PredictFutureRoots(
			Agent.MoverState, Agent.MoverIntent, StepSeconds, RootYawImpulseAgents.Contains(InputActor),
			PreparedBalance);
		auto* WindowSmoothing = ProphecyNNRootWindow::Find(InputActor);
		if (float* HistoryYaw = RootImpulseSmoothingYaw.Find(InputActor))
		{
			if (WindowSmoothing)
			{
				// A world impulse must not turn with root0. Transport only travel
				// direction; radius and relative facing retain their existing filters.
				const double Delta = WrapAngle(Agent.CurRootYaw - *HistoryYaw);
				for (auto& Sample : WindowSmoothing->Samples) Sample.Direction += Delta;
			}
			*HistoryYaw = Agent.CurRootYaw;
			// Once the spring or a fresh movement command owns translation, normal
			// locomotion smoothing resumes. No residual per-agent tracking at rest.
			if (PreparedBalance || Agent.MoverIntent.speed_amplitude > 1.e-8 ||
				(Agent.MoverState.velocity.x * Agent.MoverState.velocity.x +
				 Agent.MoverState.velocity.z * Agent.MoverState.velocity.z) < 1.e-12)
				RootImpulseSmoothingYaw.Remove(InputActor);
		}
		for (int32 FutureIndex = 1; FutureIndex <= FutureWindow; ++FutureIndex)
		{
			const prophecy::sim::RootTransform& FutureRoot = FutureRoots[FutureIndex - 1];
			FVector3f FuturePosition(
				float(FutureRoot.position.x), Agent.CurRootPos.Y, float(FutureRoot.position.z));
			FVector3f FutureLocal = TransformRow(FuturePosition - Agent.CurRootPos, YawMatrix(Agent.CurRootYaw));
			const float Scale = float(FutureIndex) * Impl->MaxSpeedScaleFinal;
			float DeltaYaw = WrapAngle(float(FutureRoot.yaw_radians) - Agent.CurRootYaw);
			if (WindowSmoothing)
			{
				double LocalYaw = -double(DeltaYaw);
				const FVector FilteredOffset = WindowSmoothing->Samples[FutureIndex - 1].Filter(
					TrainingToUnreal(FutureLocal), LocalYaw, WindowSmoothing->Factors);
				FutureLocal = UnrealToTraining(FilteredOffset);
				DeltaYaw = WrapAngle(float(-LocalYaw));
			}
			float EncodedX = FMath::Clamp(FutureLocal.X / Scale, -2.0f, 2.0f);
			float EncodedZ = FMath::Clamp(FutureLocal.Z / Scale, -2.0f, 2.0f);
			if (WindowSmoothing && FutureIndex == 1)
			{
				WindowSmoothing->ActualNextRootLocal = FVector3f(EncodedX * Scale, 0, EncodedZ * Scale);
				WindowSmoothing->ActualNextYaw = FMath::Atan2(FMath::Sin(DeltaYaw), FMath::Cos(DeltaYaw));
			}
			// Magic is added AFTER the mover's smoothing. It never rotates world-space
			// translation, enters mover momentum, or disappears when smoothing is zero.
			if (Magic)
			{
				const float Horizon = FutureIndex * StepSeconds;
				const FVector3f Extra = TransformRow(Magic->Linear * Horizon, YawMatrix(Agent.CurRootYaw));
				EncodedX += Extra.X / Scale;
				EncodedZ += Extra.Z / Scale;
				DeltaYaw += float(Magic->Yaw * Horizon);
			}
			const float EncodedCosYaw = FMath::Cos(DeltaYaw);
			if (SpeedLimits)
				LimitedWindowYaw[FutureIndex - 1] = WindowSmoothing ? double(DeltaYaw)
					: FutureRoot.yaw_radians - Agent.CurRootYaw + (Magic ? Magic->Yaw * FutureIndex * StepSeconds : 0.);
			const float EncodedSinYaw = FMath::Sin(DeltaYaw);
			*Write++ = EncodedX;
			*Write++ = EncodedZ;
			*Write++ = EncodedCosYaw;
			*Write++ = EncodedSinYaw;
		}
		check(int32(Write - (Impl->InputBuffer.GetData() + AgentIndex * InputDim)) == InputDim);
		if (SpeedLimits)
			ProphecyRootSpeedLimits::LimitWindow(*SpeedLimits,
				Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120, LimitedWindowYaw,
				FutureWindow, Impl->MaxSpeedScaleFinal, StepSeconds, Magic, Agent.WindowVerticalVelocity);
		// Select from the trajectory actually fed to the NN, not the mover's
		// pre-magic/pre-limit velocity. Root teleports cannot create false speed.
		const float* NextRoot = Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120;
		// Gait belongs to the trained local trajectory. Changing its playback rate
		// must not select a different checkpoint for an otherwise identical stride.
		const double SpeedScale = double(Impl->MaxSpeedScaleFinal) / StepSeconds;
		const double RootSpeedSquared = (double(NextRoot[0]) * NextRoot[0] + double(NextRoot[1]) * NextRoot[1]) * SpeedScale * SpeedScale;
		Agent.bUseWalkPolicy = ProphecySelectWalkCheckpoint(
			Agent.MoverIntent.mode == prophecy::sim::LocomotionMode::Run,
			Agent.MoverState.velocity.x, Agent.MoverState.velocity.z,
			InputActor ? InputActor->LocomotionWalkCheckpointSpeedThreshold : -1.f);
		if (ProphecyAutoRun::Above(RootSpeedSquared, ProphecyAutoRun::Threshold(InputActor)))
			Agent.bUseWalkPolicy = false;
		if (Agent.Slash.bActive && !Agent.Slash.bHalf)
		{
			Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);
			ProphecyBlendClock::Stop(InputActor,ProphecyBlendClock::EKind::Policy);
		}
		else if (Agent.PolicyBlend.IsActive() || Agent.PolicyBlend.bTargetWalk != Agent.bUseWalkPolicy)
		{
			const float Duration=InputActor ? (Agent.bUseWalkPolicy ? InputActor->LocomotionRunToWalkBlendSeconds
				: InputActor->LocomotionWalkToRunBlendSeconds) : 0.f;
			// Start/reverse at the current mix; consume elapsed engine ticks once,
			// even if multiple policy evaluations occur in this engine frame.
			if (Duration>0 && Agent.PolicyBlend.bTargetWalk!=Agent.bUseWalkPolicy)
				ProphecyBlendClock::Start(InputActor,ProphecyBlendClock::EKind::Policy,Duration);
			else if (Duration>0) ProphecyBlendClock::Ensure(InputActor,ProphecyBlendClock::EKind::Policy);
			const float BlendDt=Duration>0 ? float(ProphecyBlendClock::Consume(InputActor,ProphecyBlendClock::EKind::Policy)) : 0.f;
			Agent.PolicyBlend.Step(Agent.bUseWalkPolicy,
				InputActor ? InputActor->LocomotionWalkToRunBlendSeconds : 0.f,
				InputActor ? InputActor->LocomotionRunToWalkBlendSeconds : 0.f, BlendDt);
			if (!Agent.PolicyBlend.IsActive()) ProphecyBlendClock::Stop(InputActor,ProphecyBlendClock::EKind::Policy);
		}
		ProphecyAttackRecovery::Step(InputActor,Agent.PolicyBlend.WalkWeight,Agent.RecoveryWeights);
		if (!Agent.Slash.bActive && !Agent.DefensePose) ProphecyHandRecovery::Step(InputActor);

	}

	if (bShowFutureRootDebug && Impl->Agents.IsValidIndex(FutureRootDebugAgentIndex) &&
		(!Clock || Clock->Step->Due[FutureRootDebugAgentIndex]))
	{
		FImpl::FAgent& DebugAgent = Impl->Agents[FutureRootDebugAgentIndex];
		DebugAgent.FedInputRoot = DebugAgent.CurRootPos;
		DebugAgent.FedInputYaw = DebugAgent.CurRootYaw;
		const float* Read = Impl->InputBuffer.GetData() + FutureRootDebugAgentIndex * InputDim + 120;
		for (int32 FutureIndex = 1; FutureIndex <= FutureWindow; ++FutureIndex)
		{
			const float Scale = float(FutureIndex) * Impl->MaxSpeedScaleFinal;
			const FVector3f FedLocal(Read[0] * Scale, DebugAgent.WindowVerticalVelocity * FutureIndex * StepSeconds, Read[1] * Scale);
			DebugAgent.FedFutureRootPositions[FutureIndex - 1] = DebugAgent.CurRootPos +
				TransformRow(FedLocal, Transpose(YawMatrix(DebugAgent.CurRootYaw)));
			DebugAgent.FedFutureRootYaws[FutureIndex - 1] = DebugAgent.CurRootYaw +
				FMath::Atan2(Read[3], Read[2]);
			Read += 4;
		}
		DebugAgent.bHasFedFutureRoots = true;
	}
}

bool AProphecyNNLocomotionManager::RunModelBatch()
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	bool bNeedRun = false;
	bool bNeedWalk = false;
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		if (Impl->Agents[AgentIndex].DefensePose && Impl->Agents[AgentIndex].DefensePose->bDodge) continue;
		if (AgentActors.IsValidIndex(AgentIndex) && AgentActors[AgentIndex] &&
			!AgentActors[AgentIndex]->bNNInferenceEnabled)
		{
			continue;
		}
		bNeedWalk |= Impl->Agents[AgentIndex].RecoveryWeights.NeedsWalk();
		bNeedRun |= Impl->Agents[AgentIndex].RecoveryWeights.NeedsRun();
        const auto Rotations=ProphecyAttackRecovery::FootRotationWeights(AgentActors[AgentIndex],Impl->Agents[AgentIndex].PolicyBlend.WalkWeight);
        bNeedWalk |= Rotations.X>=0 || Rotations.Y>=0;
		if (const auto* H=ProphecyHandRecovery::Frame(AgentActors[AgentIndex]))
		{ bNeedRun|=H->Need[0];bNeedWalk|=H->Need[1]; }
	}
	if (bNeedRun && !Impl->Model.Run(Impl->InputBuffer, Impl->OutputBuffer))
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Run NNE policy RunSync failed."));
		SetActorTickEnabled(false);
		return false;
	}
	if (bNeedWalk && !Impl->WalkModel.Run(Impl->InputBuffer, Impl->WalkOutputBuffer))
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Walk NNE policy RunSync failed."));
		SetActorTickEnabled(false);
		return false;
	}
	// Preserve source outputs before the ordinary walk-only lane overwrites Run.
	if (ProphecyHandRecovery::HasRecovery()) for (int32 I=0;I<CrowdSize;++I)
	{
		if (Clock && !Clock->Step->Due[I]) continue;
		if (auto* H=ProphecyHandRecovery::Frame(AgentActors[I]))
		{
			if(H->Need[0]) FMemory::Memcpy(H->Raw[0],Impl->OutputBuffer.GetData()+I*PolicyOutputDim,sizeof(H->Raw[0]));
			if(H->Need[1]) FMemory::Memcpy(H->Raw[1],Impl->WalkOutputBuffer.GetData()+I*PolicyOutputDim,sizeof(H->Raw[1]));
		}
	}
	if (bNeedWalk)
	{
		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			if (!Impl->Agents[AgentIndex].RecoveryWeights.NeedsRun())
			{
				FMemory::Memcpy(
					Impl->OutputBuffer.GetData() + AgentIndex * PolicyOutputDim,
					Impl->WalkOutputBuffer.GetData() + AgentIndex * PolicyOutputDim,
					PolicyOutputDim * sizeof(float));
			}
		}
	}
	// All lanes may be deliberately frozen while Blueprint plays authored animation.
	return true;
}

void AProphecyNNLocomotionManager::AdvanceAgentMover(int32 AgentIndex, float StepSeconds)
{
    auto& Agent=Impl->Agents[AgentIndex];
    auto& MoverTargets=ResolvedMoverTargets.FindChecked(this);
    float* NextState=Agent.DefensePose && Agent.DefensePose->bDodge ? nullptr : StateSlice(Impl->NextStateBuffer,AgentIndex);
		const float* Future = Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120;
		AProphecyAgent* Actor = AgentActors.IsValidIndex(AgentIndex) ? AgentActors[AgentIndex] : nullptr;
		const auto* Magic = !IsSimBridgeActive() && (!Agent.Slash.bActive || Agent.Slash.bHalf)
			? ProphecyRootMagic::Find(Actor) : nullptr;
		const auto* SpeedLimits = !IsSimBridgeActive() && (!Agent.Slash.bActive || Agent.Slash.bHalf)
			? ProphecyRootSpeedLimits::Find(Actor) : nullptr;
		const bool bSpeedClamped = SpeedLimits && SpeedLimits->bClamped;
		if (Magic && bSpeedClamped) Magic = &SpeedLimits->AppliedMagic;
		auto* WindowSmoothing = ProphecyNNRootWindow::Find(AgentActors[AgentIndex]);
		const FVector3f MagicDelta = Magic ? Magic->Linear * StepSeconds : FVector3f::ZeroVector;
		const float MagicYaw = Magic ? float(Magic->Yaw * StepSeconds) : 0.f;
		// NN recurrence follows the combined motion. The mover below keeps only
		// its own velocity and yaw momentum; add the independent term exactly once.
		const FVector3f NextRootDelta(Future[0] * Impl->MaxSpeedScaleFinal,
			MagicDelta.Y, Future[1] * Impl->MaxSpeedScaleFinal);
		const float NextYawDelta = FMath::Atan2(Future[3], Future[2]);
		if (NextState) RebaseStateRoot(NextState, *Impl, NextRootDelta, NextYawDelta);
		if (auto* H=ProphecyHandRecovery::Frame(Actor))
			for(int32 P=0;P<2;++P) if(H->Need[P]) RebaseStateRoot(H->Lower[P],*Impl,NextRootDelta,NextYawDelta);
		Agent.PrevRootPos = Agent.CurRootPos;
		Agent.PrevRootYaw = Agent.CurRootYaw;
		FResolvedMoverTarget& MoverTarget = MoverTargets[AgentIndex];
		const bool bYawImpulse = RootYawImpulseAgents.Contains(Actor);
		const auto* BalanceSpring = ProphecyRootBalance::GetPrepared(Actor);
		if (WindowSmoothing || BalanceSpring || SpeedLimits)
		{
			// root0 is the anchor for this update. Advance the actual mover to the same
			// encoded root1 that the NN and recurrence use, including smoothing or input-range
			// clipping at unusually high balance speeds, never to a second unfiltered prediction.
			auto Predicted = Agent.MoverState;
			prophecy::sim::StepLocomotion(Predicted, Agent.MoverIntent, StepSeconds, &MoverTarget.Target, bYawImpulse, BalanceSpring);
			const FVector3f Delta = TransformRow(NextRootDelta, Transpose(YawMatrix(Agent.CurRootYaw))) - MagicDelta;
			Agent.MoverState.position.x += Delta.X;
			Agent.MoverState.position.z += Delta.Z;
			Agent.MoverState.velocity = { Delta.X / double(StepSeconds), Delta.Z / double(StepSeconds) };
			Agent.MoverState.previous_yaw_radians = Agent.MoverState.yaw_radians;
			// Subtract the applied magic without wrapping: opposing large terms must
			// cancel exactly, rather than reintroducing a complete turn after limiting.
			Agent.MoverState.yaw_radians += SpeedLimits ? SpeedLimits->NextYawDelta - MagicYaw
				: WindowSmoothing ? WindowSmoothing->ActualNextYaw : WrapAngle(NextYawDelta - MagicYaw);
			Agent.MoverState.distance_travelled += FVector2D(Delta.X, Delta.Z).Size();
			Agent.MoverState.response = Predicted.response;
		}
		else prophecy::sim::StepLocomotion(Agent.MoverState, Agent.MoverIntent, StepSeconds, &MoverTarget.Target, bYawImpulse, BalanceSpring);
		if (Magic)
		{
			Agent.MoverState.position.x += MagicDelta.X;
			Agent.MoverState.position.z += MagicDelta.Z;
			Agent.CurRootPos.Y += MagicDelta.Y;
			// Carry both endpoints and the target: external yaw creates no phantom
			// mover angular velocity or spring back toward an unchanged facing target.
			Agent.MoverState.yaw_radians += MagicYaw;
			Agent.MoverState.previous_yaw_radians += MagicYaw;
			Agent.MoverIntent.orientation_yaw_radians += MagicYaw;
			MoverTarget.Target.orientation_yaw_radians += MagicYaw;
			if (MagicYaw != 0 && WindowSmoothing)
			{
				// Transport cached travel directions into the rotated root frame,
				// preserving the mover's world momentum instead of producing a helix.
				for (auto& Sample : WindowSmoothing->Samples) Sample.Direction += MagicYaw;
				if (float* HistoryYaw = RootImpulseSmoothingYaw.Find(Actor)) *HistoryYaw += MagicYaw;
			}
			if (MagicYaw != 0 && Actor && Actor->bUseBlueprintLocomotionInput
				&& !Actor->LocomotionInput.FacingWorldDirection.IsNearlyZero())
				Actor->LocomotionInput.FacingWorldDirection = FQuat(FVector::UpVector, -double(MagicYaw))
					.RotateVector(Actor->LocomotionInput.FacingWorldDirection);
		}
		if (bYawImpulse && FMath::Abs(prophecy::sim::SignedAngleDelta(
			Agent.MoverState.previous_yaw_radians, Agent.MoverState.yaw_radians)) < 1.0e-8 &&
			FMath::Abs(prophecy::sim::SignedAngleDelta(Agent.MoverState.yaw_radians,
				Agent.MoverIntent.orientation_yaw_radians)) < 1.0e-8)
		{
			RootYawImpulseAgents.Remove(Actor);
			ProphecyRootFacing::Explicit(Actor);
		}
		MoverTarget.bRun = Agent.MoverIntent.mode == prophecy::sim::LocomotionMode::Run;
		MoverTarget.bValid = true;
		Agent.CurRootPos.X = float(Agent.MoverState.position.x);
		Agent.CurRootPos.Z = float(Agent.MoverState.position.z);
		Agent.CurRootYaw = float(Agent.MoverState.yaw_radians);
}

void AProphecyNNLocomotionManager::ApplyOutputBatch(float StepSeconds)
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		if (AgentActors.IsValidIndex(AgentIndex) && AgentActors[AgentIndex] &&
			!AgentActors[AgentIndex]->bNNInferenceEnabled)
		{
			continue;
		}
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		auto* PinSmoothing=ProphecyWalkPinning::FindSmoothing(AgentActors[AgentIndex]);
		if (PinSmoothing && (Agent.DefensePose || Agent.Slash.bActive || !Agent.RecoveryWeights.NeedsWalk()))
		{ ProphecyWalkPinning::ResetSmoothing(AgentActors[AgentIndex]);PinSmoothing=nullptr; }
		if (Agent.DefensePose && Agent.DefensePose->bDodge)
		{
			// The buffers swap for every lane below. Hold this lane until its own
			// lower/upper defense batch commits after the attacker has completed.
			FMemory::Memcpy(StateSlice(Impl->NextStateBuffer,AgentIndex),StateSlice(Impl->CurStateBuffer,AgentIndex),StateDim*sizeof(float));
			AdvanceAgentMover(AgentIndex,StepSeconds);
			continue;
		}
        auto* TickPins=PinSmoothing && !Agent.DefensePose && !Agent.Slash.bActive && Agent.RecoveryWeights.NeedsWalk()
            ? ProphecyWalkPinning::FindTickPinning(AgentActors[AgentIndex]) : nullptr;
        if(TickPins) {TickPins->Previous=TickPins->Current;TickPins->Current={};TickPins->Current.Valid=true;}
		const bool bWalkPolicy = !Agent.RecoveryWeights.NeedsRun();
		const float* CurrentState = StateSlice(Impl->CurStateBuffer, AgentIndex);
		float* Transition = StateSlice(Impl->PublishedStateBuffer, AgentIndex);
		Agent.bPreviousPublishedUseWalkPolicy = Agent.bPublishedUseWalkPolicy;
		Agent.PreviousPublishedWalkWeight = Agent.PublishedWalkWeight;
		Agent.PreviousPublishedLegWalkWeights=Agent.PublishedLegWalkWeights;
		FMemory::Memcpy(
			StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),
			Transition,
			StateDim * sizeof(float));
		float* NextState = StateSlice(Impl->NextStateBuffer, AgentIndex);
		const float* Raw = Impl->OutputBuffer.GetData() + AgentIndex * PolicyOutputDim;
        const FVector2f FootRotationWeights=!Agent.DefensePose && !Agent.Slash.bActive
            ? ProphecyAttackRecovery::FootRotationWeights(AgentActors[AgentIndex],Agent.PolicyBlend.WalkWeight) : FVector2f(-1,-1);
        const bool bOverrideFootRotation=FootRotationWeights.X>=0 || FootRotationWeights.Y>=0;
		// Tempering is locomotion-only. Half attacks also need their lower-body
		// movement unmodified, even though they use the locomotion lower policy.
		const auto* Tempering = !Agent.DefensePose && !Agent.Slash.bActive
			? ProphecyLowerTempering::Find(AgentActors[AgentIndex]) : nullptr;
		const bool bReconstructTemperedLegs = Tempering && ProphecyLegChainDebug::IsEnabled(AgentActors[AgentIndex]);
		const auto* RightTempering=Tempering ? &ProphecyLowerTempering::RightFootSettings(AgentActors[AgentIndex],*Tempering) : nullptr;
        const bool bTemperLeft=bReconstructTemperedLegs && NeedsTemperedLegReconstruction(*Tempering,*Tempering);
        const bool bTemperRight=bReconstructTemperedLegs && NeedsTemperedLegReconstruction(*Tempering,*RightTempering);
        bool bSupportSource=(bTemperLeft && Tempering->FeetRotation>0.f) || (bTemperRight && RightTempering->FeetRotation>0.f);
#if WITH_EDITOR
		if (bSupportSource) bSupportSource=CVarTemperingSupportSource.GetValueOnGameThread()!=0;
#endif
		float RunTemperingSource[StateDim],WalkTemperingSource[StateDim];
		auto* PinReachGuard=ProphecyWalkPinning::FindReachGuard(AgentActors[AgentIndex]);
		FVector3f UnpinnedFeet[2][2]; // [Run/Walk][left/right], populated only when enabled.
		const auto* PinBackwardBound=(!Agent.DefensePose && !Agent.Slash.bActive && Agent.RecoveryWeights.NeedsWalk())
			? ProphecyWalkPinning::FindBackwardBound(AgentActors[AgentIndex]) : nullptr;
		const auto* PinCircleBound=(!Agent.DefensePose && !Agent.Slash.bActive && Agent.RecoveryWeights.NeedsWalk())
			? ProphecyWalkPinning::FindCircleBound(AgentActors[AgentIndex]) : nullptr;
		FVector BoundRoot,BoundForward,CircleRoot;
		if (PinBackwardBound || PinCircleBound)
		{
			// Use the same zero-based continuous window exposed to Blueprint. Its
			// root0 is the applied current root, not the discrete previous sample.
			TArray<FTransform> Roots;TArray<float> Times;
			if (GetAgentContinuousLocomotionRootWindow(AgentActors[AgentIndex]->GetAgentHandle(),Roots,Times))
			{
				if (PinBackwardBound)
				{
					if (Roots.IsValidIndex(PinBackwardBound->RootIndex))
					{
						ProphecyWalkPinning::BackwardReference(Roots[0],Roots[PinBackwardBound->RootIndex],BoundRoot,BoundForward);
						ProphecyWalkPinning::ApplyBackwardTargetHeading(AgentActors[AgentIndex],BoundForward);
						if (BoundForward.IsNearlyZero()) PinBackwardBound=nullptr;
					}
					else PinBackwardBound=nullptr;
				}
				if (PinCircleBound)
				{
					if (Roots.IsValidIndex(PinCircleBound->RootIndex)) CircleRoot=Roots[PinCircleBound->RootIndex].GetLocation();
					else PinCircleBound=nullptr;
				}
			}
			else { PinBackwardBound=nullptr;PinCircleBound=nullptr; }
		}
		// Correct each policy with its own pinning semantics before mixing the poses.
		const float PinTransferMultiplier=PinBackwardBound
			? ProphecyWalkPinning::BackwardTransferMultiplier(AgentActors[AgentIndex]) : 0.f;
		// The ordinary single-policy path performs exactly one correction.
		auto CorrectPolicy = [&](const float* Raw, bool bWalkPolicy, float* Transition,
			FVector2f& RawPin, FVector2f& EffectivePin,bool bVisiblePolicy=true)
		{
			for (int32 Index = 0; Index < StateDim; ++Index) Transition[Index] = CurrentState[Index] + Raw[Index];
            if (bOverrideFootRotation) OverrideRecoveryFootRotations(CurrentState,
                Impl->OutputBuffer.GetData()+AgentIndex*PolicyOutputDim,
                Impl->WalkOutputBuffer.GetData()+AgentIndex*PolicyOutputDim,FootRotationWeights,Transition);
			CleanState(Transition, *Impl);
			if (bSupportSource) FMemory::Memcpy(bWalkPolicy ? WalkTemperingSource : RunTemperingSource,Transition,StateDim*sizeof(float));
			if (Tempering)
			{
				TemperLowerPose(*Tempering, StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex), Transition,RightTempering);
			}
	
			float Heights[2] = { 0.0f, 0.0f };
			float Pin[2];
			if (bWalkPolicy && Impl->bWalkPinLegacy)
			{
				const bool bBothPinned = Raw[41] < 0.0f && Raw[42] < 0.0f;
				Pin[0] = bBothPinned || Raw[41] <= Raw[42] ? 1.0f : 0.0f;
				Pin[1] = bBothPinned || Raw[42] < Raw[41] ? 1.0f : 0.0f;
				ProphecyWalkPinning::Apply(AgentActors.IsValidIndex(AgentIndex) ? AgentActors[AgentIndex] : nullptr,
					Raw[41],Raw[42],Impl->PinScale,Pin[0],Pin[1]);
			}
			else
			{
				Pin[0] = 1.0f / (1.0f + FMath::Exp(Raw[41] * Impl->PinScale));
				Pin[1] = 1.0f / (1.0f + FMath::Exp(Raw[42] * Impl->PinScale));
			}
			const int32 PosOffsets[2] = { 9, 25 };
			const int32 RotOffsets[2] = { 12, 28 };
			const int32 ToeOffsets[2] = { 24, 40 };
			for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
			{
				Heights[LimbIndex] = Impl->LowestFootHeight(LimbIndex, ReadStateVec3(Transition, PosOffsets[LimbIndex]), MatrixFromRot6(Transition + RotOffsets[LimbIndex]), Transition[ToeOffsets[LimbIndex]], bWalkPolicy);
			}
			RawPin = FVector2f(Pin[0], Pin[1]);
			if (PinSmoothing && bWalkPolicy && bVisiblePolicy)
				ProphecyWalkPinning::SmoothPins(*PinSmoothing,Pin[0],Pin[1]);
			const AProphecyAgent* PinActor = AgentActors.IsValidIndex(AgentIndex) ? AgentActors[AgentIndex] : nullptr;
			const bool bOverridePin = PinActor && PinActor->bOverrideLocomotionPinThreshold;
			const float FadeHeight = bOverridePin ? PinActor->LocomotionPinThresholdM : Impl->NearFloorFadeHeight;
			const float FullHeight = bOverridePin ? PinActor->LocomotionFullPinHeightM : Impl->NearFloorFullHeight;
			const bool bLeftBelow = !bWalkPolicy && Heights[0] < FadeHeight;
			const bool bRightBelow = !bWalkPolicy && Heights[1] < FadeHeight;
			if (bLeftBelow || bRightBelow)
			{
				const int32 Selected = bLeftBelow && bRightBelow ? (Raw[41] <= Raw[42] ? 0 : 1) : (Heights[0] <= Heights[1] ? 0 : 1);
				const float FadeSpan = FMath::Max(1.0e-6f, FadeHeight - FullHeight);
				const float Force = FMath::Clamp((FadeHeight - Heights[Selected]) / FadeSpan, 0.0f, 1.0f) * Impl->NearFloorMinPin;
				Pin[Selected] = FMath::Max(Pin[Selected], Force);
			}
	
			const bool bTransfer=PinTransferMultiplier>0 && bWalkPolicy && bVisiblePolicy;
			if (bTransfer)
			{
				FVector2f BackwardCaps,OwnCaps;
				for (int32 I=0;I<2;++I)
				{
					const FVector FootWorld=LowerPointToWorld(ReadStateVec3(CurrentState,PosOffsets[I]),
						Impl->SeedRootRot,Agent.FedInputRoot,Agent.FedInputYaw);
					BackwardCaps[I]=ProphecyWalkPinning::BoundPin(1.f,*PinBackwardBound,FootWorld,BoundRoot,BoundForward);
					OwnCaps[I]=PinCircleBound ? ProphecyWalkPinning::CircleBoundPin(BackwardCaps[I],*PinCircleBound,FootWorld,CircleRoot) : BackwardCaps[I];
				}
				ProphecyWalkPinning::TransferBackwardPins(PinTransferMultiplier,BackwardCaps,OwnCaps,Pin[0],Pin[1]);
			}
            if(TickPins && bWalkPolicy && bVisiblePolicy)
            {
                auto& T=TickPins->Current;FVector2f BackCaps(1,1);
                for(int32 I=0;I<2;++I)
                {
                    const FVector Foot=LowerPointToWorld(ReadStateVec3(CurrentState,PosOffsets[I]),Impl->SeedRootRot,Agent.FedInputRoot,Agent.FedInputYaw);
                    if(PinBackwardBound) BackCaps[I]=ProphecyWalkPinning::BoundPin(1.f,*PinBackwardBound,Foot,BoundRoot,BoundForward);
                    T.Cap[I]=PinCircleBound?ProphecyWalkPinning::CircleBoundPin(BackCaps[I],*PinCircleBound,Foot,CircleRoot):BackCaps[I];
                }
                if(bTransfer) T.Minimum=FVector2f(FMath::Clamp((1.f-BackCaps.Y)*PinTransferMultiplier,0.f,1.f),FMath::Clamp((1.f-BackCaps.X)*PinTransferMultiplier,0.f,1.f));
            }
			for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
			{
				const FVector3f PredPos = ReadStateVec3(Transition, PosOffsets[LimbIndex]);
				const FMat3f PredRot = MatrixFromRot6(Transition + RotOffsets[LimbIndex]);
				const float PredToe = Transition[ToeOffsets[LimbIndex]];
				if (!bTransfer && (PinBackwardBound || PinCircleBound) && bWalkPolicy && bVisiblePolicy)
				{
					// Measure the foot that is currently being held. Measuring only the
					// free prediction could hide a planted foot left behind by the root.
					const FVector FootWorld=LowerPointToWorld(ReadStateVec3(CurrentState,PosOffsets[LimbIndex]),
						Impl->SeedRootRot,Agent.FedInputRoot,Agent.FedInputYaw);
					if (PinBackwardBound) Pin[LimbIndex]=ProphecyWalkPinning::BoundPin(Pin[LimbIndex],*PinBackwardBound,FootWorld,BoundRoot,BoundForward);
					if (PinCircleBound) Pin[LimbIndex]=ProphecyWalkPinning::CircleBoundPin(Pin[LimbIndex],*PinCircleBound,FootWorld,CircleRoot);
				}
				if (PinReachGuard && bVisiblePolicy)
				{
					FVector3f FreePos=PredPos;
					FreePos.Z+=FMath::Max(0.f,Impl->GroundHeight-Impl->LowestFootPointZ(LimbIndex,FreePos,PredRot,PredToe,bWalkPolicy));
					UnpinnedFeet[bWalkPolicy ? 1 : 0][LimbIndex]=FreePos;
				}
				FVector3f OutPos = PredPos;
				if (Impl->FootRollSteps > 0)
				{
					const FVector3f CurPos = ReadStateVec3(CurrentState, PosOffsets[LimbIndex]);
					const FMat3f CurRot = MatrixFromRot6(CurrentState + RotOffsets[LimbIndex]);
					const float CurToe = CurrentState[ToeOffsets[LimbIndex]];
					const FVector3f RollDelta = Impl->IntegratedFootRollDelta(LimbIndex, CurRot, CurToe, PredRot, PredToe, bWalkPolicy);
					const FVector3f PinnedPos(CurPos.X + RollDelta.X, CurPos.Y + RollDelta.Y, PredPos.Z);
                    if(TickPins && bWalkPolicy && bVisiblePolicy) TickPins->Current.Delta[LimbIndex]=PinnedPos-PredPos;
					OutPos = FMath::Lerp(PredPos, PinnedPos, Pin[LimbIndex]);
				}
				const float Lowest = Impl->LowestFootPointZ(LimbIndex, OutPos, PredRot, PredToe, bWalkPolicy);
				OutPos.Z += FMath::Max(0.0f, Impl->GroundHeight - Lowest);
				WriteStateVec3(Transition, PosOffsets[LimbIndex], OutPos);
			}
			CleanState(Transition, *Impl);
			EffectivePin = FVector2f(Pin[0], Pin[1]);
            if(TickPins && bWalkPolicy && bVisiblePolicy) TickPins->Current.Applied=EffectivePin;
		};
		FVector2f RawPin, EffectivePin;
		if (auto* H=ProphecyHandRecovery::Frame(AgentActors[AgentIndex]))
		{
			FVector2f UnusedRaw,UnusedPin;
			for(int32 P=0;P<2;++P) if(H->Need[P]) CorrectPolicy(H->Raw[P],P==1,H->Lower[P],UnusedRaw,UnusedPin,false);
		}
		FVector2D RawDebug(Raw[41], Raw[42]);
		FVector3f LegSourcePelvis[2];
		FMat3f LegSourcePelvisRotation[2];
		const bool bRegional=Agent.RecoveryWeights.Left!=Agent.RecoveryWeights.Pelvis || Agent.RecoveryWeights.Right!=Agent.RecoveryWeights.Pelvis;
		if (Agent.RecoveryWeights.NeedsBoth())
		{
			float WalkState[StateDim];
			FVector2f WalkRawPin, WalkEffectivePin;
			const float* WalkRaw = Impl->WalkOutputBuffer.GetData() + AgentIndex * PolicyOutputDim;
			CorrectPolicy(Raw, false, Transition, RawPin, EffectivePin);
			CorrectPolicy(WalkRaw, true, WalkState, WalkRawPin, WalkEffectivePin);
			for (int32 I=0;I<2;++I)
			{
				const float W=I==0 ? Agent.RecoveryWeights.Left : Agent.RecoveryWeights.Right;
				if (bRegional)
				{
					float SourcePelvis[9];FMemory::Memcpy(SourcePelvis,Transition,sizeof(SourcePelvis));
					BlendLowerPolicyRegion(SourcePelvis,WalkState,0,W);
					LegSourcePelvis[I]=ReadStateVec3(SourcePelvis,0);LegSourcePelvisRotation[I]=MatrixFromRot6(SourcePelvis+3);
				}
				const int32 O=9+16*I;
				BlendLowerPolicyRegion(Transition,WalkState,O,W);
				RawPin[I]=FMath::Lerp(RawPin[I],WalkRawPin[I],W);
				EffectivePin[I]=FMath::Lerp(EffectivePin[I],WalkEffectivePin[I],W);
				RawDebug[I]=FMath::Lerp(RawDebug[I],double(WalkRaw[41+I]),double(W));
			}
			BlendLowerPolicyRegion(Transition,WalkState,0,Agent.RecoveryWeights.Pelvis);
		}
		else CorrectPolicy(Raw, bWalkPolicy, Transition, RawPin, EffectivePin);
		const FVector2f ReturningCalfDelta(ProphecyKickFootLeeway::ReturningLengthDeltaCm(AgentActors[AgentIndex],0)/100.f,
			ProphecyKickFootLeeway::ReturningLengthDeltaCm(AgentActors[AgentIndex],1)/100.f);
		const bool bReturnLengths=ReturningCalfDelta.X!=0 || ReturningCalfDelta.Y!=0;
		if (PinReachGuard && (!Agent.Slash.bActive || Agent.Slash.bHalf) && Impl->FootRollSteps>0)
		{
			// Judge the actual mixed pelvis/foot, not an unused source policy. A veto
			// restores the same policy mixture without its horizontal pin constraint;
			// it never elects the opposite foot or changes the knee's bend guidance.
			const FVector3f Pelvis=ReadStateVec3(Transition,0);
			const FMat3f PelvisRotation=MatrixFromRot6(Transition+3);
			for (int32 I=0;I<2;++I)
			{
				const float W=I==0 ? Agent.RecoveryWeights.Left : Agent.RecoveryWeights.Right;
				if (W<=0.f || EffectivePin[I]<=0.f) continue;
				const auto Limb=Impl->BlendLimb(I,W);
				const int32 O=9+16*I;
				const FVector3f Hip=Pelvis+TransformRow(Impl->LocalOffsets[Limb.Start],PelvisRotation);
				// Match the connected solver's full-extension boundary (metres),
				// including the currently returning signed calf length after kicks.
				const float Reach=Impl->LocalOffsets[Limb.Mid].Size()+Impl->LocalOffsets[Limb.End].Size()+ReturningCalfDelta[I]-2.e-5f;
				if (!ProphecyWalkPinning::RejectPin(*PinReachGuard,I,Hip,ReadStateVec3(Transition,O),Reach)) continue;
				FVector3f FreePos=Agent.RecoveryWeights.NeedsBoth()
					? FMath::Lerp(UnpinnedFeet[0][I],UnpinnedFeet[1][I],W) : UnpinnedFeet[bWalkPolicy ? 1 : 0][I];
				const auto Axes=Impl->BuildFootAxes(Limb,FreePos,MatrixFromRot6(Transition+O+3),Transition[O+15]);
				FreePos.Z+=FMath::Max(0.f,Impl->GroundHeight-ExactFootMinimum(Axes,Impl->FootHalfDims,Impl->ToeHalfDims));
				WriteStateVec3(Transition,O,FreePos);
				EffectivePin[I]=0.f;
				if (PinSmoothing) ProphecyWalkPinning::ClearSmoothedFoot(*PinSmoothing,I);
                if(TickPins) {TickPins->Current.Cap[I]=0;TickPins->Current.Applied[I]=0;TickPins->Current.Delta[I]=FVector3f::ZeroVector;}
			}
		}
		if (bReconstructTemperedLegs || ((bReturnLengths || (bRegional && !Tempering)) && ProphecyLegChainDebug::IsEnabled(AgentActors[AgentIndex])))
		{
			const AProphecyAgent* Controls=AgentActors[AgentIndex];
			const float MinimumReachMultiplier=ProphecyLowerTempering::MinimumLegReachMultiplier(Controls);
			const bool bOuterReach=Controls->bOverrideLocomotionCalfClamp
				? Controls->bLocomotionCalfClamp : bClampCalf && CalfClampLengthMultiplier>0.f;
			// Restore fixed-length chains AFTER both pinning and checkpoint blending,
			// before recurrence/upper inference. Keep the original source knee frames;
			// never reconstruct a pole from independently tempered pelvis/feet/thigh.
			for (int32 I = 0; I < 2; ++I)
			{
				const float W=I==0 ? Agent.RecoveryWeights.Left : Agent.RecoveryWeights.Right;
				const bool bTemperThisLeg=I==0 ? bTemperLeft : bTemperRight;
				if (!bTemperThisLeg && W==Agent.RecoveryWeights.Pelvis && !bReturnLengths) continue;
				auto Limb = W >= 1.f ? Impl->WalkLimbs[I] : Impl->Limbs[I];
				if (W > 0.f && W < 1.f)
				{
					Limb.LocalPoleAxes[0] = SafeNormal(FMath::Lerp(Limb.LocalPoleAxes[0], Impl->WalkLimbs[I].LocalPoleAxes[0], W));
					Limb.ToeOffset = FMath::Lerp(Limb.ToeOffset, Impl->WalkLimbs[I].ToeOffset, W);
					Limb.ToeAxis = SafeNormal(FMath::Lerp(Limb.ToeAxis, Impl->WalkLimbs[I].ToeAxis, W));
				}
				const int32 O = 9 + 16 * I;
				const float* NNSource=nullptr;
				float RegionalSource[StateDim];
				if (bSupportSource)
				{
					if (!Agent.RecoveryWeights.NeedsBoth()) NNSource=bWalkPolicy ? WalkTemperingSource : RunTemperingSource;
					else if (W==0.f) NNSource=RunTemperingSource;
					else if (W==1.f) NNSource=WalkTemperingSource;
					else
					{
						FMemory::Memcpy(RegionalSource,RunTemperingSource,sizeof(RegionalSource));
						// Transport each leg from its own checkpoint mixture's pelvis,
						// even when the final pelvis uses a different recovery weight.
						BlendLowerPolicyRegion(RegionalSource,WalkTemperingSource,0,W);
						BlendLowerPolicyRegion(RegionalSource,WalkTemperingSource,O,W);
						NNSource=RegionalSource;
					}
				}
				const FVector3f Ankle = ReadStateVec3(Transition, O);
				const auto Axes = Impl->BuildFootAxes(Limb, Ankle, MatrixFromRot6(Transition + O + 3), Transition[O + 15]);
				const FPelvisLegGeometry G{Impl->LocalOffsets[Limb.Start], Impl->LocalOffsets[Limb.Mid], Limb.LocalPoleAxes[0],
					Impl->LocalOffsets[Limb.End].Size()+ReturningCalfDelta[I], Ankle.Z + Impl->GroundHeight
					- ExactFootMinimum(Axes, Impl->FootHalfDims, Impl->ToeHalfDims) + 1.e-5f};
				if (bTemperThisLeg) ResolveTemperedLeg(I==0 ? *Tempering : *RightTempering, StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),
					G, Transition, O,Limb.ToeOffset,
					FVector3f(Impl->LocalOffsets[Limb.End].X<0.f ? 1.f : -1.f,0,0),
					FMath::Max(.15f,FMath::Abs(G.KneeOffset.Size()-G.CalfLength)*MinimumReachMultiplier),bOuterReach,
					NNSource);
				else if (W!=Agent.RecoveryWeights.Pelvis)
					ResolvePelvisLeg(LegSourcePelvis[I],LegSourcePelvisRotation[I],ReadStateVec3(Transition,0),
						MatrixFromRot6(Transition+3),G,Transition,O,nullptr,false,nullptr,0.f,bOuterReach);
				else if (bReturnLengths)
					ResolvePelvisLeg(ReadStateVec3(Transition,0),MatrixFromRot6(Transition+3),ReadStateVec3(Transition,0),
						MatrixFromRot6(Transition+3),G,Transition,O,nullptr,false,nullptr,0.f,bOuterReach);
			}
		}
        if(TickPins)
        {
            TickPins->Current.WalkWeight=Agent.RecoveryWeights.Legs();
            for(int32 I=0;I<2;++I) TickPins->Current.OtherPin[I]=EffectivePin[I]-TickPins->Current.Applied[I]*TickPins->Current.WalkWeight[I];
        }
		Agent.PinProbability = EffectivePin;
		auto* Debug = Impl->PinningDebug.IsEmpty() ? nullptr : Impl->PinningDebug.Find(AgentIndex);
		if (Debug && Debug->Owner.Get() == AgentActors[AgentIndex])
		{
			Debug->Locomotion.RawNetworkOutput = RawDebug;
			Debug->Locomotion.RawPinning = FVector2D(RawPin);
			Debug->Locomotion.EffectivePinning = FVector2D(EffectivePin);
			Debug->Locomotion.SampleTimeSeconds = GetWorld()->GetTimeSeconds();
			Debug->Locomotion.bWalkPolicy = bWalkPolicy;
			Debug->Locomotion.bAppliesToVisibleFeet = !Agent.Slash.bActive || Agent.Slash.bHalf;
		}
		Agent.PreviousPublishedRoot = Agent.PublishedRoot;
		Agent.PreviousPublishedYaw = Agent.PublishedYaw;
		Agent.PublishedRoot = Agent.CurRootPos;
		Agent.PublishedYaw = Agent.CurRootYaw;
		Agent.bPublishedUseWalkPolicy = bWalkPolicy;
		Agent.PublishedWalkWeight = Agent.RecoveryWeights.Pelvis;
		Agent.PublishedLegWalkWeights=Agent.RecoveryWeights.Legs();

		// Commit inertia and the resolved legs to the lower state BEFORE recurrence
		// and upper features. Full attacks own their lower stage in FSlashNative.
		if (!(Agent.Slash.bActive && !Agent.Slash.bHalf) && ProphecyPelvisInertia::HasTarget(AgentActors[AgentIndex]))
		{
			const AProphecyAgent* InertiaActor=AgentActors[AgentIndex];
			auto CarrierFor = [&](const FVector3f& Root, float Yaw)
			{
				const FTransform Capsule(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),
					TrainingToUnreal(Root)+FVector::UpVector*InertiaActor->GetAgentCapsule()->GetScaledCapsuleHalfHeight());
				return (InertiaActor->bManualNNPoseApplication ? InertiaActor->GetAgentMesh()->GetRelativeTransform()
					: InertiaActor->GetAuthoredMeshRelativeTransform())*Capsule;
			};
			FPelvisLegGeometry Legs[2];
			for (int32 I=0; I<2; ++I)
			{
				const auto L=Impl->BlendLimb(I,Agent.PublishedLegWalkWeights[I]);
				const int32 O=9+16*I;
				const FVector3f Ankle=ReadStateVec3(Transition,O);
				const auto Axes=Impl->BuildFootAxes(L,Ankle,MatrixFromRot6(Transition+O+3),Transition[O+15]);
				Legs[I]={Impl->LocalOffsets[L.Start],Impl->LocalOffsets[L.Mid],L.LocalPoleAxes[0],
					Impl->LocalOffsets[L.End].Size()+ProphecyKickFootLeeway::ReturningLengthDeltaCm(InertiaActor,I)/100.f, Ankle.Z+Impl->GroundHeight
					-ExactFootMinimum(Axes,Impl->FootHalfDims,Impl->ToeHalfDims)+1.e-5f};
			}
			CorrectLowerPelvis(InertiaActor,Clock?Clock->Step->SourceTimeSeconds:double(GetWorld()->GetTimeSeconds())-Impl->AccumulatedStepSeconds+StepSeconds,
				Clock?Clock->Step->WorldIntervals[AgentIndex]:StepSeconds,
				CarrierFor(Agent.PreviousPublishedRoot,Agent.PreviousPublishedYaw),CarrierFor(Agent.PublishedRoot,Agent.PublishedYaw),
				StateSlice(Impl->PreviousPublishedStateBuffer,AgentIndex),Transition,Legs);
		}

		FMemory::Memcpy(NextState, Transition, StateDim * sizeof(float));
		AdvanceAgentMover(AgentIndex,StepSeconds);
	}
	if (Clock)
	{
		// Global buffer swaps would advance histories of every skipped lane.
		for (int32 I=0;I<CrowdSize;++I) if (Clock->Step->Due[I] &&
			(!AgentActors.IsValidIndex(I) || !AgentActors[I] || AgentActors[I]->bNNInferenceEnabled))
		{
			FMemory::Memcpy(StateSlice(Impl->PrevStateBuffer,I),StateSlice(Impl->CurStateBuffer,I),StateDim*sizeof(float));
			FMemory::Memcpy(StateSlice(Impl->CurStateBuffer,I),StateSlice(Impl->NextStateBuffer,I),StateDim*sizeof(float));
		}
	}
	else
	{
		Swap(Impl->PrevStateBuffer, Impl->CurStateBuffer);
		Swap(Impl->CurStateBuffer, Impl->NextStateBuffer);
	}
}

void AProphecyNNLocomotionManager::CacheUpperRootRotationHorizon(const AProphecyAgent* Agent, float Horizon)
{
	if (!IsInGameThread() || !Impl || !IsValid(Agent)) return;
	const auto Handle = Agent->GetAgentHandle();
	if (Impl->Agents.IsValidIndex(Handle.Index) && ResolveAgent(Handle) == Agent)
		Impl->Agents[Handle.Index].UpperRootRotationHorizon = Horizon;
}

void AProphecyNNLocomotionManager::BuildUpperInputBatch()
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	for (int32 AgentIndex = 0; AgentIndex < BatchSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		if (Impl->Agents[AgentIndex].DefensePose) continue;
		if (AgentActors.IsValidIndex(AgentIndex) && AgentActors[AgentIndex] &&
			!AgentActors[AgentIndex]->bNNInferenceEnabled)
		{
			continue;
		}

		const float* PreviousUpper = UpperStateSlice(Impl->UpperPreviousStateBuffer, AgentIndex);
		const float* CurrentUpper = UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex);
		const float* CurrentBase = UpperStateSlice(Impl->UpperCurrentBaseBuffer, AgentIndex);
		float* NextBase = UpperStateSlice(Impl->UpperNextBaseBuffer, AgentIndex);
		BuildUpperBaseFromLower(StateSlice(Impl->CurStateBuffer, AgentIndex), *Impl, NextBase);

		float* Write = Impl->UpperInputBuffer.GetData() + AgentIndex * UpperInputDim;
		FMemory::Memcpy(Write, PreviousUpper, UpperStateDim * sizeof(float));
		Write += UpperStateDim;
		for (int32 Index = 0; Index < UpperStateDim; ++Index)
		{
			Write[Index] = NextBase[Index] + CurrentUpper[Index] - CurrentBase[Index];
		}
		CleanUpperState(Write);
		Write += UpperStateDim;
		FMemory::Memcpy(
			Write,
			TransformStateSlice(Impl->PreviousPelvisHeadingBuffer, AgentIndex),
			9 * sizeof(float));
		Write += 9;
		FMemory::Memcpy(
			Write,
			TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex),
			9 * sizeof(float));
		Write += 9;
		LowerTransformToHeading(
			StateSlice(Impl->CurStateBuffer, AgentIndex), 0, 3, *Impl, Write);
		Write += 9;
		FMemory::Memcpy(
			Write,
			Impl->InputBuffer.GetData() + AgentIndex * InputDim + 117,
			35 * sizeof(float));
		// Intervene only in the upper copy, after lower inference/rebasing. The default
		// cached scalar skips all additional copies, trigonometry and interpolation.
		ProphecyUpperRootHorizon::Resample(Write, Impl->Agents[AgentIndex].UpperRootRotationHorizon);
		Write += 35;

		AProphecyAgent* AgentActor = AgentActors.IsValidIndex(AgentIndex)
			? AgentActors[AgentIndex].Get()
			: nullptr;
		// Equipment owns this input. Resolve at encoding time so failed equips, drops and
		// external sword destruction cannot leave a stale Blueprint flag in the NN tensor.
		if (AgentActor) AgentActor->bUpperNNHasSword = IsValid(AgentActor->GetHeldSword());
		*Write++ = AgentActor && AgentActor->bUpperNNHasSword ? 1.0f : -1.0f;
		const float* CurrentLower = StateSlice(Impl->PrevStateBuffer, AgentIndex);
		const float* NextLower = StateSlice(Impl->CurStateBuffer, AgentIndex);
		for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
		{
			const int32 PositionOffset = LimbIndex == 0 ? 9 : 25;
			const int32 RotationOffset = LimbIndex == 0 ? 12 : 28;
			LowerTransformToHeading(CurrentLower, PositionOffset, RotationOffset, *Impl, Write);
			Write += 9;
		}
		for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
		{
			const int32 PositionOffset = LimbIndex == 0 ? 9 : 25;
			const int32 RotationOffset = LimbIndex == 0 ? 12 : 28;
			LowerTransformToHeading(NextLower, PositionOffset, RotationOffset, *Impl, Write);
			Write += 9;
		}
		*Write++ = AgentActor ? FMath::Clamp(AgentActor->UpperNNGazeYawNormalized, -1.0f, 1.0f) : 0.0f;
		*Write++ = AgentActor ? FMath::Clamp(AgentActor->UpperNNGazePitchNormalized, -1.0f, 1.0f) : 0.0f;
		check(int32(Write - (Impl->UpperInputBuffer.GetData() + AgentIndex * UpperInputDim)) == UpperInputDim);
	}
}

namespace { bool RunHandRecoverySources(AProphecyNNLocomotionManager* Manager,AProphecyNNLocomotionManager::FImpl* Impl,TArrayView<TObjectPtr<AProphecyAgent>> Actors); }
bool AProphecyNNLocomotionManager::RunUpperModelBatch()
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	bool bNeedUpper = false;
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		if (Impl->Agents[AgentIndex].DefensePose) continue;
		bNeedUpper |= !AgentActors.IsValidIndex(AgentIndex) || !AgentActors[AgentIndex] ||
			AgentActors[AgentIndex]->bNNInferenceEnabled;
	}
	if (!bNeedUpper)
	{
		return true;
	}
	if (!Impl->UpperModel.Run(Impl->UpperInputBuffer, Impl->UpperOutputBuffer))
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Upper NNE policy RunSync failed."));
		SetActorTickEnabled(false);
		return false;
	}
	return RunHandRecoverySources(this,Impl,MakeArrayView(AgentActors));
}

namespace { void CorrectLocomotionHands(AProphecyNNLocomotionManager::FImpl* Impl,AProphecyAgent* Actor,int32 Index,double Time,double Dt,float CoreFollow); }
void AProphecyNNLocomotionManager::ApplyUpperOutputBatch()
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		if (Impl->Agents[AgentIndex].DefensePose) continue;
		if (AgentActors.IsValidIndex(AgentIndex) && AgentActors[AgentIndex] &&
			!AgentActors[AgentIndex]->bNNInferenceEnabled)
		{
			continue;
		}
		float* PreviousUpper = UpperStateSlice(Impl->UpperPreviousStateBuffer, AgentIndex);
		float* CurrentUpper = UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex);
		float* CurrentBase = UpperStateSlice(Impl->UpperCurrentBaseBuffer, AgentIndex);
		const float* NextBase = UpperStateSlice(Impl->UpperNextBaseBuffer, AgentIndex);
		float* PreviousPublished = UpperStateSlice(
			Impl->UpperPreviousPublishedStateBuffer, AgentIndex);
		float* Published = UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex);
		FMemory::Memcpy(PreviousPublished, Published, UpperStateDim * sizeof(float));
		FMemory::Memcpy(PreviousUpper, CurrentUpper, UpperStateDim * sizeof(float));
		const float* Prior = Impl->UpperInputBuffer.GetData() + AgentIndex * UpperInputDim + 90;
		const float* Delta = Impl->UpperOutputBuffer.GetData() + AgentIndex * UpperStateDim;
		for (int32 Index = 0; Index < UpperStateDim; ++Index)
		{
			CurrentUpper[Index] = Prior[Index] + Delta[Index];
		}
		CleanUpperState(CurrentUpper);
		const float CoreFollow=Impl->Agents[AgentIndex].Slash.bActive ? 1.f : ProphecyCoreTempering::Rotation(AgentActors[AgentIndex]);
		if (!Impl->Agents[AgentIndex].Slash.bActive &&
			(CoreFollow<1 || ProphecyUpperBodyInertia::Active(AgentActors[AgentIndex]) || ProphecySlashReturn::Active(AgentActors[AgentIndex]) || ProphecyHandRecovery::Frame(AgentActors[AgentIndex]) || ProphecyHandRecovery::Tempering(AgentActors[AgentIndex]) ||
			ProphecyHandInertia::IsActive(AgentActors[AgentIndex],Impl->Agents[AgentIndex].PublishedWalkWeight,false)))
			CorrectLocomotionHands(Impl,AgentActors[AgentIndex],AgentIndex,
				Clock?Clock->Step->SourceTimeSeconds:double(GetWorld()->GetTimeSeconds())-Impl->AccumulatedStepSeconds+1./NNUpdateHz,
				Clock?Clock->Step->WorldIntervals[AgentIndex]:1./NNUpdateHz,CoreFollow);
		FMemory::Memcpy(Published, CurrentUpper, UpperStateDim * sizeof(float));
		FMemory::Memcpy(CurrentBase, NextBase, UpperStateDim * sizeof(float));
		FMemory::Memcpy(
			TransformStateSlice(Impl->PreviousPelvisHeadingBuffer, AgentIndex),
			TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex),
			9 * sizeof(float));
		LowerTransformToHeading(
			StateSlice(Impl->CurStateBuffer, AgentIndex), 0, 3, *Impl,
			TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex));
	}
}

void AProphecyNNLocomotionManager::ApplyAnimationLayers(float StepSeconds)
{
	const auto* Clock=ProphecyAgentTime::Context(this);
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		if (Clock && !Clock->Step->Due[AgentIndex]) continue;
		if (!Impl->Agents.IsValidIndex(AgentIndex) ||
			!AgentActors.IsValidIndex(AgentIndex) ||
			!AgentActors[AgentIndex])
		{
			continue;
		}

		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		FImpl::FAgent::FAnimationLayer& Layer = Agent.AnimationLayer;
		UAnimSequenceBase* Animation = Layer.Animation.Get();
		AProphecyAgent* AgentActor = AgentActors[AgentIndex];
		if (!Animation)
		{
			continue;
		}

		const bool bNNFrozen = !AgentActor->bNNInferenceEnabled;
		if (bNNFrozen)
		{
			FMemory::Memcpy(
				StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),
				StateSlice(Impl->PublishedStateBuffer, AgentIndex),
				StateDim * sizeof(float));
			FMemory::Memcpy(
				StateSlice(Impl->PrevStateBuffer, AgentIndex),
				StateSlice(Impl->CurStateBuffer, AgentIndex),
				StateDim * sizeof(float));
			FMemory::Memcpy(
				UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer, AgentIndex),
				UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex),
				UpperStateDim * sizeof(float));
			FMemory::Memcpy(
				UpperStateSlice(Impl->UpperPreviousStateBuffer, AgentIndex),
				UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex),
				UpperStateDim * sizeof(float));
			Agent.PreviousPublishedRoot = Agent.PublishedRoot;
			Agent.PreviousPublishedYaw = Agent.PublishedYaw;
			Agent.bPreviousPublishedUseWalkPolicy = Agent.bPublishedUseWalkPolicy;
		Agent.PreviousPublishedWalkWeight = Agent.PublishedWalkWeight;
		Agent.PreviousPublishedLegWalkWeights=Agent.PublishedLegWalkWeights;
			FMemory::Memcpy(
				StateSlice(Impl->PublishedStateBuffer, AgentIndex),
				StateSlice(Impl->AnimationFrozenBaseLowerStateBuffer, AgentIndex),
				StateDim * sizeof(float));
			FMemory::Memcpy(
				UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex),
				UpperStateSlice(Impl->AnimationFrozenBaseUpperStateBuffer, AgentIndex),
				UpperStateDim * sizeof(float));
		}

		const float PlayLength = FMath::Max(0.0f, Animation->GetPlayLength());
		Layer.ElapsedSeconds += StepSeconds;
		Layer.PlaybackTimeSeconds += StepSeconds * Layer.PlayRate;
		if (Layer.bLoop && PlayLength > UE_SMALL_NUMBER)
		{
			Layer.PlaybackTimeSeconds = FMath::Fmod(Layer.PlaybackTimeSeconds, PlayLength);
		}
		else
		{
			Layer.PlaybackTimeSeconds = FMath::Min(Layer.PlaybackTimeSeconds, PlayLength);
		}

		const float BlendInWeight = Layer.BlendInSeconds <= UE_SMALL_NUMBER
			? 1.0f
			: SmoothUnitAlpha(Layer.ElapsedSeconds / Layer.BlendInSeconds);
		float BlendWeight = BlendInWeight;
		bool bCompletesThisStep = false;
		if (Layer.bStopping)
		{
			Layer.StopElapsedSeconds += StepSeconds;
			const float StopAlpha = Layer.StopDurationSeconds <= UE_SMALL_NUMBER
				? 1.0f
				: SmoothUnitAlpha(Layer.StopElapsedSeconds / Layer.StopDurationSeconds);
			BlendWeight = Layer.StopStartWeight * (1.0f - StopAlpha);
			bCompletesThisStep = StopAlpha >= 1.0f;
		}
		else if (!Layer.bLoop)
		{
			const float RemainingPlaybackSeconds = FMath::Max(
				0.0f,
				(PlayLength - Layer.PlaybackTimeSeconds) / Layer.PlayRate);
			if (RemainingPlaybackSeconds <= Layer.BlendOutSeconds)
			{
				if (!Layer.bBlendingOutEventSent)
				{
					Layer.bBlendingOutEventSent = true;
					Layer.bNaturalCompletion = true;
					AgentActor->OnNNAnimationLayerBlendingOut.Broadcast(Animation);
				}
				const float BlendOutWeight = Layer.BlendOutSeconds <= UE_SMALL_NUMBER
					? 0.0f
					: SmoothUnitAlpha(RemainingPlaybackSeconds / Layer.BlendOutSeconds);
				BlendWeight = FMath::Min(BlendWeight, BlendOutWeight);
			}
			bCompletesThisStep = Layer.PlaybackTimeSeconds >= PlayLength;
		}
		Layer.BlendWeight = FMath::Clamp(BlendWeight, 0.0f, 1.0f);

		if (Layer.BlendWeight > UE_SMALL_NUMBER)
		{
			USkeletalMeshComponent* PoseMesh = AgentActor->GetPoseReferenceMesh();
			USkeletalMesh* SkeletalMesh = PoseMesh ? PoseMesh->GetSkeletalMeshAsset() : nullptr;
			TArrayView<FTransform> AnimationTransforms = TransformSlice(
				Impl->AnimationTransformBuffer,
				AgentIndex);
			if (!SampleAnimationComponentPose(
				*Impl,
				SkeletalMesh,
				Animation,
				Layer.PlaybackTimeSeconds,
				Layer.bLoop,
				AnimationTransforms))
			{
				UE_LOG(
					LogProphecyNNLocomotion,
					Warning,
					TEXT("Animation layer stopped: %s is not compatible with agent %d's skeleton."),
					*GetNameSafe(Animation),
					AgentIndex);
				AgentActor->ActiveNNAnimationLayerAsset = nullptr;
				Layer.Reset();
				AgentActor->OnNNAnimationLayerInterrupted.Broadcast(Animation);
				continue;
			}

			float* TargetLower = StateSlice(Impl->AnimationLowerStateBuffer, AgentIndex);
			float* TargetUpper = UpperStateSlice(Impl->AnimationUpperStateBuffer, AgentIndex);
			EncodeComponentPoseToNNStates(
				*Impl,
				Agent,
				AnimationTransforms,
				TargetLower,
				TargetUpper);

			float* PublishedLower = StateSlice(Impl->PublishedStateBuffer, AgentIndex);
			float* PublishedUpper = UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex);
			auto IsSelected = [&Layer](int32 BodyIndex)
			{
				return (Layer.BoneMask & (uint32(1) << uint32(BodyIndex))) != 0;
			};
			if (IsSelected(0))
			{
				BlendStateVector(PublishedLower, TargetLower, 0, Layer.BlendWeight);
				BlendStateRotation(PublishedLower, TargetLower, 3, Layer.BlendWeight);
			}
			const int32 PositionOffsets[2] = { 9, 25 };
			const int32 RotationOffsets[2] = { 12, 28 };
			const int32 StartRotationOffsets[2] = { 18, 34 };
			const int32 ToeOffsets[2] = { 24, 40 };
			for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
			{
				const FImpl::FLimb& Limb = Agent.bUseWalkPolicy
					? Impl->WalkLimbs[LimbIndex]
					: Impl->Limbs[LimbIndex];
				if (IsSelected(Limb.Start))
				{
					BlendStateRotation(
						PublishedLower,
						TargetLower,
						StartRotationOffsets[LimbIndex],
						Layer.BlendWeight);
				}
				if (IsSelected(Limb.End))
				{
					BlendStateVector(
						PublishedLower,
						TargetLower,
						PositionOffsets[LimbIndex],
						Layer.BlendWeight);
					BlendStateRotation(
						PublishedLower,
						TargetLower,
						RotationOffsets[LimbIndex],
						Layer.BlendWeight);
				}
				if (IsSelected(Limb.Toe))
				{
					PublishedLower[ToeOffsets[LimbIndex]] = FMath::Lerp(
						PublishedLower[ToeOffsets[LimbIndex]],
						TargetLower[ToeOffsets[LimbIndex]],
						Layer.BlendWeight);
				}
			}
			CleanState(PublishedLower, *Impl);

			for (int32 CoreIndex = 0; CoreIndex < Impl->UpperCoreBoneNames.Num(); ++CoreIndex)
			{
				const int32 BodyIndex = Impl->BodyNames.IndexOfByKey(
					Impl->UpperCoreBoneNames[CoreIndex]);
				if (IsSelected(BodyIndex))
				{
					BlendStateRotation(
						PublishedUpper,
						TargetUpper,
						CoreIndex * 6,
						Layer.BlendWeight);
				}
			}
			for (int32 ArmIndex = 0; ArmIndex < 2; ++ArmIndex)
			{
				const FImpl::FUpperArm& Arm = Impl->UpperArms[ArmIndex];
				const int32 Offset = 60 + ArmIndex * 15;
				if (IsSelected(Arm.End))
				{
					BlendStateVector(PublishedUpper, TargetUpper, Offset, Layer.BlendWeight);
					BlendStateRotation(
						PublishedUpper,
						TargetUpper,
						Offset + 3,
						Layer.BlendWeight);
				}
				if (IsSelected(Arm.Start))
				{
					BlendStateRotation(
						PublishedUpper,
						TargetUpper,
						Offset + 9,
						Layer.BlendWeight);
				}
			}
			CleanUpperState(PublishedUpper);
		}

		// The manager's current lower state is expressed in the next root frame.
		// Rebuild it from the exact blended publication so the next inference sees
		// the same pose that rendering and Physical magnetization consumed.
		float* CurrentLower = StateSlice(Impl->CurStateBuffer, AgentIndex);
		FMemory::Memcpy(
			CurrentLower,
			StateSlice(Impl->PublishedStateBuffer, AgentIndex),
			StateDim * sizeof(float));
		const float* Future = Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120;
		const auto* WindowSmoothing = ProphecyNNRootWindow::Find(AgentActors[AgentIndex]);
		const FVector3f NextRootDelta = WindowSmoothing ? WindowSmoothing->ActualNextRootLocal : FVector3f(
			Future[0] * Impl->MaxSpeedScaleFinal,
			0.0f,
			Future[1] * Impl->MaxSpeedScaleFinal);
		if (!bNNFrozen)
		{
			RebaseStateRoot(
				CurrentLower,
				*Impl,
				NextRootDelta,
				WindowSmoothing ? WindowSmoothing->ActualNextYaw : FMath::Atan2(Future[3], Future[2]));
		}
		FMemory::Memcpy(
			UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex),
			UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex),
			UpperStateDim * sizeof(float));
		BuildUpperBaseFromLower(
			CurrentLower,
			*Impl,
			UpperStateSlice(Impl->UpperCurrentBaseBuffer, AgentIndex));
		LowerTransformToHeading(
			CurrentLower,
			0,
			3,
			*Impl,
			TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex));

		if (bCompletesThisStep)
		{
			const bool bNaturalCompletion = Layer.bNaturalCompletion || !Layer.bStopping;
			Layer.BlendWeight = 0.0f;
			AgentActor->ActiveNNAnimationLayerAsset = nullptr;
			Layer.Reset();
			if (bNaturalCompletion)
			{
				AgentActor->OnNNAnimationLayerFinished.Broadcast(Animation);
			}
			else
			{
				AgentActor->OnNNAnimationLayerInterrupted.Broadcast(Animation);
			}
		}
	}
}

namespace
{
	struct FLocomotionClamps
	{
		bool bClampFoot = false, bClampCalf = false, bClampHand = false;
		bool bClampForearm = false;
		float ForearmLeeway = 0;
		float FootClampLengthMultiplier = 1, CalfClampLengthMultiplier = 1, HandClampLengthMultiplier = 1;
		float FootLeeway = 0, CalfLeeway = 0, HandLeeway = 0; // native metres
	};
	void DecodeLocomotionPose(const AProphecyNNLocomotionManager::FImpl* Impl,
		const float* PoseState, const float* UpperState, float WalkWeightForFallback,
		TArrayView<FTransform> OutComponentTransforms, TArrayView<FTransform>* OutLocalTransforms,
		const FLocomotionClamps& C,const FVector2f* LegWalkWeights=nullptr)
	{
		using FImpl = AProphecyNNLocomotionManager::FImpl;
	int32 CoreSlots[FullBodyBoneCount];
	for (int32& Slot : CoreSlots) Slot = INDEX_NONE;
	for (int32 CoreIndex = 0; CoreIndex < Impl->UpperCoreBoneNames.Num(); ++CoreIndex)
	{
		CoreSlots[Impl->BodyNames.IndexOfByKey(Impl->UpperCoreBoneNames[CoreIndex])] = CoreIndex;
	}
		FVector3f Positions[FullBodyBoneCount]{};
		FMat3f Rotations[FullBodyBoneCount];
		bool bFilled[FullBodyBoneCount]{};
		Positions[0] = ReadStateVec3(PoseState, 0);
		Rotations[0] = MatrixFromRot6(PoseState + 3);
		bFilled[0] = true;

		for (int32 BodyIndex = 1; BodyIndex < FullBodyBoneCount; ++BodyIndex)
		{
			if (bFilled[BodyIndex]) continue;
			const int32 ParentIndex = Impl->Parents[BodyIndex];
			if (CoreSlots[BodyIndex] != INDEX_NONE)
			{
				Positions[BodyIndex] = Positions[ParentIndex] +
					TransformRow(Impl->UpperLocalOffsets[BodyIndex], Rotations[ParentIndex]);
				Rotations[BodyIndex] = Multiply(
					MatrixFromRot6(UpperState + CoreSlots[BodyIndex] * 6),
					Rotations[ParentIndex]);
				bFilled[BodyIndex] = true;
				continue;
			}

			int32 ArmIndex = INDEX_NONE;
			for (int32 Candidate = 0; Candidate < 2; ++Candidate)
			{
				if (Impl->UpperArms[Candidate].Start == BodyIndex) ArmIndex = Candidate;
			}
			if (ArmIndex != INDEX_NONE)
			{
				const FImpl::FUpperArm& Arm = Impl->UpperArms[ArmIndex];
				const int32 UpperOffset = 60 + ArmIndex * 15;
				const FMat3f HeadingToRoot = Transpose(Impl->SeedRootRot);
				Positions[Arm.Start] = Positions[ParentIndex] +
					TransformRow(Impl->UpperLocalOffsets[Arm.Start], Rotations[ParentIndex]);
				Rotations[Arm.Start] = Multiply(
					MatrixFromRot6(UpperState + UpperOffset + 9), HeadingToRoot);
				Positions[Arm.Mid] = Positions[Arm.Start] +
					TransformRow(Impl->UpperLocalOffsets[Arm.Mid], Rotations[Arm.Start]);
				FVector3f End = TransformRow(
					ReadStateVec3(UpperState, UpperOffset), HeadingToRoot);
				FVector3f LowerAxis = End - Positions[Arm.Mid];
				const float Distance = LowerAxis.Size();
				const float HandLengthMultiplier = FMath::IsFinite(C.HandClampLengthMultiplier)
					? FMath::Max(0.0f, C.HandClampLengthMultiplier) : 1.0f;
				const float Maximum = FMath::Max(1.0e-5f, Arm.Lengths.Y * HandLengthMultiplier + C.HandLeeway);
				if (C.bClampForearm && Distance > 1.e-8f)
				{
					const float Allowed = float(FProphecyNNForearmClamp::ClampLength(Distance, Arm.Lengths.Y, C.ForearmLeeway));
					if (Allowed != Distance)
					{
						End = Positions[Arm.Mid] + LowerAxis * (Allowed / Distance);
						LowerAxis = End - Positions[Arm.Mid];
					}
				}
				else if (!C.bClampForearm && C.bClampHand && Distance > Maximum)
				{
					End = Positions[Arm.Mid] + LowerAxis * (Maximum / Distance);
					LowerAxis = End - Positions[Arm.Mid];
				}
				if (LowerAxis.SizeSquared() <= 1.0e-16f)
				{
					LowerAxis = TransformRow(Impl->UpperLocalOffsets[Arm.End], Rotations[Arm.Start]);
					End = Positions[Arm.Mid] + LowerAxis;
				}
				Positions[Arm.End] = End;
				Rotations[Arm.End] = Multiply(
					MatrixFromRot6(UpperState + UpperOffset + 3), HeadingToRoot);
				Rotations[Arm.Mid] = ForearmRotationFromHand(
					Impl->UpperLocalOffsets[Arm.End], LowerAxis,
					Arm.LocalPoleAxes[1], Rotations[Arm.End]);
				bFilled[Arm.Start] = bFilled[Arm.Mid] = bFilled[Arm.End] = true;
				continue;
			}

			int32 LimbIndex = INDEX_NONE;
			for (int32 Candidate = 0; Candidate < 2; ++Candidate)
			{
				if (Impl->Limbs[Candidate].Start == BodyIndex) LimbIndex = Candidate;
			}
			if (LimbIndex != INDEX_NONE)
			{
				const float WalkWeight=LegWalkWeights ? (*LegWalkWeights)[LimbIndex] : WalkWeightForFallback;
				FImpl::FLimb MixedLimb;
				const FImpl::FLimb* SelectedLimb = WalkWeight >= 1.f ? &Impl->WalkLimbs[LimbIndex] : &Impl->Limbs[LimbIndex];
				if (WalkWeight > 0.f && WalkWeight < 1.f)
				{
					MixedLimb = Impl->Limbs[LimbIndex];
					const auto& WalkLimb = Impl->WalkLimbs[LimbIndex];
					for (int32 Axis = 0; Axis < 2; ++Axis)
						MixedLimb.LocalPoleAxes[Axis] = SafeNormal(FMath::Lerp(MixedLimb.LocalPoleAxes[Axis], WalkLimb.LocalPoleAxes[Axis], WalkWeight));
					MixedLimb.ToeOffset = FMath::Lerp(MixedLimb.ToeOffset, WalkLimb.ToeOffset, WalkWeight);
					MixedLimb.ToeAxis = SafeNormal(FMath::Lerp(MixedLimb.ToeAxis, WalkLimb.ToeAxis, WalkWeight));
					SelectedLimb = &MixedLimb;
				}
				const FImpl::FLimb& Limb = *SelectedLimb;
				const int32 PositionOffset = LimbIndex == 0 ? 9 : 25;
				const int32 RotationOffset = LimbIndex == 0 ? 12 : 28;
				const int32 StartRotationOffset = LimbIndex == 0 ? 18 : 34;
				const int32 ToeOffset = LimbIndex == 0 ? 24 : 40;
				Positions[Limb.Start] = Positions[0] +
					TransformRow(Impl->LocalOffsets[Limb.Start], Rotations[0]);
				Rotations[Limb.Start] = MatrixFromRot6(PoseState + StartRotationOffset);
				Positions[Limb.Mid] = Positions[Limb.Start] +
					TransformRow(Impl->LocalOffsets[Limb.Mid], Rotations[Limb.Start]);
				FVector3f End = ReadStateVec3(PoseState, PositionOffset);
				if (C.bClampFoot)
				{
					const float MaxLength =
						(Impl->LocalOffsets[Limb.Mid].Size() + Impl->LocalOffsets[Limb.End].Size()) *
						FMath::Max(0.0f, C.FootClampLengthMultiplier) + C.FootLeeway;
					const FVector3f Delta = End - Positions[Limb.Start];
					if (MaxLength > 0.0f && Delta.SizeSquared() > FMath::Square(MaxLength))
					{
						End = Positions[Limb.Start] + Delta * (MaxLength / Delta.Size());
					}
				}
				if (C.bClampCalf)
				{
					const float Length = Impl->LocalOffsets[Limb.End].Size() *
						FMath::Max(0.0f, C.CalfClampLengthMultiplier);
					const FVector3f Delta = End - Positions[Limb.Mid];
					if (Length > 0.0f && Delta.SizeSquared() > UE_SMALL_NUMBER)
					{
						const float Distance = Delta.Size();
						const float Allowed = FMath::Clamp(Distance, FMath::Max(0.f, Length - C.CalfLeeway), Length + C.CalfLeeway);
						End = Positions[Limb.Mid] + Delta * (Allowed / Distance);
					}
				}
				Positions[Limb.End] = End;
				Rotations[Limb.Mid] = CalfRotationFromHinge(
					Impl->LocalOffsets[Limb.Mid], Impl->LocalOffsets[Limb.End],
					Limb.LocalPoleAxes[0], Limb.LocalPoleAxes[1],
					Rotations[Limb.Start], End - Positions[Limb.Mid]);
				Rotations[Limb.End] = MatrixFromRot6(PoseState + RotationOffset);
				Positions[Limb.Toe] = End + TransformRow(Limb.ToeOffset, Rotations[Limb.End]);
				Rotations[Limb.Toe] = Multiply(
					AxisAngleMatrix(
						Limb.ToeAxis,
						FMath::Clamp(PoseState[ToeOffset], -1.0f, 1.0f) * ToeAlphaRadians),
					Rotations[Limb.End]);
				bFilled[Limb.Start] = bFilled[Limb.Mid] =
					bFilled[Limb.End] = bFilled[Limb.Toe] = true;
			}
		}

		for (int32 BodyIndex = 0; BodyIndex < FullBodyBoneCount; ++BodyIndex)
		{
			OutComponentTransforms[BodyIndex] = FTransform(
				MatrixToQuat(MirrorYBasis(Rotations[BodyIndex])),
				LocalTrainingToUnreal(Positions[BodyIndex]),
				FVector::OneVector);
			if (OutLocalTransforms)
			{
				const int32 ParentIndex = Impl->Parents[BodyIndex];
				(*OutLocalTransforms)[BodyIndex] = ParentIndex == INDEX_NONE
					? OutComponentTransforms[BodyIndex]
					: OutComponentTransforms[BodyIndex].GetRelativeTransform(
						OutComponentTransforms[ParentIndex]);
				(*OutLocalTransforms)[BodyIndex].NormalizeRotation();
			}
		}
	}
}

#include "ProphecyHandInertiaRuntime.inl"

void AProphecyNNLocomotionManager::PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds)
{
	ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerPosePublish);
	const bool bHasPreviousPose=Impl->Agents[AgentIndex].PublishedPoseTimeSeconds>0.;
	const bool bNewPoseTime=SourceTimeSeconds>Impl->Agents[AgentIndex].PublishedPoseTimeSeconds;
	Impl->Agents[AgentIndex].PublishedPoseTimeSeconds = SourceTimeSeconds;
	const float* State = StateSlice(Impl->PublishedStateBuffer, AgentIndex);
	const float* PreviousState = StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex);
	TArrayView<FTransform> LocalTransforms = TransformSlice(Impl->LocalTransformBuffer, AgentIndex);
	TArrayView<FTransform> PreviousComponentTransforms = TransformSlice(Impl->PreviousComponentTransformBuffer, AgentIndex);
	TArrayView<FTransform> ComponentTransforms = TransformSlice(Impl->ComponentTransformBuffer, AgentIndex);
	const AProphecyAgent* Controls = AgentActors[AgentIndex];
	const bool bKickFootExtension=ProphecyKickFootLeeway::Current(Controls)>0;
	FLocomotionClamps C;
	C.bClampFoot = Controls->bOverrideLocomotionFootClamp ? Controls->bLocomotionFootClamp : bClampFoot;
	C.FootClampLengthMultiplier = Controls->bOverrideLocomotionFootClamp ? 1.f : FootClampLengthMultiplier;
	C.FootLeeway = Controls->bOverrideLocomotionFootClamp ? Controls->LocomotionFootClampLeewayCm / 100.f : 0.f;
	C.bClampCalf = Controls->bOverrideLocomotionCalfClamp ? Controls->bLocomotionCalfClamp : bClampCalf;
	C.CalfClampLengthMultiplier = Controls->bOverrideLocomotionCalfClamp ? 1.f : CalfClampLengthMultiplier;
	C.CalfLeeway = Controls->bOverrideLocomotionCalfClamp ? Controls->LocomotionCalfClampLeewayCm / 100.f : 0.f;
	C.bClampHand = Controls->bOverrideLocomotionHandClamp ? Controls->bLocomotionHandClamp : bClampHand;
	C.HandClampLengthMultiplier = Controls->bOverrideLocomotionHandClamp ? 1.f : HandClampLengthMultiplier;
	C.HandLeeway = Controls->bOverrideLocomotionHandClamp ? Controls->LocomotionHandClampLeewayCm / 100.f : 0.f;
	C.bClampForearm = Controls->bLocomotionForearmClamp;
	C.ForearmLeeway = Controls->LocomotionForearmClampLeewayCm / 100.f;
	auto BuildFullPoseTransforms = [&](const float* Lower, const float* Upper, float WalkWeight,const FVector2f& LegWeights,
		TArrayView<FTransform> Out, TArrayView<FTransform>* Local)
	{
		FLocomotionClamps DecodeClamps=C;
		// Preserve the candidate foot until the shared calf-axis clamp below.
		// Early mode-specific hard clamps would discard its allowed extension.
		if (bKickFootExtension) DecodeClamps.bClampFoot=DecodeClamps.bClampCalf=false;
		DecodeLocomotionPose(Impl, Lower, Upper, WalkWeight, Out, Local, DecodeClamps,&LegWeights);
	};
	FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
	const bool bDefensePose=Agent.DefensePose && Agent.DefensePose->bHasPose;
	const auto* CalfTempering=!Agent.DefensePose && !Agent.Slash.bActive
		? ProphecyLowerTempering::Find(Controls) : nullptr;
	const auto* RightCalfTempering=CalfTempering ? &ProphecyLowerTempering::RightFootSettings(Controls,*CalfTempering) : nullptr;
    bool bTemperCalves=bHasPreviousPose && CalfTempering && (CalfTempering->FeetRotation<1.f || RightCalfTempering->FeetRotation<1.f) && ProphecyLegChainDebug::IsEnabled(Controls);
#if WITH_EDITOR
	if (bTemperCalves) bTemperCalves=CVarTemperingCalfContinuity.GetValueOnGameThread()!=0;
#endif
	FQuat PreviousCalfRotations[2];
	if (bTemperCalves) for (int32 I=0;I<2;++I)
	{
		// Keep the real preceding publication. Decoding its reduced NN state
		// again discards calf twist, which that state does not store. Repeated
		// publication of one policy sample must not advance the filter again.
		PreviousCalfRotations[I]=(bNewPoseTime ? ComponentTransforms : PreviousComponentTransforms)[Impl->Limbs[I].Mid].GetRotation();
	}
	const auto* DefenseClamps=bDefensePose?ProphecyDefenseControls::Find(Controls,Agent.DefensePose->bDodge):nullptr;
	const auto* HandTempering=!Agent.DefensePose && !Agent.Slash.bActive ? ProphecyHandRecovery::Tempering(Controls) : nullptr;
	const auto* HandRecovery=!Agent.DefensePose && !Agent.Slash.bActive ? ProphecyHandRecovery::Frame(Controls) : nullptr;
	const bool bTemperArms=bHasPreviousPose && (HandTempering || HandRecovery);
	FQuat PreviousForearmRotations[2];
	const int32 HandSpine=bTemperArms && HandTempering ? Impl->BodyNames.IndexOfByKey(FName(TEXT("spine_05"))) : INDEX_NONE;
	const FQuat PreviousHandSpine=HandSpine!=INDEX_NONE
		? (bNewPoseTime?ComponentTransforms:PreviousComponentTransforms)[HandSpine].GetRotation() : FQuat::Identity;
	if (bTemperArms) for(int32 I=0;I<2;++I)
		PreviousForearmRotations[I]=(bNewPoseTime?ComponentTransforms:PreviousComponentTransforms)[Impl->UpperArms[I].Mid].GetRotation();
	FProphecyNNAttackHandClamp PresentationHandClamp=bDefensePose?FProphecyNNAttackHandClamp():Agent.Slash.HandClamp;
	if (DefenseClamps && DefenseClamps->Hand.bOverride)
	{
		PresentationHandClamp.bEnabled=DefenseClamps->Hand.bEnabled;
		PresentationHandClamp.LeewayCm=DefenseClamps->Hand.LeewayCm;
	}
	if (bDefensePose)
	{
		for (int32 Bone=0;Bone<FullBodyBoneCount;++Bone)
		{
			PreviousComponentTransforms[Bone]=Agent.DefensePose->PreviousComponent[Bone];
			ComponentTransforms[Bone]=Agent.DefensePose->CurrentComponent[Bone];
		}
		if (DefenseClamps)
		{
			const auto& D=*DefenseClamps;
			const auto* Mesh=Controls->GetPoseReferenceMesh();
			const auto* Asset=Mesh?Mesh->GetSkeletalMeshAsset():nullptr;
			const bool Foot=!bKickFootExtension && D.Foot.bOverride && D.Foot.bEnabled, Calf=!bKickFootExtension && D.Calf.bOverride && D.Calf.bEnabled;
			const bool Hand=D.Hand.bOverride && D.Hand.bEnabled, Forearm=D.Forearm.bOverride && D.Forearm.bEnabled;
			if (Asset && (Foot || Calf || Hand || Forearm))
			{
				const auto& Skeleton=Asset->GetRefSkeleton();
				for (auto Pose:{PreviousComponentTransforms,ComponentTransforms})
				{
					if (Foot || Calf) for (const auto& Leg:Impl->Limbs)
					{
						const int32 F=Skeleton.FindBoneIndex(Impl->BodyNames[Leg.End]), K=Skeleton.FindBoneIndex(Impl->BodyNames[Leg.Mid]);
						if (F!=INDEX_NONE && K!=INDEX_NONE)
							ProphecyNNLegClamps::Apply(Pose[Leg.Start].GetTranslation(),Pose[Leg.Mid],Pose[Leg.End],Pose[Leg.Toe],
								Skeleton.GetRefBonePose()[F].GetTranslation(),Skeleton.GetRefBonePose()[K].GetTranslation().Length(),
								Foot,1.f,Calf,1.f,D.Foot.LeewayCm,D.Calf.LeewayCm);
					}
					if (Hand || Forearm) for (const auto& Arm:Impl->UpperArms)
					{
						const int32 H=Skeleton.FindBoneIndex(Impl->BodyNames[Arm.End]);if (H==INDEX_NONE) continue;
						const FVector Offset=Skeleton.GetRefBonePose()[H].GetTranslation();
						PresentationHandClamp.ReferenceOffsets[Impl->BodyNames[Arm.End]==TEXT("hand_l")?0:1]=Offset;
						if (Forearm)
						{
							const auto Delta=Pose[Arm.End].GetTranslation()-Pose[Arm.Mid].GetTranslation();
							const double Length=Pose[Arm.Mid].TransformVector(Offset).Length();
							const double Allowed=FProphecyNNForearmClamp::ClampLength(Delta.Length(),Length,D.Forearm.LeewayCm);
							Pose[Arm.End].SetTranslation(Pose[Arm.Mid].GetTranslation()+Delta.GetSafeNormal(UE_SMALL_NUMBER,Pose[Arm.Mid].TransformVector(Offset).GetSafeNormal())*Allowed);
						}
						else Pose[Arm.End].SetTranslation(FProphecyNNAttackHandClamp::ClampPosition(Pose[Arm.End].GetTranslation(),Pose[Arm.Mid].TransformPosition(Offset),D.Hand.LeewayCm));
					}
				}
			}
		}
	}
	else
	{
	BuildFullPoseTransforms(
		PreviousState,
		UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer, AgentIndex),
		Agent.PreviousPublishedWalkWeight,Agent.PreviousPublishedLegWalkWeights,
		PreviousComponentTransforms,
		nullptr);
	BuildFullPoseTransforms(
		State,
		UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex),
		Agent.PublishedWalkWeight,Agent.PublishedLegWalkWeights,
		ComponentTransforms,
		&LocalTransforms);
	}
	ApplySlashPose(AgentIndex, PreviousComponentTransforms, ComponentTransforms);
	if (bTemperCalves) for (int32 I=0;I<2;++I)
	{
        const float Follow=(I==0 ? CalfTempering : RightCalfTempering)->FeetRotation;
        if (Follow==1.f) continue;
		const auto& Leg=Impl->Limbs[I];
		PreviousComponentTransforms[Leg.Mid].SetRotation(PreviousCalfRotations[I]);
		ComponentTransforms[Leg.Mid].SetRotation(TemperCalfRotation(PreviousCalfRotations[I],
			ComponentTransforms[Leg.Mid].GetRotation(),LocalTrainingToUnreal(Impl->LocalOffsets[Leg.End]),Follow));
	}
	if (bTemperArms) for(int32 I=0;I<2;++I)
	{
		const float Follow=HandChainFollow(HandTempering,HandRecovery,I,true);
		if (Follow>=1.f) continue;
		const auto& Arm=Impl->UpperArms[I];
		PreviousComponentTransforms[Arm.Mid].SetRotation(PreviousForearmRotations[I]);
		const FQuat Carried=HandSpine!=INDEX_NONE && !HandTempering->Hand[I].Normal()
			? (ComponentTransforms[HandSpine].GetRotation()*PreviousHandSpine.Inverse()*PreviousForearmRotations[I]).GetNormalized()
			: PreviousForearmRotations[I];
		ComponentTransforms[Arm.Mid].SetRotation(ProphecyHandChain::FollowTwist(Carried,
			ComponentTransforms[Arm.Mid].GetRotation(),LocalTrainingToUnreal(Impl->UpperLocalOffsets[Arm.End]),Follow));
	}
	if (bTemperCalves || bTemperArms || bDefensePose || (Agent.Slash.bActive && Agent.Slash.bHasPose))
	{
		for (int32 Bone = 0; Bone < FullBodyBoneCount; ++Bone)
		{
			const int32 Parent = Impl->Parents[Bone];
			LocalTransforms[Bone] = Parent == INDEX_NONE ? ComponentTransforms[Bone]
				: ComponentTransforms[Bone].GetRelativeTransform(ComponentTransforms[Parent]);
		}
	}

	auto BuildComponentWorldTransform = [&](const FVector3f& Root, float Yaw)
	{
		FTransform Result = FTransform::Identity;
		if (AgentActors.IsValidIndex(AgentIndex) && IsValid(AgentActors[AgentIndex]))
		{
			const AProphecyAgent* AgentActor = AgentActors[AgentIndex];
			const UCapsuleComponent* Capsule = AgentActor->GetAgentCapsule();
			const USkeletalMeshComponent* Mesh = AgentActor->GetAgentMesh();
			if (Capsule && Mesh)
			{
				const FVector CapsuleCenter = TrainingToUnreal(Root) +
					FVector::UpVector * Capsule->GetScaledCapsuleHalfHeight();
				const FTransform CapsuleWorld(
					FRotator(0.0f, -FMath::RadiansToDegrees(Yaw), 0.0f),
					CapsuleCenter,
					FVector::OneVector);
				// A manual agent may begin PIE with PhysicalMesh already simulating.
				// Its live component transform then belongs to Chaos, while the empty
				// inherited Mesh still retains the authored mesh-to-capsule offset.
				const FTransform AuthoredMeshRelative = AgentActor->bManualNNPoseApplication
					? Mesh->GetRelativeTransform()
					: AgentActor->GetAuthoredMeshRelativeTransform();
				Result = AuthoredMeshRelative * CapsuleWorld;
			}
		}
		Result.NormalizeRotation();
		return Result;
	};
	const FTransform PreviousComponentWorldTransform = BuildComponentWorldTransform(
		Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
	const FTransform ComponentWorldTransform = BuildComponentWorldTransform(
		Agent.PublishedRoot, Agent.PublishedYaw);
	if (!Agent.Slash.bActive && !bDefensePose && ProphecyUpperBodyInertia::Active(Controls))
		ProphecyUpperBodyInertia::PreserveHandoff(Controls,Impl->Parents,Impl->BodyNames,Impl->UpperCoreBoneNames,
			PreviousComponentWorldTransform,PreviousComponentTransforms);
	const AProphecyAgent* ClampActor = AgentActors[AgentIndex];
	const bool bFullAttack = Agent.Slash.bActive && Agent.Slash.bHasPose && !Agent.Slash.bHalf;
	const bool bCalfOverride = bFullAttack && ClampActor->bOverrideAttackCalfClamp;
	FProphecyNNForearmClamp ForearmClamp;
	ForearmClamp.bEnabled = !bDefensePose && C.bClampForearm && !(Agent.Slash.bActive && Agent.Slash.bHasPose);
	ForearmClamp.LeewayCm = Controls->LocomotionForearmClampLeewayCm;
	ForearmClamp.LengthsCm = FVector2D(Impl->UpperArms[0].Lengths.Y * 100.f, Impl->UpperArms[1].Lengths.Y * 100.f);
	if (DefenseClamps && DefenseClamps->Forearm.bOverride)
	{
		ForearmClamp.bEnabled=DefenseClamps->Forearm.bEnabled;
		ForearmClamp.LeewayCm=DefenseClamps->Forearm.LeewayCm;
	}
	FProphecyNNPoseStore::SetAgentLocalPose(
		PoseStoreAgentBase + AgentIndex,
		Impl->PublishedBoneNames,
		LocalTransforms,
		PreviousComponentTransforms,
		ComponentTransforms,
		PreviousComponentWorldTransform,
		ComponentWorldTransform,
		SourceTimeSeconds,
		bDefensePose || (Agent.Slash.bActive && Agent.Slash.bHasPose),
		bDefensePose ? (DefenseClamps && DefenseClamps->Calf.bOverride && DefenseClamps->Calf.bEnabled) : (bCalfOverride ? ClampActor->bAttackCalfClamp : (bFullAttack ? bClampCalf && CalfClampLengthMultiplier > 0.f : C.bClampCalf && C.CalfClampLengthMultiplier > 0.f)),
		bDefensePose ? (DefenseClamps?DefenseClamps->Calf.LeewayCm:0.f) : bCalfOverride ? ClampActor->AttackCalfClampLeewayCm : (bFullAttack ? 0.f : C.CalfLeeway * 100.f),
		bFullAttack ? Agent.Slash.CalfClampLengths : FVector2D(
			Impl->LocalOffsets[Impl->Limbs[0].End].Size() * 100.f * (bDefensePose?1.f:C.CalfClampLengthMultiplier),
			Impl->LocalOffsets[Impl->Limbs[1].End].Size() * 100.f * (bDefensePose?1.f:C.CalfClampLengthMultiplier)),
		PresentationHandClamp, ForearmClamp);
    if(auto* T=ProphecyWalkPinning::FindTickPinning(Controls))
    {
        if(!Agent.Slash.bActive && !Agent.DefensePose && T->Current.Valid && ProphecyWalkPinning::FindSmoothing(Controls))
        {
            T->PoseId=PoseStoreAgentBase+AgentIndex;T->HasBase=true;T->Dirty=true;
            for(int32 I=0;I<2;++I)
            {
                const auto& L=Impl->Limbs[I];const int32 B[]={L.Start,L.Mid,L.End,L.Toe};
                for(int32 J=0;J<4;++J){const int32 K=I*4+J;T->Bones[K]=B[J];T->BasePrevious[K]=PreviousComponentTransforms[B[J]];T->BaseCurrent[K]=ComponentTransforms[B[J]];}
            }
        }
    }
}
#include "ProphecyWalkTickPinningRuntime.inl"

void AProphecyNNLocomotionManager::UpdateVisualRoots()
{
	ProphecyJolt::CharacterProfiling::FScope Timing(ProphecyJolt::CharacterProfiling::EPhase::ManagerVisualRoots);
	if (!bSpawnVisuals) return;
	for (int32 AgentIndex = 0; AgentIndex < AgentActors.Num(); ++AgentIndex)
	{
		if (!AgentActors[AgentIndex]) continue;
		const float Alpha = ProphecyAgentTime::Alpha(this,AgentIndex,Impl->VisualPoseAlpha);
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		ProphecyNNPresentation::Publish(PoseStoreAgentBase + AgentIndex, Agent.PublishedPoseTimeSeconds, Alpha);
		const FVector3f Root = FMath::Lerp(Agent.PreviousPublishedRoot, Agent.PublishedRoot, Alpha);
		const float Yaw = Agent.PreviousPublishedYaw + WrapAngle(Agent.PublishedYaw - Agent.PreviousPublishedYaw) * Alpha;
		const FVector3f PreviousAppliedRoot = UnrealToTraining(AgentActors[AgentIndex]->GetRootLowPoint());
		const float PreviousAppliedYaw = -FMath::DegreesToRadians(float(AgentActors[AgentIndex]->GetActorRotation().Yaw));
		FVector AppliedLowPoint;
		FVector BlockingNormal;
		bool bWorldStaticBlocked = false;
		if (AgentActors[AgentIndex]->SetManagedRootLowPoint(
			TrainingToUnreal(Root), -FMath::RadiansToDegrees(Yaw), AppliedLowPoint,
			BlockingNormal, bWorldStaticBlocked))
		{
			Agent.bPhysicalWorldBlockedPending |= bWorldStaticBlocked;
			const FVector3f AppliedRoot = UnrealToTraining(AppliedLowPoint);
			const float AppliedYaw = -FMath::DegreesToRadians(float(AgentActors[AgentIndex]->GetActorRotation().Yaw));
			if (!Agent.bHasAppliedVisualRoot)
			{
				// Initial placement changes only the world-space origin of an already
				// root-local seed pose. Rebasing the recurrent state here treated the
				// spawn from (0,0,0) as a collision correction and corrupted frame one.
				const FVector3f InitialTranslation = AppliedRoot - Root;
				Agent.PrevRootPos += InitialTranslation;
				Agent.CurRootPos += InitialTranslation;
				Agent.PreviousPublishedRoot = AppliedRoot;
				Agent.PublishedRoot = AppliedRoot;
				Agent.MoverState.position = { Agent.CurRootPos.X, Agent.CurRootPos.Z };
				Agent.MoverState.previous_yaw_radians = Yaw;
				Agent.MoverState.yaw_radians = Yaw;
				Agent.PrevRootYaw = Yaw;
				Agent.CurRootYaw = Yaw;
				Agent.PreviousPublishedYaw = Yaw;
				Agent.PublishedYaw = Yaw;
				Agent.bHasAppliedVisualRoot = true;
				continue;
			}
			const FVector3f AppliedRootError = AppliedRoot - Root;
			const float AppliedYawError = WrapAngle(AppliedYaw - Yaw);
			if (AppliedRootError.SizeSquared() <= 1.0e-8f && FMath::Abs(AppliedYawError) <= 1.0e-5f)
			{
				continue;
			}
			// The policy transition is authored in the current root frame. Preserve
			// the same world-space pose when the capsule resolves somewhere other
			// than the unobstructed mover prediction; changing root numbers alone
			// makes a blocked agent's feet treadmill through the recurrent state.
			// Defense now shares the live mover. Preserve its private recurrence
			// through collision rebasing rather than cancelling the response.
			if (Agent.DefensePose) RebaseDefenseAfterRootCollision(AgentIndex,PreviousAppliedRoot,PreviousAppliedYaw,AppliedRoot,Yaw);
			const FVector3f PreviousStateRootDelta = TransformRow(
				PreviousAppliedRoot - Agent.PrevRootPos,
				YawMatrix(Agent.PrevRootYaw));
			const FVector3f CurrentStateRootDelta = TransformRow(
				AppliedRoot - Agent.CurRootPos,
				YawMatrix(Agent.CurRootYaw));
			const FVector3f PublishedStateRootDelta = TransformRow(
				AppliedRoot - Agent.PublishedRoot,
				YawMatrix(Agent.PublishedYaw));
			const FVector3f PreviousPublishedStateRootDelta = TransformRow(
				AppliedRoot - Agent.PreviousPublishedRoot,
				YawMatrix(Agent.PreviousPublishedYaw));
			RebaseStateRoot(
				StateSlice(Impl->PrevStateBuffer, AgentIndex),
				*Impl,
				PreviousStateRootDelta,
				WrapAngle(PreviousAppliedYaw - Agent.PrevRootYaw));
			RebaseStateRoot(
				StateSlice(Impl->CurStateBuffer, AgentIndex),
				*Impl,
				CurrentStateRootDelta,
				WrapAngle(Yaw - Agent.CurRootYaw));
			RebaseStateRoot(
				StateSlice(Impl->PublishedStateBuffer, AgentIndex),
				*Impl,
				PublishedStateRootDelta,
				WrapAngle(Yaw - Agent.PublishedYaw));
			RebaseStateRoot(
				StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),
				*Impl,
				PreviousPublishedStateRootDelta,
				WrapAngle(Yaw - Agent.PreviousPublishedYaw));
			RebaseUpperHeadingState(
				UpperStateSlice(Impl->UpperPreviousStateBuffer, AgentIndex),
				PreviousStateRootDelta,
				WrapAngle(PreviousAppliedYaw - Agent.PrevRootYaw));
			RebaseUpperHeadingState(
				UpperStateSlice(Impl->UpperCurrentStateBuffer, AgentIndex),
				CurrentStateRootDelta,
				WrapAngle(Yaw - Agent.CurRootYaw));
			RebaseUpperHeadingState(
				UpperStateSlice(Impl->UpperPublishedStateBuffer, AgentIndex),
				PublishedStateRootDelta,
				WrapAngle(Yaw - Agent.PublishedYaw));
			RebaseUpperHeadingState(
				UpperStateSlice(Impl->UpperPreviousPublishedStateBuffer, AgentIndex),
				PreviousPublishedStateRootDelta,
				WrapAngle(Yaw - Agent.PreviousPublishedYaw));
			BuildUpperBaseFromLower(
				StateSlice(Impl->CurStateBuffer, AgentIndex),
				*Impl,
				UpperStateSlice(Impl->UpperCurrentBaseBuffer, AgentIndex));
			LowerTransformToHeading(
				StateSlice(Impl->PrevStateBuffer, AgentIndex), 0, 3, *Impl,
				TransformStateSlice(Impl->PreviousPelvisHeadingBuffer, AgentIndex));
			LowerTransformToHeading(
				StateSlice(Impl->CurStateBuffer, AgentIndex), 0, 3, *Impl,
				TransformStateSlice(Impl->CurrentPelvisHeadingBuffer, AgentIndex));
			Agent.MoverState.position = { AppliedRoot.X, AppliedRoot.Z };
			Agent.MoverState.previous_yaw_radians = PreviousAppliedYaw;
			Agent.MoverState.yaw_radians = Yaw;
			Agent.PrevRootPos = PreviousAppliedRoot;
			Agent.CurRootPos = AppliedRoot;
			Agent.PrevRootYaw = PreviousAppliedYaw;
			Agent.CurRootYaw = Yaw;
			Agent.PreviousPublishedRoot = AppliedRoot;
			Agent.PublishedRoot = AppliedRoot;
			Agent.PreviousPublishedYaw = Yaw;
			Agent.PublishedYaw = Yaw;
			const FVector2D Normal2D(BlockingNormal.X, BlockingNormal.Y);
			const double IntoSurface = Agent.MoverState.velocity.x * Normal2D.X +
				Agent.MoverState.velocity.z * Normal2D.Y;
			if (IntoSurface < 0.0)
			{
				Agent.MoverState.velocity.x -= IntoSurface * Normal2D.X;
				Agent.MoverState.velocity.z -= IntoSurface * Normal2D.Y;
			}
			// Collision rebasing changes coordinates, not the published NN interval.
			PublishAgentPose(AgentIndex, Agent.PublishedPoseTimeSeconds);
		}
		ProphecyAttackStartInertia::Update(AgentActors[AgentIndex],PoseStoreAgentBase+AgentIndex);
	}
}

void AProphecyNNLocomotionManager::DrawFutureRootDebug() const
{
	if (!GetWorld() || !Impl->Agents.IsValidIndex(FutureRootDebugAgentIndex))
	{
		return;
	}

	const FImpl::FAgent& Agent = Impl->Agents[FutureRootDebugAgentIndex];
	if (!Agent.bHasFedFutureRoots)
	{
		return;
	}

	constexpr float FloorLiftCm = 2.0f;
	constexpr float RootRadiusCm = 5.0f;
	constexpr float FutureRadiusCm = 3.0f;
	constexpr float FacingLengthCm = 18.0f;
	constexpr float LineThickness = 1.5f;
	const FVector FloorLift(0.0f, 0.0f, FloorLiftCm);
	const FVector InputRoot = TrainingToUnreal(Agent.FedInputRoot) + FloorLift;
	const FVector InputFacing(FMath::Sin(Agent.FedInputYaw), FMath::Cos(Agent.FedInputYaw), 0.0f);
	DrawDebugSphere(GetWorld(), InputRoot, RootRadiusCm, 12, FColor::White,
		false, -1.0f, 0, LineThickness);
	DrawDebugDirectionalArrow(GetWorld(), InputRoot, InputRoot + InputFacing * FacingLengthCm,
		5.0f, FColor::White, false, -1.0f, 0, LineThickness);

	FVector Previous = InputRoot;
	for (int32 FutureIndex = 0; FutureIndex < FutureWindow; ++FutureIndex)
	{
		const float Fraction = float(FutureIndex) / float(FutureWindow - 1);
		const FColor RootColor(
			uint8(FMath::RoundToInt(FMath::Lerp(0.0f, 255.0f, Fraction))),
			uint8(FMath::RoundToInt(FMath::Lerp(255.0f, 80.0f, Fraction))),
			255);
		const FVector Root = TrainingToUnreal(Agent.FedFutureRootPositions[FutureIndex]) + FloorLift;
		const float Yaw = Agent.FedFutureRootYaws[FutureIndex];
		const FVector Facing(FMath::Sin(Yaw), FMath::Cos(Yaw), 0.0f);

		DrawDebugLine(GetWorld(), Previous, Root, RootColor,
			false, -1.0f, 0, LineThickness);
		DrawDebugSphere(GetWorld(), Root, FutureRadiusCm, 10, RootColor,
			false, -1.0f, 0, LineThickness);
		DrawDebugDirectionalArrow(GetWorld(), Root, Root + Facing * FacingLengthCm,
			5.0f, FColor::Yellow, false, -1.0f, 0, LineThickness);
		Previous = Root;
	}
}

void AProphecyNNLocomotionManager::InitializeSimpleTestPlayerView()
{
	if (!Impl->bSimpleLocomotionTest || AgentActors.IsEmpty() || !IsValid(AgentActors[0]) || !GetWorld()) return;
	// Unpossessed placed agents must not take over the player's camera.
	if (Impl->bSimpleUsesPlacedAgent && !IsValid(PlayerAgent)) return;

	Impl->SimpleTestPlayerController = GetWorld()->GetFirstPlayerController();
	if (APlayerController* PlayerController = Impl->SimpleTestPlayerController.Get())
	{
		PlayerController->SetViewTarget(AgentActors[0]);
	}
}

void AProphecyNNLocomotionManager::CaptureAbsoluteMotionAuditFrame()
{
	if (!Impl->bAbsoluteMotionAuditCanCapture || Impl->bAbsoluteMotionAuditWritten ||
		AgentActors.IsEmpty() || !IsValid(AgentActors[0]))
	{
		return;
	}

	const AProphecyAgent* AgentActor = AgentActors[0];
	const USkeletalMeshComponent* Mesh = AgentActor->GetPoseReferenceMesh();
	if (!Mesh || !Mesh->IsRegistered())
	{
		return;
	}

	const FVector Root = AgentActor->GetRootLowPoint();
	const double GameTime = GetWorld() ? double(GetWorld()->GetTimeSeconds()) : 0.0;
	Impl->AbsoluteMotionCsv += FString::Printf(
		TEXT("%.9g,%.17g,%.9g,%.9g,%.9g"),
		double(Impl->AbsoluteMotionLastRenderedPhase),
		GameTime,
		Root.X, Root.Y, Root.Z);
	for (const FName BoneName : Impl->PublishedBoneNames)
	{
		const FVector Position = Mesh->GetSocketTransform(BoneName, RTS_World).GetLocation();
		Impl->AbsoluteMotionCsv += FString::Printf(
			TEXT(",%.9g,%.9g,%.9g"),
			Position.X, Position.Y, Position.Z);
	}
	Impl->AbsoluteMotionCsv += LINE_TERMINATOR;
	++Impl->AbsoluteMotionSampleCount;

	if (Impl->AbsoluteMotionLastRenderedPhase < 75.0f)
	{
		return;
	}

	const FString OutputDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("ProphecyNN"));
	IFileManager::Get().MakeDirectory(*OutputDirectory, true);
	const FString OutputPath = FPaths::Combine(OutputDirectory, TEXT("absolute_motion_trace.csv"));
	const bool bSaved = FFileHelper::SaveStringToFile(
		Impl->AbsoluteMotionCsv,
		*OutputPath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	Impl->bAbsoluteMotionAuditWritten = true;
	UE_LOG(LogProphecyNNLocomotion, Display,
		TEXT("NN_ABSOLUTE_MOTION_TRACE saved=%d samples=%d path=%s"),
		bSaved ? 1 : 0,
		Impl->AbsoluteMotionSampleCount,
		*OutputPath);

	if (Impl->bAbsoluteMotionAuditExit && GetWorld() && GetWorld()->WorldType == EWorldType::Game)
	{
		FPlatformMisc::RequestExit(false);
	}
}

void AProphecyNNLocomotionManager::UpdateAbsoluteMotionAuditPhase()
{
	if (Impl->bAbsoluteMotionAuditWritten)
	{
		return;
	}
	const float Alpha = Impl->VisualPoseAlpha;
	Impl->AbsoluteMotionLastRenderedPhase = FMath::Max(
		1.0f,
		float(Impl->AbsoluteMotionReferenceFrame - 1) + Alpha);
	Impl->bAbsoluteMotionAuditCanCapture = true;
}

void AProphecyNNLocomotionManager::UpdateOverlaySettings()
{
	if (Impl->bLastOverlayEnabled == bOverlayEnabled && Impl->LastOverlayAnimation.Get() == OverlayAnimation &&
		FMath::IsNearlyEqual(Impl->LastOverlayBlendSeconds, OverlayBlendSeconds) && FMath::IsNearlyEqual(Impl->LastOverlayPlayRate, OverlayPlayRate)) return;
	for (USkeletalMeshComponent* Component : MeshComponents)
	{
		if (UProphecyNNLocomotionAnimInstance* Anim = Component ? Cast<UProphecyNNLocomotionAnimInstance>(Component->GetAnimInstance()) : nullptr)
		{
			Anim->OverlayAnimation = OverlayAnimation;
			Anim->bOverlayEnabled = bOverlayEnabled;
			Anim->OverlayBlendSeconds = OverlayBlendSeconds;
			Anim->OverlayPlayRate = OverlayPlayRate;
		}
	}
	Impl->bLastOverlayEnabled = bOverlayEnabled;
	Impl->LastOverlayAnimation = OverlayAnimation;
	Impl->LastOverlayBlendSeconds = OverlayBlendSeconds;
	Impl->LastOverlayPlayRate = OverlayPlayRate;
}

void AProphecyNNLocomotionManager::LogBenchmark(float DeltaSeconds)
{
	Impl->Stats.Elapsed += DeltaSeconds;
	if (!Impl->Stats.bCollecting && Impl->Stats.Elapsed >= BenchmarkWarmupSeconds)
	{
		Impl->Stats.bCollecting = true;
		Impl->Stats.WallStartSeconds = FPlatformTime::Seconds();
		return;
	}
	if (Impl->Stats.bCollecting)
	{
		Impl->Stats.WarmedSeconds += DeltaSeconds;
		++Impl->Stats.Frames;
	}
	if (!Impl->Stats.bLogged && BenchmarkSeconds > 0.0f && Impl->Stats.WarmedSeconds >= BenchmarkSeconds)
	{
		Impl->Stats.bLogged = true;
		const double WallSeconds = FMath::Max(1.0e-9, FPlatformTime::Seconds() - Impl->Stats.WallStartSeconds);
		const double FPS = Impl->Stats.WarmedSeconds > 0.0 ? double(Impl->Stats.Frames) / Impl->Stats.WarmedSeconds : 0.0;
		const double WallMillisecondsPerFrame = WallSeconds * 1000.0 / FMath::Max<int64>(1, Impl->Stats.Frames);
		const double StepDivisor = FMath::Max<int64>(1, Impl->Stats.NNSteps);
		UE_LOG(LogProphecyNNLocomotion, Display,
			TEXT("NN_LOCOMOTION_BENCHMARK crowd=%d physical=%d macd=%d drive=%s foot_roll_steps=%d overlay=%d sim_fps=%.2f wall_ms=%.4f run_runtime=%s walk_runtime=%s upper_runtime=%s build_ms=%.4f inference_ms=%.4f output_ms=%.4f store_ms=%.4f steps=%lld"),
			CrowdSize, InitialPhysicalAgentCount, bInitialPhysicalAgentsUseMACD ? InitialPhysicalAgentCount : 0,
			InitialPhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque ? TEXT("torque") : TEXT("world"),
			Impl->FootRollSteps, bOverlayEnabled ? 1 : 0, FPS, WallMillisecondsPerFrame,
			*Impl->Model.RuntimeUsed, *Impl->WalkModel.RuntimeUsed, *Impl->UpperModel.RuntimeUsed,
			Impl->Stats.BuildSeconds * 1000.0 / StepDivisor,
			Impl->Stats.InferenceSeconds * 1000.0 / StepDivisor,
			Impl->Stats.OutputSeconds * 1000.0 / StepDivisor,
			Impl->Stats.StoreSeconds * 1000.0 / StepDivisor,
			Impl->Stats.NNSteps);
	}
}

bool AProphecyNNLocomotionManager::StartSimBridge()
{
	StopSimBridge();
	if (!bSimBridge) return false;
	if (!IsValid(PlayerAgent))
	{
		UE_LOG(LogProphecyNNLocomotion, Error,
			TEXT("Sim Bridge is enabled, but Player Agent is not assigned on %s."), *GetName());
		return false;
	}

	const FString ExecutablePath = FPaths::ConvertRelativePathToFull(FPaths::Combine(
		FPaths::ProjectDir(), TEXT("StandaloneSim/build/viewer_raylib/Release/prophecy_viewer.exe")));
	if (!FPaths::FileExists(ExecutablePath))
	{
		UE_LOG(LogProphecyNNLocomotion, Error,
			TEXT("Sim Bridge executable is missing: %s"), *ExecutablePath);
		return false;
	}

	const FString MappingName = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensInBraces);
	const uint32 Access = FPlatformMemory::ESharedMemoryAccess::Read |
		FPlatformMemory::ESharedMemoryAccess::Write;
	Impl->BridgeRegion = FPlatformMemory::MapNamedSharedMemoryRegion(
		MappingName, true, Access, sizeof(prophecy::bridge::SharedState));
	if (!Impl->BridgeRegion)
	{
		UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Could not create the Sim Bridge shared memory."));
		return false;
	}

	Impl->BridgeState = static_cast<prophecy::bridge::SharedState*>(Impl->BridgeRegion->GetAddress());
	FMemory::Memzero(Impl->BridgeState, sizeof(prophecy::bridge::SharedState));
	Impl->BridgeState->magic = prophecy::bridge::kMagic;
	Impl->BridgeState->version = prophecy::bridge::kVersion;
	Impl->BridgeState->byte_size = sizeof(prophecy::bridge::SharedState);
	Impl->BridgeState->villager_count = uint32(CrowdSize);
	Impl->BridgeState->total_agent_count = uint32(CrowdSize + 1);
	WriteBridgeActorState(*PlayerAgent, Impl->BridgeState->initial_player);
	Impl->BridgeFrame.SetNumUninitialized(CrowdSize);
	Impl->LastSimSequence = 0;
	Impl->bReceivedBridgeFrame = false;
	Impl->bBridgeFailureLogged = false;

	const FString Arguments = FString::Printf(
		TEXT("--navigation-crowd-test --paired --no-telemetry --unreal-bridge \"%s\""),
		*MappingName);
	const FString WorkingDirectory = FPaths::GetPath(ExecutablePath);
	uint32 ProcessId = 0;
	Impl->BridgeProcess = FPlatformProcess::CreateProc(
		*ExecutablePath, *Arguments, true, false, false, &ProcessId, 0,
		*WorkingDirectory, nullptr, nullptr);
	if (!Impl->BridgeProcess.IsValid())
	{
		UE_LOG(LogProphecyNNLocomotion, Error,
			TEXT("Could not launch the standalone simulation for Sim Bridge."));
		StopSimBridge();
		return false;
	}

	UE_LOG(LogProphecyNNLocomotion, Display,
		TEXT("Sim Bridge launched process %u for %d villagers plus player %s."),
		ProcessId, CrowdSize, *GetNameSafe(PlayerAgent));
	return true;
}

void AProphecyNNLocomotionManager::StopSimBridge()
{
	if (Impl->BridgeState)
	{
		FPlatformAtomics::InterlockedExchange(&Impl->BridgeState->shutdown_requested, 1);
		FPlatformMisc::MemoryBarrier();
	}
	if (Impl->BridgeProcess.IsValid())
	{
		FPlatformProcess::CloseProc(Impl->BridgeProcess);
		Impl->BridgeProcess.Reset();
	}
	Impl->BridgeState = nullptr;
	if (Impl->BridgeRegion)
	{
		FPlatformMemory::UnmapNamedSharedMemoryRegion(Impl->BridgeRegion);
		Impl->BridgeRegion = nullptr;
	}
	Impl->BridgeFrame.Reset();
	Impl->LastSimSequence = 0;
	Impl->bReceivedBridgeFrame = false;
}

bool AProphecyNNLocomotionManager::ConsumeSimBridgeFrame()
{
	if (!IsSimBridgeActive()) return false;
	if (!FPlatformProcess::IsProcRunning(Impl->BridgeProcess))
	{
		if (!Impl->bBridgeFailureLogged)
		{
			const FString Error = UTF8_TO_TCHAR(Impl->BridgeState->error_message);
			UE_LOG(LogProphecyNNLocomotion, Error,
				TEXT("Sim Bridge process stopped%s%s."),
				Error.IsEmpty() ? TEXT("") : TEXT(": "), *Error);
			Impl->bBridgeFailureLogged = true;
		}
		StopSimBridge();
		return false;
	}

	const int32 FirstSequence = FPlatformAtomics::InterlockedCompareExchange(
		&Impl->BridgeState->sim_sequence, 0, 0);
	if (FirstSequence <= 0 || (FirstSequence & 1) != 0 || FirstSequence == Impl->LastSimSequence)
	{
		return false;
	}
	FMemory::Memcpy(Impl->BridgeFrame.GetData(), Impl->BridgeState->sim_agents,
		CrowdSize * sizeof(prophecy::bridge::AgentState));
	FPlatformMisc::MemoryBarrier();
	const int32 SecondSequence = FPlatformAtomics::InterlockedCompareExchange(
		&Impl->BridgeState->sim_sequence, 0, 0);
	if (FirstSequence != SecondSequence || (SecondSequence & 1) != 0)
	{
		return false;
	}

	const bool bFirstFrame = !Impl->bReceivedBridgeFrame;
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		const prophecy::bridge::AgentState& State = Impl->BridgeFrame[AgentIndex];
		if (State.active == 0U) continue;
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		const bool bBlueprintInput = AgentActors.IsValidIndex(AgentIndex) && AgentActors[AgentIndex] &&
			AgentActors[AgentIndex]->bUseBlueprintLocomotionInput;
		if (!bBlueprintInput)
		{
			// In particular, zero Blueprint facing means keep its prior target;
			// a bridge packet must not replace that target between policy steps.
			Agent.MoverIntent.mode = State.locomotion_mode == 1U
				? prophecy::sim::LocomotionMode::Run
				: State.locomotion_mode == 2U
					? prophecy::sim::LocomotionMode::Crawl
					: prophecy::sim::LocomotionMode::Walk;
			Agent.MoverIntent.speed_direction_radians = State.speed_direction_radians;
			Agent.MoverIntent.speed_amplitude = FMath::Clamp(double(State.speed_amplitude), 0.0, 1.0);
			Agent.MoverIntent.orientation_yaw_radians = State.orientation_yaw_radians;
			Agent.MoverIntent.speed_scale = FMath::Clamp(double(State.speed_scale), 0.0, 1.0);
			Agent.MoverIntent.turn_scale = FMath::Clamp(double(State.turn_scale), 0.0, 1.0);
		}
		Agent.bHasBridgeIntent = true;
		if (bFirstFrame)
		{
			Agent.bUseWalkPolicy = Agent.MoverIntent.mode != prophecy::sim::LocomotionMode::Run;
			Agent.PolicyBlend.Reset(Agent.bUseWalkPolicy);
			Agent.PublishedWalkWeight = Agent.PreviousPublishedWalkWeight = Agent.PolicyBlend.WalkWeight;
		Agent.RecoveryWeights=ProphecyAttackRecovery::FWeights(Agent.PolicyBlend.WalkWeight);
		Agent.PublishedLegWalkWeights=Agent.PreviousPublishedLegWalkWeights=Agent.RecoveryWeights.Legs();
			const TArray<TArray<float>>& SeedStates = Agent.bUseWalkPolicy
				? Impl->WalkSeedPhaseStates
				: Impl->SeedPhaseStates;
			const int32 CurPhase = 1 + (AgentIndex * 7) % (SeedStates.Num() - 1);
			const int32 PrevPhase = FMath::Max(0, CurPhase - 1);
			FMemory::Memcpy(StateSlice(Impl->PrevStateBuffer, AgentIndex), SeedStates[PrevPhase].GetData(), StateDim * sizeof(float));
			FMemory::Memcpy(StateSlice(Impl->CurStateBuffer, AgentIndex), SeedStates[CurPhase].GetData(), StateDim * sizeof(float));
			FMemory::Memcpy(StateSlice(Impl->PublishedStateBuffer, AgentIndex), SeedStates[CurPhase].GetData(), StateDim * sizeof(float));
			const FVector3f SpawnRoot = BridgeToTraining(State.position);
			Agent.MoverState = {};
			Agent.MoverState.position = { SpawnRoot.X, SpawnRoot.Z };
			Agent.MoverState.previous_yaw_radians = State.facing_radians;
			Agent.MoverState.yaw_radians = State.facing_radians;
			Agent.PrevRootPos = SpawnRoot;
			Agent.CurRootPos = SpawnRoot;
			Agent.PrevRootYaw = State.facing_radians;
			Agent.CurRootYaw = State.facing_radians;
			Agent.PreviousPublishedRoot = SpawnRoot;
			Agent.PublishedRoot = SpawnRoot;
			Agent.PreviousPublishedYaw = State.facing_radians;
			Agent.PublishedYaw = State.facing_radians;
		}
	}
	if (bFirstFrame)
	{
		for (int32 AgentIndex = 0; AgentIndex < AgentActors.Num(); ++AgentIndex)
		{
			AProphecyAgent* AgentActor = AgentActors[AgentIndex];
			if (!IsValid(AgentActor)) continue;
			const FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
			AgentActor->TeleportManagedRootLowPoint(
				TrainingToUnreal(Agent.CurRootPos),
				-FMath::RadiansToDegrees(Agent.CurRootYaw));
			AgentActor->SetActorHiddenInGame(false);
		}
	}
	Impl->LastSimSequence = SecondSequence;
	Impl->bReceivedBridgeFrame = true;
	return true;
}

void AProphecyNNLocomotionManager::PublishUnrealBridgeFrame()
{
	if (!IsSimBridgeActive() || !IsValid(PlayerAgent)) return;
	const double PublishSeconds = FPlatformTime::Seconds();
	FPlatformAtomics::InterlockedIncrement(&Impl->BridgeState->unreal_sequence);
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		prophecy::bridge::AgentState& State = Impl->BridgeState->unreal_agents[AgentIndex];
		if (AgentActors.IsValidIndex(AgentIndex) && IsValid(AgentActors[AgentIndex]))
		{
			WriteBridgeActorState(*AgentActors[AgentIndex], State);
			FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
			const FVector3f ActualRoot(State.position[0], State.position[1], State.position[2]);
			const double PublishDelta = PublishSeconds - Agent.LastBridgePublishSeconds;
			if (Agent.bHasBridgeActualRoot && PublishDelta > 1.0e-6)
			{
				const FVector3f ActualVelocity =
					(ActualRoot - Agent.LastBridgeActualRoot) / float(PublishDelta);
				State.velocity[0] = ActualVelocity.X;
				State.velocity[1] = ActualVelocity.Y;
				State.velocity[2] = ActualVelocity.Z;
			}
			Agent.LastBridgeActualRoot = ActualRoot;
			Agent.LastBridgePublishSeconds = PublishSeconds;
			Agent.bHasBridgeActualRoot = true;
			State.facing_radians = float(Agent.MoverState.yaw_radians);
			State.physical_world_blocked = Agent.bPhysicalWorldBlockedPending ? 1U : 0U;
			Agent.bPhysicalWorldBlockedPending = false;
		}
		else
		{
			State = {};
		}
	}
	WriteBridgeActorState(*PlayerAgent, Impl->BridgeState->unreal_agents[CrowdSize]);
	FPlatformMisc::MemoryBarrier();
	FPlatformAtomics::InterlockedIncrement(&Impl->BridgeState->unreal_sequence);
}

bool AProphecyNNLocomotionManager::IsSimBridgeActive() const
{
	return Impl && Impl->BridgeState && Impl->BridgeRegion && Impl->BridgeProcess.IsValid();
}

void AProphecyNNLocomotionManager::SetUpperBodyOverlayEnabled(bool bEnabled)
{
	bOverlayEnabled = bEnabled;
	UpdateOverlaySettings();
}

void AProphecyNNLocomotionManager::SetUpperBodyOverlayAnimation(UAnimSequenceBase* Animation)
{
	OverlayAnimation = Animation;
	UpdateOverlaySettings();
}

FString AProphecyNNLocomotionManager::GetActiveRuntimeName() const
{
	return Impl ? FString::Printf(TEXT("Run=%s Walk=%s"), *Impl->Model.RuntimeUsed, *Impl->WalkModel.RuntimeUsed) : FString();
}

bool AProphecyNNLocomotionManager::ReadRuntimeBenchmarkStats(FProphecyNNRuntimeBenchmarkStats& OutStats) const
{
	OutStats = {};
	if (!IsInGameThread() || !Impl) return false;
	OutStats.bInitialized = Impl->bInitialized;
	OutStats.bSimBridgeActive = IsSimBridgeActive();
	OutStats.RegisteredAgents = AgentActors.Num();
	OutStats.bUsingGPU = Impl->Model.bGpu || Impl->WalkModel.bGpu || Impl->UpperModel.bGpu;
	OutStats.RunRuntime = Impl->Model.RuntimeUsed;
	OutStats.WalkRuntime = Impl->WalkModel.RuntimeUsed;
	OutStats.UpperRuntime = Impl->UpperModel.RuntimeUsed;
	OutStats.RunBatchSize = Impl->Model.InputBatchSize;
	OutStats.WalkBatchSize = Impl->WalkModel.InputBatchSize;
	OutStats.UpperBatchSize = Impl->UpperModel.InputBatchSize;
	OutStats.FootRollSteps = Impl->FootRollSteps;
	OutStats.CompletedNNSteps = uint64(Impl->Stats.NNSteps);
	OutStats.CompletedPhysicalSamples = Impl->CompletedPhysicalSamples;
	OutStats.FailedPhysicalSamples = Impl->FailedPhysicalSamples;
	OutStats.PhysicalFeedbackExecutionMode = PhysicalFeedbackExecutionMode;
	OutStats.PreparedPhysicalSamples = Impl->PreparedPhysicalSamples;
	OutStats.PreparedPhysicalBatches = Impl->PreparedPhysicalBatches;
	OutStats.BuildSeconds = Impl->Stats.BuildSeconds;
	OutStats.InferenceSeconds = Impl->Stats.InferenceSeconds;
	OutStats.OutputSeconds = Impl->Stats.OutputSeconds;
	OutStats.StoreSeconds = Impl->Stats.StoreSeconds;
	return true;
}

FProphecyAgentHandle AProphecyNNLocomotionManager::GetAgentHandle(int32 AgentIndex) const
{
	if (Impl && AgentIndex == CrowdSize && IsValid(PlayerAgent))
	{
		FProphecyAgentHandle PlayerHandle;
		PlayerHandle.Index = AgentIndex;
		PlayerHandle.Generation = Impl->PlayerGeneration;
		return PlayerHandle;
	}
	if (!Impl || !Impl->Agents.IsValidIndex(AgentIndex) || !AgentActors.IsValidIndex(AgentIndex) || !AgentActors[AgentIndex])
	{
		return FProphecyAgentHandle();
	}

	FProphecyAgentHandle Handle;
	Handle.Index = AgentIndex;
	Handle.Generation = Impl->Agents[AgentIndex].Generation;
	return Handle;
}

AProphecyAgent* AProphecyNNLocomotionManager::ResolveAgent(FProphecyAgentHandle Handle) const
{
	if (Handle.IsValid() && Impl && Handle.Index == CrowdSize &&
		Handle.Generation == Impl->PlayerGeneration)
	{
		return PlayerAgent;
	}
	if (!Handle.IsValid() || !Impl || !Impl->Agents.IsValidIndex(Handle.Index) ||
		!AgentActors.IsValidIndex(Handle.Index) || Impl->Agents[Handle.Index].Generation != Handle.Generation)
	{
		return nullptr;
	}
	return AgentActors[Handle.Index];
}

bool AProphecyNNLocomotionManager::SetAgentSimulationMode(
	FProphecyAgentHandle Handle,
	EProphecyAgentSimulationMode NewMode)
{
	AProphecyAgent* AgentActor = ResolveAgent(Handle);
	if (!AgentActor)
	{
		return false;
	}

	if (Handle.Index == CrowdSize)
	{
		return AgentActor->SetSimulationMode(NewMode);
	}

	FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	if (AgentActor->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic &&
		NewMode == EProphecyAgentSimulationMode::Kinematic)
	{
		ResamplePhysicalAgentState(Handle.Index);
	}

	if (!AgentActor->SetSimulationMode(NewMode))
	{
		return false;
	}

	if (NewMode != EProphecyAgentSimulationMode::Kinematic)
	{
		Agent.bHasPhysicalSample = false;
	}
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentMACDEnabled(FProphecyAgentHandle Handle, bool bEnabled)
{
	AProphecyAgent* AgentActor = ResolveAgent(Handle);
	if (!AgentActor)
	{
		return false;
	}
	AgentActor->SetMACDEnabled(bEnabled);
	return true;
}

bool AProphecyNNLocomotionManager::AddAgentRootVelocityImpulse(FProphecyAgentHandle Handle,
	FVector DeltaVelocity, double DeltaWorldYawRate)
{
	AProphecyAgent* Actor = ResolveAgent(Handle);
	if (!Impl || !Impl->bInitialized || !Actor || !Actor->bNNInferenceEnabled ||
		DeltaVelocity.ContainsNaN() || !FMath::IsFinite(DeltaWorldYawRate)) return false;
	auto& Mover = Impl->Agents[Handle.Index].MoverState;
	auto& Intent = Impl->Agents[Handle.Index].MoverIntent;
	// Training yaw has the opposite sign to world-Z yaw. The helper changes
	// momentum AND its stopping target, without teleporting the present root.
	if (!prophecy::sim::AddRootYawImpulse(Mover, Intent, -DeltaWorldYawRate,
		1.0 / FMath::Max(1.0f, NNUpdateHz))) return false;
	Mover.velocity.x += DeltaVelocity.X / MetersToCentimeters;
	Mover.velocity.z += DeltaVelocity.Y / MetersToCentimeters;
	if (DeltaVelocity.X != 0.0 || DeltaVelocity.Y != 0.0)
	{
		const auto& Agent = Impl->Agents[Handle.Index];
		RootImpulseSmoothingYaw.FindOrAdd(Actor) = Agent.FedInputYaw;
		if (auto* Smoothing = ProphecyNNRootWindow::Find(Actor))
		{
			// Impulse changes velocity immediately. Do not blend its direction with
			// pre-impact walking/balance history; retain the user's radius smoothing.
			const double Direction = FMath::Atan2(Mover.velocity.z, Mover.velocity.x) + Agent.FedInputYaw;
			for (auto& Sample : Smoothing->Samples) Sample.Direction = Direction;
		}
	}
	if (FMath::Abs(DeltaWorldYawRate) > 0.0)
	{
		RootYawImpulseAgents.Add(Actor);
		ProphecyRootFacing::Impulse(Actor);
		if (Actor->bUseBlueprintLocomotionInput && !Actor->LocomotionInput.FacingWorldDirection.IsNearlyZero())
			Actor->LocomotionInput.FacingWorldDirection = FVector(FMath::Sin(Intent.orientation_yaw_radians),
				FMath::Cos(Intent.orientation_yaw_radians), 0.0);
		if (auto* Targets = ResolvedMoverTargets.Find(this); Targets && Targets->IsValidIndex(Handle.Index))
			(*Targets)[Handle.Index].Target.orientation_yaw_radians = Intent.orientation_yaw_radians;
	}
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentRootVelocity(FProphecyAgentHandle Handle,
	FVector& Linear, FVector& Angular) const
{
	Linear = Angular = FVector::ZeroVector;
	bool bRun;
	FVector Facing;
	if (!GetAgentLocomotionState(Handle, Linear, Facing, bRun)) return false;
	const float Rate=GetAgentTimeDilation(Handle);
	Linear/=Rate; // Combine/cap the mover and magic in agent-local units first.
	const auto& Mover = Impl->Agents[Handle.Index].MoverState;
	Angular.Z = -prophecy::sim::SignedAngleDelta(Mover.previous_yaw_radians, Mover.yaw_radians) *
		FMath::Max(1.0f, NNUpdateHz);
	const auto& Agent = Impl->Agents[Handle.Index];
	if (ResolveAgent(Handle)->bNNInferenceEnabled && !IsSimBridgeActive() && (!Agent.Slash.bActive || Agent.Slash.bHalf))
	{
		const auto* SpeedLimits = ProphecyRootSpeedLimits::Find(ResolveAgent(Handle));
		if (SpeedLimits) Angular.Z = -(Mover.yaw_radians - Mover.previous_yaw_radians) * FMath::Max(1.0f, NNUpdateHz);
		if (const auto* Magic = ProphecyRootMagic::Find(ResolveAgent(Handle)))
		{
			if (SpeedLimits && SpeedLimits->bClamped) Magic = &SpeedLimits->AppliedMagic;
			Linear += TrainingToUnreal(Magic->Linear);
			Angular.Z -= Magic->Yaw;
		}
		if (SpeedLimits)
		{
			Linear = Linear.GetClampedToMaxSize(SpeedLimits->Linear * 100.);
			Angular.Z = FMath::Clamp(Angular.Z, -SpeedLimits->Angular, SpeedLimits->Angular);
		}
	}
	Linear*=Rate;Angular*=Rate;
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentTimeDilation(FProphecyAgentHandle Handle,float Multiplier)
{
	if (!IsInGameThread() || !Impl || !Impl->bInitialized || IsSimBridgeActive() ||
		!FMath::IsFinite(Multiplier) || Multiplier<=0.f ||
		!FMath::IsFinite((1.f/NNUpdateHz)/Multiplier)) return false;
	auto* Actor=ResolveAgent(Handle);
	if (!Actor || Actor->IsActorBeingDestroyed()) return false;
	const auto& Agent=Impl->Agents[Handle.Index];
	if (Multiplier!=1.f && (Agent.Slash.bActive ||
		(Agent.DefensePose && Agent.DefensePose->Status.Active))) return false;
	if (Multiplier==GetAgentTimeDilation(Handle)) return true;
	if (Multiplier==1.f) ProphecyAgentTime::Reset(this,Handle.Index,Impl->VisualPoseAlpha);
	else ProphecyAgentTime::Set(this,Handle.Index,Multiplier,Impl->VisualPoseAlpha);
	// Readers outside the manager normally resolve the published per-agent alpha;
	// keep their fallback interval and animation proxy metadata consistent too.
	int32 PoseId;float Interval;bool Interpolate;
	if (Actor->GetNNPoseDataSource(PoseId,Interval,Interpolate))
	{
		const float NewInterval=(1.f/NNUpdateHz)/Multiplier;
		Actor->ConfigureNNPoseDataSource(PoseId,NewInterval,Interpolate);
		if (auto* Mesh=Actor->GetAgentMesh())
			if (auto* Anim=Cast<UProphecyNNLocomotionAnimInstance>(Mesh->GetAnimInstance()))
				Anim->NNPoseIntervalSeconds=NewInterval;
	}
	return true;
}

float AProphecyNNLocomotionManager::GetAgentTimeDilation(FProphecyAgentHandle Handle) const
{
	return ResolveAgent(Handle)?ProphecyAgentTime::Rate(this,Handle.Index):1.f;
}

bool AProphecyNNLocomotionManager::SetAgentRootVelocity(FProphecyAgentHandle Handle,
	FVector Value, bool bAngular, bool bAddToCurrent)
{
	if (!IsInGameThread() || !Impl || !Impl->bInitialized || IsSimBridgeActive() || Value.ContainsNaN()) return false;
	AProphecyAgent* Actor=ResolveAgent(Handle);
	if (!Actor || !Actor->bNNInferenceEnabled) return false;
	auto& Agent=Impl->Agents[Handle.Index];
	if (Agent.WindowStepSeconds<=0 || (Agent.Slash.bActive && !Agent.Slash.bHalf)) return false;
	auto& Mover=Agent.MoverState;
	if (!bAngular)
	{
		const FVector Current(Mover.velocity.x*100.,Mover.velocity.z*100.,0);
		const FVector Requested=FVector(Value.X,Value.Y,0)+(bAddToCurrent?Current:FVector::ZeroVector);
		if (Requested.ContainsNaN()) return false;
		// Reuse world-momentum smoothing transport; never subtract magic from a
		// combined readback, which would make successive setters fight each other.
		return AddAgentRootVelocityImpulse(Handle,Requested-Current,0.);
	}
	const double Dt=1.0/FMath::Max(1.f,NNUpdateHz);
	if (bAddToCurrent && Value.Z==0.) return true;
	const double CurrentRate=(Mover.yaw_radians-Mover.previous_yaw_radians)/Dt;
	const double Requested=-FMath::DegreesToRadians(Value.Z)+(bAddToCurrent?CurrentRate:0.);
	if (!FMath::IsFinite(Requested)) return false;
	// Recompute the stopping heading even when assigning the existing rate.
	// The impulse helper intentionally bypasses a zero DELTA; a zero SET must
	// instead cancel the old facing goal and stop at today's orientation.
	auto NextMover=Mover;
	auto NextIntent=Agent.MoverIntent;
	NextMover.previous_yaw_radians=NextMover.yaw_radians;
	NextIntent.orientation_yaw_radians=NextMover.yaw_radians;
	if (!prophecy::sim::AddRootYawImpulse(NextMover,NextIntent,Requested,Dt)) return false;
	Mover.previous_yaw_radians=NextMover.previous_yaw_radians;
	Agent.MoverIntent.orientation_yaw_radians=NextIntent.orientation_yaw_radians;
	if (Requested!=0.)
	{
		RootYawImpulseAgents.Add(Actor);
		ProphecyRootFacing::Impulse(Actor);
	}
	else
	{
		RootYawImpulseAgents.Remove(Actor);
		ProphecyRootFacing::Explicit(Actor);
	}
	if (Actor->bUseBlueprintLocomotionInput && !Actor->LocomotionInput.FacingWorldDirection.IsNearlyZero())
		Actor->LocomotionInput.FacingWorldDirection=FVector(FMath::Sin(NextIntent.orientation_yaw_radians),FMath::Cos(NextIntent.orientation_yaw_radians),0);
	if (auto* Targets=ResolvedMoverTargets.Find(this);Targets && Targets->IsValidIndex(Handle.Index))
		(*Targets)[Handle.Index].Target.orientation_yaw_radians=NextIntent.orientation_yaw_radians;
	return true;
}

bool AProphecyNNLocomotionManager::SetHalfAttackTargetRadius(const UWorld* World, float RadiusCm)
{
	if (!World || !FMath::IsFinite(RadiusCm) || RadiusCm <= 0.0f) return false;
	for (auto It = HalfAttackTargetRadii.CreateIterator(); It; ++It)
		if (!It.Key().IsValid()) It.RemoveCurrent();
	HalfAttackTargetRadii.Add(World, RadiusCm);
	return true;
}

float AProphecyNNLocomotionManager::GetHalfAttackTargetRadius(const UWorld* World)
{
	const float* Radius = HalfAttackTargetRadii.Find(World);
	return Radius ? *Radius : 125.0f;
}

bool AProphecyNNLocomotionManager::GetAgentLocomotionCheckpointWeights(FProphecyAgentHandle Handle,
	float& WalkWeight, float& RunWeight,FVector2f* LegWalkWeights) const
{
	WalkWeight = RunWeight = 0.f;
	if (!Impl || !Impl->bInitialized || !ResolveAgent(Handle) ||
		Handle.Index < 0 || Handle.Index >= CrowdSize || !Impl->Agents.IsValidIndex(Handle.Index)) return false;
	WalkWeight = Impl->Agents[Handle.Index].PublishedWalkWeight;
	if (LegWalkWeights) *LegWalkWeights=Impl->Agents[Handle.Index].PublishedLegWalkWeights;
	RunWeight = 1.f - WalkWeight;
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentLocomotionState(FProphecyAgentHandle Handle,
	FVector& WorldVelocityCmPerSecond, FVector& FacingWorldDirection, bool& bRun) const
{
	WorldVelocityCmPerSecond = FVector::ZeroVector;
	FacingWorldDirection = FVector::ZeroVector;
	bRun = false;
	if (!Impl || !Impl->bInitialized || !ResolveAgent(Handle) ||
		Handle.Index < 0 || Handle.Index >= CrowdSize || !Impl->Agents.IsValidIndex(Handle.Index))
	{
		return false;
	}
	const FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	WorldVelocityCmPerSecond = FVector(Agent.MoverState.velocity.x, Agent.MoverState.velocity.z, 0.0) *
		(double(MetersToCentimeters)*GetAgentTimeDilation(Handle));
	FacingWorldDirection = FVector(FMath::Sin(Agent.MoverState.yaw_radians), FMath::Cos(Agent.MoverState.yaw_radians), 0.0);
	bRun = Agent.MoverIntent.mode == prophecy::sim::LocomotionMode::Run;
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentLocomotionTarget(FProphecyAgentHandle Handle,
	FVector& TargetWorldVelocityCmPerSecond, float& TargetSpeedCmPerSecond,
	FVector& TargetFacingWorldDirection, bool& bRun) const
{
	TargetWorldVelocityCmPerSecond = FVector::ZeroVector;
	TargetSpeedCmPerSecond = 0.0f;
	TargetFacingWorldDirection = FVector::ZeroVector;
	bRun = false;
	const TArray<FResolvedMoverTarget>* Targets = ResolvedMoverTargets.Find(this);
	if (!Impl || !Impl->bInitialized || !ResolveAgent(Handle) || Handle.Index < 0 ||
		Handle.Index >= CrowdSize || !Targets || !Targets->IsValidIndex(Handle.Index) ||
		!(*Targets)[Handle.Index].bValid)
	{
		return false;
	}
	const FResolvedMoverTarget& Resolved = (*Targets)[Handle.Index];
	TargetWorldVelocityCmPerSecond = FVector(
		Resolved.Target.velocity.x, Resolved.Target.velocity.z, 0.0) * (double(MetersToCentimeters)*GetAgentTimeDilation(Handle));
	TargetSpeedCmPerSecond = float(TargetWorldVelocityCmPerSecond.Size());
	TargetFacingWorldDirection = FVector(FMath::Sin(Resolved.Target.orientation_yaw_radians),
		FMath::Cos(Resolved.Target.orientation_yaw_radians), 0.0);
	bRun = Resolved.bRun;
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentPhysicalFeedbackTolerance(
	FProphecyAgentHandle Handle,
	FName BoneName,
	float LinearToleranceCm,
	float AngularToleranceDegrees)
{
	if (!Impl || !ResolveAgent(Handle) || Handle.Index < 0 ||
		!Impl->Agents.IsValidIndex(Handle.Index) || BoneName.IsNone() ||
		!ControlledFeedbackBoneNames().Contains(BoneName))
	{
		return false;
	}

	FPhysicalFeedbackTolerance& Tolerance =
		Impl->Agents[Handle.Index].PhysicalFeedbackTolerances.FindOrAdd(BoneName);
	Tolerance.LinearCm = FMath::Max(0.0f, LinearToleranceCm);
	Tolerance.AngularDegrees = FMath::Max(0.0f, AngularToleranceDegrees);
	return true;
}

bool AProphecyNNLocomotionManager::SetAgentAllPhysicalFeedbackTolerances(
	FProphecyAgentHandle Handle,
	float LinearToleranceCm,
	float AngularToleranceDegrees)
{
	if (!Impl || !ResolveAgent(Handle) || Handle.Index < 0 ||
		!Impl->Agents.IsValidIndex(Handle.Index))
	{
		return false;
	}

	const float Linear = FMath::Max(0.0f, LinearToleranceCm);
	const float Angular = FMath::Max(0.0f, AngularToleranceDegrees);
	for (const FName BoneName : ControlledFeedbackBoneNames())
	{
		FPhysicalFeedbackTolerance& Tolerance =
			Impl->Agents[Handle.Index].PhysicalFeedbackTolerances.FindOrAdd(BoneName);
		Tolerance.LinearCm = Linear;
		Tolerance.AngularDegrees = Angular;
	}
	return true;
}

bool AProphecyNNLocomotionManager::PlayAgentAnimationLayer(
	FProphecyAgentHandle Handle,
	UAnimSequenceBase* Animation,
	FName FirstBlendedBone,
	float BlendInSeconds,
	float BlendOutSeconds,
	float PlayRate,
	bool bLoop)
{
	AProphecyAgent* AgentActor = ResolveAgent(Handle);
	if (!Impl || !AgentActor || !Animation || Handle.Index < 0 ||
		!Impl->Agents.IsValidIndex(Handle.Index) || PlayRate <= UE_SMALL_NUMBER ||
		Animation->GetPlayLength() <= UE_SMALL_NUMBER)
	{
		return false;
	}

	USkeletalMeshComponent* PoseMesh = AgentActor->GetPoseReferenceMesh();
	USkeletalMesh* SkeletalMesh = PoseMesh ? PoseMesh->GetSkeletalMeshAsset() : nullptr;
	if (!SkeletalMesh || Animation->GetSkeleton() != SkeletalMesh->GetSkeleton())
	{
		return false;
	}
	const FReferenceSkeleton& ReferenceSkeleton = SkeletalMesh->GetRefSkeleton();
	const int32 FirstBoneIndex = FirstBlendedBone.IsNone()
		? INDEX_NONE
		: ReferenceSkeleton.FindBoneIndex(FirstBlendedBone);
	if (!FirstBlendedBone.IsNone() && FirstBoneIndex == INDEX_NONE)
	{
		return false;
	}

	uint32 BoneMask = 0;
	for (int32 BodyIndex = 0; BodyIndex < FullBodyBoneCount; ++BodyIndex)
	{
		const int32 MeshBoneIndex = ReferenceSkeleton.FindBoneIndex(Impl->BodyNames[BodyIndex]);
		if (MeshBoneIndex != INDEX_NONE &&
			(FirstBoneIndex == INDEX_NONE || MeshBoneIndex == FirstBoneIndex ||
				ReferenceSkeleton.BoneIsChildOf(MeshBoneIndex, FirstBoneIndex)))
		{
			BoneMask |= uint32(1) << uint32(BodyIndex);
		}
	}
	if (BoneMask == 0)
	{
		return false;
	}

	FImpl::FAgent& Agent = Impl->Agents[Handle.Index];
	FImpl::FAgent::FAnimationLayer& Layer = Agent.AnimationLayer;
	if (Agent.DefensePose) StopAgentNNDefense(Handle);
	if (UAnimSequenceBase* InterruptedAnimation = Layer.Animation.Get())
	{
		AgentActor->OnNNAnimationLayerInterrupted.Broadcast(InterruptedAnimation);
	}
	Layer.Reset();
	Layer.Animation = Animation;
	Layer.BoneMask = BoneMask;
	Layer.BlendInSeconds = FMath::Max(0.0f, BlendInSeconds);
	Layer.BlendOutSeconds = FMath::Max(0.0f, BlendOutSeconds);
	Layer.PlayRate = PlayRate;
	Layer.bLoop = bLoop;
	Layer.BlendWeight = Layer.BlendInSeconds <= UE_SMALL_NUMBER ? 1.0f : 0.0f;
	AgentActor->ActiveNNAnimationLayerAsset = Animation;
	FMemory::Memcpy(
		StateSlice(Impl->AnimationFrozenBaseLowerStateBuffer, Handle.Index),
		StateSlice(Impl->PublishedStateBuffer, Handle.Index),
		StateDim * sizeof(float));
	FMemory::Memcpy(
		UpperStateSlice(Impl->AnimationFrozenBaseUpperStateBuffer, Handle.Index),
		UpperStateSlice(Impl->UpperPublishedStateBuffer, Handle.Index),
		UpperStateDim * sizeof(float));
	return true;
}

bool AProphecyNNLocomotionManager::StopAgentAnimationLayer(
	FProphecyAgentHandle Handle,
	float BlendOutSeconds)
{
	AProphecyAgent* AgentActor = ResolveAgent(Handle);
	if (!Impl || !AgentActor || Handle.Index < 0 ||
		!Impl->Agents.IsValidIndex(Handle.Index))
	{
		return false;
	}
	FImpl::FAgent::FAnimationLayer& Layer = Impl->Agents[Handle.Index].AnimationLayer;
	UAnimSequenceBase* Animation = Layer.Animation.Get();
	if (!Animation)
	{
		return false;
	}
	Layer.bStopping = true;
	Layer.bNaturalCompletion = false;
	Layer.StopElapsedSeconds = 0.0f;
	Layer.StopDurationSeconds = FMath::Max(0.0f, BlendOutSeconds);
	Layer.StopStartWeight = Layer.BlendWeight;
	if (!Layer.bBlendingOutEventSent)
	{
		Layer.bBlendingOutEventSent = true;
		AgentActor->OnNNAnimationLayerBlendingOut.Broadcast(Animation);
	}
	return true;
}

bool AProphecyNNLocomotionManager::GetAgentAnimationLayerState(
	FProphecyAgentHandle Handle,
	float& OutPlaybackTimeSeconds,
	float& OutBlendWeight) const
{
	OutPlaybackTimeSeconds = 0.0f;
	OutBlendWeight = 0.0f;
	if (!Impl || !ResolveAgent(Handle) || Handle.Index < 0 ||
		!Impl->Agents.IsValidIndex(Handle.Index))
	{
		return false;
	}
	const FImpl::FAgent::FAnimationLayer& Layer = Impl->Agents[Handle.Index].AnimationLayer;
	if (!Layer.IsActive())
	{
		return false;
	}
	OutPlaybackTimeSeconds = Layer.PlaybackTimeSeconds;
	OutBlendWeight = Layer.BlendWeight;
	return true;
}

bool UProphecyNNLocomotionWorldSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	if (!World || (World->WorldType != EWorldType::Game && World->WorldType != EWorldType::PIE))
	{
		return false;
	}

	const bool bRequested = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNLocomotion"));
	if (!bRequested && !World->GetMapName().Contains(TEXT("locomotion"), ESearchCase::IgnoreCase))
	{
		return false;
	}

	// Opening the locomotion map is normal gameplay. Only an explicitly requested
	// command-line benchmark may override the project's fixed game clock.
	if (!bRequested) return true;
	// World tick-rate selection happens before actor BeginPlay, so uncap the benchmark here.
	if (GEngine)
	{
		GEngine->bSmoothFrameRate = false;
		GEngine->bUseFixedFrameRate = false;
		GEngine->SetMaxFPS(0.0f);
	}
	if (IConsoleVariable* VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync")))
	{
		VSync->Set(0, ECVF_SetByCode);
	}
	if (IConsoleVariable* SyncInterval = IConsoleManager::Get().FindConsoleVariable(TEXT("rhi.SyncInterval")))
	{
		SyncInterval->Set(0, ECVF_SetByCode);
	}
	if (IConsoleVariable* IdleWhenNotForeground = IConsoleManager::Get().FindConsoleVariable(TEXT("t.IdleWhenNotForeground")))
	{
		IdleWhenNotForeground->Set(0, ECVF_SetByCode);
	}
	return true;
}

void UProphecyNNLocomotionWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	const bool bRequested = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNLocomotion"));
	if (!bRequested && !InWorld.GetMapName().Contains(TEXT("locomotion"), ESearchCase::IgnoreCase)) return;
	for (TActorIterator<AProphecyNNLocomotionManager> It(&InWorld); It; ++It)
	{
		Manager = *It;
		return;
	}
	Manager = InWorld.SpawnActorDeferred<AProphecyNNLocomotionManager>(
		AProphecyNNLocomotionManager::StaticClass(),
		FTransform::Identity,
		nullptr,
		nullptr,
		ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (!Manager) return;
	if (InWorld.GetMapName().Contains(TEXT("locomotion"), ESearchCase::IgnoreCase))
	{
		Manager->ConfigureSimpleLocomotionTest();
	}
	Manager->FinishSpawning(FTransform::Identity);
}

#include "ProphecySlashNative.inl"
#include "ProphecyNNSlashRuntime.inl"
#include "ProphecyNNDefenseRuntime.inl"
#include "ProphecyNNDodgeRuntime.inl"

#include "ProphecyNNInputDebug.inl"
#include "ProphecyNNAgentReset.inl"

#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
// External test entry keeps Live Coding validation out of anonymous test vtables.
bool RunCapturedKneeBendReturnChecks(FAutomationTestBase& Test)
{
    CheckCapturedKneePlaneReturn(Test);
    CheckTickPinningHingeReference(Test);
    return !Test.HasAnyErrors();
}
#endif
