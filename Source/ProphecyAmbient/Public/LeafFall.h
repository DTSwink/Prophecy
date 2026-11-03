#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "LeafFall.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UPrimitiveComponent;

/** Water / dryness of a leaf when it lets go: sets its mass, how limp or curled it is, and its colour. */
UENUM(BlueprintType)
enum class ELeafCondition : uint8 { Fresh, Dry, Damp, Wet };

/** How a leaf comes down (decided by its own geometry and mass, see ALeafFall). */
UENUM(BlueprintType)
enum class ELeafFlight : uint8
{
	Flutter,	// planar zig-zag pendulum: glides one way, swoops up, stalls, glides back (light flat leaves)
	Chaotic,	// flutter that now and then overturns into a few tumbles and back (the flutter / tumble border)
	Tumble,		// end-over-end autorotation, drifting sideways on a slanted path ("flies and rolls over")
	Roll,		// a rolled-up dry leaf: spins about its long axis like a short tube, falls faster and slants
	Spiral,		// a twisted / cupped dry leaf held at a tilt while the glide direction turns: helical descent
	Rock		// soaked, limp leaf: small fast rocking, heavy and almost straight down
};

/** Blade shapes (one mesh each). */
UENUM(BlueprintType)
enum class ELeafShape : uint8 { Flat, Wavy, Cupped, Rolled, Twisted, Wet };

USTRUCT(BlueprintType)
struct FLeafFallStats
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Trees = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 TreesInRange = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Falling = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Resting = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Spawned = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Landed = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Removed = 0;
	/** Lying leaves being pushed along the ground by the wind now, and leaves the wind has lifted off again so far. */
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 Sliding = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") int32 LiftOffs = 0;
	/** Spawned so far by flight style: Flutter, Chaotic, Tumble, Roll, Spiral, Rock. */
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") TArray<int32> ByFlight;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") float AvgTickMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Leaves") float MaxTickMs = 0.f;
};

/** One falling / resting leaf (simulated on the game thread, drawn as an instance of its shape's mesh). */
struct FLeafSim
{
	// properties
	float Len = 0.08f, Wid = 0.05f, Area = 0.003f, Mass = 2e-4f, AddedMass = 1e-4f, AR = 2.f, IStar = 0.3f, Scale = 1.f;
	float Curl = 0.f, Twist = 0.f, Wet = 0.f, Senescence = 0.5f;
	ELeafCondition Condition = ELeafCondition::Dry;
	ELeafFlight Flight = ELeafFlight::Flutter;
	ELeafShape Shape = ELeafShape::Flat;
	// motion (SI inside the model: m/s; position kept in cm)
	FVector P = FVector::ZeroVector, V = FVector::ZeroVector;
	FQuat Q = FQuat::Identity;
	// orientation oscillator (regime)
	float Psi = 0.f, PsiRate = 0.f, Theta = 0.f, Phase = 0.f, Freq = 1.f, Amp = 0.8f, Om = 8.f, Tilt = 0.6f, PlaneRate = 0.f;
	float Sigma = 0.f, Spin = 0.f, Chi = 0.f;
	bool bTumbling = false;
	// life
	bool bActive = false, bLanded = false, bSliding = false;
	float Age = 0.f, RestT = 0.f, Fade = 1.f, SettleT = 0.f;
	float GroundZ = 0.f;				// ground under the leaf when it let go (log wind profile)
	FVector SlideV = FVector::ZeroVector;		// m/s along the ground
	float TumbleAng = 0.f;				// cartwheeling over its edge while pushed
	FVector TumbleAxis = FVector::RightVector;
	FQuat LiftQ = FQuat::Identity;			// orientation when the wind picked it up again (blended into flight)
	float BlendT = 1.f;
	float LiftCool = 0.f;					// seconds before this leaf may be lifted off again
	float Grip = 1.f;					// this leaf on this bit of ground: litter interlock / roughness (x friction)
	float Snag = 0.f;					// caught on a twig or grass stem: extra hold until a stronger gust frees it
	bool bFlip = false;				// a flat leaf flipping over (otherwise it skids)
	FQuat SettleFrom = FQuat::Identity, RestQ = FQuat::Identity;
	int32 Slot = INDEX_NONE;
	FRandomStream R;
	FVector2D WidthEff = FVector2D::ZeroVector;	// x = effective width (curl narrows the projected blade), y = broadside terminal speed
};

struct FLeafPool
{
	TObjectPtr<UInstancedStaticMeshComponent> ISM = nullptr;
	TArray<int32> Free;
	TArray<FTransform> Xf;
	float ZMin = 0.f, ZMax = 0.f;		// mesh height below / above its origin (cm, unscaled) for resting on the ground
};

/**
 * Falling leaves for the trees of a level (default: the PCG hornbeams tree1 / tree2). Leaves let go sparsely from the
 * outer canopy of trees near the player, fall according to their own shape and condition, land with simple collision, lie
 * for RestTime, fade out (dithered) over FadeTime and are gone. No setup needed: one is created automatically in any world
 * that contains the tree meshes; place one to change the settings.
 *
 * Flight model (Docs/Leaves.md):
 * - the translational forces are the Andersen-Pesavento-Wang (2005) quasi-steady plate model (drag C_D(alpha), circulatory
 *   lift C_T sin 2alpha, rotational circulation C_R), with finite-aspect-ratio lift slope and induced drag, and the normal
 *   added mass (Kirchhoff), all relative to the air;
 * - the orientation follows the falling-plate regime the leaf belongs to (Field et al. 1997 phase diagram,
 *   flutter / chaotic / tumbling by the dimensionless moment of inertia I*; spiral descent, Zhong et al. 2011), with
 *   frequency and amplitude scaled from the leaf (Strouhal ~ f l / U);
 * - curl, twist and wetness come from the leaf's condition: dry leaves curl and twist (tumble, roll, spiral), soaked ones are
 *   heavy and limp (rock straight down).
 */
UCLASS(meta = (DisplayName = "Leaf Fall"))
class PROPHECYAMBIENT_API ALeafFall : public AActor
{
	GENERATED_BODY()

public:
	ALeafFall();
	static ALeafFall* Find(const UObject* WorldContext, bool bCreate = false);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") bool bEnabled = true;
	/** Trees that drop leaves (static meshes; any component using them, PCG instances included). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") TArray<TSoftObjectPtr<UStaticMesh>> TreeMeshes;
	/** Average leaves let go per tree per minute ("sparse": a few). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves", meta = (ClampMin = "0")) float LeavesPerTreePerMinute = 5.f;
	/** Only trees within this distance (cm) of a player camera drop leaves. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") float ActiveRadius = 4500.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves", meta = (ClampMin = "1")) int32 MaxLeaves = 400;
	/** Seconds a leaf lies on the ground before fading, then the fade duration (gone after RestTime + FadeTime). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") float RestTime = 7.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") float FadeTime = 2.5f;
	/** 0 = end of summer (mostly green leaves let go) .. 1 = late autumn (golden to brown). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves", meta = (ClampMin = "0", ClampMax = "1")) float Season = 0.65f;
	/** Share of each condition among the leaves let go (normalised). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Condition") float FreshShare = 0.25f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Condition") float DryShare = 0.45f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Condition") float DampShare = 0.18f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Condition") float WetShare = 0.12f;
	/** Blade length (cm): hornbeam 6-11 cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") FVector2D LeafLengthCm = FVector2D(6.f, 11.f);
	/** Extra steady air motion (cm/s) on top of the Global Wind. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") FVector Wind = FVector::ZeroVector;
	/** Lying leaves are pushed along the ground, cartwheel and can be lifted off again by strong bursts. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Wind") bool bWindMovesFallenLeaves = true;
	/** Wind right at a lying leaf as a fraction of the wind at ~10 m: log profile ln(z/z0)/ln(10 m/z0) for z ~2-5 cm over litter. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Wind") float GroundWindFactor = 0.18f;
	/** Lift / weight ratio above which a cartwheeling leaf, caught with its edge up into the wind, takes off. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Wind") float LiftOffRatio = 14.f;
	/** How often (per metre slid) a moving leaf catches on something and stops. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Wind") float SnagPerMetre = 0.6f;
	/** How much more often a tree lets a leaf go inside a burst (x at full burst intensity). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Wind") float GustReleaseBoost = 8.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") bool bCastShadows = true;
	/** Leaves hit the trees' own collision too (off: canopy collision would catch them in the branches). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves") bool bCollideWithTrees = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Assets") TSoftObjectPtr<UMaterialInterface> LeafMaterial;
	/** Meshes per ELeafShape (Flat, Wavy, Cupped, Rolled, Twisted, Wet). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Leaves|Assets") TArray<TSoftObjectPtr<UStaticMesh>> LeafMeshes;

	UFUNCTION(BlueprintCallable, Category = "Leaves") void SetWind(FVector InWindCmPerSec) { Wind = InWindCmPerSec; }
	UFUNCTION(BlueprintPure, Category = "Leaves") FLeafFallStats GetStats() const { return Stats; }
	/** Lets one leaf go at a point (tests / scripted moments). Returns its index or -1. Random condition when bRandom. */
	UFUNCTION(BlueprintCallable, Category = "Leaves") int32 SpawnLeafAt(FVector Location, ELeafCondition Condition, bool bRandomCondition = true);
	/** Rescan the level for trees now (they are also rescanned every few seconds, e.g. after PCG generation). */
	UFUNCTION(BlueprintCallable, Category = "Leaves") void RescanTrees();

	/** Air velocity (cm/s) at a point. Hook for the global wind system. */
	virtual FVector WindAt(const FVector& P) const;

	// test access
	const FLeafSim* GetLeaf(int32 Index) const { return Leaves.IsValidIndex(Index) && Leaves[Index].bActive ? &Leaves[Index] : nullptr; }
	int32 SpawnLeafWith(FVector Location, ELeafCondition Condition, int32 ForceShape = -1, int32 ForceFlight = -1);
	FVector TreeCanopyCentre(int32 i) const { return Trees.IsValidIndex(i) ? Trees[i].Centre : FVector::ZeroVector; }
	int32 NumTrees() const { return Trees.Num(); }
	FVector TreeBase(int32 i) const { return Trees.IsValidIndex(i) ? Trees[i].Base : FVector::ZeroVector; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	struct FTree { FVector Centre, Radii, Base; TWeakObjectPtr<UPrimitiveComponent> Comp; };
	TArray<FTree> Trees;
	TArray<int32> InRange;
	TArray<FVector> Cameras;
	TArray<FLeafSim> Leaves;
	TArray<int32> FreeLeaves;
	FLeafPool Pools[6];
	UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> PoolComponents;
	UPROPERTY() TArray<TObjectPtr<UPrimitiveComponent>> TreeComponents;
	UPROPERTY() TSet<TObjectPtr<UStaticMesh>> TreeSet;
	float ScanTimer = 0.f, EmitAccum = 0.f, NextGap = 1.f;
	FRandomStream Rng;
	FLeafFallStats Stats;
	double TickMsSum = 0.0;
	int32 TickN = 0;
	float StatsT = 0.f;
	bool bAssetsReady = false;
	TWeakObjectPtr<class AGlobalWind> GlobalWind;
	TArray<float> TreeWeight;
	void StepGround(FLeafSim& L, int32 Index, float Dt, const FCollisionObjectQueryParams& Obj, const FCollisionQueryParams& Q, bool& bMoved);

	void EnsureAssets();
	void ScanTrees();
	void AddTree(const FTransform& T, const FBox& LocalBox, UPrimitiveComponent* C);
	int32 AllocLeaf();
	void InitLeaf(FLeafSim& L, ELeafCondition Cond, int32 ForceShape, int32 ForceFlight);
	FQuat Orient(const FLeafSim& L) const;
	void StepAir(FLeafSim& L, float Dt);
	void Land(FLeafSim& L, const FHitResult& Hit);
	void Release(FLeafSim& L, int32 Index);
	void PushInstance(FLeafSim& L, int32* Lo, int32* Hi);
	void WriteCustom(const FLeafSim& L, bool bAll);
};

/** Creates a Leaf Fall automatically in game worlds (it only does work where the tree meshes exist). */
UCLASS()
class PROPHECYAMBIENT_API ULeafFallSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
};
