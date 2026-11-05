#pragma once

#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyNoose.generated.h"

class USkeletalMeshComponent;
class UStaticMeshComponent;
class UPrimitiveComponent;

/**
 * Procedural hangman's noose carried by the gallows rope end: a wrapped coil, a frayed tail and a loop.
 * Low poly, same material and texel density as the rope. The loop is rebuilt instantly at any size:
 * hanging free it falls in the coil's plane; tied, it closes around the limb at the limb's collision
 * radius plus a small clearance. Visual only: the rope's own bodies and the tie joint carry the physics.
 * Space: origin at the rope end bone, +Z up the rope (towards the pulley), the coil hangs below.
 */
UCLASS(ClassGroup = (Prophecy), meta = (BlueprintSpawnableComponent))
class GAMEANIMATIONSAMPLE3_API UProphecyNooseComponent : public UProceduralMeshComponent
{
	GENERATED_BODY()
public:
	UProphecyNooseComponent(const FObjectInitializer& ObjectInitializer);

	/** Radius of the rope the noose is tied from: a hangman's noose uses ~2.5 cm (one inch) rope, much thinner than
	 * the gallows line; the entry tapers from the gallows rope (HangingRopeRadius) to this. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "0.3", Units = "cm"))
	float RopeRadius = 1.25f;
	/** Radius of the hanging rope the noose continues (set from the gallows rope when installed). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "0.3", Units = "cm"))
	float HangingRopeRadius = 2.83f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "2", ClampMax = "13"))
	int32 CoilTurns = 7;
	/** Inner radius of the loop while nothing is tied. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "2", Units = "cm"))
	float LooseLoopRadius = 13.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "0", Units = "cm"))
	float TailLength = 4.f;
	/** Tied, the noose stays one rigid piece (coil and loop in one plane), the loop square across the limb so the limb
	 * sits centred in it. Optional tilt of that plane towards the rope's pull (0 = square). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "0", ClampMax = "60", Units = "deg"))
	float KnotTiltMaxDegrees = 0.f;
	/** Seconds over which a tie draws the rope end onto the knot (the noose itself is placed at once). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "0", Units = "s"))
	float TieCloseSeconds = .35f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "5", ClampMax = "16"))
	int32 Sides = 8;
	/** Rope texture density: UV across one full turn of the section, and UV per cm along the rope. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose")
	float UVAroundPerTurn = 0.07f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose")
	float UVAlongPerCm = 0.00259f;
	/** Mass the noose adds to the rope end body. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Noose", meta = (ClampMin = "0", Units = "kg"))
	float MassKg = 3.f;

	UFUNCTION(BlueprintCallable, Category = "Noose")
	void BuildLoose();
	/** Loop around a limb. Axis = limb axis and KnotSide = unit direction from the loop centre to the knot
	 * (perpendicular to Axis), both in this component's space. The loop centre follows from the knot.
	 * InnerRadius places the knot. InnerProfile (optional, evenly spaced angles from KnotSide towards
	 * Axis x KnotSide) is the loop's inner radius all around, so it hugs the skin instead of being a circle. */
	void BuildAround(const FVector& Axis, const FVector& KnotSide, float InnerRadius, const TArray<float>& InnerProfile = TArray<float>());

	float GetCoilLength() const { return CoilTurns * 2.05f * RopeRadius; }
	float GetKnotTop() const { return 0.6f * RopeRadius; }
	/** Distance from the loop's rope centreline to the knot axis (the coil's half width). */
	float GetKnotStandoff() const { return 3.f * RopeRadius; }
	/** Collision box of the coil (welded to the rope end): centre and half extents in this component's space. */
	void GetCoilBox(FVector& Center, FVector& HalfExtent) const
	{
		Center = FVector(0, 0, -(GetKnotTop() + .5f * GetCoilLength()));
		HalfExtent = FVector(3.1f * RopeRadius, 3.9f * RopeRadius, .5f * GetCoilLength() + .5f * RopeRadius);
	}
	/** Knot bottom (where the loop leaves the coil), in this component's space. */
	FVector GetKnotBottom() const { return FVector(0, 0, -(GetKnotTop() + GetCoilLength())); }
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Noose")
	float CurrentInnerRadius = 0.f;

private:
	void Build(const FVector& Axis, const FVector& KnotSide, float InnerRadius, const TArray<float>& InnerProfile);
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyNooseLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	/**
	 * Ties the gallows noose (Rope = the gallows' rope component) around one body of Target with a fully locked
	 * joint: no sliding, no twisting. The loop is rebuilt around the visible skin at the tie spot (measured from the
	 * mesh) plus Clearance, so the same noose fits a boar's neck or a human ankle. The knot stays outside the
	 * collision capsule, so the limb really passes through the loop and collision stays enabled. BodyBone = body to tie
	 * (neck_01, calf_l, ...). AtBone (optional) picks the spot along that body (foot_l to tie a calf at the ankle).
	 * The rope end must already be near the spot (it is pulled the last few cm).
	 */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Rope", meta = (ReturnDisplayName = "Tied", AdvancedDisplay = "Clearance"))
	static bool TieNoose(USkeletalMeshComponent* Rope, UPrimitiveComponent* Target, FName BodyBone, FName AtBone, FString& Error, float Clearance = 0.6f);
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Rope")
	static bool UntieNoose(USkeletalMeshComponent* Rope);
	UFUNCTION(BlueprintPure, Category = "Prophecy|Physics|Rope")
	static bool IsNooseTied(USkeletalMeshComponent* Rope);
	/** Where the rope end has to be for TieNoose with the same arguments (world). */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Rope", meta = (AdvancedDisplay = "Clearance"))
	static bool GetNooseTieTarget(USkeletalMeshComponent* Rope, UPrimitiveComponent* Target, FName BodyBone, FName AtBone, FVector& RopeEndLocation, FString& Error, float Clearance = 0.6f);
	/** Current error of the tie joint (0 = perfectly locked). */
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Physics|Rope")
	static bool GetNooseTieError(USkeletalMeshComponent* Rope, float& LinearCm, float& AngularDegrees);
};

namespace ProphecyNoose
{
// Called by the gallows rope helpers (Jolt path only).
void Install(USkeletalMeshComponent* Rope, FName TipBone, UStaticMeshComponent* AuthoredNoose);
float GetMassKg(const USkeletalMeshComponent* Rope);
void OnRopeAdmitted(USkeletalMeshComponent* Rope);
void OnRopeReeled(USkeletalMeshComponent* Rope);
}
