#include "ProphecyNNLocomotionManager.h"

#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNPoseTypes.h"

#include "Animation/AnimSequenceBase.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/EngineTypes.h"
#include "Engine/GameViewportClient.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
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
	constexpr int32 InputDim = 152;
	constexpr int32 StateDim = 41;
	constexpr int32 PolicyOutputDim = 43;
	constexpr int32 FutureWindow = 8;
	constexpr int32 PoseStoreAgentBase = 100000;
	constexpr int32 MaxCatchUpStepsPerTick = 32;
	constexpr float MetersToCentimeters = 100.0f;
	constexpr float ToeAlphaRadians = UE_PI * 0.5f;

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

	FMat3f RotationFromAxisAndPole(
		const FVector3f& LocalAxisValue,
		const FVector3f& WorldAxisValue,
		const FVector3f& LocalPoleValue,
		const FVector3f& WorldPoleValue)
	{
		const FVector3f LocalAxis = SafeNormal(LocalAxisValue);
		const FVector3f LocalSide = ProjectToPlane(LocalPoleValue, LocalAxis);
		const FVector3f LocalUp = SafeNormal(FVector3f::CrossProduct(LocalAxis, LocalSide));
		FMat3f LocalBasis;
		LocalBasis.Rows[0] = LocalAxis;
		LocalBasis.Rows[1] = LocalSide;
		LocalBasis.Rows[2] = LocalUp;

		const FVector3f WorldAxis = SafeNormal(WorldAxisValue);
		const FVector3f WorldSide = ProjectToPlane(WorldPoleValue, WorldAxis);
		const FVector3f WorldUp = SafeNormal(FVector3f::CrossProduct(WorldAxis, WorldSide));
		FMat3f WorldBasis;
		WorldBasis.Rows[0] = WorldAxis;
		WorldBasis.Rows[1] = WorldSide;
		WorldBasis.Rows[2] = WorldUp;
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

	private:
		static bool SetShape(UE::NNE::IModelInstanceRunSync* Instance)
		{
			const uint32 ShapeData[] = { uint32(BatchSize), uint32(InputDim) };
			const UE::NNE::FTensorShape Shape = UE::NNE::FTensorShape::Make(MakeArrayView(ShapeData, 2));
			return Instance->SetInputTensorShapes(MakeArrayView(&Shape, 1)) == UE::NNE::EResultStatus::Ok;
		}

		TSharedPtr<UE::NNE::IModelInstanceCPU> CpuInstance;
		TSharedPtr<UE::NNE::IModelInstanceGPU> GpuInstance;
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

	struct FAgent
	{
		FVector3f PrevRootPos = FVector3f::ZeroVector;
		FVector3f CurRootPos = FVector3f::ZeroVector;
		FVector3f PreviousPublishedRoot = FVector3f::ZeroVector;
		FVector3f PublishedRoot = FVector3f::ZeroVector;
		double PublishedPoseTimeSeconds = 0.0;
		float PrevRootYaw = 0.0f;
		float CurRootYaw = 0.0f;
		float PreviousPublishedYaw = 0.0f;
		float PublishedYaw = 0.0f;
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
		bool bHasBridgeIntent = false;
		bool bHasBridgeActualRoot = false;
		bool bPhysicalWorldBlockedPending = false;
		bool bHasAppliedVisualRoot = false;
		bool bUseWalkPolicy = false;
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

	TArray<FName> BodyNames;
	TArray<int32> Parents;
	TArray<FVector3f> LocalOffsets;
	TArray<TArray<float>> SeedPhaseStates;
	TArray<FVector3f> WalkLocalOffsets;
	TArray<TArray<float>> WalkSeedPhaseStates;
	TArray<FName> PublishedBoneNames;
	FLimb Limbs[2];
	FLimb WalkLimbs[2];
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
	TArray<float> PrevStateBuffer;
	TArray<float> CurStateBuffer;
	TArray<float> PreviousPublishedStateBuffer;
	TArray<float> PublishedStateBuffer;
	TArray<float> NextStateBuffer;
	TArray<float> PhysicalStateBuffer;
	TArray<float> PreviousPhysicalStateBuffer;
	TArray<FTransform> LocalTransformBuffer;
	TArray<FTransform> PreviousComponentTransformBuffer;
	TArray<FTransform> ComponentTransformBuffer;
	TArray<FTransform> PhysicalTransformBuffer;
	TArray<float> InputBuffer;
	TArray<float> OutputBuffer;
	TArray<float> WalkOutputBuffer;
	FPolicyModel Model;
	FPolicyModel WalkModel;
	FStats Stats;
	float AccumulatedStepSeconds = 0.0f;
	float VisualPoseAlpha = 0.0f;
	bool bInitialized = false;
	bool bLastOverlayEnabled = false;
	TWeakObjectPtr<UAnimSequenceBase> LastOverlayAnimation;
	TWeakObjectPtr<ACameraActor> SimpleTestCamera;
	TWeakObjectPtr<APlayerController> SimpleTestPlayerController;
	float LastOverlayBlendSeconds = -1.0f;
	float LastOverlayPlayRate = -1.0f;
	float SimpleTestCameraYawDegrees = 0.0f;
	float SimpleTestCameraPitchDegrees = -12.0f;
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

	FFootAxes BuildFootAxes(int32 LimbIndex, const FVector3f& FootPos, const FMat3f& FootRot, float ToeFloat, bool bWalkPolicy = false) const
	{
		const FLimb& Limb = bWalkPolicy ? WalkLimbs[LimbIndex] : Limbs[LimbIndex];
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

	TArrayView<FTransform> TransformSlice(TArray<FTransform>& Buffer, int32 AgentIndex)
	{
		return MakeArrayView(Buffer.GetData() + AgentIndex * 9, 9);
	}

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
	CrowdSize = 1;
	AgentSpeedCmPerSecond = 200.0f;
	InitialPhysicalAgentCount = 0;
}

void AProphecyNNLocomotionManager::BeginPlay()
{
	Super::BeginPlay();
	if (GetWorld() && GetWorld()->GetMapName().Contains(TEXT("locomotion"), ESearchCase::IgnoreCase))
	{
		ConfigureSimpleLocomotionTest();
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
	if (GEngine)
	{
		GEngine->bSmoothFrameRate = false;
		GEngine->bUseFixedFrameRate = Impl->bAbsoluteMotionAudit;
		if (Impl->bAbsoluteMotionAudit)
		{
			GEngine->FixedFrameRate = Impl->AbsoluteMotionRenderHz;
		}
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
	if (Impl->bSimpleLocomotionTest)
	{
		for (TActorIterator<AActor> It(GetWorld()); It; ++It)
		{
			AActor* Actor = *It;
			bool bRouteMarker =
				Actor->GetName().Equals(EndpointAActorName.ToString(), ESearchCase::IgnoreCase) ||
				Actor->GetName().Equals(EndpointBActorName.ToString(), ESearchCase::IgnoreCase);
#if WITH_EDITOR
			bRouteMarker = bRouteMarker ||
				Actor->GetActorLabel().Equals(EndpointAActorName.ToString(), ESearchCase::IgnoreCase) ||
				Actor->GetActorLabel().Equals(EndpointBActorName.ToString(), ESearchCase::IgnoreCase);
#endif
			if (bRouteMarker) Actor->SetActorEnableCollision(false);
		}
	}
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

	InitializeAgents();
	if (bSpawnVisuals) SpawnVisualComponents();
	if (Impl->bSimpleLocomotionTest) InitializeSimpleTestCamera();
	if (IsValid(PlayerAgent))
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
		TEXT("NN locomotion started: crowd=%d rate=%.1fHz run_runtime=%s walk_runtime=%s gpu=%d foot_roll_steps=%d physical_agents=%d physical_macd=%d physical_drive=%s endpoints=(%.0f,%.0f)->(%.0f,%.0f)"),
		CrowdSize, NNUpdateHz, *Impl->Model.RuntimeUsed, *Impl->WalkModel.RuntimeUsed,
		(Impl->Model.bGpu || Impl->WalkModel.bGpu) ? 1 : 0,
		Impl->FootRollSteps, InitialPhysicalAgentCount, bInitialPhysicalAgentsUseMACD ? 1 : 0,
		InitialPhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque ? TEXT("torque") : TEXT("world"),
		EndpointAFallback.X, EndpointAFallback.Y, EndpointBFallback.X, EndpointBFallback.Y);
}

void AProphecyNNLocomotionManager::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	StopSimBridge();
	if (ACameraActor* Camera = Impl->SimpleTestCamera.Get(); IsValid(Camera) && !Camera->IsActorBeingDestroyed())
	{
		Camera->Destroy();
	}
	Impl->SimpleTestCamera.Reset();
	Impl->SimpleTestPlayerController.Reset();
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		FProphecyNNPoseStore::ClearAgentPose(PoseStoreAgentBase + AgentIndex);
	}
	for (AProphecyAgent* AgentActor : AgentActors)
	{
		if (IsValid(AgentActor) && !AgentActor->IsActorBeingDestroyed())
		{
			AgentActor->Destroy();
		}
	}
	AgentActors.Reset();
	MeshComponents.Reset();
	Super::EndPlay(EndPlayReason);
}

void AProphecyNNLocomotionManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!Impl->bInitialized) return;
	if (Impl->bAbsoluteMotionAudit) CaptureAbsoluteMotionAuditFrame();
	if (Impl->bSimpleLocomotionTest) UpdateSimpleTestInput();
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
	Impl->VisualPoseAlpha = DeltaSeconds < StepSeconds
		? FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f)
		: 1.0f;
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
	UpdateVisualRoots();
	if (Impl->bSimpleLocomotionTest) UpdateSimpleTestCamera();
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

	Impl->PublishedBoneNames = { TEXT("pelvis"), TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"), TEXT("ball_l"), TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r") };
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
	Impl->Agents.SetNum(BatchSize);
	Impl->PrevStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->CurStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PreviousPublishedStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PublishedStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->NextStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PhysicalStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->PreviousPhysicalStateBuffer.SetNumUninitialized(BatchSize * StateDim);
	Impl->LocalTransformBuffer.SetNumUninitialized(BatchSize * 9);
	Impl->PreviousComponentTransformBuffer.SetNumUninitialized(BatchSize * 9);
	Impl->ComponentTransformBuffer.SetNumUninitialized(BatchSize * 9);
	Impl->PhysicalTransformBuffer.SetNumUninitialized(BatchSize * 9);
	Impl->InputBuffer.SetNumZeroed(BatchSize * InputDim);
	Impl->OutputBuffer.SetNumZeroed(BatchSize * PolicyOutputDim);
	Impl->WalkOutputBuffer.SetNumZeroed(BatchSize * PolicyOutputDim);
	const float StepSeconds = 1.0f / NNUpdateHz;
	const int32 LaneCount = Impl->bSimpleLocomotionTest ? 1 : 10;
	const int32 Rows = FMath::DivideAndRoundUp(BatchSize, LaneCount);
	const FVector3f RouteDirection = SafeNormal(Impl->EndpointB - Impl->EndpointA, FVector3f(0.0f, 0.0f, 1.0f));
	const FVector3f RouteSide = SafeNormal(FVector3f(RouteDirection.Z, 0.0f, -RouteDirection.X), FVector3f(1.0f, 0.0f, 0.0f));

	for (int32 AgentIndex = 0; AgentIndex < BatchSize; ++AgentIndex)
	{
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		const int32 Lane = AgentIndex % LaneCount;
		const int32 Row = AgentIndex / LaneCount;
		const float LaneOffset = (float(Lane) - float(LaneCount - 1) * 0.5f) * 1.15f;
		const FVector3f Offset = RouteSide * LaneOffset;
		Agent.RouteA = Impl->EndpointA + Offset;
		Agent.RouteB = Impl->EndpointB + Offset;
		const float Phase = Rows > 1 ? float(Row) / float(Rows - 1) : 0.0f;
		Agent.CurRootPos = FMath::Lerp(Agent.RouteA, Agent.RouteB, Phase);
		Agent.TargetIndex = Row % 2 == 0 ? 1 : 0;
		const FVector3f ToTarget = (Agent.TargetIndex == 0 ? Agent.RouteA : Agent.RouteB) - Agent.CurRootPos;
		Agent.CurRootYaw = FMath::Atan2(ToTarget.X, ToTarget.Z);
		const FVector3f Forward(FMath::Sin(Agent.CurRootYaw), 0.0f, FMath::Cos(Agent.CurRootYaw));
		Agent.PrevRootPos = Agent.CurRootPos - Forward * (AgentSpeedCmPerSecond / MetersToCentimeters) * StepSeconds;
		Agent.PrevRootYaw = Agent.CurRootYaw;
		Agent.PublishedRoot = Agent.CurRootPos;
		Agent.PreviousPublishedRoot = Agent.CurRootPos;
		Agent.PublishedYaw = Agent.CurRootYaw;
		Agent.PreviousPublishedYaw = Agent.CurRootYaw;
		Agent.MoverState.position = { Agent.CurRootPos.X, Agent.CurRootPos.Z };
		const prophecy::sim::Vec2 InitialDirection = prophecy::sim::DirectionFromAngle(Agent.CurRootYaw);
		const double InitialSpeed = AgentSpeedCmPerSecond / MetersToCentimeters;
		Agent.MoverState.velocity = { InitialDirection.x * InitialSpeed, InitialDirection.z * InitialSpeed };
		Agent.MoverState.previous_yaw_radians = Agent.CurRootYaw;
		Agent.MoverState.yaw_radians = Agent.CurRootYaw;
		UpdateRouteIntent(Agent, float(InitialSpeed), ArrivalRadiusCm / MetersToCentimeters);

		Agent.bUseWalkPolicy = Agent.MoverIntent.mode != prophecy::sim::LocomotionMode::Run;
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
	}
}

void AProphecyNNLocomotionManager::SpawnVisualComponents()
{
	MeshComponents.Reset(CrowdSize);
	AgentActors.Reset(CrowdSize);
	UClass* SpawnClass = AgentClass ? AgentClass.Get() : AProphecyAgent::StaticClass();
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		FActorSpawnParameters SpawnParameters;
		SpawnParameters.Owner = this;
		SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		SpawnParameters.ObjectFlags |= RF_Transient;
		AProphecyAgent* AgentActor = GetWorld()->SpawnActor<AProphecyAgent>(
			SpawnClass,
			FTransform::Identity,
			SpawnParameters);
		if (!AgentActor)
		{
			UE_LOG(LogProphecyNNLocomotion, Error, TEXT("Could not spawn agent shell %d."), AgentIndex);
			break;
		}

		FProphecyAgentHandle Handle;
		Handle.Index = AgentIndex;
		Handle.Generation = Impl->Agents[AgentIndex].Generation;
		AgentActor->SetAgentHandle(Handle);
		AgentActor->TeleportManagedRootLowPoint(
			TrainingToUnreal(Impl->Agents[AgentIndex].CurRootPos),
			-FMath::RadiansToDegrees(Impl->Agents[AgentIndex].CurRootYaw));

		USkeletalMeshComponent* Component = AgentActor->GetAgentMesh();
		if (!Component->GetSkeletalMeshAsset())
		{
			UE_LOG(LogProphecyNNLocomotion, Error,
				TEXT("Agent class %s has no skeletal mesh (agent %d)."), *GetNameSafe(SpawnClass), AgentIndex);
			AgentActor->Destroy();
			break;
		}
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
		AgentActor->SetPhysicalDriveMode(InitialPhysicalDriveMode);
		if (UProphecyNNLocomotionAnimInstance* Anim = Cast<UProphecyNNLocomotionAnimInstance>(Component->GetAnimInstance()))
		{
			Anim->AgentId = PoseStoreAgentBase + AgentIndex;
			Anim->NNPoseIntervalSeconds = 1.0f / NNUpdateHz;
			Anim->bUseViewerGlobalPoseInterpolation =
				!FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNDisableViewerGlobalInterpolation"));
		}
		AgentActors.Add(AgentActor);
		MeshComponents.Add(Component);
	}
}

void AProphecyNNLocomotionManager::StepSimulation(float StepSeconds)
{
	const bool bWarmed = Impl->Stats.bCollecting;
	double Start = FPlatformTime::Seconds();
	ResamplePhysicalAgents();
	BuildInputBatch(StepSeconds);
	if (bWarmed) Impl->Stats.BuildSeconds += FPlatformTime::Seconds() - Start;
	Start = FPlatformTime::Seconds();
	if (!RunModelBatch()) return;
	if (bWarmed) Impl->Stats.InferenceSeconds += FPlatformTime::Seconds() - Start;
	ApplyOutputBatch(StepSeconds);
	if (Impl->bAbsoluteMotionAudit)
	{
		++Impl->AbsoluteMotionReferenceFrame;
	}
	if (bWarmed) Impl->Stats.OutputSeconds += FPlatformTime::Seconds() - Start;
	if (bWarmed) ++Impl->Stats.NNSteps;
}

void AProphecyNNLocomotionManager::ResamplePhysicalAgents()
{
	for (int32 AgentIndex = 0; AgentIndex < AgentActors.Num(); ++AgentIndex)
	{
		const AProphecyAgent* AgentActor = AgentActors[AgentIndex];
		if (AgentActor && AgentActor->GetSimulationMode() == EProphecyAgentSimulationMode::Physical)
		{
			ResamplePhysicalAgentState(AgentIndex);
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
	if (!AgentActors[AgentIndex]->SampleActualComponentPose(Impl->PublishedBoneNames, ActualTransforms))
	{
		return false;
	}

	float* Sample = StateSlice(Impl->PhysicalStateBuffer, AgentIndex);
	const FTransform& Pelvis = ActualTransforms[0];
	WriteStateVec3(Sample, 0, LocalUnrealToTraining(Pelvis.GetTranslation()));
	WriteRot6(MirrorYBasis(QuatToMatrix(Pelvis.GetRotation())), Sample + 3);

	const int32 PosOffsets[2] = { 9, 25 };
	const int32 RotOffsets[2] = { 12, 28 };
	const int32 StartRotOffsets[2] = { 18, 34 };
	const int32 ToeOffsets[2] = { 24, 40 };
	FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
	for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
	{
		const int32 PoseBase = LimbIndex == 0 ? 1 : 5;
		const FMat3f ThighRotation = MirrorYBasis(QuatToMatrix(ActualTransforms[PoseBase].GetRotation()));
		const FMat3f FootRotation = MirrorYBasis(QuatToMatrix(ActualTransforms[PoseBase + 2].GetRotation()));
		const FMat3f ToeRotation = MirrorYBasis(QuatToMatrix(ActualTransforms[PoseBase + 3].GetRotation()));
		WriteStateVec3(Sample, PosOffsets[LimbIndex], LocalUnrealToTraining(ActualTransforms[PoseBase + 2].GetTranslation()));
		WriteRot6(FootRotation, Sample + RotOffsets[LimbIndex]);
		WriteRot6(ThighRotation, Sample + StartRotOffsets[LimbIndex]);

		const FMat3f ToeRelative = Multiply(ToeRotation, Transpose(FootRotation));
		const FVector3f ToeRotationVector = RotationVectorBetween(FMat3f(), ToeRelative);
		const FImpl::FLimb& Limb = Agent.bUseWalkPolicy ? Impl->WalkLimbs[LimbIndex] : Impl->Limbs[LimbIndex];
		Sample[ToeOffsets[LimbIndex]] = FMath::Clamp(
			FVector3f::DotProduct(ToeRotationVector, SafeNormal(Limb.ToeAxis)) / ToeAlphaRadians,
			-1.0f,
			1.0f);
	}
	CleanState(Sample, *Impl);

	float* Previous = StateSlice(Impl->PrevStateBuffer, AgentIndex);
	float* Current = StateSlice(Impl->CurStateBuffer, AgentIndex);
	float* PreviousPhysical = StateSlice(Impl->PreviousPhysicalStateBuffer, AgentIndex);
	FMemory::Memcpy(Previous, Agent.bHasPhysicalSample ? PreviousPhysical : Sample, StateDim * sizeof(float));
	FMemory::Memcpy(Current, Sample, StateDim * sizeof(float));
	FMemory::Memcpy(PreviousPhysical, Sample, StateDim * sizeof(float));
	Agent.bHasPhysicalSample = true;
	return true;
}

void AProphecyNNLocomotionManager::BuildInputBatch(float StepSeconds)
{
	const float Speed = AgentSpeedCmPerSecond / MetersToCentimeters;
	const float Arrival = ArrivalRadiusCm / MetersToCentimeters;
	const bool bBridgeDriving = IsSimBridgeActive() && Impl->bReceivedBridgeFrame;
	for (int32 AgentIndex = 0; AgentIndex < BatchSize; ++AgentIndex)
	{
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		if (!bBridgeDriving || AgentIndex >= CrowdSize)
		{
			UpdateRouteIntent(Agent, Speed, Arrival);
		}
		Agent.bUseWalkPolicy = Agent.MoverIntent.mode != prophecy::sim::LocomotionMode::Run;
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

		const prophecy::sim::FutureRootWindow FutureRoots = prophecy::sim::PredictFutureRoots(
			Agent.MoverState, Agent.MoverIntent, StepSeconds);
		for (int32 FutureIndex = 1; FutureIndex <= FutureWindow; ++FutureIndex)
		{
			const prophecy::sim::RootTransform& FutureRoot = FutureRoots[FutureIndex - 1];
			const FVector3f FuturePosition(
				float(FutureRoot.position.x), Agent.CurRootPos.Y, float(FutureRoot.position.z));
			const FVector3f FutureLocal = TransformRow(FuturePosition - Agent.CurRootPos, YawMatrix(Agent.CurRootYaw));
			const float Scale = float(FutureIndex) * Impl->MaxSpeedScaleFinal;
			const float DeltaYaw = WrapAngle(float(FutureRoot.yaw_radians) - Agent.CurRootYaw);
			*Write++ = FMath::Clamp(FutureLocal.X / Scale, -2.0f, 2.0f);
			*Write++ = FMath::Clamp(FutureLocal.Z / Scale, -2.0f, 2.0f);
			*Write++ = FMath::Cos(DeltaYaw);
			*Write++ = FMath::Sin(DeltaYaw);
		}
		check(int32(Write - (Impl->InputBuffer.GetData() + AgentIndex * InputDim)) == InputDim);
	}
}

bool AProphecyNNLocomotionManager::RunModelBatch()
{
	bool bNeedRun = false;
	bool bNeedWalk = false;
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		bNeedWalk |= Impl->Agents[AgentIndex].bUseWalkPolicy;
		bNeedRun |= !Impl->Agents[AgentIndex].bUseWalkPolicy;
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
	if (bNeedWalk)
	{
		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			if (Impl->Agents[AgentIndex].bUseWalkPolicy)
			{
				FMemory::Memcpy(
					Impl->OutputBuffer.GetData() + AgentIndex * PolicyOutputDim,
					Impl->WalkOutputBuffer.GetData() + AgentIndex * PolicyOutputDim,
					PolicyOutputDim * sizeof(float));
			}
		}
	}
	if (bNeedRun || bNeedWalk) return true;
	UE_LOG(LogProphecyNNLocomotion, Error, TEXT("No active NN locomotion policy was selected."));
	SetActorTickEnabled(false);
	return false;
}

void AProphecyNNLocomotionManager::ApplyOutputBatch(float StepSeconds)
{
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
		const bool bWalkPolicy = Agent.bUseWalkPolicy;
		const float* CurrentState = StateSlice(Impl->CurStateBuffer, AgentIndex);
		float* Transition = StateSlice(Impl->PublishedStateBuffer, AgentIndex);
		FMemory::Memcpy(
			StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex),
			Transition,
			StateDim * sizeof(float));
		float* NextState = StateSlice(Impl->NextStateBuffer, AgentIndex);
		const float* Raw = Impl->OutputBuffer.GetData() + AgentIndex * PolicyOutputDim;
		for (int32 Index = 0; Index < StateDim; ++Index) Transition[Index] = CurrentState[Index] + Raw[Index];
		CleanState(Transition, *Impl);

		float Heights[2] = { 0.0f, 0.0f };
		float Pin[2];
		if (bWalkPolicy && Impl->bWalkPinLegacy)
		{
			const bool bBothPinned = Raw[41] < 0.0f && Raw[42] < 0.0f;
			Pin[0] = bBothPinned || Raw[41] <= Raw[42] ? 1.0f : 0.0f;
			Pin[1] = bBothPinned || Raw[42] < Raw[41] ? 1.0f : 0.0f;
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
		const bool bLeftBelow = !bWalkPolicy && Heights[0] < Impl->NearFloorFadeHeight;
		const bool bRightBelow = !bWalkPolicy && Heights[1] < Impl->NearFloorFadeHeight;
		if (bLeftBelow || bRightBelow)
		{
			const int32 Selected = bLeftBelow && bRightBelow ? (Raw[41] <= Raw[42] ? 0 : 1) : (Heights[0] <= Heights[1] ? 0 : 1);
			const float FadeSpan = FMath::Max(1.0e-6f, Impl->NearFloorFadeHeight - Impl->NearFloorFullHeight);
			const float Force = FMath::Clamp((Impl->NearFloorFadeHeight - Heights[Selected]) / FadeSpan, 0.0f, 1.0f) * Impl->NearFloorMinPin;
			Pin[Selected] = FMath::Max(Pin[Selected], Force);
		}

		for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
		{
			const FVector3f PredPos = ReadStateVec3(Transition, PosOffsets[LimbIndex]);
			const FMat3f PredRot = MatrixFromRot6(Transition + RotOffsets[LimbIndex]);
			const float PredToe = Transition[ToeOffsets[LimbIndex]];
			FVector3f OutPos = PredPos;
			if (Impl->FootRollSteps > 0)
			{
				const FVector3f CurPos = ReadStateVec3(CurrentState, PosOffsets[LimbIndex]);
				const FMat3f CurRot = MatrixFromRot6(CurrentState + RotOffsets[LimbIndex]);
				const float CurToe = CurrentState[ToeOffsets[LimbIndex]];
				const FVector3f RollDelta = Impl->IntegratedFootRollDelta(LimbIndex, CurRot, CurToe, PredRot, PredToe, bWalkPolicy);
				const FVector3f PinnedPos(CurPos.X + RollDelta.X, CurPos.Y + RollDelta.Y, PredPos.Z);
				OutPos = FMath::Lerp(PredPos, PinnedPos, Pin[LimbIndex]);
			}
			const float Lowest = Impl->LowestFootPointZ(LimbIndex, OutPos, PredRot, PredToe, bWalkPolicy);
			OutPos.Z += FMath::Max(0.0f, Impl->GroundHeight - Lowest);
			WriteStateVec3(Transition, PosOffsets[LimbIndex], OutPos);
		}
		CleanState(Transition, *Impl);
		Agent.PinProbability = FVector2f(Pin[0], Pin[1]);
		Agent.PreviousPublishedRoot = Agent.PublishedRoot;
		Agent.PreviousPublishedYaw = Agent.PublishedYaw;
		Agent.PublishedRoot = Agent.CurRootPos;
		Agent.PublishedYaw = Agent.CurRootYaw;

		const float* Future = Impl->InputBuffer.GetData() + AgentIndex * InputDim + 120;
		const FVector3f NextRootDelta(Future[0] * Impl->MaxSpeedScaleFinal, 0.0f, Future[1] * Impl->MaxSpeedScaleFinal);
		const float NextYawDelta = FMath::Atan2(Future[3], Future[2]);
		FMemory::Memcpy(NextState, Transition, StateDim * sizeof(float));
		RebaseStateRoot(NextState, *Impl, NextRootDelta, NextYawDelta);
		Agent.PrevRootPos = Agent.CurRootPos;
		Agent.PrevRootYaw = Agent.CurRootYaw;
		prophecy::sim::StepLocomotion(Agent.MoverState, Agent.MoverIntent, StepSeconds);
		Agent.CurRootPos.X = float(Agent.MoverState.position.x);
		Agent.CurRootPos.Z = float(Agent.MoverState.position.z);
		Agent.CurRootYaw = float(Agent.MoverState.yaw_radians);
	}
	Swap(Impl->PrevStateBuffer, Impl->CurStateBuffer);
	Swap(Impl->CurStateBuffer, Impl->NextStateBuffer);
}

void AProphecyNNLocomotionManager::PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds)
{
	Impl->Agents[AgentIndex].PublishedPoseTimeSeconds = SourceTimeSeconds;
	const float* State = StateSlice(Impl->PublishedStateBuffer, AgentIndex);
	const float* PreviousState = StateSlice(Impl->PreviousPublishedStateBuffer, AgentIndex);
	TArrayView<FTransform> LocalTransforms = TransformSlice(Impl->LocalTransformBuffer, AgentIndex);
	TArrayView<FTransform> PreviousComponentTransforms = TransformSlice(Impl->PreviousComponentTransformBuffer, AgentIndex);
	TArrayView<FTransform> ComponentTransforms = TransformSlice(Impl->ComponentTransformBuffer, AgentIndex);
	const bool bWalkPolicy = Impl->Agents[AgentIndex].bUseWalkPolicy;
	const TArray<FVector3f>& LocalOffsets = bWalkPolicy ? Impl->WalkLocalOffsets : Impl->LocalOffsets;
	const int32 PosOffsets[2] = { 9, 25 };
	const int32 RotOffsets[2] = { 12, 28 };
	const int32 StartRotOffsets[2] = { 18, 34 };
	const int32 ToeOffsets[2] = { 24, 40 };

	auto BuildPoseTransforms = [&](const float* PoseState, TArrayView<FTransform> OutComponentTransforms,
		TArrayView<FTransform>* OutLocalTransforms)
	{
		const FMat3f PelvisRot = MatrixFromRot6(PoseState + 3);
		const FVector3f PelvisPos = ReadStateVec3(PoseState, 0);
		OutComponentTransforms[0] = FTransform(
			MatrixToQuat(MirrorYBasis(PelvisRot)),
			LocalTrainingToUnreal(PelvisPos),
			FVector::OneVector);
		if (OutLocalTransforms)
		{
			(*OutLocalTransforms)[0] = OutComponentTransforms[0];
		}

		for (int32 LimbIndex = 0; LimbIndex < 2; ++LimbIndex)
		{
			const FImpl::FLimb& Limb = bWalkPolicy ? Impl->WalkLimbs[LimbIndex] : Impl->Limbs[LimbIndex];
			const FVector3f Base = PelvisPos + TransformRow(LocalOffsets[Limb.Start], PelvisRot);
			const FMat3f ThighGlobal = MatrixFromRot6(PoseState + StartRotOffsets[LimbIndex]);
			const FVector3f Mid = Base + TransformRow(LocalOffsets[Limb.Mid], ThighGlobal);
			const FVector3f End = ReadStateVec3(PoseState, PosOffsets[LimbIndex]);
			const FVector3f WorldPole = TransformRow(Limb.LocalPoleAxes[0], ThighGlobal);
			const FMat3f CalfGlobal = RotationFromAxisAndPole(
				LocalOffsets[Limb.End], End - Mid, Limb.LocalPoleAxes[1], WorldPole);
			const FMat3f FootGlobal = MatrixFromRot6(PoseState + RotOffsets[LimbIndex]);
			const FMat3f ToeGlobal = Multiply(
				AxisAngleMatrix(
					Limb.ToeAxis,
					FMath::Clamp(PoseState[ToeOffsets[LimbIndex]], -1.0f, 1.0f) * ToeAlphaRadians),
				FootGlobal);
			const FVector3f ToePosition = End + TransformRow(Limb.ToeOffset, FootGlobal);
			const int32 OutputBase = LimbIndex == 0 ? 1 : 5;
			OutComponentTransforms[OutputBase + 0] = FTransform(
				MatrixToQuat(MirrorYBasis(ThighGlobal)), LocalTrainingToUnreal(Base), FVector::OneVector);
			OutComponentTransforms[OutputBase + 1] = FTransform(
				MatrixToQuat(MirrorYBasis(CalfGlobal)), LocalTrainingToUnreal(Mid), FVector::OneVector);
			OutComponentTransforms[OutputBase + 2] = FTransform(
				MatrixToQuat(MirrorYBasis(FootGlobal)), LocalTrainingToUnreal(End), FVector::OneVector);
			OutComponentTransforms[OutputBase + 3] = FTransform(
				MatrixToQuat(MirrorYBasis(ToeGlobal)), LocalTrainingToUnreal(ToePosition), FVector::OneVector);

			if (OutLocalTransforms)
			{
				const FMat3f ThighLocal = Multiply(ThighGlobal, Transpose(PelvisRot));
				const FMat3f CalfLocal = Multiply(CalfGlobal, Transpose(ThighGlobal));
				const FMat3f FootLocal = Multiply(FootGlobal, Transpose(CalfGlobal));
				const FMat3f ToeLocal = Multiply(ToeGlobal, Transpose(FootGlobal));
				const FVector3f DynamicFootLocal = TransformRow(End - Mid, Transpose(CalfGlobal));
				(*OutLocalTransforms)[OutputBase + 0] = FTransform(
					MatrixToQuat(MirrorYBasis(ThighLocal)),
					LocalTrainingToUnreal(LocalOffsets[Limb.Start]),
					FVector::OneVector);
				(*OutLocalTransforms)[OutputBase + 1] = FTransform(
					MatrixToQuat(MirrorYBasis(CalfLocal)),
					LocalTrainingToUnreal(LocalOffsets[Limb.Mid]),
					FVector::OneVector);
				(*OutLocalTransforms)[OutputBase + 2] = FTransform(
					MatrixToQuat(MirrorYBasis(FootLocal)),
					LocalTrainingToUnreal(DynamicFootLocal),
					FVector::OneVector);
				(*OutLocalTransforms)[OutputBase + 3] = FTransform(
					MatrixToQuat(MirrorYBasis(ToeLocal)),
					LocalTrainingToUnreal(Limb.ToeOffset),
					FVector::OneVector);
			}
		}
	};
	BuildPoseTransforms(PreviousState, PreviousComponentTransforms, nullptr);
	BuildPoseTransforms(State, ComponentTransforms, &LocalTransforms);

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
				Result = Mesh->GetRelativeTransform() * CapsuleWorld;
			}
		}
		Result.NormalizeRotation();
		return Result;
	};
	const FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
	const FTransform PreviousComponentWorldTransform = BuildComponentWorldTransform(
		Agent.PreviousPublishedRoot, Agent.PreviousPublishedYaw);
	const FTransform ComponentWorldTransform = BuildComponentWorldTransform(
		Agent.PublishedRoot, Agent.PublishedYaw);
	FProphecyNNPoseStore::SetAgentLocalPose(
		PoseStoreAgentBase + AgentIndex,
		Impl->PublishedBoneNames,
		LocalTransforms,
		PreviousComponentTransforms,
		ComponentTransforms,
		PreviousComponentWorldTransform,
		ComponentWorldTransform,
		SourceTimeSeconds);
}

void AProphecyNNLocomotionManager::UpdateVisualRoots()
{
	if (!bSpawnVisuals) return;
	const float Alpha = Impl->VisualPoseAlpha;
	for (int32 AgentIndex = 0; AgentIndex < AgentActors.Num(); ++AgentIndex)
	{
		if (!AgentActors[AgentIndex]) continue;
		FImpl::FAgent& Agent = Impl->Agents[AgentIndex];
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
			const double PoseSourceTime = GetWorld()
				? double(GetWorld()->GetTimeSeconds()) - double(Impl->AccumulatedStepSeconds)
				: 0.0;
			PublishAgentPose(AgentIndex, PoseSourceTime);
		}
	}
}

void AProphecyNNLocomotionManager::InitializeSimpleTestCamera()
{
	if (!Impl->bSimpleLocomotionTest || AgentActors.IsEmpty() || !IsValid(AgentActors[0]) || !GetWorld()) return;

	FActorSpawnParameters SpawnParameters;
	SpawnParameters.Owner = this;
	SpawnParameters.ObjectFlags |= RF_Transient;
	SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Impl->SimpleTestCamera = GetWorld()->SpawnActor<ACameraActor>(
		ACameraActor::StaticClass(),
		FTransform::Identity,
		SpawnParameters);
	ACameraActor* Camera = Impl->SimpleTestCamera.Get();
	if (!IsValid(Camera)) return;

	Impl->SimpleTestCameraYawDegrees = AgentActors[0]->GetActorRotation().Yaw;
	if (UCameraComponent* CameraComponent = Camera->GetCameraComponent())
	{
		CameraComponent->SetFieldOfView(72.0f);
	}

	Impl->SimpleTestPlayerController = GetWorld()->GetFirstPlayerController();
	if (APlayerController* PlayerController = Impl->SimpleTestPlayerController.Get())
	{
		FInputModeGameOnly InputMode;
		InputMode.SetConsumeCaptureMouseDown(false);
		PlayerController->SetInputMode(InputMode);
		PlayerController->bShowMouseCursor = false;
		PlayerController->SetViewTarget(Camera);
	}
	if (UGameViewportClient* ViewportClient = GetWorld()->GetGameViewport())
	{
		ViewportClient->SetMouseCaptureMode(EMouseCaptureMode::CapturePermanently_IncludingInitialMouseDown);
		ViewportClient->SetMouseLockMode(EMouseLockMode::LockAlways);
		ViewportClient->SetHideCursorDuringCapture(true);
	}
	UpdateSimpleTestCamera();
}

void AProphecyNNLocomotionManager::UpdateSimpleTestInput()
{
	if (Impl->bAbsoluteMotionAudit)
	{
		AgentSpeedCmPerSecond = Impl->bAbsoluteMotionAuditWalk ? 200.0f : 500.0f;
		return;
	}

	APlayerController* PlayerController = Impl->SimpleTestPlayerController.Get();
	if (!PlayerController && GetWorld())
	{
		Impl->SimpleTestPlayerController = GetWorld()->GetFirstPlayerController();
		PlayerController = Impl->SimpleTestPlayerController.Get();
		if (PlayerController && Impl->SimpleTestCamera.IsValid())
		{
			PlayerController->SetViewTarget(Impl->SimpleTestCamera.Get());
		}
	}
	if (!PlayerController) return;

	float MouseX = 0.0f;
	float MouseY = 0.0f;
	PlayerController->GetInputMouseDelta(MouseX, MouseY);
	Impl->SimpleTestCameraYawDegrees += MouseX * CameraSensitivity;
	Impl->SimpleTestCameraPitchDegrees = FMath::Clamp(
		Impl->SimpleTestCameraPitchDegrees + MouseY * CameraSensitivity,
		-70.0f,
		20.0f);

	const bool bRun =
		PlayerController->IsInputKeyDown(EKeys::LeftShift) ||
		PlayerController->IsInputKeyDown(EKeys::RightShift);
	AgentSpeedCmPerSecond = bRun ? 500.0f : 200.0f;
}

void AProphecyNNLocomotionManager::UpdateSimpleTestCamera()
{
	ACameraActor* Camera = Impl->SimpleTestCamera.Get();
	if (!IsValid(Camera) || AgentActors.IsEmpty() || !IsValid(AgentActors[0])) return;
	const FVector Target = AgentActors[0]->GetRootLowPoint() + FVector(0.0, 0.0, 115.0);
	const FVector OrbitDirection = FRotator(
		Impl->SimpleTestCameraPitchDegrees,
		Impl->SimpleTestCameraYawDegrees,
		0.0f).Vector();
	const FVector CameraLocation = Target - OrbitDirection * 420.0;
	Camera->SetActorLocationAndRotation(
		CameraLocation,
		(Target - CameraLocation).Rotation(),
		false,
		nullptr,
		ETeleportType::TeleportPhysics);
}

void AProphecyNNLocomotionManager::CaptureAbsoluteMotionAuditFrame()
{
	if (!Impl->bAbsoluteMotionAuditCanCapture || Impl->bAbsoluteMotionAuditWritten ||
		AgentActors.IsEmpty() || !IsValid(AgentActors[0]))
	{
		return;
	}

	const AProphecyAgent* AgentActor = AgentActors[0];
	const USkeletalMeshComponent* Mesh = AgentActor->GetAgentMesh();
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
			TEXT("NN_LOCOMOTION_BENCHMARK crowd=%d physical=%d macd=%d drive=%s foot_roll_steps=%d overlay=%d sim_fps=%.2f wall_ms=%.4f run_runtime=%s walk_runtime=%s build_ms=%.4f inference_ms=%.4f output_ms=%.4f store_ms=%.4f steps=%lld"),
			CrowdSize, InitialPhysicalAgentCount, bInitialPhysicalAgentsUseMACD ? InitialPhysicalAgentCount : 0,
			InitialPhysicalDriveMode == EProphecyAgentPhysicalDriveMode::RootAndJointTorque ? TEXT("torque") : TEXT("world"),
			Impl->FootRollSteps, bOverlayEnabled ? 1 : 0, FPS, WallMillisecondsPerFrame,
			*Impl->Model.RuntimeUsed, *Impl->WalkModel.RuntimeUsed,
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
		Agent.bHasBridgeIntent = true;
		if (bFirstFrame)
		{
			Agent.bUseWalkPolicy = Agent.MoverIntent.mode != prophecy::sim::LocomotionMode::Run;
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
	if (AgentActor->GetSimulationMode() == EProphecyAgentSimulationMode::Physical &&
		NewMode == EProphecyAgentSimulationMode::Kinematic)
	{
		ResamplePhysicalAgentState(Handle.Index);
	}

	if (!AgentActor->SetSimulationMode(NewMode))
	{
		return false;
	}

	if (NewMode == EProphecyAgentSimulationMode::Physical)
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
