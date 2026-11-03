#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BumblebeeZone.generated.h"

class UBoxComponent;
class UBillboardComponent;
class UTextRenderComponent;

/**
 * Preference box for bumblebees. Place it (or use the "Spawn Bumblebee Zone" node), size it with Box Extent or the scale
 * gizmo, set Bee Count. Its bees are placed lazily on surfaces inside the box (when a camera comes near, so collision is
 * loaded there) and then persist. They wander freely but pick landing spots inside the box with probability Preference.
 * The first zone to begin play creates the Bumblebee Swarm manager if the level has none.
 *
 * Visualiser: yellow box + bee icon + label in the editor; tick "Show In Game" to also see it while playing.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Bumblebee Zone"))
class PROPHECYAMBIENT_API ABumblebeeZone : public AActor
{
	GENERATED_BODY()

public:
	ABumblebeeZone();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bumblebees")
	TObjectPtr<UBoxComponent> Box;

	/** Half size of the box in cm (before actor scale). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "10"))
	FVector BoxExtent = FVector(500.f, 500.f, 250.f);

	/** Bees that live in this zone (read when the zone begins play). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "0", ClampMax = "2000"))
	int32 BeeCount = 20;

	/** 0 = bees roam anywhere, 1 = every landing spot is chosen inside the box. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "0", ClampMax = "1"))
	float Preference = 0.85f;

	/** Multiplies the swarm's Bee Scale for the bees of this zone. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "0.1", ClampMax = "5"))
	float BeeSizeMultiplier = 1.f;

	/** Wing beat frequency (Hz). Real bumblebees beat about 130-200 times a second (B. terrestris ~150 Hz), which reads as a
	 *  blur at any frame rate; lower values (20-40) give a visible, stylised flap. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "1", ClampMax = "400", UIMin = "10", UIMax = "250"))
	float WingBeatHz = 150.f;

	/** Average walking speed on surfaces (cm/s). Legs step in sync with it (stride grows with speed, feet stay planted). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "0.1", ClampMax = "30", UIMin = "0.5", UIMax = "10"))
	float WalkSpeed = 2.5f;

	/** How much the bees fly: 0 = short hops between long rests, 1 = mostly in the air with brief stops. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true", ClampMin = "0", ClampMax = "1"))
	float AirTime = 0.5f;

	/** Bees of this zone avoid landing in enclosed spaces (under a roof with walls around). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true"))
	bool bAvoidIndoors = true;

	/** Draw the box and label while playing (debug / tuning). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees", meta = (ExposeOnSpawn = "true"))
	bool bShowInGame = false;

	UFUNCTION(BlueprintCallable, Category = "Bumblebees")
	void SetShowInGame(bool bShow);

	/** World-space test, honours actor rotation/scale. Margin in cm grows the box. */
	bool IsInside(const FVector& P, float Margin = 0.f) const;
	FVector RandomPoint(FRandomStream& Rng, float TopBias = 0.f) const;
	FVector GetCenter() const;

protected:
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& Event) override;
#endif

private:
	UPROPERTY(VisibleAnywhere, Category = "Bumblebees")
	TObjectPtr<UTextRenderComponent> Label;
#if WITH_EDITORONLY_DATA
	UPROPERTY()
	TObjectPtr<UBillboardComponent> Sprite;
#endif
	void RefreshVisuals();
};
