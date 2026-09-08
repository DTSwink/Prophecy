#pragma once

#include "Animation/AnimInstance.h"
#include "ProphecyNNLocomotionAnimInstance.generated.h"

class UAnimSequenceBase;

UENUM(BlueprintType)
enum class EProphecyAnimationOverlayMode : uint8
{
	UpperBodyOnly UMETA(DisplayName = "Upper Body Only (NN Legs)"),
	FullBody UMETA(DisplayName = "Full Body")
};

UCLASS(Transient, Blueprintable, BlueprintType)
class GAMEANIMATIONSAMPLE3_API UProphecyNNLocomotionAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	UProphecyNNLocomotionAnimInstance();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	int32 AgentId = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	bool bInterpolateNNPose = true;

	// Match Stepper Model Viewer: blend every authored lower-body joint in
	// absolute world space between consecutive 30 Hz policy poses.
	UPROPERTY(Transient, BlueprintReadWrite, Category = "Prophecy|NN Locomotion")
	bool bUseViewerGlobalPoseInterpolation = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion", meta = (ClampMin = "0.001"))
	float NNPoseIntervalSeconds = 1.0f / 30.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	TObjectPtr<UAnimSequenceBase> OverlayAnimation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	bool bOverlayEnabled = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay", meta = (ClampMin = "0.0"))
	float OverlayBlendSeconds = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	float OverlayPlayRate = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	bool bLoopOverlay = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|NN Locomotion|Overlay")
	EProphecyAnimationOverlayMode OverlayMode = EProphecyAnimationOverlayMode::UpperBodyOnly;

	/** Restarts the current overlay from time zero without replacing the asset. */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|NN Locomotion|Overlay")
	void RestartOverlayPlayback() { ++OverlayPlaybackRevision; }

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Prophecy|NN Locomotion|Overlay")
	int32 OverlayPlaybackRevision = 0;

protected:
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
	virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;
};
