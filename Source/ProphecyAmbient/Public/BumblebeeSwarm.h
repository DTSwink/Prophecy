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
	Hover,		// short inspection hover before landing / while searching
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

	EBeeState State = EBeeState::Unplaced;
	uint8 Tier = 3;			// 0 near, 1 mid (visible), 2 far (frozen)
	int8 Lod = -1;			// rendered LOD bucket, -1 = parked
	int8 Pose = -1;			// rendered pose bucket (0 fly, 1 landed), -1 = parked
	bool bWantsPlan = false;
	bool bThreatened = false;
	bool bWalker = false;
	uint8 FlightPhase = 0;		// 0 path, 1 hover, 2 final approach
	float ViewDist = 1e9f;
	float ValidateTimer = 0.f;
	FVector ThreatPos = FVector::ZeroVector;
	bool bEscaping = false;
	bool bRenderDirty = true;
	int16 Zone = -1;

	// landed behaviour
	float LandedTimeLeft = 0.f;		// until takeoff
	float BoutTimeLeft = 0.f;		// current walk/pause bout
	bool bWalking = false;
	float WalkSpeed = 0.f;
	float TurnRate = 0.f;			// rad/s, Ornstein-Uhlenbeck correlated random walk
	float WalkPhase = 0.f;
	float WalkAmount = 0.f;
	float ProbeDistance = 0.f;		// travelled since last surface probe

	// flight path (validated polyline)
	FVector Path[6];
	uint8 PathNum = 0;
	float PathS = 0.f;			// distance travelled along path
	float PathLen = 0.f;
	float Speed = 0.f;
	float CruiseSpeed = 180.f;
	float HoverTimeLeft = 0.f;
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

	// ---------------- distances (cm)
	/** Below: LOD0 (hero), LOD1, LOD2; beyond LOD2Distance: LOD3 (very cheap) up to VisibleDistance. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float LOD0Distance = 150.f;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float LOD1Distance = 450.f;
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float LOD2Distance = 1000.f;
	/** Bees closer than this walk, probe surfaces and escape rooms. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float NearDistance = 1500.f;
	/** Rendered + simulated (fly/rest) up to here. Beyond: frozen and culled. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float VisibleDistance = 2500.f;
	/** Zones closer than this place their bees. */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Distances") float PlacementDistance = 4000.f;

	// ---------------- behaviour
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D CruiseSpeedRange = FVector2D(120.f, 240.f);
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D FlightRange = FVector2D(60.f, 600.f);
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D LandedTimeRange = FVector2D(6.f, 40.f);
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") FVector2D WalkSpeedRange = FVector2D(1.5f, 4.f);
	/** Fraction of landings in which the bee walks at all (others just rest/groom). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float WalkerFraction = 0.7f;
	/** Surfaces with normal.Z below this are not landed on (0 = walls allowed, -1 = ceilings too). */
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Behaviour") float MinLandingNormalZ = -0.05f;
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
	UPROPERTY(EditAnywhere, Category = "Bumblebees|Performance") int32 MaxTracesPerFrame = 24;
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
	UFUNCTION(BlueprintCallable, Category = "Bumblebees") void RemoveThreatActor(AActor* Actor);
	UFUNCTION(BlueprintPure, Category = "Bumblebees") FBumblebeeStats GetStats() const { return Stats; }
	UFUNCTION(BlueprintPure, Category = "Bumblebees") int32 GetNumBees() const { return Bees.Num(); }
	/** Rendered transform of a bee (for cameras/tests). */
	UFUNCTION(BlueprintPure, Category = "Bumblebees") FTransform GetBeeTransform(int32 Index) const;
	UFUNCTION(BlueprintPure, Category = "Bumblebees") bool IsBeeLanded(int32 Index) const;
	UFUNCTION(BlueprintPure, Category = "Bumblebees") bool IsBeeFlying(int32 Index) const;
	/** Moves up to Count landed bees onto surfaces around Location (test / scripted events). Returns how many moved. */
	UFUNCTION(BlueprintCallable, Category = "Bumblebees") int32 RelocateBeesTo(FVector Location, float Radius, int32 Count);

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
	static FVector PathPoint(const FBumblebee& B, float S, FVector* OutDir = nullptr);
	void SetFlightPath(FBumblebee& B, TArrayView<const FVector> Points, bool bLand, const FVector& LandPoint, const FVector& LandNormal);
	void Remember(FBumblebee& B, const FVector& P);
	float HeavyTailPause();
	float NearestViewerDistSq(const FVector& P) const;
};
