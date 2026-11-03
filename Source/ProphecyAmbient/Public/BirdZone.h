#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BirdTypes.h"
#include "BirdZone.generated.h"

class UBoxComponent;
class UBillboardComponent;
class UTextRenderComponent;
class ABird;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdCryZone, ABird*, Bird, float, Duration);

/**
 * Home range of a group of birds. Place it (or use "Spawn Bird Zone"), size the box, pick the species and count.
 * Birds are spawned when a camera comes within Activation Distance (so collision is streamed in), perch on surfaces inside
 * the box, fly around and above it, walk (gulls), call, and flee from threats. Kingfishers can be recoloured
 * (Primary = brown, Secondary = white); gulls all look the same.
 */
UCLASS(Blueprintable, meta = (DisplayName = "Bird Zone"))
class PROPHECYAMBIENT_API ABirdZone : public AActor
{
	GENERATED_BODY()

public:
	ABirdZone();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Birds") TObjectPtr<UBoxComponent> Box;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true", ClampMin = "100")) FVector BoxExtent = FVector(2000.f, 2000.f, 800.f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true")) EBirdSpecies Species = EBirdSpecies::Gull;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true", ClampMin = "0", ClampMax = "64")) int32 BirdCount = 6;
	/** Kingfisher: chestnut-brown parts. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true")) FLinearColor PrimaryColour = FLinearColor(0.36f, 0.13f, 0.05f);
	/** Kingfisher: white throat / bib. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true")) FLinearColor SecondaryColour = FLinearColor(0.95f, 0.94f, 0.92f);
	/** Random per-bird shade variation of the colours (0..0.3). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true", ClampMin = "0", ClampMax = "0.3")) float ColourVariation = 0.06f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true", ClampMin = "0.3", ClampMax = "3")) float SizeMultiplier = 1.f;
	/** 0 = mostly perched, 1 = mostly flying. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true", ClampMin = "0", ClampMax = "1")) float AirTime = 0.45f;
	/** Birds call on their own every now and then (fires each bird's OnBirdCry and this zone's OnZoneBirdCry). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true")) bool bAmbientCries = true;
	/** Birds keep landing spots inside the box with this probability (otherwise anywhere in a 1.5x box). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ClampMin = "0", ClampMax = "1")) float Preference = 0.9f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ClampMin = "0")) float ActivationDistance = 12000.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds", meta = (ExposeOnSpawn = "true")) bool bShowInGame = false;
	/** Use these instead of the species defaults (tick bOverrideSettings). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Advanced") bool bOverrideSettings = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Advanced", meta = (EditCondition = "bOverrideSettings")) FBirdSpeciesSettings Settings;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Advanced") int32 Seed = 0;

	UPROPERTY(BlueprintAssignable, Category = "Birds") FOnBirdCryZone OnZoneBirdCry;

	UFUNCTION(BlueprintPure, Category = "Birds") TArray<ABird*> GetBirds() const;
	/** Recolour every bird of the zone (kingfisher brown / white). */
	UFUNCTION(BlueprintCallable, Category = "Birds") void SetColours(FLinearColor Primary, FLinearColor Secondary);
	UFUNCTION(BlueprintCallable, Category = "Birds") void SetShowInGame(bool bShow);
	/** Make a random (or the nearest to Near if non-zero) live bird of this zone call. */
	UFUNCTION(BlueprintCallable, Category = "Birds") ABird* MakeBirdCry(FVector Near, float Duration = 0.9f);

	FBirdSpeciesSettings EffectiveSettings() const;
	bool IsInside(const FVector& P, float Margin = 0.f) const;
	FVector RandomPoint(FRandomStream& Rng, float Grow = 1.f) const;
	FBox WorldBounds(float Grow = 1.f) const;
	FVector GetCenter() const;
	void HandleBirdCry(ABird* Bird, float Duration);

protected:
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY() TArray<TObjectPtr<ABird>> SpawnedBirds;
	UPROPERTY() TObjectPtr<UTextRenderComponent> Label;
#if WITH_EDITORONLY_DATA
	UPROPERTY() TObjectPtr<UBillboardComponent> Icon;
#endif
	bool bSpawned = false;
	float Check = 0.f;
	int32 PendingSpawn = 0;
	FRandomStream Rng;
	void TrySpawn();
	void UpdateLabel();
};
