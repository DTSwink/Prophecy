#include "ProphecyDoubleReachAnimInstance.h"

#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AnimTypes.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Containers/StaticArray.h"

namespace ProphecyDoubleReach
{
enum class EJoint : uint8
{
	Root,
	Pelvis,
	Spine01,
	Spine02,
	Spine03,
	Spine04,
	Spine05,
	Neck01,
	Neck02,
	Head,
	ClavicleL,
	UpperArmL,
	LowerArmL,
	HandL,
	ClavicleR,
	UpperArmR,
	LowerArmR,
	HandR,
	ThighL,
	CalfL,
	FootL,
	BallL,
	ThighR,
	CalfR,
	FootR,
	BallR,
	Count
};

constexpr int32 JointCount = static_cast<int32>(EJoint::Count);
constexpr int32 ParameterCount = 6;
constexpr int32 LeftKey = 0;
constexpr int32 RightKey = 1;

const FName JointNames[JointCount] =
{
	TEXT("root"), TEXT("pelvis"),
	TEXT("spine_01"), TEXT("spine_02"), TEXT("spine_03"), TEXT("spine_04"), TEXT("spine_05"),
	TEXT("neck_01"), TEXT("neck_02"), TEXT("head"),
	TEXT("clavicle_l"), TEXT("upperarm_l"), TEXT("lowerarm_l"), TEXT("hand_l"),
	TEXT("clavicle_r"), TEXT("upperarm_r"), TEXT("lowerarm_r"), TEXT("hand_r"),
	TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"), TEXT("ball_l"),
	TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r")
};

using FJointPositions = TStaticArray<FVector, JointCount>;
using FJointTransforms = TStaticArray<FTransform, JointCount>;

constexpr int32 JointIndex(const EJoint Joint)
{
	return static_cast<int32>(Joint);
}

FVector& At(FJointPositions& Positions, const EJoint Joint)
{
	return Positions[JointIndex(Joint)];
}

const FVector& At(const FJointPositions& Positions, const EJoint Joint)
{
	return Positions[JointIndex(Joint)];
}

FVector SafeNormal(const FVector& Vector, const FVector& Fallback = FVector::ForwardVector)
{
	const double Length = Vector.Length();
	return Length > 1.0e-9 ? Vector / Length : Fallback;
}

double SmoothStep(const double Edge0, const double Edge1, const double Value)
{
	const double T = FMath::Clamp((Value - Edge0) / FMath::Max(1.0e-9, Edge1 - Edge0), 0.0, 1.0);
	return T * T * (3.0 - 2.0 * T);
}

double SmootherStep(const double Value)
{
	const double T = FMath::Clamp(Value, 0.0, 1.0);
	return T * T * T * (T * (T * 6.0 - 15.0) + 10.0);
}

FQuat BodyRotation(const double Yaw, const double Pitch, const double Roll)
{
	// The gym-to-Unreal mapping swaps its vertical and forward axes. That
	// reflection reverses axial-vector handedness, so mapped rotation angles
	// carry the opposite sign in Unreal component space.
	return FQuat(FVector::UpVector, -Yaw)
		* (FQuat(FVector::ForwardVector, -Pitch) * FQuat(FVector::RightVector, -Roll));
}

struct FBodyParameters
{
	double Drop = 0.0;
	double ShiftX = 0.0;
	double ShiftY = 0.0;
	double Yaw = 0.0;
	double Pitch = 0.0;
	double Roll = 0.0;
};

double GetParameter(const FBodyParameters& Parameters, const int32 Index)
{
	switch (Index)
	{
	case 0: return Parameters.Drop;
	case 1: return Parameters.ShiftX;
	case 2: return Parameters.ShiftY;
	case 3: return Parameters.Yaw;
	case 4: return Parameters.Pitch;
	default: return Parameters.Roll;
	}
}

void SetParameter(FBodyParameters& Parameters, const int32 Index, const double Value)
{
	switch (Index)
	{
	case 0: Parameters.Drop = Value; break;
	case 1: Parameters.ShiftX = Value; break;
	case 2: Parameters.ShiftY = Value; break;
	case 3: Parameters.Yaw = Value; break;
	case 4: Parameters.Pitch = Value; break;
	default: Parameters.Roll = Value; break;
	}
}

constexpr double ParameterMinimum[ParameterCount] = { 0.0, -0.18, -0.18, -0.95, -1.55, -0.95 };
constexpr double ParameterMaximum[ParameterCount] = { 0.72, 0.18, 0.18, 0.95, 1.55, 0.95 };
constexpr double EfficiencyScale[ParameterCount] = { 0.12, 0.10, 0.10, 0.30, 0.30, 0.30 };
constexpr double EfficiencyTrust[ParameterCount] = { 1.15, 1.0, 1.0, 1.15, 1.15, 1.15 };

FBodyParameters ClampParameters(FBodyParameters Parameters)
{
	for (int32 Index = 0; Index < ParameterCount; ++Index)
	{
		SetParameter(
			Parameters,
			Index,
			FMath::Clamp(GetParameter(Parameters, Index), ParameterMinimum[Index], ParameterMaximum[Index]));
	}
	return Parameters;
}

FBodyParameters BlendBodyParameters(
	const FBodyParameters& From,
	const FBodyParameters& To,
	const double Alpha)
{
	FBodyParameters Result;
	for (int32 Index = 0; Index < ParameterCount; ++Index)
	{
		SetParameter(Result, Index, FMath::Lerp(GetParameter(From, Index), GetParameter(To, Index), Alpha));
	}
	return Result;
}

FBodyParameters LimitBodyParameterMotion(
	const FBodyParameters& Current,
	const FBodyParameters& Target,
	const double DeltaSeconds,
	const double HalfLifeSeconds,
	const double TranslationSpeedMetersPerSecond,
	const double AngularSpeedRadiansPerSecond)
{
	if (DeltaSeconds <= UE_DOUBLE_SMALL_NUMBER)
	{
		return Current;
	}

	const double ResponseAlpha = HalfLifeSeconds <= UE_DOUBLE_SMALL_NUMBER
		? 1.0
		: 1.0 - FMath::Exp(-0.6931471805599453 * DeltaSeconds / HalfLifeSeconds);
	FBodyParameters Result;
	for (int32 Index = 0; Index < ParameterCount; ++Index)
	{
		const double CurrentValue = GetParameter(Current, Index);
		const double TargetValue = GetParameter(Target, Index);
		const double SpeedLimit = Index <= 2
			? TranslationSpeedMetersPerSecond
			: AngularSpeedRadiansPerSecond;
		const double RequestedStep = (TargetValue - CurrentValue) * ResponseAlpha;
		const double MaximumStep = FMath::Max(0.0, SpeedLimit) * DeltaSeconds;
		SetParameter(Result, Index, CurrentValue + FMath::Clamp(RequestedStep, -MaximumStep, MaximumStep));
	}
	return ClampParameters(Result);
}

bool AreBodyParametersNearlyZero(const FBodyParameters& Parameters)
{
	for (int32 Index = 0; Index < ParameterCount; ++Index)
	{
		if (FMath::Abs(GetParameter(Parameters, Index)) > 1.0e-5)
		{
			return false;
		}
	}
	return true;
}

struct FArmSpec
{
	double Sign = 1.0;
	EJoint Clavicle = EJoint::ClavicleL;
	EJoint Shoulder = EJoint::UpperArmL;
	EJoint Elbow = EJoint::LowerArmL;
	EJoint Hand = EJoint::HandL;
	double UpperLength = 0.0;
	double LowerLength = 0.0;
	double MaxReach = 0.0;
	double GirdleUpperLength = 0.0;
	double GirdleLowerLength = 0.0;
	FVector SourceDirection = FVector::ForwardVector;
};

struct FLegSpec
{
	double Sign = 1.0;
	EJoint Hip = EJoint::ThighL;
	EJoint Knee = EJoint::CalfL;
	EJoint Foot = EJoint::FootL;
	EJoint Ball = EJoint::BallL;
	double UpperLength = 0.0;
	double LowerLength = 0.0;
	FVector SourceBend = FVector::ForwardVector;
};

struct FArmResult
{
	FVector Shoulder = FVector::ZeroVector;
	FVector Elbow = FVector::ZeroVector;
	FVector Hand = FVector::ZeroVector;
	FVector Bend = FVector::ZeroVector;
	double Error = 0.0;
};

struct FLegResult
{
	FVector Knee = FVector::ZeroVector;
	double Error = 0.0;
	double ExtensionReserve = 0.0;
};

struct FSupportMetrics
{
	FVector CenterOfMass = FVector::ZeroVector;
	double Distance = 0.0;
	double Radius = 0.135;
	double Overflow = 0.0;
};

struct FSourcePose
{
	FJointPositions Positions;
	FJointTransforms ComponentTransforms;
	FArmSpec Arms[2];
	FLegSpec Legs[2];
};

struct FBodyPose
{
	FJointPositions Positions;
	FLegResult Legs[2];
	FSupportMetrics Balance;
	FBodyParameters Parameters;
	double LegError = 0.0;
};

struct FSolveResult
{
	FJointPositions Positions;
	FBodyParameters Parameters;
};

FArmSpec MakeArmSpec(const FSourcePose& Source, const bool bLeft)
{
	FArmSpec Spec;
	Spec.Sign = bLeft ? 1.0 : -1.0;
	Spec.Clavicle = bLeft ? EJoint::ClavicleL : EJoint::ClavicleR;
	Spec.Shoulder = bLeft ? EJoint::UpperArmL : EJoint::UpperArmR;
	Spec.Elbow = bLeft ? EJoint::LowerArmL : EJoint::LowerArmR;
	Spec.Hand = bLeft ? EJoint::HandL : EJoint::HandR;
	Spec.UpperLength = FVector::Distance(At(Source.Positions, Spec.Shoulder), At(Source.Positions, Spec.Elbow));
	Spec.LowerLength = FVector::Distance(At(Source.Positions, Spec.Elbow), At(Source.Positions, Spec.Hand));
	Spec.MaxReach = Spec.UpperLength + Spec.LowerLength;
	Spec.GirdleUpperLength = FVector::Distance(At(Source.Positions, EJoint::Spine05), At(Source.Positions, Spec.Clavicle));
	Spec.GirdleLowerLength = FVector::Distance(At(Source.Positions, Spec.Clavicle), At(Source.Positions, Spec.Shoulder));
	Spec.SourceDirection = SafeNormal(
		At(Source.Positions, Spec.Hand) - At(Source.Positions, Spec.Shoulder),
		FVector(Spec.Sign, 0.0, -1.0));
	return Spec;
}

FLegSpec MakeLegSpec(const FSourcePose& Source, const bool bLeft)
{
	FLegSpec Spec;
	Spec.Sign = bLeft ? 1.0 : -1.0;
	Spec.Hip = bLeft ? EJoint::ThighL : EJoint::ThighR;
	Spec.Knee = bLeft ? EJoint::CalfL : EJoint::CalfR;
	Spec.Foot = bLeft ? EJoint::FootL : EJoint::FootR;
	Spec.Ball = bLeft ? EJoint::BallL : EJoint::BallR;
	Spec.UpperLength = FVector::Distance(At(Source.Positions, Spec.Hip), At(Source.Positions, Spec.Knee));
	Spec.LowerLength = FVector::Distance(At(Source.Positions, Spec.Knee), At(Source.Positions, Spec.Foot));

	const FVector Direction = SafeNormal(
		At(Source.Positions, Spec.Foot) - At(Source.Positions, Spec.Hip),
		-FVector::UpVector);
	const double Distance = FVector::Distance(At(Source.Positions, Spec.Hip), At(Source.Positions, Spec.Foot));
	const double Along =
		(Spec.UpperLength * Spec.UpperLength - Spec.LowerLength * Spec.LowerLength + Distance * Distance)
		/ FMath::Max(2.0 * Distance, 1.0e-9);
	const FVector Center = At(Source.Positions, Spec.Hip) + Direction * Along;
	Spec.SourceBend = SafeNormal(
		At(Source.Positions, Spec.Knee) - Center,
		FVector(0.25 * Spec.Sign, 1.0, 0.0));
	return Spec;
}

FVector PreferredBend(const FArmSpec& Spec, const FVector& Direction)
{
	const FVector Outward(Spec.Sign, 0.0, 0.0);
	const FVector Preferred(Spec.Sign, -0.22, -0.28);
	const FVector OutwardProjected = Outward - Direction * FVector::DotProduct(Outward, Direction);
	FVector Projected = Preferred - Direction * FVector::DotProduct(Preferred, Direction);
	if (Projected.Length() < 1.0e-7)
	{
		const FVector Fallback(0.0, -0.65, -0.35);
		Projected = Fallback - Direction * FVector::DotProduct(Fallback, Direction);
	}

	FVector Bend = SafeNormal(Projected, FVector(Spec.Sign, 0.0, 0.0));
	const double OutwardProjectionLength = OutwardProjected.Length();
	if (OutwardProjectionLength > 1.0e-5)
	{
		const FVector OutwardTangent = OutwardProjected / OutwardProjectionLength;
		const double OutwardAmount = FVector::DotProduct(Bend, OutwardTangent);
		constexpr double MinimumOutward = 0.55;
		if (OutwardAmount < MinimumOutward)
		{
			const FVector Transverse = SafeNormal(
				FVector::CrossProduct(Direction, OutwardTangent) * Spec.Sign,
				FVector(0.0, -0.35, -1.0));
			FVector Canonical = SafeNormal(
				OutwardTangent * MinimumOutward
				+ Transverse * FMath::Sqrt(1.0 - MinimumOutward * MinimumOutward));
			if (FVector::DotProduct(Bend, Canonical) < 0.0)
			{
				Canonical *= -1.0;
			}
			const double Weight = SmoothStep(0.25, 0.55, OutwardProjectionLength)
				* SmoothStep(0.0, 0.15, MinimumOutward - OutwardAmount);
			Bend = SafeNormal(Bend * (1.0 - Weight) + Canonical * Weight, Canonical);
		}
	}
	return Bend;
}

FArmResult SolveArm(const FArmSpec& Spec, const FVector& Shoulder, const FVector& Target)
{
	FArmResult Result;
	Result.Shoulder = Shoulder;
	const FVector Raw = Target - Shoulder;
	const double RequestedDistance = Raw.Length();
	const FVector Direction = SafeNormal(Raw, Spec.SourceDirection);
	const double Minimum = FMath::Abs(Spec.UpperLength - Spec.LowerLength) + 1.0e-6;
	const double Maximum = Spec.MaxReach - 1.0e-6;
	const double ReachDistance = FMath::Clamp(RequestedDistance, Minimum, Maximum);
	Result.Hand = Shoulder + Direction * ReachDistance;
	const double Along =
		(Spec.UpperLength * Spec.UpperLength - Spec.LowerLength * Spec.LowerLength + ReachDistance * ReachDistance)
		/ FMath::Max(2.0 * ReachDistance, 1.0e-9);
	const double Height = FMath::Sqrt(FMath::Max(0.0, Spec.UpperLength * Spec.UpperLength - Along * Along));
	const FVector Center = Shoulder + Direction * Along;
	Result.Bend = PreferredBend(Spec, Direction);
	Result.Elbow = Center + Result.Bend * Height;
	Result.Error = FVector::Distance(Result.Hand, Target);
	return Result;
}

FVector ProjectElbowToFeasibleCircle(
	const FArmSpec& Spec,
	const FVector& Shoulder,
	const FVector& Hand,
	const FVector& NaturalElbow,
	const FVector& RequestedElbow)
{
	const FVector Raw = Hand - Shoulder;
	const double ReachDistance = Raw.Length();
	if (ReachDistance <= 1.0e-9)
	{
		return NaturalElbow;
	}

	const FVector Direction = Raw / ReachDistance;
	const double Along =
		(Spec.UpperLength * Spec.UpperLength
			- Spec.LowerLength * Spec.LowerLength
			+ ReachDistance * ReachDistance)
		/ (2.0 * ReachDistance);
	const double Height = FMath::Sqrt(FMath::Max(
		0.0,
		Spec.UpperLength * Spec.UpperLength - Along * Along));
	const FVector Center = Shoulder + Direction * Along;
	FVector RequestedBend = RequestedElbow - Center;
	RequestedBend -= Direction * FVector::DotProduct(RequestedBend, Direction);
	FVector NaturalBend = NaturalElbow - Center;
	NaturalBend -= Direction * FVector::DotProduct(NaturalBend, Direction);
	return Center + SafeNormal(RequestedBend, SafeNormal(NaturalBend, PreferredBend(Spec, Direction))) * Height;
}

FLegResult SolveLeg(const FSourcePose& Source, const FLegSpec& Spec, const FVector& Hip)
{
	FLegResult Result;
	const FVector& Foot = At(Source.Positions, Spec.Foot);
	const FVector Raw = Foot - Hip;
	const double RequestedDistance = Raw.Length();
	const FVector Direction = SafeNormal(Raw, -FVector::UpVector);
	const double Minimum = FMath::Abs(Spec.UpperLength - Spec.LowerLength) + 1.0e-6;
	const double Maximum = Spec.UpperLength + Spec.LowerLength - 1.0e-6;
	const double ReachDistance = FMath::Clamp(RequestedDistance, Minimum, Maximum);
	const double Along =
		(Spec.UpperLength * Spec.UpperLength - Spec.LowerLength * Spec.LowerLength + ReachDistance * ReachDistance)
		/ FMath::Max(2.0 * ReachDistance, 1.0e-9);
	const double Height = FMath::Sqrt(FMath::Max(0.0, Spec.UpperLength * Spec.UpperLength - Along * Along));
	const FVector Center = Hip + Direction * Along;
	FVector Bend = Spec.SourceBend - Direction * FVector::DotProduct(Spec.SourceBend, Direction);
	if (Bend.Length() < 1.0e-6)
	{
		const FVector Fallback(0.22 * Spec.Sign, 1.0, 0.0);
		Bend = Fallback - Direction * FVector::DotProduct(Fallback, Direction);
	}
	Bend = SafeNormal(Bend, FVector(0.2 * Spec.Sign, 1.0, 0.0));
	Result.Knee = Center + Bend * Height;
	Result.Error = FMath::Abs(RequestedDistance - ReachDistance);
	Result.ExtensionReserve = Maximum - RequestedDistance;
	return Result;
}

void PlaceBranch(
	FJointPositions& Positions,
	const FSourcePose& Source,
	const EJoint* Chain,
	const int32 ChainLength,
	EJoint Parent,
	const FQuat& Orientation)
{
	for (int32 Index = 0; Index < ChainLength; ++Index)
	{
		const EJoint Child = Chain[Index];
		At(Positions, Child) = At(Positions, Parent)
			+ Orientation.RotateVector(At(Source.Positions, Child) - At(Source.Positions, Parent));
		Parent = Child;
	}
}

FSupportMetrics SupportMetrics(const FSourcePose& Source, const FJointPositions& Positions)
{
	FSupportMetrics Result;
	const FVector LeftCenter = (At(Source.Positions, EJoint::FootL) + At(Source.Positions, EJoint::BallL)) * 0.5;
	const FVector RightCenter = (At(Source.Positions, EJoint::FootR) + At(Source.Positions, EJoint::BallR)) * 0.5;
	struct FWeightedJoint { EJoint Joint; double Weight; };
	const FWeightedJoint Weighted[] =
	{
		{ EJoint::Pelvis, 0.30 }, { EJoint::Spine03, 0.22 }, { EJoint::Spine05, 0.18 }, { EJoint::Head, 0.08 },
		{ EJoint::ThighL, 0.055 }, { EJoint::ThighR, 0.055 }, { EJoint::CalfL, 0.035 }, { EJoint::CalfR, 0.035 },
		{ EJoint::UpperArmL, 0.02 }, { EJoint::UpperArmR, 0.02 }
	};
	double TotalWeight = 0.0;
	for (const FWeightedJoint& Entry : Weighted)
	{
		Result.CenterOfMass += At(Positions, Entry.Joint) * Entry.Weight;
		TotalWeight += Entry.Weight;
	}
	Result.CenterOfMass /= TotalWeight;

	const FVector Segment = RightCenter - LeftCenter;
	const double SegmentLengthSquared = Segment.X * Segment.X + Segment.Y * Segment.Y;
	const FVector Relative = Result.CenterOfMass - LeftCenter;
	const double T = SegmentLengthSquared > 1.0e-9
		? FMath::Clamp((Relative.X * Segment.X + Relative.Y * Segment.Y) / SegmentLengthSquared, 0.0, 1.0)
		: 0.0;
	const FVector Closest = LeftCenter + Segment * T;
	Result.Distance = FVector2D(Result.CenterOfMass.X - Closest.X, Result.CenterOfMass.Y - Closest.Y).Length();
	Result.Overflow = FMath::Max(0.0, Result.Distance - Result.Radius);
	return Result;
}

FBodyPose BuildBodyPose(const FSourcePose& Source, FBodyParameters Parameters)
{
	FBodyPose Result;
	Parameters = ClampParameters(Parameters);
	Result.Parameters = Parameters;
	Result.Positions = Source.Positions;
	At(Result.Positions, EJoint::Pelvis) = At(Source.Positions, EJoint::Pelvis)
		+ FVector(Parameters.ShiftX, Parameters.ShiftY, -Parameters.Drop);

	const FQuat PelvisOrientation = BodyRotation(Parameters.Yaw * 0.15, 0.0, 0.0);
	const EJoint Spine[] = { EJoint::Spine01, EJoint::Spine02, EJoint::Spine03, EJoint::Spine04, EJoint::Spine05 };
	const FQuat SpineIncrement = BodyRotation(
		Parameters.Yaw * 0.85 / UE_ARRAY_COUNT(Spine),
		Parameters.Pitch / UE_ARRAY_COUNT(Spine),
		Parameters.Roll / UE_ARRAY_COUNT(Spine));
	FQuat SpineOrientation = PelvisOrientation;
	EJoint Parent = EJoint::Pelvis;
	for (const EJoint Child : Spine)
	{
		SpineOrientation = SpineIncrement * SpineOrientation;
		At(Result.Positions, Child) = At(Result.Positions, Parent)
			+ SpineOrientation.RotateVector(At(Source.Positions, Child) - At(Source.Positions, Parent));
		Parent = Child;
	}

	const EJoint Neck[] = { EJoint::Neck01, EJoint::Neck02, EJoint::Head };
	PlaceBranch(Result.Positions, Source, Neck, UE_ARRAY_COUNT(Neck), EJoint::Spine05, SpineOrientation);

	for (int32 Key = 0; Key < 2; ++Key)
	{
		const FArmSpec& Spec = Source.Arms[Key];
		const EJoint ArmChain[] = { Spec.Clavicle, Spec.Shoulder };
		PlaceBranch(Result.Positions, Source, ArmChain, UE_ARRAY_COUNT(ArmChain), EJoint::Spine05, SpineOrientation);
		At(Result.Positions, Spec.Elbow) = At(Result.Positions, Spec.Shoulder)
			+ SpineOrientation.RotateVector(At(Source.Positions, Spec.Elbow) - At(Source.Positions, Spec.Shoulder));
		At(Result.Positions, Spec.Hand) = At(Result.Positions, Spec.Elbow)
			+ SpineOrientation.RotateVector(At(Source.Positions, Spec.Hand) - At(Source.Positions, Spec.Elbow));
	}

	for (int32 Key = 0; Key < 2; ++Key)
	{
		const FLegSpec& Spec = Source.Legs[Key];
		At(Result.Positions, Spec.Hip) = At(Result.Positions, EJoint::Pelvis)
			+ PelvisOrientation.RotateVector(At(Source.Positions, Spec.Hip) - At(Source.Positions, EJoint::Pelvis));
		Result.Legs[Key] = SolveLeg(Source, Spec, At(Result.Positions, Spec.Hip));
		At(Result.Positions, Spec.Knee) = Result.Legs[Key].Knee;
		At(Result.Positions, Spec.Foot) = At(Source.Positions, Spec.Foot);
		At(Result.Positions, Spec.Ball) = At(Source.Positions, Spec.Ball);
	}
	Result.LegError = Result.Legs[0].Error + Result.Legs[1].Error;
	Result.Balance = SupportMetrics(Source, Result.Positions);
	return Result;
}

void ApplyShoulderGirdles(
	const FSourcePose& Source,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount,
	FBodyPose& Pose)
{
	for (int32 ActiveIndex = 0; ActiveIndex < KeyCount; ++ActiveIndex)
	{
		const int32 Key = Keys[ActiveIndex];
		const FArmSpec& Spec = Source.Arms[Key];
		const FVector Root = At(Pose.Positions, EJoint::Spine05);
		const FVector OriginalMid = At(Pose.Positions, Spec.Clavicle);
		const FVector OriginalEnd = At(Pose.Positions, Spec.Shoulder);
		const FVector TargetDirection = SafeNormal(Targets[Key] - OriginalEnd, FVector(Spec.Sign, 0.0, 0.0));
		const double ArmDistance = FVector::Distance(OriginalEnd, Targets[Key]);
		const double Demand = FMath::Clamp((ArmDistance - Spec.MaxReach * 0.80) / 0.20, 0.0, 1.0);
		const FVector DesiredEnd = OriginalEnd + TargetDirection * (0.065 * Demand);
		const FVector Raw = DesiredEnd - Root;
		const double RequestedDistance = Raw.Length();
		const FVector Direction = SafeNormal(
			Raw,
			SafeNormal(OriginalEnd - Root, FVector(Spec.Sign, 0.0, 0.0)));
		const double Minimum = FMath::Abs(Spec.GirdleUpperLength - Spec.GirdleLowerLength) + 1.0e-6;
		const double Maximum = Spec.GirdleUpperLength + Spec.GirdleLowerLength - 1.0e-6;
		const double ReachDistance = FMath::Clamp(RequestedDistance, Minimum, Maximum);
		const FVector End = Root + Direction * ReachDistance;
		const double Along =
			(Spec.GirdleUpperLength * Spec.GirdleUpperLength
				- Spec.GirdleLowerLength * Spec.GirdleLowerLength
				+ ReachDistance * ReachDistance)
			/ FMath::Max(2.0 * ReachDistance, 1.0e-9);
		const double Height = FMath::Sqrt(FMath::Max(
			0.0,
			Spec.GirdleUpperLength * Spec.GirdleUpperLength - Along * Along));
		const FVector Center = Root + Direction * Along;
		FVector Bend = OriginalMid - Center;
		Bend -= Direction * FVector::DotProduct(Bend, Direction);
		Bend = SafeNormal(Bend, FVector(0.0, 0.2 * Spec.Sign, 1.0));
		const FVector Mid = Center + Bend * Height;
		const FVector ShoulderDelta = End - OriginalEnd;
		At(Pose.Positions, Spec.Clavicle) = Mid;
		At(Pose.Positions, Spec.Shoulder) = End;
		At(Pose.Positions, Spec.Elbow) += ShoulderDelta;
		At(Pose.Positions, Spec.Hand) += ShoulderDelta;
	}
	Pose.Balance = SupportMetrics(Source, Pose.Positions);
}

FBodyPose EvaluateBodyPose(
	const FSourcePose& Source,
	const FBodyParameters Parameters,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount)
{
	FBodyPose Pose = BuildBodyPose(Source, Parameters);
	ApplyShoulderGirdles(Source, Targets, Keys, KeyCount, Pose);
	Pose.LegError = Pose.Legs[0].Error + Pose.Legs[1].Error;
	return Pose;
}

FBodyParameters MaximumBodyParameters(const FSourcePose& Source, const FVector& Target, const int32 Key)
{
	const FArmSpec& Spec = Source.Arms[Key];
	const FVector Shoulder = At(Source.Positions, Spec.Shoulder);
	const FVector Delta = Target - Shoulder;
	const double Distance = Delta.Length();
	const FVector Horizontal = SafeNormal(FVector(Delta.X, Delta.Y, 0.0), FVector(Spec.Sign, 0.0, 0.0));
	const double High = SmoothStep(0.12, 0.58, Target.Z - Shoulder.Z);
	const double Reach = SmoothStep(Spec.MaxReach * 0.72, Spec.MaxReach + 0.45, Distance);
	const double FloorLow = 1.0 - SmoothStep(0.04, 0.78, Target.Z);
	const double RelativeLow = SmoothStep(0.10, 0.82, Shoulder.Z - Target.Z);
	const double Low = FMath::Clamp(FloorLow + 0.22 * RelativeLow * Reach, 0.0, 1.0);
	const double Lean = FMath::Clamp(0.78 * Reach + 0.18 * Low + 0.10 * High, 0.0, 0.90);
	const double RearReach = SmoothStep(0.05, 0.90, -Horizontal.Y);
	const double HorizontalAngle = FMath::Asin(FMath::Clamp(Horizontal.X, -1.0, 1.0))
		+ Spec.Sign * UE_PI * RearReach;
	const double LowPitchLimit = 1.55 - 0.40 * Low;
	FBodyParameters Result;
	Result.Drop = 0.64 * Low + 0.10 * SmoothStep(0.18, 0.85, Reach) * (1.0 - High) * (1.0 - Low);
	Result.ShiftX = 0.15 * Horizontal.X * Reach * (1.0 - Low);
	Result.ShiftY = 0.15 * Horizontal.Y * Reach * (1.0 - Low);
	Result.Yaw = HorizontalAngle * 0.38 * Reach;
	Result.Pitch = FMath::Clamp(Horizontal.Y * Lean * (1.0 + 0.40 * Low), -LowPitchLimit, LowPitchLimit);
	Result.Roll = Horizontal.X * Lean * (2.0 * High - 1.0) * (1.0 + 0.65 * Low);
	return ClampParameters(Result);
}

FBodyParameters CombinedMaximumBodyParameters(
	const FSourcePose& Source,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount)
{
	if (KeyCount == 1)
	{
		return MaximumBodyParameters(Source, Targets[Keys[0]], Keys[0]);
	}
	FBodyParameters Requests[2];
	double Weights[2] = { 0.0, 0.0 };
	double WeightSum = 0.0;
	for (int32 Index = 0; Index < KeyCount; ++Index)
	{
		const int32 Key = Keys[Index];
		Requests[Index] = MaximumBodyParameters(Source, Targets[Key], Key);
		const double Distance = FVector::Distance(At(Source.Positions, Source.Arms[Key].Shoulder), Targets[Key]);
		Weights[Index] = 0.18 + SmoothStep(Source.Arms[Key].MaxReach * 0.72, Source.Arms[Key].MaxReach + 0.42, Distance);
		WeightSum += Weights[Index];
	}
	FBodyParameters Combined;
	for (int32 ParameterIndex = 0; ParameterIndex < ParameterCount; ++ParameterIndex)
	{
		double Value = 0.0;
		for (int32 Index = 0; Index < KeyCount; ++Index)
		{
			Value += GetParameter(Requests[Index], ParameterIndex) * Weights[Index];
		}
		SetParameter(Combined, ParameterIndex, Value / WeightSum);
	}
	const double SharedFloorReach =
		((1.0 - SmoothStep(0.04, 0.78, Targets[Keys[0]].Z))
			+ (1.0 - SmoothStep(0.04, 0.78, Targets[Keys[1]].Z)))
		* 0.5;
	Combined.Drop += 0.08 * SharedFloorReach;
	return ClampParameters(Combined);
}

FBodyParameters ParametersAtEngagement(
	const FBodyParameters& Maximum,
	const double Engagement,
	const bool bScaleDrop)
{
	FBodyParameters Result;
	for (int32 Index = 0; Index < ParameterCount; ++Index)
	{
		double Value = GetParameter(Maximum, Index);
		if (Index == 0)
		{
			Value *= bScaleDrop ? Engagement : 1.0;
		}
		else if (Index == 1 || Index == 2)
		{
			Value *= FMath::Pow(Engagement, 4.0);
		}
		else
		{
			Value *= Engagement;
		}
		SetParameter(Result, Index, Value);
	}
	return ClampParameters(Result);
}

bool IsFeasible(const FBodyPose& Pose)
{
	return Pose.LegError <= 1.0e-6 && Pose.Balance.Overflow <= 1.0e-6;
}

FBodyParameters StabilizeBothHandParameters(
	FBodyParameters Parameters,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount)
{
	Parameters = ClampParameters(Parameters);
	const double HorizontalShift = FVector2D(Parameters.ShiftX, Parameters.ShiftY).Length();
	const double StabilizingDrop = 0.06 * SmoothStep(0.015, 0.09, HorizontalShift);
	Parameters.Drop = FMath::Max(Parameters.Drop, StabilizingDrop);
	double LowTarget = 0.0;
	for (int32 Index = 0; Index < KeyCount; ++Index)
	{
		LowTarget += 1.0 - SmoothStep(0.04, 0.78, Targets[Keys[Index]].Z);
	}
	LowTarget /= KeyCount;
	const double LowPitchLimit = 1.55 - 0.40 * LowTarget;
	Parameters.Pitch = FMath::Clamp(Parameters.Pitch, -LowPitchLimit, LowPitchLimit);
	return Parameters;
}

struct FReachEfficiencyState
{
	FBodyPose Pose;
	double Distances[2] = { 0.0, 0.0 };
	double Residuals[2] = { 0.0, 0.0 };
	double WorstResidual = 0.0;
	bool bFeasible = false;
};

FReachEfficiencyState BodyReachEfficiencyState(
	const FSourcePose& Source,
	const FBodyParameters Parameters,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount)
{
	FReachEfficiencyState State;
	State.Pose = EvaluateBodyPose(
		Source,
		StabilizeBothHandParameters(Parameters, Targets, Keys, KeyCount),
		Targets,
		Keys,
		KeyCount);
	for (int32 Index = 0; Index < KeyCount; ++Index)
	{
		const int32 Key = Keys[Index];
		State.Distances[Index] = FVector::Distance(At(State.Pose.Positions, Source.Arms[Key].Shoulder), Targets[Key]);
		State.Residuals[Index] = FMath::Max(0.0, State.Distances[Index] - (Source.Arms[Key].MaxReach - 0.002));
		State.WorstResidual = FMath::Max(State.WorstResidual, State.Residuals[Index]);
	}
	State.bFeasible = IsFeasible(State.Pose);
	return State;
}

double RefinementFeasibilityScale(const FBodyPose& Pose)
{
	const double BalanceMargin = Pose.Balance.Radius - Pose.Balance.Distance;
	const double LegMargin = FMath::Min(Pose.Legs[0].ExtensionReserve, Pose.Legs[1].ExtensionReserve);
	return FMath::Min(SmoothStep(0.0, 0.025, BalanceMargin), SmoothStep(0.0, 0.025, LegMargin));
}

FBodyPose RefineBothHandBodyPose(
	const FSourcePose& Source,
	const FBodyPose& SeedPose,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount)
{
	const FBodyParameters Seed = StabilizeBothHandParameters(SeedPose.Parameters, Targets, Keys, KeyCount);
	FReachEfficiencyState Current = BodyReachEfficiencyState(Source, Seed, Targets, Keys, KeyCount);
	constexpr double Epsilon = 0.018;
	constexpr double DampingSquared = 0.08 * 0.08;
	for (int32 Iteration = 0; Iteration < 20; ++Iteration)
	{
		if (Current.WorstResidual <= 1.0e-5)
		{
			break;
		}
		double Jacobian[2][ParameterCount] = {};
		for (int32 ParameterIndex = 0; ParameterIndex < ParameterCount; ++ParameterIndex)
		{
			const double Offset = EfficiencyScale[ParameterIndex] * Epsilon;
			FBodyParameters Plus = Current.Pose.Parameters;
			FBodyParameters Minus = Current.Pose.Parameters;
			SetParameter(Plus, ParameterIndex, GetParameter(Plus, ParameterIndex) + Offset);
			SetParameter(Minus, ParameterIndex, GetParameter(Minus, ParameterIndex) - Offset);
			Plus = ClampParameters(Plus);
			Minus = ClampParameters(Minus);
			const FBodyPose PlusPose = EvaluateBodyPose(
				Source,
				StabilizeBothHandParameters(Plus, Targets, Keys, KeyCount),
				Targets,
				Keys,
				KeyCount);
			const FBodyPose MinusPose = EvaluateBodyPose(
				Source,
				StabilizeBothHandParameters(Minus, Targets, Keys, KeyCount),
				Targets,
				Keys,
				KeyCount);
			for (int32 KeyIndex = 0; KeyIndex < KeyCount; ++KeyIndex)
			{
				const int32 Key = Keys[KeyIndex];
				const double PlusDistance = FVector::Distance(At(PlusPose.Positions, Source.Arms[Key].Shoulder), Targets[Key]);
				const double MinusDistance = FVector::Distance(At(MinusPose.Positions, Source.Arms[Key].Shoulder), Targets[Key]);
				Jacobian[KeyIndex][ParameterIndex] = (PlusDistance - MinusDistance) / (2.0 * Epsilon);
			}
		}

		double A00 = DampingSquared;
		double A01 = 0.0;
		double A11 = DampingSquared;
		for (int32 ParameterIndex = 0; ParameterIndex < ParameterCount; ++ParameterIndex)
		{
			A00 += Jacobian[0][ParameterIndex] * Jacobian[0][ParameterIndex];
			A01 += Jacobian[0][ParameterIndex] * Jacobian[1][ParameterIndex];
			A11 += Jacobian[1][ParameterIndex] * Jacobian[1][ParameterIndex];
		}
		const double Determinant = A00 * A11 - A01 * A01;
		if (FMath::Abs(Determinant) < 1.0e-10)
		{
			break;
		}
		const double Y0 = (A11 * Current.Residuals[0] - A01 * Current.Residuals[1]) / Determinant;
		const double Y1 = (A00 * Current.Residuals[1] - A01 * Current.Residuals[0]) / Determinant;
		double NormalizedStep[ParameterCount] = {};
		for (int32 ParameterIndex = 0; ParameterIndex < ParameterCount; ++ParameterIndex)
		{
			if (Iteration >= 10 && ParameterIndex <= 2)
			{
				NormalizedStep[ParameterIndex] = 0.0;
				continue;
			}
			NormalizedStep[ParameterIndex] = FMath::Clamp(
				-(Jacobian[0][ParameterIndex] * Y0 + Jacobian[1][ParameterIndex] * Y1),
				-0.35,
				0.35);
		}

		FBodyParameters Candidate;
		const double Fraction = 0.22 * RefinementFeasibilityScale(Current.Pose);
		for (int32 ParameterIndex = 0; ParameterIndex < ParameterCount; ++ParameterIndex)
		{
			const double CurrentOffset =
				(GetParameter(Current.Pose.Parameters, ParameterIndex) - GetParameter(Seed, ParameterIndex))
				/ EfficiencyScale[ParameterIndex];
			const double NextOffset = FMath::Clamp(
				CurrentOffset + NormalizedStep[ParameterIndex] * Fraction,
				-EfficiencyTrust[ParameterIndex],
				EfficiencyTrust[ParameterIndex]);
			SetParameter(
				Candidate,
				ParameterIndex,
				GetParameter(Seed, ParameterIndex) + NextOffset * EfficiencyScale[ParameterIndex]);
		}
		FReachEfficiencyState Evaluated = BodyReachEfficiencyState(Source, Candidate, Targets, Keys, KeyCount);
		if (!Evaluated.bFeasible)
		{
			break;
		}
		Current = MoveTemp(Evaluated);
	}
	return Current.Pose;
}

FBodyPose SolveMarkovianBodyPose(
	const FSourcePose& Source,
	const FVector Targets[2],
	const int32* Keys,
	const int32 KeyCount)
{
	FBodyParameters Maximum = CombinedMaximumBodyParameters(Source, Targets, Keys, KeyCount);
	if (KeyCount == 2)
	{
		const FBodyPose Probe = EvaluateBodyPose(
			Source,
			ParametersAtEngagement(Maximum, 1.0, true),
			Targets,
			Keys,
			KeyCount);
		const double LeftDistance = FVector::Distance(At(Probe.Positions, Source.Arms[LeftKey].Shoulder), Targets[LeftKey]);
		const double RightDistance = FVector::Distance(At(Probe.Positions, Source.Arms[RightKey].Shoulder), Targets[RightKey]);
		const double Imbalance = FMath::Clamp((RightDistance - LeftDistance) / 0.18, -1.0, 1.0);
		Maximum.ShiftX -= 0.035 * Imbalance;
		Maximum.Yaw -= 0.12 * Imbalance;
		Maximum.Roll += 0.42 * Imbalance;
		Maximum = ClampParameters(Maximum);
	}

	auto PoseAt = [&](const double Engagement)
	{
		return EvaluateBodyPose(
			Source,
			ParametersAtEngagement(Maximum, Engagement, KeyCount > 1),
			Targets,
			Keys,
			KeyCount);
	};

	double FeasibleEngagement = 1.0;
	if (!IsFeasible(PoseAt(FeasibleEngagement)))
	{
		double Low = 0.0;
		double High = 1.0;
		for (int32 Iteration = 0; Iteration < 16; ++Iteration)
		{
			const double Middle = (Low + High) * 0.5;
			if (IsFeasible(PoseAt(Middle)))
			{
				Low = Middle;
			}
			else
			{
				High = Middle;
			}
		}
		FeasibleEngagement = Low;
	}

	auto WorstComfortExcess = [&](const FBodyPose& Pose)
	{
		double Worst = -DBL_MAX;
		for (int32 Index = 0; Index < KeyCount; ++Index)
		{
			const int32 Key = Keys[Index];
			const double Distance = FVector::Distance(At(Pose.Positions, Source.Arms[Key].Shoulder), Targets[Key]);
			Worst = FMath::Max(Worst, Distance - Source.Arms[Key].MaxReach * 0.90);
		}
		return Worst;
	};

	const FBodyPose Neutral = PoseAt(0.0);
	const double NeutralExcess = WorstComfortExcess(Neutral);
	if (KeyCount == 2)
	{
		const double Demand = SmoothStep(0.0, 0.18, FMath::Max(0.0, NeutralExcess));
		const FBodyPose Seed = PoseAt(FeasibleEngagement * Demand);
		return RefineBothHandBodyPose(Source, Seed, Targets, Keys, KeyCount);
	}

	if (NeutralExcess <= 0.0)
	{
		return Neutral;
	}
	const FBodyPose MaximumFeasible = PoseAt(FeasibleEngagement);
	if (WorstComfortExcess(MaximumFeasible) > 0.0)
	{
		return MaximumFeasible;
	}

	double Low = 0.0;
	double High = FeasibleEngagement;
	FBodyPose Best = MaximumFeasible;
	for (int32 Iteration = 0; Iteration < 16; ++Iteration)
	{
		const double Middle = (Low + High) * 0.5;
		FBodyPose Candidate = PoseAt(Middle);
		if (WorstComfortExcess(Candidate) > 0.0)
		{
			Low = Middle;
		}
		else
		{
			High = Middle;
			Best = MoveTemp(Candidate);
		}
	}
	return Best;
}

int32 ResolveModeKeys(const EProphecyDoubleReachMode Mode, int32 Keys[2])
{
	Keys[0] = LeftKey;
	Keys[1] = RightKey;
	switch (Mode)
	{
	case EProphecyDoubleReachMode::Left:
		Keys[0] = LeftKey;
		return 1;
	case EProphecyDoubleReachMode::Right:
		Keys[0] = RightKey;
		return 1;
	case EProphecyDoubleReachMode::Both:
		return 2;
	default:
		return 0;
	}
}

bool ModeUsesHand(const EProphecyDoubleReachMode Mode, const int32 Key)
{
	return Mode == EProphecyDoubleReachMode::Both
		|| (Mode == EProphecyDoubleReachMode::Left && Key == LeftKey)
		|| (Mode == EProphecyDoubleReachMode::Right && Key == RightKey);
}

FSolveResult SolveModeWithBodyParameters(
	const FSourcePose& Source,
	const FVector Targets[2],
	const EProphecyDoubleReachMode Mode,
	const FBodyParameters& Parameters)
{
	int32 Keys[2];
	const int32 KeyCount = ResolveModeKeys(Mode, Keys);
	FSolveResult Result;
	Result.Positions = Source.Positions;
	Result.Parameters = ClampParameters(Parameters);
	if (KeyCount == 0 && AreBodyParametersNearlyZero(Result.Parameters))
	{
		return Result;
	}

	FBodyPose Body = EvaluateBodyPose(Source, Result.Parameters, Targets, Keys, KeyCount);
	for (int32 Index = 0; Index < KeyCount; ++Index)
	{
		const int32 Key = Keys[Index];
		const FArmSpec& Spec = Source.Arms[Key];
		const FArmResult Arm = SolveArm(Spec, At(Body.Positions, Spec.Shoulder), Targets[Key]);
		At(Body.Positions, Spec.Elbow) = Arm.Elbow;
		At(Body.Positions, Spec.Hand) = Arm.Hand;
	}
	Result.Positions = Body.Positions;
	Result.Parameters = Body.Parameters;
	return Result;
}

FSolveResult SolveMode(
	const FSourcePose& Source,
	const FVector Targets[2],
	const EProphecyDoubleReachMode Mode)
{
	int32 Keys[2];
	const int32 KeyCount = ResolveModeKeys(Mode, Keys);
	if (KeyCount == 0)
	{
		FSolveResult Result;
		Result.Positions = Source.Positions;
		return Result;
	}

	const FBodyPose Body = SolveMarkovianBodyPose(Source, Targets, Keys, KeyCount);
	return SolveModeWithBodyParameters(Source, Targets, Mode, Body.Parameters);
}

FQuat AlignRotation(
	const FQuat& SourceRotation,
	const FVector& SourceDirection,
	const FVector& SolvedDirection)
{
	const FVector From = SafeNormal(SourceDirection);
	const FVector To = SafeNormal(SolvedDirection, From);
	return (FQuat::FindBetweenNormals(From, To) * SourceRotation).GetNormalized();
}

void BuildEndpointTransforms(
	const FSourcePose& Source,
	const FSolveResult& Solved,
	const EProphecyDoubleReachMode Mode,
	FJointTransforms& Output)
{
	Output = Source.ComponentTransforms;
	if (Mode == EProphecyDoubleReachMode::Off && AreBodyParametersNearlyZero(Solved.Parameters))
	{
		return;
	}

	for (int32 Index = 0; Index < JointCount; ++Index)
	{
		Output[Index].SetTranslation(Solved.Positions[Index] * 100.0);
	}

	const FQuat PelvisOrientation = BodyRotation(Solved.Parameters.Yaw * 0.15, 0.0, 0.0);
	const FQuat SpineIncrement = BodyRotation(
		Solved.Parameters.Yaw * 0.85 / 5.0,
		Solved.Parameters.Pitch / 5.0,
		Solved.Parameters.Roll / 5.0);
	FQuat SpineOrientation = PelvisOrientation;
	Output[JointIndex(EJoint::Pelvis)].SetRotation(
		(PelvisOrientation * Source.ComponentTransforms[JointIndex(EJoint::Pelvis)].GetRotation()).GetNormalized());
	const EJoint Spine[] = { EJoint::Spine01, EJoint::Spine02, EJoint::Spine03, EJoint::Spine04, EJoint::Spine05 };
	for (const EJoint Joint : Spine)
	{
		SpineOrientation = SpineIncrement * SpineOrientation;
		Output[JointIndex(Joint)].SetRotation(
			(SpineOrientation * Source.ComponentTransforms[JointIndex(Joint)].GetRotation()).GetNormalized());
	}
	for (const EJoint Joint : { EJoint::Neck01, EJoint::Neck02, EJoint::Head })
	{
		Output[JointIndex(Joint)].SetRotation(
			(SpineOrientation * Source.ComponentTransforms[JointIndex(Joint)].GetRotation()).GetNormalized());
	}

	auto AlignJointToChild = [&](const EJoint Joint, const EJoint Child)
	{
		Output[JointIndex(Joint)].SetRotation(AlignRotation(
			Source.ComponentTransforms[JointIndex(Joint)].GetRotation(),
			At(Source.Positions, Child) - At(Source.Positions, Joint),
			At(Solved.Positions, Child) - At(Solved.Positions, Joint)));
	};

	for (int32 Key = 0; Key < 2; ++Key)
	{
		const FArmSpec& Arm = Source.Arms[Key];
		AlignJointToChild(Arm.Clavicle, Arm.Shoulder);
		AlignJointToChild(Arm.Shoulder, Arm.Elbow);
		AlignJointToChild(Arm.Elbow, Arm.Hand);
		const FQuat HandSwing = FQuat::FindBetweenNormals(
			SafeNormal(At(Source.Positions, Arm.Hand) - At(Source.Positions, Arm.Elbow)),
			SafeNormal(At(Solved.Positions, Arm.Hand) - At(Solved.Positions, Arm.Elbow)));
		Output[JointIndex(Arm.Hand)].SetRotation(
			(HandSwing * Source.ComponentTransforms[JointIndex(Arm.Hand)].GetRotation()).GetNormalized());
	}
	for (int32 Key = 0; Key < 2; ++Key)
	{
		const FLegSpec& Leg = Source.Legs[Key];
		AlignJointToChild(Leg.Hip, Leg.Knee);
		AlignJointToChild(Leg.Knee, Leg.Foot);
		Output[JointIndex(Leg.Foot)].SetRotation(Source.ComponentTransforms[JointIndex(Leg.Foot)].GetRotation());
		Output[JointIndex(Leg.Ball)].SetRotation(Source.ComponentTransforms[JointIndex(Leg.Ball)].GetRotation());
	}
	for (FTransform& Transform : Output)
	{
		Transform.NormalizeRotation();
	}
}

FCompactPoseBoneIndex ResolveCompactBoneIndex(const FBoneContainer& RequiredBones, const FName BoneName)
{
	const int32 SkeletonIndex = RequiredBones.GetReferenceSkeleton().FindBoneIndex(BoneName);
	return SkeletonIndex == INDEX_NONE
		? FCompactPoseBoneIndex(INDEX_NONE)
		: RequiredBones.GetCompactPoseIndexFromSkeletonIndex(SkeletonIndex);
}
}

class FProphecyDoubleReachAnimInstanceProxy final : public FAnimInstanceProxy
{
public:
	FProphecyDoubleReachAnimInstanceProxy() = default;
	explicit FProphecyDoubleReachAnimInstanceProxy(UAnimInstance* Instance)
		: FAnimInstanceProxy(Instance)
	{
	}

protected:
	virtual void PreUpdate(UAnimInstance* InAnimInstance, float DeltaSeconds) override
	{
		FAnimInstanceProxy::PreUpdate(InAnimInstance, DeltaSeconds);
		const UProphecyDoubleReachAnimInstance* Instance = Cast<UProphecyDoubleReachAnimInstance>(InAnimInstance);
		if (!Instance)
		{
			return;
		}

		if (BaseAnimation != Instance->BaseAnimation)
		{
			BaseAnimation = Instance->BaseAnimation;
			AnimationTimeSeconds = 0.0;
		}
		AnimationPlayRate = Instance->AnimationPlayRate;
		bLoopAnimation = Instance->bLoopAnimation;
		LeftTargetComponentSpace = Instance->LeftTargetComponentSpace;
		RightTargetComponentSpace = Instance->RightTargetComponentSpace;
		TransitionDuration = FMath::Max(0.0f, Instance->TransitionDuration);
		bEnableUpperBodyMotionLimit = Instance->bEnableUpperBodyMotionLimit;
		if (!bEnableUpperBodyMotionLimit)
		{
			bFilteredBodyInitialized = false;
		}
		UpperBodySmoothingHalfLife = FMath::Max(0.0f, Instance->UpperBodySmoothingHalfLife);
		MaxPelvisTranslationSpeedCmPerSecond = FMath::Max(1.0f, Instance->MaxPelvisTranslationSpeedCmPerSecond);
		MaxSpineAngularSpeedDegreesPerSecond = FMath::Max(1.0f, Instance->MaxSpineAngularSpeedDegreesPerSecond);
		MaxHandVelocityCmPerSecond = FMath::Max(0.0f, Instance->MaxHandVelocityCmPerSecond);
		MaxElbowVelocityCmPerSecond = FMath::Max(0.0f, Instance->MaxElbowVelocityCmPerSecond);
		EvaluationDeltaSeconds = FMath::Clamp(DeltaSeconds, 0.0f, 0.1f);

		const EProphecyDoubleReachMode DesiredMode = Instance->bEnableReachSolver
			? Instance->ReachMode
			: EProphecyDoubleReachMode::Off;
		if (!bModeInitialized)
		{
			SourceMode = EProphecyDoubleReachMode::Off;
			TargetMode = DesiredMode;
			ModeBlendLinear = DesiredMode == EProphecyDoubleReachMode::Off
				|| TransitionDuration <= UE_SMALL_NUMBER
				? 1.0
				: 0.0;
			bModeInitialized = true;
		}
		else if (DesiredMode != TargetMode)
		{
			SourceMode = ModeBlendLinear >= 0.5 ? TargetMode : SourceMode;
			TargetMode = DesiredMode;
			ModeBlendLinear = 0.0;
		}
		else if (TransitionDuration <= UE_SMALL_NUMBER)
		{
			ModeBlendLinear = 1.0;
			SourceMode = TargetMode;
		}
		else
		{
			ModeBlendLinear = FMath::Min(1.0, ModeBlendLinear + DeltaSeconds / TransitionDuration);
			if (ModeBlendLinear >= 1.0)
			{
				SourceMode = TargetMode;
			}
		}

		if (BaseAnimation)
		{
			const double PlayLength = FMath::Max(0.0, BaseAnimation->GetPlayLength());
			AnimationTimeSeconds += DeltaSeconds * AnimationPlayRate;
			if (PlayLength > UE_DOUBLE_SMALL_NUMBER)
			{
				AnimationTimeSeconds = bLoopAnimation
					? FMath::Fmod(AnimationTimeSeconds, PlayLength)
					: FMath::Clamp(AnimationTimeSeconds, 0.0, PlayLength);
			}
		}
	}

	virtual bool Evaluate(FPoseContext& Output) override
	{
		using namespace ProphecyDoubleReach;
		Output.ResetToRefPose();
		if (BaseAnimation && BaseAnimation->GetSkeleton())
		{
			FAnimationPoseData AnimationPoseData(Output);
			BaseAnimation->GetAnimationPose(
				AnimationPoseData,
				FAnimExtractContext(AnimationTimeSeconds, false, FDeltaTimeRecord(), bLoopAnimation));
		}

		if (SourceMode == EProphecyDoubleReachMode::Off
			&& TargetMode == EProphecyDoubleReachMode::Off)
		{
			bFilteredHandTargetInitialized[LeftKey] = false;
			bFilteredHandTargetInitialized[RightKey] = false;
			bFilteredElbowInitialized[LeftKey] = false;
			bFilteredElbowInitialized[RightKey] = false;
		}
		if (SourceMode == EProphecyDoubleReachMode::Off
			&& TargetMode == EProphecyDoubleReachMode::Off
			&& (!bEnableUpperBodyMotionLimit
				|| !bFilteredBodyInitialized
				|| AreBodyParametersNearlyZero(FilteredBodyParameters)))
		{
			Output.Pose.NormalizeRotations();
			return true;
		}

		const FBoneContainer& PoseBones = Output.Pose.GetBoneContainer();
		if (!bCompactIndexCacheValid || CachedBoneContainerSerial != PoseBones.GetSerialNumber())
		{
			CompactIndices.Reset(JointCount);
			CompactIndices.AddUninitialized(JointCount);
			bCompactIndexCacheValid = true;
			CachedBoneContainerSerial = PoseBones.GetSerialNumber();
			for (int32 Index = 0; Index < JointCount; ++Index)
			{
				CompactIndices[Index] = ResolveCompactBoneIndex(PoseBones, JointNames[Index]);
				if (!CompactIndices[Index].IsValid())
				{
					bCompactIndexCacheValid = false;
				}
			}
		}
		if (!bCompactIndexCacheValid)
		{
			Output.Pose.NormalizeRotations();
			return true;
		}

		FCSPose<FCompactPose> ComponentPose;
		ComponentPose.InitPose(Output.Pose);
		FSourcePose Source;
		for (int32 Index = 0; Index < JointCount; ++Index)
		{
			Source.ComponentTransforms[Index] = ComponentPose.GetComponentSpaceTransform(CompactIndices[Index]);
			Source.Positions[Index] = Source.ComponentTransforms[Index].GetTranslation() * 0.01;
		}
		Source.Arms[LeftKey] = MakeArmSpec(Source, true);
		Source.Arms[RightKey] = MakeArmSpec(Source, false);
		Source.Legs[LeftKey] = MakeLegSpec(Source, true);
		Source.Legs[RightKey] = MakeLegSpec(Source, false);

		FVector Targets[2] =
		{
			LeftTargetComponentSpace * 0.01,
			RightTargetComponentSpace * 0.01
		};
		for (int32 Key = 0; Key < 2; ++Key)
		{
			const bool bHandActive = ModeUsesHand(SourceMode, Key) || ModeUsesHand(TargetMode, Key);
			const FVector SourceHand = At(Source.Positions, Source.Arms[Key].Hand);
			if (!bHandActive)
			{
				bFilteredHandTargetInitialized[Key] = false;
				Targets[Key] = SourceHand;
				continue;
			}

			if (!bFilteredHandTargetInitialized[Key])
			{
				FilteredHandTargets[Key] = SourceHand;
				bFilteredHandTargetInitialized[Key] = true;
			}
			if (MaxHandVelocityCmPerSecond <= UE_SMALL_NUMBER)
			{
				FilteredHandTargets[Key] = Targets[Key];
			}
			else
			{
				FilteredHandTargets[Key] = FMath::VInterpConstantTo(
					FilteredHandTargets[Key],
					Targets[Key],
					EvaluationDeltaSeconds,
					MaxHandVelocityCmPerSecond * 0.01f);
			}
			Targets[Key] = FilteredHandTargets[Key];
		}
		FJointTransforms SourceEndpoint = Source.ComponentTransforms;
		FJointTransforms TargetEndpoint = Source.ComponentTransforms;
		FSolveResult SourceSolved;
		SourceSolved.Positions = Source.Positions;
		FSolveResult TargetSolved;
		TargetSolved.Positions = Source.Positions;
		if (ModeBlendLinear < 1.0 && SourceMode != EProphecyDoubleReachMode::Off)
		{
			SourceSolved = SolveMode(Source, Targets, SourceMode);
		}
		if (TargetMode != EProphecyDoubleReachMode::Off)
		{
			TargetSolved = SolveMode(Source, Targets, TargetMode);
		}

		const double BlendAlpha = ModeBlendLinear >= 1.0 ? 1.0 : SmootherStep(ModeBlendLinear);
		if (bEnableUpperBodyMotionLimit)
		{
			const FBodyParameters DesiredParameters = BlendBodyParameters(
				SourceSolved.Parameters,
				TargetSolved.Parameters,
				BlendAlpha);
			if (!bFilteredBodyInitialized)
			{
				FilteredBodyParameters = DesiredParameters;
				bFilteredBodyInitialized = true;
			}
			else
			{
				FilteredBodyParameters = LimitBodyParameterMotion(
					FilteredBodyParameters,
					DesiredParameters,
					EvaluationDeltaSeconds,
					UpperBodySmoothingHalfLife,
					MaxPelvisTranslationSpeedCmPerSecond * 0.01,
					FMath::DegreesToRadians(MaxSpineAngularSpeedDegreesPerSecond));
			}

			const FSolveResult FilteredSource = SolveModeWithBodyParameters(
				Source,
				Targets,
				SourceMode,
				FilteredBodyParameters);
			BuildEndpointTransforms(Source, FilteredSource, SourceMode, SourceEndpoint);
			if (SourceMode == TargetMode)
			{
				TargetEndpoint = SourceEndpoint;
			}
			else
			{
				const FSolveResult FilteredTarget = SolveModeWithBodyParameters(
					Source,
					Targets,
					TargetMode,
					FilteredBodyParameters);
				BuildEndpointTransforms(Source, FilteredTarget, TargetMode, TargetEndpoint);
			}
		}
		else
		{
			if (ModeBlendLinear < 1.0 && SourceMode != EProphecyDoubleReachMode::Off)
			{
				BuildEndpointTransforms(Source, SourceSolved, SourceMode, SourceEndpoint);
			}
			if (TargetMode != EProphecyDoubleReachMode::Off)
			{
				BuildEndpointTransforms(Source, TargetSolved, TargetMode, TargetEndpoint);
			}
		}

		FJointTransforms FinalEndpoint;
		for (int32 Index = 0; Index < JointCount; ++Index)
		{
			FinalEndpoint[Index].Blend(SourceEndpoint[Index], TargetEndpoint[Index], BlendAlpha);
			FinalEndpoint[Index].NormalizeRotation();
		}
		ApplyElbowMotionLimit(Source, FinalEndpoint);

		TArray<FBoneTransform, TInlineAllocator<JointCount>> BoneTransforms;
		BoneTransforms.Reserve(JointCount - 1);
		for (int32 Index = 1; Index < JointCount; ++Index)
		{
			BoneTransforms.Emplace(CompactIndices[Index], FinalEndpoint[Index]);
		}
		BoneTransforms.Sort([](const FBoneTransform& A, const FBoneTransform& B)
		{
			return A.BoneIndex < B.BoneIndex;
		});

		ComponentPose.LocalBlendCSBoneTransforms(BoneTransforms, 1.0f);
		FCSPose<FCompactPose>::ConvertComponentPosesToLocalPosesSafe(ComponentPose, Output.Pose);
		Output.Pose.NormalizeRotations();
		return true;
	}

private:
	void ApplyElbowMotionLimit(
		const ProphecyDoubleReach::FSourcePose& Source,
		ProphecyDoubleReach::FJointTransforms& FinalEndpoint)
	{
		using namespace ProphecyDoubleReach;
		for (int32 Key = 0; Key < 2; ++Key)
		{
			const bool bHandActive = ModeUsesHand(SourceMode, Key) || ModeUsesHand(TargetMode, Key);
			if (!bHandActive)
			{
				bFilteredElbowInitialized[Key] = false;
				continue;
			}

			const FArmSpec& Arm = Source.Arms[Key];
			const int32 ShoulderIndex = JointIndex(Arm.Shoulder);
			const int32 ElbowIndex = JointIndex(Arm.Elbow);
			const int32 HandIndex = JointIndex(Arm.Hand);
			const FVector Shoulder = FinalEndpoint[ShoulderIndex].GetTranslation() * 0.01;
			const FVector NaturalElbow = FinalEndpoint[ElbowIndex].GetTranslation() * 0.01;
			const FVector Hand = FinalEndpoint[HandIndex].GetTranslation() * 0.01;
			if (!bFilteredElbowInitialized[Key])
			{
				FilteredElbows[Key] = At(Source.Positions, Arm.Elbow);
				bFilteredElbowInitialized[Key] = true;
			}

			if (MaxElbowVelocityCmPerSecond <= UE_SMALL_NUMBER)
			{
				FilteredElbows[Key] = NaturalElbow;
				continue;
			}

			const FVector RequestedElbow = FMath::VInterpConstantTo(
				FilteredElbows[Key],
				NaturalElbow,
				EvaluationDeltaSeconds,
				MaxElbowVelocityCmPerSecond * 0.01f);
			const FVector FeasibleElbow = ProjectElbowToFeasibleCircle(
				Arm,
				Shoulder,
				Hand,
				NaturalElbow,
				RequestedElbow);
			FilteredElbows[Key] = FeasibleElbow;
			FinalEndpoint[ElbowIndex].SetTranslation(FeasibleElbow * 100.0);
			FinalEndpoint[ShoulderIndex].SetRotation(AlignRotation(
				Source.ComponentTransforms[ShoulderIndex].GetRotation(),
				At(Source.Positions, Arm.Elbow) - At(Source.Positions, Arm.Shoulder),
				FeasibleElbow - Shoulder));
			FinalEndpoint[ElbowIndex].SetRotation(AlignRotation(
				Source.ComponentTransforms[ElbowIndex].GetRotation(),
				At(Source.Positions, Arm.Hand) - At(Source.Positions, Arm.Elbow),
				Hand - FeasibleElbow));
			const FQuat HandSwing = FQuat::FindBetweenNormals(
				SafeNormal(At(Source.Positions, Arm.Hand) - At(Source.Positions, Arm.Elbow)),
				SafeNormal(Hand - FeasibleElbow));
			FinalEndpoint[HandIndex].SetRotation(
				(HandSwing * Source.ComponentTransforms[HandIndex].GetRotation()).GetNormalized());
		}
	}

	UAnimSequenceBase* BaseAnimation = nullptr;
	double AnimationTimeSeconds = 0.0;
	float AnimationPlayRate = 1.0f;
	bool bLoopAnimation = true;
	FVector LeftTargetComponentSpace = FVector::ZeroVector;
	FVector RightTargetComponentSpace = FVector::ZeroVector;
	float TransitionDuration = 0.35f;
	float EvaluationDeltaSeconds = 0.0f;
	float UpperBodySmoothingHalfLife = 0.075f;
	float MaxPelvisTranslationSpeedCmPerSecond = 180.0f;
	float MaxSpineAngularSpeedDegreesPerSecond = 240.0f;
	float MaxHandVelocityCmPerSecond = 300.0f;
	float MaxElbowVelocityCmPerSecond = 360.0f;
	EProphecyDoubleReachMode SourceMode = EProphecyDoubleReachMode::Off;
	EProphecyDoubleReachMode TargetMode = EProphecyDoubleReachMode::Off;
	double ModeBlendLinear = 1.0;
	bool bModeInitialized = false;
	bool bEnableUpperBodyMotionLimit = true;
	bool bFilteredBodyInitialized = false;
	ProphecyDoubleReach::FBodyParameters FilteredBodyParameters;
	FVector FilteredHandTargets[2] = { FVector::ZeroVector, FVector::ZeroVector };
	bool bFilteredHandTargetInitialized[2] = { false, false };
	FVector FilteredElbows[2] = { FVector::ZeroVector, FVector::ZeroVector };
	bool bFilteredElbowInitialized[2] = { false, false };

	bool bCompactIndexCacheValid = false;
	uint16 CachedBoneContainerSerial = 0;
	TArray<FCompactPoseBoneIndex, TInlineAllocator<ProphecyDoubleReach::JointCount>> CompactIndices;
};

UProphecyDoubleReachAnimInstance::UProphecyDoubleReachAnimInstance() = default;

FAnimInstanceProxy* UProphecyDoubleReachAnimInstance::CreateAnimInstanceProxy()
{
	return new FProphecyDoubleReachAnimInstanceProxy(this);
}

void UProphecyDoubleReachAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy)
{
	delete InProxy;
}
