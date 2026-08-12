#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
#include "ProphecyNNPoseTypes.generated.h"

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

struct GAMEANIMATIONSAMPLE3_API FProphecyNNPoseSnapshot
{
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

	bool IsValid() const
	{
		return Revision != 0 && BoneNames.Num() == LocalTransforms.Num();
	}

	void Reset()
	{
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
	}
};

class GAMEANIMATIONSAMPLE3_API FProphecyNNPoseStore
{
public:
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
		double SourceTimeSeconds);

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
