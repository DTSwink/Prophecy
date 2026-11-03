#pragma once

#include "CoreMinimal.h"
#include "UObject/SoftObjectPtr.h"
#include "BirdTypes.generated.h"

class USkeletalMesh;
class UAnimSequence;
class UMaterialInterface;
class AActor;
class UPrimitiveComponent;
class ABird;

UENUM(BlueprintType)
enum class EBirdSpecies : uint8
{
	Gull,
	Kingfisher
};

UENUM(BlueprintType)
enum class EBirdState : uint8
{
	Unplaced,
	Perched,
	Walking,
	TakingOff,
	Flying,
	Landing,
	Dead
};

/** What a bird is busy with on top of its movement state (feeding). */
UENUM(BlueprintType)
enum class EBirdTask : uint8
{
	None,
	/** Kingfisher: flying out over the water to a hunting point. */
	FishHunt,
	/** Kingfisher: hovering, looking down for a fish. */
	FishHover,
	/** Kingfisher: plunge dive (wings folded). */
	FishDive,
	/** Kingfisher: under the surface. */
	FishUnder,
	/** Kingfisher: breaking out of the water. */
	FishEmerge,
	/** Kingfisher: carrying the fish to the beach. */
	FishCarry,
	/** Kingfisher: on the beach, holding the fish until it stops moving. */
	FishHold,
	/** Kingfisher: fish dropped, pecking at it. */
	FishPeck,
	/** Gull: flying to the remains. */
	ScavengeFly,
	/** Gull: walking up to the remains. */
	ScavengeWalk,
	/** Gull: picking up and swallowing the remains whole. */
	ScavengeEat
};

/**
 * Everything that differs between species. Defaults come from FBirdSpeciesSettings::Defaults(Species); a zone copies them
 * and you can override any value per zone. Units: cm, seconds, degrees, kg.
 * Assets are looked up by bone NAME (see Docs/Birds.md), so a better model with the same bone names drops straight in.
 */
USTRUCT(BlueprintType)
struct PROPHECYAMBIENT_API FBirdSpeciesSettings
{
	GENERATED_BODY()

	// ---- assets
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<USkeletalMesh> Mesh;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<UAnimSequence> AnimPerch;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<UAnimSequence> AnimWalk;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<UAnimSequence> AnimGlide;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<UAnimSequence> AnimFlap;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<UAnimSequence> AnimHover;
	/** Feather burst material (per-instance custom data: atlas cell + colours). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TSoftObjectPtr<UMaterialInterface> FeatherFXMaterial;

	// ---- body (model at scale 1)
	/** Body centre above the feet when perched (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Body") float BodyHeight = 17.f;
	/** Body radius used for ground spacing and the no-overlap rule when perched / walking. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Body") float BodyRadius = 14.f;
	/** Half wingspan: the no-overlap radius between flying birds. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Body") float HalfSpan = 55.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Body") float MassKg = 1.25f;

	// ---- flight
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float CruiseSpeed = 1000.f;
	/** Below this the bird hovers / brakes with deep flaps instead of banking. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float MinSpeed = 420.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float MaxSpeed = 1600.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float MaxBankDeg = 50.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float RollRateDeg = 140.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float MaxClimbDeg = 28.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float PitchRateDeg = 60.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float FlapHz = 3.f;
	/** Each bird flaps at its own rate (FlapHz +/- this fraction) that also wanders slowly, and every wingbeat has a slightly
	 *  different depth, so fast flappers never lock onto the frame rate (a fixed 10 Hz beat at 30 fps shows 3 frozen poses). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float FlapHzVariation = 0.12f;
	/** Body motion within each wingbeat is integrated from the lift the wings make over the stroke (downstroke ~55 % of the
	 *  cycle, mean lift = weight): heave = double integral of (lift - weight), so its size follows g / FlapHz^2 (gull ~5 cm
	 *  peak to peak, kingfisher <1 cm). Share of the downstroke's lift still made during the upstroke (0 = hover, 0.2-0.3 cruise). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float UpstrokeLift = 0.25f;
	/** Body pitch swing per wingbeat (deg): lift ahead of the centre of mass in the forward-swept downstroke, behind it in the upstroke. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float StrokePitchDeg = 2.5f;
	/** Response to air turbulence (strongest while gliding): roll (deg) and heave (cm at scale 1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float GustRollDeg = 3.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float GustHeaveCm = 1.5f;
	/** 0 = flaps all the time, 1 = glides / soars whenever it is not climbing or braking. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float GlideFraction = 0.6f;
	/** Sink rate while gliding (cm/s). Gulls ~ 1:12 glide ratio. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float GlideSink = 80.f;
	/** Cruise altitude band above the ground (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") FVector2D CruiseHeight = FVector2D(500.f, 1800.f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") float Acceleration = 450.f;

	// ---- ground
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float WalkSpeed = 45.f;
	/** Distance covered by one cycle of the Walk clip (two steps) at scale 1. The clip plays at WalkSpeed / Stride. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float StrideCm = 13.5f;
	/** Chance that a perched bird goes for a walk instead of just looking around. 0 = never walks. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float WalkChance = 0.7f;
	/** 0 = lands anywhere flat (ground mostly), 1 = strongly prefers raised perches (posts, rails, rocks, roofs). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float PerchHeightPreference = 0.25f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") FVector2D PerchTime = FVector2D(5.f, 18.f);
	/** While perched, every this-many seconds the bird does something small: turns on the spot or shuffles a few steps. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") FVector2D IdleActionTime = FVector2D(1.5f, 4.5f);
	/** Share of those idle actions that are a few steps (the rest are turns on the spot). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float ShuffleChance = 0.5f;
	/** Length of an idle shuffle (cm, scale 1). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") FVector2D ShuffleDistance = FVector2D(12.f, 45.f);
	/** Turn-on-the-spot rate (deg/s) and how many degrees one walk cycle (two steps) turns the bird. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float TurnRateDeg = 150.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ground") float TurnDegPerStepCycle = 80.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flight") FVector2D FlightTime = FVector2D(10.f, 35.f);

	// ---- threats
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Threats") float ThreatRadius = 700.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Threats") float PanicRadius = 250.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Threats") float ThreatMinSpeed = 60.f;

	// ---- beak / voice
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Voice") float BeakOpenDeg = 34.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Voice") FVector2D CryInterval = FVector2D(10.f, 40.f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Voice") FVector2D CryDuration = FVector2D(0.5f, 1.4f);

	// ---- feathers
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feathers") int32 DeathFeathers = 70;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feathers") int32 HitFeathers = 9;
	/** Typical body (contour) feather length (cm). Down is ~0.35x, coverts ~1.5x. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feathers") float FeatherSize = 6.5f;
	/** Colours used to tint the burst when the bird is not recoloured (the atlas already holds the species colours). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feathers") FLinearColor FeatherPrimary = FLinearColor(0.035f, 0.035f, 0.04f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feathers") FLinearColor FeatherSecondary = FLinearColor(0.93f, 0.93f, 0.92f);
	/** Fraction of burst feathers taken from the dark (primary-colour) tracts. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feathers") float DarkFeatherFraction = 0.3f;

	// ---- feeding
	/** Hunts fish: hovers over water, plunge-dives, carries the catch to the beach (kingfisher). Needs water (see Docs/Birds.md). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") bool bFishes = false;
	/** Seconds between fishing trips (while perched). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") FVector2D FishingInterval = FVector2D(30.f, 90.f);
	/** Water further than this from the bird is ignored (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") float FishingRange = 4000.f;
	/** Chance that a dive brings up a fish (real kingfishers: roughly every other dive). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") float FishingSuccess = 0.6f;
	/** Length of a caught fish (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") float FishLength = 8.f;
	/** How long the fish keeps struggling in the beak (s). The bird waits on the beach until it is still. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") float FishStruggleTime = 45.f;
	/** Pecks taken at the dropped fish before leaving the rest. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") FVector2D PeckCount = FVector2D(8.f, 14.f);
	/** Eats food remains left by other birds (gull): walks / flies to them and swallows them whole. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") bool bScavenges = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") float ScavengeRadius = 3500.f;
	/** Bill geometry in the mesh's reference pose (cm, scale 1): where the gape is and how long the bill is (+X). Used to hold food. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") FVector BillBase = FVector(20.1f, 0.f, 27.7f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feeding") float BillLength = 6.7f;

	// ---- blood
	/** Radius (cm, scale 1) of a blood stain on the plumage at a bleeding hit (exit wounds are 0.7x). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Blood") float BloodStainRadius = 4.5f;
	/** Scale of the project's blood splat Niagara system spawned at a bleeding hit (0 = none for this species). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Blood") float BloodVFXScale = 0.4f;

	// ---- colours (recolouring through the R/G masks of the body + feather textures)
	/** True when Primary/Secondary colours are applied to the bird (kingfisher). Gulls keep their texture colours. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Colours") bool bRecolourable = false;

	static FBirdSpeciesSettings Defaults(EBirdSpecies Species);
};

UENUM(BlueprintType)
enum class EBirdHitSource : uint8
{
	/** Kill / Wound / AddBloodStain called directly. */
	Manual,
	/** ApplyDamage / ApplyPointDamage. */
	Damage,
	/** A registered lethal object (spear...) swept through the bird. */
	LethalObject,
	/** A simulating physics object struck the bird. */
	PhysicsImpact
};

/** Everything known about a hit on a bird - the input of the bleed condition (and of OnBirdHit). */
USTRUCT(BlueprintType)
struct PROPHECYAMBIENT_API FBirdHitInfo
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category = "Bird") TObjectPtr<ABird> Bird = nullptr;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") EBirdHitSource Source = EBirdHitSource::Manual;
	/** The spear / sword / rock / damage causer (may be null). */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") TObjectPtr<AActor> Object = nullptr;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") TObjectPtr<UPrimitiveComponent> Component = nullptr;
	/** World hit point (on or in the bird). */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") FVector Location = FVector::ZeroVector;
	/** Direction the object travelled relative to the bird (unit). */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") FVector Direction = FVector::ForwardVector;
	/** Relative speed at impact (cm/s). 0 when unknown (plain damage). */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Speed = 0.f;
	/** Object mass x relative speed (kg cm/s). 0 when unknown. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Momentum = 0.f;
	/** The object's own forward axis (spear shaft / blade direction: its actor forward vector). */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") FVector ObjectForward = FVector::ForwardVector;
	/** Angle between ObjectForward and Direction (deg): 0 = tip first, 90 = sideways / flat, 180 = butt first. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float AlignmentDeg = 0.f;
	/** Angle between Direction and the bird's body surface (deg): 90 = straight in, 0 = grazing. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float IncidenceDeg = 90.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Damage = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") FName Bone = NAME_None;
	/** The hit kills the bird. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") bool bLethal = false;
	/** The object is a registered lethal object (spear class / tag / name). */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") bool bLethalObject = false;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Time = 0.f;
};

/** Return true to make the hit bleed (stain on the plumage at the hit point + the blood splat). */
DECLARE_DYNAMIC_DELEGATE_RetVal_OneParam(bool, FBirdBleedCondition, const FBirdHitInfo&, Hit);

/** Per-frame animation inputs (written by ABird, read by UBirdAnimInstance on the anim worker). */
USTRUCT(BlueprintType)
struct PROPHECYAMBIENT_API FBirdAnimParams
{
	GENERATED_BODY()
	/** 0 = on the ground, 1 = airborne pose. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Flight = 0.f;
	/** 0 = glide pose, 1 = flapping. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Flap = 0.f;
	/** Braking / take-off flaps with the body upright. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Hover = 0.f;
	/** Cycle phase 0..1 of the flap / hover clips. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float FlapPhase = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Walk = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float WalkPhase = 0.f;
	/** 0 closed .. 1 fully open. */
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float Beak = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float LookYaw = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float LookPitch = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bird") float BeakOpenDeg = 34.f;
};
