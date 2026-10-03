#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "ProphecyNNPoseTypes.generated.h"

UENUM(BlueprintType)
enum class EProphecyNNInterpolationMode : uint8
{
    Current = 0 UMETA(DisplayName="Current (Linear / Viewer Rotation)"),
    HermiteSlerp = 1 UMETA(DisplayName="Hermite Positions / SLERP Rotations"),
    AttackViewer = 2 UMETA(DisplayName="Attack Viewer")
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

// Anatomical wrist offsets, shared by every policy and interpolated presentation.
struct FProphecyNNFixedArms
{
	FVector ForearmOffsets[2] = {FVector::ZeroVector, FVector::ZeroVector};
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
	FProphecyNNFixedArms FixedArms;
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
		FixedArms = FProphecyNNFixedArms();
		CalfClampLengths = FVector2D::ZeroVector;
	}
};

class GAMEANIMATIONSAMPLE3_API FProphecyNNPoseStore
{
public:
    static void SetForearmReturnLengths(int32 AgentId,FVector2D Lengths);
    // Replace only the eight cached leg transforms; preserve source time and upper pose.
    static void UpdateTickPinningLegs(int32 AgentId,TConstArrayView<int32> Indices,
        TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current);

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
		bool bSpecialPresentation = false, bool bRigidCalves = false,
		float CalfClampLeewayCm = 0, FVector2D CalfClampLengths = FVector2D::ZeroVector,
		const FProphecyNNFixedArms& FixedArms = FProphecyNNFixedArms(),bool bHalfAttack = false,bool bFixedArms = true);

	/** Preserve exact calf attachment, or the published attack length band; toes follow any correction. */
	static void ApplyRigidCalves(int32 AgentId, const FProphecyNNPoseSnapshot& Snapshot,
		TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms, float InterpolationAlpha = 1.f);

	/** Every mode: keep anatomical hand-parent offsets after world interpolation. */
	static void ApplyRigidForearms(int32 AgentId, const FProphecyNNPoseSnapshot& Snapshot,
		TConstArrayView<FName> BoneNames, TArrayView<FTransform> Transforms);
	/** True for the attack publication, including its unchanged handoff frame. */
	static bool UsesAttackPresentation(int32 AgentId);
	static bool UsesLowerSpecialPresentation(int32 AgentId);

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
