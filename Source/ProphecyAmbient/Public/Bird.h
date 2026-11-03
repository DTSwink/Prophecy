#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BirdTypes.h"
#include "Bird.generated.h"

class USkeletalMeshComponent;
class UBirdAnimInstance;
class ABirdFlock;
class ABirdZone;
class UMaterialInstanceDynamic;
class UPrimitiveComponent;
class ABirdFish;
class USphereComponent;
class UPhysicsAsset;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdCry, ABird*, Bird, float, Duration);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdDied, ABird*, Bird, AActor*, Killer);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdStateChanged, ABird*, Bird, EBirdState, NewState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdHit, const FBirdHitInfo&, Hit, bool, bBled);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdPlunge, ABird*, Bird, FVector, WaterLocation);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBirdFish, ABird*, Bird, ABirdFish*, Fish);

/**
 * One ambient bird (gull or kingfisher). Spawned and simulated by its ABirdZone / the world's ABirdFlock; it does not tick
 * on its own. Actor location = body centre.
 *
 * Voice: call Cry (or let Ambient Cries do it) and bind OnBirdCry to play the sound - the beak opens for the duration.
 * Death: ApplyDamage >= the flock's LethalDamage, a hit by a lethal object (spear by default: class, tag or name), a heavy
 * physics impact, or Kill(). The bird becomes a ragdoll (runtime physics asset with realistic mass) and bursts feathers.
 */
UCLASS(NotPlaceable, meta = (DisplayName = "Bird"))
class PROPHECYAMBIENT_API ABird : public AActor
{
	GENERATED_BODY()

public:
	ABird();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bird") TObjectPtr<USceneComponent> Root;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bird") TObjectPtr<USkeletalMeshComponent> Mesh;
	/** Collision of the live bird (one sphere instead of a dozen kinematic ragdoll bodies dragged along every frame); the
	 *  mesh gets its physics bodies only when the bird dies. Hits on it are handled like hits on the mesh were. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Bird") TObjectPtr<USphereComponent> Body;

	/** Fired when the bird calls (ambient cry or Cry node). Play your gull / kingfisher SFX here (attach to Mesh, socket "head"). */
	UPROPERTY(BlueprintAssignable, Category = "Bird") FOnBirdCry OnBirdCry;
	UPROPERTY(BlueprintAssignable, Category = "Bird") FOnBirdDied OnBirdDied;
	UPROPERTY(BlueprintAssignable, Category = "Bird") FOnBirdStateChanged OnBirdStateChanged;
	/** Every kill / wound, with the full hit description and whether it bled (blood SFX, gameplay...). */
	UPROPERTY(BlueprintAssignable, Category = "Bird") FOnBirdHit OnBirdHit;
	/** Kingfisher hits the water (splash SFX / VFX here). */
	UPROPERTY(BlueprintAssignable, Category = "Bird|Feeding") FOnBirdPlunge OnBirdPlunge;
	/** Came out of the water with a fish. */
	UPROPERTY(BlueprintAssignable, Category = "Bird|Feeding") FOnBirdFish OnBirdCaughtFish;
	/** Kingfisher finished eating and left the remains. */
	UPROPERTY(BlueprintAssignable, Category = "Bird|Feeding") FOnBirdFish OnBirdLeftRemains;
	/** Gull swallowed the remains (the fish actor is destroyed right after). */
	UPROPERTY(BlueprintAssignable, Category = "Bird|Feeding") FOnBirdFish OnBirdSwallowed;

	/** Kingfisher: go fishing now (water within Fishing Range needed). Returns false when there is no water / not possible. */
	UFUNCTION(BlueprintCallable, Category = "Bird|Feeding") bool GoFishing();
	UFUNCTION(BlueprintPure, Category = "Bird|Feeding") EBirdTask GetTask() const { return Task; }
	UFUNCTION(BlueprintPure, Category = "Bird|Feeding") ABirdFish* GetFish() const { return HeldFish; }

	/** Open the beak for Duration seconds (and fire OnBirdCry). Openness 0..1. Gulls also throw the head back on long calls. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void Cry(float Duration = 0.9f, float Openness = 1.f);
	/** Hold the beak at a fixed openness (0..1), e.g. to sync with your own audio envelope. Negative = release to automatic. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void SetBeakOpen(float Openness);
	/** Kill now: ragdoll + feather burst. Impulse = velocity change (cm/s) given to the hit bone. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void Kill(FVector HitLocation, FVector Impulse, AActor* Killer = nullptr, FName Bone = NAME_None);
	/** Non-lethal hit: a few feathers and the bird flees. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void Wound(FVector HitLocation, FVector Direction, AActor* HitBy = nullptr);
	/** Makes the bird take off / flee away from a point. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void Startle(FVector From);
	/** Blood stain on the plumage at a world point (follows the body, survives the ragdoll; the 4 most recent stains are kept).
	 *  RadiusCm <= 0 uses the species default. bSplat also spawns the blood splat Niagara system there. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void AddBloodStain(FVector WorldLocation, FVector Direction, float RadiusCm = 0.f, bool bSplat = true, FName Bone = NAME_None);
	UFUNCTION(BlueprintCallable, Category = "Bird") void ClearBloodStains();
	/** Recolour (brown / white for the kingfisher). Ignored for species that are not recolourable unless bForce. */
	UFUNCTION(BlueprintCallable, Category = "Bird") void SetColours(FLinearColor InPrimary, FLinearColor InSecondary, bool bForce = false);

	UFUNCTION(BlueprintPure, Category = "Bird") EBirdState GetState() const { return State; }
	UFUNCTION(BlueprintPure, Category = "Bird") EBirdSpecies GetSpecies() const { return Species; }
	UFUNCTION(BlueprintPure, Category = "Bird") bool IsDead() const { return State == EBirdState::Dead; }
	UFUNCTION(BlueprintPure, Category = "Bird") bool IsFlying() const { return State == EBirdState::Flying || State == EBirdState::TakingOff || State == EBirdState::Landing; }
	UFUNCTION(BlueprintPure, Category = "Bird") FVector GetBirdVelocity() const { return Vel; }

	virtual float TakeDamage(float Damage, struct FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser) override;

	// ------------------------------------------------------------------------------------------------ simulation (flock)
	void Setup(ABirdFlock* InFlock, ABirdZone* InZone, EBirdSpecies InSpecies, const FBirdSpeciesSettings& InSettings, float InScale, uint32 Seed);
	void ApplyColours();
	void PlacePerched(const FVector& Foot, const FVector& Normal, float Yaw);
	void PlaceFlying(const FVector& Centre, const FVector& Velocity);
	bool PlaceOnRandomSpot(const FVector& Start);
	void Simulate(float Dt);
	void PushVisuals(float Dt);
	void ProbeImpacts(float Dt);
	void PushApart(const FVector& Delta, bool bKillApproach);
	float SeparationRadius() const;	// sphere radius used for the no-overlap rule
	FVector GetFootSpot() const { return bHasSpot ? Spot : (Pos - FVector::UpVector * BodyH()); }
	bool HasReservedSpot() const { return bHasSpot; }
	FVector GetReservedSpot() const { return Spot; }
	FVector GetPos() const { return Pos; }
	float BodyH() const { return S.BodyHeight * Scale; }
	float BodyR() const { return S.BodyRadius * Scale; }
	const FBirdSpeciesSettings& Settings() const { return S; }
	float GetScale() const { return Scale; }
	FLinearColor GetPrimary() const { return Primary; }
	FLinearColor GetSecondary() const { return Secondary; }
	bool bTintActive = false;
	/** Describes the hit that the next Kill / Wound call (this frame) belongs to; filled by the flock's detection paths. */
	void SetHitContext(const FBirdHitInfo& Hit) { PendingHit = Hit; bPendingHit = true; }
	/** Frames of impact-probe logging (test / debugging). */
	int32 ProbeDebugFrames = 0;

	// distance tiers (decided by the flock from the player cameras)
	bool bFar = false;
	bool bMid = false;			// beyond the flock's UpdateRateDistance
	bool bShadowOn = true;
	float FarDt = 0.f;			// time not yet simulated while thinking at the far rate
	void SetShadowCasting(bool bOn);
	/** Idle on the ground with nothing in the bill: safe to simulate at a reduced rate. */
	bool CanThinkSlowly() const;

	// stats
	int32 Takeoffs = 0, Landings = 0, Walks = 0, Cries = 0, AbortedLandings = 0, Scrapes = 0, Turns = 0, Shuffles = 0, Bleeds = 0;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
	UPROPERTY() TObjectPtr<ABirdFlock> Flock;
	TWeakObjectPtr<ABirdZone> Zone;
	UPROPERTY() TObjectPtr<UBirdAnimInstance> Anim;
	UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> Mids;
	FBirdSpeciesSettings S;
	EBirdSpecies Species = EBirdSpecies::Gull;
	float Scale = 1.f;
	FRandomStream Rng;
	FLinearColor Primary = FLinearColor::White, Secondary = FLinearColor::White;

	EBirdState State = EBirdState::Unplaced;
	float StateTime = 0.f;
	float Timer = 0.f;		// time left in the current perch / flight bout
	FVector Pos = FVector::ZeroVector, Vel = FVector::ZeroVector;
	float Yaw = 0.f, Pitch = 0.f, Bank = 0.f, Gamma = 0.f;	// heading yaw, visual pitch, roll (deg), flight-path angle (deg)
	float Speed = 0.f;
	FVector Waypoint = FVector::ZeroVector;
	// landing spot (feet position) + approach
	bool bHasSpot = false;
	FVector Spot = FVector::ZeroVector, SpotNormal = FVector::UpVector;
	FVector ApproachDir = FVector::ForwardVector;
	bool bFinal = false;
	float SpotSearchCooldown = 0.f;
	// threat / flee
	bool bFleeing = false;
	FVector FleeFrom = FVector::ZeroVector;
	float ThreatCheck = 0.f;
	// sensing caches
	float GroundZ = -1e9f, GroundCheck = 0.f;
	FVector AvoidDir = FVector::ZeroVector;
	float AvoidCheck = 0.f, AvoidTime = 0.f;
	// flapping
	float FlapPhase = 0.f, FlapW = 0.f, HoverW = 0.f, FlightW = 0.f, BoutTime = 0.f;
	bool bGlideBout = false;
	// walking + idle life
	FVector WalkTarget = FVector::ZeroVector;
	float WalkW = 0.f, WalkPhase = 0.f, WalkSpeedCur = 0.f;
	float IdleTimer = 0.f, TurnTarget = 0.f, TimerBeforeWalk = 0.f;
	bool bTurning = false, bShuffle = false;
	// wingbeat variation
	float FlapMul = 1.f, FlapT = 0.f, FlapSeedA = 0.f, FlapSeedB = 0.f, FlapAmp = 1.f, FlapAmpNext = 1.f, LastFlapFrac = 0.f;
	float FlapRate() const;
	// body motion within the wingbeat (normalised tables, see BuildStrokeTables) + gust response
	static constexpr int32 StrokeN = 32;
	float HeaveTab[StrokeN] = {}, SurgeTab[StrokeN] = {}, PitchTab[StrokeN] = {};
	float TurbA = 0.f, TurbB = 0.f, TurbC = 0.f;
	bool bMeshOffset = false;
	FVector PushedPos = FVector(1e30);	// last transform given to the actor (unchanged -> no move, no transform propagation)
	FQuat PushedQ = FQuat::Identity;
	bool bUROOn = false;
	UPROPERTY() TObjectPtr<UPhysicsAsset> Ragdoll;
	void BuildStrokeTables();
	// voice
	float FlightCryMul = 0.7f;
	// blood
	FLinearColor BloodStains[4];
	int32 NextStain = 0;
	FBirdHitInfo PendingHit;
	// ---- feeding
	EBirdTask Task = EBirdTask::None;
	UPROPERTY() TObjectPtr<ABirdFish> HeldFish;
	TWeakObjectPtr<ABirdFish> FoodTarget;
	FVector HuntPoint = FVector::ZeroVector, FoodApproach = FVector::ZeroVector;
	float HuntHeight = 400.f, WaterZ = 0.f, TaskT = 0.f, TaskDur = 1.f, FishingTimer = 30.f, ScavengeScan = 1.f;
	int32 PeckLeft = 0, PeckTotal = 0, Dives = 0, ScavengeTries = 0, HoverMoves = 0;
	float DiveStartZ = 0.f;
	bool bDirectDive = false;
	bool bLeaveAfterMeal = false, bFishDropped = false;
	float FoldW = 0.f, TaskPitch = 0.f;
	bool bTaskLook = false;
	float TaskLookPitch = 0.f, TaskLookYaw = 0.f, TaskLookRate = 14.f;
	FVector2D FishSwing = FVector2D::ZeroVector;
	int32 HeadIdx = INDEX_NONE;
	FVector BillInHead = FVector::ZeroVector, BillDirInHead = FVector::ForwardVector, LatInHead = FVector::RightVector, UpInHead = FVector::UpVector;
	void CacheBill();
	FVector BillPoint(float Along) const;		// world point along the bill (0 gape .. 1 tip)
	FVector BillDir() const;
	FVector HeadLat() const;
	FVector HeadUp() const;
	bool UpdateAirTask(float Dt);			// true = movement handled (hover / dive / under water / emerge)
	bool UpdatePerchedTask(float Dt);		// true = the frame is taken by feeding
	bool TryScavenge();
	bool StartWalkTo(const FVector& TargetFoot);
	void Plunge();
	void DropFish(bool bAsRemains);
	void PlaceHeldFish();
	void EndTask();
	float FishTrip = 0.f;
	bool bPendingHit = false;
	FBirdHitInfo MakeHitInfo(const FVector& Location, const FVector& Dir, AActor* Object, FName Bone, bool bLethal);
	void ResolveBleed(FBirdHitInfo& Hit);
	// settle after touchdown
	float SettleT = 1.f;
	FVector SettleFrom = FVector::ZeroVector, SettleVel = FVector::ZeroVector;
	float SettlePitch = 0.f, SettleBank = 0.f;
	// voice + look
	float CryLeft = 0.f, CryOpen = 1.f, CryTotal = 1.f, NextCry = 0.f, BeakHold = -1.f, Beak = 0.f;
	float LookYaw = 0.f, LookPitch = 0.f, LookYawT = 0.f, LookPitchT = 0.f, NextLook = 0.f;
	float LastHitTime = -10.f;
	float DeathZ = 0.f;
	// feathers keep coming loose while the body falls and when it hits the ground
	int32 ShedLeft = 0, ShedTotal = 0, GroundBursts = 0;
	float DeadT = 0.f, PrevCorpseVz = 0.f, CorpseStillT = 0.f;
	bool bCulled = false;
	TMap<TWeakObjectPtr<UPrimitiveComponent>, FVector> NearbyVel;	// physics objects near the bird last frame: velocity ...
	TMap<TWeakObjectPtr<UPrimitiveComponent>, FVector> NearbyPos;	// ... and bounds centre (impact detection)

	void SetState(EBirdState NewState);
	void UpdatePerched(float Dt);
	void UpdateWalking(float Dt);
	void UpdateAir(float Dt);
	void UpdateLook(float Dt);
	void UpdateVoice(float Dt);
	void StartFlight(bool bFlee);
	bool TryStartWalk(float MinDist = 50.f, float MaxDist = 260.f);
	bool ChooseSpot();
	friend class ABirdTestDirector;
	void ReleaseSpot() { bHasSpot = false; bFinal = false; }
	FVector PickWaypoint();
	void SenseGround();
	void SenseObstacles();
	bool CheckThreats();
	FVector Separation() const;
	void Touchdown();
	void BankedFlight(float Dt, const FVector& DesiredDir, float TargetSpeed, bool bAllowGlide);
	void HoverFlight(float Dt, const FVector& TargetVel, float Accel);
	float Rand(const FVector2D& R) { return Rng.FRandRange(R.X, R.Y); }

	UFUNCTION() void OnMeshHit(UPrimitiveComponent* HitComp, AActor* Other, UPrimitiveComponent* OtherComp, FVector NormalImpulse, const FHitResult& Hit);
};
