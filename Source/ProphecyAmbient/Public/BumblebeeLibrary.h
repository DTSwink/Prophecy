#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "BumblebeeSwarm.h"
#include "BumblebeeLibrary.generated.h"

class ABumblebeeZone;

/** Blueprint nodes for the ambient bumblebees (category "Bumblebees"). */
UCLASS()
class PROPHECYAMBIENT_API UBumblebeeLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Spawns a preference box; its bees are placed on surfaces inside it as soon as a camera is near.
	 *  Wing Beat Hz: wing frequency (150 = real bumblebee blur). Walk Speed: cm/s on surfaces (legs follow it).
	 *  Air Time: 0 = mostly resting, 1 = mostly flying. */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees", meta = (WorldContext = "WorldContext", AdvancedDisplay = "Rotation,bAvoidIndoors,bShowInGame",
		Keywords = "bee spawn zone box"))
	static ABumblebeeZone* SpawnBumblebeeZone(const UObject* WorldContext, FVector Location, FVector BoxExtent = FVector(500.f, 500.f, 250.f),
		int32 BeeCount = 20, float Preference = 0.85f, float SizeMultiplier = 1.f, float WingBeatHz = 150.f, float WalkSpeed = 2.5f,
		float AirTime = 0.5f, FRotator Rotation = FRotator::ZeroRotator,
		bool bAvoidIndoors = true, bool bShowInGame = false);

	/** Size of every bee: 1 = 2.5 cm model, 0.75 (default) = typical worker about 1.9 cm. */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static void SetBumblebeeSize(const UObject* WorldContext, float Scale = 0.75f);

	/** Bees take off when this actor moves close to them. */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static void AddBumblebeeThreat(const UObject* WorldContext, AActor* Actor);

	UFUNCTION(BlueprintCallable, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static void RemoveBumblebeeThreat(const UObject* WorldContext, AActor* Actor);

	/** Pause/resume the whole simulation (bees stay where they are). */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static void SetBumblebeesEnabled(const UObject* WorldContext, bool bEnabled);

	/** Show/hide every zone box while playing. */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static void ShowBumblebeeZones(const UObject* WorldContext, bool bShow);

	UFUNCTION(BlueprintPure, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static FBumblebeeStats GetBumblebeeStats(const UObject* WorldContext);
};
