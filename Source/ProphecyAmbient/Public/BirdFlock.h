#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BirdTypes.h"
#include "UObject/ObjectKey.h"
#include "BirdFlock.generated.h"

class ABird;
class UInstancedStaticMeshComponent;
class UPhysicsAsset;
class USkeletalMesh;
class UMaterialInterface;
class UNiagaraSystem;
class UStaticMesh;
class ABirdFish;

USTRUCT(BlueprintType)
struct FBirdFlockStats
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Birds = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Perched = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Walking = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Flying = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Dead = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Feathers = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Takeoffs = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Landings = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Walks = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Cries = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Kills = 0;
	/** Times a bird touched geometry in flight (the look-ahead should keep this near 0). */
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Scrapes = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 AbortedLandings = 0;
	/** Idle turns on the spot / short shuffles while perched, and hits that bled. */
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Turns = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Shuffles = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 Bleeds = 0;
	/** Closest centre distance between two live birds divided by their combined no-overlap radius (>= 1 means no overlap). */
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float MinSeparationRatio = 99.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 SeparationCorrections = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float AvgTickMs = 0.f;
	/** Average ms per frame of each part of the flock tick (last second). */
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float SimulateMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float ProbeMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float SeparationMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float VisualsMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float FeathersMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float ScansMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float MaxTickMs = 0.f;
	/** Birds currently simulated at the reduced far rate, and casting shadows. */
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 FarBirds = 0;
	UPROPERTY(BlueprintReadOnly, Category = "Birds") int32 ShadowCasters = 0;
	/** Seconds the background scan takes to visit every actor of the world once. */
	UPROPERTY(BlueprintReadOnly, Category = "Birds") float ScanCycleSeconds = 0.f;
};

/** A falling feather of a burst (simulated on the game thread, drawn with one instanced mesh per species). */
struct FBirdFeather
{
	FVector P = FVector::ZeroVector, V = FVector::ZeroVector, W = FVector::ZeroVector, SwayDir = FVector::ForwardVector;
	FQuat Q = FQuat::Identity;
	float Size = 5.f, Width = 0.32f, Age = 0.f, Life = 40.f, Vt = 60.f, Freq = 3.f, Amp = 30.f, Phase = 0.f, Spin = 0.f;
	float GroundZ = -1e9f, GroundCheck = 0.f, Settle = 0.f;
	float TiltBias = 0.f, TiltAmp = 30.f;
	FVector GroundN = FVector::UpVector;
	bool bLanded = false;
	bool bActive = false;
	int32 Slot = INDEX_NONE;
};

struct FBirdFeatherPool
{
	TObjectPtr<UInstancedStaticMeshComponent> ISM = nullptr;
	TArray<FBirdFeather> Feathers;		// index == ISM instance
	TArray<int32> Free;
	TArray<FTransform> Xf;				// last transform sent to each instance (only changed ones are re-sent)
	int32 Active = 0;
	bool bDirty = false;
};

/**
 * World manager for the ambient birds (created by the first Bird Zone). Simulates every bird in one place so the no-overlap
 * rule, landing-spot reservations, threats and lethal hits are resolved consistently, and runs the feather bursts.
 *
 * Lethal objects: anything whose class is in LethalClasses, has a tag in LethalTags, or whose name contains one of
 * LethalNameContains, moving faster than LethalMinSpeed through a bird (swept test, works for projectiles with no collision).
 */
UCLASS(NotPlaceable, meta = (DisplayName = "Bird Flock"))
class PROPHECYAMBIENT_API ABirdFlock : public AActor
{
	GENERATED_BODY()

public:
	ABirdFlock();
	static ABirdFlock* Find(const UObject* WorldContext, bool bCreate = true);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds") bool bEnabled = true;

	// ---- threats (birds take off / flee)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Threats") TArray<TObjectPtr<AActor>> ThreatActors;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Threats") bool bPlayerPawnsAreThreats = true;
	/** Actors with this tag become threats (checked every second). BeeThreat actors scare birds too. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Threats") TArray<FName> ThreatTags = { TEXT("BirdThreat"), TEXT("BeeThreat") };
	/** Classes whose instances are threats (e.g. your NPC / animal base class). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Threats") TArray<TSoftClassPtr<AActor>> ThreatClasses;

	// ---- death
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") TArray<TSoftClassPtr<AActor>> LethalClasses;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") TArray<FName> LethalTags = { TEXT("BirdLethal"), TEXT("Spear"), TEXT("BodyflipProjectile") };
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") TArray<FString> LethalNameContains = { TEXT("Spear"), TEXT("Javelin"), TEXT("Arrow") };
	/** A lethal object must move at least this fast (cm/s) to kill (a spear lying on the ground does not). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") float LethalMinSpeed = 750.f;
	/** Unreal damage (ApplyDamage / ApplyPointDamage) at or above this kills; below it wounds (feathers + flee). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") float LethalDamage = 10.f;
	/** Physics impact on a live bird (kg cm/s) at or above this kills (thrown rock, falling crate...). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") float HeavyHitImpulse = 250.f;
	/** ... and only when the object moves at least this fast relative to the bird (cm/s): a slow push never kills. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") float HeavyHitMinSpeed = 300.f;
	/** Corpses are removed after this many seconds (0 = keep forever). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") float CorpseLifetime = 300.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Death") int32 MaxFeathers = 1500;
	/** Breeze that carries loose feathers (cm/s at 2 m above ground; 150 = a light 1.5 m/s sea breeze). A feather falls at only
	 *  0.2-1 m/s, so even a light breeze moves it metres before it lands - the main reason feathers scatter. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feathers") FVector Wind = FVector(150.f, 60.f, 0.f);
	/** Turbulence as a fraction of the wind speed (0.3-0.5 over a beach). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feathers") float WindGustiness = 0.45f;
	/** Take the direction from the level's Wind Directional Source (if any), keeping Wind's speed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feathers") bool bUseLevelWindDirection = true;

	// ---- feeding
	/** Fish caught by kingfishers (placeholder: the smoked fish until the real one; any static mesh works). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feeding") TSoftObjectPtr<UStaticMesh> FishMesh;
	/** Optional splash Niagara system spawned where a kingfisher hits the water (OnBirdPlunge fires either way). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feeding") TSoftObjectPtr<UNiagaraSystem> SplashSystem;
	/** Water is found automatically: actors tagged BirdWater, or flat meshes / actors whose mesh, class or name says
	 *  water / ocean / sea / lake. Add others with Add Bird Water. The top of the actor's bounds is the surface. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feeding") bool bAutoDetectWater = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Feeding") TArray<TObjectPtr<AActor>> WaterActors;
	UFUNCTION(BlueprintCallable, Category = "Birds") void AddWaterActor(AActor* Actor);
	/** True when P is above (or in) water; OutSurfaceZ = water level there. */
	bool IsWater(const FVector& P, float* OutSurfaceZ = nullptr, float Margin = 0.f) const;
	bool IsWaterActor(const AActor* A) const;
	/** A point over water near From (closest of a few random candidates within Range, at least Inset inside the edge). */
	bool PickWaterPoint(const FVector& From, float Range, float Inset, FRandomStream& Rng, FVector& Out) const;
	void RegisterFood(ABirdFish* Fish);
	/** Unclaimed remains nearest to P within Radius. */
	ABirdFish* FindFood(const FVector& P, float Radius) const;

	// ---- blood
	/** Spawn the project's blood splat Niagara system at a bleeding hit (its User.decal_callback is bound automatically to the
	 *  level's decal manager, so drops stain the ground / meshes exactly like the rest of the game's blood). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Blood") bool bBloodSplat = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Blood") TSoftObjectPtr<UNiagaraSystem> BloodSplatSystem;
	/** When bound, decides whether a hit bleeds (see Set Bird Bleed Condition). Unbound = DefaultShouldBleed. */
	UPROPERTY() FBirdBleedCondition BleedCondition;
	UFUNCTION(BlueprintCallable, Category = "Birds") void SetBleedCondition(FBirdBleedCondition Condition) { BleedCondition = Condition; }
	UFUNCTION(BlueprintCallable, Category = "Birds") void ClearBleedCondition() { BleedCondition.Clear(); }
	/** Placeholder rule until the real conditions exist: kills and hits by lethal objects (spear...) bleed; blunt wounds don't. */
	UFUNCTION(BlueprintPure, Category = "Birds") bool DefaultShouldBleed(const FBirdHitInfo& Hit) const;
	void SpawnBloodSplat(const FVector& At, const FVector& Dir, float ScaleMul);

	// ---- performance
	/** Birds farther than this (cm) from every player camera cast no shadow (a 30 cm bird's shadow is a few pixels there).
	 *  0 = always cast. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Performance") float ShadowDistance = 4500.f;
	/** Birds standing about farther than this (cm) update their bones at a reduced, interpolated rate (update-rate
	 *  optimisation; never in flight or while feeding). 0 = never. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Performance") float UpdateRateDistance = 2500.f;
	/** Idle perched birds farther than this (cm) from every player camera think at a reduced rate (0 = never). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Performance") float FarDistance = 6000.f;
	/** Far idle birds are simulated every Nth frame (with the summed time step). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Performance", meta = (ClampMin = "1", ClampMax = "8")) int32 FarTickInterval = 4;
	/** Actors looked at per frame by the background lethal / threat / water scan: the world is covered in slices instead of a
	 *  full sweep of every actor every half second (no hitch on big levels). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Birds|Performance", meta = (ClampMin = "16")) int32 ScanActorsPerFrame = 256;

	UFUNCTION(BlueprintCallable, Category = "Birds") void AddThreatActor(AActor* Actor);
	UFUNCTION(BlueprintCallable, Category = "Birds") void RemoveThreatActor(AActor* Actor);
	UFUNCTION(BlueprintCallable, Category = "Birds") void AddLethalClass(TSubclassOf<AActor> Class);
	UFUNCTION(BlueprintPure, Category = "Birds") FBirdFlockStats GetStats() const { return Stats; }
	UFUNCTION(BlueprintPure, Category = "Birds") TArray<ABird*> GetBirds() const;

	// ---- used by birds / zones
	void Register(ABird* Bird);
	void Unregister(ABird* Bird);
	const TArray<TObjectPtr<ABird>>& AllBirds() const { return Birds; }
	bool IsSpotFree(const ABird* Self, const FVector& Foot, float Radius) const;
	bool IsLethal(const AActor* Actor) const;
	/** Cheap check against the objects already found to be lethal (no tag / class / name tests). */
	bool IsKnownLethal(const AActor* Actor) const { return Actor && LethalSet.Contains(FObjectKey(Actor)); }
	void SpawnFeathers(const ABird* Bird, const FVector& At, const FVector& Dir, int32 Count, float Energy, const FVector* BaseVel = nullptr);
	/** Air velocity (cm/s) at a point: Wind (direction from the level's Wind Directional Source when there is one) slowed near
	 *  the ground (log boundary layer) plus turbulent gusts that differ from metre to metre. */
	FVector WindAt(const FVector& P, float HeightAboveGround, float Time) const;
	UPhysicsAsset* GetRagdollAsset(USkeletalMesh* Mesh, const FBirdSpeciesSettings& S);
	void StartleNear(const FVector& At, float Radius, const ABird* Except);
	void NotifyKill() { ++Stats.Kills; }
	const TArray<AActor*>& TraceIgnore() const { return IgnoreList; }

	struct FThreat
	{
		TWeakObjectPtr<AActor> Actor;
		FVector Pos = FVector::ZeroVector, PrevPos = FVector::ZeroVector, Vel = FVector::ZeroVector;
		float Speed = 0.f;
		bool bInit = false;
	};
	const TArray<FThreat>& GetThreats() const { return Threats; }

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;

private:
	UPROPERTY() TArray<TObjectPtr<ABird>> Birds;
	UPROPERTY() TArray<TObjectPtr<AActor>> IgnoreListHolder;
	TArray<AActor*> IgnoreList;
	TArray<FThreat> Threats;
	float ThreatScan = 0.f;

	struct FLethal
	{
		TWeakObjectPtr<AActor> Actor;
		FVector Tip = FVector::ZeroVector, Tail = FVector::ZeroVector, PrevTip = FVector::ZeroVector, PrevTail = FVector::ZeroVector;
		FVector Vel = FVector::ZeroVector;
		// the shaft: biggest visible primitive and its long axis in local space (re-found every second, not every frame)
		TWeakObjectPtr<UPrimitiveComponent> Shape;
		FVector LocalOrigin = FVector::ZeroVector, LocalAxis = FVector::ZeroVector;
		float Radius = 0.f, Refind = 0.f;
		bool bInit = false;
	};
	TArray<FLethal> Lethals;
	TSet<FObjectKey> LethalSet;
	void AddLethal(AActor* A);
	TArray<TPair<TWeakObjectPtr<AActor>, float>> Fresh;
	FDelegateHandle SpawnHandle;
	void OnAnyActorSpawned(AActor* A);
	// background scan: a cursor through every level's actor list, ScanActorsPerFrame actors per frame
	int32 ScanLevelIdx = 0, ScanActorIdx = 0;
	double ScanCycleStart = 0.0;
	TSet<FObjectKey> WaterChecked;
	mutable TMap<FObjectKey, uint8> ClassFlags;		// per class: 1 = lethal class / name, 2 = threat class
	uint8 GetClassFlags(const UClass* C) const;
	void ConsiderActor(AActor* A, bool bWaterCheck);
	bool LooksLikeWater(AActor* A) const;
	void ScanSlice();
	void ScanLethals();
	void UpdateLethals(float Dt);
	void GatherThreats(float Dt);
	void EnforceSeparation(float FixedDt);

	UPROPERTY() TMap<TObjectPtr<USkeletalMesh>, TObjectPtr<UPhysicsAsset>> Ragdolls;
	TMap<TObjectPtr<UMaterialInterface>, FBirdFeatherPool> Pools;
	UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> PoolComponents;
	FBirdFeatherPool* GetPool(UMaterialInterface* Mat);
	FVector WindNow = FVector::ZeroVector;
	struct FWater { TWeakObjectPtr<AActor> Actor; FBox Box; };
	TArray<FWater> Waters;
	void ScanWater();
	// player cameras (for the distance tiers), refreshed every frame
	TArray<FVector> Cameras;
	void GatherCameras();
	float CameraDistSq(const FVector& P) const;
	int32 TierCursor = 0;
	void UpdateTiers();
	TArray<TWeakObjectPtr<ABirdFish>> Foods;
	float WindCheck = 0.f;
	void UpdateFeathers(float Dt);

	FBirdFlockStats Stats;
	double TickMsSum = 0.0;
	double PartMs[6] = { 0, 0, 0, 0, 0, 0 };
	int32 TickSamples = 0;
	float StatsWindow = 0.f;
};
