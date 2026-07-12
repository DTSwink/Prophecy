#pragma once

#include "Animation/AnimInstance.h"
#include "ProphecyDoubleReachTypes.h"
#include "ProphecyDoubleReachAnimInstance.generated.h"

class UAnimSequenceBase;

UCLASS(Transient, Blueprintable, BlueprintType)
class GAMEANIMATIONSAMPLE3_API UProphecyDoubleReachAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	UProphecyDoubleReachAnimInstance();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Animation")
	TObjectPtr<UAnimSequenceBase> BaseAnimation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Animation")
	float AnimationPlayRate = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Animation")
	bool bLoopAnimation = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach")
	EProphecyDoubleReachMode ReachMode = EProphecyDoubleReachMode::Off;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach")
	FVector LeftTargetComponentSpace = FVector(70.0, 45.0, 110.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach")
	FVector RightTargetComponentSpace = FVector(-70.0, 45.0, 110.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach", meta = (ClampMin = "0.0", Units = "s"))
	float TransitionDuration = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Upper Body Motion Limit")
	bool bEnableUpperBodyMotionLimit = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Upper Body Motion Limit", meta = (ClampMin = "0.0", Units = "s"))
	float UpperBodySmoothingHalfLife = 0.075f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Upper Body Motion Limit", meta = (ClampMin = "1.0", Units = "cm/s"))
	float MaxPelvisTranslationSpeedCmPerSecond = 180.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Upper Body Motion Limit", meta = (ClampMin = "1.0", Units = "deg/s"))
	float MaxSpineAngularSpeedDegreesPerSecond = 240.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Hand Motion Limit", meta = (ClampMin = "0.0", Units = "cm/s"))
	float MaxHandVelocityCmPerSecond = 300.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Hand Motion Limit", meta = (ClampMin = "0.0", Units = "cm/s"))
	float MaxElbowVelocityCmPerSecond = 360.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach")
	bool bEnableReachSolver = true;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
};
