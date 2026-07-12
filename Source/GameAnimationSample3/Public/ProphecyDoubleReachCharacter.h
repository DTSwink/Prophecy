#pragma once

#include "GameFramework/Character.h"
#include "ProphecyDoubleReachTypes.h"
#include "ProphecyDoubleReachCharacter.generated.h"

class UAnimSequenceBase;
class UStaticMeshComponent;

UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyDoubleReachCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AProphecyDoubleReachCharacter();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach")
	EProphecyDoubleReachMode ReachMode = EProphecyDoubleReachMode::Off;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Animation")
	TObjectPtr<UAnimSequenceBase> BaseAnimation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Animation")
	float AnimationPlayRate = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Animation")
	bool bLoopAnimation = true;

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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Double Reach|Debug")
	bool bShowTargetMarkers = true;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Double Reach|Targets")
	TObjectPtr<UStaticMeshComponent> LeftReachTarget;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Double Reach|Targets")
	TObjectPtr<UStaticMeshComponent> RightReachTarget;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Double Reach")
	void SetReachMode(EProphecyDoubleReachMode NewMode);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Double Reach")
	void SetReachTargetsWorld(FVector LeftWorldLocation, FVector RightWorldLocation);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Double Reach")
	void SetLeftReachTargetWorld(FVector WorldLocation);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Double Reach")
	void SetRightReachTargetWorld(FVector WorldLocation);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Double Reach|Animation")
	void SetBaseAnimation(UAnimSequenceBase* NewAnimation);

protected:
	virtual void BeginPlay() override;

private:
	void SyncAnimInstance();
	void UpdateTargetMarkerVisibility();
};
