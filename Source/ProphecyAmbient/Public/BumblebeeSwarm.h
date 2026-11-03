#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Engine/EngineTypes.h"
#include "BumblebeeSwarm.generated.h"

class ABumblebeeZone;
class UInstancedStaticMeshComponent;
class UStaticMesh;

UENUM()
enum class EBeeState : uint8
{
	Unplaced,	// zone not yet near/loaded: no cost
	Landed,		// resting / walking on a surface
	Flying,		// following a pre-validated path
	Hover,		// unused (kept for compatibility): bees never stop in the air
};

/** One bee. Plain data, simulated by ABumblebeeSwarm. */
struct FBumblebee
{
	// placement
	FVector Pos = FVector::ZeroVector;		// landed: point on the surface, flying: body centre
	FVector Up = FVector::UpVector;			// landed: surface normal
	FVector Fwd = FVector::ForwardVector;	// heading (tangent to surface when landed)
	FQuat Rot = FQuat::Identity;			// rendered rotation (smoothed)
	FVector Vel = FVector::ZeroVector;
	// flight smoothing state
	FVector Base = FVector::ZeroVector;			// point on the validated path (Pos = Base + sway offset)
	FVector Accel = FVector::ZeroVector;		// low-passed path acceleration (banking / pitch)
	FVector PathVel = FVector::ZeroVector;		// path tangent x speed of the last update
	float SwayAmp = 0.f;						// side-to-side sway amplitude, eased (continuous across legs)
	FVector SwaySide = FVector::RightVector;	// sway direction, parallel-transported along the path (no flips on vertical stretches)
	bool bSettling = false;						// just landed: body still rotating into the surface pose

	EBeeState State = EBeeState::Unplaced;
	uint8 Tier = 3;			// 0 near, 1 mid (visible), 2 far (frozen)
	int8 Lod = -1;			// rendered LOD bucket, -1 = parked
	int8 Pose = -1;			// rendered pose bucket (0 fly, 1 landed), -1 = parked
	bool bWantsPlan = false;
	bool bThreatened = false;
	bool bWalker = false;
	uint8 FlightPhase = 0;		// 0 path, 1 doubling back along the validated path while the next leg is planned
	float ViewDist = 1e9f;
	float ValidateTimer = 0.f;
	float Scale = 1.f;				// final render/behaviour scale (swarm BeeScale x zone multiplier x variation)
	float SizeVariation = 1.f;
	float ThreatCooldown = 0.f;		// after a failed flee plan, don't re-check threats every frame
	float PendingDt = 0.f;			// accumulated time for bees updated at a reduced rate
	FVector ThreatPos = FVector::ZeroVector;
	bool bEscaping = false;
	bool bRenderDirty = true;
	FVector LastRenderPos = FVector::ZeroVector;	// last transform sent to the renderer (sub-pixel updates are skipped for bees on surfaces)
	FQuat LastRenderRot = FQuat::Identity;
	float LastRenderAmount = 0.f;
	int16 Zone = -1;

	// landed behaviour
	float LandedTimeLeft = 0.f;		// until takeoff
	float BoutTimeLeft = 0.f;		// current walk/pause bout
	bool bWalking = false;
	float WalkSpeed = 0.f;
	float TurnRate = 0.f;			// rad/s, Ornstein-Uhlenbeck correlated random walk
	float WalkPhase = 0.f;			// leg cycles walked (distance / stride): drives the material, so feet never slide
	float WalkAmount = 0.f;
	float StrideModel = 0.7f;		// stride length in model cm (scaled by Scale in the world); grows with walking speed
	float WalkBase = 2.5f;			// zone walking speed (cm/s) x individual variation
	float WingHz = 150.f;			// wing beat frequency of this bee (per-instance custom data 3)
	// walking moves along short segments whose end point was checked on the surface first (never past an edge)
	FVector WalkStart = FVector::ZeroVector, WalkTarget = FVector::ZeroVector;
	FVector WalkStartUp = FVector::UpVector, WalkTargetN = FVector::UpVector;
	float WalkSegLen = 0.f, WalkSegRemain = 0.f;

	// flight path (validated polyline, corners rounded within the validated clearance)
	FVector Path[6];
	float CornerR[6] = { 0.f, 0.f, 0.f, 0.f, 0.f, 0.f };	// rounding radius at interior points (0 at the ends)
	uint8 PathNum = 0;
	uint8 AirLegsLeft = 0;		// aerial legs still to fly before looking for a landing spot
	float PathS = 0.f;			// distance travelled along path
	float PathLen = 0.f;
	float LastLegS = 0.f;
	// leg geometry, computed once per leg (path lookups and speed limits are then plain arithmetic)
	FVector3f SegDir[6];			// direction of segment i (Path[i] -> Path[i+1])
	float LineStartS[6];			// path distance where segment i's straight part starts
	float LineLen[6];				// length of segment i's straight part
	FVector ArcO[6];				// arc centre at corner i (interior points)
	FVector3f ArcN0[6];				// arc inward normal at its start
	float ArcR[6];					// arc radius (0 = no arc: straight through)
	float ArcPhi[6];				// arc turn angle
	float ArcLen[6];				// corner piece length
	float CornerVc[6];				// corner speed limit (lateral acceleration / turn-rate)		// path distance where the final straight segment begins (follow-up legs start from there)
	float Speed = 0.f;
	float CruiseSpeed = 180.f;
	float ApproachLen = 0.f;	// length of the last (surface-normal) segment of a landing path
	bool bLandAtEnd = false;
	FVector LandPoint = FVector::ZeroVector;
	FVector LandNormal = FVector::UpVector;
	float WobbleSeed = 0.f;
	float PlanCooldown = 0.f;
	int32 PlanFailures = 0;

	// escape memory (indoor search)
	FVector Visited[6];
	uint8 VisitedNum = 0;
	uint8 VisitedHead = 0;
	float EscapeTime = 0.f;
	float IndoorCheckAge = 1e9f;
	bool bIndoorCached = false;
};

USTRUCT(BlueprintType)
struct FBumblebeeStats
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Bees = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Unplaced = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Landed = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Walking = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Flying = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Near = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Mid = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Far = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Escaping = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") float AvgTickMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") float MaxTickMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") float TracesPerSecond = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Takeoffs = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 ThreatTakeoffs = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 Landings = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 EscapesStarted = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 EscapesSucceeded = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 PlanFailures = 0;
	/** Flights that reached the end of their path before the next leg was planned (bee doubled back instead of stopping). */
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 DoubleBacks = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Bumblebees") int32 InstanceUpdatesPerSecond = 0;
};

/**
 * Lightweight bumblebee simulation + renderer for hundreds of ambient bees.
 * - One actor, 8 instanced static mesh components (fly/landed pose x 4 LODs). No per-bee actors, skeletons or ticks.
 * - Wings and legs are animated in the material (World Position Offset) from per-instance custom data.
 * - Flights follow polylines validated with sphere sweeps before take-off, so bees never fly through static geometry.
 * - Cost scales with distance: near bees walk (with surface probes) and react, mid bees fly/rest without probes,
 *   far bees are frozen in a valid resting pose (zero CPU besides a distance check) and culled on GPU.
 * - All traces go through a global per-frame budget.
 */
UCLASS(meta = (DisplayName = "Bumblebee Swarm"))
class PROPHECYAMBIENT_API ABumblebeeSwarm : public AActor
{
	GENERATED_BODY()

public:
	ABumblebeeSwarm();

	static ABumblebeeSwarm* Find(const UObject* WorldContext);
	static ABumblebeeSwarm* GetOrCreate(const UObject* WorldContext);

	UFUNCTION(BlueprintPure, Category = "Bumblebees", meta = (WorldContext = "WorldContext"))
	static ABumblebeeSwarm* GetBumblebeeSwarm(const UObject* WorldContext) { return Find(WorldContext); }

	// ---------------- assets
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Assets")
	TSoftObjectPtr<UStaticMesh> FlyMesh;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Assets")
	TSoftObjectPtr<UStaticMesh> LandedMesh;

	// ---------------- size
	/** 1 = the modelled bee (about 2.5 cm long, a queen). Workers are smaller: the default 0.75 gives about 1.9 cm bees.
	 *  Scales rendering, walking, take-off/landing offsets and flight clearance together. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bumblebees|Size", meta = (ClampMin = "0.05", UIMin = "0.3", UIMax = "3"))
	float BeeScale = 0.75f;
	/** Random per-bee size factor (a few percent of bees are queens at x1.2-1.35). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Size") FVector2D SizeVariation = FVector2D(0.8f, 1.15f);

	// ---------------- distances (cm)
	/** Below: LOD0 (hero), LOD1, LOD2; beyond LOD2Distance: LOD3 (very cheap) up to VisibleDistance. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float LOD0Distance = 150.f;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float LOD1Distance = 450.f;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float LOD2Distance = 1000.f;
	/** Bees closer than this react, plan detailed flights and escape rooms. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float NearDistance = 1500.f;
	/** Bees closer than this walk on their surface (a 2 cm bee is a few pixels beyond ~6 m); farther ones rest/groom. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float WalkDistance = 600.f;
	/** Rendered + simulated (fly/rest) up to here. Beyond: frozen and culled. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float VisibleDistance = 2500.f;
	/** Zones closer than this place their bees. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float PlacementDistance = 4000.f;

	// ---------------- behaviour
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D CruiseSpeedRange = FVector2D(120.f, 240.f);
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D FlightRange = FVector2D(60.f, 600.f);
	/** Length of the aerial legs bees chain together before landing (zone Air Time sets how many). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D AirLegRange = FVector2D(60.f, 320.f);
	/** Time spent on a surface (scaled down by the zone's Air Time). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D LandedTimeRange = FVector2D(2.f, 14.f);
	/** Per-bee factor on the zone Walk Speed. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D WalkSpeedVariation = FVector2D(0.75f, 1.25f);
	/** Fraction of landings in which the bee walks at all (others just rest/groom). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float WalkerFraction = 0.92f;
	/** Mean duration of a walking bout (s). Pauses between bouts are short, heavy-tailed. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float WalkBoutMean = 2.6f;
	/** Typical pause between walking bouts (s); occasional long pauses come from the heavy tail. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float PauseScale = 0.18f;
	/** Surfaces with normal.Z below this are not landed on (0 = walls allowed, -1 = ceilings too). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float MinLandingNormalZ = -0.5f;
	/** Sideways acceleration limit in turns (cm/s2); bees slow down for tight turns but never stop. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float TurnAcceleration = 2500.f;
	/** Heading change limit along the path (deg/s): in tight spots bees slow down and pivot instead of whipping round. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float MaxPathTurnRate = 340.f;
	/** Landing: speed falls in proportion to the distance left (1/s, i.e. constant time-to-contact)... */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float ApproachRate = 4.f;
	/** ... down to this touchdown speed (cm/s for a 1x bee). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float TouchdownSpeed = 7.f;
	/** Widest corner rounding (cm). Wide corners are checked with extra sweeps along the curve; tight spots fall back to
	 *  rounding that stays inside the already-validated clearance. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float MaxCornerRadius = 70.f;	// tangent length of the arc
	/** Body turn-rate limit (deg/s). Bumblebee body saccades peak around 350-500 deg/s. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float MaxBodyTurnRate = 360.f;
	/** Bank into turns: degrees of roll per g of sideways acceleration (clamped to 35 deg). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float BankPerG = 30.f;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") bool bLandOnMovableComponents = false;

	// ---------------- threats
	/** Actors that make bees take off when they move close. Player pawns are added automatically if enabled. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bumblebees|Threats") TArray<TObjectPtr<AActor>> ThreatActors;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Threats") bool bPlayerPawnsAreThreats = true;
	/** Actors with this tag are added to ThreatActors at BeginPlay. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Threats") FName ThreatTag = TEXT("BeeThreat");
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Threats") float ThreatRadius = 180.f;
	/** A threat must move at least this fast (cm/s) to disturb bees at ThreatRadius ... */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Threats") float ThreatMinSpeed = 25.f;
	/** ... but anything closer than this always does. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Threats") float ThreatPanicRadius = 45.f;

	// ---------------- cost
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") int32 MaxTracesPerFrame = 32;
	/** Walking surface probes may use at most this many of the per-frame traces; the rest is kept for take-offs and flight legs. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") int32 MaxWalkTracesPerFrame = 16;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") int32 MaxEscapingBees = 6;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") bool bCastShadowsNear = true;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") TEnumAsByte<ECollisionChannel> TraceChannel = ECC_Visibility;
	/** Complex (per-triangle) traces for landing/walking, so bees sit on the visible surface. Sweeps always use simple collision. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") bool bTraceComplex = true;
	/** Clearance radius used to validate flight paths (body + wings + wobble). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") float FlightClearance = 5.f;

	UPROPERTY(EditAnywhere, Category = "Bumblebees|Debug") bool bDrawDebug = false;

	// ---------------- API
	UFUNCTION(BlueprintCallable, Category = "Bumblebees") void AddThreatActor(AActor* Actor);
	/** Change the size of every bee at runtime (1 = 2.5 cm model, 0.75 = typical worker). */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees") void SetBeeScale(float NewScale);
	UFUNCTION(BlueprintCallable, Category = "Bumblebees") void RemoveThreatActor(AActor* Actor);
	UFUNCTION(BlueprintPure, Category = "Bumblebees") FBumblebeeStats GetStats() const { return Stats; }
	UFUNCTION(BlueprintPure, Category = "Bumblebees") int32 GetNumBees() const { return Bees.Num(); }
	/** Rendered transform of a bee (for cameras/tests). */
	UFUNCTION(BlueprintPure, Category = "Bumblebees") FTransform GetBeeTransform(int32 Index) const;
	UFUNCTION(BlueprintPure, Category = "Bumblebees") bool IsBeeLanded(int32 Index) const;
	UFUNCTION(BlueprintPure, Category = "Bumblebees") bool IsBeeFlying(int32 Index) const;
	UFUNCTION(BlueprintPure, Category = "Bumblebees") bool IsBeeWalking(int32 Index) const;
	/** Surface normal under a landed bee (zero when flying). */
	UFUNCTION(BlueprintPure, Category = "Bumblebees") FVector GetBeeSurfaceNormal(int32 Index) const;
	/** Moves up to Count landed bees onto surfaces around Location (test / scripted events). Returns how many moved. */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees") int32 RelocateBeesTo(FVector Location, float Radius, int32 Count, bool bWalkers = false);

	void RegisterZone(ABumblebeeZone* Zone);
	void UnregisterZone(ABumblebeeZone* Zone);

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

private:
	struct FZoneEntry
	{
		TWeakObjectPtr<ABumblebeeZone> Zone;
		int32 FirstBee = 0;
		int32 Count = 0;
		int32 Placed = 0;
	};
	struct FThreat
	{
		TWeakObjectPtr<AActor> Actor;
		FVector LastPos = FVector::ZeroVector;
		FVector Pos = FVector::ZeroVector;
		float Speed = 0.f;
		bool bValid = false;
	};

	UPROPERTY(VisibleAnywhere, Category = "Bumblebees") TArray<TObjectPtr<UInstancedStaticMeshComponent>> Instances; // [pose*4+lod]

	TArray<FBumblebee> Bees;
	TArray<FZoneEntry> Zones;
	TArray<FThreat> Threats;
	TArray<FVector> Viewers;
	FRandomStream Rng;
	int32 TracesThisFrame = 0;
	int32 WalkTracesThisFrame = 0;
	int32 TracesWindow = 0;
	float StatsWindow = 0.f;
	double TickMsSum = 0.0;
	int32 TickCount = 0;
	float TickMsMax = 0.f;
	FBumblebeeStats Stats;
	bool bAssetsReady = false;
	float Time = 0.f;
	uint32 FrameCounter = 0;
	float LogTimer = 0.f;
	TArray<int32> UrgentQueue, NearQueue, MidQueue;
	int32 InstanceUpdatesWindow = 0;
	bool bRenderHidden = false, bShadowsOff = false, bWpoOff = false;

	// optional profiler (bumblebees.Profile 1): where the swarm's game-thread time goes
	enum EProf : uint8 { P_Scan, P_Landed, P_Flight, P_Plan, P_Render, P_Place, P_TraceWalk, P_TracePlan, P_TracePlace, P_Num };
	bool bProfile = false;
	uint8 TraceCtx = P_TracePlan;
	double ProfSec[P_Num] = {};
	int32 ProfFrames = 0;
	void ApplyDebugToggles();

	// setup
	void EnsureComponents();
	void AllocateZoneBees(FZoneEntry& Entry);
	bool TryPlaceBee(int32 Index, const ABumblebeeZone* Zone);

	// per-frame
	void GatherViewersAndThreats(float Dt);
	void UpdateTier(FBumblebee& B) const;
	void TickLanded(int32 Index, FBumblebee& B, float Dt);
	void TickFlying(int32 Index, FBumblebee& B, float Dt);
	void CheckThreat(FBumblebee& B);
	enum class EPlan : uint8 { Done, Failed, Deferred };
	EPlan Plan(int32 Index, FBumblebee& B);
	bool PlanLanding(int32 Index, FBumblebee& B, const FVector& From, const FVector& AwayFrom);
	bool PlanEscapeStep(int32 Index, FBumblebee& B, const FVector& From);
	void FreezeFar(FBumblebee& B);
	void Land(FBumblebee& B);
	void StartLandedBehaviour(FBumblebee& B, bool bFresh);
	void UpdateRender(int32 Index, FBumblebee& B);
	void UpdateStats(float Dt);

	// queries (budgeted)
	bool HasBudget(int32 Needed, bool bUrgent) const;
	bool Line(const FVector& A, const FVector& B, FHitResult& Hit);
	bool Sweep(const FVector& A, const FVector& B, float Radius, FHitResult& Hit);
	bool IsLandable(const FHitResult& Hit) const;
	bool IsEnclosed(const FVector& P, bool bUrgent);
	bool HasOpenSky(const FVector& P);

	const ABumblebeeZone* ZoneOf(const FBumblebee& B) const;
	float Clearance(const FBumblebee& B) const;
	void RefreshBeeScale(FBumblebee& B);
	static FVector PathPoint(const FBumblebee& B, float S, FVector* OutDir = nullptr);
	void SetFlightPath(FBumblebee& B, TArrayView<const FVector> Points, bool bLand, const FVector& LandPoint, const FVector& LandNormal);
	bool PlanAirLeg(int32 Index, FBumblebee& B, const FVector& From);
	static FVector FlightBase(const FBumblebee& B) { return B.State == EBeeState::Flying ? B.Base : B.Pos; }
	bool CornerCurveIsFree(const FBumblebee& B, const FVector& Din, const FVector& Dout, const FVector& C, float D);
	float SpeedLimit(const FBumblebee& B) const;
	void BeginFlight(FBumblebee& B);
	void Remember(FBumblebee& B, const FVector& P);
	float HeavyTailPause();
	float NearestViewerDistSq(const FVector& P) const;
};
