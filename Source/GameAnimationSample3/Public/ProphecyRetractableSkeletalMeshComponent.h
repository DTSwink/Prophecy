#pragma once

#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "ProphecyRetractableSkeletalMeshComponent.generated.h"

/**
 * Single-component renderer and PHAT rig for the Potence rope.
 *
 * Chaos keeps ownership of the rigid bodies and constraints. Immediately before
 * Unreal publishes the finalized bone pose for rendering, this component shortens
 * the reeled bones only along their authored local Z axis. X/Y stay unchanged, so
 * the rope keeps its full diameter and the Physics Asset is never resized.
 */
UCLASS(ClassGroup = (Prophecy), meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyRetractableSkeletalMeshComponent final : public USkeletalMeshComponent
{
	GENERATED_BODY()

public:
	void SetRetractionVisualAmount(float InAmount);

	virtual void FinalizeBoneTransform() override;

private:
	void ApplyRetractionVisualPose();

	float RetractionVisualAmount = 0.0f;
	bool bRetractionVisualActive = false;
};
