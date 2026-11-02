#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BumblebeeZone.generated.h"

class UBoxComponent;

/**
 * Preference box for bumblebees. Drop it over flower beds / gardens, scale the box, set BeeCount.
 * Its bees are placed lazily (when the area is near enough for its collision to be loaded) and then persist.
 * They wander freely but pick landing spots inside their box with probability Preference.
 * The first zone to begin play creates the ABumblebeeSwarm manager if the level has none.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Bumblebee Zone"))
class PROPHECYAMBIENT_API ABumblebeeZone : public AActor
{
	GENERATED_BODY()

public:
	ABumblebeeZone();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bumblebees")
	TObjectPtr<UBoxComponent> Box;

	/** Bees that live in this zone. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ClampMin = "0", ClampMax = "2000"))
	int32 BeeCount = 20;

	/** 0 = bees roam anywhere, 1 = every landing spot is chosen inside the box. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ClampMin = "0", ClampMax = "1"))
	float Preference = 0.85f;

	/** Bees of this zone avoid landing in enclosed spaces (under a roof with walls around). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees")
	bool bAvoidIndoors = true;

	/** World-space test, honours actor rotation/scale. Margin in cm grows the box. */
	bool IsInside(const FVector& P, float Margin = 0.f) const;
	FVector RandomPoint(FRandomStream& Rng, float TopBias = 0.f) const;
	FVector GetCenter() const;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
};
