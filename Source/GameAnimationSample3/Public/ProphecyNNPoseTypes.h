#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "ProphecyNNPoseTypes.generated.h"

UENUM(BlueprintType)
enum class EProphecyNNInterpolationMode : uint8
{
    Current = 0 UMETA(DisplayName="Current (Linear / Viewer Rotation)"),
    HermiteSlerp = 1 UMETA(DisplayName="Hermite Positions / SLERP Rotations")
};

USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyNNBonePose
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose")
	FName BoneName;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose")
	FTransform LocalTransform;

	FProphecyNNBonePose()
		: BoneName(NAME_None)
		, LocalTransform(FTransform::Identity)
	{
	}

	FProphecyNNBonePose(FName InBoneName, const FTransform& InLocalTransform)
		: BoneName(InBoneName)
		, LocalTransform(InLocalTransform)
	{
	}
};

struct FProphecyNNAttackHandClamp
{
	bool bEnabled = true;
	float LeewayCm = 0;
	FVector ReferenceOffsets[2] = {FVector::ZeroVector, FVector::ZeroVector};

	static FVector ClampPosition(const FVector& Position, const FVector& Attachment, float Leeway)
	{
		if (Leeway <= 0) return Attachment;
		const FVector Delta = Position - Attachment;
		return Delta.SizeSquared() <= FMath::Square(double(Leeway))
			? Position : Attachment + Delta.GetSafeNormal() * Leeway;
	}
};

struct FProphecyNNForearmClamp
{
	bool bEnabled = false;
	float LeewayCm = 0;
	FVector2D LengthsCm = FVector2D::ZeroVector;
	static double ClampLength(double Distance, double Length, double Leeway)
	{
		return FMath::Clamp(Distance, FMath::Max(0., Length-Leeway), Length+Leeway);
	}
	FVector ClampHand(const FVector& Hand, const FTransform& Forearm, const FVector& LocalDirection, int32 Side) const
	{
		const FVector Nominal = Forearm.TransformVector(LocalDirection.GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector) * LengthsCm[Side]);
		const FVector Delta = Hand - Forearm.GetTranslation();
		const double Distance = Delta.Length();
		const double Allowed = ClampLength(Distance, Nominal.Length(), LeewayCm);
		if (Distance == Allowed) return Hand;
		return Forearm.GetTranslation() + Delta.GetSafeNormal(UE_SMALL_NUMBER, Nominal.GetSafeNormal()) * Allowed;
	}
};

struct GAMEANIMATIONSAMPLE3_API FProphecyNNPoseSnapshot
{
	EProphecyNNInterpolationMode InterpolationMode = EProphecyNNInterpolationMode::Current;
	TArray<FVector> InterpolationStartTangents, InterpolationEndTangents;
	double InterpolationIntervalSeconds = 0;
	TArray<FName> BoneNames;
	TArray<FTransform> LocalTransforms;
	TArray<FTransform> PreviousComponentTransforms;
	TArray<FTransform> ComponentTransforms;
	FTransform PreviousComponentWorldTransform = FTransform::Identity;
	FTransform ComponentWorldTransform = FTransform::Identity;
	uint32 BoneLayoutHash = 0;
	uint32 Revision = 0;
	double SourceTimeSeconds = 0.0;
	bool bHasComponentWorldTransform = false;
	float CalfClampLeewayCm = 0;
	FProphecyNNAttackHandClamp AttackHandClamp;
	FProphecyNNForearmClamp ForearmClamp;
	FVector2D CalfClampLengths = FVector2D::ZeroVector;

	bool IsValid() const
	{
		return Revision != 0 && BoneNames.Num() == LocalTransforms.Num();
	}

	void Reset()
	{
		InterpolationMode = EProphecyNNInterpolationMode::Current;
		InterpolationStartTangents.Empty(); InterpolationEndTangents.Empty();
		InterpolationIntervalSeconds = 0;
		BoneNames.Reset();
		LocalTransforms.Reset();
		PreviousComponentTransforms.Reset();
		ComponentTransforms.Reset();
		PreviousComponentWorldTransform = FTransform::Identity;
		ComponentWorldTransform = FTransform::Identity;
		BoneLayoutHash = 0;
		Revision = 0;
		SourceTimeSeconds = 0.0;
		bHasComponentWorldTransform = false;
		CalfClampLeewayCm = 0;
		AttackHandClamp = FProphecyNNAttackHandClamp();
		ForearmClamp = FProphecyNNForearmClamp();
		CalfClampLengths = FVector2D::ZeroVector;
	}
};

class GAMEANIMATIONSAMPLE3_API FProphecyNNPoseStore
{
public:
	/** Requested mode is applied atomically with the next pose publication. */
	static void SetInterpolationMode(int32 AgentId, EProphecyNNInterpolationMode Mode);
	/** Translate both world carriers without rebuilding local poses or changing interpolation tangents. */
	static void TranslateAgentWorldPose(int32 AgentId, const FVector& WorldDelta);
	static void SetAgentLocalPose(
		int32 AgentId,
		TConstArrayView<FName> BoneNames,
		TConstArrayView<FTransform> LocalTransforms,
		double SourceTimeSeconds = 0.0);

	/** Publishes a pose together with the exact component-to-world transform of that policy frame. */
	static void SetAgentLocalPose(
		int32 AgentId,
		TConstArrayView<FName> BoneNames,
		TConstArrayView<FTransform> LocalTransforms,
		const FTransform& ComponentWorldTransform,
		double SourceTimeSeconds);

	/** Publishes the consecutive 30 Hz component-space poses used by the model viewer. */
	static void SetAgentLocalPose(
		int32 AgentId,
		TConstArrayView<FName> BoneNames,
		TConstArrayView<FTransform> LocalTransforms,
		TConstArrayView<FTransform> PreviousComponentTransforms,
		TConstArrayView<FTransform> ComponentTransforms,
		const FTransform& PreviousComponentWorldTransform,
		const FTransform& ComponentWorldTransform,
		double SourceTimeSeconds,
		bool bRigidForearms = false, bool bRigidCalves = false,
		float CalfClampLeewayCm = 0, FVector2D CalfClampLengths = FVector2D::ZeroVector,
		const FProphecyNNAttackHandClamp& HandClamp = FProphecyNNAttackHandClamp(),
		const FProphecyNNForearmClamp& ForearmClamp = FProphecyNNForearmClamp());

	/** Preserve exact calf attachment, or the published attack length band; toes follow any correction. */
	static void ApplyRigidCalves(int32 AgentId, const FProphecyNNPoseSnapshot& Snapshot,
		TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms);

	/** Attack presentation: keep fixed hand-parent offsets after world interpolation. */
	static void ApplyRigidForearms(int32 AgentId, const FProphecyNNPoseSnapshot& Snapshot,
		TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms);
	/** True for the attack publication, including its unchanged handoff frame. */
	static bool UsesAttackPresentation(int32 AgentId);

	static void SetAgentLocalPose(
		int32 AgentId,
		TConstArrayView<FProphecyNNBonePose> BonePoses,
		double SourceTimeSeconds = 0.0);

	static bool GetAgentLocalPose(int32 AgentId, FProphecyNNPoseSnapshot& OutSnapshot);
	static bool GetAgentLocalPoseIfNewer(int32 AgentId, uint32 KnownRevision, FProphecyNNPoseSnapshot& OutSnapshot);
	static void ClearAgentPose(int32 AgentId);
	static void ClearAllPoses();
	static int32 NumPoses();
};
