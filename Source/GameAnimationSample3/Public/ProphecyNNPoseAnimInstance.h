#pragma once

#include "Animation/AnimInstance.h"
#include "ProphecyNNPoseAnimInstance.generated.h"

UCLASS(Transient, Blueprintable, BlueprintType)
class GAMEANIMATIONSAMPLE3_API UProphecyNNPoseAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	UProphecyNNPoseAnimInstance();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose")
	int32 AgentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose")
	bool bUseStoredPose;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose|Debug")
	bool bEnableDebugMotion;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose|Debug")
	FName DebugBoneName;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose|Debug", meta = (ClampMin = "0.0"))
	float DebugMotionDegrees;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Pose|Debug", meta = (ClampMin = "0.0"))
	float DebugMotionHz;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
};
