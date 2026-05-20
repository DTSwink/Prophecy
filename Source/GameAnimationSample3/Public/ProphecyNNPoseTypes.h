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
	uint32 Revision = 0;
	double SourceTimeSeconds = 0.0;

	bool IsValid() const
	{
		return Revision != 0 && BoneNames.Num() == LocalTransforms.Num();
	}

	void Reset()
	{
		BoneNames.Reset();
		LocalTransforms.Reset();
		Revision = 0;
		SourceTimeSeconds = 0.0;
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

	static void SetAgentLocalPose(
		int32 AgentId,
		TConstArrayView<FProphecyNNBonePose> BonePoses,
		double SourceTimeSeconds = 0.0);

	static bool GetAgentLocalPose(int32 AgentId, FProphecyNNPoseSnapshot& OutSnapshot);
	static void ClearAgentPose(int32 AgentId);
	static void ClearAllPoses();
	static int32 NumPoses();
};
