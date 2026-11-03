#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BirdFish.generated.h"

class UStaticMeshComponent;
class UStaticMesh;
class ABird;

UENUM(BlueprintType)
enum class EBirdFishState : uint8
{
	/** In a bird's bill (struggling while Struggle > 0). */
	Held,
	/** On the ground, being eaten. */
	Dropped,
	/** What is left: scavengers (gulls) come for it. */
	Remains,
	/** Being swallowed (destroyed when done). */
	Swallowed
};

/**
 * A fish caught by a bird (placeholder mesh until the real fish: any static mesh, scaled to the catch length; its longest
 * axis is the fish's length and its thinnest axis the side it lies on). Spawned and driven by the birds; destroyed when a
 * gull swallows it. Tagged "BirdFood".
 */
UCLASS(NotPlaceable, meta = (DisplayName = "Bird Fish"))
class PROPHECYAMBIENT_API ABirdFish : public AActor
{
	GENERATED_BODY()

public:
	ABirdFish();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Fish") TObjectPtr<USceneComponent> Root;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Fish") TObjectPtr<UStaticMeshComponent> Mesh;
	UPROPERTY(BlueprintReadOnly, Category = "Fish") EBirdFishState FishState = EBirdFishState::Held;
	/** 1 = fresh catch thrashing hard, 0 = still. */
	UPROPERTY(BlueprintReadOnly, Category = "Fish") float Struggle = 1.f;
	/** 1 = whole, lower = eaten (the visible size follows it). */
	UPROPERTY(BlueprintReadOnly, Category = "Fish") float Meat = 1.f;

	/** Mesh + length (cm) + seconds of struggling. */
	void Init(UStaticMesh* InMesh, float LengthCm, float StruggleSeconds, int32 Seed);
	/** Advances the struggle; returns the current swing of the fish (deg, about its height axis) and roll (deg). */
	FVector2D UpdateStruggle(float Dt);
	bool IsStill() const { return Struggle <= 0.f; }
	/** Actor rotation that puts the fish's length along Long and its flat side facing Side. */
	static FQuat Orientation(const FVector& Long, const FVector& Side);
	void SetMeat(float InMeat);
	/** A quick jerk (beak strike / grab). */
	void Nudge(float Amount) { NudgeAmp = FMath::Max(NudgeAmp, Amount); }
	float GetHalfThickness() const { return HalfThick; }
	float GetLength() const { return Length; }

	TWeakObjectPtr<ABird> Holder;
	TWeakObjectPtr<ABird> Claimant;

private:
	float Length = 8.f, HalfThick = 0.6f, StruggleTime = 45.f, Age = 0.f;
	float BurstLeft = 0.f, PauseLeft = 0.5f, BurstHz = 4.f, BurstAmp = 30.f, Phase = 0.f, NudgeAmp = 0.f;
	FVector MeshOffset = FVector::ZeroVector;
	float MeshScale = 1.f;
	FRandomStream Rng;
};
