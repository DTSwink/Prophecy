#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BirdTypes.h"
#include "BirdFlock.h"
#include "BirdLibrary.generated.h"

class ABirdZone;
class ABird;

/** Blueprint nodes for the ambient birds (category "Birds"). */
UCLASS()
class PROPHECYAMBIENT_API UBirdLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Spawns a bird home range. Primary / Secondary colours recolour kingfishers (brown / white); gulls all look the same.
	 *  Air Time: 0 = mostly perched, 1 = mostly flying. Ambient Cries: birds call on their own (bind OnBirdCry / OnZoneBirdCry for SFX). */
	UFUNCTION(BlueprintCallable, Category = "Birds", meta = (WorldContext = "WorldContext", AdvancedDisplay = "Rotation,bShowInGame,Seed",
		Keywords = "bird gull seagull kingfisher spawn zone"))
	static ABirdZone* SpawnBirdZone(const UObject* WorldContext, FVector Location, FVector BoxExtent = FVector(2000.f, 2000.f, 800.f),
		EBirdSpecies Species = EBirdSpecies::Gull, int32 BirdCount = 6,
		FLinearColor PrimaryColour = FLinearColor(0.36f, 0.13f, 0.05f, 1.f), FLinearColor SecondaryColour = FLinearColor(0.95f, 0.94f, 0.92f, 1.f),
		float SizeMultiplier = 1.f, float AirTime = 0.45f, bool bAmbientCries = true, FRotator Rotation = FRotator::ZeroRotator,
		bool bShowInGame = false, int32 Seed = 0);

	/** Opens the bird's beak for Duration seconds and fires its OnBirdCry event (play your SFX there). */
	UFUNCTION(BlueprintCallable, Category = "Birds", meta = (Keywords = "bird call scream sound beak"))
	static void BirdCry(ABird* Bird, float Duration = 0.9f, float Openness = 1.f);

	/** Kills a bird (ragdoll + feather burst). Impulse is a velocity change in cm/s. */
	UFUNCTION(BlueprintCallable, Category = "Birds")
	static void KillBird(ABird* Bird, FVector HitLocation, FVector Impulse);

	/** Birds take off / flee when this actor moves close to them. */
	UFUNCTION(BlueprintCallable, Category = "Birds", meta = (WorldContext = "WorldContext"))
	static void AddBirdThreat(const UObject* WorldContext, AActor* Actor);

	/** Objects of this class kill birds they pass through at speed (the spear Blueprint is registered by default). */
	UFUNCTION(BlueprintCallable, Category = "Birds", meta = (WorldContext = "WorldContext"))
	static void AddBirdLethalClass(const UObject* WorldContext, TSubclassOf<AActor> Class);

	/** Decides which hits bleed. Bind a function (Create Event) taking a Bird Hit Info and returning true to bleed: it gets the
	 *  object, its speed, momentum, alignment (tip-first angle), incidence, bone, lethal flags... Leave unbound for the default
	 *  rule (kills and lethal objects bleed). Console: birds.Blood 0 = never, 2 = always. */
	UFUNCTION(BlueprintCallable, Category = "Birds|Blood", meta = (WorldContext = "WorldContext", Keywords = "bird blood bleed stain condition"))
	static void SetBirdBleedCondition(const UObject* WorldContext, FBirdBleedCondition Condition);

	UFUNCTION(BlueprintCallable, Category = "Birds|Blood", meta = (WorldContext = "WorldContext"))
	static void ClearBirdBleedCondition(const UObject* WorldContext);

	/** Puts a blood stain on the bird's plumage at a world point (and optionally the blood splat). RadiusCm <= 0 = species default. */
	UFUNCTION(BlueprintCallable, Category = "Birds|Blood", meta = (Keywords = "bird blood bleed stain"))
	static void AddBirdBloodStain(ABird* Bird, FVector WorldLocation, FVector Direction, float RadiusCm = 0.f, bool bSplat = true);

	/** Marks an actor as water for the birds (kingfishers fish there, nobody lands on it). Usually not needed: actors tagged
	 *  BirdWater and flat meshes named water / ocean / sea / lake are found automatically. */
	UFUNCTION(BlueprintCallable, Category = "Birds|Feeding", meta = (WorldContext = "WorldContext", Keywords = "bird water sea fishing"))
	static void AddBirdWater(const UObject* WorldContext, AActor* WaterActor);

	/** Sends a kingfisher fishing now (it needs water within its Fishing Range). */
	UFUNCTION(BlueprintCallable, Category = "Birds|Feeding", meta = (Keywords = "bird kingfisher fish dive"))
	static bool SendBirdFishing(ABird* Bird);

	UFUNCTION(BlueprintPure, Category = "Birds", meta = (WorldContext = "WorldContext"))
	static TArray<ABird*> GetAllBirds(const UObject* WorldContext);

	UFUNCTION(BlueprintCallable, Category = "Birds", meta = (WorldContext = "WorldContext"))
	static void SetBirdsEnabled(const UObject* WorldContext, bool bEnabled);

	UFUNCTION(BlueprintPure, Category = "Birds", meta = (WorldContext = "WorldContext"))
	static FBirdFlockStats GetBirdStats(const UObject* WorldContext);
};
