#include "ProphecyNNCrowdBenchmark.h"

#include "ProphecyNNPoseAnimInstance.h"
#include "ProphecyNNPoseTypes.h"

#include "Animation/AnimInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/LODSyncComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/VolumetricCloudComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/Light.h"
#include "Engine/LocalPlayer.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/SkyLight.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "HAL/IConsoleManager.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Interfaces/IPluginManager.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "MeshDescriptionBuilder.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "NNE.h"
#include "NNEModelData.h"
#include "NNERuntimeCPU.h"
#include "NNERuntimeGPU.h"
#include "NNERuntimeRunSync.h"
#include "NNETypes.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "StaticMeshAttributes.h"
#include "UnrealClient.h"

namespace
{
DEFINE_LOG_CATEGORY_STATIC(LogProphecyNNBenchmark, Log, All);

constexpr int32 ProphecyBatchSize = 100;
constexpr int32 ProphecyInputDim = 569;
constexpr int32 ProphecyOutputDim = 155;
constexpr int32 ProphecyPoseDimNoContacts = 153;
constexpr int32 ProphecyBodyBoneCount = 25;
constexpr int32 ProphecyNonPelvisBoneCount = 24;
constexpr float ProphecyMetersToCentimeters = 100.0f;
constexpr float ProphecyGrassNearRadiusCm = 3500.0f;
constexpr float ProphecyGrassFarRadiusCm = 8000.0f;
constexpr float ProphecyGrassHorizonRadiusCm = 42000.0f;
constexpr float ProphecyGrassDistantFadeStartCm = 52000.0f;
constexpr float ProphecyGrassDistantFadeRangeCm = 12000.0f;
constexpr float ProphecyGrassFarRootLiftStartCm = 5400.0f;
constexpr float ProphecyGrassFarRootLiftRangeCm = 3000.0f;
constexpr float ProphecyGrassFarRootLiftStrength = 0.60f;
constexpr float ProphecyGroundGrassGrainWorldCm = 360.0f;
constexpr float ProphecyGroundGrassGrainStrength = 0.55f;
constexpr float ProphecyGrassFarTargetSpacingCm = 420.0f;
constexpr float ProphecyGrassFarCoverage = 0.72f;
constexpr float ProphecyGrassFarScaleXYMin = 1.14f;
constexpr float ProphecyGrassFarScaleXYMax = 2.05f;
constexpr float ProphecyGrassFarScaleZMin = 0.72f;
constexpr float ProphecyGrassFarScaleZMax = 1.08f;
constexpr int32 ProphecyGrassBladesPerTile = 44;
constexpr int32 ProphecyGrassDenseBladesPerTile = 176;
constexpr int32 ProphecyGrassDenseFillersPerTile = 8;
constexpr float ProphecyGrassTileSizeCm = 240.0f;
constexpr float ProphecyGrassDenseMeshRadiusCm = 18000.0f;
constexpr int32 ProphecyDistantHillSegments = 192;
constexpr int32 ProphecyDistantHillRings = 18;
constexpr float ProphecyDistantHillInnerRadiusCm = 22000.0f;
constexpr float ProphecyDistantHillRiseStartRadiusCm = 27000.0f;
constexpr float ProphecyDistantHillOuterRadiusCm = 86000.0f;
constexpr float ProphecyTerrainCenterX = 0.0f;
constexpr float ProphecyTerrainCenterY = 700.0f;
constexpr int32 ProphecyTreeComponentCount = 12;
constexpr float ProphecyTreePlayableInnerRadiusCm = 2600.0f;
constexpr float ProphecyTreePlayableOuterRadiusCm = 15500.0f;
constexpr float ProphecyTreeShadowMaskHalfExtentCm = 17000.0f;
const FLinearColor ProphecyGrassGroundBaseColor(0.135f, 0.285f, 0.058f, 1.0f);
const FLinearColor ProphecyGrassTerrainBaseColor(0.078f, 0.170f, 0.042f, 1.0f);
const FLinearColor ProphecyGrassContinuationColor(0.105f, 0.245f, 0.048f, 1.0f);
const FLinearColor ProphecyGrassFarRootLiftColor(0.130f, 0.275f, 0.052f, 1.0f);
const FLinearColor ProphecyGroundGrassGrainDarkColor(0.070f, 0.195f, 0.032f, 1.0f);
const FLinearColor ProphecyGroundGrassGrainLightColor(0.165f, 0.340f, 0.072f, 1.0f);

float ProphecySmooth01(float T)
{
	T = FMath::Clamp(T, 0.0f, 1.0f);
	return T * T * (3.0f - 2.0f * T);
}

float ProphecyDistantHillHeightAtRadiusAngle(float Radius, float Angle)
{
	const float RiseT = ProphecySmooth01((Radius - ProphecyDistantHillRiseStartRadiusCm) / (ProphecyDistantHillOuterRadiusCm - ProphecyDistantHillRiseStartRadiusCm));
	const float RidgeWave =
		0.58f
		+ 0.30f * FMath::Sin(Angle * 2.0f + 0.35f)
		+ 0.24f * FMath::Sin(Angle * 5.0f - 1.25f)
		+ 0.18f * FMath::Sin(Angle * 9.0f + Radius * 0.00007f)
		+ 0.10f * FMath::Sin(Angle * 17.0f - Radius * 0.00011f);
	const float RidgeStrength = FMath::Clamp(RidgeWave, 0.10f, 1.25f);
	const float RollingDetail =
		FMath::Sin(Angle * 13.0f + Radius * 0.00017f) * 760.0f
		+ FMath::Sin(Angle * 3.0f - Radius * 0.00008f) * 1180.0f
		+ FMath::Sin(Angle * 23.0f + Radius * 0.00021f) * 360.0f;
	float Height = -4.0f + FMath::Pow(RiseT, 0.62f) * (2600.0f + 5200.0f * RidgeStrength) + RollingDetail * 0.72f * RiseT * (1.0f - RiseT * 0.16f);
	if (Radius <= ProphecyDistantHillInnerRadiusCm + 1.0f)
	{
		Height = -4.0f;
	}
	return Height;
}

bool ProphecyDistantTerrainHeightAtXY(const FVector2D& WorldXY, float& OutHeight)
{
	const FVector2D Local = WorldXY - FVector2D(ProphecyTerrainCenterX, ProphecyTerrainCenterY);
	const float Radius = Local.Size();
	if (Radius < ProphecyDistantHillInnerRadiusCm || Radius > ProphecyDistantHillOuterRadiusCm)
	{
		return false;
	}

	const float Angle = FMath::Atan2(Local.Y, Local.X);
	OutHeight = ProphecyDistantHillHeightAtRadiusAngle(Radius, Angle);
	return true;
}

struct FProphecyTreeShadowCaster
{
	FVector2D Position = FVector2D::ZeroVector;
	float HeightCm = 1800.0f;
	float TrunkRadiusCm = 30.0f;
	float CrownRadiusCm = 260.0f;
	float Strength = 0.42f;
};

struct FProphecyNNRot6
{
	FVector3f A = FVector3f(1.0f, 0.0f, 0.0f);
	FVector3f B = FVector3f(0.0f, 1.0f, 0.0f);
};

struct FProphecyNNMat3
{
	FVector3f Row0 = FVector3f(1.0f, 0.0f, 0.0f);
	FVector3f Row1 = FVector3f(0.0f, 1.0f, 0.0f);
	FVector3f Row2 = FVector3f(0.0f, 0.0f, 1.0f);
};

struct FProphecyNNPoseRuntime
{
	FVector3f PelvisPos = FVector3f::ZeroVector;
	FProphecyNNRot6 PelvisRot6;
	TArray<FProphecyNNRot6> NonPelvisRot6;
	TArray<FVector3f> CanonPos;
	FVector2f Contacts = FVector2f::ZeroVector;
};

struct FProphecyNNAgentRuntime
{
	FProphecyNNPoseRuntime PrevPose;
	FProphecyNNPoseRuntime CurPose;
	FVector3f PrevRootPos = FVector3f::ZeroVector;
	FVector3f CurRootPos = FVector3f::ZeroVector;
	float PrevRootYaw = 0.0f;
	float CurRootYaw = 0.0f;
	float SpeedMetersPerSecond = 1.45f;
	float YawRateRadiansPerSecond = 0.0f;
	TArray<FTransform> LocalTransforms;
};

struct FProphecyBenchmarkStats
{
	double ElapsedSeconds = 0.0;
	double WarmedSeconds = 0.0;
	double BuildInputSeconds = 0.0;
	double InferenceSeconds = 0.0;
	double OutputSeconds = 0.0;
	double StoreSeconds = 0.0;
	double VisualSeconds = 0.0;
	double SimSeconds = 0.0;
	int64 FrameCount = 0;
	int64 WarmedFrameCount = 0;
	int64 NNStepCount = 0;
	int64 WarmedNNStepCount = 0;
	double LastLogSeconds = 0.0;
};

class FProphecyNNRunSyncModel
{
public:
	bool CreateGpu(TObjectPtr<UNNEModelData> ModelData, const FString& RuntimeName)
	{
		TWeakInterfacePtr<INNERuntimeGPU> Runtime = UE::NNE::GetRuntime<INNERuntimeGPU>(RuntimeName);
		if (!Runtime.IsValid())
		{
			return false;
		}

		if (Runtime->CanCreateModelGPU(ModelData) != UE::NNE::EResultStatus::Ok)
		{
			UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("NNE runtime %s cannot create the GPU model."), *RuntimeName);
			return false;
		}

		TSharedPtr<UE::NNE::IModelGPU> Model = Runtime->CreateModelGPU(ModelData);
		if (!Model.IsValid())
		{
			return false;
		}

		GpuInstance = Model->CreateModelInstanceGPU();
		if (!GpuInstance.IsValid())
		{
			return false;
		}

		RuntimeUsed = RuntimeName;
		bUsingGpu = true;
		return SetInputShape(GpuInstance.Get());
	}

	bool CreateCpu(TObjectPtr<UNNEModelData> ModelData, const FString& RuntimeName)
	{
		TWeakInterfacePtr<INNERuntimeCPU> Runtime = UE::NNE::GetRuntime<INNERuntimeCPU>(RuntimeName);
		if (!Runtime.IsValid())
		{
			return false;
		}

		if (Runtime->CanCreateModelCPU(ModelData) != UE::NNE::EResultStatus::Ok)
		{
			UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("NNE runtime %s cannot create the CPU model."), *RuntimeName);
			return false;
		}

		TSharedPtr<UE::NNE::IModelCPU> Model = Runtime->CreateModelCPU(ModelData);
		if (!Model.IsValid())
		{
			return false;
		}

		CpuInstance = Model->CreateModelInstanceCPU();
		if (!CpuInstance.IsValid())
		{
			return false;
		}

		RuntimeUsed = RuntimeName;
		bUsingGpu = false;
		return SetInputShape(CpuInstance.Get());
	}

	bool Run(TArray<float>& InputBuffer, TArray<float>& OutputBuffer)
	{
		UE::NNE::IModelInstanceRunSync* Instance = GetInstance();
		if (!Instance)
		{
			return false;
		}

		const UE::NNE::FTensorBindingCPU InputBinding{ InputBuffer.GetData(), uint64(InputBuffer.Num() * sizeof(float)) };
		const UE::NNE::FTensorBindingCPU OutputBinding{ OutputBuffer.GetData(), uint64(OutputBuffer.Num() * sizeof(float)) };
		return Instance->RunSync(MakeArrayView(&InputBinding, 1), MakeArrayView(&OutputBinding, 1)) == UE::NNE::EResultStatus::Ok;
	}

	FString RuntimeUsed;
	bool bUsingGpu = false;

private:
	static bool SetInputShape(UE::NNE::IModelInstanceRunSync* Instance)
	{
		const uint32 ShapeData[] = { uint32(ProphecyBatchSize), uint32(ProphecyInputDim) };
		const UE::NNE::FTensorShape InputShape = UE::NNE::FTensorShape::Make(MakeArrayView(ShapeData, 2));
		return Instance->SetInputTensorShapes(MakeArrayView(&InputShape, 1)) == UE::NNE::EResultStatus::Ok;
	}

	UE::NNE::IModelInstanceRunSync* GetInstance() const
	{
		if (GpuInstance.IsValid())
		{
			return GpuInstance.Get();
		}
		return CpuInstance.Get();
	}

	TSharedPtr<UE::NNE::IModelInstanceCPU> CpuInstance;
	TSharedPtr<UE::NNE::IModelInstanceGPU> GpuInstance;
};

FString ResolveProjectPath(const FString& MaybeRelativePath)
{
	if (FPaths::IsRelative(MaybeRelativePath))
	{
		return FPaths::ConvertRelativePathToFull(FPaths::ProjectDir(), MaybeRelativePath);
	}
	return MaybeRelativePath;
}

void SetBenchmarkCVar(const TCHAR* Name, float Value, FString& OutAppliedSettings)
{
	if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Name))
	{
		CVar->Set(Value, ECVF_SetByCode);
		OutAppliedSettings += FString::Printf(TEXT("%s=%.3g "), Name, Value);
	}
}

void SetBenchmarkCVar(const TCHAR* Name, int32 Value, FString& OutAppliedSettings)
{
	if (IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(Name))
	{
		CVar->Set(Value, ECVF_SetByCode);
		OutAppliedSettings += FString::Printf(TEXT("%s=%d "), Name, Value);
	}
}

bool IsHybridShadowMode(const FString& ShadowMode)
{
	return ShadowMode.Equals(TEXT("Hybrid"), ESearchCase::IgnoreCase);
}

bool IsFullShadowMode(const FString& ShadowMode)
{
	return ShadowMode.Equals(TEXT("Full"), ESearchCase::IgnoreCase);
}

bool IsShadowEnabled(const FString& ShadowMode)
{
	return IsHybridShadowMode(ShadowMode) || IsFullShadowMode(ShadowMode);
}

bool ShouldAgentCastRealShadow(const FString& ShadowMode, int32 RealShadowBudget, int32 AgentIndex)
{
	if (IsFullShadowMode(ShadowMode))
	{
		return true;
	}
	if (!IsHybridShadowMode(ShadowMode))
	{
		return false;
	}
	return AgentIndex < FMath::Max(0, RealShadowBudget);
}

FVector GetBenchmarkLightDirection(const ADirectionalLight* BenchmarkKeyLight)
{
	if (BenchmarkKeyLight && BenchmarkKeyLight->GetLightComponent())
	{
		const FVector LightDirection = BenchmarkKeyLight->GetLightComponent()->GetDirection().GetSafeNormal();
		if (!LightDirection.IsNearlyZero())
		{
			return LightDirection;
		}
	}

	return FRotator(-45.0, 35.0, 0.0).Vector().GetSafeNormal();
}

FVector GetGroundShadowDirectionForLight(const ADirectionalLight* BenchmarkKeyLight)
{
	FVector LightDirection = GetBenchmarkLightDirection(BenchmarkKeyLight);
	if (LightDirection.Z > 0.0)
	{
		LightDirection *= -1.0;
	}

	FVector GroundDirection(LightDirection.X, LightDirection.Y, 0.0);
	if (GroundDirection.IsNearlyZero())
	{
		GroundDirection = FVector(FMath::Cos(FMath::DegreesToRadians(35.0f)), FMath::Sin(FMath::DegreesToRadians(35.0f)), 0.0);
	}
	return GroundDirection.GetSafeNormal();
}

float GetGroundShadowProjectionScaleForLight(const ADirectionalLight* BenchmarkKeyLight)
{
	FVector LightDirection = GetBenchmarkLightDirection(BenchmarkKeyLight);
	if (LightDirection.Z > 0.0)
	{
		LightDirection *= -1.0;
	}

	const float Horizontal = FVector2D(float(LightDirection.X), float(LightDirection.Y)).Size();
	const float Vertical = FMath::Max(0.12f, float(-LightDirection.Z));
	return FMath::Clamp(Horizontal / Vertical, 0.35f, 2.25f);
}

float GetYawForLocalYAlignedShadowMesh(const FVector& ShadowDirection)
{
	const FVector Direction = ShadowDirection.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
	return FMath::RadiansToDegrees(FMath::Atan2(float(-Direction.X), float(Direction.Y)));
}

bool IsRootContactShadowVariant(const FString& Variant)
{
	return Variant.IsEmpty() ||
		Variant.Equals(TEXT("Root"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("Cheap"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("Fast"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("HighlyOptimized"), ESearchCase::IgnoreCase);
}

bool IsLimbContactShadowVariant(const FString& Variant)
{
	return Variant.Equals(TEXT("Limbs"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("Limb"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("Optimized"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("DynamicLimbs"), ESearchCase::IgnoreCase);
}

bool IsFullDynamicShadowVariant(const FString& Variant)
{
	return Variant.Equals(TEXT("Full"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("FullDynamic"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("Real"), ESearchCase::IgnoreCase);
}

bool IsContactShadowVariantDisabled(const FString& Variant)
{
	return Variant.Equals(TEXT("None"), ESearchCase::IgnoreCase) ||
		Variant.Equals(TEXT("Off"), ESearchCase::IgnoreCase);
}

FString CanonicalContactShadowVariant(const FString& Variant)
{
	if (IsLimbContactShadowVariant(Variant))
	{
		return TEXT("Limbs");
	}
	if (IsFullDynamicShadowVariant(Variant))
	{
		return TEXT("Full");
	}
	if (IsContactShadowVariantDisabled(Variant))
	{
		return TEXT("None");
	}
	return TEXT("Root");
}

float WrapAngleRadians(float Value)
{
	while (Value > UE_PI)
	{
		Value -= UE_TWO_PI;
	}
	while (Value < -UE_PI)
	{
		Value += UE_TWO_PI;
	}
	return Value;
}

FVector3f SafeNormal3f(const FVector3f& Value, const FVector3f& Fallback)
{
	const float SizeSquared = Value.SizeSquared();
	if (SizeSquared <= UE_SMALL_NUMBER)
	{
		return Fallback;
	}
	return Value * FMath::InvSqrt(SizeSquared);
}

FVector3f PickPerpendicular(const FVector3f& Axis)
{
	const FVector3f Candidate = FMath::Abs(Axis.X) < 0.8f ? FVector3f(1.0f, 0.0f, 0.0f) : FVector3f(0.0f, 1.0f, 0.0f);
	return SafeNormal3f(Candidate - Axis * FVector3f::DotProduct(Candidate, Axis), FVector3f(0.0f, 1.0f, 0.0f));
}

FProphecyNNRot6 CleanRot6(const FProphecyNNRot6& InRot6)
{
	FProphecyNNRot6 Out;
	Out.A = SafeNormal3f(InRot6.A, FVector3f(1.0f, 0.0f, 0.0f));
	FVector3f Second = InRot6.B - Out.A * FVector3f::DotProduct(Out.A, InRot6.B);
	if (Second.SizeSquared() <= UE_SMALL_NUMBER)
	{
		Second = PickPerpendicular(Out.A);
	}
	Out.B = SafeNormal3f(Second, FVector3f(0.0f, 1.0f, 0.0f));
	return Out;
}

FProphecyNNMat3 Rotation6DToMatrix(const FProphecyNNRot6& InRot6)
{
	const FProphecyNNRot6 Clean = CleanRot6(InRot6);
	FProphecyNNMat3 Out;
	Out.Row0 = Clean.A;
	Out.Row1 = Clean.B;
	Out.Row2 = FVector3f::CrossProduct(Clean.A, Clean.B);
	return Out;
}

FProphecyNNMat3 MatrixMultiply(const FProphecyNNMat3& A, const FProphecyNNMat3& B)
{
	const FVector3f ARows[] = { A.Row0, A.Row1, A.Row2 };
	const FVector3f BRows[] = { B.Row0, B.Row1, B.Row2 };
	FProphecyNNMat3 Out;
	FVector3f* ORows[] = { &Out.Row0, &Out.Row1, &Out.Row2 };

	for (int32 Row = 0; Row < 3; ++Row)
	{
		for (int32 Col = 0; Col < 3; ++Col)
		{
			(*ORows[Row])[Col] =
				ARows[Row].X * BRows[0][Col] +
				ARows[Row].Y * BRows[1][Col] +
				ARows[Row].Z * BRows[2][Col];
		}
	}
	return Out;
}

FVector3f TransformRowVector(const FVector3f& Vector, const FProphecyNNMat3& Matrix)
{
	return FVector3f(
		Vector.X * Matrix.Row0.X + Vector.Y * Matrix.Row1.X + Vector.Z * Matrix.Row2.X,
		Vector.X * Matrix.Row0.Y + Vector.Y * Matrix.Row1.Y + Vector.Z * Matrix.Row2.Y,
		Vector.X * Matrix.Row0.Z + Vector.Y * Matrix.Row1.Z + Vector.Z * Matrix.Row2.Z);
}

FProphecyNNMat3 YawToRowMatrix(float YawRadians)
{
	const float C = FMath::Cos(YawRadians);
	const float S = FMath::Sin(YawRadians);
	FProphecyNNMat3 Out;
	Out.Row0 = FVector3f(C, 0.0f, S);
	Out.Row1 = FVector3f(0.0f, 1.0f, 0.0f);
	Out.Row2 = FVector3f(-S, 0.0f, C);
	return Out;
}

FQuat MatrixToQuat(const FProphecyNNMat3& Matrix)
{
	const FMatrix UnrealMatrix(
		FPlane(Matrix.Row0.X, Matrix.Row0.Y, Matrix.Row0.Z, 0.0),
		FPlane(Matrix.Row1.X, Matrix.Row1.Y, Matrix.Row1.Z, 0.0),
		FPlane(Matrix.Row2.X, Matrix.Row2.Y, Matrix.Row2.Z, 0.0),
		FPlane(0.0, 0.0, 0.0, 1.0));
	return FQuat(UnrealMatrix).GetNormalized();
}

FVector ToUnrealVector(const FVector3f& ValueMeters)
{
	return FVector(ValueMeters.X, ValueMeters.Y, ValueMeters.Z) * ProphecyMetersToCentimeters;
}

FVector TrainingWorldToUnrealVector(const FVector3f& ValueMeters)
{
	return FVector(ValueMeters.X, ValueMeters.Z, ValueMeters.Y) * ProphecyMetersToCentimeters;
}

bool JsonNumberArrayToFloats(const TArray<TSharedPtr<FJsonValue>>& Values, TArray<float>& Out)
{
	Out.Reset(Values.Num());
	for (const TSharedPtr<FJsonValue>& Value : Values)
	{
		if (!Value.IsValid() || Value->Type != EJson::Number)
		{
			return false;
		}
		Out.Add(float(Value->AsNumber()));
	}
	return true;
}

bool JsonValueToVec3(const TSharedPtr<FJsonValue>& Value, FVector3f& Out)
{
	if (!Value.IsValid() || Value->Type != EJson::Array)
	{
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>& Values = Value->AsArray();
	if (Values.Num() != 3)
	{
		return false;
	}

	Out = FVector3f(float(Values[0]->AsNumber()), float(Values[1]->AsNumber()), float(Values[2]->AsNumber()));
	return true;
}

bool ReadVec3Array(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName, TArray<FVector3f>& Out)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Object->TryGetArrayField(FieldName, Values))
	{
		return false;
	}

	Out.Reset(Values->Num());
	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		FVector3f Vec = FVector3f::ZeroVector;
		if (!JsonValueToVec3(Value, Vec))
		{
			return false;
		}
		Out.Add(Vec);
	}
	return true;
}

bool ReadMat3(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName, FProphecyNNMat3& Out)
{
	const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
	if (!Object->TryGetArrayField(FieldName, Rows) || Rows->Num() != 3)
	{
		return false;
	}

	FVector3f* OutRows[] = { &Out.Row0, &Out.Row1, &Out.Row2 };
	for (int32 Row = 0; Row < 3; ++Row)
	{
		if (!(*Rows)[Row].IsValid() || (*Rows)[Row]->Type != EJson::Array)
		{
			return false;
		}

		TArray<float> Values;
		if (!JsonNumberArrayToFloats((*Rows)[Row]->AsArray(), Values) || Values.Num() != 3)
		{
			return false;
		}

		*OutRows[Row] = FVector3f(Values[0], Values[1], Values[2]);
	}

	return true;
}

bool ReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName, TArray<int32>& Out)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Object->TryGetArrayField(FieldName, Values))
	{
		return false;
	}

	Out.Reset(Values->Num());
	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		if (!Value.IsValid() || Value->Type != EJson::Number)
		{
			return false;
		}
		Out.Add(int32(Value->AsNumber()));
	}
	return true;
}

bool ReadNameArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName, TArray<FName>& Out)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Object->TryGetArrayField(FieldName, Values))
	{
		return false;
	}

	Out.Reset(Values->Num());
	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		if (!Value.IsValid() || Value->Type != EJson::String)
		{
			return false;
		}
		Out.Add(FName(*Value->AsString()));
	}
	return true;
}

void EnsureNiagaraContentMounted()
{
	static bool bAttemptedMount = false;
	if (bAttemptedMount)
	{
		return;
	}
	bAttemptedMount = true;

	const TSharedPtr<IPlugin> NiagaraPlugin = IPluginManager::Get().FindPlugin(TEXT("Niagara"));
	if (!NiagaraPlugin.IsValid())
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Niagara plugin was not found by IPluginManager; plugin content assets may not load."));
		return;
	}

	const FString NiagaraContentDir = FPaths::Combine(NiagaraPlugin->GetBaseDir(), TEXT("Content/"));
	if (!FPaths::DirectoryExists(NiagaraContentDir))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Niagara plugin content directory does not exist: %s"), *NiagaraContentDir);
		return;
	}

	FPackageName::RegisterMountPoint(TEXT("/Niagara/"), NiagaraContentDir);
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Mounted Niagara content root: /Niagara/ -> %s"), *NiagaraContentDir);
}

bool ReadRot6Array(const TSharedPtr<FJsonObject>& Object, const TCHAR* FieldName, TArray<FProphecyNNRot6>& Out)
{
	const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
	if (!Object->TryGetArrayField(FieldName, Values))
	{
		return false;
	}

	Out.Reset(Values->Num());
	for (const TSharedPtr<FJsonValue>& Value : *Values)
	{
		if (!Value.IsValid() || Value->Type != EJson::Array)
		{
			return false;
		}

		TArray<float> Numbers;
		if (!JsonNumberArrayToFloats(Value->AsArray(), Numbers) || Numbers.Num() != 6)
		{
			return false;
		}

		FProphecyNNRot6 Rot6;
		Rot6.A = FVector3f(Numbers[0], Numbers[1], Numbers[2]);
		Rot6.B = FVector3f(Numbers[3], Numbers[4], Numbers[5]);
		Out.Add(CleanRot6(Rot6));
	}
	return true;
}

bool ReadPose(const TSharedPtr<FJsonObject>& Object, FProphecyNNPoseRuntime& OutPose)
{
	TArray<float> PelvisPos;
	TArray<float> PelvisRot6;
	TArray<float> Contacts;

	const TArray<TSharedPtr<FJsonValue>>* PelvisPosValues = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* PelvisRot6Values = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* ContactValues = nullptr;

	if (!Object->TryGetArrayField(TEXT("pelvis_pos"), PelvisPosValues) ||
		!Object->TryGetArrayField(TEXT("pelvis_rot6"), PelvisRot6Values) ||
		!Object->TryGetArrayField(TEXT("contacts"), ContactValues))
	{
		return false;
	}

	if (!JsonNumberArrayToFloats(*PelvisPosValues, PelvisPos) || PelvisPos.Num() != 3 ||
		!JsonNumberArrayToFloats(*PelvisRot6Values, PelvisRot6) || PelvisRot6.Num() != 6 ||
		!JsonNumberArrayToFloats(*ContactValues, Contacts) || Contacts.Num() != 2)
	{
		return false;
	}

	OutPose.PelvisPos = FVector3f(PelvisPos[0], PelvisPos[1], PelvisPos[2]);
	OutPose.PelvisRot6.A = FVector3f(PelvisRot6[0], PelvisRot6[1], PelvisRot6[2]);
	OutPose.PelvisRot6.B = FVector3f(PelvisRot6[3], PelvisRot6[4], PelvisRot6[5]);
	OutPose.PelvisRot6 = CleanRot6(OutPose.PelvisRot6);
	OutPose.Contacts = FVector2f(Contacts[0], Contacts[1]);

	return ReadRot6Array(Object, TEXT("nonpelvis_rot6"), OutPose.NonPelvisRot6);
}

float Sigmoid(float Value)
{
	return 1.0f / (1.0f + FMath::Exp(-Value));
}
}

struct AProphecyNNCrowdBenchmarkActor::FImpl
{
	TArray<FName> BodyNames;
	TArray<FName> PublishedBoneNames;
	TArray<int32> Parents;
	TArray<FVector3f> LocalOffsets;
	FProphecyNNPoseRuntime SeedPrevPose;
	FProphecyNNPoseRuntime SeedCurPose;
	FProphecyNNMat3 SeedRootRot;
	TArray<FProphecyNNAgentRuntime> Agents;
	TArray<float> InputBuffer;
	TArray<float> OutputBuffer;
	TArray<FTransform> ScratchTransforms;
	TArray<FTransform> ScratchBoneComponentTransforms;
	TArray<FVector> ScratchBoneWorldPositions;
	FProphecyNNRunSyncModel Model;
	FProphecyBenchmarkStats Stats;
	TArray<FIntPoint> ProxySegments;
	TArray<FIntPoint> ShadowLimbSegments;
	TArray<float> ShadowLimbHalfWidthsCm;
	TArray<float> GrassShadowMaskValues;
	TArray<float> StaticGrassShadowMaskValues;
	TArray<FColor> GrassShadowMaskPixels;
	TArray<float> GroundShadowMaskValues;
	TArray<float> StaticGroundShadowMaskValues;
	TArray<FColor> GroundShadowMaskPixels;
	TArray<float> BloodMaskValues;
	TArray<float> BloodMaskCoreValues;
	TArray<FColor> BloodMaskPixels;
	TArray<FProphecyTreeShadowCaster> TreeShadowCasters;
	bool bLoggedGrassShadowMaskStats = false;
	bool bLoggedGroundShadowMaskStats = false;
	int64 LastGrassShadowMaskNNStep = -1;
	int64 LastGroundShadowMaskNNStep = -1;
	FString AppliedRenderSettings;
	FString ActiveGrassRenderer = TEXT("None");
	int32 GrassInstanceCount = 0;
	int32 GrassDenseInstanceCount = 0;
	int64 GrassVisualBladeCount = 0;
	int32 TreeInstanceCount = 0;
	int32 NiagaraComponentCount = 0;
	int32 GrassShadowMaskSize = 512;
	FVector2D GrassShadowMaskCenter = FVector2D::ZeroVector;
	float GrassShadowMaskHalfExtent = 6000.0f;
	int32 GroundShadowMaskSize = 256;
	FVector2D GroundShadowMaskCenter = FVector2D::ZeroVector;
	float GroundShadowMaskHalfExtent = 6000.0f;
	int32 BloodMaskSize = 1024;
	FVector2D BloodMaskCenter = FVector2D::ZeroVector;
	float BloodMaskHalfExtent = 12000.0f;
	bool bBloodMaskDirty = false;
	bool bSingleProxyComponent = true;
	float MaxSpeedScaleFinal = 0.16666667f;
	float MaxTurnRateScaleFinal = 0.41887903f;
	float PoseDeltaScaleFinal = 0.06666667f;
	int32 FutureWindow = 8;
	int32 PelvisBoneIndex = INDEX_NONE;
	int32 LeftFootBoneIndex = INDEX_NONE;
	int32 RightFootBoneIndex = INDEX_NONE;
	int32 LeftFootAnchorBoneIndex = INDEX_NONE;
	int32 RightFootAnchorBoneIndex = INDEX_NONE;
	float AccumulatedStepSeconds = 0.0f;
	bool bInitialized = false;
	bool bRanFinalSummary = false;
	bool bScreenshotRequested = false;
	double LastLiveVisualPollSeconds = 0.0;
	FDateTime LastLiveVisualConfigTimestamp = FDateTime::MinValue();
	int32 LiveVisualScreenshotIndex = 0;

	void ComputeFK(FProphecyNNPoseRuntime& Pose, const FVector3f& RootPos, const FProphecyNNMat3& RootRot) const
	{
		TArray<FProphecyNNMat3> GlobalRot;
		TArray<FVector3f> GlobalPos;
		GlobalRot.SetNum(BodyNames.Num());
		GlobalPos.SetNum(BodyNames.Num());
		Pose.CanonPos.SetNum(BodyNames.Num());

		const FProphecyNNMat3 PelvisRot = Rotation6DToMatrix(Pose.PelvisRot6);
		const FProphecyNNMat3 Heading = YawToRowMatrix(0.0f);

		for (int32 BoneIndex = 0; BoneIndex < BodyNames.Num(); ++BoneIndex)
		{
			const FProphecyNNMat3 LocalRot = BoneIndex == 0 ? PelvisRot : Rotation6DToMatrix(Pose.NonPelvisRot6[BoneIndex - 1]);
			const FVector3f LocalOffset = BoneIndex == 0 ? Pose.PelvisPos : LocalOffsets[BoneIndex];
			const int32 ParentIndex = Parents[BoneIndex];
			if (ParentIndex < 0)
			{
				GlobalRot[BoneIndex] = MatrixMultiply(LocalRot, RootRot);
				GlobalPos[BoneIndex] = TransformRowVector(LocalOffset, RootRot) + RootPos;
			}
			else
			{
				GlobalRot[BoneIndex] = MatrixMultiply(LocalRot, GlobalRot[ParentIndex]);
				GlobalPos[BoneIndex] = TransformRowVector(LocalOffset, GlobalRot[ParentIndex]) + GlobalPos[ParentIndex];
			}
		}

		for (int32 BoneIndex = 0; BoneIndex < BodyNames.Num(); ++BoneIndex)
		{
			Pose.CanonPos[BoneIndex] = TransformRowVector(GlobalPos[BoneIndex] - RootPos, Heading);
		}
	}
};

AProphecyNNCrowdBenchmarkActor::AProphecyNNCrowdBenchmarkActor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SceneRoot->SetMobility(EComponentMobility::Static);
	SetRootComponent(SceneRoot);

	Impl = new FImpl();
}

AProphecyNNCrowdBenchmarkActor::~AProphecyNNCrowdBenchmarkActor()
{
	delete Impl;
	Impl = nullptr;
}

void AProphecyNNCrowdBenchmarkActor::BeginPlay()
{
	Super::BeginPlay();

	ApplyCommandLineOverrides();
	if (bApplyBattleSimRenderProfile)
	{
		ApplyBattleSimRenderProfile();
	}
	if (GEngine)
	{
		GEngine->bSmoothFrameRate = false;
		GEngine->SetMaxFPS(0.0f);
	}
	if (IConsoleVariable* VSyncCVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync")))
	{
		VSyncCVar->Set(0, ECVF_SetByCode);
	}

	const bool bRunAgents = !bSceneryOnly;
	CrowdSize = bRunAgents ? FMath::Clamp(CrowdSize, 1, ProphecyBatchSize) : 0;
	NNUpdateHz = FMath::Max(1.0f, NNUpdateHz);

	if (bRunAgents && !InitializeSeedData())
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Prophecy NN benchmark seed initialization failed."));
		SetActorTickEnabled(false);
		return;
	}

	if (bRunAgents)
	{
		InitializeAgents();
	}

	if (bRunAgents && !InitializeNNE())
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Prophecy NN benchmark NNE initialization failed."));
		SetActorTickEnabled(false);
		return;
	}
	if (!bRunAgents)
	{
		Impl->Model.RuntimeUsed = TEXT("SceneryOnly");
	}

	if (bRunAgents && bSpawnVisuals)
	{
		if (VisualMode.StartsWith(TEXT("Instanced"), ESearchCase::IgnoreCase) ||
			VisualMode.Equals(TEXT("Proxy"), ESearchCase::IgnoreCase))
		{
			SpawnInstancedProxyComponents();
		}
		else if (VisualMode.Equals(TEXT("MetaHuman"), ESearchCase::IgnoreCase) ||
			VisualMode.Equals(TEXT("MetaHumanFull"), ESearchCase::IgnoreCase) ||
			VisualMode.Equals(TEXT("MetaHumanComparison"), ESearchCase::IgnoreCase))
		{
			SpawnMetaHumanActors();
		}
		else
		{
			SpawnVisualComponents();
		}
	}

	if (bSpawnVisuals || bSceneryOnly)
	{
		SetupBenchmarkView();
		if (bRunAgents && bSpawnContactShadows && IsShadowEnabled(ShadowMode) && (bSpawnGrass || bDebugShadowGeometry || IsFullDynamicShadowVariant(ContactShadowVariant)))
		{
			SpawnContactShadowComponents();
		}
		if (bSpawnGrass)
		{
			if (bHideGrassBladesOnly)
			{
				Impl->ActiveGrassRenderer = TEXT("HiddenBlades");
				UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Near grass blades hidden for diagnostic capture; distant grass hills remain visible."));
			}
			else if (GrassRenderer.Equals(TEXT("Niagara"), ESearchCase::IgnoreCase))
			{
				SpawnNiagaraGrassField();
			}
			else
			{
				SpawnGrassField();
			}
		}
	}

	if (bRunAgents)
	{
		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			PublishAgentPose(AgentIndex, FPlatformTime::Seconds());
		}
		UpdateVisualRoots();
	}

	Impl->Stats = FProphecyBenchmarkStats();
	Impl->bInitialized = true;
	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Prophecy NN benchmark started: profile=%s crowd=%d batch=%d rate=%.1fHz scenery_only=%d visuals=%d visual_mode=%s shadow_mode=%s real_shadow_budget=%d contact_shadow_variant=%s shadow_geometry_debug=%d grass=%d grass_renderer=%s grass_wind=%d grass_wind_diagnostic=%d trees=%d tree_count=%d center_tree_diagnostic=%d tree_wind=%d tree_wind_diagnostic=%d runtime=%s gpu=%d"),
		BenchmarkProfile.IsEmpty() ? TEXT("Custom") : *BenchmarkProfile,
		CrowdSize,
		ProphecyBatchSize,
		NNUpdateHz,
		bSceneryOnly ? 1 : 0,
		bSpawnVisuals ? 1 : 0,
		*VisualMode,
		*ShadowMode,
		RealShadowBudget,
		*ContactShadowVariant,
		bDebugShadowGeometry ? 1 : 0,
		bSpawnGrass ? 1 : 0,
		*Impl->ActiveGrassRenderer,
		bGrassWind ? 1 : 0,
		bGrassWindDiagnostic ? 1 : 0,
		bSpawnTrees ? 1 : 0,
		Impl->TreeInstanceCount,
		bCenterTreeDiagnostic ? 1 : 0,
		bTreeWind ? 1 : 0,
		bTreeWindDiagnostic ? 1 : 0,
		*Impl->Model.RuntimeUsed,
		Impl->Model.bUsingGpu ? 1 : 0);
}

void AProphecyNNCrowdBenchmarkActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (Impl)
	{
		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			FProphecyNNPoseStore::ClearAgentPose(AgentIndex);
		}
	}
	MetaHumanActors.Reset();
	MetaHumanBodyComponents.Reset();
	MetaHumanAgentIndices.Reset();
	MetaHumanWorldOffsets.Reset();
	MetaHumanActorTiers.Reset();
	Super::EndPlay(EndPlayReason);
}

void AProphecyNNCrowdBenchmarkActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!Impl->bInitialized)
	{
		return;
	}

	const double FrameStart = FPlatformTime::Seconds();
	if (bSceneryOnly)
	{
		Impl->Stats.SimSeconds += FPlatformTime::Seconds() - FrameStart;
		PollLiveVisualIteration();
		LogProgressIfNeeded(DeltaSeconds);
		return;
	}

	const float StepSeconds = 1.0f / NNUpdateHz;
	Impl->AccumulatedStepSeconds += DeltaSeconds;

	int32 StepsThisFrame = 0;
	while (Impl->AccumulatedStepSeconds >= StepSeconds && StepsThisFrame < 4)
	{
		StepSimulation(StepSeconds);
		Impl->AccumulatedStepSeconds -= StepSeconds;
		++StepsThisFrame;
	}
	if (StepsThisFrame == 4 && Impl->AccumulatedStepSeconds >= StepSeconds)
	{
		Impl->AccumulatedStepSeconds = FMath::Fmod(Impl->AccumulatedStepSeconds, StepSeconds);
	}

	const double VisualStart = FPlatformTime::Seconds();
	UpdateVisualRoots();
	Impl->Stats.VisualSeconds += FPlatformTime::Seconds() - VisualStart;

	Impl->Stats.SimSeconds += FPlatformTime::Seconds() - FrameStart;
	PollLiveVisualIteration();
	LogProgressIfNeeded(DeltaSeconds);
}

void AProphecyNNCrowdBenchmarkActor::ApplyCommandLineOverrides()
{
	const TCHAR* Cmd = FCommandLine::Get();
	FParse::Value(Cmd, TEXT("ProphecyNNProfile="), BenchmarkProfile);
	ApplyBenchmarkProfile();

	const bool bCrowdSpecified = FParse::Value(Cmd, TEXT("ProphecyNNCrowd="), CrowdSize);
	FParse::Value(Cmd, TEXT("ProphecyNNRate="), NNUpdateHz);
	FParse::Value(Cmd, TEXT("ProphecyNNBenchmarkSeconds="), BenchmarkSeconds);
	FParse::Value(Cmd, TEXT("ProphecyNNSeconds="), BenchmarkSeconds);
	FParse::Value(Cmd, TEXT("ProphecyNNWarmup="), WarmupSeconds);
	FParse::Value(Cmd, TEXT("ProphecyNNRuntime="), PreferredRuntime);
	FParse::Value(Cmd, TEXT("ProphecyNNVisualMode="), VisualMode);
	FParse::Value(Cmd, TEXT("ProphecyNNShadowMode="), ShadowMode);
	FParse::Value(Cmd, TEXT("ProphecyNNRealShadowBudget="), RealShadowBudget);
	bool bContactShadowVariantSpecified = false;
	bContactShadowVariantSpecified = FParse::Value(Cmd, TEXT("ProphecyNNContactShadowVariant="), ContactShadowVariant) || bContactShadowVariantSpecified;
	bContactShadowVariantSpecified = FParse::Value(Cmd, TEXT("ProphecyNNGrassShadowVariant="), ContactShadowVariant) || bContactShadowVariantSpecified;
	FParse::Value(Cmd, TEXT("ProphecyNNForcedLOD="), ForcedMeshLOD);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHuman="), MetaHumanBlueprintClassPath);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanLOD="), MetaHumanForcedLOD);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanForcedLOD="), MetaHumanForcedLOD);
	FParse::Value(Cmd, TEXT("ProphecyNNSkeletalTickHz="), SkeletalTickHz);
	FParse::Value(Cmd, TEXT("ProphecyNNOnnx="), OnnxModelPath);
	FParse::Value(Cmd, TEXT("ProphecyNNSeed="), RuntimeSeedPath);
	FParse::Value(Cmd, TEXT("ProphecyNNScreenshot="), ScreenshotPath);
	FParse::Value(Cmd, TEXT("ProphecyNNScreenshotSeconds="), ScreenshotSeconds);
	FParse::Value(Cmd, TEXT("ProphecyNNLiveConfig="), LiveVisualConfigPath);
	FParse::Value(Cmd, TEXT("ProphecyNNLivePoll="), LiveVisualPollSeconds);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassRenderer="), GrassRenderer);
	FParse::Value(Cmd, TEXT("ProphecyNNNiagaraSystem="), NiagaraGrassSystemPath);
	FParse::Value(Cmd, TEXT("ProphecyNNNiagaraComponents="), NiagaraGrassComponentCount);

	int32 VisualsValue = bSpawnVisuals ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNVisuals="), VisualsValue))
	{
		bSpawnVisuals = VisualsValue != 0;
	}

	int32 MetaHumanDriveBodyValue = bMetaHumanDriveBodyWithNNPose ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanDriveBody="), MetaHumanDriveBodyValue))
	{
		bMetaHumanDriveBodyWithNNPose = MetaHumanDriveBodyValue != 0;
	}
	int32 MetaHumanPreserveReferenceTranslationsValue = bMetaHumanPreserveReferenceBoneTranslations ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanPreserveRefTranslations="), MetaHumanPreserveReferenceTranslationsValue))
	{
		bMetaHumanPreserveReferenceBoneTranslations = MetaHumanPreserveReferenceTranslationsValue != 0;
	}
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanTier="), MetaHumanTier);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanTierComparisonList="), MetaHumanTierComparisonList);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanTierSpacingCm="), MetaHumanTierComparisonSpacingCm);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanClothingMode="), MetaHumanClothingMode);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanGroomMode="), MetaHumanGroomMode);
	FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanFaceMode="), MetaHumanFaceMode);
	int32 MetaHumanFreezeSkeletalTicksValue = bMetaHumanFreezeSkeletalTicks ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanFreezeSkeletalTicks="), MetaHumanFreezeSkeletalTicksValue))
	{
		bMetaHumanFreezeSkeletalTicks = MetaHumanFreezeSkeletalTicksValue != 0;
	}
	int32 MetaHumanTierComparisonValue = bMetaHumanTierComparison ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNMetaHumanTierComparison="), MetaHumanTierComparisonValue))
	{
		bMetaHumanTierComparison = MetaHumanTierComparisonValue != 0;
	}
	bMetaHumanTierComparison = bMetaHumanTierComparison || FParse::Param(Cmd, TEXT("ProphecyNNMetaHumanTierCompare"));

	int32 SceneryOnlyValue = bSceneryOnly ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNSceneryOnly="), SceneryOnlyValue))
	{
		bSceneryOnly = SceneryOnlyValue != 0;
	}
	int32 AgentsValue = bSceneryOnly ? 0 : 1;
	if (FParse::Value(Cmd, TEXT("ProphecyNNAgents="), AgentsValue))
	{
		bSceneryOnly = AgentsValue == 0;
	}
	if (bCrowdSpecified && CrowdSize <= 0)
	{
		bSceneryOnly = true;
	}
	int32 ClosePreviewCameraValue = bClosePreviewCamera ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNClosePreview="), ClosePreviewCameraValue))
	{
		bClosePreviewCamera = ClosePreviewCameraValue != 0;
	}

	int32 ShadowsValue = bCastShadows ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNShadows="), ShadowsValue))
	{
		bCastShadows = ShadowsValue != 0;
		if (ShadowMode.Equals(TEXT("None"), ESearchCase::IgnoreCase))
		{
			ShadowMode = bCastShadows ? TEXT("Full") : TEXT("None");
		}
	}

	int32 FloorValue = bSpawnBenchmarkFloor ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNFloor="), FloorValue))
	{
		bSpawnBenchmarkFloor = FloorValue != 0;
	}

	int32 LightsValue = bSpawnBenchmarkLights ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNLights="), LightsValue))
	{
		bSpawnBenchmarkLights = LightsValue != 0;
	}

	int32 RenderProfileValue = bApplyBattleSimRenderProfile ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNRenderProfile="), RenderProfileValue))
	{
		bApplyBattleSimRenderProfile = RenderProfileValue != 0;
	}

	int32 ContactShadowValue = bSpawnContactShadows ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNContactShadows="), ContactShadowValue))
	{
		bSpawnContactShadows = ContactShadowValue != 0;
	}

	int32 GrassValue = bSpawnGrass ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNGrass="), GrassValue))
	{
		bSpawnGrass = GrassValue != 0;
	}

	int32 ShadowDebugValue = bDebugShadowGeometry ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNShadowGeometryDebug="), ShadowDebugValue) ||
		FParse::Value(Cmd, TEXT("ProphecyNNShadowDebug="), ShadowDebugValue))
	{
		bDebugShadowGeometry = ShadowDebugValue != 0;
	}

	int32 GrassDiagnosticValue = bGrassDiagnosticMode ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNGrassDiagnostic="), GrassDiagnosticValue))
	{
		bGrassDiagnosticMode = GrassDiagnosticValue != 0;
	}
	int32 GrassWindValue = bGrassWind ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNGrassWind="), GrassWindValue))
	{
		bGrassWind = GrassWindValue != 0;
	}
	int32 GrassWindDiagnosticValue = bGrassWindDiagnostic ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNGrassWindDiagnostic="), GrassWindDiagnosticValue) ||
		FParse::Value(Cmd, TEXT("ProphecyNNWindDiagnostic="), GrassWindDiagnosticValue))
	{
		bGrassWindDiagnostic = GrassWindDiagnosticValue != 0;
		if (bGrassWindDiagnostic)
		{
			bGrassWind = true;
		}
	}
	FParse::Value(Cmd, TEXT("ProphecyNNGrassWindBendCm="), GrassWindBendCm);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassWindLiftCm="), GrassWindLiftCm);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassWindWorldFreq="), GrassWindWorldFrequency);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassWindPatchFreq="), GrassWindPatchFrequency);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassWindSpeed="), GrassWindSpeed);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassWindGust="), GrassWindGustStrength);
	int32 TreesValue = bSpawnTrees ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNTrees="), TreesValue) ||
		FParse::Value(Cmd, TEXT("ProphecyNNTreeField="), TreesValue))
	{
		bSpawnTrees = TreesValue != 0;
	}
	FParse::Value(Cmd, TEXT("ProphecyNNTreeSource="), TreeSource);
	FParse::Value(Cmd, TEXT("ProphecyNNTreeCount="), TreeInstanceCount);
	int32 TreeWindValue = bTreeWind ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNTreeWind="), TreeWindValue))
	{
		bTreeWind = TreeWindValue != 0;
	}
	int32 TreeWindDiagnosticValue = bTreeWindDiagnostic ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNTreeWindDiagnostic="), TreeWindDiagnosticValue))
	{
		bTreeWindDiagnostic = TreeWindDiagnosticValue != 0;
		if (bTreeWindDiagnostic)
		{
			bTreeWind = true;
		}
	}
	FParse::Value(Cmd, TEXT("ProphecyNNTreeWindBendCm="), TreeWindBendCm);
	FParse::Value(Cmd, TEXT("ProphecyNNTreeWindLiftCm="), TreeWindLiftCm);
	FParse::Value(Cmd, TEXT("ProphecyNNTreeWindWorldFreq="), TreeWindWorldFrequency);
	FParse::Value(Cmd, TEXT("ProphecyNNTreeWindSpeed="), TreeWindSpeed);
	FParse::Value(Cmd, TEXT("ProphecyNNTreeWindGust="), TreeWindGustStrength);
	int32 ShadowMaskDiagnosticValue = bShadowMaskDiagnostic ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNShadowMaskDiagnostic="), ShadowMaskDiagnosticValue))
	{
		bShadowMaskDiagnostic = ShadowMaskDiagnosticValue != 0;
	}
	int32 CenterTreeDiagnosticValue = bCenterTreeDiagnostic ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNCenterTrees="), CenterTreeDiagnosticValue) ||
		FParse::Value(Cmd, TEXT("ProphecyNNTreeShadowDiagnostic="), CenterTreeDiagnosticValue))
	{
		bCenterTreeDiagnostic = CenterTreeDiagnosticValue != 0;
		if (bCenterTreeDiagnostic)
		{
			bSpawnTrees = true;
		}
	}
	int32 HideGrassValue = bHideGrassForShadowInspection ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNHideGrass="), HideGrassValue) ||
		FParse::Value(Cmd, TEXT("ProphecyNNGrassHidden="), HideGrassValue))
	{
		bHideGrassForShadowInspection = HideGrassValue != 0;
	}
	int32 HideGrassBladesOnlyValue = bHideGrassBladesOnly ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNHideGrassBladesOnly="), HideGrassBladesOnlyValue) ||
		FParse::Value(Cmd, TEXT("ProphecyNNHideNearGrass="), HideGrassBladesOnlyValue))
	{
		bHideGrassBladesOnly = HideGrassBladesOnlyValue != 0;
	}

	int32 SingleProxyValue = Impl->bSingleProxyComponent ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNSingleProxy="), SingleProxyValue))
	{
		Impl->bSingleProxyComponent = SingleProxyValue != 0;
	}

	if (bSceneryOnly)
	{
		bSpawnVisuals = false;
	}

	bExitWhenDone = bExitWhenDone || FParse::Param(Cmd, TEXT("ProphecyNNBenchmarkExit"));
	int32 LiveVisualValue = bLiveVisualIteration ? 1 : 0;
	if (FParse::Value(Cmd, TEXT("ProphecyNNLiveVisual="), LiveVisualValue))
	{
		bLiveVisualIteration = LiveVisualValue != 0;
	}
	bLiveVisualIteration = bLiveVisualIteration || FParse::Param(Cmd, TEXT("ProphecyNNLiveVisual"));
	if (bLiveVisualIteration)
	{
		BenchmarkSeconds = 0.0f;
		bExitWhenDone = false;
	}
	if (bContactShadowVariantSpecified && !IsContactShadowVariantDisabled(ContactShadowVariant))
	{
		bSpawnContactShadows = true;
	}
	NormalizeShadowVariantSettings();
}

void AProphecyNNCrowdBenchmarkActor::ApplyBenchmarkProfile()
{
	if (BenchmarkProfile.IsEmpty())
	{
		return;
	}

	const bool bCharactersFloorShadows = BenchmarkProfile.Equals(TEXT("CharactersFloorShadows"), ESearchCase::IgnoreCase);
	const bool bGrassField = BenchmarkProfile.Equals(TEXT("GrassField"), ESearchCase::IgnoreCase);
	if (!bCharactersFloorShadows && !bGrassField)
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Unknown ProphecyNNProfile '%s'; using explicit command-line settings."), *BenchmarkProfile);
		return;
	}

	CrowdSize = 100;
	NNUpdateHz = 30.0f;
	bSpawnVisuals = true;
	bSpawnBenchmarkFloor = true;
	bSpawnBenchmarkLights = true;
	bCastShadows = true;
	bApplyBattleSimRenderProfile = true;
	ShadowMode = TEXT("Hybrid");
	RealShadowBudget = bGrassField ? 0 : 10;
	bSpawnContactShadows = true;
	ContactShadowVariant = TEXT("Root");
	bSpawnGrass = bGrassField;
	bSpawnTrees = bGrassField;
	GrassRenderer = TEXT("HISM");
	VisualMode = TEXT("Skeletal");
	ForcedMeshLOD = 3;
	SkeletalTickHz = 30.0f;
	PreferredRuntime = TEXT("NNERuntimeORTCpu");
	BenchmarkSeconds = 12.0f;
	WarmupSeconds = 3.0f;
}

void AProphecyNNCrowdBenchmarkActor::NormalizeShadowVariantSettings()
{
	ContactShadowVariant = CanonicalContactShadowVariant(ContactShadowVariant);
	if (IsContactShadowVariantDisabled(ContactShadowVariant))
	{
		bSpawnContactShadows = false;
		return;
	}

	if (bDebugShadowGeometry)
	{
		bSpawnGrass = false;
		bSpawnTrees = false;
		bSpawnContactShadows = true;
	}
	if (!bSpawnContactShadows)
	{
		return;
	}

	bSpawnContactShadows = true;
	bCastShadows = true;
	if (IsFullDynamicShadowVariant(ContactShadowVariant))
	{
		ShadowMode = TEXT("Full");
		RealShadowBudget = CrowdSize;
		return;
	}

	if (!IsShadowEnabled(ShadowMode))
	{
		ShadowMode = TEXT("Hybrid");
	}
}

void AProphecyNNCrowdBenchmarkActor::ApplyBattleSimRenderProfile()
{
	Impl->AppliedRenderSettings.Reset();
	SetBenchmarkCVar(TEXT("r.VSync"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.DynamicGlobalIlluminationMethod"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.ReflectionMethod"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Lumen.DiffuseIndirect.Allow"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Lumen.Reflections.Allow"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Shadow.Virtual.Enable"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Shadow.CSM.MaxCascades"), 1, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Shadow.MaxResolution"), 512, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Shadow.DistanceScale"), 0.35f, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Shadow.RadiusThreshold"), 0.06f, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.DistanceFieldShadowing"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.ContactShadows"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.AmbientOcclusionLevels"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.SSR.Quality"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.DefaultFeature.AutoExposure"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.EyeAdaptationQuality"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.Fog"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.SkyAtmosphere"), 1, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.VolumetricCloud"), 1, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.VolumetricCloud.ViewRaySampleMaxCount"), 96, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.MotionBlurQuality"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.BloomQuality"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.DepthOfFieldQuality"), 0, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.PostProcessAAQuality"), 2, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.AntiAliasingMethod"), 2, Impl->AppliedRenderSettings);
	SetBenchmarkCVar(TEXT("r.ScreenPercentage"), 100, Impl->AppliedRenderSettings);

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Applied battle-sim render profile: %s"), *Impl->AppliedRenderSettings);
}

bool AProphecyNNCrowdBenchmarkActor::InitializeSeedData()
{
	FString JsonText;
	const FString SeedPath = ResolveProjectPath(RuntimeSeedPath);
	if (!FFileHelper::LoadFileToString(JsonText, *SeedPath))
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Failed to read seed JSON: %s"), *SeedPath);
		return false;
	}

	TSharedPtr<FJsonObject> RootObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, RootObject) || !RootObject.IsValid())
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Failed to parse seed JSON: %s"), *SeedPath);
		return false;
	}

	if (!ReadNameArray(RootObject, TEXT("body_names"), Impl->BodyNames) ||
		!ReadIntArray(RootObject, TEXT("parents_body"), Impl->Parents) ||
		!ReadVec3Array(RootObject, TEXT("local_offsets_m"), Impl->LocalOffsets))
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Seed JSON is missing body names, parents, or offsets."));
		return false;
	}

	const TSharedPtr<FJsonObject>* PrevPoseObject = nullptr;
	const TSharedPtr<FJsonObject>* CurPoseObject = nullptr;
	if (!RootObject->TryGetObjectField(TEXT("prev_pose"), PrevPoseObject) ||
		!RootObject->TryGetObjectField(TEXT("cur_pose"), CurPoseObject) ||
		!ReadPose(*PrevPoseObject, Impl->SeedPrevPose) ||
		!ReadPose(*CurPoseObject, Impl->SeedCurPose))
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Seed JSON pose data is incomplete."));
		return false;
	}

	if (Impl->BodyNames.Num() != ProphecyBodyBoneCount ||
		Impl->Parents.Num() != ProphecyBodyBoneCount ||
		Impl->LocalOffsets.Num() != ProphecyBodyBoneCount ||
		Impl->SeedPrevPose.NonPelvisRot6.Num() != ProphecyNonPelvisBoneCount ||
		Impl->SeedCurPose.NonPelvisRot6.Num() != ProphecyNonPelvisBoneCount)
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Seed JSON dimensions do not match the exported Stepper model."));
		return false;
	}

	RootObject->TryGetNumberField(TEXT("max_speed_scale_final"), Impl->MaxSpeedScaleFinal);
	RootObject->TryGetNumberField(TEXT("max_turn_rate_scale_final"), Impl->MaxTurnRateScaleFinal);
	RootObject->TryGetNumberField(TEXT("pose_delta_scale_final"), Impl->PoseDeltaScaleFinal);
	RootObject->TryGetNumberField(TEXT("future_window"), Impl->FutureWindow);

	Impl->SeedRootRot = FProphecyNNMat3();
	ReadMat3(RootObject, TEXT("root_rot0"), Impl->SeedRootRot);
	Impl->PublishedBoneNames.Reset(Impl->BodyNames.Num() + 1);
	Impl->PublishedBoneNames.Add(TEXT("root"));
	Impl->PublishedBoneNames.Append(Impl->BodyNames);
	Impl->PelvisBoneIndex = Impl->BodyNames.Find(TEXT("pelvis"));
	Impl->LeftFootBoneIndex = Impl->BodyNames.Find(TEXT("foot_l"));
	Impl->RightFootBoneIndex = Impl->BodyNames.Find(TEXT("foot_r"));
	Impl->LeftFootAnchorBoneIndex = Impl->BodyNames.Find(TEXT("ball_l"));
	if (Impl->LeftFootAnchorBoneIndex == INDEX_NONE)
	{
		Impl->LeftFootAnchorBoneIndex = Impl->LeftFootBoneIndex;
	}
	Impl->RightFootAnchorBoneIndex = Impl->BodyNames.Find(TEXT("ball_r"));
	if (Impl->RightFootAnchorBoneIndex == INDEX_NONE)
	{
		Impl->RightFootAnchorBoneIndex = Impl->RightFootBoneIndex;
	}

	Impl->ComputeFK(Impl->SeedPrevPose, FVector3f::ZeroVector, Impl->SeedRootRot);
	Impl->ComputeFK(Impl->SeedCurPose, FVector3f::ZeroVector, Impl->SeedRootRot);
	return true;
}

bool AProphecyNNCrowdBenchmarkActor::InitializeNNE()
{
	FModuleManager::Get().LoadModule(TEXT("NNERuntimeORT"));

	TArray64<uint8> OnnxBytes;
	const FString ModelPath = ResolveProjectPath(OnnxModelPath);
	if (!FFileHelper::LoadFileToArray(OnnxBytes, *ModelPath))
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Failed to read ONNX model: %s"), *ModelPath);
		return false;
	}

	ModelData = NewObject<UNNEModelData>(this);
	ModelData->Init(TEXT("onnx"), TConstArrayView64<uint8>(OnnxBytes.GetData(), OnnxBytes.Num()));

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Registered NNE runtimes: %s"), *FString::Join(UE::NNE::GetAllRuntimeNames(), TEXT(", ")));

	const FString Requested = PreferredRuntime.TrimStartAndEnd();
	if (Requested.Equals(TEXT("cpu"), ESearchCase::IgnoreCase) || Requested.Equals(TEXT("NNERuntimeORTCpu"), ESearchCase::IgnoreCase))
	{
		return TryCreateCpuModel(TEXT("NNERuntimeORTCpu"));
	}

	if (Requested.Equals(TEXT("gpu"), ESearchCase::IgnoreCase) || Requested.Equals(TEXT("dml"), ESearchCase::IgnoreCase) || Requested.Equals(TEXT("NNERuntimeORTDml"), ESearchCase::IgnoreCase))
	{
		if (TryCreateGpuModel(TEXT("NNERuntimeORTDml")))
		{
			return true;
		}
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Falling back from DirectML to CPU."));
		return TryCreateCpuModel(TEXT("NNERuntimeORTCpu"));
	}

	if (TryCreateGpuModel(Requested) || TryCreateCpuModel(Requested))
	{
		return true;
	}

	return TryCreateGpuModel(TEXT("NNERuntimeORTDml")) || TryCreateCpuModel(TEXT("NNERuntimeORTCpu"));
}

bool AProphecyNNCrowdBenchmarkActor::TryCreateGpuModel(const FString& RuntimeName)
{
	return Impl->Model.CreateGpu(ModelData, RuntimeName);
}

bool AProphecyNNCrowdBenchmarkActor::TryCreateCpuModel(const FString& RuntimeName)
{
	return Impl->Model.CreateCpu(ModelData, RuntimeName);
}

void AProphecyNNCrowdBenchmarkActor::InitializeAgents()
{
	Impl->Agents.Reset(ProphecyBatchSize);
	Impl->Agents.SetNum(ProphecyBatchSize);
	Impl->InputBuffer.SetNumZeroed(ProphecyBatchSize * ProphecyInputDim);
	Impl->OutputBuffer.SetNumZeroed(ProphecyBatchSize * ProphecyOutputDim);
	Impl->ScratchTransforms.SetNum(ProphecyBodyBoneCount);

	const int32 GridSide = FMath::Max(1, FMath::CeilToInt(FMath::Sqrt(float(FMath::Max(1, CrowdSize)))));
	const float SpacingMeters = 1.8f;
	const float StepSeconds = 1.0f / FMath::Max(1.0f, NNUpdateHz);

	for (int32 AgentIndex = 0; AgentIndex < ProphecyBatchSize; ++AgentIndex)
	{
		FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
		Agent.PrevPose = Impl->SeedPrevPose;
		Agent.CurPose = Impl->SeedCurPose;
		Agent.LocalTransforms.SetNum(ProphecyBodyBoneCount + 1);

		const int32 Row = AgentIndex / GridSide;
		const int32 Col = AgentIndex % GridSide;
		const FVector3f StartRoot((float(Col) - float(GridSide - 1) * 0.5f) * SpacingMeters, 0.0f, float(Row) * SpacingMeters);
		Agent.CurRootPos = StartRoot;
		Agent.PrevRootPos = StartRoot - FVector3f(0.0f, 0.0f, Agent.SpeedMetersPerSecond * StepSeconds);
		Agent.CurRootYaw = 0.0f;
		Agent.PrevRootYaw = 0.0f;
		Agent.SpeedMetersPerSecond = 1.35f + 0.25f * float(AgentIndex % 5) / 4.0f;
		Agent.YawRateRadiansPerSecond = 0.0f;

		Impl->ComputeFK(Agent.PrevPose, Agent.PrevRootPos, Impl->SeedRootRot);
		Impl->ComputeFK(Agent.CurPose, Agent.CurRootPos, Impl->SeedRootRot);
	}
}

void AProphecyNNCrowdBenchmarkActor::SpawnVisualComponents()
{
	BenchmarkMesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/UEFN_Mannequin/Meshes/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
	if (!BenchmarkMesh)
	{
		BenchmarkMesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/UE5_Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
	}
	if (!BenchmarkMesh)
	{
		BenchmarkMesh = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/Characters/UE5_Mannequins/Meshes/SKM_Manny.SKM_Manny"));
	}
	if (!BenchmarkMesh)
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Could not load Manny mesh; continuing model-only."));
		bSpawnVisuals = false;
		return;
	}

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Benchmark mesh %s has %d LODs; forced LOD=%d skeletal_tick_hz=%.1f"),
		*BenchmarkMesh->GetName(),
		BenchmarkMesh->GetLODNum(),
		ForcedMeshLOD,
		SkeletalTickHz);

	MeshComponents.Reset(CrowdSize);
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		USkeletalMeshComponent* Component = NewObject<USkeletalMeshComponent>(this);
		Component->SetSkeletalMesh(BenchmarkMesh);
		Component->SetAnimInstanceClass(UProphecyNNPoseAnimInstance::StaticClass());
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCastShadow(bCastShadows && ShouldAgentCastRealShadow(ShadowMode, RealShadowBudget, AgentIndex));
		Component->SetCastContactShadow(false);
		Component->SetCastInsetShadow(false);
		Component->SetAffectDistanceFieldLighting(false);
		Component->SetAffectDynamicIndirectLighting(false);
		Component->SetVisibleInRayTracing(false);
		Component->SetReceivesDecals(false);
		Component->SetForcedLOD(FMath::Max(0, ForcedMeshLOD));
		Component->SetDisablePostProcessBlueprint(true);
		Component->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		Component->bEnableUpdateRateOptimizations = true;
		Component->bComponentUseFixedSkelBounds = true;
		if (SkeletalTickHz > 0.0f)
		{
			Component->SetComponentTickInterval(1.0f / SkeletalTickHz);
		}
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(Component);
		Component->RegisterComponent();

		if (UProphecyNNPoseAnimInstance* PoseInstance = Cast<UProphecyNNPoseAnimInstance>(Component->GetAnimInstance()))
		{
			PoseInstance->AgentId = AgentIndex;
			PoseInstance->bUseStoredPose = true;
			PoseInstance->bEnableDebugMotion = false;
		}

		MeshComponents.Add(Component);
	}
}

void AProphecyNNCrowdBenchmarkActor::SpawnMetaHumanActors()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		bSpawnVisuals = false;
		return;
	}

	UClass* MetaHumanClass = LoadClass<AActor>(nullptr, *MetaHumanBlueprintClassPath);
	if (!MetaHumanClass && !MetaHumanBlueprintClassPath.Contains(TEXT(".")))
	{
		const FString ObjectName = FPackageName::GetShortName(MetaHumanBlueprintClassPath);
		const FString GeneratedClassPath = FString::Printf(TEXT("%s.%s_C"), *MetaHumanBlueprintClassPath, *ObjectName);
		MetaHumanClass = LoadClass<AActor>(nullptr, *GeneratedClassPath);
	}
	if (!MetaHumanClass)
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Could not load MetaHuman blueprint class '%s'; continuing model-only."), *MetaHumanBlueprintClassPath);
		bSpawnVisuals = false;
		return;
	}

	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	auto CanonicalTierName = [](const FString& InTier)
	{
		const FString Tier = InTier.TrimStartAndEnd();
		if (Tier.Equals(TEXT("Full"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Full"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Tier1"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("T1"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Near"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Production"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Full"));
		}
		if (Tier.Equals(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Tier2"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("T2"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Medium"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Gameplay"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Mid"));
		}
		if (Tier.Equals(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Tier3"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("T3"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Distant"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Distant"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Distance"), ESearchCase::IgnoreCase) ||
			Tier.Equals(TEXT("Proxy"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Far"));
		}
		return Tier.IsEmpty() ? FString(TEXT("Full")) : Tier;
	};

	auto IsMetaHumanGroomComponent = [](const UPrimitiveComponent* Component)
	{
		if (!Component)
		{
			return false;
		}

		const FString ComponentName = Component->GetName();
		const FString ClassName = Component->GetClass() ? Component->GetClass()->GetName() : FString();
		return ClassName.Contains(TEXT("Groom")) ||
			ComponentName.Equals(TEXT("Hair"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Eyebrows"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Fuzz"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Eyelashes"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Mustache"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Beard"), ESearchCase::IgnoreCase);
	};

	auto IsTinyMetaHumanGroomComponent = [](const UPrimitiveComponent* Component)
	{
		if (!Component)
		{
			return false;
		}

		const FString ComponentName = Component->GetName();
		return ComponentName.Equals(TEXT("Fuzz"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Eyelashes"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Mustache"), ESearchCase::IgnoreCase) ||
			ComponentName.Equals(TEXT("Beard"), ESearchCase::IgnoreCase);
	};

	auto IsFarTierName = [](const FString& Tier)
	{
		return Tier.Equals(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Tier3"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Distant"), ESearchCase::IgnoreCase);
	};

	auto IsMidTierName = [](const FString& Tier)
	{
		return Tier.Equals(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Tier2"), ESearchCase::IgnoreCase);
	};

	auto ResolveTierForcedLOD = [this](const FString& Tier)
	{
		if (MetaHumanForcedLOD >= 0)
		{
			return MetaHumanForcedLOD;
		}
		if (Tier.Equals(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Tier3"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Distant"), ESearchCase::IgnoreCase))
		{
			return 3;
		}
		if (Tier.Equals(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Tier2"), ESearchCase::IgnoreCase))
		{
			return 1;
		}
		return -1;
	};

	auto ResolveTierTickHz = [this](const FString& Tier)
	{
		if (SkeletalTickHz <= 0.0f)
		{
			return SkeletalTickHz;
		}
		if (Tier.Equals(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Far"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Tier3"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Distant"), ESearchCase::IgnoreCase))
		{
			return FMath::Min(SkeletalTickHz, 15.0f);
		}
		if (Tier.Equals(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.StartsWith(TEXT("Mid"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("Tier2"), ESearchCase::IgnoreCase))
		{
			return FMath::Min(SkeletalTickHz, 24.0f);
		}
		return SkeletalTickHz;
	};

	auto ResolveTierClothingMode = [this, IsFarTierName](const FString& Tier)
	{
		const FString RequestedMode = MetaHumanClothingMode.TrimStartAndEnd();
		if (!RequestedMode.IsEmpty() &&
			!RequestedMode.Equals(TEXT("TierDefault"), ESearchCase::IgnoreCase) &&
			!RequestedMode.Equals(TEXT("Default"), ESearchCase::IgnoreCase))
		{
			return RequestedMode;
		}
		return IsFarTierName(Tier) ? FString(TEXT("Following")) : FString(TEXT("Native"));
	};

	auto ResolveTierGroomMode = [this, IsFarTierName, IsMidTierName](const FString& Tier)
	{
		const FString RequestedMode = MetaHumanGroomMode.TrimStartAndEnd();
		if (!RequestedMode.IsEmpty() &&
			!RequestedMode.Equals(TEXT("TierDefault"), ESearchCase::IgnoreCase) &&
			!RequestedMode.Equals(TEXT("Default"), ESearchCase::IgnoreCase))
		{
			return RequestedMode;
		}
		if (Tier.Contains(TEXT("NoGroom"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("NoHair"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Hidden"));
		}
		if (IsFarTierName(Tier))
		{
			return FString(TEXT("Hidden"));
		}
		if (IsMidTierName(Tier))
		{
			return FString(TEXT("TinyHidden"));
		}
		return FString(TEXT("Native"));
	};

	auto ResolveTierFaceMode = [this](const FString& Tier)
	{
		if (Tier.Contains(TEXT("FaceStatic"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("StaticFace"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Static"));
		}
		if (Tier.Contains(TEXT("FaceLeader"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("LeaderFace"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Leader"));
		}
		if (Tier.Contains(TEXT("FaceNative"), ESearchCase::IgnoreCase) ||
			Tier.Contains(TEXT("NativeFace"), ESearchCase::IgnoreCase))
		{
			return FString(TEXT("Native"));
		}

		const FString RequestedMode = MetaHumanFaceMode.TrimStartAndEnd();
		if (!RequestedMode.IsEmpty() &&
			!RequestedMode.Equals(TEXT("TierDefault"), ESearchCase::IgnoreCase) &&
			!RequestedMode.Equals(TEXT("Default"), ESearchCase::IgnoreCase))
		{
			return RequestedMode;
		}
		return FString(TEXT("Native"));
	};

	const bool bTierComparison = bMetaHumanTierComparison || VisualMode.Equals(TEXT("MetaHumanComparison"), ESearchCase::IgnoreCase);
	TArray<FString> RequestedTiers;
	if (bTierComparison)
	{
		FString TierList = MetaHumanTierComparisonList;
		TierList.ReplaceInline(TEXT("+"), TEXT(","));
		TierList.ReplaceInline(TEXT("|"), TEXT(","));
		TierList.ReplaceInline(TEXT(";"), TEXT(","));
		TierList.ParseIntoArray(RequestedTiers, TEXT(","), true);
		if (RequestedTiers.Num() == 0)
		{
			RequestedTiers = { TEXT("Full"), TEXT("Mid"), TEXT("Far") };
		}
	}
	else
	{
		RequestedTiers.SetNum(CrowdSize);
		for (FString& Tier : RequestedTiers)
		{
			Tier = MetaHumanTier;
		}
	}

	TArray<FString> SpawnTiers;
	SpawnTiers.Reserve(RequestedTiers.Num());
	for (const FString& Tier : RequestedTiers)
	{
		SpawnTiers.Add(CanonicalTierName(Tier));
	}

	const int32 VisualCount = SpawnTiers.Num();
	FString TierSummary = FString::Join(SpawnTiers, TEXT(","));
	int32 SpawnedCount = 0;
	int32 BodyDrivenCount = 0;
	int32 NativeClothingComponentCount = 0;
	int32 LeaderPoseClothingComponentCount = 0;
	int32 HiddenClothingComponentCount = 0;
	int32 LeaderPoseFaceComponentCount = 0;
	int32 StaticFaceComponentCount = 0;
	int32 HiddenFaceComponentCount = 0;
	int32 SkeletalComponentCount = 0;
	int32 FrozenSkeletalComponentCount = 0;
	int32 PrimitiveComponentCount = 0;
	int32 HiddenPrimitiveComponentCount = 0;

	MetaHumanActors.Reset(VisualCount);
	MetaHumanBodyComponents.Reset(VisualCount);
	MetaHumanAgentIndices.Reset(VisualCount);
	MetaHumanWorldOffsets.Reset(VisualCount);
	MetaHumanActorTiers.Reset(VisualCount);
	for (int32 VisualIndex = 0; VisualIndex < VisualCount; ++VisualIndex)
	{
		const int32 SourceAgentIndex = bTierComparison ? 0 : VisualIndex;
		if (!Impl->Agents.IsValidIndex(SourceAgentIndex))
		{
			continue;
		}

		const FString& Tier = SpawnTiers[VisualIndex];
		const bool bMidTier = IsMidTierName(Tier);
		const bool bFarTier = IsFarTierName(Tier);
		const FString ClothingMode = ResolveTierClothingMode(Tier);
		const bool bUseLeaderPoseClothing = ClothingMode.Equals(TEXT("Following"), ESearchCase::IgnoreCase) ||
			ClothingMode.Equals(TEXT("Follow"), ESearchCase::IgnoreCase) ||
			ClothingMode.Equals(TEXT("Leader"), ESearchCase::IgnoreCase);
		const bool bHideTierClothing = ClothingMode.Equals(TEXT("Hidden"), ESearchCase::IgnoreCase);
		const FString GroomMode = ResolveTierGroomMode(Tier);
		const bool bHideAllGrooms = GroomMode.Equals(TEXT("Hidden"), ESearchCase::IgnoreCase) ||
			GroomMode.Equals(TEXT("AllHidden"), ESearchCase::IgnoreCase) ||
			GroomMode.Equals(TEXT("None"), ESearchCase::IgnoreCase);
		const bool bHideTinyGrooms = bHideAllGrooms ||
			GroomMode.Equals(TEXT("TinyHidden"), ESearchCase::IgnoreCase) ||
			GroomMode.Equals(TEXT("SmallHidden"), ESearchCase::IgnoreCase);
		const FString FaceMode = ResolveTierFaceMode(Tier);
		const bool bUseLeaderPoseFace = FaceMode.Equals(TEXT("Leader"), ESearchCase::IgnoreCase);
		const bool bUseStaticFace = FaceMode.Equals(TEXT("Static"), ESearchCase::IgnoreCase);
		const bool bHideTierFace = FaceMode.Equals(TEXT("Hidden"), ESearchCase::IgnoreCase);
		const int32 TierForcedLOD = ResolveTierForcedLOD(Tier);
		const int32 SkeletalForcedLOD = TierForcedLOD >= 0 ? TierForcedLOD + 1 : 0;
		const float TierTickHz = ResolveTierTickHz(Tier);
		const float ComparisonCenter = 0.5f * float(FMath::Max(0, VisualCount - 1));
		const FVector TierOffset = bTierComparison
			? FVector((float(VisualIndex) - ComparisonCenter) * FMath::Max(120.0f, MetaHumanTierComparisonSpacingCm), 0.0f, 0.0f)
			: FVector::ZeroVector;

		const FProphecyNNAgentRuntime& Agent = Impl->Agents[SourceAgentIndex];
		const FVector Location = TrainingWorldToUnrealVector(Agent.CurRootPos) + TierOffset;
		const FRotator Rotation(0.0, FMath::RadiansToDegrees(double(Agent.CurRootYaw)), 0.0);
		AActor* MetaHumanActor = World->SpawnActor<AActor>(MetaHumanClass, Location, Rotation, Params);
		if (!MetaHumanActor)
		{
			MetaHumanActors.Add(nullptr);
			MetaHumanBodyComponents.Add(nullptr);
			MetaHumanAgentIndices.Add(SourceAgentIndex);
			MetaHumanWorldOffsets.Add(TierOffset);
			MetaHumanActorTiers.Add(Tier);
			continue;
		}

		MetaHumanActor->SetActorEnableCollision(false);

		TArray<UPrimitiveComponent*> PrimitiveComponents;
		MetaHumanActor->GetComponents(PrimitiveComponents);
		for (UPrimitiveComponent* PrimitiveComponent : PrimitiveComponents)
		{
			if (!PrimitiveComponent)
			{
				continue;
			}

			PrimitiveComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			PrimitiveComponent->SetGenerateOverlapEvents(false);
			const bool bHidePrimitive = (bHideAllGrooms && IsMetaHumanGroomComponent(PrimitiveComponent)) ||
				(bHideTinyGrooms && IsTinyMetaHumanGroomComponent(PrimitiveComponent));
			if (bHidePrimitive)
			{
				PrimitiveComponent->SetVisibility(false, true);
				PrimitiveComponent->SetHiddenInGame(true, true);
				PrimitiveComponent->SetCastShadow(false);
				PrimitiveComponent->Deactivate();
				++HiddenPrimitiveComponentCount;
			}
			else
			{
				PrimitiveComponent->SetCastShadow(!bFarTier && bCastShadows && ShouldAgentCastRealShadow(ShadowMode, RealShadowBudget, VisualIndex));
			}
			PrimitiveComponent->SetCastContactShadow(false);
			PrimitiveComponent->SetCastInsetShadow(false);
			PrimitiveComponent->SetAffectDistanceFieldLighting(false);
			PrimitiveComponent->SetAffectDynamicIndirectLighting(false);
			PrimitiveComponent->SetVisibleInRayTracing(false);
			PrimitiveComponent->SetReceivesDecals(false);
			++PrimitiveComponentCount;
		}

		USkeletalMeshComponent* BodyComponent = nullptr;
		USkeletalMeshComponent* FaceComponent = nullptr;
		TArray<USkeletalMeshComponent*> ClothingComponents;
		TArray<USkeletalMeshComponent*> SkeletalComponents;
		MetaHumanActor->GetComponents(SkeletalComponents);
		for (USkeletalMeshComponent* SkeletalComponent : SkeletalComponents)
		{
			if (!SkeletalComponent)
			{
				continue;
			}

			SkeletalComponent->SetForcedLOD(SkeletalForcedLOD);
			SkeletalComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			SkeletalComponent->bEnableUpdateRateOptimizations = true;
			SkeletalComponent->bComponentUseFixedSkelBounds = true;
			if (TierTickHz > 0.0f)
			{
				SkeletalComponent->SetComponentTickInterval(1.0f / TierTickHz);
			}

			const FName ComponentName = SkeletalComponent->GetFName();
			if (ComponentName == FName(TEXT("Body")))
			{
				BodyComponent = SkeletalComponent;
			}
			else if (ComponentName == FName(TEXT("Face")))
			{
				FaceComponent = SkeletalComponent;
			}
			else if (ComponentName == FName(TEXT("Torso")) || ComponentName == FName(TEXT("Legs")) || ComponentName == FName(TEXT("Feet")))
			{
				ClothingComponents.Add(SkeletalComponent);
				++NativeClothingComponentCount;
			}
			++SkeletalComponentCount;
		}

		if (BodyComponent && bMetaHumanDriveBodyWithNNPose)
		{
			BodyComponent->SetAnimInstanceClass(UProphecyNNPoseAnimInstance::StaticClass());
			BodyComponent->SetDisablePostProcessBlueprint(true);
			BodyComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
			if (UProphecyNNPoseAnimInstance* PoseInstance = Cast<UProphecyNNPoseAnimInstance>(BodyComponent->GetAnimInstance()))
			{
				PoseInstance->AgentId = SourceAgentIndex;
				PoseInstance->bUseStoredPose = true;
				PoseInstance->bPreserveReferenceBoneTranslations = bMetaHumanPreserveReferenceBoneTranslations;
				PoseInstance->bEnableDebugMotion = false;
				++BodyDrivenCount;
			}
		}

		if (BodyComponent)
		{
			if (FaceComponent)
			{
				if (bHideTierFace)
				{
					FaceComponent->SetVisibility(false, true);
					FaceComponent->SetHiddenInGame(true, true);
					FaceComponent->SetCastShadow(false);
					FaceComponent->Deactivate();
					++HiddenFaceComponentCount;
				}
				else if (bUseLeaderPoseFace)
				{
					FaceComponent->SetLeaderPoseComponent(BodyComponent, true, false);
					FaceComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
					FaceComponent->bEnableUpdateRateOptimizations = true;
					++LeaderPoseFaceComponentCount;
				}
				else if (bUseStaticFace)
				{
					FaceComponent->bPauseAnims = true;
					FaceComponent->SetComponentTickEnabled(false);
					FaceComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
					FaceComponent->bEnableUpdateRateOptimizations = true;
					++StaticFaceComponentCount;
				}
			}

			for (USkeletalMeshComponent* ClothingComponent : ClothingComponents)
			{
				if (!ClothingComponent)
				{
					continue;
				}
				if (bHideTierClothing)
				{
					ClothingComponent->SetVisibility(false, true);
					ClothingComponent->SetHiddenInGame(true, true);
					ClothingComponent->SetCastShadow(false);
					ClothingComponent->Deactivate();
					++HiddenClothingComponentCount;
				}
				else if (bUseLeaderPoseClothing)
				{
					ClothingComponent->SetLeaderPoseComponent(BodyComponent, true, false);
					ClothingComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
					ClothingComponent->bEnableUpdateRateOptimizations = true;
					++LeaderPoseClothingComponentCount;
				}
			}
		}

		if (bMetaHumanFreezeSkeletalTicks)
		{
			for (USkeletalMeshComponent* SkeletalComponent : SkeletalComponents)
			{
				if (!SkeletalComponent)
				{
					continue;
				}

				SkeletalComponent->bPauseAnims = true;
				SkeletalComponent->SetComponentTickEnabled(false);
				SkeletalComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
				++FrozenSkeletalComponentCount;
			}
		}

		TArray<ULODSyncComponent*> LODSyncComponents;
		MetaHumanActor->GetComponents(LODSyncComponents);
		for (ULODSyncComponent* LODSyncComponent : LODSyncComponents)
		{
			if (!LODSyncComponent)
			{
				continue;
			}

			LODSyncComponent->ForcedLOD = TierForcedLOD;
			LODSyncComponent->RefreshSyncComponents();
			LODSyncComponent->UpdateLOD();
		}

		MetaHumanActors.Add(MetaHumanActor);
		MetaHumanBodyComponents.Add(BodyComponent);
		MetaHumanAgentIndices.Add(SourceAgentIndex);
		MetaHumanWorldOffsets.Add(TierOffset);
		MetaHumanActorTiers.Add(Tier);
		++SpawnedCount;
	}

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Spawned MetaHuman visuals: class=%s actors=%d tiers=%s comparison=%d body_nn_driven=%d preserve_ref_translations=%d native_clothing_components=%d following_clothing_components=%d hidden_clothing_components=%d leader_pose_face_components=%d static_face_components=%d hidden_face_components=%d skeletal_components=%d frozen_skeletal_components=%d primitive_components=%d hidden_primitive_components=%d global_metahuman_lod=%d skeletal_tick_hz=%.1f"),
		*MetaHumanClass->GetPathName(),
		SpawnedCount,
		*TierSummary,
		bTierComparison ? 1 : 0,
		BodyDrivenCount,
		bMetaHumanPreserveReferenceBoneTranslations ? 1 : 0,
		NativeClothingComponentCount,
		LeaderPoseClothingComponentCount,
		HiddenClothingComponentCount,
		LeaderPoseFaceComponentCount,
		StaticFaceComponentCount,
		HiddenFaceComponentCount,
		SkeletalComponentCount,
		FrozenSkeletalComponentCount,
		PrimitiveComponentCount,
		HiddenPrimitiveComponentCount,
		MetaHumanForcedLOD,
		SkeletalTickHz);
}

void AProphecyNNCrowdBenchmarkActor::SpawnInstancedProxyComponents()
{
	UStaticMesh* SegmentMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (!SegmentMesh)
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Could not load cube mesh for instanced proxy visuals; continuing model-only."));
		bSpawnVisuals = false;
		return;
	}

	UMaterialInterface* BrightMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));

	Impl->ProxySegments.Reset();
	auto AddSegmentByName = [this](const TCHAR* ParentName, const TCHAR* ChildName)
	{
		const int32 ParentIndex = Impl->BodyNames.Find(FName(ParentName));
		const int32 ChildIndex = Impl->BodyNames.Find(FName(ChildName));
		if (ParentIndex != INDEX_NONE && ChildIndex != INDEX_NONE)
		{
			Impl->ProxySegments.Add(FIntPoint(ParentIndex, ChildIndex));
		}
	};

	if (VisualMode.Equals(TEXT("InstancedFull"), ESearchCase::IgnoreCase))
	{
		for (int32 BoneIndex = 0; BoneIndex < Impl->Parents.Num(); ++BoneIndex)
		{
			if (Impl->Parents[BoneIndex] >= 0)
			{
				Impl->ProxySegments.Add(FIntPoint(Impl->Parents[BoneIndex], BoneIndex));
			}
		}
	}
	else if (VisualMode.Equals(TEXT("InstancedLite"), ESearchCase::IgnoreCase))
	{
		AddSegmentByName(TEXT("pelvis"), TEXT("spine_05"));
		AddSegmentByName(TEXT("spine_05"), TEXT("head"));
		AddSegmentByName(TEXT("spine_05"), TEXT("hand_l"));
		AddSegmentByName(TEXT("spine_05"), TEXT("hand_r"));
		AddSegmentByName(TEXT("pelvis"), TEXT("foot_l"));
		AddSegmentByName(TEXT("pelvis"), TEXT("foot_r"));
	}
	else
	{
		AddSegmentByName(TEXT("pelvis"), TEXT("spine_05"));
		AddSegmentByName(TEXT("spine_05"), TEXT("head"));
		AddSegmentByName(TEXT("spine_05"), TEXT("upperarm_l"));
		AddSegmentByName(TEXT("upperarm_l"), TEXT("lowerarm_l"));
		AddSegmentByName(TEXT("lowerarm_l"), TEXT("hand_l"));
		AddSegmentByName(TEXT("spine_05"), TEXT("upperarm_r"));
		AddSegmentByName(TEXT("upperarm_r"), TEXT("lowerarm_r"));
		AddSegmentByName(TEXT("lowerarm_r"), TEXT("hand_r"));
		AddSegmentByName(TEXT("pelvis"), TEXT("thigh_l"));
		AddSegmentByName(TEXT("thigh_l"), TEXT("calf_l"));
		AddSegmentByName(TEXT("calf_l"), TEXT("foot_l"));
		AddSegmentByName(TEXT("pelvis"), TEXT("thigh_r"));
		AddSegmentByName(TEXT("thigh_r"), TEXT("calf_r"));
		AddSegmentByName(TEXT("calf_r"), TEXT("foot_r"));
	}

	ProxySegmentComponents.Reset(Impl->bSingleProxyComponent ? 1 : Impl->ProxySegments.Num());
	const int32 ComponentCount = Impl->bSingleProxyComponent ? 1 : Impl->ProxySegments.Num();
	for (int32 ComponentIndex = 0; ComponentIndex < ComponentCount; ++ComponentIndex)
	{
		UInstancedStaticMeshComponent* Component = NewObject<UInstancedStaticMeshComponent>(this);
		Component->SetStaticMesh(SegmentMesh);
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCastShadow(bCastShadows);
		Component->SetCastContactShadow(false);
		Component->SetCastInsetShadow(false);
		Component->SetAffectDistanceFieldLighting(false);
		Component->SetAffectDynamicIndirectLighting(false);
		Component->SetVisibleInRayTracing(false);
		Component->SetReceivesDecals(false);
		Component->SetMobility(EComponentMobility::Movable);
		if (BrightMaterial)
		{
			Component->SetMaterial(0, BrightMaterial);
		}
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(Component);
		Component->RegisterComponent();

		const int32 InstanceCount = Impl->bSingleProxyComponent ? Impl->ProxySegments.Num() * CrowdSize : CrowdSize;
		for (int32 InstanceIndex = 0; InstanceIndex < InstanceCount; ++InstanceIndex)
		{
			Component->AddInstance(FTransform::Identity);
		}

		ProxySegmentComponents.Add(Component);
	}

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Spawned instanced proxy visuals: components=%d segments=%d instances=%d"),
		ProxySegmentComponents.Num(),
		Impl->ProxySegments.Num(),
		Impl->ProxySegments.Num() * CrowdSize);
}

UMaterialInterface* AProphecyNNCrowdBenchmarkActor::CreateTintedMaterial(FName ObjectName, const FLinearColor& Color)
{
	UMaterialInterface* ParentMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	if (!ParentMaterial)
	{
		ParentMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
	}
	if (!ParentMaterial)
	{
		return nullptr;
	}

	UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(ParentMaterial, this, ObjectName);
	if (!Material)
	{
		return ParentMaterial;
	}

	Material->SetVectorParameterValue(TEXT("Color"), Color);
	Material->SetVectorParameterValue(TEXT("BaseColor"), Color);
	Material->SetVectorParameterValue(TEXT("Base Color"), Color);
	Material->SetVectorParameterValue(TEXT("Tint"), Color);
	return Material;
}

void AProphecyNNCrowdBenchmarkActor::ApplyGrassWindMaterialParameters()
{
	if (!GrassMaterialInstance)
	{
		return;
	}

	const bool bUseDiagnosticWind = bGrassWindDiagnostic;
	const float EffectiveBendCm = bUseDiagnosticWind ? FMath::Max(GrassWindBendCm, 85.0f) : GrassWindBendCm;
	const float EffectiveLiftCm = bUseDiagnosticWind ? FMath::Max(GrassWindLiftCm, 100.0f) : GrassWindLiftCm;
	const float EffectiveWorldFrequency = FMath::Max(GrassWindWorldFrequency, 0.00001f);
	const float EffectivePatchFrequency = FMath::Max(GrassWindPatchFrequency, 0.00001f);
	const float EffectiveSpeed = FMath::Max(GrassWindSpeed, 0.0f);
	const float EffectiveGust = FMath::Max(GrassWindGustStrength, 0.0f);
	const float WindEnabled = bGrassWind ? 1.0f : 0.0f;

	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindEnabled"), WindEnabled);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindDiagnostic"), bUseDiagnosticWind ? 1.0f : 0.0f);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindBendCm"), EffectiveBendCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindLiftCm"), EffectiveLiftCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindWorldFrequency"), EffectiveWorldFrequency);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindPatchFrequency"), EffectivePatchFrequency);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindSpeed"), EffectiveSpeed);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindGustStrength"), EffectiveGust);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindTextureScale"), EffectiveWorldFrequency / UE_TWO_PI);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassWindTextureSpeed"), EffectiveSpeed * 0.025f);
	GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassWindDirection"), FLinearColor(0.86f, 0.50f, 0.0f, 0.0f));
	GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassWindPatchDirection"), FLinearColor(-0.46f, 0.89f, 0.0f, 0.0f));
	GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassDistantFadeCenter"), FLinearColor(0.0f, 700.0f, 0.0f, 0.0f));
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantColorStartCm"), ProphecyGrassDistantFadeStartCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantColorInvRange"), 1.0f / ProphecyGrassDistantFadeRangeCm);
	GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassDistantColor"), ProphecyGrassContinuationColor);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassFarRootLiftStartCm"), ProphecyGrassFarRootLiftStartCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassFarRootLiftInvRange"), 1.0f / ProphecyGrassFarRootLiftRangeCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassFarRootLiftStrength"), ProphecyGrassFarRootLiftStrength);
	GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassFarRootLiftColor"), ProphecyGrassFarRootLiftColor);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenStartCm"), ProphecyGrassDistantFadeStartCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenInvRange"), 1.0f / ProphecyGrassDistantFadeRangeCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenCm"), 0.0f);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantOpacityStartCm"), ProphecyGrassDistantFadeStartCm);
	GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantOpacityInvRange"), 1.0f / ProphecyGrassDistantFadeRangeCm);

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Grass wind material parameters: enabled=%d diagnostic=%d bend=%.1fcm lift=%.1fcm world_freq=%.6f patch_freq=%.6f speed=%.2f gust=%.2f"),
		bGrassWind ? 1 : 0,
		bGrassWindDiagnostic ? 1 : 0,
		EffectiveBendCm,
		EffectiveLiftCm,
		EffectiveWorldFrequency,
		EffectivePatchFrequency,
		EffectiveSpeed,
		EffectiveGust);
}

void AProphecyNNCrowdBenchmarkActor::ApplyTreeWindMaterialParameters()
{
	if (!TreeMaterialInstance)
	{
		return;
	}

	const bool bUseDiagnosticWind = bTreeWindDiagnostic;
	const float EffectiveBendCm = bUseDiagnosticWind ? FMath::Max(TreeWindBendCm, 180.0f) : TreeWindBendCm;
	const float EffectiveLiftCm = bUseDiagnosticWind ? FMath::Max(TreeWindLiftCm, 85.0f) : TreeWindLiftCm;
	const float EffectiveWorldFrequency = FMath::Max(TreeWindWorldFrequency, 0.00001f);
	const float EffectiveSpeed = FMath::Max(TreeWindSpeed, 0.0f);
	const float EffectiveGust = FMath::Max(TreeWindGustStrength, 0.0f);
	const float WindEnabled = bTreeWind ? 1.0f : 0.0f;

	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindEnabled"), WindEnabled);
	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindDiagnostic"), bUseDiagnosticWind ? 1.0f : 0.0f);
	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindBendCm"), EffectiveBendCm);
	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindLiftCm"), EffectiveLiftCm);
	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindWorldFrequency"), EffectiveWorldFrequency);
	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindSpeed"), EffectiveSpeed);
	TreeMaterialInstance->SetScalarParameterValue(TEXT("TreeWindGustStrength"), EffectiveGust);
	TreeMaterialInstance->SetVectorParameterValue(TEXT("TreeWindDirection"), FLinearColor(0.86f, 0.50f, 0.0f, 0.0f));

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Tree wind material parameters: enabled=%d diagnostic=%d bend=%.1fcm lift=%.1fcm world_freq=%.6f speed=%.2f gust=%.2f"),
		bTreeWind ? 1 : 0,
		bTreeWindDiagnostic ? 1 : 0,
		EffectiveBendCm,
		EffectiveLiftCm,
		EffectiveWorldFrequency,
		EffectiveSpeed,
		EffectiveGust);
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateGrassClusterMesh()
{
	return CreateGrassClusterMeshVariant(GrassMesh, TEXT("ProphecyRuntimeGrassCluster"), ProphecyGrassBladesPerTile, false);
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateDenseGrassClusterMesh()
{
	return CreateGrassClusterMeshVariant(DenseGrassMesh, TEXT("ProphecyRuntimeDenseGrassCluster"), ProphecyGrassDenseBladesPerTile, true);
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateGrassClusterMeshVariant(TObjectPtr<UStaticMesh>& MeshSlot, FName MeshName, int32 BladesPerTile, bool bDenseCoverage)
{
	if (MeshSlot)
	{
		return MeshSlot;
	}

	UMaterialInterface* GrassMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrass_UnlitField.M_ProphecyGrass_UnlitField"));
	if (!GrassMaterial)
	{
		GrassMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrass_LitVertexColor.M_ProphecyGrass_LitVertexColor"));
	}
	if (!GrassMaterial)
	{
		GrassMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"));
	}
	if (!GrassMaterial)
	{
		GrassMaterial = CreateTintedMaterial(TEXT("ProphecyGrassFallbackMaterial"), FLinearColor(0.08f, 0.24f, 0.055f, 1.0f));
	}
	if (!GrassMaterialInstance && GrassMaterial)
	{
		GrassMaterialInstance = UMaterialInstanceDynamic::Create(GrassMaterial, this);
		ApplyGrassWindMaterialParameters();
		ConfigureBloodMaskMaterials();
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	FMeshDescriptionBuilder Builder;
	Builder.SetMeshDescription(&MeshDescription);
	Builder.SetNumUVLayers(1);
	Builder.ReserveNewVertices(BladesPerTile * 12 + (bDenseCoverage ? ProphecyGrassDenseFillersPerTile * 6 : 0));
	FPolygonGroupID PolygonGroup = Builder.AppendPolygonGroup(TEXT("Grass"));

	auto AddTriangle = [&Builder, PolygonGroup](const FVector& A, const FVector& B, const FVector& C, const FVector4f& ColorA, const FVector4f& ColorB, const FVector4f& ColorC, double U0, double U1, double U2, double V0, double V1, double V2)
	{
		const FVertexID VA = Builder.AppendVertex(A);
		const FVertexID VB = Builder.AppendVertex(B);
		const FVertexID VC = Builder.AppendVertex(C);
		const FVertexInstanceID IA = Builder.AppendInstance(VA);
		const FVertexInstanceID IB = Builder.AppendInstance(VB);
		const FVertexInstanceID IC = Builder.AppendInstance(VC);
		const FVector FaceNormal = FVector::CrossProduct(B - A, C - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector Normal = (FaceNormal * 0.20 + FVector::UpVector * 0.80).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector Tangent = (B - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
		Builder.SetInstanceNormal(IA, Normal);
		Builder.SetInstanceNormal(IB, Normal);
		Builder.SetInstanceNormal(IC, Normal);
		Builder.SetInstanceTangentSpace(IA, Normal, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IB, Normal, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IC, Normal, Tangent, 1.0f);
		Builder.SetInstanceUV(IA, FVector2D(U0, V0));
		Builder.SetInstanceUV(IB, FVector2D(U1, V1));
		Builder.SetInstanceUV(IC, FVector2D(U2, V2));
		Builder.SetInstanceColor(IA, ColorA);
		Builder.SetInstanceColor(IB, ColorB);
		Builder.SetInstanceColor(IC, ColorC);
		Builder.AppendTriangle(IA, IB, IC, PolygonGroup);
	};

	auto AddQuad = [&AddTriangle](const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector4f& ColorA, const FVector4f& ColorB, const FVector4f& ColorC, const FVector4f& ColorD, double VA, double VB, double VC, double VD)
	{
		AddTriangle(A, C, B, ColorA, ColorC, ColorB, 0.0, 0.0, 1.0, VA, VC, VB);
		AddTriangle(B, C, D, ColorB, ColorC, ColorD, 1.0, 0.0, 1.0, VB, VC, VD);
	};

	auto VaryColor = [](const FVector3f& Color, float CoolWarm, float ValueShift)
	{
		return FVector4f(
			FMath::Clamp(Color.X + CoolWarm * 0.020f + ValueShift, 0.008f, 0.420f),
			FMath::Clamp(Color.Y + ValueShift * 1.20f, 0.025f, 0.560f),
			FMath::Clamp(Color.Z - CoolWarm * 0.010f + ValueShift * 0.55f, 0.005f, 0.260f),
			1.0f);
	};

	auto AddBlade = [&AddQuad](float YawDegrees, float OffsetX, float OffsetY, float WidthCm, float HeightCm, float LeanForwardCm, float LeanSideCm, const FVector4f& BaseColor, const FVector4f& MidColor, const FVector4f& TipColor)
	{
		const float YawRadians = FMath::DegreesToRadians(YawDegrees);
		const FVector Right(FMath::Cos(YawRadians), FMath::Sin(YawRadians), 0.0);
		const FVector Forward(-Right.Y, Right.X, 0.0);
		const FVector BaseCenter(OffsetX, OffsetY, 0.0);
		const FVector Bend = Forward * LeanForwardCm + Right * LeanSideCm;
		const FVector MidCenter = BaseCenter + Bend * 0.42 + FVector(0.0, 0.0, HeightCm * 0.56);
		const FVector TipCenter = BaseCenter + Bend + FVector(0.0, 0.0, HeightCm);
		const float BaseWidth = WidthCm;
		const float MidWidth = WidthCm * 0.54f;
		const float TipWidth = FMath::Max(0.06f, WidthCm * 0.10f);

		const FVector BaseA = BaseCenter - Right * (BaseWidth * 0.5);
		const FVector BaseB = BaseCenter + Right * (BaseWidth * 0.5);
		const FVector MidA = MidCenter - Right * (MidWidth * 0.5);
		const FVector MidB = MidCenter + Right * (MidWidth * 0.5);
		const FVector TipA = TipCenter - Right * (TipWidth * 0.5);
		const FVector TipB = TipCenter + Right * (TipWidth * 0.5);
		AddQuad(BaseA, BaseB, MidA, MidB, BaseColor, BaseColor, MidColor, MidColor, 0.0, 0.0, 0.55, 0.55);
		AddQuad(MidA, MidB, TipA, TipB, MidColor, MidColor, TipColor, TipColor, 0.55, 0.55, 1.0, 1.0);
	};

	auto AddGroundFiller = [&AddQuad](float YawDegrees, float OffsetX, float OffsetY, float WidthCm, float LengthCm, float LiftCm, float SideCm, const FVector4f& BaseColor, const FVector4f& TipColor)
	{
		const float YawRadians = FMath::DegreesToRadians(YawDegrees);
		const FVector Right(FMath::Cos(YawRadians), FMath::Sin(YawRadians), 0.0);
		const FVector Forward(-Right.Y, Right.X, 0.0);
		const FVector BaseCenter(OffsetX, OffsetY, 1.0);
		const FVector TipCenter = BaseCenter + Forward * LengthCm + Right * SideCm + FVector(0.0, 0.0, LiftCm);
		const float BaseWidth = WidthCm;
		const float TipWidth = WidthCm * 0.42f;
		const FVector BaseA = BaseCenter - Right * (BaseWidth * 0.5);
		const FVector BaseB = BaseCenter + Right * (BaseWidth * 0.5);
		const FVector TipA = TipCenter - Right * (TipWidth * 0.5);
		const FVector TipB = TipCenter + Right * (TipWidth * 0.5);
		AddQuad(BaseA, BaseB, TipA, TipB, BaseColor, BaseColor, TipColor, TipColor, 0.0, 0.0, 1.0, 1.0);
	};

	FRandomStream TileRandom(51091);
	const float HalfTile = ProphecyGrassTileSizeCm * 0.5f;
	const int32 ClumpCount = bDenseCoverage ? 62 : 34;
	TArray<FVector2D> ClumpCenters;
	ClumpCenters.Reserve(ClumpCount);
	for (int32 ClumpIndex = 0; ClumpIndex < ClumpCount; ++ClumpIndex)
	{
		ClumpCenters.Add(FVector2D(
			TileRandom.FRandRange(-HalfTile * 0.92f, HalfTile * 0.92f),
			TileRandom.FRandRange(-HalfTile * 0.92f, HalfTile * 0.92f)));
	}

	for (int32 BladeIndex = 0; BladeIndex < BladesPerTile; ++BladeIndex)
	{
		float OffsetX = TileRandom.FRandRange(-HalfTile, HalfTile);
		float OffsetY = TileRandom.FRandRange(-HalfTile, HalfTile);
		const float ClumpChance = bDenseCoverage ? 0.28f : 0.78f;
		if (TileRandom.FRand() < ClumpChance && ClumpCenters.Num() > 0)
		{
			const FVector2D Clump = ClumpCenters[TileRandom.RandRange(0, ClumpCenters.Num() - 1)];
			const float Radius = TileRandom.FRandRange(5.0f, bDenseCoverage ? 46.0f : 32.0f) * FMath::Sqrt(TileRandom.FRand());
			const float Angle = TileRandom.FRandRange(0.0f, UE_TWO_PI);
			OffsetX = FMath::Clamp(Clump.X + FMath::Cos(Angle) * Radius, -HalfTile, HalfTile);
			OffsetY = FMath::Clamp(Clump.Y + FMath::Sin(Angle) * Radius, -HalfTile, HalfTile);
		}

		const float Yaw = TileRandom.FRandRange(0.0f, 360.0f);
		float Height = TileRandom.FRandRange(bDenseCoverage ? 26.0f : 20.0f, bDenseCoverage ? 66.0f : 52.0f);
		if (TileRandom.FRand() < (bDenseCoverage ? 0.20f : 0.14f))
		{
			Height += TileRandom.FRandRange(9.0f, bDenseCoverage ? 30.0f : 22.0f);
		}
		if (TileRandom.FRand() < 0.09f)
		{
			Height *= TileRandom.FRandRange(0.52f, 0.76f);
		}
		const float Width = TileRandom.FRandRange(bDenseCoverage ? 1.15f : 0.95f, bDenseCoverage ? 3.85f : 3.10f);
		const float LeanForward = TileRandom.FRandRange(bDenseCoverage ? -6.0f : -4.0f, bDenseCoverage ? 28.0f : 20.0f) + Height * TileRandom.FRandRange(0.10f, bDenseCoverage ? 0.38f : 0.28f);
		const float LeanSide = TileRandom.FRandRange(bDenseCoverage ? -11.0f : -7.0f, bDenseCoverage ? 11.0f : 7.0f);
		const float CoolWarm = TileRandom.FRandRange(-1.0f, 1.0f);
		const float ValueShift = TileRandom.FRandRange(-0.030f, 0.040f);
		const float ToneRoll = TileRandom.FRand();
		const float DryChance = bDenseCoverage ? 0.025f : 0.045f;
		const float ShadeChance = bDenseCoverage ? 0.205f : 0.265f;
		const float SunChance = bDenseCoverage ? 0.145f : 0.105f;
		FVector3f BaseTint(0.022f, 0.080f, 0.018f);
		FVector3f MidTint(0.060f, 0.175f, 0.036f);
		FVector3f TipTint(0.145f, 0.340f, 0.064f);
		if (ToneRoll < DryChance)
		{
			BaseTint = FVector3f(0.070f, 0.072f, 0.030f);
			MidTint = FVector3f(0.145f, 0.155f, 0.060f);
			TipTint = FVector3f(0.240f, 0.250f, 0.095f);
		}
		else if (ToneRoll < DryChance + ShadeChance)
		{
			BaseTint = FVector3f(0.014f, 0.055f, 0.014f);
			MidTint = FVector3f(0.035f, 0.115f, 0.025f);
			TipTint = FVector3f(0.075f, 0.210f, 0.043f);
		}
		else if (ToneRoll < DryChance + ShadeChance + SunChance)
		{
			BaseTint = FVector3f(0.030f, 0.100f, 0.020f);
			MidTint = FVector3f(0.090f, 0.235f, 0.042f);
			TipTint = FVector3f(0.195f, 0.430f, 0.075f);
		}
		AddBlade(
			Yaw,
			OffsetX,
			OffsetY,
			Width,
			Height,
			LeanForward,
			LeanSide,
			VaryColor(BaseTint, CoolWarm, ValueShift * 0.45f),
			VaryColor(MidTint, CoolWarm, ValueShift * 0.70f),
			VaryColor(TipTint, CoolWarm, ValueShift));
	}

	if (bDenseCoverage)
	{
		for (int32 FillerIndex = 0; FillerIndex < ProphecyGrassDenseFillersPerTile; ++FillerIndex)
		{
			const float OffsetX = TileRandom.FRandRange(-HalfTile, HalfTile);
			const float OffsetY = TileRandom.FRandRange(-HalfTile, HalfTile);
			const float Yaw = TileRandom.FRandRange(0.0f, 360.0f);
			const float Width = TileRandom.FRandRange(2.0f, 5.2f);
			const float Length = TileRandom.FRandRange(22.0f, 64.0f);
			const float Lift = TileRandom.FRandRange(1.0f, 6.5f);
			const float Side = TileRandom.FRandRange(-10.0f, 10.0f);
			const float CoolWarm = TileRandom.FRandRange(-1.0f, 1.0f);
			const float ValueShift = TileRandom.FRandRange(-0.030f, 0.008f);
			const FVector3f BaseTint(0.015f, 0.055f, 0.012f);
			const FVector3f TipTint(0.060f, 0.165f, 0.034f);
			AddGroundFiller(
				Yaw,
				OffsetX,
				OffsetY,
				Width,
				Length,
				Lift,
				Side,
				VaryColor(BaseTint, CoolWarm, ValueShift * 0.45f),
				VaryColor(TipTint, CoolWarm, ValueShift));
		}
	}

	MeshSlot = NewObject<UStaticMesh>(this, MeshName, RF_Transient);
	if (!MeshSlot)
	{
		return nullptr;
	}
	MeshSlot->GetStaticMaterials().Add(FStaticMaterial(GrassMaterial, TEXT("Grass")));

	UStaticMesh::FBuildMeshDescriptionsParams Params;
	Params.bBuildSimpleCollision = false;
	Params.bCommitMeshDescription = false;
	Params.bFastBuild = true;
	Params.bAllowCpuAccess = false;
	TArray<const FMeshDescription*> MeshDescriptions;
	MeshDescriptions.Add(&MeshDescription);
	if (!MeshSlot->BuildFromMeshDescriptions(MeshDescriptions, Params))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Failed to build runtime grass mesh."));
		MeshSlot = nullptr;
	}
	return MeshSlot;
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateDistantGrassHillsMesh()
{
	if (DistantHillsMesh)
	{
		return DistantHillsMesh;
	}

	const bool bHillShadeDiagnostic = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNHillShadeDiagnostic"));
	const bool bHillVertexColorDiagnostic = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNHillVertexColorDiagnostic"));
	if (bHillShadeDiagnostic)
	{
		UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Using temporary diagnostic exaggerated distant hill vertex shading."));
	}
	if (bHillVertexColorDiagnostic)
	{
		UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Using temporary diagnostic distant hill vertex-color material."));
	}

	UMaterialInterface* HillsMaterial = bHillVertexColorDiagnostic
		? LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"))
		: LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassTerrainShared.M_ProphecyGrassTerrainShared"));
	if (bHillVertexColorDiagnostic && !HillsMaterial)
	{
		HillsMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassTerrainShared.M_ProphecyGrassTerrainShared"));
	}
	if (!HillsMaterial)
	{
		HillsMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassFarHills.M_ProphecyGrassFarHills"));
	}
	if (!HillsMaterial)
	{
		HillsMaterial = CreateTintedMaterial(TEXT("ProphecyDistantHillsFallbackMaterial"), ProphecyGrassGroundBaseColor);
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	FMeshDescriptionBuilder Builder;
	Builder.SetMeshDescription(&MeshDescription);
	Builder.SetNumUVLayers(1);
	Builder.ReserveNewVertices((ProphecyDistantHillRings - 1) * ProphecyDistantHillSegments * 6);
	FPolygonGroupID PolygonGroup = Builder.AppendPolygonGroup(TEXT("DistantGrassHills"));

	auto HillPoint = [](int32 RingIndex, int32 SegmentIndex)
	{
		const float Angle = (float(SegmentIndex) / float(ProphecyDistantHillSegments)) * UE_TWO_PI;
		const float RingT = float(RingIndex) / float(ProphecyDistantHillRings - 1);
		const float Radius = FMath::Lerp(ProphecyDistantHillInnerRadiusCm, ProphecyDistantHillOuterRadiusCm, ProphecySmooth01(RingT));
		const float Height = ProphecyDistantHillHeightAtRadiusAngle(Radius, Angle);
		return FVector(
			ProphecyTerrainCenterX + FMath::Cos(Angle) * Radius,
			ProphecyTerrainCenterY + FMath::Sin(Angle) * Radius,
			Height);
	};

	const FVector BakedSunDirection = FRotationMatrix(FRotator(-45.0, 35.0, 0.0)).GetUnitAxis(EAxis::X).GetSafeNormal();
	const FVector BakedToSunDirection = (-BakedSunDirection).GetSafeNormal();
	const FVector2D BakedSunHorizontal(BakedToSunDirection.X, BakedToSunDirection.Y);
	const FVector2D BakedSunHorizontalSafe = BakedSunHorizontal.IsNearlyZero() ? FVector2D(1.0, 0.0) : BakedSunHorizontal.GetSafeNormal();
	const FVector2D BakedSunCross(-BakedSunHorizontalSafe.Y, BakedSunHorizontalSafe.X);

	auto BakedSelfShadowAt = [BakedSunHorizontalSafe](const FVector& Position)
	{
		float Shadow = 0.0f;
		const FVector2D Start(Position.X, Position.Y);
		constexpr int32 StepCount = 18;
		constexpr float StepLengthCm = 1550.0f;
		constexpr float ShadowRisePerCm = 0.10f;
		for (int32 StepIndex = 1; StepIndex <= StepCount; ++StepIndex)
		{
			const float DistanceCm = StepLengthCm * float(StepIndex);
			const FVector2D SampleXY = Start + BakedSunHorizontalSafe * DistanceCm;
			float SampleHeight = 0.0f;
			if (!ProphecyDistantTerrainHeightAtXY(SampleXY, SampleHeight))
			{
				continue;
			}
			const float LightRayHeight = float(Position.Z) + DistanceCm * ShadowRisePerCm + 80.0f;
			if (SampleHeight > LightRayHeight)
			{
				const float Penetration = FMath::Clamp((SampleHeight - LightRayHeight) / 2600.0f, 0.0f, 1.0f);
				const float DistanceFade = FMath::Clamp(1.0f - (float(StepIndex - 1) / float(StepCount)), 0.0f, 1.0f);
				Shadow = FMath::Max(Shadow, Penetration * (0.45f + 0.55f * DistanceFade));
			}
		}
		return Shadow;
	};

	auto TerrainNormalAt = [](const FVector& Position)
	{
		constexpr float SampleStepCm = 700.0f;
		auto HeightAtOr = [](const FVector2D& WorldXY, float FallbackHeight)
		{
			float Height = FallbackHeight;
			ProphecyDistantTerrainHeightAtXY(WorldXY, Height);
			return Height;
		};

		const FVector2D CenterXY(Position.X, Position.Y);
		const float HeightX0 = HeightAtOr(CenterXY - FVector2D(SampleStepCm, 0.0f), Position.Z);
		const float HeightX1 = HeightAtOr(CenterXY + FVector2D(SampleStepCm, 0.0f), Position.Z);
		const float HeightY0 = HeightAtOr(CenterXY - FVector2D(0.0f, SampleStepCm), Position.Z);
		const float HeightY1 = HeightAtOr(CenterXY + FVector2D(0.0f, SampleStepCm), Position.Z);
		const FVector SlopeX(SampleStepCm * 2.0f, 0.0f, HeightX1 - HeightX0);
		const FVector SlopeY(0.0f, SampleStepCm * 2.0f, HeightY1 - HeightY0);
		FVector Normal = FVector::CrossProduct(SlopeX, SlopeY).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		if (Normal.Z < 0.0)
		{
			Normal *= -1.0;
		}
		return Normal;
	};

	auto BakedShadeAt = [BakedToSunDirection, BakedSunHorizontalSafe, BakedSunCross, bHillShadeDiagnostic, &BakedSelfShadowAt, &TerrainNormalAt](const FVector& Position)
	{
		if (!bHillShadeDiagnostic)
		{
			return 1.0f;
		}

		const FVector Normal = TerrainNormalAt(Position);
		const float LitAmount = FMath::Clamp(float(FVector::DotProduct(Normal, BakedToSunDirection)), 0.0f, 1.0f);
		const FVector2D RawSlopeAspect(Normal.X, Normal.Y);
		const FVector2D SlopeAspect = RawSlopeAspect.IsNearlyZero() ? FVector2D::ZeroVector : RawSlopeAspect.GetSafeNormal();
		const float AspectLight = RawSlopeAspect.IsNearlyZero()
			? LitAmount
			: FMath::Clamp(0.5f + 0.5f * float(FVector2D::DotProduct(SlopeAspect, BakedSunHorizontalSafe)), 0.0f, 1.0f);
		const float HeightAlpha = FMath::Clamp(float(Position.Z / 9000.0), 0.0f, 1.0f);
		const float ReliefStrength = FMath::Clamp((1.0f - float(Normal.Z)) * 22.0f, 0.25f, 1.0f);
		const float SelfShadow = BakedSelfShadowAt(Position);
		const float LeeShadow = FMath::Pow(1.0f - AspectLight, 0.78f) * FMath::Lerp(0.45f, 1.0f, ReliefStrength);
		const float ShadowAmount = FMath::Clamp(FMath::Max(LeeShadow, SelfShadow), 0.0f, 1.0f);
		const float LitLift = FMath::Lerp(0.90f, 1.12f, FMath::Pow(AspectLight, 0.75f));
		const float Shade = FMath::Lerp(LitLift, 0.14f, ShadowAmount) * (0.84f + 0.18f * HeightAlpha);
		float ClampedShade = FMath::Clamp(Shade, 0.08f, 1.14f);
		if (bHillShadeDiagnostic)
		{
			const FVector2D CenterXY(Position.X, Position.Y);
			const float AlongSun = float(FVector2D::DotProduct(CenterXY, BakedSunHorizontalSafe));
			const float AcrossSun = float(FVector2D::DotProduct(CenterXY, BakedSunCross));
			const int32 SunBandIndex = FMath::FloorToInt((AcrossSun + AlongSun * 0.35f) / 1800.0f);
			const bool bDarkDiagnosticBand = (SunBandIndex & 1) == 0;
			ClampedShade = bDarkDiagnosticBand ? 0.015f : 1.85f;
		}
		return ClampedShade;
	};

	auto AddTerrainTriangle = [&Builder, PolygonGroup, &TerrainNormalAt, &BakedShadeAt](const FVector& A, const FVector& B, const FVector& C)
	{
		const FVertexID VA = Builder.AppendVertex(A);
		const FVertexID VB = Builder.AppendVertex(B);
		const FVertexID VC = Builder.AppendVertex(C);
		const FVertexInstanceID IA = Builder.AppendInstance(VA);
		const FVertexInstanceID IB = Builder.AppendInstance(VB);
		const FVertexInstanceID IC = Builder.AppendInstance(VC);
		const FVector Tangent = (B - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
		const FVector NormalA = TerrainNormalAt(A);
		const FVector NormalB = TerrainNormalAt(B);
		const FVector NormalC = TerrainNormalAt(C);
		const float ShadeA = BakedShadeAt(A);
		const float ShadeB = BakedShadeAt(B);
		const float ShadeC = BakedShadeAt(C);
		const FVector4f ColorA(ShadeA, ShadeA, ShadeA, 1.0f);
		const FVector4f ColorB(ShadeB, ShadeB, ShadeB, 1.0f);
		const FVector4f ColorC(ShadeC, ShadeC, ShadeC, 1.0f);
		Builder.SetInstanceNormal(IA, NormalA);
		Builder.SetInstanceNormal(IB, NormalB);
		Builder.SetInstanceNormal(IC, NormalC);
		Builder.SetInstanceTangentSpace(IA, NormalA, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IB, NormalB, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IC, NormalC, Tangent, 1.0f);
		Builder.SetInstanceUV(IA, FVector2D(A.X * 0.000045, A.Y * 0.000045));
		Builder.SetInstanceUV(IB, FVector2D(B.X * 0.000045, B.Y * 0.000045));
		Builder.SetInstanceUV(IC, FVector2D(C.X * 0.000045, C.Y * 0.000045));
		Builder.SetInstanceColor(IA, ColorA);
		Builder.SetInstanceColor(IB, ColorB);
		Builder.SetInstanceColor(IC, ColorC);
		Builder.AppendTriangle(IA, IC, IB, PolygonGroup);
	};

	for (int32 RingIndex = 0; RingIndex < ProphecyDistantHillRings - 1; ++RingIndex)
	{
		for (int32 SegmentIndex = 0; SegmentIndex < ProphecyDistantHillSegments; ++SegmentIndex)
		{
			const int32 NextSegmentIndex = (SegmentIndex + 1) % ProphecyDistantHillSegments;
			const FVector InnerA = HillPoint(RingIndex, SegmentIndex);
			const FVector InnerB = HillPoint(RingIndex, NextSegmentIndex);
			const FVector OuterA = HillPoint(RingIndex + 1, SegmentIndex);
			const FVector OuterB = HillPoint(RingIndex + 1, NextSegmentIndex);
			AddTerrainTriangle(InnerA, OuterA, InnerB);
			AddTerrainTriangle(InnerB, OuterA, OuterB);
		}
	}

	DistantHillsMesh = NewObject<UStaticMesh>(this, TEXT("ProphecyRuntimeDistantGrassHills"), RF_Transient);
	if (!DistantHillsMesh)
	{
		return nullptr;
	}
	DistantHillsMesh->GetStaticMaterials().Add(FStaticMaterial(HillsMaterial, TEXT("DistantGrassHills")));

	UStaticMesh::FBuildMeshDescriptionsParams Params;
	Params.bBuildSimpleCollision = false;
	Params.bCommitMeshDescription = false;
	Params.bFastBuild = true;
	Params.bAllowCpuAccess = false;
	TArray<const FMeshDescription*> MeshDescriptions;
	MeshDescriptions.Add(&MeshDescription);
	if (!DistantHillsMesh->BuildFromMeshDescriptions(MeshDescriptions, Params))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Failed to build runtime distant grass hills mesh."));
		DistantHillsMesh = nullptr;
	}
	return DistantHillsMesh;
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateTreeMesh()
{
	if (TreeMesh)
	{
		return TreeMesh;
	}

	UMaterialInterface* TreeMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyTreeVertexWind.M_ProphecyTreeVertexWind"));
	if (!TreeMaterial)
	{
		TreeMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"));
	}
	if (!TreeMaterial)
	{
		TreeMaterial = CreateTintedMaterial(TEXT("ProphecyTreeFallbackMaterial"), FLinearColor(0.04f, 0.14f, 0.04f, 1.0f));
	}
	if (!TreeMaterialInstance && TreeMaterial)
	{
		TreeMaterialInstance = UMaterialInstanceDynamic::Create(TreeMaterial, this);
		ApplyTreeWindMaterialParameters();
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	FMeshDescriptionBuilder Builder;
	Builder.SetMeshDescription(&MeshDescription);
	Builder.SetNumUVLayers(1);
	Builder.ReserveNewVertices(120);
	FPolygonGroupID PolygonGroup = Builder.AppendPolygonGroup(TEXT("Tree"));

	auto AddTriangle = [&Builder, PolygonGroup](const FVector& A, const FVector& B, const FVector& C, const FVector4f& ColorA, const FVector4f& ColorB, const FVector4f& ColorC, const FVector2D& UVA, const FVector2D& UVB, const FVector2D& UVC)
	{
		const FVertexID VA = Builder.AppendVertex(A);
		const FVertexID VB = Builder.AppendVertex(B);
		const FVertexID VC = Builder.AppendVertex(C);
		const FVertexInstanceID IA = Builder.AppendInstance(VA);
		const FVertexInstanceID IB = Builder.AppendInstance(VB);
		const FVertexInstanceID IC = Builder.AppendInstance(VC);
		const FVector Normal = FVector::CrossProduct(B - A, C - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector Tangent = (B - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
		Builder.SetInstanceNormal(IA, Normal);
		Builder.SetInstanceNormal(IB, Normal);
		Builder.SetInstanceNormal(IC, Normal);
		Builder.SetInstanceTangentSpace(IA, Normal, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IB, Normal, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IC, Normal, Tangent, 1.0f);
		Builder.SetInstanceUV(IA, UVA);
		Builder.SetInstanceUV(IB, UVB);
		Builder.SetInstanceUV(IC, UVC);
		Builder.SetInstanceColor(IA, ColorA);
		Builder.SetInstanceColor(IB, ColorB);
		Builder.SetInstanceColor(IC, ColorC);
		Builder.AppendTriangle(IA, IB, IC, PolygonGroup);
	};

	auto AddQuad = [&AddTriangle](const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector4f& ColorA, const FVector4f& ColorB, const FVector4f& ColorC, const FVector4f& ColorD)
	{
		AddTriangle(A, B, C, ColorA, ColorB, ColorC, FVector2D(0.0, 0.0), FVector2D(1.0, 0.0), FVector2D(0.0, 1.0));
		AddTriangle(B, D, C, ColorB, ColorD, ColorC, FVector2D(1.0, 0.0), FVector2D(1.0, 1.0), FVector2D(0.0, 1.0));
	};

	constexpr int32 Sides = 8;
	auto Color4 = [](const FLinearColor& Color)
	{
		return FVector4f(Color.R, Color.G, Color.B, Color.A);
	};
	auto BarkColor = [&Color4](float T)
	{
		const FLinearColor Base(0.022f, 0.015f, 0.010f, 1.0f);
		const FLinearColor High(0.070f, 0.046f, 0.030f, 1.0f);
		return Color4(FMath::Lerp(Base, High, FMath::Clamp(T, 0.0f, 1.0f)));
	};
	auto LeafColor = [&Color4](float Shade)
	{
		const FLinearColor Base(0.004f, 0.026f, 0.006f, 1.0f);
		const FLinearColor Lit(0.030f, 0.082f, 0.018f, 1.0f);
		return Color4(FMath::Lerp(Base, Lit, FMath::Clamp(Shade, 0.0f, 1.0f)));
	};
	auto RingPoint = [](float Angle, float RadiusX, float RadiusY, float Z)
	{
		return FVector(FMath::Cos(Angle) * RadiusX, FMath::Sin(Angle) * RadiusY, Z);
	};

	const TArray<float> TrunkZ = { 0.0f, 420.0f, 920.0f, 1420.0f, 1880.0f };
	const TArray<float> TrunkR = { 31.0f, 27.0f, 23.0f, 19.0f, 15.0f };
	for (int32 Ring = 0; Ring < TrunkZ.Num() - 1; ++Ring)
	{
		for (int32 Side = 0; Side < Sides; ++Side)
		{
			const float A0 = UE_TWO_PI * float(Side) / float(Sides);
			const float A1 = UE_TWO_PI * float(Side + 1) / float(Sides);
			const float Groove0 = 1.0f + 0.08f * FMath::Sin(float(Side) * 2.31f + float(Ring) * 0.64f);
			const float Groove1 = 1.0f + 0.08f * FMath::Sin(float(Side + 1) * 2.31f + float(Ring) * 0.64f);
			const FVector Base0 = RingPoint(A0, TrunkR[Ring] * Groove0, TrunkR[Ring] * Groove0, TrunkZ[Ring]);
			const FVector Base1 = RingPoint(A1, TrunkR[Ring] * Groove1, TrunkR[Ring] * Groove1, TrunkZ[Ring]);
			const FVector Top0 = RingPoint(A0, TrunkR[Ring + 1] * Groove0, TrunkR[Ring + 1] * Groove0, TrunkZ[Ring + 1]);
			const FVector Top1 = RingPoint(A1, TrunkR[Ring + 1] * Groove1, TrunkR[Ring + 1] * Groove1, TrunkZ[Ring + 1]);
			const float Shade0 = (Side & 1) ? 0.42f : 0.72f;
			const float Shade1 = ((Side + 1) & 1) ? 0.42f : 0.72f;
			AddQuad(Base0, Base1, Top0, Top1, BarkColor(Shade0), BarkColor(Shade1), BarkColor(Shade0 + 0.08f), BarkColor(Shade1 + 0.08f));
		}
	}

	const FVector4f BranchColor = BarkColor(0.55f);
	for (int32 BranchIndex = 0; BranchIndex < 4; ++BranchIndex)
	{
		const float Angle = float(BranchIndex) * UE_HALF_PI + 0.35f;
		const float BaseZ = 1040.0f + float(BranchIndex) * 175.0f;
		const FVector Base(FMath::Cos(Angle) * 16.0f, FMath::Sin(Angle) * 16.0f, BaseZ);
		const FVector Tip(FMath::Cos(Angle) * 260.0f, FMath::Sin(Angle) * 220.0f, BaseZ + 180.0f);
		const FVector Cross(-FMath::Sin(Angle) * 10.0f, FMath::Cos(Angle) * 10.0f, 0.0f);
		AddQuad(Base - Cross, Base + Cross, Tip - Cross * 0.45f, Tip + Cross * 0.45f, BranchColor, BranchColor, BranchColor, BranchColor);
	}

	const TArray<float> CrownZ = { 1450.0f, 1690.0f, 1990.0f, 2260.0f };
	const TArray<float> CrownRX = { 150.0f, 345.0f, 290.0f, 110.0f };
	const TArray<float> CrownRY = { 120.0f, 285.0f, 245.0f, 95.0f };
	for (int32 Ring = 0; Ring < CrownZ.Num() - 1; ++Ring)
	{
		for (int32 Side = 0; Side < Sides; ++Side)
		{
			const float Angle0 = UE_TWO_PI * float(Side) / float(Sides);
			const float Angle1 = UE_TWO_PI * float(Side + 1) / float(Sides);
			const float WarpA0 = 1.0f + 0.16f * FMath::Sin(float(Side) * 1.73f + float(Ring) * 0.91f) + 0.08f * FMath::Sin(float(Side) * 3.37f + 0.41f);
			const float WarpA1 = 1.0f + 0.16f * FMath::Sin(float(Side + 1) * 1.73f + float(Ring) * 0.91f) + 0.08f * FMath::Sin(float(Side + 1) * 3.37f + 0.41f);
			const float WarpB0 = 1.0f + 0.16f * FMath::Sin(float(Side) * 1.73f + float(Ring + 1) * 0.91f) + 0.08f * FMath::Sin(float(Side) * 3.37f + 0.41f);
			const float WarpB1 = 1.0f + 0.16f * FMath::Sin(float(Side + 1) * 1.73f + float(Ring + 1) * 0.91f) + 0.08f * FMath::Sin(float(Side + 1) * 3.37f + 0.41f);
			const FVector A = RingPoint(Angle0, CrownRX[Ring] * WarpA0, CrownRY[Ring] * WarpA0, CrownZ[Ring]);
			const FVector B = RingPoint(Angle1, CrownRX[Ring] * WarpA1, CrownRY[Ring] * WarpA1, CrownZ[Ring]);
			const FVector C = RingPoint(Angle0, CrownRX[Ring + 1] * WarpB0, CrownRY[Ring + 1] * WarpB0, CrownZ[Ring + 1]);
			const FVector D = RingPoint(Angle1, CrownRX[Ring + 1] * WarpB1, CrownRY[Ring + 1] * WarpB1, CrownZ[Ring + 1]);
			const float Shade0 = 0.34f + 0.38f * FMath::Max(0.0f, FMath::Cos(Angle0 - 0.55f));
			const float Shade1 = 0.34f + 0.38f * FMath::Max(0.0f, FMath::Cos(Angle1 - 0.55f));
			AddQuad(A, B, C, D, LeafColor(Shade0), LeafColor(Shade1), LeafColor(Shade0 + 0.08f), LeafColor(Shade1 + 0.08f));
		}
	}

	const FVector CrownTop(0.0, 0.0, 2390.0);
	const FVector4f CrownTopColor = LeafColor(0.70f);
	for (int32 Side = 0; Side < Sides; ++Side)
	{
		const float Angle0 = UE_TWO_PI * float(Side) / float(Sides);
		const float Angle1 = UE_TWO_PI * float(Side + 1) / float(Sides);
		const FVector A = RingPoint(Angle0, CrownRX.Last(), CrownRY.Last(), CrownZ.Last());
		const FVector B = RingPoint(Angle1, CrownRX.Last(), CrownRY.Last(), CrownZ.Last());
		AddTriangle(A, B, CrownTop, LeafColor(0.54f), LeafColor(0.60f), CrownTopColor, FVector2D(0.0, 0.0), FVector2D(1.0, 0.0), FVector2D(0.5, 1.0));
	}

	TreeMesh = NewObject<UStaticMesh>(this, TEXT("ProphecyRuntimeLowPolyTree"), RF_Transient);
	if (!TreeMesh)
	{
		return nullptr;
	}
	TreeMesh->GetStaticMaterials().Add(FStaticMaterial(TreeMaterial, TEXT("Tree")));

	UStaticMesh::FBuildMeshDescriptionsParams Params;
	Params.bBuildSimpleCollision = false;
	Params.bCommitMeshDescription = false;
	Params.bFastBuild = true;
	Params.bAllowCpuAccess = false;
	TArray<const FMeshDescription*> MeshDescriptions;
	MeshDescriptions.Add(&MeshDescription);
	if (!TreeMesh->BuildFromMeshDescriptions(MeshDescriptions, Params))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Failed to build runtime tree mesh."));
		TreeMesh = nullptr;
	}
	return TreeMesh;
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateContactShadowMesh()
{
	if (ContactShadowMesh)
	{
		return ContactShadowMesh;
	}

	const bool bUseSoftContactShadow = bSpawnGrass || bDebugShadowGeometry || IsRootContactShadowVariant(ContactShadowVariant) || IsFullDynamicShadowVariant(ContactShadowVariant);
	UMaterialInterface* ContactShadowMaterial = bUseSoftContactShadow
		? LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassContactShadow.M_ProphecyGrassContactShadow"))
		: nullptr;
	if (!ContactShadowMaterial)
	{
		ContactShadowMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"));
	}
	if (!ContactShadowMaterial)
	{
		ContactShadowMaterial = CreateTintedMaterial(TEXT("ProphecyContactShadowFallbackMaterial"), bUseSoftContactShadow ? FLinearColor(0.018f, 0.075f, 0.018f, 1.0f) : FLinearColor(0.02f, 0.018f, 0.012f, 1.0f));
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	FMeshDescriptionBuilder Builder;
	Builder.SetMeshDescription(&MeshDescription);
	Builder.SetNumUVLayers(1);
	FPolygonGroupID PolygonGroup = Builder.AppendPolygonGroup(TEXT("ContactShadow"));

	auto AddTriangle = [&Builder, PolygonGroup](const FVector& A, const FVector& B, const FVector& C, const FVector4f& ColorA, const FVector4f& ColorB, const FVector4f& ColorC, double U0, double U1, double U2, double V0, double V1, double V2)
	{
		const FVertexID VA = Builder.AppendVertex(A);
		const FVertexID VB = Builder.AppendVertex(B);
		const FVertexID VC = Builder.AppendVertex(C);
		const FVertexInstanceID IA = Builder.AppendInstance(VA);
		const FVertexInstanceID IB = Builder.AppendInstance(VB);
		const FVertexInstanceID IC = Builder.AppendInstance(VC);
		const FVector FaceNormal = FVector::CrossProduct(B - A, C - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector Normal = (FaceNormal * 0.35 + FVector::UpVector * 0.65).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
		const FVector Tangent = (B - A).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
		Builder.SetInstanceNormal(IA, Normal);
		Builder.SetInstanceNormal(IB, Normal);
		Builder.SetInstanceNormal(IC, Normal);
		Builder.SetInstanceTangentSpace(IA, Normal, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IB, Normal, Tangent, 1.0f);
		Builder.SetInstanceTangentSpace(IC, Normal, Tangent, 1.0f);
		Builder.SetInstanceUV(IA, FVector2D(U0, V0));
		Builder.SetInstanceUV(IB, FVector2D(U1, V1));
		Builder.SetInstanceUV(IC, FVector2D(U2, V2));
		Builder.SetInstanceColor(IA, ColorA);
		Builder.SetInstanceColor(IB, ColorB);
		Builder.SetInstanceColor(IC, ColorC);
		Builder.AppendTriangle(IA, IB, IC, PolygonGroup);
	};

	auto AddQuad = [&AddTriangle](const FVector& A, const FVector& B, const FVector& C, const FVector& D, const FVector4f& ColorA, const FVector4f& ColorB, const FVector4f& ColorC, const FVector4f& ColorD, double VA, double VB, double VC, double VD)
	{
		AddTriangle(A, C, B, ColorA, ColorC, ColorB, 0.0, 0.0, 1.0, VA, VC, VB);
		AddTriangle(B, C, D, ColorB, ColorC, ColorD, 1.0, 0.0, 1.0, VB, VC, VD);
	};

	if (bUseSoftContactShadow)
	{
		auto AddInstance = [&Builder](FVertexID Vertex, const FVector& Normal, const FVector& Tangent, const FVector2D& UV, const FVector4f& Color)
		{
			const FVertexInstanceID Instance = Builder.AppendInstance(Vertex);
			Builder.SetInstanceNormal(Instance, Normal);
			Builder.SetInstanceTangentSpace(Instance, Normal, Tangent, 1.0f);
			Builder.SetInstanceUV(Instance, UV);
			Builder.SetInstanceColor(Instance, Color);
			return Instance;
		};

		auto AddSoftEllipse = [&Builder, PolygonGroup, &AddInstance](const FVector2D& Center, float InnerRadiusX, float InnerRadiusY, float OuterRadiusX, float OuterRadiusY, float RotationDegrees, const FVector4f& CenterColor, const FVector4f& MidColor, const FVector4f& EdgeColor, int32 Segments)
		{
			const float RotationRadians = FMath::DegreesToRadians(RotationDegrees);
			const float CosR = FMath::Cos(RotationRadians);
			const float SinR = FMath::Sin(RotationRadians);
			auto RotatePoint = [Center, CosR, SinR](float X, float Y)
			{
				return FVector(Center.X + X * CosR - Y * SinR, Center.Y + X * SinR + Y * CosR, 0.0);
			};

			const FVector Normal = FVector::UpVector;
			const FVector Tangent = FVector::ForwardVector;
			const FVertexID CenterVertex = Builder.AppendVertex(FVector(Center.X, Center.Y, 0.0));

			for (int32 Index = 0; Index < Segments; ++Index)
			{
				const float AngleA = UE_TWO_PI * float(Index) / float(Segments);
				const float AngleB = UE_TWO_PI * float(Index + 1) / float(Segments);
				const FVector InnerA = RotatePoint(FMath::Cos(AngleA) * InnerRadiusX, FMath::Sin(AngleA) * InnerRadiusY);
				const FVector InnerB = RotatePoint(FMath::Cos(AngleB) * InnerRadiusX, FMath::Sin(AngleB) * InnerRadiusY);
				const FVector OuterA = RotatePoint(FMath::Cos(AngleA) * OuterRadiusX, FMath::Sin(AngleA) * OuterRadiusY);
				const FVector OuterB = RotatePoint(FMath::Cos(AngleB) * OuterRadiusX, FMath::Sin(AngleB) * OuterRadiusY);

				const FVertexID InnerVertexA = Builder.AppendVertex(InnerA);
				const FVertexID InnerVertexB = Builder.AppendVertex(InnerB);
				const FVertexID OuterVertexA = Builder.AppendVertex(OuterA);
				const FVertexID OuterVertexB = Builder.AppendVertex(OuterB);

				const FVertexInstanceID IC = AddInstance(CenterVertex, Normal, Tangent, FVector2D(0.5, 0.5), CenterColor);
				const FVertexInstanceID IIA = AddInstance(InnerVertexA, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleA) * 0.25, 0.5 + FMath::Sin(AngleA) * 0.25), MidColor);
				const FVertexInstanceID IIB = AddInstance(InnerVertexB, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleB) * 0.25, 0.5 + FMath::Sin(AngleB) * 0.25), MidColor);
				Builder.AppendTriangle(IC, IIA, IIB, PolygonGroup);

				const FVertexInstanceID IIA2 = AddInstance(InnerVertexA, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleA) * 0.25, 0.5 + FMath::Sin(AngleA) * 0.25), MidColor);
				const FVertexInstanceID IOA = AddInstance(OuterVertexA, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleA) * 0.5, 0.5 + FMath::Sin(AngleA) * 0.5), EdgeColor);
				const FVertexInstanceID IIB2 = AddInstance(InnerVertexB, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleB) * 0.25, 0.5 + FMath::Sin(AngleB) * 0.25), MidColor);
				Builder.AppendTriangle(IIA2, IOA, IIB2, PolygonGroup);

				const FVertexInstanceID IIB3 = AddInstance(InnerVertexB, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleB) * 0.25, 0.5 + FMath::Sin(AngleB) * 0.25), MidColor);
				const FVertexInstanceID IOA2 = AddInstance(OuterVertexA, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleA) * 0.5, 0.5 + FMath::Sin(AngleA) * 0.5), EdgeColor);
				const FVertexInstanceID IOB = AddInstance(OuterVertexB, Normal, Tangent, FVector2D(0.5 + FMath::Cos(AngleB) * 0.5, 0.5 + FMath::Sin(AngleB) * 0.5), EdgeColor);
				Builder.AppendTriangle(IIB3, IOA2, IOB, PolygonGroup);
			}
		};

		struct FShadowBandSection
		{
			float Y = 0.0f;
			float InnerHalfWidth = 0.0f;
			float OuterHalfWidth = 0.0f;
			float AlphaScale = 1.0f;
		};

		auto AddSoftSilhouetteBand = [&AddQuad](const TArray<FShadowBandSection>& Sections, const FVector4f& CenterColor, const FVector4f& MidColor, const FVector4f& EdgeColor)
		{
			if (Sections.Num() < 2)
			{
				return;
			}

			auto ScaledAlpha = [](const FVector4f& Color, float Scale)
			{
				return FVector4f(Color.X, Color.Y, Color.Z, Color.W * Scale);
			};

			for (int32 SectionIndex = 0; SectionIndex < Sections.Num() - 1; ++SectionIndex)
			{
				const FShadowBandSection& ASection = Sections[SectionIndex];
				const FShadowBandSection& BSection = Sections[SectionIndex + 1];
				const FVector APoints[5] = {
					FVector(-ASection.OuterHalfWidth, ASection.Y, 0.0),
					FVector(-ASection.InnerHalfWidth, ASection.Y, 0.0),
					FVector(0.0, ASection.Y, 0.0),
					FVector(ASection.InnerHalfWidth, ASection.Y, 0.0),
					FVector(ASection.OuterHalfWidth, ASection.Y, 0.0),
				};
				const FVector BPoints[5] = {
					FVector(-BSection.OuterHalfWidth, BSection.Y, 0.0),
					FVector(-BSection.InnerHalfWidth, BSection.Y, 0.0),
					FVector(0.0, BSection.Y, 0.0),
					FVector(BSection.InnerHalfWidth, BSection.Y, 0.0),
					FVector(BSection.OuterHalfWidth, BSection.Y, 0.0),
				};
				const FVector4f AColors[5] = {
					ScaledAlpha(EdgeColor, ASection.AlphaScale),
					ScaledAlpha(MidColor, ASection.AlphaScale),
					ScaledAlpha(CenterColor, ASection.AlphaScale),
					ScaledAlpha(MidColor, ASection.AlphaScale),
					ScaledAlpha(EdgeColor, ASection.AlphaScale),
				};
				const FVector4f BColors[5] = {
					ScaledAlpha(EdgeColor, BSection.AlphaScale),
					ScaledAlpha(MidColor, BSection.AlphaScale),
					ScaledAlpha(CenterColor, BSection.AlphaScale),
					ScaledAlpha(MidColor, BSection.AlphaScale),
					ScaledAlpha(EdgeColor, BSection.AlphaScale),
				};

				for (int32 ColumnIndex = 0; ColumnIndex < 4; ++ColumnIndex)
				{
					AddQuad(
						APoints[ColumnIndex],
						APoints[ColumnIndex + 1],
						BPoints[ColumnIndex],
						BPoints[ColumnIndex + 1],
						AColors[ColumnIndex],
						AColors[ColumnIndex + 1],
						BColors[ColumnIndex],
						BColors[ColumnIndex + 1],
						0.0,
						0.0,
						1.0,
						1.0);
				}
			}
		};

		if (IsRootContactShadowVariant(ContactShadowVariant) || IsFullDynamicShadowVariant(ContactShadowVariant))
		{
			const float FullProxyAlphaScale = IsFullDynamicShadowVariant(ContactShadowVariant) ? 0.62f : 1.0f;
			const FVector4f BodyCenterColor = bDebugShadowGeometry ? FVector4f(0.0f, 0.0f, 0.0f, 0.58f) : FVector4f(0.010f, 0.045f, 0.010f, 0.24f * FullProxyAlphaScale);
			const FVector4f BodyMidColor = bDebugShadowGeometry ? FVector4f(0.0f, 0.0f, 0.0f, 0.34f) : FVector4f(0.018f, 0.080f, 0.016f, 0.13f * FullProxyAlphaScale);
			const FVector4f BodyEdgeColor = bDebugShadowGeometry ? FVector4f(0.0f, 0.0f, 0.0f, 0.0f) : FVector4f(0.055f, 0.155f, 0.038f, 0.0f);
			TArray<FShadowBandSection> BodySections;
			BodySections.Reserve(8);
			BodySections.Add({0.0f, 5.0f, 13.0f, 0.58f});
			BodySections.Add({18.0f, 7.0f, 16.0f, 0.76f});
			BodySections.Add({48.0f, 8.0f, 19.0f, 0.86f});
			BodySections.Add({84.0f, 13.0f, 28.0f, 0.84f});
			BodySections.Add({118.0f, 20.0f, 40.0f, 0.76f});
			BodySections.Add({148.0f, 14.0f, 30.0f, 0.54f});
			BodySections.Add({174.0f, 8.0f, 20.0f, 0.36f});
			BodySections.Add({194.0f, 2.0f, 10.0f, 0.0f});
			AddSoftSilhouetteBand(BodySections, BodyCenterColor, BodyMidColor, BodyEdgeColor);
		}
	}
	else
	{
		const FVector4f ShadowColor(0.015f, 0.012f, 0.008f, 1.0f);
		const float RadiusX = 58.0f;
		const float RadiusY = 38.0f;
		const int32 Segments = 16;
		const FVertexID CenterVertex = Builder.AppendVertex(FVector::ZeroVector);
		for (int32 Index = 0; Index < Segments; ++Index)
		{
			const float AngleA = UE_TWO_PI * float(Index) / float(Segments);
			const float AngleB = UE_TWO_PI * float(Index + 1) / float(Segments);
			const FVertexID VA = Builder.AppendVertex(FVector(FMath::Cos(AngleA) * RadiusX, FMath::Sin(AngleA) * RadiusY, 0.0));
			const FVertexID VB = Builder.AppendVertex(FVector(FMath::Cos(AngleB) * RadiusX, FMath::Sin(AngleB) * RadiusY, 0.0));
			const FVertexInstanceID IC = Builder.AppendInstance(CenterVertex);
			const FVertexInstanceID IA = Builder.AppendInstance(VA);
			const FVertexInstanceID IB = Builder.AppendInstance(VB);
			Builder.SetInstanceNormal(IC, FVector::UpVector);
			Builder.SetInstanceNormal(IA, FVector::UpVector);
			Builder.SetInstanceNormal(IB, FVector::UpVector);
			Builder.SetInstanceTangentSpace(IC, FVector::UpVector, FVector::ForwardVector, 1.0f);
			Builder.SetInstanceTangentSpace(IA, FVector::UpVector, FVector::ForwardVector, 1.0f);
			Builder.SetInstanceTangentSpace(IB, FVector::UpVector, FVector::ForwardVector, 1.0f);
			Builder.SetInstanceUV(IC, FVector2D(0.5, 0.5));
			Builder.SetInstanceUV(IA, FVector2D(0.0, 0.0));
			Builder.SetInstanceUV(IB, FVector2D(1.0, 0.0));
			Builder.SetInstanceColor(IC, ShadowColor);
			Builder.SetInstanceColor(IA, ShadowColor);
			Builder.SetInstanceColor(IB, ShadowColor);
			Builder.AppendTriangle(IC, IA, IB, PolygonGroup);
		}
	}

	ContactShadowMesh = NewObject<UStaticMesh>(this, TEXT("ProphecyRuntimeContactShadow"), RF_Transient);
	if (!ContactShadowMesh)
	{
		return nullptr;
	}
	ContactShadowMesh->GetStaticMaterials().Add(FStaticMaterial(ContactShadowMaterial, TEXT("ContactShadow")));

	UStaticMesh::FBuildMeshDescriptionsParams Params;
	Params.bBuildSimpleCollision = false;
	Params.bCommitMeshDescription = false;
	Params.bFastBuild = true;
	Params.bAllowCpuAccess = false;
	TArray<const FMeshDescription*> MeshDescriptions;
	MeshDescriptions.Add(&MeshDescription);
	if (!ContactShadowMesh->BuildFromMeshDescriptions(MeshDescriptions, Params))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Failed to build runtime contact shadow mesh."));
		ContactShadowMesh = nullptr;
	}
	return ContactShadowMesh;
}

UStaticMesh* AProphecyNNCrowdBenchmarkActor::CreateLimbShadowMesh()
{
	if (LimbShadowMesh)
	{
		return LimbShadowMesh;
	}

	UMaterialInterface* ShadowMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassContactShadow.M_ProphecyGrassContactShadow"));
	if (!ShadowMaterial)
	{
		ShadowMaterial = CreateTintedMaterial(TEXT("ProphecyLimbShadowFallbackMaterial"), FLinearColor(0.018f, 0.075f, 0.018f, 1.0f));
	}

	FMeshDescription MeshDescription;
	FStaticMeshAttributes Attributes(MeshDescription);
	Attributes.Register();

	FMeshDescriptionBuilder Builder;
	Builder.SetMeshDescription(&MeshDescription);
	Builder.SetNumUVLayers(1);
	FPolygonGroupID PolygonGroup = Builder.AppendPolygonGroup(TEXT("LimbShadow"));

	auto AddVertex = [&Builder](const FVector& Position, const FVector2D& UV, const FVector4f& Color)
	{
		const FVector Normal = FVector::UpVector;
		const FVector Tangent = FVector::ForwardVector;
		const FVertexID Vertex = Builder.AppendVertex(Position);
		const FVertexInstanceID Instance = Builder.AppendInstance(Vertex);
		Builder.SetInstanceNormal(Instance, Normal);
		Builder.SetInstanceTangentSpace(Instance, Normal, Tangent, 1.0f);
		Builder.SetInstanceUV(Instance, UV);
		Builder.SetInstanceColor(Instance, Color);
		return Instance;
	};

	auto ScaledAlpha = [](const FVector4f& Color, float Scale)
	{
		return FVector4f(Color.X, Color.Y, Color.Z, Color.W * Scale);
	};

	const FVector4f CenterColor = bDebugShadowGeometry ? FVector4f(0.0f, 0.0f, 0.0f, 0.46f) : FVector4f(0.010f, 0.045f, 0.010f, 0.26f);
	const FVector4f MidColor = bDebugShadowGeometry ? FVector4f(0.0f, 0.0f, 0.0f, 0.26f) : FVector4f(0.018f, 0.080f, 0.016f, 0.14f);
	const FVector4f EdgeColor = bDebugShadowGeometry ? FVector4f(0.0f, 0.0f, 0.0f, 0.0f) : FVector4f(0.055f, 0.155f, 0.038f, 0.0f);
	constexpr float XSections[] = {-50.0f, -28.0f, 28.0f, 50.0f};
	constexpr float XAlpha[] = {0.0f, 1.0f, 1.0f, 0.0f};
	constexpr float YSections[] = {-50.0f, -24.0f, 0.0f, 24.0f, 50.0f};

	auto ColorForColumn = [&](int32 ColumnIndex, float AlphaScale)
	{
		if (ColumnIndex == 0 || ColumnIndex == UE_ARRAY_COUNT(YSections) - 1)
		{
			return ScaledAlpha(EdgeColor, AlphaScale);
		}
		if (ColumnIndex == 2)
		{
			return ScaledAlpha(CenterColor, AlphaScale);
		}
		return ScaledAlpha(MidColor, AlphaScale);
	};

	for (int32 XIndex = 0; XIndex < UE_ARRAY_COUNT(XSections) - 1; ++XIndex)
	{
		for (int32 YIndex = 0; YIndex < UE_ARRAY_COUNT(YSections) - 1; ++YIndex)
		{
			const FVector A(XSections[XIndex], YSections[YIndex], 0.0);
			const FVector B(XSections[XIndex + 1], YSections[YIndex], 0.0);
			const FVector C(XSections[XIndex], YSections[YIndex + 1], 0.0);
			const FVector D(XSections[XIndex + 1], YSections[YIndex + 1], 0.0);
			const FVector4f ColorA = ColorForColumn(YIndex, XAlpha[XIndex]);
			const FVector4f ColorB = ColorForColumn(YIndex, XAlpha[XIndex + 1]);
			const FVector4f ColorC = ColorForColumn(YIndex + 1, XAlpha[XIndex]);
			const FVector4f ColorD = ColorForColumn(YIndex + 1, XAlpha[XIndex + 1]);
			const FVector2D UVA(float(XIndex) / 3.0f, float(YIndex) / 4.0f);
			const FVector2D UVB(float(XIndex + 1) / 3.0f, float(YIndex) / 4.0f);
			const FVector2D UVC(float(XIndex) / 3.0f, float(YIndex + 1) / 4.0f);
			const FVector2D UVD(float(XIndex + 1) / 3.0f, float(YIndex + 1) / 4.0f);
			const FVertexInstanceID IA = AddVertex(A, UVA, ColorA);
			const FVertexInstanceID IB = AddVertex(B, UVB, ColorB);
			const FVertexInstanceID IC = AddVertex(C, UVC, ColorC);
			const FVertexInstanceID ID = AddVertex(D, UVD, ColorD);
			Builder.AppendTriangle(IA, IC, IB, PolygonGroup);
			Builder.AppendTriangle(IB, IC, ID, PolygonGroup);
		}
	}

	LimbShadowMesh = NewObject<UStaticMesh>(this, TEXT("ProphecyRuntimeLimbShadow"), RF_Transient);
	if (!LimbShadowMesh)
	{
		return nullptr;
	}
	LimbShadowMesh->GetStaticMaterials().Add(FStaticMaterial(ShadowMaterial, TEXT("LimbShadow")));

	UStaticMesh::FBuildMeshDescriptionsParams Params;
	Params.bBuildSimpleCollision = false;
	Params.bCommitMeshDescription = false;
	Params.bFastBuild = true;
	Params.bAllowCpuAccess = false;
	TArray<const FMeshDescription*> MeshDescriptions;
	MeshDescriptions.Add(&MeshDescription);
	if (!LimbShadowMesh->BuildFromMeshDescriptions(MeshDescriptions, Params))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Failed to build runtime limb shadow mesh."));
		LimbShadowMesh = nullptr;
	}
	return LimbShadowMesh;
}

void AProphecyNNCrowdBenchmarkActor::InitializeShadowLimbSegments()
{
	if (!Impl->ShadowLimbSegments.IsEmpty())
	{
		return;
	}

	Impl->ShadowLimbSegments.Reset();
	Impl->ShadowLimbHalfWidthsCm.Reset();
	auto AddShadowSegment = [this](const TCHAR* ParentName, const TCHAR* ChildName, float HalfWidthCm)
	{
		const int32 ParentIndex = Impl->BodyNames.Find(FName(ParentName));
		const int32 ChildIndex = Impl->BodyNames.Find(FName(ChildName));
		if (ParentIndex != INDEX_NONE && ChildIndex != INDEX_NONE)
		{
			Impl->ShadowLimbSegments.Add(FIntPoint(ParentIndex, ChildIndex));
			Impl->ShadowLimbHalfWidthsCm.Add(HalfWidthCm);
		}
	};

	AddShadowSegment(TEXT("pelvis"), TEXT("spine_05"), 24.0f);
	AddShadowSegment(TEXT("spine_05"), TEXT("head"), 14.0f);
	AddShadowSegment(TEXT("spine_05"), TEXT("upperarm_l"), 9.0f);
	AddShadowSegment(TEXT("upperarm_l"), TEXT("lowerarm_l"), 8.0f);
	AddShadowSegment(TEXT("lowerarm_l"), TEXT("hand_l"), 8.0f);
	AddShadowSegment(TEXT("spine_05"), TEXT("upperarm_r"), 9.0f);
	AddShadowSegment(TEXT("upperarm_r"), TEXT("lowerarm_r"), 8.0f);
	AddShadowSegment(TEXT("lowerarm_r"), TEXT("hand_r"), 8.0f);
	AddShadowSegment(TEXT("pelvis"), TEXT("thigh_l"), 15.0f);
	AddShadowSegment(TEXT("thigh_l"), TEXT("calf_l"), 13.0f);
	AddShadowSegment(TEXT("calf_l"), TEXT("foot_l"), 12.0f);
	AddShadowSegment(TEXT("foot_l"), TEXT("ball_l"), 14.0f);
	AddShadowSegment(TEXT("pelvis"), TEXT("thigh_r"), 15.0f);
	AddShadowSegment(TEXT("thigh_r"), TEXT("calf_r"), 13.0f);
	AddShadowSegment(TEXT("calf_r"), TEXT("foot_r"), 12.0f);
	AddShadowSegment(TEXT("foot_r"), TEXT("ball_r"), 14.0f);
}

void AProphecyNNCrowdBenchmarkActor::SpawnContactShadowComponents()
{
	if (IsFullDynamicShadowVariant(ContactShadowVariant) && !bDebugShadowGeometry)
	{
		return;
	}
	if (!bDebugShadowGeometry && (IsRootContactShadowVariant(ContactShadowVariant) || IsLimbContactShadowVariant(ContactShadowVariant)))
	{
		return;
	}

	if (!IsLimbContactShadowVariant(ContactShadowVariant))
	{
		UStaticMesh* Mesh = CreateContactShadowMesh();
		if (!Mesh)
		{
			return;
		}

		ContactShadowComponent = NewObject<UInstancedStaticMeshComponent>(this);
		ContactShadowComponent->SetStaticMesh(Mesh);
		ContactShadowComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ContactShadowComponent->SetGenerateOverlapEvents(false);
		ContactShadowComponent->SetCastShadow(false);
		ContactShadowComponent->SetCastContactShadow(false);
		ContactShadowComponent->SetAffectDistanceFieldLighting(false);
		ContactShadowComponent->SetAffectDynamicIndirectLighting(false);
		ContactShadowComponent->SetVisibleInRayTracing(false);
		ContactShadowComponent->SetReceivesDecals(false);
		ContactShadowComponent->SetMobility(EComponentMobility::Movable);
		ContactShadowComponent->SetCullDistances(0, bSpawnGrass ? 16000 : 9000);
		ContactShadowComponent->TranslucencySortPriority = bSpawnGrass ? 1 : 0;
		ContactShadowComponent->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(ContactShadowComponent);
		ContactShadowComponent->RegisterComponent();
		ContactShadowComponent->PreAllocateInstancesMemory(CrowdSize);

		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			ContactShadowComponent->AddInstance(FTransform::Identity);
		}
	}

	if (!IsLimbContactShadowVariant(ContactShadowVariant))
	{
		return;
	}
	if (FloorMaterialInstance && !bSpawnGrass && !bDebugShadowGeometry)
	{
		return;
	}

	InitializeShadowLimbSegments();

	UStaticMesh* LimbMesh = CreateLimbShadowMesh();
	if (!LimbMesh || Impl->ShadowLimbSegments.Num() == 0)
	{
		return;
	}

	LimbShadowComponent = NewObject<UInstancedStaticMeshComponent>(this);
	LimbShadowComponent->SetStaticMesh(LimbMesh);
	LimbShadowComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	LimbShadowComponent->SetGenerateOverlapEvents(false);
	LimbShadowComponent->SetCastShadow(false);
	LimbShadowComponent->SetCastContactShadow(false);
	LimbShadowComponent->SetAffectDistanceFieldLighting(false);
	LimbShadowComponent->SetAffectDynamicIndirectLighting(false);
	LimbShadowComponent->SetVisibleInRayTracing(false);
	LimbShadowComponent->SetReceivesDecals(false);
	LimbShadowComponent->SetMobility(EComponentMobility::Movable);
	LimbShadowComponent->SetCullDistances(0, bSpawnGrass ? 16000 : 9000);
	LimbShadowComponent->TranslucencySortPriority = bSpawnGrass ? 2 : 1;
	LimbShadowComponent->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
	AddInstanceComponent(LimbShadowComponent);
	LimbShadowComponent->RegisterComponent();

	const int32 InstanceCount = Impl->ShadowLimbSegments.Num() * CrowdSize;
	LimbShadowComponent->PreAllocateInstancesMemory(InstanceCount);
	for (int32 InstanceIndex = 0; InstanceIndex < InstanceCount; ++InstanceIndex)
	{
		LimbShadowComponent->AddInstance(FTransform::Identity);
	}
}

void AProphecyNNCrowdBenchmarkActor::ConfigureBloodMaskMaterials()
{
	if (!BloodMaskTexture)
	{
		return;
	}

	auto ConfigureMaterial = [this](UMaterialInstanceDynamic* Material, bool bGrassMaterial)
	{
		if (!Material)
		{
			return;
		}

		Material->SetTextureParameterValue(TEXT("BloodMask"), BloodMaskTexture);
		Material->SetVectorParameterValue(TEXT("BloodMaskCenter"), FLinearColor(Impl->BloodMaskCenter.X, Impl->BloodMaskCenter.Y, 0.0f, 0.0f));
		Material->SetScalarParameterValue(TEXT("BloodMaskInvExtent"), 1.0f / (Impl->BloodMaskHalfExtent * 2.0f));
		Material->SetVectorParameterValue(TEXT("BloodColor"), FLinearColor(0.235f, 0.016f, 0.010f, 1.0f));
		Material->SetVectorParameterValue(TEXT("BloodDarkColor"), FLinearColor(0.070f, 0.003f, 0.003f, 1.0f));
		Material->SetVectorParameterValue(TEXT("BloodGrassRootColor"), FLinearColor(0.065f, 0.0012f, 0.0022f, 1.0f));
		Material->SetVectorParameterValue(TEXT("BloodGrassColor"), FLinearColor(0.235f, 0.004f, 0.009f, 1.0f));
		Material->SetScalarParameterValue(TEXT("BloodStrength"), bGrassMaterial ? 0.0f : 0.88f);
		Material->SetScalarParameterValue(TEXT("BloodWetStrength"), bGrassMaterial ? 0.0f : 0.58f);
		Material->SetScalarParameterValue(TEXT("BloodGrassStrength"), bGrassMaterial ? 1.02f : 0.0f);
	};

	ConfigureMaterial(FloorMaterialInstance.Get(), false);
	ConfigureMaterial(GrassMaterialInstance.Get(), true);
}

void AProphecyNNCrowdBenchmarkActor::InitializeBloodMask(const FVector2D& FieldCenter, float FieldHalfExtent)
{
	Impl->BloodMaskCenter = FieldCenter;
	Impl->BloodMaskHalfExtent = FMath::Max(FieldHalfExtent, 1.0f);
	Impl->BloodMaskSize = 1024;
	const int32 PixelCount = Impl->BloodMaskSize * Impl->BloodMaskSize;
	Impl->BloodMaskValues.SetNumZeroed(PixelCount);
	Impl->BloodMaskCoreValues.SetNumZeroed(PixelCount);
	Impl->BloodMaskPixels.SetNumZeroed(PixelCount);

	if (!BloodMaskTexture)
	{
		BloodMaskTexture = UTexture2D::CreateTransient(Impl->BloodMaskSize, Impl->BloodMaskSize, PF_B8G8R8A8, TEXT("ProphecyBloodMask"));
		if (!BloodMaskTexture)
		{
			return;
		}
		BloodMaskTexture->SRGB = false;
		BloodMaskTexture->Filter = TF_Bilinear;
		BloodMaskTexture->AddressX = TA_Clamp;
		BloodMaskTexture->AddressY = TA_Clamp;
		BloodMaskTexture->UpdateResource();
	}

	ConfigureBloodMaskMaterials();
	Impl->bBloodMaskDirty = true;
	UploadBloodMask();
}

void AProphecyNNCrowdBenchmarkActor::ClearBloodMask()
{
	for (float& Value : Impl->BloodMaskValues)
	{
		Value = 0.0f;
	}
	for (float& Value : Impl->BloodMaskCoreValues)
	{
		Value = 0.0f;
	}
	Impl->bBloodMaskDirty = true;
}

void AProphecyNNCrowdBenchmarkActor::StampBloodDropMask(const FVector2D& Center, float RadiusXCm, float RadiusYCm, float RotationRadians, float Strength, float CoreStrength)
{
	if (Impl->BloodMaskValues.IsEmpty() || Impl->BloodMaskCoreValues.Num() != Impl->BloodMaskValues.Num())
	{
		return;
	}

	const int32 Size = Impl->BloodMaskSize;
	const float RadiusX = FMath::Max(RadiusXCm, 1.0f);
	const float RadiusY = FMath::Max(RadiusYCm, 1.0f);
	const float MaxRadius = FMath::Max(RadiusX, RadiusY);
	const float CmPerPixel = (Impl->BloodMaskHalfExtent * 2.0f) / float(Size);
	auto WorldToPixel = [this, Size](const FVector2D& World)
	{
		const float U = (World.X - (Impl->BloodMaskCenter.X - Impl->BloodMaskHalfExtent)) / (Impl->BloodMaskHalfExtent * 2.0f);
		const float V = (World.Y - (Impl->BloodMaskCenter.Y - Impl->BloodMaskHalfExtent)) / (Impl->BloodMaskHalfExtent * 2.0f);
		return FIntPoint(FMath::FloorToInt(U * float(Size)), FMath::FloorToInt(V * float(Size)));
	};
	const FIntPoint MinPixel = WorldToPixel(Center - FVector2D(MaxRadius, MaxRadius));
	const FIntPoint MaxPixel = WorldToPixel(Center + FVector2D(MaxRadius, MaxRadius));
	if (MaxPixel.X < 0 || MaxPixel.Y < 0 || MinPixel.X > Size - 1 || MinPixel.Y > Size - 1)
	{
		return;
	}

	const int32 X0 = FMath::Clamp(MinPixel.X, 0, Size - 1);
	const int32 Y0 = FMath::Clamp(MinPixel.Y, 0, Size - 1);
	const int32 X1 = FMath::Clamp(MaxPixel.X, 0, Size - 1);
	const int32 Y1 = FMath::Clamp(MaxPixel.Y, 0, Size - 1);
	const float CosR = FMath::Cos(RotationRadians);
	const float SinR = FMath::Sin(RotationRadians);
	auto Smooth01 = [](float T)
	{
		T = FMath::Clamp(T, 0.0f, 1.0f);
		return T * T * (3.0f - 2.0f * T);
	};

	for (int32 Y = Y0; Y <= Y1; ++Y)
	{
		const float WorldY = Impl->BloodMaskCenter.Y - Impl->BloodMaskHalfExtent + (float(Y) + 0.5f) * CmPerPixel;
		for (int32 X = X0; X <= X1; ++X)
		{
			const float WorldX = Impl->BloodMaskCenter.X - Impl->BloodMaskHalfExtent + (float(X) + 0.5f) * CmPerPixel;
			const FVector2D Offset(WorldX - Center.X, WorldY - Center.Y);
			const float LocalX = Offset.X * CosR + Offset.Y * SinR;
			const float LocalY = -Offset.X * SinR + Offset.Y * CosR;
			const float NormalizedDistance = FMath::Sqrt(FMath::Square(LocalX / RadiusX) + FMath::Square(LocalY / RadiusY));
			if (NormalizedDistance >= 1.0f)
			{
				continue;
			}

			const float EdgeSoft = 1.0f - Smooth01((NormalizedDistance - 0.52f) / 0.48f);
			const float GrainA = 0.5f + 0.5f * FMath::Sin(WorldX * 0.021f + WorldY * 0.037f + Center.X * 0.003f);
			const float GrainB = 0.5f + 0.5f * FMath::Sin(WorldX * 0.063f - WorldY * 0.029f + Center.Y * 0.004f);
			const float Breakup = FMath::Clamp(0.74f + 0.20f * GrainA + 0.16f * GrainB, 0.0f, 1.0f);
			const float MaskValue = FMath::Clamp(Strength * EdgeSoft * Breakup, 0.0f, 1.0f);
			const float CoreValue = FMath::Clamp(CoreStrength * (1.0f - Smooth01((NormalizedDistance - 0.18f) / 0.54f)) * Breakup, 0.0f, 1.0f);
			const int32 Index = Y * Size + X;
			Impl->BloodMaskValues[Index] = FMath::Max(Impl->BloodMaskValues[Index], MaskValue);
			Impl->BloodMaskCoreValues[Index] = FMath::Max(Impl->BloodMaskCoreValues[Index], CoreValue);
		}
	}

	Impl->bBloodMaskDirty = true;
}

void AProphecyNNCrowdBenchmarkActor::GeneratePreviewBloodStains(float RadiusScale, float Strength)
{
	ClearBloodMask();

	const float Scale = FMath::Clamp(RadiusScale, 0.35f, 3.0f);
	const float BaseStrength = FMath::Clamp(Strength, 0.05f, 1.0f);
	struct FPreviewBloodPool
	{
		FVector2D Center;
		float RadiusX;
		float RadiusY;
		float Rotation;
		float StrengthScale;
	};
	const FPreviewBloodPool Pools[] = {
		{ FVector2D(-520.0f, -1150.0f), 260.0f, 210.0f, 0.28f, 0.94f },
		{ FVector2D(260.0f, -610.0f), 360.0f, 250.0f, -0.15f, 1.00f },
		{ FVector2D(780.0f, 120.0f), 250.0f, 190.0f, 0.64f, 0.82f },
		{ FVector2D(-900.0f, 620.0f), 300.0f, 215.0f, -0.42f, 0.78f },
		{ FVector2D(120.0f, 1220.0f), 430.0f, 250.0f, 0.10f, 0.64f }
	};

	FRandomStream Random(91427);
	for (const FPreviewBloodPool& Pool : Pools)
	{
		StampBloodDropMask(Pool.Center, Pool.RadiusX * Scale, Pool.RadiusY * Scale, Pool.Rotation, BaseStrength * Pool.StrengthScale, BaseStrength * 0.86f * Pool.StrengthScale);
		for (int32 Index = 0; Index < 28; ++Index)
		{
			const float Angle = Random.FRandRange(0.0f, UE_TWO_PI);
			const float Distance = Random.FRandRange(90.0f, 780.0f) * Scale;
			const FVector2D SplatterCenter = Pool.Center + FVector2D(FMath::Cos(Angle), FMath::Sin(Angle)) * Distance;
			const float Radius = Random.FRandRange(18.0f, 72.0f) * Scale;
			const float Stretch = Random.FRandRange(0.55f, 1.85f);
			StampBloodDropMask(
				SplatterCenter,
				Radius * Stretch,
				Radius,
				Angle + Random.FRandRange(-0.55f, 0.55f),
				BaseStrength * Random.FRandRange(0.34f, 0.74f),
				BaseStrength * Random.FRandRange(0.12f, 0.42f));
		}
	}

	for (int32 Index = 0; Index < 42; ++Index)
	{
		const float T = float(Index) / 41.0f;
		const FVector2D TrailCenter(
			FMath::Lerp(-1120.0f, 960.0f, T) + Random.FRandRange(-150.0f, 150.0f),
			FMath::Lerp(-1450.0f, 1650.0f, T) + Random.FRandRange(-95.0f, 95.0f));
		const float Radius = Random.FRandRange(16.0f, 54.0f) * Scale;
		StampBloodDropMask(TrailCenter, Radius * Random.FRandRange(0.8f, 1.8f), Radius, Random.FRandRange(-UE_PI, UE_PI), BaseStrength * Random.FRandRange(0.22f, 0.58f), BaseStrength * Random.FRandRange(0.08f, 0.28f));
	}

	UploadBloodMask();
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Generated preview blood mask: size=%d half_extent=%.0fcm radius_scale=%.2f strength=%.2f"), Impl->BloodMaskSize, Impl->BloodMaskHalfExtent, Scale, BaseStrength);
}

void AProphecyNNCrowdBenchmarkActor::UploadBloodMask()
{
	if (!BloodMaskTexture || !Impl->bBloodMaskDirty)
	{
		return;
	}

	const int32 Size = Impl->BloodMaskSize;
	const int32 PixelCount = Size * Size;
	if (Impl->BloodMaskValues.Num() != PixelCount || Impl->BloodMaskCoreValues.Num() != PixelCount || Impl->BloodMaskPixels.Num() != PixelCount)
	{
		return;
	}

	for (int32 Index = 0; Index < PixelCount; ++Index)
	{
		const uint8 MaskValue = uint8(FMath::Clamp(Impl->BloodMaskValues[Index], 0.0f, 1.0f) * 255.0f);
		const uint8 CoreValue = uint8(FMath::Clamp(Impl->BloodMaskCoreValues[Index], 0.0f, 1.0f) * 255.0f);
		Impl->BloodMaskPixels[Index] = FColor(MaskValue, CoreValue, 0, 255);
	}

	const int32 ByteCount = PixelCount * sizeof(FColor);
	uint8* UploadData = static_cast<uint8*>(FMemory::Malloc(ByteCount));
	FMemory::Memcpy(UploadData, Impl->BloodMaskPixels.GetData(), ByteCount);
	FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, Size, Size);
	BloodMaskTexture->UpdateTextureRegions(
		0,
		1,
		Region,
		uint32(Size * sizeof(FColor)),
		uint32(sizeof(FColor)),
		UploadData,
		[](uint8* SrcData, const FUpdateTextureRegion2D* Regions)
		{
			FMemory::Free(SrcData);
			delete Regions;
		});
	Impl->bBloodMaskDirty = false;
}

void AProphecyNNCrowdBenchmarkActor::InitializeGrassShadowMask(const FVector2D& FieldCenter, float FieldHalfExtent)
{
	if (!GrassMaterialInstance)
	{
		return;
	}

	Impl->GrassShadowMaskCenter = FieldCenter;
	Impl->GrassShadowMaskHalfExtent = FMath::Max(FieldHalfExtent, 1.0f);
	Impl->GrassShadowMaskSize = bGrassDiagnosticMode ? 1024 : 512;
	const int32 PixelCount = Impl->GrassShadowMaskSize * Impl->GrassShadowMaskSize;
	Impl->GrassShadowMaskValues.SetNumZeroed(PixelCount);
	Impl->GrassShadowMaskPixels.SetNumZeroed(PixelCount);
	Impl->LastGrassShadowMaskNNStep = -1;
	if (IsLimbContactShadowVariant(ContactShadowVariant) || IsFullDynamicShadowVariant(ContactShadowVariant))
	{
		InitializeShadowLimbSegments();
	}

	if (!GrassShadowMaskTexture)
	{
		GrassShadowMaskTexture = UTexture2D::CreateTransient(Impl->GrassShadowMaskSize, Impl->GrassShadowMaskSize, PF_B8G8R8A8, TEXT("ProphecyGrassShadowMask"));
		if (!GrassShadowMaskTexture)
		{
			return;
		}
		GrassShadowMaskTexture->SRGB = false;
		GrassShadowMaskTexture->Filter = TF_Bilinear;
		GrassShadowMaskTexture->AddressX = TA_Clamp;
		GrassShadowMaskTexture->AddressY = TA_Clamp;
		GrassShadowMaskTexture->UpdateResource();
	}

	const bool bDiagnosticMask = bGrassDiagnosticMode || bShadowMaskDiagnostic;
	const float GrassMaskStrength = bDiagnosticMask ? 1.0f : (IsFullDynamicShadowVariant(ContactShadowVariant) ? 0.86f : (IsRootContactShadowVariant(ContactShadowVariant) ? 0.70f : 0.76f));
	const FLinearColor GrassMaskTint = bDiagnosticMask
		? FLinearColor::Black
		: (IsFullDynamicShadowVariant(ContactShadowVariant)
			? FLinearColor(0.13f, 0.26f, 0.10f, 1.0f)
			: (IsRootContactShadowVariant(ContactShadowVariant)
				? FLinearColor(0.17f, 0.32f, 0.13f, 1.0f)
				: FLinearColor(0.18f, 0.32f, 0.13f, 1.0f)));
	auto ConfigureGrassShadowMaterial = [&](UMaterialInstanceDynamic* Material)
	{
		if (!Material)
		{
			return;
		}
		Material->SetTextureParameterValue(TEXT("GrassShadowMask"), GrassShadowMaskTexture);
		Material->SetVectorParameterValue(TEXT("GrassShadowMaskCenter"), FLinearColor(FieldCenter.X, FieldCenter.Y, 0.0f, 0.0f));
		Material->SetScalarParameterValue(TEXT("GrassShadowMaskInvExtent"), 1.0f / (Impl->GrassShadowMaskHalfExtent * 2.0f));
		Material->SetScalarParameterValue(TEXT("GrassShadowMaskStrength"), GrassMaskStrength);
		Material->SetVectorParameterValue(TEXT("GrassShadowMaskTint"), GrassMaskTint);
	};
	ConfigureGrassShadowMaterial(GrassMaterialInstance);
	ApplyGrassWindMaterialParameters();
	BakeStaticTreeShadowMasks();
	UpdateGrassShadowMask();
}

void AProphecyNNCrowdBenchmarkActor::SpawnGrassField()
{
	Impl->ActiveGrassRenderer = TEXT("HISM");
	Impl->NiagaraComponentCount = 0;
	NiagaraGrassComponents.Reset();

	UStaticMesh* StandardMesh = CreateGrassClusterMesh();
	UStaticMesh* DenseMesh = bGrassDiagnosticMode ? StandardMesh : CreateDenseGrassClusterMesh();
	if (!StandardMesh)
	{
		return;
	}
	DenseMesh = DenseMesh ? DenseMesh : StandardMesh;

	GrassComponents.Reset();
	Impl->GrassInstanceCount = 0;
	Impl->GrassDenseInstanceCount = 0;
	Impl->GrassVisualBladeCount = 0;
	const FVector FieldCenter(0.0, 700.0, 0.0);
	const float FieldHalfExtent = ProphecyGrassHorizonRadiusCm;
	constexpr float DiagnosticDenseGrassRadiusCm = 4200.0f;
	constexpr float DiagnosticGrassSpacingCm = 72.0f;
	constexpr float DiagnosticGrassCellPadCm = 1800.0f;
	const float GrassShadowHalfExtent = bGrassDiagnosticMode
		? DiagnosticDenseGrassRadiusCm
		: (bSpawnTrees ? ProphecyTreeShadowMaskHalfExtentCm : 8000.0f);
	InitializeGrassShadowMask(FVector2D(FieldCenter.X, FieldCenter.Y), GrassShadowHalfExtent);
	const int32 CellsPerAxis = 22;
	const float CellSize = FieldHalfExtent * 2.0f / float(CellsPerAxis);
	const int32 GrassSeed = 334703;
	auto Smooth01 = [](float T)
	{
		T = FMath::Clamp(T, 0.0f, 1.0f);
		return T * T * (3.0f - 2.0f * T);
	};
	const TCHAR* Cmd = FCommandLine::Get();
	float FarTargetSpacingCm = ProphecyGrassFarTargetSpacingCm;
	float FarCoverage = ProphecyGrassFarCoverage;
	float FarScaleXYMin = ProphecyGrassFarScaleXYMin;
	float FarScaleXYMax = ProphecyGrassFarScaleXYMax;
	float FarScaleZMin = ProphecyGrassFarScaleZMin;
	float FarScaleZMax = ProphecyGrassFarScaleZMax;
	float DenseMeshRadiusCm = ProphecyGrassDenseMeshRadiusCm;
	FParse::Value(Cmd, TEXT("ProphecyNNGrassFarTargetSpacing="), FarTargetSpacingCm);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassFarCoverage="), FarCoverage);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassFarScaleXYMin="), FarScaleXYMin);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassFarScaleXYMax="), FarScaleXYMax);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassFarScaleZMin="), FarScaleZMin);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassFarScaleZMax="), FarScaleZMax);
	FParse::Value(Cmd, TEXT("ProphecyNNGrassDenseMeshRadius="), DenseMeshRadiusCm);
	FarTargetSpacingCm = FMath::Clamp(FarTargetSpacingCm, 180.0f, 1200.0f);
	FarCoverage = FMath::Clamp(FarCoverage, 0.05f, 1.0f);
	FarScaleXYMin = FMath::Clamp(FarScaleXYMin, 0.70f, 4.00f);
	FarScaleXYMax = FMath::Clamp(FarScaleXYMax, FarScaleXYMin, 5.50f);
	FarScaleZMin = FMath::Clamp(FarScaleZMin, 0.20f, 1.60f);
	FarScaleZMax = FMath::Clamp(FarScaleZMax, FarScaleZMin, 1.80f);
	DenseMeshRadiusCm = FMath::Clamp(DenseMeshRadiusCm, 2400.0f, 18000.0f);

	for (int32 CellY = 0; CellY < CellsPerAxis; ++CellY)
	{
		for (int32 CellX = 0; CellX < CellsPerAxis; ++CellX)
		{
			const float MinX = -FieldHalfExtent + float(CellX) * CellSize;
			const float MinY = -FieldHalfExtent + float(CellY) * CellSize;
			const float MaxX = MinX + CellSize;
			const float MaxY = MinY + CellSize;
			const FVector2D CellCenter((MinX + MaxX) * 0.5f, (MinY + MaxY) * 0.5f);
			const float CellDistance = CellCenter.Length();
			if (CellDistance > ProphecyGrassHorizonRadiusCm + CellSize)
			{
				continue;
			}

			const bool bUseDenseMesh = !bGrassDiagnosticMode && CellDistance <= DenseMeshRadiusCm + CellSize * 0.5f;
			const int32 ComponentBladesPerTile = bUseDenseMesh ? ProphecyGrassDenseBladesPerTile : ProphecyGrassBladesPerTile;
			const float CandidateSpacing = bGrassDiagnosticMode && CellDistance <= DiagnosticDenseGrassRadiusCm + DiagnosticGrassCellPadCm ? DiagnosticGrassSpacingCm : 105.0f;
			UHierarchicalInstancedStaticMeshComponent* Component = NewObject<UHierarchicalInstancedStaticMeshComponent>(this);
			Component->SetStaticMesh(bUseDenseMesh ? DenseMesh : StandardMesh);
			if (GrassMaterialInstance)
			{
				Component->SetMaterial(0, GrassMaterialInstance);
			}
			Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Component->SetGenerateOverlapEvents(false);
			Component->SetCastShadow(false);
			Component->SetCastContactShadow(false);
			Component->SetAffectDistanceFieldLighting(false);
			Component->SetAffectDynamicIndirectLighting(false);
			Component->SetVisibleInRayTracing(false);
			Component->SetReceivesDecals(false);
			Component->SetMobility(EComponentMobility::Static);
			Component->BoundsScale = bGrassWind ? (bGrassWindDiagnostic ? 5.0f : 1.25f) : 1.0f;
			Component->SetCullDistances(42000, 56000);
			Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
			AddInstanceComponent(Component);
			Component->RegisterComponent();

			const int32 PerAxis = FMath::Max(1, FMath::CeilToInt(CellSize / CandidateSpacing));
			Component->PreAllocateInstancesMemory(PerAxis * PerAxis);

			FRandomStream CellRandom(GrassSeed + CellX * 928371 + CellY * 12377);
			int32 CellInstances = 0;
			for (int32 Y = 0; Y < PerAxis; ++Y)
			{
				for (int32 X = 0; X < PerAxis; ++X)
				{
					const float LocalX = MinX + (float(X) + 0.5f) * CellSize / float(PerAxis);
					const float LocalY = MinY + (float(Y) + 0.5f) * CellSize / float(PerAxis);
					const float JitterX = CellRandom.FRandRange(-0.42f, 0.42f) * CandidateSpacing;
					const float JitterY = CellRandom.FRandRange(-0.42f, 0.42f) * CandidateSpacing;
					const FVector2D Offset(LocalX + JitterX, LocalY + JitterY);
					const float Distance = Offset.Length();
					if (Distance > ProphecyGrassHorizonRadiusCm)
					{
						continue;
					}

					const float FarT = Smooth01((Distance - ProphecyGrassFarRadiusCm) / (ProphecyGrassHorizonRadiusCm - ProphecyGrassFarRadiusCm));
					const float NearT = Smooth01((Distance - ProphecyGrassNearRadiusCm) / (ProphecyGrassFarRadiusCm - ProphecyGrassNearRadiusCm));
					const float FarLodT = Smooth01((Distance - (ProphecyGrassFarRadiusCm - 2600.0f)) / 7200.0f);
					const float TargetSpacing = bGrassDiagnosticMode && Distance <= DiagnosticDenseGrassRadiusCm
						? DiagnosticGrassSpacingCm
						: FMath::Lerp(
							FMath::Lerp(105.0f, 160.0f, NearT),
							FMath::Lerp(170.0f, FarTargetSpacingCm, FarT),
							FarLodT);
					const float DistanceCoverage = Distance <= ProphecyGrassFarRadiusCm ? 1.0f : FMath::Lerp(1.0f, FarCoverage, FarT);
					const float DensityKeep = FMath::Clamp(FMath::Square(CandidateSpacing / TargetSpacing) * DistanceCoverage, 0.0f, 1.0f);
					if (CellRandom.FRand() > DensityKeep)
					{
						continue;
					}

					const float Yaw = CellRandom.FRandRange(0.0f, 360.0f);
					const float ScaleRollXY = CellRandom.FRand();
					const float ScaleRollZ = CellRandom.FRand();
					const float NearScaleXY = FMath::Lerp(0.88f, 1.26f, ScaleRollXY);
					const float NearScaleZ = FMath::Lerp(0.82f, 1.18f, ScaleRollZ);
					const float FarScaleXY = FMath::Lerp(FMath::Lerp(1.10f, FarScaleXYMin, FarT), FMath::Lerp(1.80f, FarScaleXYMax, FarT), ScaleRollXY);
					const float FarScaleZ = FMath::Lerp(FMath::Lerp(0.80f, FarScaleZMin, FarT), FMath::Lerp(1.04f, FarScaleZMax, FarT), ScaleRollZ);
					const float ScaleXY = FMath::Lerp(NearScaleXY, FarScaleXY, FarLodT);
					const float ScaleZ = FMath::Lerp(NearScaleZ, FarScaleZ, FarLodT);
					const FTransform InstanceTransform(
						FRotator(0.0, Yaw, 0.0),
						FieldCenter + FVector(Offset.X, Offset.Y, 0.0),
						FVector(ScaleXY, ScaleXY, ScaleZ));
					Component->AddInstance(InstanceTransform);
					++CellInstances;
				}
			}

			if (CellInstances > 0)
			{
				if (bHideGrassForShadowInspection)
				{
					Component->SetVisibility(false, true);
					Component->SetHiddenInGame(true);
					Component->SetCullDistances(0, 1);
				}

				GrassComponents.Add(Component);
				Impl->GrassInstanceCount += CellInstances;
				Impl->GrassDenseInstanceCount += bUseDenseMesh ? CellInstances : 0;
				Impl->GrassVisualBladeCount += int64(CellInstances) * int64(ComponentBladesPerTile);
			}
			else
			{
				Component->DestroyComponent();
			}
		}
	}

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Spawned grass field: components=%d patch_instances=%d dense_patch_instances=%d visual_blades=%lld standard_blades_per_tile=%d dense_blades_per_tile=%d dense_fillers_per_tile=%d dense_mesh_radius=%.0fcm tile_size=%.0fcm near_radius=%.0fcm far_radius=%.0fcm horizon_radius=%.0fcm unified_wind=%d diagnostic=%d"),
		GrassComponents.Num(),
		Impl->GrassInstanceCount,
		Impl->GrassDenseInstanceCount,
		Impl->GrassVisualBladeCount,
		ProphecyGrassBladesPerTile,
		ProphecyGrassDenseBladesPerTile,
		ProphecyGrassDenseFillersPerTile,
		DenseMeshRadiusCm,
		ProphecyGrassTileSizeCm,
		ProphecyGrassNearRadiusCm,
		ProphecyGrassFarRadiusCm,
		ProphecyGrassHorizonRadiusCm,
		bGrassWind ? 1 : 0,
		bGrassDiagnosticMode ? 1 : 0);
}

void AProphecyNNCrowdBenchmarkActor::SpawnDistantGrassHills()
{
	if (DistantHillsComponent || bHideGrassForShadowInspection)
	{
		return;
	}

	UStaticMesh* HillsMesh = CreateDistantGrassHillsMesh();
	if (!HillsMesh)
	{
		return;
	}

	const bool bHillShadeDiagnostic = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNHillShadeDiagnostic"));
	const bool bHillVertexColorDiagnostic = FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNHillVertexColorDiagnostic"));
	UMaterialInterface* HillsMaterial = bHillVertexColorDiagnostic
		? LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial.VertexColorMaterial"))
		: LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassTerrainShared.M_ProphecyGrassTerrainShared"));
	if (bHillVertexColorDiagnostic && !HillsMaterial)
	{
		HillsMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassTerrainShared.M_ProphecyGrassTerrainShared"));
	}
	if (!HillsMaterial)
	{
		HillsMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassFarHills.M_ProphecyGrassFarHills"));
	}
	if (!HillsMaterial)
	{
		HillsMaterial = CreateTintedMaterial(TEXT("ProphecyDistantHillsMaterial"), ProphecyGrassGroundBaseColor);
	}
	if (HillsMaterial && !bHillShadeDiagnostic && !bHillVertexColorDiagnostic)
	{
		DistantHillsMaterialInstance = UMaterialInstanceDynamic::Create(HillsMaterial, this);
	}
	if (!bHillShadeDiagnostic && !bHillVertexColorDiagnostic)
	{
		InitializeDistantTerrainTexture();
	}

	DistantHillsComponent = NewObject<UStaticMeshComponent>(this);
	if (!DistantHillsComponent)
	{
		return;
	}

	DistantHillsComponent->SetStaticMesh(HillsMesh);
	if (DistantHillsMaterialInstance)
	{
		DistantHillsComponent->SetMaterial(0, DistantHillsMaterialInstance);
	}
	else if (HillsMaterial)
	{
		DistantHillsComponent->SetMaterial(0, HillsMaterial);
	}
	DistantHillsComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	DistantHillsComponent->SetGenerateOverlapEvents(false);
	DistantHillsComponent->SetCanEverAffectNavigation(false);
	DistantHillsComponent->SetCastShadow(false);
	DistantHillsComponent->SetCastContactShadow(false);
	DistantHillsComponent->SetAffectDistanceFieldLighting(false);
	DistantHillsComponent->SetAffectDynamicIndirectLighting(false);
	DistantHillsComponent->SetVisibleInRayTracing(false);
	DistantHillsComponent->SetReceivesDecals(false);
	DistantHillsComponent->SetCullDistance(150000.0f);
	DistantHillsComponent->SetMobility(EComponentMobility::Static);
	DistantHillsComponent->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
	AddInstanceComponent(DistantHillsComponent);
	DistantHillsComponent->RegisterComponent();

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Spawned distant grass hills: segments=%d rings=%d triangles=%d inner_radius=%.0fcm rise_start=%.0fcm outer_radius=%.0fcm material=%s"),
		ProphecyDistantHillSegments,
		ProphecyDistantHillRings,
		(ProphecyDistantHillRings - 1) * ProphecyDistantHillSegments * 2,
		ProphecyDistantHillInnerRadiusCm,
		ProphecyDistantHillRiseStartRadiusCm,
		ProphecyDistantHillOuterRadiusCm,
		HillsMaterial ? *HillsMaterial->GetPathName() : TEXT("None"));
}

void AProphecyNNCrowdBenchmarkActor::SpawnTreeField()
{
	if (TreeInstanceCount <= 0 && !bCenterTreeDiagnostic)
	{
		return;
	}

	const FString TreeSourceName = TreeSource.TrimStartAndEnd();
	if (TreeSourceName.Equals(TEXT("PCG"), ESearchCase::IgnoreCase) ||
		TreeSourceName.Equals(TEXT("PCGSample"), ESearchCase::IgnoreCase) ||
		TreeSourceName.Equals(TEXT("SimpleForest"), ESearchCase::IgnoreCase) ||
		TreeSourceName.Equals(TEXT("EngineSample"), ESearchCase::IgnoreCase))
	{
		if (SpawnPCGSampleTreeField())
		{
			return;
		}

		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("PCG sample tree source requested, but no PCG tree meshes loaded; trying next tree source."));
	}

	if (TreeSourceName.Equals(TEXT("PVE"), ESearchCase::IgnoreCase) ||
		TreeSourceName.Equals(TEXT("ProceduralVegetation"), ESearchCase::IgnoreCase) ||
		TreeSourceName.Equals(TEXT("ProceduralVegetationEditor"), ESearchCase::IgnoreCase) ||
		TreeSourceName.Equals(TEXT("Megaplants"), ESearchCase::IgnoreCase))
	{
		if (SpawnPVETreeField())
		{
			return;
		}

		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("PVE tree source requested, but no PVE tree meshes loaded; falling back to generated tree mesh."));
	}

	UStaticMesh* RuntimeTreeMesh = CreateTreeMesh();
	if (!RuntimeTreeMesh)
	{
		return;
	}

	TreeComponents.Reset();
	SkeletalTreeComponents.Reset();
	Impl->TreeShadowCasters.Reset();
	Impl->TreeInstanceCount = 0;

	TArray<UHierarchicalInstancedStaticMeshComponent*> Components;
	Components.Reserve(ProphecyTreeComponentCount);
	for (int32 ComponentIndex = 0; ComponentIndex < ProphecyTreeComponentCount; ++ComponentIndex)
	{
		UHierarchicalInstancedStaticMeshComponent* Component = NewObject<UHierarchicalInstancedStaticMeshComponent>(this);
		if (!Component)
		{
			continue;
		}

		Component->SetStaticMesh(RuntimeTreeMesh);
		if (TreeMaterialInstance)
		{
			Component->SetMaterial(0, TreeMaterialInstance);
		}
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCastShadow(false);
		Component->SetCastContactShadow(false);
		Component->SetAffectDistanceFieldLighting(false);
		Component->SetAffectDynamicIndirectLighting(false);
		Component->SetVisibleInRayTracing(false);
		Component->SetReceivesDecals(false);
		Component->SetMobility(EComponentMobility::Static);
		Component->BoundsScale = bTreeWind ? (bTreeWindDiagnostic ? 3.5f : 1.35f) : 1.0f;
		Component->SetCullDistances(0, 36000);
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(Component);
		Component->RegisterComponent();
		Component->PreAllocateInstancesMemory(FMath::Max(1, TreeInstanceCount / ProphecyTreeComponentCount + 64));
		Components.Add(Component);
		TreeComponents.Add(Component);
	}

	if (Components.Num() == 0)
	{
		return;
	}

	const int32 DesiredCount = FMath::Clamp(TreeInstanceCount, 0, 6000);
	FRandomStream Random(20260521);
	for (int32 AttemptIndex = 0; AttemptIndex < DesiredCount * 16 && Impl->TreeInstanceCount < DesiredCount; ++AttemptIndex)
	{
		const float AreaT = Random.FRand();
		float Radius = FMath::Sqrt(FMath::Lerp(FMath::Square(ProphecyTreePlayableInnerRadiusCm), FMath::Square(ProphecyTreePlayableOuterRadiusCm), AreaT));
		const float Angle = Random.FRandRange(0.0f, UE_TWO_PI);
		Radius += Random.FRandRange(-420.0f, 420.0f);
		Radius = FMath::Clamp(Radius, ProphecyTreePlayableInnerRadiusCm, ProphecyTreePlayableOuterRadiusCm);

		const FVector2D Direction(FMath::Cos(Angle), FMath::Sin(Angle));
		const FVector2D FieldCenter(ProphecyTerrainCenterX, ProphecyTerrainCenterY);
		const FVector2D PositionXY = FieldCenter + Direction * Radius + FVector2D(Random.FRandRange(-320.0f, 320.0f), Random.FRandRange(-320.0f, 320.0f));
		if (FMath::Abs(PositionXY.X) < 2850.0f && PositionXY.Y > -2600.0f && PositionXY.Y < 12600.0f)
		{
			continue;
		}
		if (PositionXY.Y < -3600.0f && FMath::Abs(PositionXY.X) < 5200.0f)
		{
			continue;
		}

		const float Height = 0.0f;
		const float Yaw = Random.FRandRange(0.0f, 360.0f);
		const float UniformScale = Random.FRandRange(0.74f, 1.28f);
		const float HeightScale = Random.FRandRange(0.82f, 1.34f);
		const float SlopeLeanPitch = Random.FRandRange(-1.2f, 1.2f);
		const float SlopeLeanRoll = Random.FRandRange(-1.2f, 1.2f);
		const FTransform InstanceTransform(
			FRotator(SlopeLeanPitch, Yaw, SlopeLeanRoll),
			FVector(PositionXY.X, PositionXY.Y, Height - 5.0f),
			FVector(UniformScale, UniformScale, HeightScale));

		const int32 ComponentIndex = FMath::Clamp(FMath::FloorToInt((Angle / UE_TWO_PI) * float(Components.Num())), 0, Components.Num() - 1);
		Components[ComponentIndex]->AddInstance(InstanceTransform);

		FProphecyTreeShadowCaster Caster;
		Caster.Position = PositionXY;
		Caster.HeightCm = 2120.0f * HeightScale;
		Caster.TrunkRadiusCm = 34.0f * UniformScale;
		Caster.CrownRadiusCm = 315.0f * UniformScale;
		Caster.Strength = Random.FRandRange(0.34f, 0.50f);
		Impl->TreeShadowCasters.Add(Caster);
		++Impl->TreeInstanceCount;
	}

	if (bCenterTreeDiagnostic)
	{
		const FVector2D DiagnosticPositions[] =
		{
			FVector2D(-850.0f, 2600.0f),
			FVector2D(800.0f, 3100.0f),
			FVector2D(-350.0f, 3900.0f),
			FVector2D(420.0f, 4800.0f),
			FVector2D(0.0f, 5800.0f)
		};
		const float DiagnosticUniformScales[] = { 1.18f, 1.05f, 1.30f, 1.12f, 1.24f };
		const float DiagnosticHeightScales[] = { 1.24f, 1.08f, 1.36f, 1.18f, 1.28f };
		for (int32 Index = 0; Index < UE_ARRAY_COUNT(DiagnosticPositions); ++Index)
		{
			const float Yaw = 31.0f + float(Index) * 67.0f;
			const float UniformScale = DiagnosticUniformScales[Index];
			const float HeightScale = DiagnosticHeightScales[Index];
			const FTransform InstanceTransform(
				FRotator(0.0f, Yaw, 0.0f),
				FVector(DiagnosticPositions[Index].X, DiagnosticPositions[Index].Y, -5.0f),
				FVector(UniformScale, UniformScale, HeightScale));

			Components[Index % Components.Num()]->AddInstance(InstanceTransform);

			FProphecyTreeShadowCaster Caster;
			Caster.Position = DiagnosticPositions[Index];
			Caster.HeightCm = 2280.0f * HeightScale;
			Caster.TrunkRadiusCm = 46.0f * UniformScale;
			Caster.CrownRadiusCm = 420.0f * UniformScale;
			Caster.Strength = bShadowMaskDiagnostic ? 1.0f : 0.92f;
			Impl->TreeShadowCasters.Add(Caster);
			++Impl->TreeInstanceCount;
		}
	}

	BakeStaticTreeShadowMasks();
	UpdateGroundShadowMask();

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Spawned playable forest trees: components=%d instances=%d inner_radius=%.0fcm outer_radius=%.0fcm static_shadow_casters=%d dynamic_tree_shadows=0 wind=%d diagnostic=%d center_diagnostic=%d"),
		TreeComponents.Num(),
		Impl->TreeInstanceCount,
		ProphecyTreePlayableInnerRadiusCm,
		ProphecyTreePlayableOuterRadiusCm,
		Impl->TreeShadowCasters.Num(),
		bTreeWind ? 1 : 0,
		bTreeWindDiagnostic ? 1 : 0,
		bCenterTreeDiagnostic ? 1 : 0);
}

bool AProphecyNNCrowdBenchmarkActor::SpawnPCGSampleTreeField()
{
	struct FPCGTreeSpecies
	{
		const TCHAR* Path = nullptr;
		float Weight = 1.0f;
		float BaseUniformScale = 1.0f;
		float BaseHeightScale = 1.0f;
		float ShadowHeightCm = 1900.0f;
		float TrunkRadiusCm = 34.0f;
		float CrownRadiusCm = 360.0f;
	};

	static constexpr FPCGTreeSpecies SpeciesDefs[] =
	{
		{ TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_01.PCG_Tree_01"), 1.00f, 1.72f, 1.82f, 2200.0f, 38.0f, 410.0f },
		{ TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_02.PCG_Tree_02"), 1.20f, 1.55f, 1.70f, 2050.0f, 34.0f, 390.0f },
		{ TEXT("/PCG/SampleContent/SimpleForest/Meshes/PCG_Tree_03.PCG_Tree_03"), 0.90f, 1.86f, 1.92f, 2350.0f, 42.0f, 435.0f }
	};

	struct FLoadedPCGTree
	{
		UHierarchicalInstancedStaticMeshComponent* Component = nullptr;
		FPCGTreeSpecies Species;
	};

	TreeComponents.Reset();
	SkeletalTreeComponents.Reset();
	Impl->TreeShadowCasters.Reset();
	Impl->TreeInstanceCount = 0;

	TArray<FLoadedPCGTree> LoadedTrees;
	LoadedTrees.Reserve(UE_ARRAY_COUNT(SpeciesDefs));
	float TotalWeight = 0.0f;
	for (const FPCGTreeSpecies& Species : SpeciesDefs)
	{
		UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, Species.Path);
		if (!Mesh)
		{
			continue;
		}

		UHierarchicalInstancedStaticMeshComponent* Component = NewObject<UHierarchicalInstancedStaticMeshComponent>(this);
		if (!Component)
		{
			continue;
		}

		Component->SetStaticMesh(Mesh);
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCanEverAffectNavigation(false);
		Component->SetCastShadow(bCastShadows);
		Component->SetCastContactShadow(false);
		Component->SetAffectDistanceFieldLighting(false);
		Component->SetAffectDynamicIndirectLighting(false);
		Component->SetVisibleInRayTracing(false);
		Component->SetReceivesDecals(false);
		Component->SetMobility(EComponentMobility::Static);
		Component->SetCullDistances(0, 60000);
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(Component);
		Component->RegisterComponent();
		Component->PreAllocateInstancesMemory(FMath::Max(1, TreeInstanceCount / 2));

		FLoadedPCGTree& Loaded = LoadedTrees.AddDefaulted_GetRef();
		Loaded.Component = Component;
		Loaded.Species = Species;
		TotalWeight += FMath::Max(0.01f, Species.Weight);
		TreeComponents.Add(Component);
	}

	if (LoadedTrees.Num() == 0)
	{
		return false;
	}

	auto PickTree = [&LoadedTrees, TotalWeight](FRandomStream& Random) -> FLoadedPCGTree&
	{
		float Pick = Random.FRandRange(0.0f, FMath::Max(0.01f, TotalWeight));
		for (FLoadedPCGTree& Tree : LoadedTrees)
		{
			Pick -= FMath::Max(0.01f, Tree.Species.Weight);
			if (Pick <= 0.0f)
			{
				return Tree;
			}
		}
		return LoadedTrees.Last();
	};

	auto AddTree = [this, &PickTree](FRandomStream& Random, const FVector2D& PositionXY, float YawDegrees, float UniformJitter, float HeightJitter, bool bDiagnostic)
	{
		FLoadedPCGTree& Tree = PickTree(Random);
		if (!Tree.Component)
		{
			return;
		}

		const float UniformScale = Tree.Species.BaseUniformScale * UniformJitter;
		const float HeightScale = Tree.Species.BaseHeightScale * HeightJitter;
		const FTransform InstanceTransform(
			FRotator(Random.FRandRange(-1.2f, 1.2f), YawDegrees, Random.FRandRange(-1.2f, 1.2f)),
			FVector(PositionXY.X, PositionXY.Y, -5.0f),
			FVector(UniformScale, UniformScale, HeightScale));
		Tree.Component->AddInstance(InstanceTransform);

		FProphecyTreeShadowCaster Caster;
		Caster.Position = PositionXY;
		Caster.HeightCm = Tree.Species.ShadowHeightCm * HeightScale;
		Caster.TrunkRadiusCm = Tree.Species.TrunkRadiusCm * UniformScale;
		Caster.CrownRadiusCm = Tree.Species.CrownRadiusCm * UniformScale;
		Caster.Strength = bDiagnostic ? 0.95f : Random.FRandRange(0.38f, 0.58f);
		Impl->TreeShadowCasters.Add(Caster);
		++Impl->TreeInstanceCount;
	};

	const int32 DesiredCount = FMath::Clamp(TreeInstanceCount, 0, 1200);
	FRandomStream Random(20260523);
	for (int32 AttemptIndex = 0; AttemptIndex < DesiredCount * 16 && Impl->TreeInstanceCount < DesiredCount; ++AttemptIndex)
	{
		const float AreaT = Random.FRand();
		float Radius = FMath::Sqrt(FMath::Lerp(FMath::Square(ProphecyTreePlayableInnerRadiusCm), FMath::Square(ProphecyTreePlayableOuterRadiusCm), AreaT));
		const float Angle = Random.FRandRange(0.0f, UE_TWO_PI);
		Radius += Random.FRandRange(-480.0f, 480.0f);
		Radius = FMath::Clamp(Radius, ProphecyTreePlayableInnerRadiusCm, ProphecyTreePlayableOuterRadiusCm);

		const FVector2D Direction(FMath::Cos(Angle), FMath::Sin(Angle));
		const FVector2D FieldCenter(ProphecyTerrainCenterX, ProphecyTerrainCenterY);
		const FVector2D PositionXY = FieldCenter + Direction * Radius + FVector2D(Random.FRandRange(-360.0f, 360.0f), Random.FRandRange(-360.0f, 360.0f));
		if (FMath::Abs(PositionXY.X) < 2650.0f && PositionXY.Y > -2600.0f && PositionXY.Y < 12600.0f)
		{
			continue;
		}
		if (PositionXY.Y < -3600.0f && FMath::Abs(PositionXY.X) < 5100.0f)
		{
			continue;
		}

		AddTree(Random, PositionXY, Random.FRandRange(0.0f, 360.0f), Random.FRandRange(0.82f, 1.22f), Random.FRandRange(0.86f, 1.22f), false);
	}

	if (bCenterTreeDiagnostic)
	{
		const FVector2D DiagnosticPositions[] =
		{
			FVector2D(-1180.0f, 2450.0f),
			FVector2D(1120.0f, 3020.0f),
			FVector2D(-680.0f, 4200.0f),
			FVector2D(720.0f, 5200.0f),
			FVector2D(-160.0f, 6400.0f),
			FVector2D(1260.0f, 6950.0f)
		};
		for (int32 Index = 0; Index < UE_ARRAY_COUNT(DiagnosticPositions); ++Index)
		{
			AddTree(Random, DiagnosticPositions[Index], 30.0f + float(Index) * 63.0f, 1.08f + 0.06f * float(Index % 3), 1.08f + 0.05f * float(Index % 2), true);
		}
	}

	for (UHierarchicalInstancedStaticMeshComponent* Component : TreeComponents)
	{
		if (Component)
		{
			Component->BuildTreeIfOutdated(true, true);
		}
	}

	BakeStaticTreeShadowMasks();
	UpdateGroundShadowMask();

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Spawned PCG sample forest trees: components=%d requested=%d spawned=%d inner_radius=%.0fcm outer_radius=%.0fcm static_shadow_casters=%d dynamic_tree_shadows=%d center_diagnostic=%d"),
		TreeComponents.Num(),
		TreeInstanceCount,
		Impl->TreeInstanceCount,
		ProphecyTreePlayableInnerRadiusCm,
		ProphecyTreePlayableOuterRadiusCm,
		Impl->TreeShadowCasters.Num(),
		bCastShadows ? 1 : 0,
		bCenterTreeDiagnostic ? 1 : 0);

	return true;
}

bool AProphecyNNCrowdBenchmarkActor::SpawnPVETreeField()
{
	struct FPVETreeSpecies
	{
		const TCHAR* Path = nullptr;
		float Weight = 1.0f;
		float BaseUniformScale = 1.0f;
		float BaseHeightScale = 1.0f;
		float ShadowHeightCm = 1800.0f;
		float TrunkRadiusCm = 34.0f;
		float CrownRadiusCm = 320.0f;
	};

	static constexpr FPVETreeSpecies SpeciesDefs[] =
	{
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_European_QuakingAspen_01/SK_European_QuakingAspen_01.SK_European_QuakingAspen_01"), 1.35f, 1.16f, 1.18f, 2500.0f, 38.0f, 380.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_European_QuakingAspen_01/SK_European_QuakingAspen_02.SK_European_QuakingAspen_02"), 1.20f, 1.08f, 1.12f, 2320.0f, 34.0f, 350.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_European_QuakingAspen_01/SK_European_QuakingAspen_03.SK_European_QuakingAspen_03"), 1.15f, 1.12f, 1.16f, 2380.0f, 36.0f, 360.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_European_QuakingAspen_01/SK_European_QuakingAspen_04.SK_European_QuakingAspen_04"), 1.00f, 1.04f, 1.10f, 2240.0f, 32.0f, 335.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_Common_Hazel_01/SK_CommonHazel_01.SK_CommonHazel_01"), 0.55f, 0.88f, 0.88f, 1160.0f, 18.0f, 235.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_Common_Hazel_01/SK_CommonHazel_02.SK_CommonHazel_02"), 0.48f, 0.92f, 0.90f, 1200.0f, 18.0f, 245.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_Common_Hazel_01/SK_CommonHazel_03.SK_CommonHazel_03"), 0.44f, 0.84f, 0.86f, 1080.0f, 16.0f, 225.0f },
		{ TEXT("/ProceduralVegetationEditor/SampleAssets/Tree_Common_Hazel_01/SK_CommonHazel_04.SK_CommonHazel_04"), 0.40f, 0.90f, 0.88f, 1120.0f, 17.0f, 235.0f }
	};

	struct FLoadedPVETree
	{
		USkeletalMesh* Mesh = nullptr;
		FPVETreeSpecies Species;
	};

	TArray<FLoadedPVETree> LoadedTrees;
	LoadedTrees.Reserve(UE_ARRAY_COUNT(SpeciesDefs));
	float TotalWeight = 0.0f;
	for (const FPVETreeSpecies& Species : SpeciesDefs)
	{
		USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, Species.Path);
		if (!Mesh)
		{
			continue;
		}

		FLoadedPVETree& Loaded = LoadedTrees.AddDefaulted_GetRef();
		Loaded.Mesh = Mesh;
		Loaded.Species = Species;
		TotalWeight += FMath::Max(0.01f, Species.Weight);
	}

	if (LoadedTrees.Num() == 0)
	{
		return false;
	}

	TreeComponents.Reset();
	SkeletalTreeComponents.Reset();
	Impl->TreeShadowCasters.Reset();
	Impl->TreeInstanceCount = 0;

	auto PickTree = [&LoadedTrees, TotalWeight](FRandomStream& Random) -> const FLoadedPVETree&
	{
		float Pick = Random.FRandRange(0.0f, FMath::Max(0.01f, TotalWeight));
		for (const FLoadedPVETree& Tree : LoadedTrees)
		{
			Pick -= FMath::Max(0.01f, Tree.Species.Weight);
			if (Pick <= 0.0f)
			{
				return Tree;
			}
		}
		return LoadedTrees.Last();
	};

	auto SpawnOneTree = [this, &PickTree](FRandomStream& Random, const FVector2D& PositionXY, float YawDegrees, float UniformJitter, float HeightJitter, bool bDiagnostic)
	{
		const FLoadedPVETree& Tree = PickTree(Random);
		USkeletalMeshComponent* Component = NewObject<USkeletalMeshComponent>(this);
		if (!Component)
		{
			return;
		}

		const float UniformScale = Tree.Species.BaseUniformScale * UniformJitter;
		const float HeightScale = Tree.Species.BaseHeightScale * HeightJitter;
		const FTransform TreeTransform(
			FRotator(Random.FRandRange(-1.0f, 1.0f), YawDegrees, Random.FRandRange(-1.0f, 1.0f)),
			FVector(PositionXY.X, PositionXY.Y, -4.0f),
			FVector(UniformScale, UniformScale, HeightScale));

		Component->SetSkeletalMesh(Tree.Mesh);
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCanEverAffectNavigation(false);
		Component->SetCastShadow(bCastShadows);
		Component->SetCastContactShadow(false);
		Component->SetAffectDistanceFieldLighting(false);
		Component->SetAffectDynamicIndirectLighting(false);
		Component->SetVisibleInRayTracing(false);
		Component->SetReceivesDecals(false);
		Component->bPauseAnims = !bTreeWind;
		Component->SetComponentTickEnabled(bTreeWind);
		Component->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
		Component->bEnableUpdateRateOptimizations = true;
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		Component->SetRelativeTransform(TreeTransform);
		AddInstanceComponent(Component);
		Component->RegisterComponent();

		SkeletalTreeComponents.Add(Component);

		FProphecyTreeShadowCaster Caster;
		Caster.Position = PositionXY;
		Caster.HeightCm = Tree.Species.ShadowHeightCm * HeightScale;
		Caster.TrunkRadiusCm = Tree.Species.TrunkRadiusCm * UniformScale;
		Caster.CrownRadiusCm = Tree.Species.CrownRadiusCm * UniformScale;
		Caster.Strength = bDiagnostic ? 0.94f : Random.FRandRange(0.36f, 0.56f);
		Impl->TreeShadowCasters.Add(Caster);
		++Impl->TreeInstanceCount;
	};

	const int32 DesiredCount = FMath::Clamp(TreeInstanceCount, 0, 240);
	FRandomStream Random(20260522);
	for (int32 AttemptIndex = 0; AttemptIndex < DesiredCount * 20 && Impl->TreeInstanceCount < DesiredCount; ++AttemptIndex)
	{
		const float AreaT = Random.FRand();
		float Radius = FMath::Sqrt(FMath::Lerp(FMath::Square(ProphecyTreePlayableInnerRadiusCm), FMath::Square(ProphecyTreePlayableOuterRadiusCm), AreaT));
		const float Angle = Random.FRandRange(0.0f, UE_TWO_PI);
		Radius += Random.FRandRange(-520.0f, 520.0f);
		Radius = FMath::Clamp(Radius, ProphecyTreePlayableInnerRadiusCm, ProphecyTreePlayableOuterRadiusCm);

		const FVector2D Direction(FMath::Cos(Angle), FMath::Sin(Angle));
		const FVector2D FieldCenter(ProphecyTerrainCenterX, ProphecyTerrainCenterY);
		const FVector2D PositionXY = FieldCenter + Direction * Radius + FVector2D(Random.FRandRange(-420.0f, 420.0f), Random.FRandRange(-420.0f, 420.0f));
		if (FMath::Abs(PositionXY.X) < 2550.0f && PositionXY.Y > -2500.0f && PositionXY.Y < 12600.0f)
		{
			continue;
		}
		if (PositionXY.Y < -3600.0f && FMath::Abs(PositionXY.X) < 5000.0f)
		{
			continue;
		}

		SpawnOneTree(Random, PositionXY, Random.FRandRange(0.0f, 360.0f), Random.FRandRange(0.78f, 1.22f), Random.FRandRange(0.86f, 1.26f), false);
	}

	if (bCenterTreeDiagnostic)
	{
		const FVector2D DiagnosticPositions[] =
		{
			FVector2D(-1150.0f, 2500.0f),
			FVector2D(1220.0f, 3100.0f),
			FVector2D(-700.0f, 4300.0f),
			FVector2D(760.0f, 5200.0f),
			FVector2D(-180.0f, 6400.0f),
			FVector2D(1320.0f, 6900.0f)
		};
		for (int32 Index = 0; Index < UE_ARRAY_COUNT(DiagnosticPositions); ++Index)
		{
			SpawnOneTree(Random, DiagnosticPositions[Index], 22.0f + float(Index) * 71.0f, 1.08f + 0.06f * float(Index % 3), 1.12f + 0.04f * float(Index % 2), true);
		}
	}

	BakeStaticTreeShadowMasks();
	UpdateGroundShadowMask();

	UE_LOG(
		LogProphecyNNBenchmark,
		Display,
		TEXT("Spawned PVE playable forest trees: skeletal_components=%d species=%d requested=%d spawned=%d inner_radius=%.0fcm outer_radius=%.0fcm static_shadow_casters=%d dynamic_tree_shadows=%d wind=%d diagnostic=%d center_diagnostic=%d"),
		SkeletalTreeComponents.Num(),
		LoadedTrees.Num(),
		TreeInstanceCount,
		Impl->TreeInstanceCount,
		ProphecyTreePlayableInnerRadiusCm,
		ProphecyTreePlayableOuterRadiusCm,
		Impl->TreeShadowCasters.Num(),
		bCastShadows ? 1 : 0,
		bTreeWind ? 1 : 0,
		bTreeWindDiagnostic ? 1 : 0,
		bCenterTreeDiagnostic ? 1 : 0);

	return true;
}

void AProphecyNNCrowdBenchmarkActor::BakeStaticTreeShadowMasks()
{
	auto BakeMask = [this](TArray<float>& OutMask, int32 Size, const FVector2D& Center, float HalfExtent, bool bGrassReceiver)
	{
		const int32 PixelCount = Size * Size;
		if (PixelCount <= 0)
		{
			OutMask.Reset();
			return;
		}

		OutMask.SetNumZeroed(PixelCount);
		if (Impl->TreeShadowCasters.Num() == 0)
		{
			return;
		}

		const FVector SunShadowDirection = GetGroundShadowDirectionForLight(BenchmarkKeyLight);
		const FVector2D ShadowDirection(float(SunShadowDirection.X), float(SunShadowDirection.Y));
		const FVector2D ShadowDirectionSafe = ShadowDirection.IsNearlyZero() ? FVector2D(0.819f, 0.574f) : ShadowDirection.GetSafeNormal();
		const FVector2D CrossDirection(-ShadowDirectionSafe.Y, ShadowDirectionSafe.X);
		const float ProjectionScale = GetGroundShadowProjectionScaleForLight(BenchmarkKeyLight);
		const float CmPerPixel = (HalfExtent * 2.0f) / float(Size);

		auto WorldToPixel = [Center, HalfExtent, Size](const FVector2D& World)
		{
			const float U = (World.X - (Center.X - HalfExtent)) / (HalfExtent * 2.0f);
			const float V = (World.Y - (Center.Y - HalfExtent)) / (HalfExtent * 2.0f);
			return FIntPoint(FMath::FloorToInt(U * float(Size)), FMath::FloorToInt(V * float(Size)));
		};

		auto StampCapsuleMax = [&OutMask, Size, CmPerPixel, Center, HalfExtent, &WorldToPixel](const FVector2D& A, const FVector2D& B, float RadiusCm, float Strength)
		{
			constexpr int32 EdgePadPixels = 2;
			const float Radius = FMath::Max(RadiusCm, CmPerPixel * 0.65f);
			const FVector2D MinWorld(FMath::Min(A.X, B.X) - Radius, FMath::Min(A.Y, B.Y) - Radius);
			const FVector2D MaxWorld(FMath::Max(A.X, B.X) + Radius, FMath::Max(A.Y, B.Y) + Radius);
			const FIntPoint MinPixel = WorldToPixel(MinWorld);
			const FIntPoint MaxPixel = WorldToPixel(MaxWorld);
			if (MaxPixel.X < EdgePadPixels || MaxPixel.Y < EdgePadPixels || MinPixel.X > Size - 1 - EdgePadPixels || MinPixel.Y > Size - 1 - EdgePadPixels)
			{
				return;
			}

			const int32 X0 = FMath::Clamp(MinPixel.X, EdgePadPixels, Size - 1 - EdgePadPixels);
			const int32 Y0 = FMath::Clamp(MinPixel.Y, EdgePadPixels, Size - 1 - EdgePadPixels);
			const int32 X1 = FMath::Clamp(MaxPixel.X, EdgePadPixels, Size - 1 - EdgePadPixels);
			const int32 Y1 = FMath::Clamp(MaxPixel.Y, EdgePadPixels, Size - 1 - EdgePadPixels);
			const FVector2D Segment = B - A;
			const float SegmentLenSq = FMath::Max(Segment.SizeSquared(), 1.0f);
			const float InnerRadius = Radius * 0.38f;

			for (int32 Y = Y0; Y <= Y1; ++Y)
			{
				const float WorldY = Center.Y - HalfExtent + (float(Y) + 0.5f) * CmPerPixel;
				for (int32 X = X0; X <= X1; ++X)
				{
					const float WorldX = Center.X - HalfExtent + (float(X) + 0.5f) * CmPerPixel;
					const FVector2D Point(WorldX, WorldY);
					const float T = FMath::Clamp(FVector2D::DotProduct(Point - A, Segment) / SegmentLenSq, 0.0f, 1.0f);
					const FVector2D Closest = A + Segment * T;
					const float Distance = FVector2D::Distance(Point, Closest);
					if (Distance >= Radius)
					{
						continue;
					}

					const float EdgeT = FMath::Clamp((Distance - InnerRadius) / FMath::Max(Radius - InnerRadius, 1.0f), 0.0f, 1.0f);
					const float Soft = 1.0f - EdgeT * EdgeT * (3.0f - 2.0f * EdgeT);
					const int32 Index = Y * Size + X;
					OutMask[Index] = FMath::Max(OutMask[Index], FMath::Clamp(Strength * Soft, 0.0f, 1.0f));
				}
			}
		};

		for (const FProphecyTreeShadowCaster& Caster : Impl->TreeShadowCasters)
		{
			const float CasterStrength = bShadowMaskDiagnostic ? 1.0f : Caster.Strength;
			const float ShadowLength = FMath::Clamp(Caster.HeightCm * ProjectionScale * 0.92f, 760.0f, 2850.0f);
			const float TrunkRadius = FMath::Max(Caster.TrunkRadiusCm * (bGrassReceiver ? 1.45f : 1.80f), bGrassReceiver ? 62.0f : 82.0f);
			const float CrownRadius = FMath::Max(Caster.CrownRadiusCm, bGrassReceiver ? 230.0f : 280.0f);
			const FVector2D Base = Caster.Position;
			StampCapsuleMax(Base - ShadowDirectionSafe * 35.0f, Base + ShadowDirectionSafe * ShadowLength, TrunkRadius, CasterStrength * 0.72f);

			const FVector2D CrownCenter = Base + ShadowDirectionSafe * (ShadowLength * 0.58f);
			StampCapsuleMax(
				CrownCenter - CrossDirection * (CrownRadius * 0.95f),
				CrownCenter + CrossDirection * (CrownRadius * 0.95f),
				CrownRadius * 0.62f,
				CasterStrength * 0.52f);
			StampCapsuleMax(
				Base + ShadowDirectionSafe * (ShadowLength * 0.25f) - CrossDirection * (CrownRadius * 0.42f),
				Base + ShadowDirectionSafe * (ShadowLength * 0.25f) + CrossDirection * (CrownRadius * 0.28f),
				CrownRadius * 0.30f,
				CasterStrength * 0.30f);
		}
	};

	if (Impl->GrassShadowMaskValues.Num() > 0)
	{
		BakeMask(Impl->StaticGrassShadowMaskValues, Impl->GrassShadowMaskSize, Impl->GrassShadowMaskCenter, Impl->GrassShadowMaskHalfExtent, true);
		Impl->LastGrassShadowMaskNNStep = -1;
		Impl->bLoggedGrassShadowMaskStats = false;
	}
	if (Impl->GroundShadowMaskValues.Num() > 0)
	{
		BakeMask(Impl->StaticGroundShadowMaskValues, Impl->GroundShadowMaskSize, Impl->GroundShadowMaskCenter, Impl->GroundShadowMaskHalfExtent, false);
		Impl->LastGroundShadowMaskNNStep = -1;
		Impl->bLoggedGroundShadowMaskStats = false;
	}
}

void AProphecyNNCrowdBenchmarkActor::InitializeDistantTerrainTexture()
{
	if (!FloorMaterialInstance && !DistantHillsMaterialInstance)
	{
		return;
	}

	constexpr int32 TextureSize = 1024;
	constexpr float TerrainCenterX = 0.0f;
	constexpr float TerrainCenterY = 700.0f;
	constexpr float TerrainExtentCm = ProphecyDistantHillOuterRadiusCm;
	constexpr float InvTerrainExtent = 1.0f / (TerrainExtentCm * 2.0f);

	if (!DistantTerrainTexture)
	{
		DistantTerrainTexture = UTexture2D::CreateTransient(TextureSize, TextureSize, PF_B8G8R8A8, TEXT("ProphecyDistantTerrainBakedColor"));
		if (!DistantTerrainTexture)
		{
			return;
		}
		DistantTerrainTexture->SRGB = true;
		DistantTerrainTexture->Filter = TF_Bilinear;
		DistantTerrainTexture->AddressX = TA_Clamp;
		DistantTerrainTexture->AddressY = TA_Clamp;
		DistantTerrainTexture->UpdateResource();

		auto Smooth01 = [](float T)
		{
			T = FMath::Clamp(T, 0.0f, 1.0f);
			return T * T * (3.0f - 2.0f * T);
		};

		TArray<FColor> GroundNoisePixels;
		int32 GroundNoiseWidth = 0;
		int32 GroundNoiseHeight = 0;
		const FString GroundNoisePath = FPaths::ProjectSavedDir() / TEXT("ProphecyGrassGroundNoise.png");
		TArray<uint8> CompressedGroundNoise;
		if (FFileHelper::LoadFileToArray(CompressedGroundNoise, *GroundNoisePath))
		{
			IImageWrapperModule& ImageWrapperModule = FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
			TSharedPtr<IImageWrapper> ImageWrapper = ImageWrapperModule.CreateImageWrapper(EImageFormat::PNG, *GroundNoisePath);
			if (ImageWrapper.IsValid() && ImageWrapper->SetCompressed(CompressedGroundNoise.GetData(), CompressedGroundNoise.Num()))
			{
				TArray64<uint8> RawBGRA;
				if (ImageWrapper->GetRaw(ERGBFormat::BGRA, 8, RawBGRA))
				{
					GroundNoiseWidth = ImageWrapper->GetWidth();
					GroundNoiseHeight = ImageWrapper->GetHeight();
					const int32 SourcePixelCount = GroundNoiseWidth * GroundNoiseHeight;
					if (SourcePixelCount > 0 && RawBGRA.Num() >= int64(SourcePixelCount) * int64(sizeof(FColor)))
					{
						GroundNoisePixels.SetNumUninitialized(SourcePixelCount);
						FMemory::Memcpy(GroundNoisePixels.GetData(), RawBGRA.GetData(), SourcePixelCount * sizeof(FColor));
					}
				}
			}
		}
		if (GroundNoisePixels.IsEmpty())
		{
			UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Could not load %s for baked terrain color; falling back to flat terrain base color."), *GroundNoisePath);
		}

		auto Wrap01 = [](float Value)
		{
			float Wrapped = FMath::Fmod(Value, 1.0f);
			if (Wrapped < 0.0f)
			{
				Wrapped += 1.0f;
			}
			return Wrapped;
		};

		auto SampleGroundAlbedo = [&GroundNoisePixels, GroundNoiseWidth, GroundNoiseHeight, Wrap01](float WorldX, float WorldY)
		{
			if (GroundNoisePixels.IsEmpty() || GroundNoiseWidth <= 0 || GroundNoiseHeight <= 0)
			{
				return ProphecyGrassTerrainBaseColor;
			}

			const float U = Wrap01(WorldX * (1.0f / 22000.0f));
			const float V = Wrap01(WorldY * (1.0f / 22000.0f));
			const float SourceX = U * float(GroundNoiseWidth);
			const float SourceY = V * float(GroundNoiseHeight);
			const int32 X0 = FMath::Clamp(FMath::FloorToInt(SourceX), 0, GroundNoiseWidth - 1);
			const int32 Y0 = FMath::Clamp(FMath::FloorToInt(SourceY), 0, GroundNoiseHeight - 1);
			const int32 X1 = (X0 + 1) % GroundNoiseWidth;
			const int32 Y1 = (Y0 + 1) % GroundNoiseHeight;
			const float Tx = FMath::Frac(SourceX);
			const float Ty = FMath::Frac(SourceY);
			const FLinearColor C00 = FLinearColor::FromSRGBColor(GroundNoisePixels[Y0 * GroundNoiseWidth + X0]);
			const FLinearColor C10 = FLinearColor::FromSRGBColor(GroundNoisePixels[Y0 * GroundNoiseWidth + X1]);
			const FLinearColor C01 = FLinearColor::FromSRGBColor(GroundNoisePixels[Y1 * GroundNoiseWidth + X0]);
			const FLinearColor C11 = FLinearColor::FromSRGBColor(GroundNoisePixels[Y1 * GroundNoiseWidth + X1]);
			const FLinearColor CX0 = FMath::Lerp(C00, C10, Tx);
			const FLinearColor CX1 = FMath::Lerp(C01, C11, Tx);
			const FLinearColor NoiseColor = FMath::Lerp(CX0, CX1, Ty);
			return FMath::Lerp(ProphecyGrassTerrainBaseColor, NoiseColor, 0.18f);
		};

		auto HillHeightAtRadiusAngle = [&Smooth01](float Radius, float Angle)
		{
			const float RiseT = Smooth01((Radius - ProphecyDistantHillRiseStartRadiusCm) / (ProphecyDistantHillOuterRadiusCm - ProphecyDistantHillRiseStartRadiusCm));
			const float RidgeWave =
				0.58f
				+ 0.30f * FMath::Sin(Angle * 2.0f + 0.35f)
				+ 0.24f * FMath::Sin(Angle * 5.0f - 1.25f)
				+ 0.18f * FMath::Sin(Angle * 9.0f + Radius * 0.00007f)
				+ 0.10f * FMath::Sin(Angle * 17.0f - Radius * 0.00011f);
			const float RidgeStrength = FMath::Clamp(RidgeWave, 0.10f, 1.25f);
			const float RollingDetail =
				FMath::Sin(Angle * 13.0f + Radius * 0.00017f) * 760.0f
				+ FMath::Sin(Angle * 3.0f - Radius * 0.00008f) * 1180.0f
				+ FMath::Sin(Angle * 23.0f + Radius * 0.00021f) * 360.0f;
			float Height = -4.0f + FMath::Pow(RiseT, 0.62f) * (2600.0f + 5200.0f * RidgeStrength) + RollingDetail * 0.72f * RiseT * (1.0f - RiseT * 0.16f);
			if (Radius <= ProphecyDistantHillInnerRadiusCm + 1.0f)
			{
				Height = -4.0f;
			}
			return Height;
		};

		auto TerrainHeightAtXY = [&HillHeightAtRadiusAngle](const FVector2D& WorldXY, float& OutHeight)
		{
			const FVector2D Local = WorldXY - FVector2D(TerrainCenterX, TerrainCenterY);
			const float Radius = Local.Size();
			if (Radius < ProphecyDistantHillInnerRadiusCm || Radius > ProphecyDistantHillOuterRadiusCm)
			{
				return false;
			}
			const float Angle = FMath::Atan2(Local.Y, Local.X);
			OutHeight = HillHeightAtRadiusAngle(Radius, Angle);
			return true;
		};

		auto TerrainNormalAt = [&TerrainHeightAtXY](const FVector& Position)
		{
			constexpr float SampleStepCm = 500.0f;
			auto HeightAtOr = [&TerrainHeightAtXY](const FVector2D& WorldXY, float FallbackHeight)
			{
				float Height = FallbackHeight;
				TerrainHeightAtXY(WorldXY, Height);
				return Height;
			};

			const FVector2D CenterXY(Position.X, Position.Y);
			const float HeightX0 = HeightAtOr(CenterXY - FVector2D(SampleStepCm, 0.0f), Position.Z);
			const float HeightX1 = HeightAtOr(CenterXY + FVector2D(SampleStepCm, 0.0f), Position.Z);
			const float HeightY0 = HeightAtOr(CenterXY - FVector2D(0.0f, SampleStepCm), Position.Z);
			const float HeightY1 = HeightAtOr(CenterXY + FVector2D(0.0f, SampleStepCm), Position.Z);
			const FVector SlopeX(SampleStepCm * 2.0f, 0.0f, HeightX1 - HeightX0);
			const FVector SlopeY(0.0f, SampleStepCm * 2.0f, HeightY1 - HeightY0);
			FVector Normal = FVector::CrossProduct(SlopeX, SlopeY).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
			if (Normal.Z < 0.0)
			{
				Normal *= -1.0;
			}
			return Normal;
		};

		const FVector BakedSunDirection = FRotationMatrix(FRotator(-45.0, 35.0, 0.0)).GetUnitAxis(EAxis::X).GetSafeNormal();
		const FVector BakedToSunDirection = (-BakedSunDirection).GetSafeNormal();
		const FVector2D BakedSunHorizontal(BakedToSunDirection.X, BakedToSunDirection.Y);
		const FVector2D BakedSunHorizontalSafe = BakedSunHorizontal.IsNearlyZero() ? FVector2D(1.0, 0.0) : BakedSunHorizontal.GetSafeNormal();

		auto BakedSelfShadowAt = [&TerrainHeightAtXY, BakedSunHorizontalSafe](const FVector& Position)
		{
			float Shadow = 0.0f;
			const FVector2D Start(Position.X, Position.Y);
			constexpr int32 StepCount = 20;
			constexpr float StepLengthCm = 950.0f;
			constexpr float ShadowRisePerCm = 0.10f;
			for (int32 StepIndex = 1; StepIndex <= StepCount; ++StepIndex)
			{
				const float DistanceCm = StepLengthCm * float(StepIndex);
				const FVector2D SampleXY = Start + BakedSunHorizontalSafe * DistanceCm;
				float SampleHeight = 0.0f;
				if (!TerrainHeightAtXY(SampleXY, SampleHeight))
				{
					continue;
				}
				const float LightRayHeight = float(Position.Z) + DistanceCm * ShadowRisePerCm + 80.0f;
				if (SampleHeight > LightRayHeight)
				{
					const float Penetration = FMath::Clamp((SampleHeight - LightRayHeight) / 2300.0f, 0.0f, 1.0f);
					const float DistanceFade = FMath::Clamp(1.0f - (float(StepIndex - 1) / float(StepCount)), 0.0f, 1.0f);
					Shadow = FMath::Max(Shadow, Penetration * (0.45f + 0.55f * DistanceFade));
				}
			}
			return Shadow;
		};

		auto BakedShadeAt = [&TerrainNormalAt, &BakedSelfShadowAt, BakedToSunDirection, BakedSunHorizontalSafe](const FVector& Position)
		{
			const FVector Normal = TerrainNormalAt(Position);
			const float LitAmount = FMath::Clamp(float(FVector::DotProduct(Normal, BakedToSunDirection)), 0.0f, 1.0f);
			const FVector2D RawSlopeAspect(Normal.X, Normal.Y);
			const FVector2D SlopeAspect = RawSlopeAspect.IsNearlyZero() ? FVector2D::ZeroVector : RawSlopeAspect.GetSafeNormal();
			const float AspectLight = RawSlopeAspect.IsNearlyZero()
				? LitAmount
				: FMath::Clamp(0.5f + 0.5f * float(FVector2D::DotProduct(SlopeAspect, BakedSunHorizontalSafe)), 0.0f, 1.0f);
			const float HeightAlpha = FMath::Clamp(float(Position.Z / 9000.0), 0.0f, 1.0f);
			const float ReliefStrength = FMath::Clamp((1.0f - float(Normal.Z)) * 20.0f, 0.25f, 1.0f);
			const float SelfShadow = BakedSelfShadowAt(Position);
			const float LeeShadow = FMath::Pow(1.0f - AspectLight, 0.86f) * FMath::Lerp(0.38f, 0.92f, ReliefStrength);
			const float ShadowAmount = FMath::Clamp(FMath::Max(LeeShadow, SelfShadow), 0.0f, 1.0f);
			const float LitLift = FMath::Lerp(0.94f, 1.10f, FMath::Pow(AspectLight, 0.75f));
			const float Shade = FMath::Lerp(LitLift, 0.82f, ShadowAmount) * (0.98f + 0.02f * HeightAlpha);
			return FMath::Clamp(Shade, 0.80f, 1.04f);
		};

		TArray<FColor> Pixels;
		Pixels.SetNumUninitialized(TextureSize * TextureSize);
		for (int32 Y = 0; Y < TextureSize; ++Y)
		{
			const float V = (float(Y) + 0.5f) / float(TextureSize);
			const float WorldY = TerrainCenterY + (V - 0.5f) * (TerrainExtentCm * 2.0f);
			for (int32 X = 0; X < TextureSize; ++X)
			{
				const float U = (float(X) + 0.5f) / float(TextureSize);
				const float WorldX = TerrainCenterX + (U - 0.5f) * (TerrainExtentCm * 2.0f);
				const FVector2D WorldXY(WorldX, WorldY);
				const FVector2D Local = WorldXY - FVector2D(TerrainCenterX, TerrainCenterY);
				const float Radius = Local.Size();
				FLinearColor TerrainColor = SampleGroundAlbedo(WorldX, WorldY);

				float Height = 0.0f;
				float Shade = 1.0f;
				if (TerrainHeightAtXY(WorldXY, Height))
				{
					const float HillShadeAlpha = 0.35f * Smooth01((Radius - ProphecyDistantHillInnerRadiusCm) / 22000.0f);
					Shade = FMath::Lerp(1.0f, BakedShadeAt(FVector(WorldX, WorldY, Height)), HillShadeAlpha);
				}
				TerrainColor.R = FMath::Clamp(TerrainColor.R * Shade, 0.0f, 1.0f);
				TerrainColor.G = FMath::Clamp(TerrainColor.G * Shade, 0.0f, 1.0f);
				TerrainColor.B = FMath::Clamp(TerrainColor.B * Shade, 0.0f, 1.0f);
				Pixels[Y * TextureSize + X] = TerrainColor.ToFColorSRGB();
			}
		}

		const int32 ByteCount = Pixels.Num() * sizeof(FColor);
		uint8* UploadData = static_cast<uint8*>(FMemory::Malloc(ByteCount));
		FMemory::Memcpy(UploadData, Pixels.GetData(), ByteCount);
		FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, TextureSize, TextureSize);
		DistantTerrainTexture->UpdateTextureRegions(
			0,
			1,
			Region,
			uint32(TextureSize * sizeof(FColor)),
			uint32(sizeof(FColor)),
			UploadData,
			[](uint8* SrcData, const FUpdateTextureRegion2D* Regions)
			{
				FMemory::Free(SrcData);
				delete Regions;
			});

		UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Initialized baked distant terrain color texture from old albedo plus shade: size=%d extent=%.0fcm"), TextureSize, TerrainExtentCm);
	}

	auto ApplyTerrainTexture = [this](UMaterialInstanceDynamic* MaterialInstance)
	{
		if (!MaterialInstance || !DistantTerrainTexture)
		{
			return;
		}
		MaterialInstance->SetTextureParameterValue(TEXT("TerrainBakedColorTexture"), DistantTerrainTexture);
		MaterialInstance->SetVectorParameterValue(TEXT("TerrainCenter"), FLinearColor(TerrainCenterX, TerrainCenterY, 0.0f, 0.0f));
		MaterialInstance->SetScalarParameterValue(TEXT("TerrainInvExtent"), InvTerrainExtent);
	};

	ApplyTerrainTexture(FloorMaterialInstance.Get());
	ApplyTerrainTexture(DistantHillsMaterialInstance.Get());
}

void AProphecyNNCrowdBenchmarkActor::SpawnNiagaraGrassField()
{
	Impl->ActiveGrassRenderer = TEXT("Niagara");
	Impl->GrassInstanceCount = 0;
	Impl->GrassDenseInstanceCount = 0;
	Impl->GrassVisualBladeCount = 0;
	Impl->NiagaraComponentCount = 0;
	GrassComponents.Reset();
	NiagaraGrassComponents.Reset();

	if (NiagaraGrassSystemPath.IsEmpty())
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Niagara grass renderer requested, but ProphecyNNNiagaraSystem is empty."));
		return;
	}

	EnsureNiagaraContentMounted();
	UNiagaraSystem* NiagaraSystem = LoadObject<UNiagaraSystem>(nullptr, *NiagaraGrassSystemPath);
	if (!NiagaraSystem)
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("Could not load Niagara grass system '%s'. This run will not render grass."), *NiagaraGrassSystemPath);
		return;
	}

	const int32 DesiredComponentCount = FMath::Clamp(NiagaraGrassComponentCount, 1, 256);
	const int32 ComponentsPerAxis = FMath::Max(1, FMath::CeilToInt(FMath::Sqrt(float(DesiredComponentCount))));
	const float FieldDiameter = ProphecyGrassFarRadiusCm * 2.0f;
	const float CellSize = FieldDiameter / float(ComponentsPerAxis);
	const FVector FieldCenter(0.0, 700.0, 0.0);
	const FBox LocalBounds(
		FVector(-ProphecyGrassFarRadiusCm, -ProphecyGrassFarRadiusCm, -50.0f),
		FVector(ProphecyGrassFarRadiusCm, ProphecyGrassFarRadiusCm, 500.0f));

	for (int32 Index = 0; Index < DesiredComponentCount; ++Index)
	{
		const int32 CellX = Index % ComponentsPerAxis;
		const int32 CellY = Index / ComponentsPerAxis;
		const float LocalX = -ProphecyGrassFarRadiusCm + (float(CellX) + 0.5f) * CellSize;
		const float LocalY = -ProphecyGrassFarRadiusCm + (float(CellY) + 0.5f) * CellSize;

		UNiagaraComponent* Component = NewObject<UNiagaraComponent>(this);
		Component->SetAsset(NiagaraSystem);
		Component->SetAutoActivate(false);
		Component->SetForceSolo(false);
		Component->SetAllowScalability(false);
		Component->SetTickBehavior(ENiagaraTickBehavior::UsePrereqs);
		Component->SetRandomSeedOffset(Index * 7919);
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCastShadow(false);
		Component->SetCastContactShadow(false);
		Component->SetAffectDistanceFieldLighting(false);
		Component->SetAffectDynamicIndirectLighting(false);
		Component->SetVisibleInRayTracing(false);
		Component->SetReceivesDecals(false);
		Component->SetMobility(EComponentMobility::Static);
		Component->SetSystemFixedBounds(LocalBounds);
		Component->SetVariableInt(TEXT("User.ProphecyComponentIndex"), Index);
		Component->SetVariableInt(TEXT("User.ProphecyComponentCount"), DesiredComponentCount);
		Component->SetVariableFloat(TEXT("User.ProphecyFarRadiusCm"), ProphecyGrassFarRadiusCm);
		Component->SetVariableFloat(TEXT("User.ProphecyNearRadiusCm"), ProphecyGrassNearRadiusCm);
		Component->SetVariableFloat(TEXT("User.ProphecyGrassHeightCm"), 30.0f);
		Component->SetVariableVec3(TEXT("User.ProphecyFieldCenter"), FieldCenter);
		Component->SetVariableVec3(TEXT("User.ProphecyCellCenter"), FieldCenter + FVector(LocalX, LocalY, 0.0));
		Component->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		Component->SetRelativeLocation(FieldCenter + FVector(LocalX, LocalY, 0.0));
		AddInstanceComponent(Component);
		Component->RegisterComponent();
		Component->Activate(true);
		NiagaraGrassComponents.Add(Component);
	}

	Impl->NiagaraComponentCount = NiagaraGrassComponents.Num();
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Spawned Niagara grass candidate: components=%d system=%s note=system_asset_controls_particle_count_and_visuals"),
		Impl->NiagaraComponentCount,
		*NiagaraGrassSystemPath);
}

void AProphecyNNCrowdBenchmarkActor::StepSimulation(float StepSeconds)
{
	const double BuildStart = FPlatformTime::Seconds();
	BuildInputBatch(StepSeconds);
	Impl->Stats.BuildInputSeconds += FPlatformTime::Seconds() - BuildStart;

	const double InferenceStart = FPlatformTime::Seconds();
	RunModelBatch();
	Impl->Stats.InferenceSeconds += FPlatformTime::Seconds() - InferenceStart;

	const double OutputStart = FPlatformTime::Seconds();
	ApplyOutputBatch(StepSeconds);
	Impl->Stats.OutputSeconds += FPlatformTime::Seconds() - OutputStart;

	const double StoreStart = FPlatformTime::Seconds();
	const double NowSeconds = FPlatformTime::Seconds();
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		PublishAgentPose(AgentIndex, NowSeconds);
	}
	Impl->Stats.StoreSeconds += FPlatformTime::Seconds() - StoreStart;
	++Impl->Stats.NNStepCount;
	if (Impl->Stats.ElapsedSeconds >= WarmupSeconds)
	{
		++Impl->Stats.WarmedNNStepCount;
	}
}

void AProphecyNNCrowdBenchmarkActor::BuildInputBatch(float StepSeconds)
{
	for (int32 AgentIndex = 0; AgentIndex < ProphecyBatchSize; ++AgentIndex)
	{
		const FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
		float* Write = Impl->InputBuffer.GetData() + AgentIndex * ProphecyInputDim;

		auto WriteVec3 = [&Write](const FVector3f& Vec)
		{
			*Write++ = Vec.X;
			*Write++ = Vec.Y;
			*Write++ = Vec.Z;
		};
		auto WriteRot6 = [&Write](const FProphecyNNRot6& Rot6)
		{
			*Write++ = Rot6.A.X;
			*Write++ = Rot6.A.Y;
			*Write++ = Rot6.A.Z;
			*Write++ = Rot6.B.X;
			*Write++ = Rot6.B.Y;
			*Write++ = Rot6.B.Z;
		};
		auto WritePose = [&WriteVec3, &WriteRot6](const FProphecyNNPoseRuntime& Pose)
		{
			WriteVec3(Pose.PelvisPos);
			WriteRot6(Pose.PelvisRot6);
			for (const FVector3f& CanonPos : Pose.CanonPos)
			{
				WriteVec3(CanonPos);
			}
			for (const FProphecyNNRot6& Rot6 : Pose.NonPelvisRot6)
			{
				WriteRot6(Rot6);
			}
		};

		WritePose(Agent.CurPose);
		WritePose(Agent.PrevPose);

		WriteVec3((Agent.CurPose.PelvisPos - Agent.PrevPose.PelvisPos) / Impl->PoseDeltaScaleFinal);
		for (int32 BoneIndex = 0; BoneIndex < ProphecyBodyBoneCount; ++BoneIndex)
		{
			WriteVec3((Agent.CurPose.CanonPos[BoneIndex] - Agent.PrevPose.CanonPos[BoneIndex]) / Impl->PoseDeltaScaleFinal);
		}

		const FProphecyNNMat3 PrevHeading = YawToRowMatrix(Agent.PrevRootYaw);
		const FVector3f DeltaLocal = TransformRowVector(Agent.CurRootPos - Agent.PrevRootPos, PrevHeading);
		*Write++ = DeltaLocal.X / Impl->MaxSpeedScaleFinal;
		*Write++ = DeltaLocal.Z / Impl->MaxSpeedScaleFinal;
		*Write++ = WrapAngleRadians(Agent.CurRootYaw - Agent.PrevRootYaw) / Impl->MaxTurnRateScaleFinal;

		const FProphecyNNMat3 CurHeading = YawToRowMatrix(Agent.CurRootYaw);
		for (int32 FutureIndex = 1; FutureIndex <= Impl->FutureWindow; ++FutureIndex)
		{
			const float FutureTime = StepSeconds * float(FutureIndex);
			const float FutureYaw = Agent.CurRootYaw + Agent.YawRateRadiansPerSecond * FutureTime;
			const FVector3f Forward(FMath::Sin(Agent.CurRootYaw), 0.0f, FMath::Cos(Agent.CurRootYaw));
			const FVector3f FuturePos = Agent.CurRootPos + Forward * Agent.SpeedMetersPerSecond * FutureTime;
			const FVector3f FutureLocal = TransformRowVector(FuturePos - Agent.CurRootPos, CurHeading);
			const float ScaleK = float(FutureIndex) * Impl->MaxSpeedScaleFinal;
			*Write++ = FMath::Clamp(FutureLocal.X / ScaleK, -2.0f, 2.0f);
			*Write++ = FMath::Clamp(FutureLocal.Z / ScaleK, -2.0f, 2.0f);
			const float DeltaYaw = WrapAngleRadians(FutureYaw - Agent.CurRootYaw);
			*Write++ = FMath::Cos(DeltaYaw);
			*Write++ = FMath::Sin(DeltaYaw);
		}

		check(int32(Write - (Impl->InputBuffer.GetData() + AgentIndex * ProphecyInputDim)) == ProphecyInputDim);
	}
}

void AProphecyNNCrowdBenchmarkActor::RunModelBatch()
{
	if (!Impl->Model.Run(Impl->InputBuffer, Impl->OutputBuffer))
	{
		UE_LOG(LogProphecyNNBenchmark, Error, TEXT("NNE RunSync failed."));
		SetActorTickEnabled(false);
	}
}

void AProphecyNNCrowdBenchmarkActor::ApplyOutputBatch(float StepSeconds)
{
	for (int32 AgentIndex = 0; AgentIndex < ProphecyBatchSize; ++AgentIndex)
	{
		FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
		const float* Read = Impl->OutputBuffer.GetData() + AgentIndex * ProphecyOutputDim;
		float PoseOutput[ProphecyPoseDimNoContacts];

		int32 Cursor = 0;
		PoseOutput[Cursor++] = Agent.CurPose.PelvisPos.X + *Read++;
		PoseOutput[Cursor++] = Agent.CurPose.PelvisPos.Y + *Read++;
		PoseOutput[Cursor++] = Agent.CurPose.PelvisPos.Z + *Read++;

		const float CurrentPelvisRot6[] = {
			Agent.CurPose.PelvisRot6.A.X, Agent.CurPose.PelvisRot6.A.Y, Agent.CurPose.PelvisRot6.A.Z,
			Agent.CurPose.PelvisRot6.B.X, Agent.CurPose.PelvisRot6.B.Y, Agent.CurPose.PelvisRot6.B.Z
		};
		for (int32 Index = 0; Index < 6; ++Index)
		{
			PoseOutput[Cursor++] = CurrentPelvisRot6[Index] + *Read++;
		}

		for (const FProphecyNNRot6& CurrentRot6 : Agent.CurPose.NonPelvisRot6)
		{
			const float CurrentRotValues[] = {
				CurrentRot6.A.X, CurrentRot6.A.Y, CurrentRot6.A.Z,
				CurrentRot6.B.X, CurrentRot6.B.Y, CurrentRot6.B.Z
			};
			for (int32 Index = 0; Index < 6; ++Index)
			{
				PoseOutput[Cursor++] = CurrentRotValues[Index] + *Read++;
			}
		}
		check(Cursor == ProphecyPoseDimNoContacts);

		FProphecyNNPoseRuntime NextPose;
		NextPose.NonPelvisRot6.SetNum(ProphecyNonPelvisBoneCount);
		NextPose.PelvisPos = FVector3f(PoseOutput[0], PoseOutput[1], PoseOutput[2]);

		FProphecyNNRot6 PelvisRot6;
		PelvisRot6.A = FVector3f(PoseOutput[3], PoseOutput[4], PoseOutput[5]);
		PelvisRot6.B = FVector3f(PoseOutput[6], PoseOutput[7], PoseOutput[8]);
		NextPose.PelvisRot6 = CleanRot6(PelvisRot6);

		int32 RotCursor = 9;
		for (int32 RotIndex = 0; RotIndex < ProphecyNonPelvisBoneCount; ++RotIndex)
		{
			FProphecyNNRot6 Rot6;
			Rot6.A = FVector3f(PoseOutput[RotCursor], PoseOutput[RotCursor + 1], PoseOutput[RotCursor + 2]);
			Rot6.B = FVector3f(PoseOutput[RotCursor + 3], PoseOutput[RotCursor + 4], PoseOutput[RotCursor + 5]);
			NextPose.NonPelvisRot6[RotIndex] = CleanRot6(Rot6);
			RotCursor += 6;
		}

		NextPose.Contacts = FVector2f(Sigmoid(Read[0]), Sigmoid(Read[1]));

		Agent.PrevPose = Agent.CurPose;
		Agent.CurPose = MoveTemp(NextPose);
		Agent.PrevRootPos = Agent.CurRootPos;
		Agent.PrevRootYaw = Agent.CurRootYaw;

		Agent.CurRootYaw = WrapAngleRadians(Agent.CurRootYaw + Agent.YawRateRadiansPerSecond * StepSeconds);
		const FVector3f Forward(FMath::Sin(Agent.CurRootYaw), 0.0f, FMath::Cos(Agent.CurRootYaw));
		Agent.CurRootPos += Forward * Agent.SpeedMetersPerSecond * StepSeconds;

		const FProphecyNNMat3 RootRot = MatrixMultiply(Impl->SeedRootRot, YawToRowMatrix(Agent.CurRootYaw));
		Impl->ComputeFK(Agent.CurPose, Agent.CurRootPos, RootRot);
	}
}

void AProphecyNNCrowdBenchmarkActor::PublishAgentPose(int32 AgentIndex, double SourceTimeSeconds)
{
	FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
	Agent.LocalTransforms[0] = FTransform::Identity;

	for (int32 BoneIndex = 0; BoneIndex < ProphecyBodyBoneCount; ++BoneIndex)
	{
		const FProphecyNNMat3 LocalRot = BoneIndex == 0
			? Rotation6DToMatrix(Agent.CurPose.PelvisRot6)
			: Rotation6DToMatrix(Agent.CurPose.NonPelvisRot6[BoneIndex - 1]);
		const FVector3f LocalOffset = BoneIndex == 0 ? Agent.CurPose.PelvisPos : Impl->LocalOffsets[BoneIndex];
		Agent.LocalTransforms[BoneIndex + 1] = FTransform(MatrixToQuat(LocalRot), ToUnrealVector(LocalOffset), FVector::OneVector);
	}

	FProphecyNNPoseStore::SetAgentLocalPose(AgentIndex, Impl->PublishedBoneNames, Agent.LocalTransforms, SourceTimeSeconds);
}

void AProphecyNNCrowdBenchmarkActor::BuildAgentVisualBoneWorldPositions(int32 AgentIndex, float Alpha, TArray<FVector>& OutPositions) const
{
	OutPositions.SetNum(ProphecyBodyBoneCount);
	if (!Impl->Agents.IsValidIndex(AgentIndex))
	{
		return;
	}

	const FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
	const FVector3f VisualRoot = FMath::Lerp(Agent.PrevRootPos, Agent.CurRootPos, Alpha);
	const FTransform MeshTransform(
		FRotator(0.0, FMath::RadiansToDegrees(double(Agent.CurRootYaw)), 0.0),
		TrainingWorldToUnrealVector(VisualRoot),
		FVector::OneVector);

	Impl->ScratchBoneComponentTransforms.SetNumUninitialized(ProphecyBodyBoneCount);
	for (int32 BoneIndex = 0; BoneIndex < ProphecyBodyBoneCount; ++BoneIndex)
	{
		const FTransform LocalTransform = Agent.LocalTransforms.IsValidIndex(BoneIndex + 1)
			? Agent.LocalTransforms[BoneIndex + 1]
			: FTransform::Identity;
		const int32 ParentIndex = Impl->Parents.IsValidIndex(BoneIndex) ? Impl->Parents[BoneIndex] : INDEX_NONE;
		const FTransform ComponentTransform = ParentIndex >= 0 && Impl->ScratchBoneComponentTransforms.IsValidIndex(ParentIndex)
			? LocalTransform * Impl->ScratchBoneComponentTransforms[ParentIndex]
			: LocalTransform;
		Impl->ScratchBoneComponentTransforms[BoneIndex] = ComponentTransform;
		OutPositions[BoneIndex] = MeshTransform.TransformPosition(ComponentTransform.GetLocation());
	}
}

void AProphecyNNCrowdBenchmarkActor::UpdateVisualRoots()
{
	if (!bSpawnVisuals)
	{
		return;
	}

	if (ProxySegmentComponents.Num() > 0)
	{
		UpdateInstancedProxyVisuals();
		UpdateContactShadowVisuals();
		UpdateLimbShadowVisuals();
		UpdateGrassShadowMask();
		UpdateGroundShadowMask();
		return;
	}

	if (MetaHumanActors.Num() > 0)
	{
		UpdateMetaHumanRoots();
		UpdateContactShadowVisuals();
		UpdateLimbShadowVisuals();
		UpdateGrassShadowMask();
		UpdateGroundShadowMask();
		return;
	}

	const float StepSeconds = 1.0f / NNUpdateHz;
	const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
	for (int32 AgentIndex = 0; AgentIndex < MeshComponents.Num(); ++AgentIndex)
	{
		if (!MeshComponents[AgentIndex])
		{
			continue;
		}

		const FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
		const FVector3f VisualRoot = FMath::Lerp(Agent.PrevRootPos, Agent.CurRootPos, Alpha);
		MeshComponents[AgentIndex]->SetRelativeLocation(TrainingWorldToUnrealVector(VisualRoot));
		MeshComponents[AgentIndex]->SetRelativeRotation(FRotator(0.0, FMath::RadiansToDegrees(double(Agent.CurRootYaw)), 0.0));
	}
	UpdateContactShadowVisuals();
	UpdateLimbShadowVisuals();
	UpdateGrassShadowMask();
	UpdateGroundShadowMask();
}

void AProphecyNNCrowdBenchmarkActor::UpdateMetaHumanRoots()
{
	const float StepSeconds = 1.0f / NNUpdateHz;
	const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
	for (int32 VisualIndex = 0; VisualIndex < MetaHumanActors.Num(); ++VisualIndex)
	{
		AActor* MetaHumanActor = MetaHumanActors[VisualIndex];
		const int32 SourceAgentIndex = MetaHumanAgentIndices.IsValidIndex(VisualIndex) ? MetaHumanAgentIndices[VisualIndex] : VisualIndex;
		if (!MetaHumanActor || !Impl->Agents.IsValidIndex(SourceAgentIndex))
		{
			continue;
		}

		const FProphecyNNAgentRuntime& Agent = Impl->Agents[SourceAgentIndex];
		const FVector3f VisualRoot = FMath::Lerp(Agent.PrevRootPos, Agent.CurRootPos, Alpha);
		const FVector TierOffset = MetaHumanWorldOffsets.IsValidIndex(VisualIndex) ? MetaHumanWorldOffsets[VisualIndex] : FVector::ZeroVector;
		MetaHumanActor->SetActorLocationAndRotation(
			TrainingWorldToUnrealVector(VisualRoot) + TierOffset,
			FRotator(0.0, FMath::RadiansToDegrees(double(Agent.CurRootYaw)), 0.0),
			false,
			nullptr,
			ETeleportType::TeleportPhysics);
	}
}

void AProphecyNNCrowdBenchmarkActor::UpdateContactShadowVisuals()
{
	if (!ContactShadowComponent)
	{
		return;
	}

	const float StepSeconds = 1.0f / NNUpdateHz;
	const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
	Impl->ScratchTransforms.SetNumUninitialized(CrowdSize);
	const float ShadowZ = bSpawnGrass ? 24.0f : 0.45f;
	const bool bUseProjectedProxy = bSpawnGrass || bDebugShadowGeometry || IsRootContactShadowVariant(ContactShadowVariant) || IsFullDynamicShadowVariant(ContactShadowVariant);
	const FVector SunShadowDirection = GetGroundShadowDirectionForLight(BenchmarkKeyLight);
	const float SunShadowMeshYawDegrees = GetYawForLocalYAlignedShadowMesh(SunShadowDirection);
	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		const FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
		const FVector3f VisualRoot = FMath::Lerp(Agent.PrevRootPos, Agent.CurRootPos, Alpha);
		FVector Location = TrainingWorldToUnrealVector(VisualRoot);
		Location.Z = ShadowZ;
		FRotator ShadowRotation = FRotator(0.0, FMath::RadiansToDegrees(double(Agent.CurRootYaw)), 0.0);
		FVector Scale3D(ShouldAgentCastRealShadow(ShadowMode, RealShadowBudget, AgentIndex) ? 0.72f : 1.0f);
		Scale3D.Z = 1.0;

		if (bUseProjectedProxy)
		{
			BuildAgentVisualBoneWorldPositions(AgentIndex, Alpha, Impl->ScratchBoneWorldPositions);
			if (IsRootContactShadowVariant(ContactShadowVariant) || IsFullDynamicShadowVariant(ContactShadowVariant))
			{
				if (Impl->PelvisBoneIndex != INDEX_NONE &&
					Impl->ScratchBoneWorldPositions.IsValidIndex(Impl->PelvisBoneIndex))
				{
					Location = Impl->ScratchBoneWorldPositions[Impl->PelvisBoneIndex];
				}
				Location.Z = ShadowZ;
				ShadowRotation = FRotator(0.0, SunShadowMeshYawDegrees, 0.0);
				const double FullProxyScale = IsFullDynamicShadowVariant(ContactShadowVariant) ? 0.82 : 1.0;
				Scale3D = FVector(FullProxyScale, FullProxyScale, 1.0);
			}
			else if (Impl->LeftFootAnchorBoneIndex != INDEX_NONE &&
				Impl->RightFootAnchorBoneIndex != INDEX_NONE &&
				Impl->ScratchBoneWorldPositions.IsValidIndex(Impl->LeftFootAnchorBoneIndex) &&
				Impl->ScratchBoneWorldPositions.IsValidIndex(Impl->RightFootAnchorBoneIndex))
			{
				FVector Left = Impl->ScratchBoneWorldPositions[Impl->LeftFootAnchorBoneIndex];
				FVector Right = Impl->ScratchBoneWorldPositions[Impl->RightFootAnchorBoneIndex];
				Left.Z = ShadowZ;
				Right.Z = ShadowZ;
				const FVector FootDelta(Right.X - Left.X, Right.Y - Left.Y, 0.0);
				const double FootSeparation = FootDelta.Length();
				Location = (Left + Right) * 0.5;
				if (FootSeparation > 2.0)
				{
					ShadowRotation = FRotator(0.0, FMath::RadiansToDegrees(FMath::Atan2(FootDelta.Y, FootDelta.X)), 0.0);
					Scale3D = FVector(
						FMath::Clamp(FootSeparation / 18.0, 0.65, 2.5),
						IsFullDynamicShadowVariant(ContactShadowVariant) ? 0.75 : 1.0,
						1.0);
				}
				else
				{
					ShadowRotation = FRotator(0.0, FMath::RadiansToDegrees(double(Agent.CurRootYaw)), 0.0);
					Scale3D = FVector(IsFullDynamicShadowVariant(ContactShadowVariant) ? 0.75 : 1.0, IsFullDynamicShadowVariant(ContactShadowVariant) ? 0.75 : 1.0, 1.0);
				}
			}
		}

		bool bSuppressFullDynamicProxy = false;
		if (IsFullDynamicShadowVariant(ContactShadowVariant) && ShouldAgentCastRealShadow(ShadowMode, RealShadowBudget, AgentIndex))
		{
			if (BenchmarkCamera)
			{
				const double FallbackStartDistanceCm = bSpawnGrass ? 5600.0 : 4600.0;
				bSuppressFullDynamicProxy = FVector::DistSquared2D(Location, BenchmarkCamera->GetActorLocation()) < FMath::Square(FallbackStartDistanceCm);
			}
			else
			{
				bSuppressFullDynamicProxy = true;
			}
		}

		Impl->ScratchTransforms[AgentIndex] = bSuppressFullDynamicProxy
			? FTransform(ShadowRotation, Location, FVector::ZeroVector)
			: FTransform(ShadowRotation, Location, Scale3D);
	}
	ContactShadowComponent->BatchUpdateInstancesTransforms(0, Impl->ScratchTransforms, false, true, true);
}

void AProphecyNNCrowdBenchmarkActor::UpdateLimbShadowVisuals()
{
	if (!LimbShadowComponent || Impl->ShadowLimbSegments.Num() == 0)
	{
		return;
	}

	const float StepSeconds = 1.0f / NNUpdateHz;
	const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
	const int32 InstanceCount = Impl->ShadowLimbSegments.Num() * CrowdSize;
	Impl->ScratchTransforms.SetNumUninitialized(InstanceCount);

	constexpr float MeshSizeCm = 100.0f;
	const float SunProjectionScale = GetGroundShadowProjectionScaleForLight(BenchmarkKeyLight);
	const float ShadowZ = bSpawnGrass ? 24.0f : 0.45f;
	const FVector ShadowDirection = GetGroundShadowDirectionForLight(BenchmarkKeyLight);

	auto ProjectToShadowLayer = [this, ShadowDirection, ShadowZ, SunProjectionScale](const FVector& Position, int32 BoneIndex)
	{
		if (BoneIndex == Impl->LeftFootAnchorBoneIndex ||
			BoneIndex == Impl->RightFootAnchorBoneIndex ||
			BoneIndex == Impl->LeftFootBoneIndex ||
			BoneIndex == Impl->RightFootBoneIndex)
		{
			return FVector(Position.X, Position.Y, ShadowZ);
		}

		const double Height = FMath::Max(0.0, Position.Z - double(ShadowZ));
		return FVector(
			Position.X + ShadowDirection.X * Height * SunProjectionScale,
			Position.Y + ShadowDirection.Y * Height * SunProjectionScale,
			ShadowZ);
	};

	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		BuildAgentVisualBoneWorldPositions(AgentIndex, Alpha, Impl->ScratchBoneWorldPositions);
		for (int32 SegmentIndex = 0; SegmentIndex < Impl->ShadowLimbSegments.Num(); ++SegmentIndex)
		{
			FTransform SegmentTransform(FQuat::Identity, FVector::ZeroVector, FVector::ZeroVector);
			const FIntPoint Segment = Impl->ShadowLimbSegments[SegmentIndex];
			const float HalfWidthCm = Impl->ShadowLimbHalfWidthsCm.IsValidIndex(SegmentIndex) ? Impl->ShadowLimbHalfWidthsCm[SegmentIndex] : 8.0f;
			if (Impl->ScratchBoneWorldPositions.IsValidIndex(Segment.X) &&
				Impl->ScratchBoneWorldPositions.IsValidIndex(Segment.Y))
			{
				const FVector Parent = ProjectToShadowLayer(Impl->ScratchBoneWorldPositions[Segment.X], Segment.X);
				const FVector Child = ProjectToShadowLayer(Impl->ScratchBoneWorldPositions[Segment.Y], Segment.Y);
				const FVector Delta(Child.X - Parent.X, Child.Y - Parent.Y, 0.0);
				const double Length = Delta.Length();
				if (Length > 2.0)
				{
					const FVector Midpoint = (Parent + Child) * 0.5;
					const double YawDegrees = FMath::RadiansToDegrees(FMath::Atan2(Delta.Y, Delta.X));
					SegmentTransform = FTransform(
						FRotator(0.0, YawDegrees, 0.0),
						Midpoint,
						FVector(FMath::Max(Length * 1.25, 4.0) / MeshSizeCm, FMath::Max(HalfWidthCm * 2.7f, 4.0f) / MeshSizeCm, 1.0));
				}
			}

			const int32 InstanceIndex = SegmentIndex * CrowdSize + AgentIndex;
			Impl->ScratchTransforms[InstanceIndex] = SegmentTransform;
		}
	}

	LimbShadowComponent->BatchUpdateInstancesTransforms(0, Impl->ScratchTransforms, false, true, true);
}

void AProphecyNNCrowdBenchmarkActor::UpdateGrassShadowMask()
{
	if (!bSpawnGrass || !GrassShadowMaskTexture || !GrassMaterialInstance || Impl->GrassShadowMaskValues.Num() == 0)
	{
		return;
	}

	const int32 Size = Impl->GrassShadowMaskSize;
	const int32 PixelCount = Size * Size;
	if (Impl->GrassShadowMaskValues.Num() != PixelCount || Impl->GrassShadowMaskPixels.Num() != PixelCount)
	{
		return;
	}
	if (!bGrassDiagnosticMode && !bDebugShadowGeometry && Impl->LastGrassShadowMaskNNStep == Impl->Stats.NNStepCount)
	{
		return;
	}
	Impl->LastGrassShadowMaskNNStep = Impl->Stats.NNStepCount;

	if (Impl->StaticGrassShadowMaskValues.Num() == PixelCount)
	{
		FMemory::Memcpy(Impl->GrassShadowMaskValues.GetData(), Impl->StaticGrassShadowMaskValues.GetData(), PixelCount * sizeof(float));
	}
	else
	{
		for (float& Value : Impl->GrassShadowMaskValues)
		{
			Value = 0.0f;
		}
	}

	{
		const float StepSeconds = 1.0f / NNUpdateHz;
		const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
		const float SunProjectionScale = GetGroundShadowProjectionScaleForLight(BenchmarkKeyLight);
		const FVector SunShadowDirection = GetGroundShadowDirectionForLight(BenchmarkKeyLight);
		const FVector2D ShadowDirection(float(SunShadowDirection.X), float(SunShadowDirection.Y));
		const float CmPerPixel = (Impl->GrassShadowMaskHalfExtent * 2.0f) / float(Size);

		auto WorldToPixel = [this, Size](const FVector2D& World)
		{
			const float U = (World.X - (Impl->GrassShadowMaskCenter.X - Impl->GrassShadowMaskHalfExtent)) / (Impl->GrassShadowMaskHalfExtent * 2.0f);
			const float V = (World.Y - (Impl->GrassShadowMaskCenter.Y - Impl->GrassShadowMaskHalfExtent)) / (Impl->GrassShadowMaskHalfExtent * 2.0f);
			return FIntPoint(FMath::FloorToInt(U * float(Size)), FMath::FloorToInt(V * float(Size)));
		};

		auto ProjectToShadowLayer = [ShadowDirection](const FVector& Position, float ProjectionScale, bool bGrounded)
		{
			if (bGrounded)
			{
				return FVector2D(Position.X, Position.Y);
			}
			const float Height = FMath::Max(0.0f, float(Position.Z - 24.0));
			return FVector2D(Position.X, Position.Y) + ShadowDirection * Height * ProjectionScale;
		};

		auto StampCapsule = [this, Size, CmPerPixel, &WorldToPixel](const FVector2D& A, const FVector2D& B, float RadiusCm, float Strength)
		{
			constexpr int32 EdgePadPixels = 3;
			const float Radius = FMath::Max(RadiusCm, CmPerPixel * 0.55f);
			const FVector2D MinWorld(FMath::Min(A.X, B.X) - Radius, FMath::Min(A.Y, B.Y) - Radius);
			const FVector2D MaxWorld(FMath::Max(A.X, B.X) + Radius, FMath::Max(A.Y, B.Y) + Radius);
			const FIntPoint MinPixel = WorldToPixel(MinWorld);
			const FIntPoint MaxPixel = WorldToPixel(MaxWorld);
			if (MaxPixel.X < EdgePadPixels || MaxPixel.Y < EdgePadPixels || MinPixel.X > Size - 1 - EdgePadPixels || MinPixel.Y > Size - 1 - EdgePadPixels)
			{
				return;
			}
			const int32 X0 = FMath::Clamp(MinPixel.X, EdgePadPixels, Size - 1 - EdgePadPixels);
			const int32 Y0 = FMath::Clamp(MinPixel.Y, EdgePadPixels, Size - 1 - EdgePadPixels);
			const int32 X1 = FMath::Clamp(MaxPixel.X, EdgePadPixels, Size - 1 - EdgePadPixels);
			const int32 Y1 = FMath::Clamp(MaxPixel.Y, EdgePadPixels, Size - 1 - EdgePadPixels);
			const FVector2D Segment = B - A;
			const float SegmentLenSq = FMath::Max(Segment.SizeSquared(), 1.0f);
			const float InnerRadius = Radius * 0.46f;

			for (int32 Y = Y0; Y <= Y1; ++Y)
			{
				const float WorldY = Impl->GrassShadowMaskCenter.Y - Impl->GrassShadowMaskHalfExtent + (float(Y) + 0.5f) * CmPerPixel;
				for (int32 X = X0; X <= X1; ++X)
				{
					const float WorldX = Impl->GrassShadowMaskCenter.X - Impl->GrassShadowMaskHalfExtent + (float(X) + 0.5f) * CmPerPixel;
					const FVector2D Point(WorldX, WorldY);
					const float T = FMath::Clamp(FVector2D::DotProduct(Point - A, Segment) / SegmentLenSq, 0.0f, 1.0f);
					const FVector2D Closest = A + Segment * T;
					const float Distance = FVector2D::Distance(Point, Closest);
					if (Distance >= Radius)
					{
						continue;
					}

					const float EdgeT = FMath::Clamp((Distance - InnerRadius) / FMath::Max(Radius - InnerRadius, 1.0f), 0.0f, 1.0f);
					const float Soft = 1.0f - EdgeT * EdgeT * (3.0f - 2.0f * EdgeT);
					const int32 Index = Y * Size + X;
					Impl->GrassShadowMaskValues[Index] = FMath::Max(Impl->GrassShadowMaskValues[Index], Strength * Soft);
				}
			}
		};

		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			BuildAgentVisualBoneWorldPositions(AgentIndex, Alpha, Impl->ScratchBoneWorldPositions);
			if (Impl->ScratchBoneWorldPositions.Num() == 0)
			{
				continue;
			}

			if (IsRootContactShadowVariant(ContactShadowVariant))
			{
				if (Impl->PelvisBoneIndex != INDEX_NONE && Impl->ScratchBoneWorldPositions.IsValidIndex(Impl->PelvisBoneIndex))
				{
					const FVector Pelvis = Impl->ScratchBoneWorldPositions[Impl->PelvisBoneIndex];
					const float PelvisHeightCm = FMath::Max(80.0f, float(Pelvis.Z));
					const float RootShadowLengthCm = FMath::Clamp((PelvisHeightCm + 70.0f) * SunProjectionScale, 135.0f, 285.0f);
					const FVector2D Center(Pelvis.X, Pelvis.Y);
					const FVector2D Start = Center - ShadowDirection * 38.0f;
					const FVector2D End = Center + ShadowDirection * RootShadowLengthCm;
					StampCapsule(Start, End, 54.0f, (bGrassDiagnosticMode || bShadowMaskDiagnostic) ? 1.0f : (bDebugShadowGeometry ? 0.95f : 0.58f));
				}
			}
			else if (IsLimbContactShadowVariant(ContactShadowVariant) || IsFullDynamicShadowVariant(ContactShadowVariant))
			{
				for (int32 SegmentIndex = 0; SegmentIndex < Impl->ShadowLimbSegments.Num(); ++SegmentIndex)
				{
					const FIntPoint Segment = Impl->ShadowLimbSegments[SegmentIndex];
					if (!Impl->ScratchBoneWorldPositions.IsValidIndex(Segment.X) || !Impl->ScratchBoneWorldPositions.IsValidIndex(Segment.Y))
					{
						continue;
					}

					const bool bParentGrounded = Segment.X == Impl->LeftFootAnchorBoneIndex ||
						Segment.X == Impl->RightFootAnchorBoneIndex ||
						Segment.X == Impl->LeftFootBoneIndex ||
						Segment.X == Impl->RightFootBoneIndex;
					const bool bChildGrounded = Segment.Y == Impl->LeftFootAnchorBoneIndex ||
						Segment.Y == Impl->RightFootAnchorBoneIndex ||
						Segment.Y == Impl->LeftFootBoneIndex ||
						Segment.Y == Impl->RightFootBoneIndex;
					const FVector2D A = ProjectToShadowLayer(Impl->ScratchBoneWorldPositions[Segment.X], SunProjectionScale, bParentGrounded);
					const FVector2D B = ProjectToShadowLayer(Impl->ScratchBoneWorldPositions[Segment.Y], SunProjectionScale, bChildGrounded);
					const float HalfWidth = Impl->ShadowLimbHalfWidthsCm.IsValidIndex(SegmentIndex) ? Impl->ShadowLimbHalfWidthsCm[SegmentIndex] : 12.0f;
					const bool bFullGrassReceiver = IsFullDynamicShadowVariant(ContactShadowVariant);
					StampCapsule(A, B, HalfWidth * (bGrassDiagnosticMode || bDebugShadowGeometry ? 1.75f : 1.22f), (bGrassDiagnosticMode || bShadowMaskDiagnostic) ? 1.0f : (bFullGrassReceiver ? 0.62f : (bDebugShadowGeometry ? 0.82f : 0.54f)));
				}
			}
		}
	}

	for (int32 Index = 0; Index < PixelCount; ++Index)
	{
		const uint8 ByteValue = uint8(FMath::Clamp(Impl->GrassShadowMaskValues[Index], 0.0f, 1.0f) * 255.0f);
		Impl->GrassShadowMaskPixels[Index] = FColor(ByteValue, ByteValue, ByteValue, 255);
	}
	if (!Impl->bLoggedGrassShadowMaskStats)
	{
		float MaxValue = 0.0f;
		int32 NonZeroPixels = 0;
		for (const float Value : Impl->GrassShadowMaskValues)
		{
			MaxValue = FMath::Max(MaxValue, Value);
			NonZeroPixels += Value > 0.001f ? 1 : 0;
		}
		if (NonZeroPixels > 0)
		{
			Impl->bLoggedGrassShadowMaskStats = true;
			UE_LOG(
				LogProphecyNNBenchmark,
				Display,
				TEXT("Grass shadow mask populated: variant=%s size=%d half_extent=%.0fcm nonzero_pixels=%d max=%.3f"),
				*ContactShadowVariant,
				Size,
				Impl->GrassShadowMaskHalfExtent,
				NonZeroPixels,
				MaxValue);
		}
	}

	const int32 ByteCount = PixelCount * sizeof(FColor);
	uint8* UploadData = static_cast<uint8*>(FMemory::Malloc(ByteCount));
	FMemory::Memcpy(UploadData, Impl->GrassShadowMaskPixels.GetData(), ByteCount);
	FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, Size, Size);
	GrassShadowMaskTexture->UpdateTextureRegions(
		0,
		1,
		Region,
		uint32(Size * sizeof(FColor)),
		uint32(sizeof(FColor)),
		UploadData,
		[](uint8* SrcData, const FUpdateTextureRegion2D* Regions)
		{
			FMemory::Free(SrcData);
			delete Regions;
		});
}

void AProphecyNNCrowdBenchmarkActor::InitializeGroundShadowMask(const FVector2D& FieldCenter, float FieldHalfExtent)
{
	if (!FloorMaterialInstance)
	{
		return;
	}

	Impl->GroundShadowMaskCenter = FieldCenter;
	Impl->GroundShadowMaskHalfExtent = FMath::Max(FieldHalfExtent, 1.0f);
	Impl->GroundShadowMaskSize = (bDebugShadowGeometry || bShadowMaskDiagnostic || bCenterTreeDiagnostic) ? 512 : 256;
	const int32 PixelCount = Impl->GroundShadowMaskSize * Impl->GroundShadowMaskSize;
	Impl->GroundShadowMaskValues.SetNumZeroed(PixelCount);
	Impl->GroundShadowMaskPixels.SetNumZeroed(PixelCount);
	if (IsLimbContactShadowVariant(ContactShadowVariant))
	{
		InitializeShadowLimbSegments();
	}

	if (!GroundShadowMaskTexture)
	{
		GroundShadowMaskTexture = UTexture2D::CreateTransient(Impl->GroundShadowMaskSize, Impl->GroundShadowMaskSize, PF_B8G8R8A8, TEXT("ProphecyGroundShadowMask"));
		if (!GroundShadowMaskTexture)
		{
			return;
		}
		GroundShadowMaskTexture->SRGB = false;
		GroundShadowMaskTexture->Filter = TF_Bilinear;
		GroundShadowMaskTexture->AddressX = TA_Clamp;
		GroundShadowMaskTexture->AddressY = TA_Clamp;
		GroundShadowMaskTexture->UpdateResource();
	}

	FloorMaterialInstance->SetTextureParameterValue(TEXT("GroundShadowMask"), GroundShadowMaskTexture);
	FloorMaterialInstance->SetVectorParameterValue(TEXT("GroundShadowMaskCenter"), FLinearColor(FieldCenter.X, FieldCenter.Y, 0.0f, 0.0f));
	FloorMaterialInstance->SetScalarParameterValue(TEXT("GroundShadowMaskInvExtent"), 1.0f / (Impl->GroundShadowMaskHalfExtent * 2.0f));
	const bool bRootGrassGroundMask = bSpawnGrass && IsRootContactShadowVariant(ContactShadowVariant);
	const bool bLimbGrassGroundMask = bSpawnGrass && IsLimbContactShadowVariant(ContactShadowVariant);
	const float GroundMaskStrength = (bDebugShadowGeometry || bShadowMaskDiagnostic) ? 1.0f : (bRootGrassGroundMask ? 0.12f : (bLimbGrassGroundMask ? 0.58f : 0.82f));
	const FLinearColor GroundMaskTint = (bDebugShadowGeometry || bShadowMaskDiagnostic)
		? FLinearColor::Black
		: (bRootGrassGroundMask ? FLinearColor(0.20f, 0.35f, 0.15f, 1.0f) : (bLimbGrassGroundMask ? FLinearColor(0.13f, 0.20f, 0.10f, 1.0f) : FLinearColor(0.08f, 0.09f, 0.085f, 1.0f)));
	FloorMaterialInstance->SetScalarParameterValue(TEXT("GroundShadowMaskStrength"), GroundMaskStrength);
	FloorMaterialInstance->SetVectorParameterValue(TEXT("GroundShadowMaskTint"), GroundMaskTint);
	FloorMaterialInstance->SetTextureParameterValue(TEXT("GrassShadowMask"), GroundShadowMaskTexture);
	FloorMaterialInstance->SetVectorParameterValue(TEXT("GrassShadowMaskCenter"), FLinearColor(FieldCenter.X, FieldCenter.Y, 0.0f, 0.0f));
	FloorMaterialInstance->SetScalarParameterValue(TEXT("GrassShadowMaskInvExtent"), 1.0f / (Impl->GroundShadowMaskHalfExtent * 2.0f));
	FloorMaterialInstance->SetScalarParameterValue(TEXT("GrassShadowMaskStrength"), GroundMaskStrength);
	FloorMaterialInstance->SetVectorParameterValue(TEXT("GrassShadowMaskTint"), GroundMaskTint);
	BakeStaticTreeShadowMasks();
	UpdateGroundShadowMask();
}

void AProphecyNNCrowdBenchmarkActor::UpdateGroundShadowMask()
{
	if (!FloorMaterialInstance || !GroundShadowMaskTexture || Impl->GroundShadowMaskValues.Num() == 0)
	{
		return;
	}
	if (!bSpawnTrees && !IsRootContactShadowVariant(ContactShadowVariant) && !IsLimbContactShadowVariant(ContactShadowVariant))
	{
		return;
	}
	if (!bDebugShadowGeometry && Impl->LastGroundShadowMaskNNStep == Impl->Stats.NNStepCount)
	{
		return;
	}
	Impl->LastGroundShadowMaskNNStep = Impl->Stats.NNStepCount;

	const int32 Size = Impl->GroundShadowMaskSize;
	const int32 PixelCount = Size * Size;
	if (Impl->GroundShadowMaskValues.Num() != PixelCount || Impl->GroundShadowMaskPixels.Num() != PixelCount)
	{
		return;
	}

	if (Impl->StaticGroundShadowMaskValues.Num() == PixelCount)
	{
		FMemory::Memcpy(Impl->GroundShadowMaskValues.GetData(), Impl->StaticGroundShadowMaskValues.GetData(), PixelCount * sizeof(float));
	}
	else
	{
		for (float& Value : Impl->GroundShadowMaskValues)
		{
			Value = 0.0f;
		}
	}

	const float StepSeconds = 1.0f / NNUpdateHz;
	const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
	const float SunProjectionScale = GetGroundShadowProjectionScaleForLight(BenchmarkKeyLight);
	const FVector SunShadowDirection = GetGroundShadowDirectionForLight(BenchmarkKeyLight);
	const FVector2D ShadowDirection(float(SunShadowDirection.X), float(SunShadowDirection.Y));
	const float CmPerPixel = (Impl->GroundShadowMaskHalfExtent * 2.0f) / float(Size);

	auto WorldToPixel = [this, Size](const FVector2D& World)
	{
		const float U = (World.X - (Impl->GroundShadowMaskCenter.X - Impl->GroundShadowMaskHalfExtent)) / (Impl->GroundShadowMaskHalfExtent * 2.0f);
		const float V = (World.Y - (Impl->GroundShadowMaskCenter.Y - Impl->GroundShadowMaskHalfExtent)) / (Impl->GroundShadowMaskHalfExtent * 2.0f);
		return FIntPoint(FMath::FloorToInt(U * float(Size)), FMath::FloorToInt(V * float(Size)));
	};

	auto ProjectToShadowLayer = [ShadowDirection](const FVector& Position, float ProjectionScale, bool bGrounded)
	{
		if (bGrounded)
		{
			return FVector2D(Position.X, Position.Y);
		}
		const float Height = FMath::Max(0.0f, float(Position.Z - 0.45));
		return FVector2D(Position.X, Position.Y) + ShadowDirection * Height * ProjectionScale;
	};

	auto StampCapsuleMax = [this, Size, CmPerPixel, &WorldToPixel](const FVector2D& A, const FVector2D& B, float RadiusCm, float Strength)
	{
		constexpr int32 EdgePadPixels = 3;
		const float Radius = FMath::Max(RadiusCm, CmPerPixel * 0.60f);
		const FVector2D MinWorld(FMath::Min(A.X, B.X) - Radius, FMath::Min(A.Y, B.Y) - Radius);
		const FVector2D MaxWorld(FMath::Max(A.X, B.X) + Radius, FMath::Max(A.Y, B.Y) + Radius);
		const FIntPoint MinPixel = WorldToPixel(MinWorld);
		const FIntPoint MaxPixel = WorldToPixel(MaxWorld);
		if (MaxPixel.X < EdgePadPixels || MaxPixel.Y < EdgePadPixels || MinPixel.X > Size - 1 - EdgePadPixels || MinPixel.Y > Size - 1 - EdgePadPixels)
		{
			return;
		}
		const int32 X0 = FMath::Clamp(MinPixel.X, EdgePadPixels, Size - 1 - EdgePadPixels);
		const int32 Y0 = FMath::Clamp(MinPixel.Y, EdgePadPixels, Size - 1 - EdgePadPixels);
		const int32 X1 = FMath::Clamp(MaxPixel.X, EdgePadPixels, Size - 1 - EdgePadPixels);
		const int32 Y1 = FMath::Clamp(MaxPixel.Y, EdgePadPixels, Size - 1 - EdgePadPixels);
		const FVector2D Segment = B - A;
		const float SegmentLenSq = FMath::Max(Segment.SizeSquared(), 1.0f);
		const float InnerRadius = Radius * 0.46f;

		for (int32 Y = Y0; Y <= Y1; ++Y)
		{
			const float WorldY = Impl->GroundShadowMaskCenter.Y - Impl->GroundShadowMaskHalfExtent + (float(Y) + 0.5f) * CmPerPixel;
			for (int32 X = X0; X <= X1; ++X)
			{
				const float WorldX = Impl->GroundShadowMaskCenter.X - Impl->GroundShadowMaskHalfExtent + (float(X) + 0.5f) * CmPerPixel;
				const FVector2D Point(WorldX, WorldY);
				const float T = FMath::Clamp(FVector2D::DotProduct(Point - A, Segment) / SegmentLenSq, 0.0f, 1.0f);
				const FVector2D Closest = A + Segment * T;
				const float Distance = FVector2D::Distance(Point, Closest);
				if (Distance >= Radius)
				{
					continue;
				}

				const float EdgeT = FMath::Clamp((Distance - InnerRadius) / FMath::Max(Radius - InnerRadius, 1.0f), 0.0f, 1.0f);
				const float Soft = 1.0f - EdgeT * EdgeT * (3.0f - 2.0f * EdgeT);
				const int32 Index = Y * Size + X;
				Impl->GroundShadowMaskValues[Index] = FMath::Max(Impl->GroundShadowMaskValues[Index], Strength * Soft);
			}
		}
	};

	for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
	{
		if (ShouldAgentCastRealShadow(ShadowMode, RealShadowBudget, AgentIndex))
		{
			continue;
		}

		BuildAgentVisualBoneWorldPositions(AgentIndex, Alpha, Impl->ScratchBoneWorldPositions);
		if (Impl->ScratchBoneWorldPositions.Num() == 0)
		{
			continue;
		}

		if (IsRootContactShadowVariant(ContactShadowVariant))
		{
			if (Impl->PelvisBoneIndex != INDEX_NONE && Impl->ScratchBoneWorldPositions.IsValidIndex(Impl->PelvisBoneIndex))
			{
				const FVector Pelvis = Impl->ScratchBoneWorldPositions[Impl->PelvisBoneIndex];
				const float PelvisHeightCm = FMath::Max(80.0f, float(Pelvis.Z));
				const float RootShadowLengthCm = FMath::Clamp((PelvisHeightCm + 70.0f) * SunProjectionScale, 135.0f, 285.0f);
				const FVector2D Center(Pelvis.X, Pelvis.Y);
				const FVector2D Start = Center - ShadowDirection * 38.0f;
				const FVector2D End = Center + ShadowDirection * RootShadowLengthCm;
				StampCapsuleMax(Start, End, 54.0f, bShadowMaskDiagnostic ? 1.0f : (bDebugShadowGeometry ? 0.95f : 0.86f));
			}
		}
		else if (IsLimbContactShadowVariant(ContactShadowVariant))
		{
			for (int32 SegmentIndex = 0; SegmentIndex < Impl->ShadowLimbSegments.Num(); ++SegmentIndex)
			{
				const FIntPoint Segment = Impl->ShadowLimbSegments[SegmentIndex];
				if (!Impl->ScratchBoneWorldPositions.IsValidIndex(Segment.X) || !Impl->ScratchBoneWorldPositions.IsValidIndex(Segment.Y))
				{
					continue;
				}

				const bool bParentGrounded = Segment.X == Impl->LeftFootAnchorBoneIndex ||
					Segment.X == Impl->RightFootAnchorBoneIndex ||
					Segment.X == Impl->LeftFootBoneIndex ||
					Segment.X == Impl->RightFootBoneIndex;
				const bool bChildGrounded = Segment.Y == Impl->LeftFootAnchorBoneIndex ||
					Segment.Y == Impl->RightFootAnchorBoneIndex ||
					Segment.Y == Impl->LeftFootBoneIndex ||
					Segment.Y == Impl->RightFootBoneIndex;
				const FVector2D A = ProjectToShadowLayer(Impl->ScratchBoneWorldPositions[Segment.X], SunProjectionScale, bParentGrounded);
				const FVector2D B = ProjectToShadowLayer(Impl->ScratchBoneWorldPositions[Segment.Y], SunProjectionScale, bChildGrounded);
				const float HalfWidth = Impl->ShadowLimbHalfWidthsCm.IsValidIndex(SegmentIndex) ? Impl->ShadowLimbHalfWidthsCm[SegmentIndex] : 12.0f;
				StampCapsuleMax(A, B, HalfWidth * (bDebugShadowGeometry ? 1.75f : 1.22f), bShadowMaskDiagnostic ? 1.0f : (bDebugShadowGeometry ? 0.82f : 0.66f));
			}
		}
	}

	for (int32 Index = 0; Index < PixelCount; ++Index)
	{
		const uint8 ByteValue = uint8(FMath::Clamp(Impl->GroundShadowMaskValues[Index], 0.0f, 1.0f) * 255.0f);
		Impl->GroundShadowMaskPixels[Index] = FColor(ByteValue, ByteValue, ByteValue, 255);
	}
	if (!Impl->bLoggedGroundShadowMaskStats)
	{
		float MaxValue = 0.0f;
		int32 NonZeroPixels = 0;
		for (const float Value : Impl->GroundShadowMaskValues)
		{
			MaxValue = FMath::Max(MaxValue, Value);
			NonZeroPixels += Value > 0.001f ? 1 : 0;
		}
		Impl->bLoggedGroundShadowMaskStats = true;
		UE_LOG(
			LogProphecyNNBenchmark,
			Display,
			TEXT("Ground shadow max-mask initialized: variant=%s size=%d half_extent=%.0fcm nonzero_pixels=%d max=%.3f"),
			*ContactShadowVariant,
			Size,
			Impl->GroundShadowMaskHalfExtent,
			NonZeroPixels,
			MaxValue);
	}

	const int32 ByteCount = PixelCount * sizeof(FColor);
	uint8* UploadData = static_cast<uint8*>(FMemory::Malloc(ByteCount));
	FMemory::Memcpy(UploadData, Impl->GroundShadowMaskPixels.GetData(), ByteCount);
	FUpdateTextureRegion2D* Region = new FUpdateTextureRegion2D(0, 0, 0, 0, Size, Size);
	GroundShadowMaskTexture->UpdateTextureRegions(
		0,
		1,
		Region,
		uint32(Size * sizeof(FColor)),
		uint32(sizeof(FColor)),
		UploadData,
		[](uint8* SrcData, const FUpdateTextureRegion2D* Regions)
		{
			FMemory::Free(SrcData);
			delete Regions;
		});
}

void AProphecyNNCrowdBenchmarkActor::UpdateInstancedProxyVisuals()
{
	const float StepSeconds = 1.0f / NNUpdateHz;
	const float Alpha = FMath::Clamp(Impl->AccumulatedStepSeconds / StepSeconds, 0.0f, 1.0f);
	constexpr float SegmentThicknessCm = 8.0f;
	constexpr float MeshSizeCm = 100.0f;

	auto BuildSegmentTransform = [this, Alpha](const int32 SegmentIndex, const int32 AgentIndex, const float SegmentThicknessCm, const float MeshSizeCm)
	{
		FTransform SegmentTransform = FTransform::Identity;
		if (!Impl->ProxySegments.IsValidIndex(SegmentIndex))
		{
			return SegmentTransform;
		}

		const int32 ParentBoneIndex = Impl->ProxySegments[SegmentIndex].X;
		const int32 ChildBoneIndex = Impl->ProxySegments[SegmentIndex].Y;
		const FProphecyNNAgentRuntime& Agent = Impl->Agents[AgentIndex];
		const FVector3f ParentTrainingPos = FMath::Lerp(
			Agent.PrevRootPos + Agent.PrevPose.CanonPos[ParentBoneIndex],
			Agent.CurRootPos + Agent.CurPose.CanonPos[ParentBoneIndex],
			Alpha);
		const FVector3f ChildTrainingPos = FMath::Lerp(
			Agent.PrevRootPos + Agent.PrevPose.CanonPos[ChildBoneIndex],
			Agent.CurRootPos + Agent.CurPose.CanonPos[ChildBoneIndex],
			Alpha);

		const FVector Parent = TrainingWorldToUnrealVector(ParentTrainingPos);
		const FVector Child = TrainingWorldToUnrealVector(ChildTrainingPos);
		const FVector Delta = Child - Parent;
		const double Length = Delta.Length();
		if (Length > UE_SMALL_NUMBER)
		{
			const FVector Direction = Delta / Length;
			SegmentTransform.SetLocation((Parent + Child) * 0.5);
			SegmentTransform.SetRotation(FQuat::FindBetweenNormals(FVector::UpVector, Direction));
			SegmentTransform.SetScale3D(FVector(SegmentThicknessCm / MeshSizeCm, SegmentThicknessCm / MeshSizeCm, Length / MeshSizeCm));
		}
		return SegmentTransform;
	};

	if (Impl->bSingleProxyComponent && ProxySegmentComponents.Num() == 1 && ProxySegmentComponents[0])
	{
		const int32 InstanceCount = Impl->ProxySegments.Num() * CrowdSize;
		Impl->ScratchTransforms.SetNumUninitialized(InstanceCount);
		for (int32 SegmentIndex = 0; SegmentIndex < Impl->ProxySegments.Num(); ++SegmentIndex)
		{
			for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
			{
				const int32 InstanceIndex = SegmentIndex * CrowdSize + AgentIndex;
				Impl->ScratchTransforms[InstanceIndex] = BuildSegmentTransform(SegmentIndex, AgentIndex, SegmentThicknessCm, MeshSizeCm);
			}
		}
		ProxySegmentComponents[0]->BatchUpdateInstancesTransforms(0, Impl->ScratchTransforms, false, true, true);
		return;
	}

	for (int32 SegmentIndex = 0; SegmentIndex < ProxySegmentComponents.Num(); ++SegmentIndex)
	{
		UInstancedStaticMeshComponent* Component = ProxySegmentComponents[SegmentIndex];
		if (!Component || !Impl->ProxySegments.IsValidIndex(SegmentIndex))
		{
			continue;
		}

		Impl->ScratchTransforms.SetNumUninitialized(CrowdSize);
		for (int32 AgentIndex = 0; AgentIndex < CrowdSize; ++AgentIndex)
		{
			Impl->ScratchTransforms[AgentIndex] = BuildSegmentTransform(SegmentIndex, AgentIndex, SegmentThicknessCm, MeshSizeCm);
		}
		Component->BatchUpdateInstancesTransforms(0, Impl->ScratchTransforms, false, true, true);
	}
}

void AProphecyNNCrowdBenchmarkActor::SetupBenchmarkView()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	int32 DisabledExistingLightComponentCount = 0;
	int32 DisabledExistingSkyLightComponentCount = 0;
	int32 HiddenExistingSkyMeshComponentCount = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* ExistingActor = *It;
		if (!ExistingActor || ExistingActor == this)
		{
			continue;
		}

		bool bDisabledActorLighting = false;
		TArray<ULightComponent*> LightComponents;
		ExistingActor->GetComponents(LightComponents);
		for (ULightComponent* ExistingLightComponent : LightComponents)
		{
			if (!ExistingLightComponent)
			{
				continue;
			}

			ExistingLightComponent->SetCastShadows(false);
			ExistingLightComponent->SetIntensity(0.0f);
			ExistingLightComponent->SetVisibility(false, true);
			ExistingLightComponent->Deactivate();
			ExistingLightComponent->MarkRenderStateDirty();
			++DisabledExistingLightComponentCount;
			bDisabledActorLighting = true;
		}

		TArray<USkyLightComponent*> SkyLightComponents;
		ExistingActor->GetComponents(SkyLightComponents);
		for (USkyLightComponent* ExistingSkyLightComponent : SkyLightComponents)
		{
			if (!ExistingSkyLightComponent)
			{
				continue;
			}

			ExistingSkyLightComponent->SetCastShadows(false);
			ExistingSkyLightComponent->SetIntensity(0.0f);
			ExistingSkyLightComponent->SetVisibility(false, true);
			ExistingSkyLightComponent->Deactivate();
			ExistingSkyLightComponent->MarkRenderStateDirty();
			++DisabledExistingSkyLightComponentCount;
			bDisabledActorLighting = true;
		}

		if (bDisabledActorLighting)
		{
			ExistingActor->SetActorHiddenInGame(true);
		}

		TArray<UStaticMeshComponent*> StaticMeshComponents;
		ExistingActor->GetComponents(StaticMeshComponents);
		bool bHiddenActorSkyMesh = false;
		for (UStaticMeshComponent* ExistingMeshComponent : StaticMeshComponents)
		{
			if (!ExistingMeshComponent || !ExistingMeshComponent->GetStaticMesh())
			{
				continue;
			}

			const FString MeshPath = ExistingMeshComponent->GetStaticMesh()->GetPathName();
			const FString ActorName = ExistingActor->GetName();
			const FString ComponentName = ExistingMeshComponent->GetName();
			const bool bLooksLikeMapSkyDome =
				MeshPath.Contains(TEXT("SM_SkySphere"), ESearchCase::IgnoreCase) ||
				MeshPath.Contains(TEXT("SkySphere"), ESearchCase::IgnoreCase) ||
				ActorName.Contains(TEXT("SkySphere"), ESearchCase::IgnoreCase) ||
				ActorName.Contains(TEXT("Sky_Sphere"), ESearchCase::IgnoreCase) ||
				ComponentName.Contains(TEXT("SkySphere"), ESearchCase::IgnoreCase) ||
				ComponentName.Contains(TEXT("Sky_Sphere"), ESearchCase::IgnoreCase);
			if (!bLooksLikeMapSkyDome)
			{
				continue;
			}

			ExistingMeshComponent->SetVisibility(false, true);
			ExistingMeshComponent->SetHiddenInGame(true);
			ExistingMeshComponent->SetCastShadow(false);
			ExistingMeshComponent->SetCastContactShadow(false);
			ExistingMeshComponent->MarkRenderStateDirty();
			++HiddenExistingSkyMeshComponentCount;
			bHiddenActorSkyMesh = true;
		}
		if (bHiddenActorSkyMesh)
		{
			ExistingActor->SetActorHiddenInGame(true);
		}
	}
	if (DisabledExistingLightComponentCount > 0 || DisabledExistingSkyLightComponentCount > 0 || HiddenExistingSkyMeshComponentCount > 0)
	{
		UE_LOG(
			LogProphecyNNBenchmark,
			Display,
			TEXT("Disabled %d pre-existing light component(s), %d pre-existing sky light component(s), and %d pre-existing sky mesh component(s) for benchmark scene isolation."),
			DisabledExistingLightComponentCount,
			DisabledExistingSkyLightComponentCount,
			HiddenExistingSkyMeshComponentCount);
	}

	const bool bMetaHumanComparisonView =
		(bMetaHumanTierComparison || VisualMode.Equals(TEXT("MetaHumanComparison"), ESearchCase::IgnoreCase)) &&
		VisualMode.StartsWith(TEXT("MetaHuman"), ESearchCase::IgnoreCase);
	const bool bSingleAgentView = (!bSceneryOnly || bClosePreviewCamera || bMetaHumanComparisonView) && !bSpawnGrass && !bSpawnTrees && (CrowdSize <= 4 || bMetaHumanComparisonView);
	const bool bTreeOnlySceneryView = bSceneryOnly && bSpawnTrees && !bSpawnGrass;
	FString PreviewCameraSide;
	FParse::Value(FCommandLine::Get(), TEXT("ProphecyNNPreviewCameraSide="), PreviewCameraSide);
	const bool bFrontPreviewCamera =
		bSingleAgentView &&
		(FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNFrontPreview")) ||
			PreviewCameraSide.Equals(TEXT("Front"), ESearchCase::IgnoreCase));
	const FVector Center = TrainingWorldToUnrealVector(FVector3f(0.0f, 0.0f, bSingleAgentView ? 0.6f : 8.0f));
	const FVector LookAt = Center + (bSingleAgentView ? FVector(0.0, 0.0, 105.0) : (bTreeOnlySceneryView ? FVector(0.0, 4300.0, 520.0) : (bSpawnGrass ? FVector(0.0, 28500.0, 820.0) : FVector(0.0, 0.0, 120.0))));
	const FVector CameraLocation = Center + (bSingleAgentView ? (bMetaHumanComparisonView ? FVector(0.0, bFrontPreviewCamera ? 900.0 : -900.0, 185.0) : FVector(0.0, bFrontPreviewCamera ? 520.0 : -520.0, 150.0)) : (bTreeOnlySceneryView ? FVector(0.0, -4200.0, 680.0) : (bSpawnGrass ? FVector(0.0, -3000.0, 310.0) : FVector(0.0, -1700.0, 650.0))));

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	UStaticMesh* PlaneMesh = bSpawnBenchmarkFloor ? LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane")) : nullptr;
	UMaterialInterface* FloorMaterial = nullptr;
	if (bSpawnBenchmarkFloor)
	{
		const bool bUseGroundShadowMask = IsShadowEnabled(ShadowMode) && !IsFullDynamicShadowVariant(ContactShadowVariant) && (IsRootContactShadowVariant(ContactShadowVariant) || IsLimbContactShadowVariant(ContactShadowVariant));
		if (bSpawnGrass || bSpawnTrees || bUseGroundShadowMask)
		{
			FloorMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecyGrassGround.M_ProphecyGrassGround"));
		}
		if (!FloorMaterial)
		{
			FloorMaterial = CreateTintedMaterial(TEXT("ProphecyBenchmarkFloorMaterial"), (bSpawnGrass || bSpawnTrees) ? FLinearColor(0.105f, 0.210f, 0.070f, 1.0f) : FLinearColor(0.18f, 0.17f, 0.14f, 1.0f));
		}
	}
	if (bSpawnBenchmarkFloor && PlaneMesh)
	{
		FloorComponent = NewObject<UStaticMeshComponent>(this);
		FloorComponent->SetStaticMesh(PlaneMesh);
		FloorComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		FloorComponent->SetCastShadow(false);
		FloorComponent->SetCastContactShadow(false);
		FloorComponent->SetAffectDistanceFieldLighting(false);
		FloorComponent->SetAffectDynamicIndirectLighting(false);
		FloorComponent->SetVisibleInRayTracing(false);
		FloorComponent->SetReceivesDecals(false);
		FloorComponent->SetRelativeLocation(FVector(0.0, bSingleAgentView ? 0.0 : ((bSpawnGrass || bSpawnTrees) ? 12000.0 : 900.0), 0.0));
		FloorComponent->SetRelativeScale3D(FVector(bSingleAgentView ? 10.0 : ((bSpawnGrass || bSpawnTrees) ? 6000.0 : 42.0), bSingleAgentView ? 10.0 : ((bSpawnGrass || bSpawnTrees) ? 6000.0 : 34.0), 1.0));
		if (FloorMaterial)
		{
			FloorMaterialInstance = UMaterialInstanceDynamic::Create(FloorMaterial, this);
			if (FloorMaterialInstance)
			{
				FloorMaterialInstance->SetVectorParameterValue(TEXT("GroundBaseColor"), (bSpawnGrass || bSpawnTrees) ? ProphecyGrassGroundBaseColor : FLinearColor(0.56f, 0.55f, 0.50f, 1.0f));
				FloorMaterialInstance->SetScalarParameterValue(TEXT("GroundNoiseStrength"), (bSpawnGrass || bSpawnTrees) ? 0.55f : 0.82f);
				FloorMaterialInstance->SetVectorParameterValue(TEXT("DirtColor"), FLinearColor(0.52f, 0.36f, 0.18f, 1.0f));
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtStrength"), (bSpawnGrass || bSpawnTrees) ? 1.0f : 0.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtPatchScale"), 1.0f / 14000.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtPatchThreshold"), -1.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtPatchContrast"), 1.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtTextureScale"), 1.0f / 1600.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtTextureStrength"), 1.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtFadeStartCm"), 1500.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtFadeInvRange"), 1.0f / 900.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtViewMin"), 0.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("DirtViewScale"), 10.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("GroundShadowMaskStrength"), 0.0f);
				FloorMaterialInstance->SetScalarParameterValue(TEXT("GrassShadowMaskStrength"), 0.0f);
			}
			FloorComponent->SetMaterial(0, FloorMaterialInstance ? FloorMaterialInstance.Get() : FloorMaterial);
		}
		FloorComponent->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
		AddInstanceComponent(FloorComponent);
		FloorComponent->RegisterComponent();
		if (FloorMaterialInstance && IsShadowEnabled(ShadowMode) && (IsRootContactShadowVariant(ContactShadowVariant) || IsLimbContactShadowVariant(ContactShadowVariant)))
		{
			const FVector FloorLocation = FloorComponent->GetRelativeLocation();
			const FVector FloorScale = FloorComponent->GetRelativeScale3D();
			const FVector2D ShadowMaskCenter = bCenterTreeDiagnostic
				? FVector2D(0.0f, 4000.0f)
				: ((bSpawnGrass || bSpawnTrees) ? FVector2D(0.0f, 700.0f) : FVector2D(FloorLocation.X, FloorLocation.Y));
			const float FloorHalfExtent = bSpawnTrees
				? (bCenterTreeDiagnostic ? 7000.0f : ProphecyTreeShadowMaskHalfExtentCm)
				: (bSpawnGrass
					? (bGrassDiagnosticMode ? 4200.0f : 8000.0f)
					: FMath::Max(float(FloorScale.X), float(FloorScale.Y)) * 50.0f);
			InitializeGroundShadowMask(ShadowMaskCenter, FloorHalfExtent);
		}
		if (FloorMaterialInstance && (bSpawnGrass || bSpawnTrees))
		{
			InitializeBloodMask(FVector2D(0.0f, 700.0f), 12000.0f);
		}
	}

	if (bSpawnGrass || bSpawnTrees)
	{
		SpawnDistantGrassHills();
	}

	if (bSpawnTrees)
	{
		SpawnTreeField();
	}

	if ((bSpawnGrass || bSpawnTrees) && !bSpawnBenchmarkLights)
	{
		UStaticMesh* SkySphereMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
		UMaterialInterface* SkyMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Prophecy/Materials/M_ProphecySky_Unlit.M_ProphecySky_Unlit"));
		if (SkySphereMesh && SkyMaterial)
		{
			SkyDomeComponent = NewObject<UStaticMeshComponent>(this);
			SkyDomeComponent->SetStaticMesh(SkySphereMesh);
			SkyDomeComponent->SetMaterial(0, SkyMaterial);
			SkyDomeComponent->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			SkyDomeComponent->SetGenerateOverlapEvents(false);
			SkyDomeComponent->SetCastShadow(false);
			SkyDomeComponent->SetCastContactShadow(false);
			SkyDomeComponent->SetAffectDistanceFieldLighting(false);
			SkyDomeComponent->SetAffectDynamicIndirectLighting(false);
			SkyDomeComponent->SetVisibleInRayTracing(false);
			SkyDomeComponent->SetReceivesDecals(false);
			SkyDomeComponent->SetRelativeLocation(FVector::ZeroVector);
			SkyDomeComponent->SetRelativeScale3D(FVector(2600.0f));
			SkyDomeComponent->AttachToComponent(SceneRoot, FAttachmentTransformRules::KeepRelativeTransform);
			AddInstanceComponent(SkyDomeComponent);
			SkyDomeComponent->RegisterComponent();
		}
	}

	BenchmarkCamera = World->SpawnActor<ACameraActor>(CameraLocation, (LookAt - CameraLocation).Rotation(), Params);
	if (BenchmarkCamera)
	{
		BenchmarkCamera->GetCameraComponent()->FieldOfView = bMetaHumanComparisonView ? 78.0f : 68.0f;
		if (APlayerController* PlayerController = World->GetFirstPlayerController())
		{
			PlayerController->SetViewTarget(BenchmarkCamera);
			if (APawn* Pawn = PlayerController->GetPawn())
			{
				Pawn->SetActorHiddenInGame(true);
				Pawn->SetActorEnableCollision(false);
			}
		}
	}

	if (bSpawnBenchmarkLights)
	{
		const bool bGrassFullDynamicShadow = (bSpawnGrass || bDebugShadowGeometry) && IsFullDynamicShadowVariant(ContactShadowVariant);
		const FRotator BenchmarkSunRotation = (bSpawnGrass || bSpawnTrees)
			? FRotator(-19.0f, 31.0f, 0.0f)
			: FRotator(bGrassFullDynamicShadow ? -34.0f : -45.0f, 35.0f, 0.0f);
		BenchmarkKeyLight = World->SpawnActor<ADirectionalLight>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
		if (BenchmarkKeyLight && BenchmarkKeyLight->GetLightComponent())
		{
			if (UDirectionalLightComponent* DirectionalLight = Cast<UDirectionalLightComponent>(BenchmarkKeyLight->GetLightComponent()))
			{
				DirectionalLight->SetMobility(EComponentMobility::Movable);
				DirectionalLight->SetRelativeRotation(BenchmarkSunRotation);
				DirectionalLight->UpdateComponentToWorld();
			}
			BenchmarkKeyLight->GetLightComponent()->SetIntensity((bSpawnGrass || bSpawnTrees) ? 8.5f : 5.0f);
			BenchmarkKeyLight->GetLightComponent()->SetCastShadows(IsShadowEnabled(ShadowMode));
			BenchmarkKeyLight->GetLightComponent()->ShadowResolutionScale = 0.35f;
			if (UDirectionalLightComponent* DirectionalLight = Cast<UDirectionalLightComponent>(BenchmarkKeyLight->GetLightComponent()))
			{
				DirectionalLight->SetAtmosphereSunLight(true);
				DirectionalLight->SetAtmosphereSunLightIndex(0);
				DirectionalLight->SetAtmosphereSunDiskColorScale(FLinearColor(1.0f, 0.88f, 0.72f, 1.0f));
				DirectionalLight->SetLightSourceAngle(bGrassFullDynamicShadow && !bDebugShadowGeometry ? 1.15f : 0.53f);
				DirectionalLight->SetShadowSourceAngleFactor(bGrassFullDynamicShadow && !bDebugShadowGeometry ? 1.8f : 1.0f);
				DirectionalLight->SetShadowAmount(bGrassFullDynamicShadow && !bDebugShadowGeometry ? 0.38f : 1.0f);
				DirectionalLight->SetDynamicShadowDistanceMovableLight(bSpawnGrass ? 5600.0f : 4600.0f);
				DirectionalLight->DynamicShadowCascades = 1;
				DirectionalLight->CascadeTransitionFraction = 0.05f;
				DirectionalLight->ShadowDistanceFadeoutFraction = 0.12f;
				DirectionalLight->bUseInsetShadowsForMovableObjects = false;
				DirectionalLight->FarShadowCascadeCount = 0;
				DirectionalLight->FarShadowDistance = 0.0f;
				DirectionalLight->DistanceFieldShadowDistance = 0.0f;
				DirectionalLight->bCastShadowsOnClouds = true;
				DirectionalLight->bCastShadowsOnAtmosphere = true;
				DirectionalLight->bCastCloudShadows = true;
				DirectionalLight->CloudShadowStrength = 0.34f;
				DirectionalLight->CloudShadowOnAtmosphereStrength = 0.38f;
				DirectionalLight->CloudShadowOnSurfaceStrength = 0.08f;
				DirectionalLight->CloudShadowExtent = 80.0f;
				DirectionalLight->CloudShadowMapResolutionScale = 0.50f;
				DirectionalLight->CloudShadowRaySampleCountScale = 0.50f;
				DirectionalLight->CloudScatteredLuminanceScale = FLinearColor(1.0f, 0.90f, 0.78f, 1.0f);
			}

			const FVector ShadowDirection = GetGroundShadowDirectionForLight(BenchmarkKeyLight);
			UE_LOG(
				LogProphecyNNBenchmark,
				Display,
				TEXT("Benchmark sun projection: light_dir=(%.3f, %.3f, %.3f) fake_shadow_dir=(%.3f, %.3f) fake_shadow_scale=%.3f"),
				GetBenchmarkLightDirection(BenchmarkKeyLight).X,
				GetBenchmarkLightDirection(BenchmarkKeyLight).Y,
				GetBenchmarkLightDirection(BenchmarkKeyLight).Z,
				ShadowDirection.X,
				ShadowDirection.Y,
				GetGroundShadowProjectionScaleForLight(BenchmarkKeyLight));
		}

		BenchmarkSkyAtmosphere = World->SpawnActor<ASkyAtmosphere>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
		if (BenchmarkSkyAtmosphere)
		{
			if (USkyAtmosphereComponent* AtmosphereComponent = BenchmarkSkyAtmosphere->GetComponent())
			{
				AtmosphereComponent->SetRayleighScatteringScale(0.0370f);
				AtmosphereComponent->SetMieScatteringScale(0.0064f);
				AtmosphereComponent->SetMieAbsorptionScale(0.00026f);
				AtmosphereComponent->SetMieAnisotropy(0.82f);
				AtmosphereComponent->SetMultiScatteringFactor(1.22f);
				AtmosphereComponent->SetSkyLuminanceFactor(FLinearColor(1.52f, 1.60f, 1.82f, 1.0f));
				AtmosphereComponent->SetAerialPespectiveViewDistanceScale(1.10f);
				AtmosphereComponent->SetAerialPerspectiveStartDepth(0.03f);
				AtmosphereComponent->SetTransmittanceMinLightElevationAngle(-3.0f);
			}
		}

		BenchmarkVolumetricCloud = World->SpawnActor<AVolumetricCloud>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
		if (BenchmarkVolumetricCloud)
		{
			if (UVolumetricCloudComponent* CloudComponent = BenchmarkVolumetricCloud->FindComponentByClass<UVolumetricCloudComponent>())
			{
				if (UMaterialInterface* CloudMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst")))
				{
					BenchmarkCloudMaterialInstance = UMaterialInstanceDynamic::Create(CloudMaterial, this);
					if (BenchmarkCloudMaterialInstance)
					{
						BenchmarkCloudMaterialInstance->SetScalarParameterValue(TEXT("BrightnessMult"), 1.75f);
						BenchmarkCloudMaterialInstance->SetVectorParameterValue(TEXT("Cloud_AlbedoColor"), FLinearColor(1.0f, 0.96f, 0.90f, 1.0f));
						CloudComponent->SetMaterial(BenchmarkCloudMaterialInstance.Get());
					}
					else
					{
						CloudComponent->SetMaterial(CloudMaterial);
					}
				}
				CloudComponent->SetLayerBottomAltitude(3.6f);
				CloudComponent->SetLayerHeight(8.0f);
				CloudComponent->SetTracingStartMaxDistance(360.0f);
				CloudComponent->SetTracingMaxDistance(220.0f);
				CloudComponent->SetGroundAlbedo(FColor(78, 118, 62));
				CloudComponent->SetbUsePerSampleAtmosphericLightTransmittance(true);
				CloudComponent->SetSkyLightCloudBottomOcclusion(0.36f);
				CloudComponent->SetViewSampleCountScale(0.92f);
				CloudComponent->SetShadowViewSampleCountScale(0.55f);
				CloudComponent->SetReflectionViewSampleCountScale(0.25f);
				CloudComponent->SetShadowReflectionViewSampleCountScale(0.20f);
				CloudComponent->SetShadowTracingDistance(12.0f);
				CloudComponent->SetStopTracingTransmittanceThreshold(0.008f);
			}
		}

		BenchmarkSkyLight = World->SpawnActor<ASkyLight>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
		if (BenchmarkSkyLight && BenchmarkSkyLight->GetLightComponent())
		{
			if (USkyLightComponent* SkyLightComponent = BenchmarkSkyLight->GetLightComponent())
			{
				SkyLightComponent->SetMobility(EComponentMobility::Movable);
				SkyLightComponent->SetIntensity(2.6f);
				SkyLightComponent->SetRealTimeCapture(true);
				SkyLightComponent->SourceType = SLS_CapturedScene;
				SkyLightComponent->CubemapResolution = 256;
				SkyLightComponent->SkyDistanceThreshold = 150000.0f;
				SkyLightComponent->bLowerHemisphereIsBlack = true;
				SkyLightComponent->RecaptureSky();
			}
		}
	}

	if (bSpawnTrees)
	{
		BakeStaticTreeShadowMasks();
		UpdateGroundShadowMask();
		if (bSpawnGrass)
		{
			UpdateGrassShadowMask();
		}
	}
}

void AProphecyNNCrowdBenchmarkActor::PollLiveVisualIteration()
{
	if (!bLiveVisualIteration || LiveVisualConfigPath.IsEmpty())
	{
		return;
	}

	const double NowSeconds = FPlatformTime::Seconds();
	const double PollInterval = FMath::Max(double(LiveVisualPollSeconds), 0.05);
	if (NowSeconds - Impl->LastLiveVisualPollSeconds < PollInterval)
	{
		return;
	}
	Impl->LastLiveVisualPollSeconds = NowSeconds;

	const FString ConfigPath = ResolveProjectPath(LiveVisualConfigPath);
	if (!FPaths::FileExists(ConfigPath))
	{
		return;
	}

	const FDateTime ConfigTimestamp = IFileManager::Get().GetTimeStamp(*ConfigPath);
	if (ConfigTimestamp <= Impl->LastLiveVisualConfigTimestamp)
	{
		return;
	}

	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *ConfigPath))
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Live visual config exists but could not be read: %s"), *ConfigPath);
		return;
	}

	TSharedPtr<FJsonObject> RootObject;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, RootObject) || !RootObject.IsValid())
	{
		UE_LOG(LogProphecyNNBenchmark, Warning, TEXT("Live visual config is not valid JSON: %s"), *ConfigPath);
		return;
	}

	Impl->LastLiveVisualConfigTimestamp = ConfigTimestamp;
	ApplyLiveVisualIterationConfig(RootObject);
}

void AProphecyNNCrowdBenchmarkActor::ApplyLiveVisualIterationConfig(const TSharedPtr<FJsonObject>& RootObject)
{
	if (!RootObject.IsValid())
	{
		return;
	}

	auto TryNumber = [&RootObject](const TCHAR* FieldName, double& OutValue)
	{
		return RootObject->TryGetNumberField(FieldName, OutValue);
	};

	auto TryBool = [&RootObject](const TCHAR* FieldName, bool& bOutValue)
	{
		return RootObject->TryGetBoolField(FieldName, bOutValue);
	};

	auto TryColor = [&RootObject](const TCHAR* FieldName, FLinearColor& OutColor)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!RootObject->TryGetArrayField(FieldName, Values) || !Values || Values->Num() < 3)
		{
			return false;
		}
		if (!(*Values)[0].IsValid() || !(*Values)[1].IsValid() || !(*Values)[2].IsValid())
		{
			return false;
		}

		const double R = (*Values)[0]->AsNumber();
		const double G = (*Values)[1]->AsNumber();
		const double B = (*Values)[2]->AsNumber();
		const double A = Values->Num() >= 4 && (*Values)[3].IsValid() ? (*Values)[3]->AsNumber() : 1.0;
		OutColor = FLinearColor(float(R), float(G), float(B), float(A));
		return true;
	};

	auto TryVector = [&RootObject](const TCHAR* FieldName, FVector& OutVector)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!RootObject->TryGetArrayField(FieldName, Values) || !Values || Values->Num() < 3)
		{
			return false;
		}
		if (!(*Values)[0].IsValid() || !(*Values)[1].IsValid() || !(*Values)[2].IsValid())
		{
			return false;
		}

		OutVector = FVector((*Values)[0]->AsNumber(), (*Values)[1]->AsNumber(), (*Values)[2]->AsNumber());
		return true;
	};

	auto ApplyScalarParameter = [&TryNumber](UMaterialInstanceDynamic* Material, const TCHAR* JsonField, const TCHAR* AlternateJsonField, const TCHAR* ParameterName)
	{
		if (!Material)
		{
			return;
		}

		double Value = 0.0;
		if (TryNumber(JsonField, Value) || (AlternateJsonField && TryNumber(AlternateJsonField, Value)))
		{
			Material->SetScalarParameterValue(ParameterName, float(Value));
		}
	};

	auto ApplyColorParameter = [&TryColor](UMaterialInstanceDynamic* Material, const TCHAR* JsonField, const TCHAR* AlternateJsonField, const TCHAR* ParameterName)
	{
		if (!Material)
		{
			return;
		}

		FLinearColor Value;
		if (TryColor(JsonField, Value) || (AlternateJsonField && TryColor(AlternateJsonField, Value)))
		{
			Material->SetVectorParameterValue(ParameterName, Value);
		}
	};

	if (GrassMaterialInstance)
	{
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_enabled"), TEXT("GrassWindEnabled"), TEXT("GrassWindEnabled"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_bend_cm"), TEXT("GrassWindBendCm"), TEXT("GrassWindBendCm"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_lift_cm"), TEXT("GrassWindLiftCm"), TEXT("GrassWindLiftCm"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_world_freq"), TEXT("GrassWindWorldFrequency"), TEXT("GrassWindWorldFrequency"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_patch_freq"), TEXT("GrassWindPatchFrequency"), TEXT("GrassWindPatchFrequency"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_speed"), TEXT("GrassWindSpeed"), TEXT("GrassWindSpeed"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_wind_gust"), TEXT("GrassWindGustStrength"), TEXT("GrassWindGustStrength"));

		double RangeCm = 0.0;
		if ((TryNumber(TEXT("grass_distant_color_range_cm"), RangeCm) || TryNumber(TEXT("GrassDistantColorRangeCm"), RangeCm)) && RangeCm > UE_SMALL_NUMBER)
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantColorInvRange"), 1.0f / float(RangeCm));
		}

		double StartCm = 0.0;
		if (TryNumber(TEXT("grass_distant_color_start_cm"), StartCm) || TryNumber(TEXT("GrassDistantColorStartCm"), StartCm))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantColorStartCm"), float(StartCm));
		}

		double InvRange = 0.0;
		if (TryNumber(TEXT("grass_distant_color_inv_range"), InvRange) || TryNumber(TEXT("GrassDistantColorInvRange"), InvRange))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantColorInvRange"), float(InvRange));
		}

		FLinearColor GrassDistantColor;
		if (TryColor(TEXT("grass_distant_color"), GrassDistantColor) || TryColor(TEXT("GrassDistantColor"), GrassDistantColor))
		{
			GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassDistantColor"), GrassDistantColor);
		}

		double FarRootLiftStartCm = 0.0;
		if (TryNumber(TEXT("grass_far_root_lift_start_cm"), FarRootLiftStartCm) || TryNumber(TEXT("GrassFarRootLiftStartCm"), FarRootLiftStartCm))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassFarRootLiftStartCm"), float(FarRootLiftStartCm));
		}

		double FarRootLiftRangeCm = 0.0;
		if ((TryNumber(TEXT("grass_far_root_lift_range_cm"), FarRootLiftRangeCm) || TryNumber(TEXT("GrassFarRootLiftRangeCm"), FarRootLiftRangeCm)) && FarRootLiftRangeCm > UE_SMALL_NUMBER)
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassFarRootLiftInvRange"), 1.0f / float(FarRootLiftRangeCm));
		}

		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_far_root_lift_inv_range"), TEXT("GrassFarRootLiftInvRange"), TEXT("GrassFarRootLiftInvRange"));
		ApplyScalarParameter(GrassMaterialInstance.Get(), TEXT("grass_far_root_lift_strength"), TEXT("GrassFarRootLiftStrength"), TEXT("GrassFarRootLiftStrength"));
		ApplyColorParameter(GrassMaterialInstance.Get(), TEXT("grass_far_root_lift_color"), TEXT("GrassFarRootLiftColor"), TEXT("GrassFarRootLiftColor"));

		double FlattenStartCm = 0.0;
		if (TryNumber(TEXT("grass_distant_flatten_start_cm"), FlattenStartCm) || TryNumber(TEXT("GrassDistantFlattenStartCm"), FlattenStartCm))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenStartCm"), float(FlattenStartCm));
		}

		double FlattenRangeCm = 0.0;
		if ((TryNumber(TEXT("grass_distant_flatten_range_cm"), FlattenRangeCm) || TryNumber(TEXT("GrassDistantFlattenRangeCm"), FlattenRangeCm)) && FlattenRangeCm > UE_SMALL_NUMBER)
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenInvRange"), 1.0f / float(FlattenRangeCm));
		}

		double FlattenInvRange = 0.0;
		if (TryNumber(TEXT("grass_distant_flatten_inv_range"), FlattenInvRange) || TryNumber(TEXT("GrassDistantFlattenInvRange"), FlattenInvRange))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenInvRange"), float(FlattenInvRange));
		}

		double FlattenCm = 0.0;
		if (TryNumber(TEXT("grass_distant_flatten_cm"), FlattenCm) || TryNumber(TEXT("GrassDistantFlattenCm"), FlattenCm))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantFlattenCm"), float(FlattenCm));
		}

		double OpacityStartCm = 0.0;
		if (TryNumber(TEXT("grass_distant_opacity_start_cm"), OpacityStartCm) || TryNumber(TEXT("GrassDistantOpacityStartCm"), OpacityStartCm))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantOpacityStartCm"), float(OpacityStartCm));
		}

		double OpacityRangeCm = 0.0;
		if ((TryNumber(TEXT("grass_distant_opacity_range_cm"), OpacityRangeCm) || TryNumber(TEXT("GrassDistantOpacityRangeCm"), OpacityRangeCm)) && OpacityRangeCm > UE_SMALL_NUMBER)
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantOpacityInvRange"), 1.0f / float(OpacityRangeCm));
		}

		double OpacityInvRange = 0.0;
		if (TryNumber(TEXT("grass_distant_opacity_inv_range"), OpacityInvRange) || TryNumber(TEXT("GrassDistantOpacityInvRange"), OpacityInvRange))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassDistantOpacityInvRange"), float(OpacityInvRange));
		}

		double GrassShadowStrength = 0.0;
		if (TryNumber(TEXT("grass_shadow_strength"), GrassShadowStrength) || TryNumber(TEXT("GrassShadowMaskStrength"), GrassShadowStrength))
		{
			GrassMaterialInstance->SetScalarParameterValue(TEXT("GrassShadowMaskStrength"), float(GrassShadowStrength));
		}

		FLinearColor GrassShadowTint;
		if (TryColor(TEXT("grass_shadow_tint"), GrassShadowTint) || TryColor(TEXT("GrassShadowMaskTint"), GrassShadowTint))
		{
			GrassMaterialInstance->SetVectorParameterValue(TEXT("GrassShadowMaskTint"), GrassShadowTint);
		}
	}

	auto ApplyGroundMaterialParameters = [&](UMaterialInstanceDynamic* Material)
	{
		if (!Material)
		{
			return;
		}

		Material->SetScalarParameterValue(TEXT("GroundGrassGrainFrequency"), UE_TWO_PI / ProphecyGroundGrassGrainWorldCm);
		Material->SetScalarParameterValue(TEXT("GroundGrassGrainStrength"), ProphecyGroundGrassGrainStrength);
		Material->SetVectorParameterValue(TEXT("GroundGrassGrainDarkColor"), ProphecyGroundGrassGrainDarkColor);
		Material->SetVectorParameterValue(TEXT("GroundGrassGrainLightColor"), ProphecyGroundGrassGrainLightColor);
		ApplyScalarParameter(Material, TEXT("ground_noise_strength"), TEXT("GroundNoiseStrength"), TEXT("GroundNoiseStrength"));
		ApplyScalarParameter(Material, TEXT("ground_noise_scale"), TEXT("GroundNoiseScale"), TEXT("GroundNoiseScale"));
		ApplyScalarParameter(Material, TEXT("ground_grass_grain_strength"), TEXT("GroundGrassGrainStrength"), TEXT("GroundGrassGrainStrength"));
		ApplyScalarParameter(Material, TEXT("ground_grass_grain_frequency"), TEXT("GroundGrassGrainFrequency"), TEXT("GroundGrassGrainFrequency"));
		ApplyColorParameter(Material, TEXT("ground_base_color"), TEXT("GroundBaseColor"), TEXT("GroundBaseColor"));
		ApplyColorParameter(Material, TEXT("ground_grass_grain_dark_color"), TEXT("GroundGrassGrainDarkColor"), TEXT("GroundGrassGrainDarkColor"));
		ApplyColorParameter(Material, TEXT("ground_grass_grain_light_color"), TEXT("GroundGrassGrainLightColor"), TEXT("GroundGrassGrainLightColor"));
		ApplyColorParameter(Material, TEXT("dirt_color"), TEXT("DirtColor"), TEXT("DirtColor"));
		ApplyScalarParameter(Material, TEXT("dirt_strength"), TEXT("DirtStrength"), TEXT("DirtStrength"));
		ApplyScalarParameter(Material, TEXT("dirt_patch_scale"), TEXT("DirtPatchScale"), TEXT("DirtPatchScale"));
		ApplyScalarParameter(Material, TEXT("dirt_patch_threshold"), TEXT("DirtPatchThreshold"), TEXT("DirtPatchThreshold"));
		ApplyScalarParameter(Material, TEXT("dirt_patch_contrast"), TEXT("DirtPatchContrast"), TEXT("DirtPatchContrast"));
		ApplyScalarParameter(Material, TEXT("dirt_texture_scale"), TEXT("DirtTextureScale"), TEXT("DirtTextureScale"));
		ApplyScalarParameter(Material, TEXT("dirt_texture_strength"), TEXT("DirtTextureStrength"), TEXT("DirtTextureStrength"));
		ApplyScalarParameter(Material, TEXT("dirt_fade_start_cm"), TEXT("DirtFadeStartCm"), TEXT("DirtFadeStartCm"));
		ApplyScalarParameter(Material, TEXT("dirt_fade_inv_range"), TEXT("DirtFadeInvRange"), TEXT("DirtFadeInvRange"));
		ApplyScalarParameter(Material, TEXT("dirt_view_min"), TEXT("DirtViewMin"), TEXT("DirtViewMin"));
		ApplyScalarParameter(Material, TEXT("dirt_view_scale"), TEXT("DirtViewScale"), TEXT("DirtViewScale"));
		ApplyScalarParameter(Material, TEXT("ground_shadow_strength"), TEXT("GroundShadowMaskStrength"), TEXT("GroundShadowMaskStrength"));

		double GroundNoiseWorldCm = 0.0;
		if ((TryNumber(TEXT("ground_noise_world_cm"), GroundNoiseWorldCm) || TryNumber(TEXT("GroundNoiseWorldCm"), GroundNoiseWorldCm)) && GroundNoiseWorldCm > UE_SMALL_NUMBER)
		{
			Material->SetScalarParameterValue(TEXT("GroundNoiseScale"), 1.0f / float(GroundNoiseWorldCm));
		}

		double GroundGrassGrainWorldCm = 0.0;
		if ((TryNumber(TEXT("ground_grass_grain_world_cm"), GroundGrassGrainWorldCm) || TryNumber(TEXT("GroundGrassGrainWorldCm"), GroundGrassGrainWorldCm)) && GroundGrassGrainWorldCm > UE_SMALL_NUMBER)
		{
			Material->SetScalarParameterValue(TEXT("GroundGrassGrainFrequency"), UE_TWO_PI / float(GroundGrassGrainWorldCm));
		}

		double DirtPatchWorldCm = 0.0;
		if ((TryNumber(TEXT("dirt_patch_world_cm"), DirtPatchWorldCm) || TryNumber(TEXT("DirtPatchWorldCm"), DirtPatchWorldCm) ||
			TryNumber(TEXT("dirt_patch_size_cm"), DirtPatchWorldCm) || TryNumber(TEXT("DirtPatchSizeCm"), DirtPatchWorldCm)) && DirtPatchWorldCm > UE_SMALL_NUMBER)
		{
			Material->SetScalarParameterValue(TEXT("DirtPatchScale"), 1.0f / float(DirtPatchWorldCm));
		}

		double DirtTextureWorldCm = 0.0;
		if ((TryNumber(TEXT("dirt_texture_world_cm"), DirtTextureWorldCm) || TryNumber(TEXT("DirtTextureWorldCm"), DirtTextureWorldCm)) && DirtTextureWorldCm > UE_SMALL_NUMBER)
		{
			Material->SetScalarParameterValue(TEXT("DirtTextureScale"), 1.0f / float(DirtTextureWorldCm));
		}

		double DirtFadeRangeCm = 0.0;
		if ((TryNumber(TEXT("dirt_fade_range_cm"), DirtFadeRangeCm) || TryNumber(TEXT("DirtFadeRangeCm"), DirtFadeRangeCm)) && DirtFadeRangeCm > UE_SMALL_NUMBER)
		{
			Material->SetScalarParameterValue(TEXT("DirtFadeInvRange"), 1.0f / float(DirtFadeRangeCm));
		}
	};

	ApplyGroundMaterialParameters(FloorMaterialInstance.Get());
	ApplyGroundMaterialParameters(DistantHillsMaterialInstance.Get());

	if (!BloodMaskTexture && (FloorMaterialInstance || GrassMaterialInstance))
	{
		InitializeBloodMask(FVector2D(0.0f, 700.0f), 12000.0f);
	}

	auto ApplyBloodMaterialParameters = [&](UMaterialInstanceDynamic* Material)
	{
		if (!Material)
		{
			return;
		}

		ApplyColorParameter(Material, TEXT("blood_color"), TEXT("BloodColor"), TEXT("BloodColor"));
		ApplyColorParameter(Material, TEXT("blood_dark_color"), TEXT("BloodDarkColor"), TEXT("BloodDarkColor"));
		ApplyColorParameter(Material, TEXT("blood_grass_root_color"), TEXT("BloodGrassRootColor"), TEXT("BloodGrassRootColor"));
		ApplyColorParameter(Material, TEXT("blood_grass_color"), TEXT("BloodGrassColor"), TEXT("BloodGrassColor"));
		ApplyScalarParameter(Material, TEXT("blood_strength"), TEXT("BloodStrength"), TEXT("BloodStrength"));
		ApplyScalarParameter(Material, TEXT("blood_wet_strength"), TEXT("BloodWetStrength"), TEXT("BloodWetStrength"));
		ApplyScalarParameter(Material, TEXT("blood_grass_strength"), TEXT("BloodGrassStrength"), TEXT("BloodGrassStrength"));
	};
	ApplyBloodMaterialParameters(FloorMaterialInstance.Get());
	ApplyBloodMaterialParameters(GrassMaterialInstance.Get());

	bool bClearBlood = false;
	if (TryBool(TEXT("blood_clear"), bClearBlood) || TryBool(TEXT("BloodClear"), bClearBlood))
	{
		if (bClearBlood)
		{
			ClearBloodMask();
			UploadBloodMask();
		}
	}

	bool bBloodPreview = false;
	if (TryBool(TEXT("blood_preview"), bBloodPreview) || TryBool(TEXT("BloodPreview"), bBloodPreview))
	{
		if (bBloodPreview)
		{
			double RadiusScale = 1.0;
			TryNumber(TEXT("blood_radius_scale"), RadiusScale) || TryNumber(TEXT("BloodRadiusScale"), RadiusScale);
			double PreviewStrength = 0.86;
			TryNumber(TEXT("blood_preview_strength"), PreviewStrength) || TryNumber(TEXT("BloodPreviewStrength"), PreviewStrength) || TryNumber(TEXT("blood_strength"), PreviewStrength) || TryNumber(TEXT("BloodStrength"), PreviewStrength);
			GeneratePreviewBloodStains(float(RadiusScale), float(PreviewStrength));
		}
	}

	bool bHideGrass = false;
	if (TryBool(TEXT("hide_grass"), bHideGrass) || TryBool(TEXT("HideGrass"), bHideGrass))
	{
		const bool bVisible = !bHideGrass;
		for (UHierarchicalInstancedStaticMeshComponent* Component : GrassComponents)
		{
			if (Component)
			{
				Component->SetVisibility(bVisible, true);
				Component->SetHiddenInGame(!bVisible);
				Component->SetCullDistances(bVisible ? 0 : 0, bVisible ? 0 : 1);
			}
		}
		for (UNiagaraComponent* Component : NiagaraGrassComponents)
		{
			if (Component)
			{
				Component->SetVisibility(bVisible, true);
				Component->SetHiddenInGame(!bVisible);
				if (bVisible)
				{
					Component->Activate(true);
				}
				else
				{
					Component->Deactivate();
				}
			}
		}
	}

	bool bGrassVisible = false;
	if (TryBool(TEXT("grass_visible"), bGrassVisible) || TryBool(TEXT("GrassVisible"), bGrassVisible))
	{
		for (UHierarchicalInstancedStaticMeshComponent* Component : GrassComponents)
		{
			if (Component)
			{
				Component->SetVisibility(bGrassVisible, true);
				Component->SetHiddenInGame(!bGrassVisible);
				Component->SetCullDistances(bGrassVisible ? 0 : 0, bGrassVisible ? 0 : 1);
			}
		}
	}

	bool bHillsVisible = false;
	if ((TryBool(TEXT("hills_visible"), bHillsVisible) || TryBool(TEXT("HillsVisible"), bHillsVisible)) && DistantHillsComponent)
	{
		DistantHillsComponent->SetVisibility(bHillsVisible, true);
		DistantHillsComponent->SetHiddenInGame(!bHillsVisible);
	}

	if (BenchmarkCamera)
	{
		FVector CameraLocation;
		if (TryVector(TEXT("camera_location"), CameraLocation) || TryVector(TEXT("CameraLocation"), CameraLocation))
		{
			BenchmarkCamera->SetActorLocation(CameraLocation);
		}

		FVector CameraLookAt;
		if (TryVector(TEXT("camera_look_at"), CameraLookAt) || TryVector(TEXT("CameraLookAt"), CameraLookAt))
		{
			BenchmarkCamera->SetActorRotation((CameraLookAt - BenchmarkCamera->GetActorLocation()).Rotation());
		}

		double CameraFov = 0.0;
		if ((TryNumber(TEXT("camera_fov"), CameraFov) || TryNumber(TEXT("CameraFov"), CameraFov)) && CameraFov > 1.0)
		{
			if (UCameraComponent* CameraComponent = BenchmarkCamera->GetCameraComponent())
			{
				CameraComponent->SetFieldOfView(float(CameraFov));
			}
		}
	}

	if (BenchmarkKeyLight && BenchmarkKeyLight->GetLightComponent())
	{
		double SunIntensity = 0.0;
		if (TryNumber(TEXT("sun_intensity"), SunIntensity) || TryNumber(TEXT("SunIntensity"), SunIntensity))
		{
			BenchmarkKeyLight->GetLightComponent()->SetIntensity(float(SunIntensity));
		}

		double SunPitch = 0.0;
		double SunYaw = 0.0;
		double SunRoll = 0.0;
		const bool bHasPitch = TryNumber(TEXT("sun_pitch"), SunPitch) || TryNumber(TEXT("SunPitch"), SunPitch);
		const bool bHasYaw = TryNumber(TEXT("sun_yaw"), SunYaw) || TryNumber(TEXT("SunYaw"), SunYaw);
		const bool bHasRoll = TryNumber(TEXT("sun_roll"), SunRoll) || TryNumber(TEXT("SunRoll"), SunRoll);
		if (bHasPitch || bHasYaw || bHasRoll)
		{
			if (UDirectionalLightComponent* DirectionalLight = Cast<UDirectionalLightComponent>(BenchmarkKeyLight->GetLightComponent()))
			{
				FRotator Rotation = DirectionalLight->GetRelativeRotation();
				if (bHasPitch)
				{
					Rotation.Pitch = SunPitch;
				}
				if (bHasYaw)
				{
					Rotation.Yaw = SunYaw;
				}
				if (bHasRoll)
				{
					Rotation.Roll = SunRoll;
				}
				DirectionalLight->SetRelativeRotation(Rotation);
				DirectionalLight->UpdateComponentToWorld();
			}
		}
	}

	if (BenchmarkSkyLight && BenchmarkSkyLight->GetLightComponent())
	{
		double SkyIntensity = 0.0;
		if (TryNumber(TEXT("sky_intensity"), SkyIntensity) || TryNumber(TEXT("SkyIntensity"), SkyIntensity))
		{
			BenchmarkSkyLight->GetLightComponent()->SetIntensity(float(SkyIntensity));
			if (USkyLightComponent* SkyLightComponent = BenchmarkSkyLight->GetLightComponent())
			{
				SkyLightComponent->RecaptureSky();
			}
		}
	}

	bool bRequestScreenshot = false;
	RootObject->TryGetBoolField(TEXT("request_screenshot"), bRequestScreenshot);
	FString RequestedScreenshotPath;
	RootObject->TryGetStringField(TEXT("screenshot_path"), RequestedScreenshotPath);
	if (RequestedScreenshotPath.IsEmpty())
	{
		RootObject->TryGetStringField(TEXT("shot"), RequestedScreenshotPath);
	}

	if (bRequestScreenshot || !RequestedScreenshotPath.IsEmpty())
	{
		if (RequestedScreenshotPath.IsEmpty())
		{
			RequestedScreenshotPath = FPaths::ProjectSavedDir() / TEXT("LiveShots") / FString::Printf(TEXT("live_%04d.png"), ++Impl->LiveVisualScreenshotIndex);
		}
		const FString ResolvedScreenshotPath = ResolveProjectPath(RequestedScreenshotPath);
		IFileManager::Get().MakeDirectory(*FPaths::GetPath(ResolvedScreenshotPath), true);
		FScreenshotRequest::RequestScreenshot(ResolvedScreenshotPath, false, false);
		UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Live visual screenshot requested: %s"), *ResolvedScreenshotPath);
	}

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Applied live visual config."));
}

void AProphecyNNCrowdBenchmarkActor::LogProgressIfNeeded(float DeltaSeconds)
{
	FProphecyBenchmarkStats& Stats = Impl->Stats;
	Stats.ElapsedSeconds += DeltaSeconds;
	++Stats.FrameCount;

	if (Stats.ElapsedSeconds >= WarmupSeconds)
	{
		Stats.WarmedSeconds += DeltaSeconds;
		++Stats.WarmedFrameCount;
	}

	const bool bShouldLog = Stats.ElapsedSeconds - Stats.LastLogSeconds >= 2.0;
	if (bShouldLog)
	{
		Stats.LastLogSeconds = Stats.ElapsedSeconds;
		const double EffectiveSeconds = Stats.WarmedSeconds > UE_SMALL_NUMBER ? Stats.WarmedSeconds : Stats.ElapsedSeconds;
		const int64 EffectiveFrames = Stats.WarmedFrameCount > 0 ? Stats.WarmedFrameCount : Stats.FrameCount;
		const int64 EffectiveSteps = Stats.WarmedNNStepCount > 0 ? Stats.WarmedNNStepCount : FMath::Max<int64>(1, Stats.NNStepCount);
		const double FPS = double(EffectiveFrames) / FMath::Max(EffectiveSeconds, UE_SMALL_NUMBER);

		UE_LOG(
			LogProphecyNNBenchmark,
			Display,
			TEXT("ProphecyNN %.1fs fps=%.1f frame=%.2fms steps=%lld build=%.3fms inf=%.3fms out=%.3fms store=%.3fms visual=%.3fms runtime=%s"),
			Stats.ElapsedSeconds,
			FPS,
			Stats.SimSeconds * 1000.0 / double(FMath::Max<int64>(1, Stats.FrameCount)),
			Stats.NNStepCount,
			Stats.BuildInputSeconds * 1000.0 / double(EffectiveSteps),
			Stats.InferenceSeconds * 1000.0 / double(EffectiveSteps),
			Stats.OutputSeconds * 1000.0 / double(EffectiveSteps),
			Stats.StoreSeconds * 1000.0 / double(EffectiveSteps),
			Stats.VisualSeconds * 1000.0 / double(FMath::Max<int64>(1, Stats.FrameCount)),
			*Impl->Model.RuntimeUsed);
	}

	if (!Impl->bScreenshotRequested && !ScreenshotPath.IsEmpty() && Stats.ElapsedSeconds >= ScreenshotSeconds)
	{
		Impl->bScreenshotRequested = true;
		const FString ResolvedScreenshotPath = ResolveProjectPath(ScreenshotPath);
		FScreenshotRequest::RequestScreenshot(ResolvedScreenshotPath, false, false);
		UE_LOG(LogProphecyNNBenchmark, Display, TEXT("Requested benchmark screenshot: %s"), *ResolvedScreenshotPath);
	}

	if (!Impl->bRanFinalSummary && BenchmarkSeconds > 0.0f && Stats.ElapsedSeconds >= BenchmarkSeconds)
	{
		Impl->bRanFinalSummary = true;
		LogFinalSummary();
		if (bExitWhenDone)
		{
			FGenericPlatformMisc::RequestExit(false);
		}
	}
}

void AProphecyNNCrowdBenchmarkActor::LogFinalSummary() const
{
	const FProphecyBenchmarkStats& Stats = Impl->Stats;
	const double EffectiveSeconds = FMath::Max(Stats.WarmedSeconds, UE_SMALL_NUMBER);
	const int64 EffectiveFrames = FMath::Max<int64>(1, Stats.WarmedFrameCount);
	const int64 EffectiveSteps = FMath::Max<int64>(1, Stats.WarmedNNStepCount);

	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("========== Prophecy NN Benchmark Summary =========="));
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("profile=%s crowd=%d visuals=%d visual_mode=%s update_hz=%.1f shadow_mode=%s real_shadow_budget=%d contact_shadows=%d contact_shadow_variant=%s shadow_geometry_debug=%d limb_shadow_instances=%d floor=%d grass=%d grass_renderer=%s grass_wind=%d grass_wind_diagnostic=%d grass_wind_bend_cm=%.1f grass_wind_lift_cm=%.1f grass_patch_instances=%d grass_dense_patch_instances=%d grass_visual_blades=%lld trees=%d tree_instances=%d tree_wind=%d tree_wind_diagnostic=%d tree_wind_bend_cm=%.1f tree_wind_lift_cm=%.1f niagara_components=%d niagara_system=%s runtime=%s gpu=%d"),
		BenchmarkProfile.IsEmpty() ? TEXT("Custom") : *BenchmarkProfile,
		CrowdSize,
		bSpawnVisuals ? 1 : 0,
		*VisualMode,
		NNUpdateHz,
		*ShadowMode,
		RealShadowBudget,
		ContactShadowComponent ? 1 : 0,
		*ContactShadowVariant,
		bDebugShadowGeometry ? 1 : 0,
		LimbShadowComponent ? Impl->ShadowLimbSegments.Num() * CrowdSize : 0,
		bSpawnBenchmarkFloor ? 1 : 0,
		bSpawnGrass ? 1 : 0,
		*Impl->ActiveGrassRenderer,
		bGrassWind ? 1 : 0,
		bGrassWindDiagnostic ? 1 : 0,
		bGrassWindDiagnostic ? FMath::Max(GrassWindBendCm, 85.0f) : GrassWindBendCm,
		bGrassWindDiagnostic ? FMath::Max(GrassWindLiftCm, 100.0f) : GrassWindLiftCm,
		Impl->GrassInstanceCount,
		Impl->GrassDenseInstanceCount,
		Impl->GrassVisualBladeCount,
		bSpawnTrees ? 1 : 0,
		Impl->TreeInstanceCount,
		bTreeWind ? 1 : 0,
		bTreeWindDiagnostic ? 1 : 0,
		bTreeWindDiagnostic ? FMath::Max(TreeWindBendCm, 180.0f) : TreeWindBendCm,
		bTreeWindDiagnostic ? FMath::Max(TreeWindLiftCm, 85.0f) : TreeWindLiftCm,
		Impl->NiagaraComponentCount,
		*NiagaraGrassSystemPath,
		*Impl->Model.RuntimeUsed,
		Impl->Model.bUsingGpu ? 1 : 0);
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("render_settings=%s"), *Impl->AppliedRenderSettings);
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("fps=%.2f frame=%.3fms nn_steps=%lld"), double(EffectiveFrames) / EffectiveSeconds, Stats.SimSeconds * 1000.0 / double(FMath::Max<int64>(1, Stats.FrameCount)), Stats.NNStepCount);
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("per_nn_step_ms build=%.4f inference=%.4f output=%.4f store=%.4f"), Stats.BuildInputSeconds * 1000.0 / double(EffectiveSteps), Stats.InferenceSeconds * 1000.0 / double(EffectiveSteps), Stats.OutputSeconds * 1000.0 / double(EffectiveSteps), Stats.StoreSeconds * 1000.0 / double(EffectiveSteps));
	UE_LOG(LogProphecyNNBenchmark, Display, TEXT("per_frame_ms visual_roots=%.4f total_sim_tick=%.4f"), Stats.VisualSeconds * 1000.0 / double(FMath::Max<int64>(1, Stats.FrameCount)), Stats.SimSeconds * 1000.0 / double(FMath::Max<int64>(1, Stats.FrameCount)));
}

bool UProphecyNNBenchmarkWorldSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	return Super::ShouldCreateSubsystem(Outer) && FParse::Param(FCommandLine::Get(), TEXT("ProphecyNNBenchmark"));
}

void UProphecyNNBenchmarkWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	if (!InWorld.IsGameWorld() || BenchmarkActor)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.Name = TEXT("ProphecyNNCrowdBenchmark");
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	BenchmarkActor = InWorld.SpawnActor<AProphecyNNCrowdBenchmarkActor>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
}
