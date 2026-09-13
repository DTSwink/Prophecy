#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootPinningTypes.generated.h"

/** Last completed policy step. All pairs use X = left foot, Y = right foot. */
USTRUCT(BlueprintType)
struct FProphecyFootPinningSample
{
	GENERATED_BODY()
	/** Unmodified neural outputs (logits), not percentages. */
	UPROPERTY(BlueprintReadOnly, Category="Pinning")
	FVector2D RawNetworkOutput = FVector2D::ZeroVector;
	/** Decoded weights before near-ground forcing. Range 0..1. */
	UPROPERTY(BlueprintReadOnly, Category="Pinning")
	FVector2D RawPinning = FVector2D::ZeroVector;
	/** Weights actually supplied to this stage's foot projection. Range 0..1. */
	UPROPERTY(BlueprintReadOnly, Category="Pinning")
	FVector2D EffectivePinning = FVector2D::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="Pinning")
	double SampleTimeSeconds = -1;
	/** False for background locomotion during full attacks, or attack ghost legs in half attacks. */
	UPROPERTY(BlueprintReadOnly, Category="Pinning")
	bool bAppliesToVisibleFeet = false;
	UPROPERTY(BlueprintReadOnly, Category="Pinning")
	bool bWalkPolicy = false;
};
