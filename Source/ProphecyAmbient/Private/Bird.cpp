#include "Bird.h"
#include "BirdFish.h"
#include "BirdFlock.h"
#include "BirdZone.h"
#include "BirdAnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/SphereComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Engine/DamageEvents.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "CollisionQueryParams.h"
#include "Engine/OverlapResult.h"
#include "GameFramework/Pawn.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "ReferenceSkeleton.h"

static TAutoConsoleVariable<int32> CVarBirdDebug(TEXT("birds.Debug"), 0, TEXT("1 = draw bird spots, approach and separation radii"));
static TAutoConsoleVariable<int32> CVarBirdBlood(TEXT("birds.Blood"), 1, TEXT("0 = birds never bleed, 1 = bleed when the bleed condition says so, 2 = every kill / wound bleeds"));

namespace
{
	const TCHAR* BirdRoot = TEXT("/Game/Prophecy/Creatures/Birds");
	constexpr float G = 980.f;

	float Approach(float Cur, float Target, float MaxStep)
	{
		return Cur + FMath::Clamp(Target - Cur, -MaxStep, MaxStep);
	}
	float ApproachAngle(float Cur, float Target, float MaxStep)
	{
		return Cur + FMath::Clamp(FMath::FindDeltaAngleDegrees(Cur, Target), -MaxStep, MaxStep);
	}
	float SmoothStep01(float A, float B, float X)
	{
		const float T = FMath::Clamp((X - A) / FMath::Max(B - A, 1e-4f), 0.f, 1.f);
		return T * T * (3.f - 2.f * T);
	}
	FVector Horizontal(const FVector& V) { return FVector(V.X, V.Y, 0.f); }
}

FBirdSpeciesSettings FBirdSpeciesSettings::Defaults(EBirdSpecies Species)
{
	FBirdSpeciesSettings S;
	const FString Name = Species == EBirdSpecies::Gull ? TEXT("Gull") : TEXT("Kingfisher");
	const FString Dir = FString::Printf(TEXT("%s/%s"), BirdRoot, *Name);
	auto Anim = [&](const TCHAR* Clip) { return TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(FString::Printf(TEXT("%s/A_%s_%s.A_%s_%s"), *Dir, *Name, Clip, *Name, Clip))); };
	S.Mesh = TSoftObjectPtr<USkeletalMesh>(FSoftObjectPath(FString::Printf(TEXT("%s/SK_%s.SK_%s"), *Dir, *Name, *Name)));
	S.AnimPerch = Anim(TEXT("Perch"));
	S.AnimWalk = Anim(TEXT("Walk"));
	S.AnimGlide = Anim(TEXT("Glide"));
	S.AnimFlap = Anim(TEXT("Flap"));
	S.AnimHover = Anim(TEXT("Hover"));
	S.FeatherFXMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(FString::Printf(TEXT("%s/MI_%s_FeatherFX.MI_%s_FeatherFX"), *Dir, *Name, *Name)));
	if (Species == EBirdSpecies::Gull) S.bScavenges = true;
	if (Species == EBirdSpecies::Kingfisher)
	{
		S.BodyHeight = 6.2f; S.BodyRadius = 5.f; S.HalfSpan = 19.f; S.MassKg = 0.085f;
		S.CruiseSpeed = 800.f; S.MinSpeed = 260.f; S.MaxSpeed = 1300.f; S.MaxBankDeg = 65.f; S.RollRateDeg = 320.f;
		S.MaxClimbDeg = 35.f; S.PitchRateDeg = 120.f; S.FlapHz = 10.f; S.GlideFraction = 0.12f; S.GlideSink = 160.f;
		S.CruiseHeight = FVector2D(150.f, 600.f); S.Acceleration = 700.f;
		S.WalkSpeed = 8.f; S.StrideCm = 3.3f; S.WalkChance = 0.15f; S.PerchHeightPreference = 0.9f;
		S.PerchTime = FVector2D(6.f, 28.f); S.FlightTime = FVector2D(3.f, 10.f);
		S.IdleActionTime = FVector2D(1.8f, 5.5f); S.ShuffleChance = 0.35f; S.ShuffleDistance = FVector2D(3.5f, 9.f);
		S.TurnRateDeg = 260.f; S.TurnDegPerStepCycle = 90.f; S.FlapHzVariation = 0.15f;
		S.UpstrokeLift = 0.1f; S.StrokePitchDeg = 0.8f; S.GustRollDeg = 1.2f; S.GustHeaveCm = 0.4f;	// torso ~10x steadier than the wings
		S.BloodStainRadius = 1.8f; S.BloodVFXScale = 0.18f;
		S.bFishes = true; S.bScavenges = false; S.BillBase = FVector(7.2f, 0.f, 9.85f); S.BillLength = 6.f;
		S.ThreatRadius = 500.f; S.PanicRadius = 180.f;
		S.BeakOpenDeg = 28.f; S.CryInterval = FVector2D(8.f, 30.f); S.CryDuration = FVector2D(0.3f, 1.1f);
		S.DeathFeathers = 45; S.HitFeathers = 6; S.FeatherSize = 2.6f;
		S.FeatherPrimary = FLinearColor(0.36f, 0.13f, 0.05f); S.FeatherSecondary = FLinearColor(0.95f, 0.94f, 0.92f);
		S.DarkFeatherFraction = 0.75f; S.bRecolourable = true;
	}
	return S;
}

// =====================================================================================================================
ABird::ABird()
{
	PrimaryActorTick.bCanEverTick = false;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Root->SetMobility(EComponentMobility::Movable);
	Body = CreateDefaultSubobject<USphereComponent>(TEXT("Body"));
	Body->SetupAttachment(Root);
	Body->InitSphereRadius(10.f);
	Body->SetCollisionObjectType(ECC_WorldDynamic);
	Body->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Body->SetCollisionResponseToAllChannels(ECR_Block);
	Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Body->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	Body->SetGenerateOverlapEvents(false);
	Body->SetNotifyRigidBodyCollision(true);
	Body->SetCanEverAffectNavigation(false);
	Body->SetHiddenInGame(true);
	Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	// no collision (so no physics bodies) while alive: the Body sphere and the flock's probes do the hit detection.
	// Kill() gives the mesh its ragdoll.
	Mesh->SetCollisionObjectType(ECC_PhysicsBody);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetGenerateOverlapEvents(false);
	Mesh->SetNotifyRigidBodyCollision(false);
	// bones are evaluated only when the bird is on screen (or its shadow is); far birds standing still update at a lower
	// rate (update-rate optimisation, switched off in flight so wingbeats are never decimated)
	Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPose;
	Mesh->bEnableUpdateRateOptimizations = false;
	Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
	Mesh->bCastDynamicShadow = true;
	// bounds from the mesh asset (bind pose = wings spread, covers every pose) instead of the ragdoll bodies: with the
	// smaller body-based bounds, wing / tail feathers poked outside them and their cached shadows were never cleared
	// (the dark feather marks left on the ground)
	Mesh->bComponentUseFixedSkelBounds = true;
	Mesh->SetBoundsScale(1.2f);
	Mesh->SetCanEverAffectNavigation(false);
}

void ABird::BeginPlay()
{
	Super::BeginPlay();
	Body->OnComponentHit.AddDynamic(this, &ABird::OnMeshHit);
}

void ABird::EndPlay(const EEndPlayReason::Type Reason)
{
	if (Flock) Flock->Unregister(this);
	Super::EndPlay(Reason);
}

void ABird::Setup(ABirdFlock* InFlock, ABirdZone* InZone, EBirdSpecies InSpecies, const FBirdSpeciesSettings& InSettings, float InScale, uint32 InSeed)
{
	Flock = InFlock;
	Zone = InZone;
	Species = InSpecies;
	S = InSettings;
	Scale = InScale;
	Rng.Initialize(int32(InSeed));
	NextCry = Rand(S.CryInterval) * Rng.FRandRange(0.2f, 1.f);
	BoutTime = Rng.FRandRange(0.f, 3.f);
	FlapMul = 1.f + Rng.FRandRange(-1.f, 1.f) * S.FlapHzVariation;
	FlapSeedA = Rng.FRandRange(0.f, 6.283f);
	FlapSeedB = Rng.FRandRange(0.f, 6.283f);
	FlapPhase = Rng.FRand();
	IdleTimer = Rand(S.IdleActionTime);
	for (FLinearColor& St : BloodStains) St = FLinearColor(0, 0, 0, 0);
	TurbA = Rng.FRandRange(0.f, 6.283f); TurbB = Rng.FRandRange(0.f, 6.283f); TurbC = Rng.FRandRange(0.f, 6.283f);
	BuildStrokeTables();

	USkeletalMesh* SK = S.Mesh.LoadSynchronous();
	if (SK)
	{
		Mesh->SetSkeletalMeshAsset(SK);
		Mesh->SetAnimInstanceClass(UBirdAnimInstance::StaticClass());
		Anim = Cast<UBirdAnimInstance>(Mesh->GetAnimInstance());
		if (Anim)
		{
			Anim->SetClips(S.AnimPerch.LoadSynchronous(), S.AnimWalk.LoadSynchronous(), S.AnimGlide.LoadSynchronous(),
				S.AnimFlap.LoadSynchronous(), S.AnimHover.LoadSynchronous());
		}
		if (Flock) Ragdoll = Flock->GetRagdollAsset(SK, S);		// assigned at death
		else Ragdoll = nullptr;
		Mids.Reset();
		for (int32 i = 0; i < Mesh->GetNumMaterials(); ++i) Mids.Add(Mesh->CreateDynamicMaterialInstance(i));
		CacheBill();
	}
	FishingTimer = Rand(S.FishingInterval) * Rng.FRandRange(0.3f, 1.f);
	ScavengeScan = Rng.FRandRange(0.5f, 2.f);
	Mesh->SetRelativeScale3D(FVector(Scale));
	Mesh->SetRelativeLocation(FVector(0.f, 0.f, -BodyH()));
	Body->SetSphereRadius(BodyR() * 1.15f);
	PushedPos = FVector(1e30);
	if (Flock) Flock->Register(this);
}

void ABird::SetColours(FLinearColor InPrimary, FLinearColor InSecondary, bool bForce)
{
	Primary = InPrimary;
	Secondary = InSecondary;
	bTintActive = S.bRecolourable || bForce;
	ApplyColours();
}

void ABird::ApplyColours()
{
	for (UMaterialInstanceDynamic* M : Mids)
	{
		if (!M) continue;
		M->SetVectorParameterValue(TEXT("PrimaryColour"), Primary);
		M->SetVectorParameterValue(TEXT("SecondaryColour"), Secondary);
		M->SetScalarParameterValue(TEXT("TintStrength"), bTintActive ? 1.f : 0.f);
	}
}

float ABird::SeparationRadius() const
{
	if (State == EBirdState::Perched || State == EBirdState::Walking || State == EBirdState::Unplaced) return BodyR() * 1.05f;
	// wings raised in the braking / take-off stroke take less room than a full glide span
	return FMath::Lerp(S.HalfSpan * Scale, S.HalfSpan * Scale * 0.7f, HoverW);
}

void ABird::BuildStrokeTables()
{
	// Vertical force over one wingbeat (units of body weight): downstroke 55 % of the cycle with a sine lift pulse, a weaker
	// pulse in the upstroke, scaled so the cycle mean = 1 (level flight). Net acceleration (lift - weight) and the forward thrust
	// pulse (peaking later in the downstroke, as measured in birds) are double-integrated with their first harmonics -> the
	// periodic displacement of the body in units of g / f^2. Pitch: lift x fore/aft sweep of the wing (forward in the downstroke).
	constexpr int32 N = StrokeN;
	const float R = FMath::Clamp(S.UpstrokeLift, 0.f, 1.f);
	const float C = PI / (2.f * (0.55f + 0.45f * R));
	float A[N], AX[N], M[N];
	float MeanT = 0.f, MeanM = 0.f;
	for (int32 j = 0; j < N; ++j)
	{
		const float P = float(j) / N;
		const float L = P < 0.55f ? C * FMath::Sin(PI * P / 0.55f) : R * C * FMath::Sin(PI * (P - 0.55f) / 0.45f);
		A[j] = L - 1.f;
		AX[j] = (P >= 0.08f && P < 0.63f) ? 0.25f * C * FMath::Sin(PI * (P - 0.08f) / 0.55f) : 0.f;
		const float Th = P < 0.55f ? PI * P / 0.55f : PI + PI * (P - 0.55f) / 0.45f;
		M[j] = L * FMath::Sin(Th);
		MeanT += AX[j] / N;
		MeanM += M[j] / N;
	}
	for (int32 j = 0; j < N; ++j) { AX[j] -= MeanT; M[j] -= MeanM; }
	auto Integrate = [](const float* In, float* Out)
	{
		for (int32 j = 0; j < N; ++j) Out[j] = 0.f;
		for (int32 k = 1; k <= 6; ++k)
		{
			float Re = 0.f, Im = 0.f;
			for (int32 j = 0; j < N; ++j)
			{
				const float Ang = 2.f * PI * k * j / N;
				Re += In[j] * FMath::Cos(Ang) / N;
				Im -= In[j] * FMath::Sin(Ang) / N;
			}
			const float W2 = FMath::Square(2.f * PI * k);
			for (int32 j = 0; j < N; ++j)
			{
				const float Ang = 2.f * PI * k * j / N;
				Out[j] -= 2.f * (Re * FMath::Cos(Ang) - Im * FMath::Sin(Ang)) / W2;
			}
		}
	};
	Integrate(A, HeaveTab);
	Integrate(AX, SurgeTab);
	Integrate(M, PitchTab);
	float MaxP = 1e-6f;
	for (int32 j = 0; j < N; ++j) MaxP = FMath::Max(MaxP, FMath::Abs(PitchTab[j]));
	for (int32 j = 0; j < N; ++j) PitchTab[j] /= MaxP;
}

float ABird::FlapRate() const
{
	// own rate + slow wander (two incommensurate sines): the sampled wing angles drift instead of repeating
	const float W = 1.f + S.FlapHzVariation * (0.35f * FMath::Sin(FlapT * 1.13f + FlapSeedA) + 0.12f * FMath::Sin(FlapT * 2.71f + FlapSeedB));
	return S.FlapHz * FlapMul * W;
}

void ABird::SetState(EBirdState NewState)
{
	if (State == NewState) return;
	bTurning = false;
	State = NewState;
	StateTime = 0.f;
	OnBirdStateChanged.Broadcast(this, NewState);
}

void ABird::PlacePerched(const FVector& Foot, const FVector& Normal, float InYaw)
{
	Spot = Foot;
	SpotNormal = Normal;
	bHasSpot = true;
	Pos = Foot + FVector::UpVector * BodyH();
	Vel = FVector::ZeroVector;
	Speed = 0.f;
	Yaw = InYaw;
	Pitch = Bank = Gamma = 0.f;
	FlightW = FlapW = HoverW = 0.f;
	SettleT = 1.f;
	Timer = Rand(S.PerchTime);
	SetState(EBirdState::Perched);
	SetActorLocationAndRotation(Pos, FRotator(0.f, Yaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	PushedPos = FVector(1e30);
}

void ABird::PlaceFlying(const FVector& Centre, const FVector& Velocity)
{
	Pos = Centre;
	Vel = Velocity;
	Speed = Vel.Size();
	Yaw = Vel.Rotation().Yaw;
	Gamma = Vel.Rotation().Pitch;
	FlightW = 1.f;
	FlapW = 1.f;
	ReleaseSpot();
	Timer = Rand(S.FlightTime);
	Waypoint = PickWaypoint();
	SetState(EBirdState::Flying);
	SetActorLocationAndRotation(Pos, FRotator(Gamma * 0.6f, Yaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	PushedPos = FVector(1e30);
}

bool ABird::PlaceOnRandomSpot(const FVector& Start)
{
	Pos = Start;
	GroundZ = Start.Z - 20000.f;
	if (!ChooseSpot()) return false;
	PlacePerched(Spot, SpotNormal, Rng.FRandRange(0.f, 360.f));
	return true;
}

// ---------------------------------------------------------------------------------------------------- voice / look
void ABird::Cry(float Duration, float Openness)
{
	if (State == EBirdState::Dead || State == EBirdState::Unplaced) return;
	CryTotal = CryLeft = FMath::Max(Duration, 0.1f);
	CryOpen = FMath::Clamp(Openness, 0.f, 1.f);
	++Cries;
	OnBirdCry.Broadcast(this, Duration);
	if (ABirdZone* Z = Zone.Get()) Z->HandleBirdCry(this, Duration);
}

void ABird::SetBeakOpen(float Openness)
{
	BeakHold = Openness < 0.f ? -1.f : FMath::Clamp(Openness, 0.f, 1.f);
}

void ABird::UpdateVoice(float Dt)
{
	if (const ABirdZone* Z = Zone.Get())
	{
		if (Z->bAmbientCries)
		{
			NextCry -= Dt;
			if (NextCry <= 0.f)
			{
				NextCry = Rand(S.CryInterval) * (IsFlying() ? FlightCryMul : 1.f);
				Cry(Rand(S.CryDuration), Rng.FRandRange(0.7f, 1.f));
			}
		}
	}
	float Target = 0.f;
	if (BeakHold >= 0.f)
	{
		Target = BeakHold;
	}
	else if (CryLeft > 0.f)
	{
		CryLeft -= Dt;
		const float T = CryTotal - CryLeft;
		// quick open, syllable flutter, close over the last 0.1 s
		const float Env = SmoothStep01(0.f, 0.07f, T) * SmoothStep01(0.f, 0.1f, CryLeft);
		Target = CryOpen * Env * (0.78f + 0.22f * FMath::Sin(T * 17.f + 1.3f));
	}
	Beak = Approach(Beak, Target, Dt * 14.f);
}

void ABird::UpdateLook(float Dt)
{
	if (bTaskLook)
	{
		LookYaw = FMath::FInterpTo(LookYaw, TaskLookYaw, Dt, TaskLookRate);
		LookPitch = FMath::FInterpTo(LookPitch, TaskLookPitch, Dt, TaskLookRate);
		return;
	}
	NextLook -= Dt;
	const bool bGround = State == EBirdState::Perched || State == EBirdState::Walking;
	if (NextLook <= 0.f)
	{
		NextLook = bGround ? Rng.FRandRange(0.6f, 3.5f) : Rng.FRandRange(1.5f, 4.f);
		if (bGround)
		{
			LookYawT = Rng.FRand() < 0.3f ? 0.f : Rng.FRandRange(-85.f, 85.f);
			LookPitchT = Rng.FRandRange(-12.f, 14.f);
			// keep an eye on the closest threat
			if (Flock)
			{
				float Best = FMath::Square(S.ThreatRadius * 2.f);
				for (const ABirdFlock::FThreat& T : Flock->GetThreats())
				{
					const float D2 = FVector::DistSquared(T.Pos, Pos);
					if (D2 < Best)
					{
						Best = D2;
						LookYawT = FMath::Clamp(FMath::FindDeltaAngleDegrees(Yaw, (T.Pos - Pos).Rotation().Yaw), -100.f, 100.f);
					}
				}
			}
		}
		else
		{
			LookYawT = FMath::Clamp(Bank * 0.4f, -25.f, 25.f);
			LookPitchT = 0.f;
		}
	}
	float PitchT = LookPitchT;
	if (CryLeft > 0.f && CryTotal > 1.0f && Species == EBirdSpecies::Gull && bGround) PitchT = 32.f;	// long call: head thrown back
	// bird heads move in quick saccades
	LookYaw = FMath::FInterpTo(LookYaw, LookYawT, Dt, 14.f);
	LookPitch = FMath::FInterpTo(LookPitch, PitchT, Dt, 10.f);
}

// ---------------------------------------------------------------------------------------------------- sensing
void ABird::SenseGround()
{
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdGround), false);
	if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
	FHitResult H;
	if (GetWorld()->LineTraceSingleByChannel(H, Pos, Pos - FVector(0, 0, 20000.f), ECC_Visibility, Q)) GroundZ = H.ImpactPoint.Z;
	else GroundZ = Pos.Z - 20000.f;
}

void ABird::SenseObstacles()
{
	const float Look = FMath::Max(Speed * 1.6f, 300.f);
	FVector Dir = Vel.GetSafeNormal();
	if (Dir.IsNearlyZero()) return;
	float Len = Look;
	if (State == EBirdState::Landing && bHasSpot) Len = FMath::Min(Len, float(FVector::Dist(Pos, Spot + FVector::UpVector * BodyH())) - BodyR() * 2.5f);
	if (Len < 20.f)
	{ AvoidDir = FMath::Lerp(AvoidDir, FVector::ZeroVector, 0.5f); return; }
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdAvoid), false);
	if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
	FHitResult H;
	if (GetWorld()->SweepSingleByChannel(H, Pos, Pos + Dir * Len, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR() * 1.6f), Q))
	{
		const float Urgency = 1.f - H.Time;
		AvoidDir = (H.ImpactNormal + FVector::UpVector * 0.5f).GetSafeNormal() * (0.6f + 2.f * Urgency);
		AvoidTime = 0.8f;
	}
}

bool ABird::CheckThreats()
{
	if (!Flock) return false;
	for (const ABirdFlock::FThreat& T : Flock->GetThreats())
	{
		const float D2 = FVector::DistSquared(T.Pos, Pos);
		if (D2 < FMath::Square(S.PanicRadius) || (D2 < FMath::Square(S.ThreatRadius) && T.Speed > S.ThreatMinSpeed))
		{
			FleeFrom = T.Pos;
			return true;
		}
	}
	return false;
}

FVector ABird::Separation() const
{
	FVector Steer = FVector::ZeroVector;
	if (!Flock) return Steer;
	const float MyR = SeparationRadius();
	for (const ABird* O : Flock->AllBirds())
	{
		if (!O || O == this || O->State == EBirdState::Dead || O->State == EBirdState::Unplaced) continue;
		const FVector Rel = O->Pos - Pos;
		const float R = (MyR + O->SeparationRadius()) * 1.35f + 30.f;
		if (Rel.SizeSquared() > FMath::Square(R + (Speed + O->Speed) * 1.5f)) continue;
		const FVector RelV = O->Vel - Vel;
		const float VV = RelV.SizeSquared();
		const float T = VV > 1.f ? FMath::Clamp(-FVector::DotProduct(Rel, RelV) / VV, 0.f, 1.5f) : 0.f;
		const FVector Closest = Rel + RelV * T;
		const float D = Closest.Size();
		if (D < R)
		{
			FVector Away = -Closest.GetSafeNormal();
			if (Away.IsNearlyZero()) Away = FVector::UpVector;
			// split vertically too: the lower-address bird climbs, the other dives (as real birds do)
			Away.Z += (this < O ? 0.6f : -0.6f) * (1.f - FMath::Abs(Away.Z));
			Steer += Away.GetSafeNormal() * (1.f - D / R) * (T < 0.3f ? 3.f : 1.8f);
		}
	}
	return Steer;
}

// ---------------------------------------------------------------------------------------------------- spots & waypoints
FVector ABird::PickWaypoint()
{
	const ABirdZone* Z = Zone.Get();
	FVector P = Z ? Z->RandomPoint(Rng, 1.4f) : Pos + FVector(Rng.FRandRange(-3000.f, 3000.f), Rng.FRandRange(-3000.f, 3000.f), 0.f);
	const float Base = Z ? FMath::Max(GroundZ, Z->WorldBounds().Min.Z) : GroundZ;
	P.Z = Base + Rand(S.CruiseHeight);
	if (Z) P.Z = FMath::Max(P.Z, Z->WorldBounds().Min.Z + S.CruiseHeight.X * 0.5f);
	return P;
}

bool ABird::ChooseSpot()
{
	ABirdZone* Z = Zone.Get();
	if (!Z || !Flock) return false;
	UWorld* W = GetWorld();
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdSpot), false);
	Q.AddIgnoredActors(Flock->TraceIgnore());
	const FBox Bounds = Z->WorldBounds(1.5f);
	const float Spacing = S.HalfSpan * Scale * 0.75f + BodyR() * 1.1f + 3.f;
	struct FCand { FVector Foot, N, App; float Score; };
	TArray<FCand, TInlineAllocator<4>> Good;
	float LowZ = 1e9f;
	for (int32 k = 0; k < 12 && Good.Num() < 3; ++k)
	{
		bool bIn = Rng.FRand() < Z->Preference;
		FVector P = Z->RandomPoint(Rng, bIn ? 1.f : 1.5f);
		if (Task == EBirdTask::FishCarry)
		{
			// with a fish: the nearest stretch of beach (toward home), low down
			const FVector Home = FMath::Lerp(Pos, Z->GetCenter(), 0.35f);
			P = Home + FVector(Rng.FRandRange(-1500.f, 1500.f), Rng.FRandRange(-1500.f, 1500.f), 0.f);
			bIn = true;
		}
		else if (Task == EBirdTask::ScavengeFly)
		{
			// land a short walk away from the remains
			const float A = Rng.FRandRange(0.f, 2.f * PI);
			P = FoodApproach + FVector(FMath::Cos(A), FMath::Sin(A), 0.f) * Rng.FRandRange(70.f, 200.f) * Scale;
			bIn = true;
		}
		if (bFleeing && !FleeFrom.IsZero())
		{
			// prefer spots away from the threat
			const FVector Away = Horizontal(P - FleeFrom);
			if (Away.Size() < S.ThreatRadius * 1.3f) continue;
		}
		const float Top = FMath::Max(Bounds.Max.Z + 300.f, Pos.Z);
		FHitResult H;
		if (!W->LineTraceSingleByChannel(H, FVector(P.X, P.Y, Top), FVector(P.X, P.Y, Bounds.Min.Z - 1500.f), ECC_Visibility, Q)) continue;
		if (H.ImpactNormal.Z < 0.8f) continue;
		const FVector Foot = H.ImpactPoint;
		// never on the water
		float SurfZ = 0.f;
		if (Flock->IsWaterActor(H.GetActor()) || (Flock->IsWater(Foot, &SurfZ) && Foot.Z <= SurfZ + 20.f)) continue;
		if (!Flock->IsSpotFree(this, Foot, Spacing)) continue;
		if (Task == EBirdTask::ScavengeFly && FoodTarget.IsValid() && Horizontal(Foot - FoodTarget->GetActorLocation()).Size() < BodyR() * 2.f) continue;
		// room for the body
		if (W->OverlapAnyTestByChannel(Foot + FVector(0, 0, BodyR() * 1.25f + 3.f), FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR() * 1.1f), Q)) continue;
		// open sky above (approach from above)
		FHitResult Up;
		if (W->LineTraceSingleByChannel(Up, Foot + FVector(0, 0, BodyH() * 2.f), Foot + FVector(0, 0, 700.f), ECC_Visibility, Q)) continue;
		// feet supported (not a knife edge)
		bool bSupport = true;
		for (int32 s = 0; s < 2 && bSupport; ++s)
		{
			const FVector Off = FRotator(0, Rng.FRandRange(0.f, 360.f), 0).Vector() * BodyR() * 0.45f;
			FHitResult F;
			bSupport = W->LineTraceSingleByChannel(F, Foot + Off + FVector(0, 0, 8.f), Foot + Off - FVector(0, 0, 8.f), ECC_Visibility, Q);
		}
		if (!bSupport) continue;
		// approach corridor: try the direct heading first, then 3 others
		FVector App = Horizontal(Foot - Pos).GetSafeNormal();
		if (App.IsNearlyZero()) App = FRotator(0, Yaw, 0).Vector();
		bool bClear = false;
		for (int32 a = 0; a < 4 && !bClear; ++a)
		{
			const FVector D = App.RotateAngleAxis(a == 0 ? 0.f : (a == 1 ? 70.f : (a == 2 ? -70.f : 180.f)), FVector::UpVector);
			const FVector End = Foot + FVector(0, 0, BodyH() + 2.f);
			const FVector Start = End - D * 700.f + FVector(0, 0, 220.f);
			FHitResult C;
			if (!W->SweepSingleByChannel(C, Start, End, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR() * 1.2f), Q))
			{
				App = D;
				bClear = true;
			}
		}
		if (!bClear) continue;
		LowZ = FMath::Min(LowZ, Foot.Z);
		Good.Add({ Foot, H.ImpactNormal, App, Rng.FRand() * 0.5f + (bIn ? 0.3f : 0.f) });
	}
	if (Good.Num() == 0) return false;
	int32 Best = 0;
	for (int32 i = 0; i < Good.Num(); ++i)
	{
		const float Pref = (Task == EBirdTask::FishCarry || Task == EBirdTask::ScavengeFly) ? -1.f : S.PerchHeightPreference;
		Good[i].Score += Pref * FMath::Clamp((Good[i].Foot.Z - LowZ) / 150.f, 0.f, 1.5f);
		if (Good[i].Score > Good[Best].Score) Best = i;
	}
	Spot = Good[Best].Foot;
	SpotNormal = Good[Best].N;
	ApproachDir = Good[Best].App;
	bHasSpot = true;
	bFinal = false;
	return true;
}

// ---------------------------------------------------------------------------------------------------- ground states
void ABird::StartFlight(bool bFlee)
{
	ReleaseSpot();
	bFleeing = bFlee;
	// feeding interrupted: a held fish goes along (eaten elsewhere), anything else is abandoned
	if (Task == EBirdTask::FishHold) Task = EBirdTask::FishCarry;
	else if (Task == EBirdTask::FishPeck || Task == EBirdTask::ScavengeEat || Task == EBirdTask::ScavengeWalk || (bFlee && Task == EBirdTask::ScavengeFly)) EndTask();
	bTaskLook = false;
	TaskPitch = 0.f;
	// alarm call when flushed (both species call as they take off from a threat)
	if (bFlee && CryLeft <= 0.f && Rng.FRand() < (Species == EBirdSpecies::Kingfisher ? 0.8f : 0.55f)) Cry(Rand(S.CryDuration), 1.f);
	FVector Dir = FRotator(0.f, Yaw + Rng.FRandRange(-50.f, 50.f), 0.f).Vector();
	if (bFlee && !FleeFrom.IsZero())
	{
		Dir = Horizontal(Pos - FleeFrom).GetSafeNormal();
		if (Dir.IsNearlyZero()) Dir = FRotator(0.f, Yaw, 0.f).Vector();
		Dir = Dir.RotateAngleAxis(Rng.FRandRange(-30.f, 30.f), FVector::UpVector);
	}
	else if (const ABirdZone* Z = Zone.Get())
	{
		if (!Z->IsInside(Pos, -200.f)) Dir = Horizontal(Z->GetCenter() - Pos).GetSafeNormal();
	}
	if (Flock)
	{
		FVector Away = FVector::ZeroVector;
		for (const ABird* O : Flock->AllBirds())
		{
			if (!O || O == this || O->IsDead() || O->GetState() == EBirdState::Unplaced) continue;
			const FVector Rel = Horizontal(Pos - O->GetPos());
			const float Clear = (S.HalfSpan * Scale * 0.7f + O->SeparationRadius()) * 1.6f;
			if (Rel.Size() < Clear) Away += Rel.GetSafeNormal() * (1.f - Rel.Size() / Clear);
		}
		if (!Away.IsNearlyZero()) Dir = (Dir + Away.GetSafeNormal() * 2.f).GetSafeNormal();
	}
	// pick a clear climb-out direction
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdTakeoff), false);
	if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
	FHitResult H;
	bool bFound = false;
	for (int32 a = 0; a < 8 && !bFound; ++a)
	{
		const FVector D = Dir.RotateAngleAxis(a * 45.f * (a % 2 ? 1.f : -1.f) * ((a + 1) / 2), FVector::UpVector);
		const FVector End = Pos + D * 250.f * Scale + FVector(0, 0, 220.f * Scale);
		if (!GetWorld()->SweepSingleByChannel(H, Pos + FVector(0, 0, 5.f), End, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR()), Q))
		{
			Dir = D;
			bFound = true;
		}
	}
	ApproachDir = bFound ? Dir : FVector::ZeroVector;	// zero = straight up
	Vel = FVector::ZeroVector;		// the leg push + first downstroke ramp it up (HoverFlight accel), no instant velocity
	Speed = 0.f;
	HoverW = 1.f;
	FlapPhase = 0.f;
	Timer = Rand(S.FlightTime);
	if (const ABirdZone* Z = Zone.Get()) Timer *= 0.6f + 0.9f * Z->AirTime;
	++Takeoffs;
	SetState(EBirdState::TakingOff);
	if (bFlee && Species == EBirdSpecies::Gull && Rng.FRand() < 0.6f) Cry(Rng.FRandRange(0.35f, 0.7f), 1.f);	// alarm call
}

bool ABird::TryStartWalk(float MinDist, float MaxDist)
{
	if (!Flock || S.WalkChance <= 0.f) return false;
	UWorld* W = GetWorld();
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdWalk), false);
	Q.AddIgnoredActors(Flock->TraceIgnore());
	const FVector Foot = Pos - FVector::UpVector * BodyH();
	const float Spacing = S.HalfSpan * Scale * 0.75f + BodyR() * 1.1f + 3.f;
	const ABirdZone* Z = Zone.Get();
	for (int32 k = 0; k < 6; ++k)
	{
		const float A = Yaw + Rng.FRandRange(-110.f, 110.f);
		const FVector Dir = FRotator(0, A, 0).Vector();
		const float Dist = Rng.FRandRange(MinDist, MaxDist) * Scale;
		FVector Target = Foot + Dir * Dist;
		FHitResult H;
		if (!W->LineTraceSingleByChannel(H, Target + FVector(0, 0, 40.f * Scale), Target - FVector(0, 0, 60.f * Scale), ECC_Visibility, Q)) continue;
		if (H.ImpactNormal.Z < 0.8f || FMath::Abs(H.ImpactPoint.Z - Foot.Z) > 25.f * Scale) continue;
		Target = H.ImpactPoint;
		if (Z && !Z->IsInside(Target) && Rng.FRand() < Z->Preference) continue;
		if (!Flock->IsSpotFree(this, Target, Spacing)) continue;
		bool bPathClear = true;
		for (const ABird* O : Flock->AllBirds())
		{
			if (!O || O == this || O->IsDead() || O->IsFlying() || O->GetState() == EBirdState::Unplaced) continue;
			const float Need = FMath::Max(Spacing, O->Settings().HalfSpan * O->GetScale() * 0.75f + O->BodyR() * 1.1f + 3.f);
			if (FMath::PointDistToSegment(O->GetFootSpot(), Foot, Target) < Need) { bPathClear = false; break; }
		}
		if (!bPathClear) continue;
		// clear path at body height
		if (W->SweepSingleByChannel(H, Pos, Target + FVector::UpVector * BodyH(), FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR() * 0.8f), Q)) continue;
		// no gaps / steps along the way
		bool bOk = true;
		for (int32 s = 1; s <= 3 && bOk; ++s)
		{
			const FVector M = FMath::Lerp(Foot, Target, s / 4.f);
			FHitResult GH;
			bOk = W->LineTraceSingleByChannel(GH, M + FVector(0, 0, 20.f * Scale), M - FVector(0, 0, 25.f * Scale), ECC_Visibility, Q) && GH.ImpactNormal.Z > 0.75f;
		}
		if (!bOk) continue;
		WalkTarget = Target;
		Spot = Target;
		bHasSpot = true;
		WalkSpeedCur = 0.f;
		if (MaxDist > 60.f) ++Walks;
		SetState(EBirdState::Walking);
		return true;
	}
	return false;
}

void ABird::UpdatePerched(float Dt)
{
	if (SettleT < 1.f)
	{
		// critically damped spring from the touchdown position + velocity to the perch (legs absorb the landing)
		SettleT = FMath::Min(1.f, SettleT + Dt / 0.45f);
		const FVector Goal = Spot + FVector::UpVector * BodyH();
		constexpr float W = 14.f;
		SettleVel += ((Goal - Pos) * (W * W) - SettleVel * (2.f * W)) * Dt;
		Pos += SettleVel * Dt;
		if (SettleT >= 1.f) { Pos = Goal; SettleVel = FVector::ZeroVector; }
		const float E = SmoothStep01(0.f, 1.f, SettleT);
		Pitch = FMath::Lerp(SettlePitch, 0.f, E);
		Bank = FMath::Lerp(SettleBank, 0.f, E);
	}
	else
	{
		Pitch = Approach(Pitch, TaskPitch, 110.f * Dt);		// feeding poses lean the body forward / back
	}
	if (UpdatePerchedTask(Dt)) return;
	if (bTurning)
	{
		// turn on the spot with small steps (the walk cycle advances with the turned angle)
		const float D = FMath::FindDeltaAngleDegrees(Yaw, TurnTarget);
		// the head swings round first and the body follows it
		LookYawT = FMath::Clamp(D, -75.f, 75.f);
		NextLook = FMath::Max(NextLook, 0.3f);
		const float Rate = S.TurnRateDeg * FMath::Clamp(FMath::Abs(D) / 25.f + 0.35f, 0.35f, 1.f);	// eases out
		const float StepDeg = FMath::Sign(D) * FMath::Min(FMath::Abs(D), Rate * Dt);
		Yaw = FRotator::NormalizeAxis(Yaw + StepDeg);
		WalkPhase += FMath::Abs(StepDeg) / FMath::Max(S.TurnDegPerStepCycle, 10.f);
		WalkW = Approach(WalkW, 0.75f, Dt * 7.f);
		if (FMath::Abs(D) < 0.5f) bTurning = false;
	}
	else
	{
		WalkW = Approach(WalkW, 0.f, Dt * 4.f);
	}
	ThreatCheck -= Dt;
	if (ThreatCheck <= 0.f)
	{
		ThreatCheck = 0.12f;
		if (CheckThreats())
		{
			StartFlight(true);
			return;
		}
	}
	if (SettleT < 1.f) return;
	// feeding: kingfishers go fishing now and then, gulls look out for remains
	if (Task == EBirdTask::None && Flock)
	{
		if (S.bFishes)
		{
			FishingTimer -= Dt;
			if (FishingTimer <= 0.f)
			{
				FishingTimer = Rand(S.FishingInterval);
				if (GoFishing()) return;
			}
		}
		if (S.bScavenges)
		{
			ScavengeScan -= Dt;
			if (ScavengeScan <= 0.f)
			{
				ScavengeScan = 1.5f;
				if (TryScavenge()) return;
			}
		}
	}
	Timer -= Dt;
	if (Timer <= 0.f && !bTurning)
	{
		const float AirTime = Zone.IsValid() ? Zone->AirTime : 0.5f;
		if (bLeaveAfterMeal || Rng.FRand() < 0.15f + 0.5f * AirTime)
		{
			bLeaveAfterMeal = false;
			StartFlight(false);
			return;
		}
		Timer = Rand(S.PerchTime) * 0.5f;
		if (Rng.FRand() < S.WalkChance && TryStartWalk())
		{
			bShuffle = false;
			return;
		}
	}
	// idle life between the big decisions: look around (UpdateLook), turn on the spot, shuffle a few steps
	IdleTimer -= Dt;
	if (IdleTimer <= 0.f && !bTurning)
	{
		IdleTimer = Rand(S.IdleActionTime);
		if (Rng.FRand() < S.ShuffleChance)
		{
			TimerBeforeWalk = Timer;
			if (TryStartWalk(S.ShuffleDistance.X, S.ShuffleDistance.Y))
			{
				bShuffle = true;
				++Shuffles;
				return;
			}
		}
		const float Amount = Rng.FRand() < 0.25f ? Rng.FRandRange(110.f, 180.f) : Rng.FRandRange(20.f, 80.f);
		TurnTarget = FRotator::NormalizeAxis(Yaw + (Rng.FRand() < 0.5f ? -Amount : Amount));
		bTurning = true;
		++Turns;
	}
}

void ABird::UpdateWalking(float Dt)
{
	ThreatCheck -= Dt;
	if (ThreatCheck <= 0.f)
	{
		ThreatCheck = 0.12f;
		if (CheckThreats())
		{
			StartFlight(true);
			return;
		}
	}
	FVector Foot = Pos - FVector::UpVector * BodyH();
	const FVector To = Horizontal(WalkTarget - Foot);
	const float Dist = To.Size();
	auto Stop = [&]()
	{
		Spot = Foot;
		bHasSpot = true;
		Timer = bShuffle ? FMath::Max(TimerBeforeWalk - StateTime, 1.f) : Rand(S.PerchTime) * 0.6f;
		bShuffle = false;
		IdleTimer = Rand(S.IdleActionTime);
		SettleT = 1.f;
		SetState(EBirdState::Perched);
		if (Task == EBirdTask::ScavengeWalk)
		{
			// at the remains -> eat; stopped short (a bird in the way...) -> try again a few times
			if (Horizontal(Foot - FoodApproach).Size() < 12.f * Scale) { Task = EBirdTask::ScavengeEat; TaskT = 0.f; }
			else if (++ScavengeTries > 3 || !StartWalkTo(FoodApproach)) EndTask();
		}
	};
	if (Dist < 2.5f * Scale || StateTime > 20.f)
	{
		Stop();
		return;
	}
	const float WantYaw = To.Rotation().Yaw;
	const float DYaw = FMath::FindDeltaAngleDegrees(Yaw, WantYaw);
	LookYawT = FMath::Clamp(DYaw * 1.2f, -70.f, 70.f);		// looks where it is going before the body turns
	NextLook = FMath::Max(NextLook, 0.3f);
	Yaw = ApproachAngle(Yaw, WantYaw, 200.f * Dt);
	const float Brake = FMath::Clamp(Dist / (12.f * Scale), 0.2f, 1.f);
	const float WantSpeed = S.WalkSpeed * Scale * (FMath::Abs(DYaw) > 35.f ? 0.35f : 1.f) * Brake * (bShuffle ? 0.75f : 1.f);
	WalkSpeedCur = Approach(WalkSpeedCur, WantSpeed, 160.f * Scale * Dt);
	// don't walk into another bird
	if (Flock)
	{
		const FVector Fwd = FRotator(0, Yaw, 0).Vector();
		for (const ABird* O : Flock->AllBirds())
		{
			if (!O || O == this || O->IsDead() || O->IsFlying() || O->State == EBirdState::Unplaced) continue;
			const FVector Rel = Horizontal(O->Pos - Pos);
			const float Need = FMath::Max(S.HalfSpan * Scale * 0.75f + BodyR() * 1.1f, O->Settings().HalfSpan * O->GetScale() * 0.75f + O->BodyR() * 1.1f) + 3.f;
			if (Rel.Size() < Need && FVector::DotProduct(Rel, Fwd) > 0.f)
			{
				Stop();
				return;
			}
		}
	}
	const FVector Step = FRotator(0, Yaw, 0).Vector() * WalkSpeedCur * Dt;
	FVector NewFoot = Foot + Step;
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdWalkStep), false);
	if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
	FHitResult H;
	if (!GetWorld()->LineTraceSingleByChannel(H, NewFoot + FVector(0, 0, 12.f * Scale), NewFoot - FVector(0, 0, 20.f * Scale), ECC_Visibility, Q)
		|| H.ImpactNormal.Z < 0.7f)
	{
		Stop();
		return;
	}
	NewFoot.Z = FMath::FInterpTo(Foot.Z, H.ImpactPoint.Z, Dt, 18.f);
	Pos = NewFoot + FVector::UpVector * BodyH();
	WalkPhase += WalkSpeedCur * Dt / FMath::Max(S.StrideCm * Scale, 0.5f);
	WalkW = Approach(WalkW, WalkSpeedCur > 1.f ? 1.f : 0.f, Dt * 5.f);
	Spot = WalkTarget;
}

// ---------------------------------------------------------------------------------------------------- flight
void ABird::BankedFlight(float Dt, const FVector& DesiredDir, float TargetSpeed, bool bAllowGlide)
{
	const FVector Dir = DesiredDir.GetSafeNormal();
	const float V = FMath::Max(Speed, 50.f);
	// heading: bank-limited coordinated turn (lateral acceleration = g tan(bank))
	if (!Horizontal(Dir).IsNearlyZero())
	{
		const float WantYaw = Dir.Rotation().Yaw;
		const float DYaw = FMath::FindDeltaAngleDegrees(Yaw, WantYaw);
		const float TurnRate = FMath::DegreesToRadians(FMath::Clamp(DYaw * 1.4f, -120.f, 120.f));
		const float BankWant = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(V * TurnRate / G)), -S.MaxBankDeg, S.MaxBankDeg);
		Bank = Approach(Bank, BankWant, S.RollRateDeg * Dt);
	}
	else
	{
		Bank = Approach(Bank, 0.f, S.RollRateDeg * Dt);
	}
	Yaw += FMath::RadiansToDegrees(G * FMath::Tan(FMath::DegreesToRadians(Bank)) / V) * Dt;
	Yaw = FRotator::NormalizeAxis(Yaw);

	// flap / glide bouts
	BoutTime -= Dt;
	if (BoutTime <= 0.f)
	{
		bGlideBout = Rng.FRand() < S.GlideFraction;
		BoutTime = bGlideBout ? (S.GlideFraction > 0.3f ? Rng.FRandRange(2.5f, 7.f) : Rng.FRandRange(0.25f, 0.7f))
		                      : (S.GlideFraction > 0.3f ? Rng.FRandRange(1.5f, 4.f) : Rng.FRandRange(0.8f, 2.5f));
	}
	float GammaWant = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(Dir.Z, -1.f, 1.f)));
	GammaWant = FMath::Clamp(GammaWant, -S.MaxClimbDeg * 1.3f, S.MaxClimbDeg);
	const bool bGlide = bAllowGlide && bGlideBout && GammaWant < 3.f && TargetSpeed <= S.CruiseSpeed * 1.05f;
	if (bGlide) GammaWant = FMath::Min(GammaWant, -FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(S.GlideSink / V, 0.f, 0.5f))));
	Gamma = Approach(Gamma, GammaWant, S.PitchRateDeg * Dt);

	// speed: thrust toward the target, gravity along the path
	Speed = Approach(Speed, TargetSpeed, S.Acceleration * Dt);
	Speed -= G * FMath::Sin(FMath::DegreesToRadians(Gamma)) * 0.25f * Dt;
	Speed = FMath::Min(Speed, S.MaxSpeed);
	if (Speed < S.MinSpeed * 0.6f) Speed = Approach(Speed, S.MinSpeed * 0.6f, S.Acceleration * 2.f * Dt);	// ramp, never jump
	const float CG = FMath::Cos(FMath::DegreesToRadians(Gamma));
	Vel = FVector(CG * FMath::Cos(FMath::DegreesToRadians(Yaw)), CG * FMath::Sin(FMath::DegreesToRadians(Yaw)), FMath::Sin(FMath::DegreesToRadians(Gamma))) * Speed;

	FlapW = Approach(FlapW, bGlide ? 0.f : 1.f, Dt * (bGlide ? 1.6f : 3.f));
	HoverW = Approach(HoverW, 0.f, Dt * 2.f);
	const float Effort = FMath::Clamp(Gamma / 20.f, 0.f, 1.f) + (TargetSpeed > Speed + 50.f ? 0.25f : 0.f);
	FlapPhase += FlapRate() * (1.f + 0.3f * Effort) * Dt;
	Pitch = Approach(Pitch, Gamma * 0.6f, 90.f * Dt);
}

void ABird::HoverFlight(float Dt, const FVector& TargetVel, float Accel)
{
	const FVector DV = TargetVel - Vel;
	Vel += FVector(DV.X, DV.Y, 0.f).GetClampedToMaxSize(Accel * Dt);
	Vel.Z += FMath::Clamp(DV.Z, -Accel * 1.5f * Dt, Accel * 1.5f * Dt);
	Speed = Vel.Size();
	const FVector H = Horizontal(Vel);
	if (H.Size() > 40.f) Yaw = ApproachAngle(Yaw, H.Rotation().Yaw, 320.f * Dt);
	else if (!ApproachDir.IsNearlyZero()) Yaw = ApproachAngle(Yaw, ApproachDir.Rotation().Yaw, 200.f * Dt);
	Gamma = Speed > 1.f ? FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(Vel.Z / Speed, -1.f, 1.f))) : 0.f;
	Bank = Approach(Bank, 0.f, S.RollRateDeg * Dt);
	Pitch = Approach(Pitch, 0.f, 120.f * Dt);
	FlapW = Approach(FlapW, 1.f, Dt * 5.f);
	FlapPhase += FlapRate() * 1.2f * Dt;
}

void ABird::Touchdown()
{
	SettleVel = Vel;
	SettleFrom = Pos;
	SettlePitch = Pitch;
	SettleBank = Bank;
	SettleT = 0.f;
	Vel = FVector::ZeroVector;
	Speed = 0.f;
	bFinal = false;
	bFleeing = false;
	const float AirTime = Zone.IsValid() ? Zone->AirTime : 0.5f;
	Timer = Rand(S.PerchTime) * (1.3f - 0.9f * AirTime);
	++Landings;
	SetState(EBirdState::Perched);
	if (Task == EBirdTask::FishCarry && HeldFish) { Task = EBirdTask::FishHold; TaskT = 0.f; }
	else if (Task == EBirdTask::FishCarry) EndTask();
	else if (Task == EBirdTask::ScavengeFly)
	{
		Task = EBirdTask::ScavengeWalk;
		ScavengeTries = 0;
		SettleT = 1.f;
		Pos = Spot + FVector::UpVector * BodyH();
		if (!FoodTarget.IsValid() || !StartWalkTo(FoodApproach)) EndTask();
	}
}

void ABird::UpdateAir(float Dt)
{
	if (UpdateAirTask(Dt)) return;
	GroundCheck -= Dt;
	if (GroundCheck <= 0.f) { GroundCheck = 0.25f; SenseGround(); }
	AvoidCheck -= Dt;
	if (AvoidCheck <= 0.f) { AvoidCheck = 0.12f; SenseObstacles(); }
	AvoidTime -= Dt;
	if (AvoidTime <= 0.f) AvoidDir = FMath::Lerp(AvoidDir, FVector::ZeroVector, FMath::Min(1.f, Dt * 3.f));
	ThreatCheck -= Dt;
	if (ThreatCheck <= 0.f)
	{
		ThreatCheck = 0.2f;
		if (CheckThreats() && State != EBirdState::TakingOff)
		{
			if (State == EBirdState::Landing) { ++AbortedLandings; ReleaseSpot(); SetState(EBirdState::Flying); Waypoint = PickWaypoint(); }
			if (Task == EBirdTask::FishHunt || Task == EBirdTask::ScavengeFly) EndTask();
			bFleeing = true;
			Timer = FMath::Max(Timer, 4.f);
		}
	}
	const FVector Old = Pos;
	const float Agl = Pos.Z - GroundZ;

	if (State == EBirdState::TakingOff)
	{
		const FVector Fwd = ApproachDir.IsNearlyZero() ? FVector::ZeroVector : ApproachDir;
		const float Ramp = FMath::Clamp(StateTime / 1.2f, 0.f, 1.f);
		const FVector Want = Fwd * FMath::Lerp(80.f, S.MinSpeed * 1.35f, Ramp) + FVector(0, 0, FMath::Lerp(260.f, 140.f, Ramp) * FMath::Sqrt(Scale));
		HoverFlight(Dt, Want, S.Acceleration * (StateTime < 0.15f ? 2.6f : 1.6f));
		HoverW = Approach(HoverW, 1.f - SmoothStep01(S.MinSpeed * 0.7f, S.MinSpeed * 1.2f, Horizontal(Vel).Size()), Dt * 3.f);
		if ((Horizontal(Vel).Size() > S.MinSpeed * 1.1f && Agl > BodyH() * 2.f + 120.f) || StateTime > 4.f)
		{
			if (Horizontal(Vel).Size() < 50.f) Vel += FRotator(0, Yaw, 0).Vector() * S.MinSpeed;
			Speed = Vel.Size();
			Yaw = Vel.Rotation().Yaw;
			Gamma = Vel.Rotation().Pitch;
			Waypoint = PickWaypoint();
			SetState(EBirdState::Flying);
		}
	}
	else if (State == EBirdState::Flying)
	{
		Timer -= Dt;
		if (Task == EBirdTask::FishCarry || Task == EBirdTask::ScavengeFly) Timer = FMath::Min(Timer, 0.f);
		if (Task == EBirdTask::FishHunt) Timer = FMath::Max(Timer, 1.f);
		if (Task == EBirdTask::None && S.bScavenges && Flock)
		{
			ScavengeScan -= Dt;
			if (ScavengeScan <= 0.f) { ScavengeScan = 2.f; TryScavenge(); }
		}
		if (Timer <= 0.f && !bFleeing)
		{
			SpotSearchCooldown -= Dt;
			if (SpotSearchCooldown <= 0.f)
			{
				SpotSearchCooldown = 0.5f;
				if (ChooseSpot()) SetState(EBirdState::Landing);
			}
		}
		const bool bErrand = Task == EBirdTask::FishHunt || Task == EBirdTask::FishCarry || Task == EBirdTask::ScavengeFly;
		if (Task != EBirdTask::FishHunt && (FVector::DistSquared(Pos, Waypoint) < FMath::Square(500.f) || (StateTime > 60.f && FMath::Fmod(StateTime, 20.f) < Dt))) Waypoint = PickWaypoint();
		FVector D = (Waypoint - Pos).GetSafeNormal();
		if (bFleeing)
		{
			const FVector Away = (Pos - FleeFrom).GetSafeNormal();
			D = (Horizontal(Away).GetSafeNormal() + FVector(0, 0, 0.45f)).GetSafeNormal();
			if (StateTime > 3.f && FVector::Dist(Pos, FleeFrom) > S.ThreatRadius * 1.5f) { bFleeing = false; Waypoint = PickWaypoint(); }
		}
		if (Agl < S.CruiseHeight.X * 0.5f) D.Z += 0.6f;
		if (const ABirdZone* Z = Zone.Get())
		{
			if (!bErrand && !Z->IsInside(Pos, 2500.f)) D += (Z->GetCenter() - Pos).GetSafeNormal() * 0.8f;
			if (Pos.Z > Z->WorldBounds().Max.Z + S.CruiseHeight.Y) D.Z -= 0.4f;
		}
		D += AvoidDir * 2.f + Separation();
		BankedFlight(Dt, D, S.CruiseSpeed * (bFleeing ? 1.25f : 1.f), !bFleeing);
	}
	else if (State == EBirdState::Landing)
	{
		bool bAbort = !bHasSpot;
		const float Decel = S.Acceleration * 0.9f;
		const FVector Target = Spot + FVector::UpVector * BodyH();
		const FVector ToT = Target - Pos;
		const float D = ToT.Size();
		if (!bAbort && !bFinal)
		{
			const float Lapp = Speed * Speed / (2.f * Decel) + 250.f * FMath::Sqrt(Scale);
			const FVector A = Target - ApproachDir * Lapp + FVector(0, 0, Lapp * 0.22f);
			FVector Dir = (A - Pos).GetSafeNormal();
			Dir += AvoidDir * 1.5f + Separation();
			BankedFlight(Dt, Dir, S.CruiseSpeed * 0.85f, false);
			const float Ang = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(Vel.GetSafeNormal(), ToT.GetSafeNormal()), -1.f, 1.f)));
			if ((FVector::Dist(Pos, A) < FMath::Max(300.f, Speed * 0.7f) && Ang < 40.f) || (D < Lapp * 1.1f && Ang < 25.f)) bFinal = true;
			if (StateTime > 30.f) bAbort = true;
		}
		else if (!bAbort)
		{
			const float VWant = FMath::Sqrt(2.f * Decel * D) + 12.f * FMath::Sqrt(Scale);
			HoverW = Approach(HoverW, 1.f - SmoothStep01(S.MinSpeed * 0.9f, S.MinSpeed * 1.6f, Speed), Dt * 2.5f);
			// aim point rides a glide cone above the perch: the descent ends exactly on the spot, never below its surface
			const float Hd0 = Horizontal(ToT).Size();
			const FVector Aim = Target + FVector(0, 0, Hd0 * 0.16f);
			const FVector ToAim = Aim - Pos;
			// descent never faster than what can still be stopped above the perch surface (sqrt(2 a h)), banked or hovering
			const float Above = Pos.Z - (Spot.Z + BodyH() * 0.75f);
			const float VzMin = Above > 0.f ? -FMath::Sqrt(2.f * Decel * 1.2f * Above) * 0.8f : -Above * 4.f;
			if (Speed > S.MinSpeed * 1.05f && D > BodyH() * 6.f && Above > BodyH() * 3.f + 30.f)
			{
				FVector Dir = ToAim.GetSafeNormal();
				if (Dir.Z * Speed < VzMin) Dir = FVector(Dir.X, Dir.Y, VzMin / FMath::Max(Speed, 1.f)).GetSafeNormal();
				BankedFlight(Dt, Dir + Separation() * 0.5f, FMath::Min(VWant, S.CruiseSpeed), false);
				FlapW = Approach(FlapW, 1.f, Dt * 3.f);
			}
			else
			{
				FVector TV = ToAim.GetSafeNormal() * FMath::Min(VWant, S.MinSpeed * 0.9f);
				TV.Z = FMath::Max(TV.Z, VzMin);
				HoverFlight(Dt, TV, Decel * 1.8f);
			}
			// overshoot at speed -> go around (a hovering bird simply turns back to the spot)
			if (Speed > S.MinSpeed && FVector::DotProduct(Vel, ToT) < 0.f && D > 40.f * Scale)
			{
				++AbortedLandings;
				bFinal = false;
				ApproachDir = Horizontal(Vel).GetSafeNormal();
				if (ApproachDir.IsNearlyZero()) ApproachDir = FRotator(0, Yaw, 0).Vector();
			}
			// feet touch: the remaining centimetre is taken by the settle easing (no snap)
			if (D < FMath::Max(1.2f * Scale, Speed * Dt * 1.2f))
			{
				Pos += Vel * Dt;
				Touchdown();
				return;
			}
			if (StateTime > 40.f) bAbort = true;
		}
		if (bAbort)
		{
			++AbortedLandings;
			ReleaseSpot();
			Timer = 2.f;
			Waypoint = PickWaypoint();
			if (Speed < S.MinSpeed)
			{
				// too slow to bank away: climb out like a take-off (velocity stays continuous)
				ApproachDir = Horizontal(Vel).IsNearlyZero() ? FRotator(0, Yaw, 0).Vector() : Horizontal(Vel).GetSafeNormal();
				SetState(EBirdState::TakingOff);
				HoverFlight(Dt, Vel, S.Acceleration);
			}
			else
			{
				SetState(EBirdState::Flying);
				BankedFlight(Dt, (Waypoint - Pos).GetSafeNormal() + FVector(0, 0, 0.3f), S.CruiseSpeed, false);
			}
		}
		else if (bFinal)
		{
			// never sink below the perch: near the spot the body centre stays above the surface it lands on
			const float Hd = Horizontal(ToT).Size();
			const float Floor = Spot.Z + BodyH() * 0.75f;
			if (Hd < BodyR() * 6.f && Pos.Z + Vel.Z * Dt < Floor)
			{
				Vel.Z = FMath::Max(Vel.Z, (Floor - Pos.Z) / Dt * 0.5f);
				Speed = Vel.Size();
				Gamma = Speed > 1.f ? FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(Vel.Z / Speed, -1.f, 1.f))) : 0.f;
			}
		}
	}
	Pos += Vel * Dt;
	// hard world collision: never pass through geometry
	{
		const bool bFinalApproach = State == EBirdState::Landing && bFinal;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdMove), false);
		if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
		FHitResult H;
		if (GetWorld()->SweepSingleByChannel(H, Old, Pos, FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR() * (bFinalApproach ? 0.4f : 0.8f)), Q) && !H.bStartPenetrating)
		{
			// safety net only (look-ahead avoidance should prevent contact): slide along the surface, keep the heading
			// continuous (the bank-limited turn steers out next frames), never pass through
			const FVector Slide = Pos - Old;
			const float SlideInto = FVector::DotProduct(Slide, H.ImpactNormal);
			Pos = H.Location + H.ImpactNormal * 0.5f + (Slide - H.ImpactNormal * FMath::Min(SlideInto, 0.f)) * (1.f - H.Time);
			const float Into = FVector::DotProduct(Vel, H.ImpactNormal);
			if (Into < 0.f) Vel -= H.ImpactNormal * Into;
			Speed = FMath::Max(Vel.Size(), 1.f);
			Gamma = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(Vel.Z / Speed, -1.f, 1.f)));
			AvoidDir = (H.ImpactNormal + FVector::UpVector * 0.5f).GetSafeNormal() * 2.5f;
			AvoidTime = 1.f;
			++Scrapes;
		}
	}
}

// ---------------------------------------------------------------------------------------------------- frame
void ABird::Simulate(float Dt)
{
	if (State == EBirdState::Dead)
	{
		DeadT += Dt;
		if (Flock && Mesh && (ShedLeft > 0 || GroundBursts < 2) && DeadT < 6.f)
		{
			const FVector BodyP = Mesh->Bounds.Origin;
			const FVector CV = Mesh->GetPhysicsLinearVelocity(TEXT("spine_02"));
			if (ShedLeft > 0)
			{
				// the rest of the burst is shed over the first 1.2 s of the fall, from wherever the body is
				const int32 Due = FMath::RoundToInt(ShedTotal * FMath::Pow(FMath::Clamp(DeadT / 1.2f, 0.f, 1.f), 0.7f));
				const int32 N = FMath::Min(ShedLeft, Due - (ShedTotal - ShedLeft));
				if (N > 0)
				{
					Flock->SpawnFeathers(this, BodyP, CV.IsNearlyZero() ? FVector::UpVector : -CV.GetSafeNormal(), N, 0.35f, &CV);
					ShedLeft -= N;
				}
			}
			// hitting the ground knocks a few more loose
			if (PrevCorpseVz < -250.f && CV.Z > -60.f && GroundBursts < 2)
			{
				++GroundBursts;
				const FVector Still = FVector::ZeroVector;
				Flock->SpawnFeathers(this, BodyP, FVector::UpVector, FMath::Max(3, S.HitFeathers / 2), 0.3f + 0.0004f * (-PrevCorpseVz), &Still);
			}
			PrevCorpseVz = CV.Z;
		}
		if (Mesh && DeadT > 2.f && Mesh->VisibilityBasedAnimTickOption != EVisibilityBasedAnimTickOption::AlwaysTickPose)
		{
			// lying still for a second -> put every body to sleep (no more solver work) and refresh bones only when seen
			const float V = Mesh->GetPhysicsLinearVelocity(TEXT("pelvis")).Size();
			CorpseStillT = V < 4.f ? CorpseStillT + Dt : 0.f;
			if (CorpseStillT > 1.f || (DeadT > 8.f && !Mesh->IsAnyRigidBodyAwake()))
			{
				for (FBodyInstance* BI : Mesh->Bodies) if (BI) BI->PutInstanceToSleep();
				Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPose;
			}
		}
		if (!bCulled && Mesh && Mesh->GetComponentLocation().Z < DeathZ - 5000.f) { bCulled = true; SetLifeSpan(0.05f); }	// fell out of the world (deferred: we are inside the flock loop)
		return;
	}
	if (State == EBirdState::Unplaced) return;
	StateTime += Dt;
	FlapT += Dt;
	// wings: half swept back early in the dive, fully just before the water (speed builds the fold), open again on the way out
	const float FoldT = Task == EBirdTask::FishDive ? FMath::Clamp(Vel.Size() / 700.f, 0.f, 1.f) : 0.f;
	FoldW = Approach(FoldW, FoldT, Dt * (Task == EBirdTask::FishDive ? 2.5f : 4.f));
	if (HeldFish && HeldFish->FishState == EBirdFishState::Held) FishSwing = HeldFish->UpdateStruggle(Dt);
	UpdateVoice(Dt);
	UpdateLook(Dt);
	switch (State)
	{
	case EBirdState::Perched: UpdatePerched(Dt); break;
	case EBirdState::Walking: UpdateWalking(Dt); break;
	default: UpdateAir(Dt); break;
	}
}

void ABird::ProbeImpacts(float Dt)
{
	if (!Flock || State == EBirdState::Dead || State == EBirdState::Unplaced || !Mesh) return;
	const bool bAir = IsFlying();
	const float Reach = (bAir ? S.HalfSpan * Scale : BodyH() * 1.4f) + 80.f;
	FCollisionObjectQueryParams Obj;
	Obj.AddObjectTypesToQuery(ECC_WorldStatic);
	Obj.AddObjectTypesToQuery(ECC_WorldDynamic);
	Obj.AddObjectTypesToQuery(ECC_PhysicsBody);
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdImpact), false);
	Q.AddIgnoredActors(Flock->TraceIgnore());
	// only movable shapes can hit a bird: skip the static tree (landscape, buildings, the ground the bird stands on) entirely
	Q.MobilityType = EQueryMobilityType::Dynamic;
	TArray<FOverlapResult> Hits;
	GetWorld()->OverlapMultiByObjectType(Hits, Pos, FQuat::Identity, Obj, FCollisionShape::MakeSphere(Reach), Q);	// return value = "blocking", not "found"
	const bool bDbg = ProbeDebugFrames > 0;
	if (bDbg) --ProbeDebugFrames;
	if (bDbg) UE_LOG(LogTemp, Display, TEXT("BIRDPROBE %s state=%d pos=%s reach=%.0f overlaps=%d"), *GetName(), int32(State), *Pos.ToCompactString(), Reach, Hits.Num());
	if (Hits.Num() == 0) { NearbyVel.Reset(); NearbyPos.Reset(); return; }
	const float RealDt = FMath::Max(GetWorld()->GetDeltaSeconds(), 1e-3f);
	// the bird's hittable volume: body, head, and the wings in flight (bone positions read only when something is near)
	struct FPt { FVector P; float R; FName Bone; };
	TArray<FPt, TInlineAllocator<4>> Pts;
	auto EnsurePts = [&]()
	{
		if (Pts.Num()) return;
		Pts.Add({ Pos, BodyR() * 1.2f, TEXT("pelvis") });
		Pts.Add({ Mesh->GetSocketLocation(TEXT("head")), S.BodyHeight * Scale * 0.38f, TEXT("head") });
		if (bAir)
		{
			Pts.Add({ Mesh->GetSocketLocation(TEXT("lowerarm_l")), S.HalfSpan * Scale * 0.3f, TEXT("lowerarm_l") });
			Pts.Add({ Mesh->GetSocketLocation(TEXT("lowerarm_r")), S.HalfSpan * Scale * 0.3f, TEXT("lowerarm_r") });
		}
	};
	TMap<TWeakObjectPtr<UPrimitiveComponent>, FVector> Seen, SeenPos;
	for (const FOverlapResult& O : Hits)
	{
		UPrimitiveComponent* C = O.GetComponent();
		if (!C || C->Mobility != EComponentMobility::Movable) continue;
		AActor* ObjOwner = C->GetOwner();
		if (ObjOwner && (ObjOwner->IsA<APawn>() || ObjOwner->IsA<ABird>())) continue;		// characters walking into birds don't kill them (threats make them flee)
		const bool bSim = C->IsSimulatingPhysics();
		if (!bSim && C->GetCollisionObjectType() != ECC_PhysicsBody && !(ObjOwner && Flock->IsLethal(ObjOwner))) continue;
		EnsurePts();
		const FVector Ctr = C->Bounds.Origin;
		// velocity of the physics body, or measured from its motion: objects simulated by another solver (Jolt) or moved
		// kinematically report no Chaos velocity. Jumps faster than 60 m/s are teleports, not motion.
		FVector V = bSim ? C->GetPhysicsLinearVelocity() : FVector::ZeroVector;
		if (const FVector* PP = NearbyPos.Find(C))
		{
			const FVector Vm = (Ctr - *PP) / RealDt;
			if (Vm.SizeSquared() > V.SizeSquared() && Vm.SizeSquared() < FMath::Square(6000.f)) V = Vm;
		}
		SeenPos.Add(C, Ctr);
		Seen.Add(C, V);
		FVector Rel = V - Vel;
		const float Rad = C->Bounds.SphereRadius + 2.f;
		// already bounced off us this step? (physics resolved the contact before we looked) -> judge by the speed it came in with
		bool bBounced = false;
		if (const FVector* Prev = NearbyVel.Find(C))
		{
			if ((V - *Prev).Size() > 250.f)
			{
				for (const FPt& Pt : Pts)
				{
					if (FVector::Dist(Ctr, Pt.P) < Rad + Pt.R + 8.f && FVector::DotProduct(*Prev - Vel, Pt.P - Ctr) > 0.f) { bBounced = true; Rel = *Prev - Vel; break; }
				}
			}
		}
		const float RelSpeed = Rel.Size();
		if (bDbg) UE_LOG(LogTemp, Display, TEXT("BIRDPROBE   %s v=%s dist=%.1f rad=%.1f bounced=%d rel=%.0f mass=%.2f"), *GetNameSafe(C), *V.ToCompactString(),
			float(FVector::Dist(Ctr, Pos)), Rad, bBounced ? 1 : 0, RelSpeed, bSim ? C->GetMass() : C->CalculateMass());
		if (RelSpeed < 150.f) continue;
		const FVector End = Ctr + Rel * Dt * 2.f;
		for (const FPt& Pt : Pts)
		{
			const FVector Q2 = FMath::ClosestPointOnSegment(Pt.P, Ctr, End);
			if (!bBounced && (FVector::DistSquared(Q2, Pt.P) > FMath::Square(Rad + Pt.R) || FVector::DotProduct(Rel, Pt.P - Ctr) <= 0.f)) continue;
			const float Mass = bSim ? C->GetMass() : C->CalculateMass();
			const float Momentum = RelSpeed * Mass;		// kg cm/s; an impact transfers about twice that
			AActor* Other = C->GetOwner();
			const bool bLethalObj = Other && Flock->IsLethal(Other) && RelSpeed > Flock->LethalMinSpeed;
			FBirdHitInfo H;
			H.Source = bLethalObj ? EBirdHitSource::LethalObject : EBirdHitSource::PhysicsImpact;
			H.Object = Other;
			H.Component = C;
			H.Location = Pt.P + (Q2 - Pt.P).GetClampedToMaxSize(Pt.R);
			H.Direction = Rel.GetSafeNormal();
			H.Speed = RelSpeed;
			H.Momentum = Momentum;
			H.ObjectForward = C->GetForwardVector();
			H.Bone = Pt.Bone;
			H.bLethalObject = Other && Flock->IsLethal(Other);
			H.Time = GetWorld()->GetTimeSeconds();
			SetHitContext(H);
			if (bDbg) UE_LOG(LogTemp, Display, TEXT("BIRDPROBE   -> contact %s momentum=%.0f"), *Pt.Bone.ToString(), Momentum);
			if (bLethalObj || (RelSpeed >= Flock->HeavyHitMinSpeed && Momentum * 2.f >= Flock->HeavyHitImpulse))
			{
				Kill(Pt.P + (Q2 - Pt.P).GetClampedToMaxSize(Pt.R), Rel.GetSafeNormal() * FMath::Clamp(RelSpeed * 0.6f, 250.f, 1500.f), Other, Pt.Bone);
				return;
			}
			if (Momentum * 2.f > Flock->HeavyHitImpulse * 0.15f) Wound(Pt.P, Rel, Other);
			break;
		}
	}
	NearbyVel = MoveTemp(Seen);
	NearbyPos = MoveTemp(SeenPos);
}

void ABird::PushApart(const FVector& Delta, bool bKillApproach)
{
	Pos += Delta;
	if (bKillApproach && !Delta.IsNearlyZero())
	{
		const FVector N = Delta.GetSafeNormal();
		const float Into = FVector::DotProduct(Vel, N);
		if (Into < 0.f) Vel -= N * Into;
		if (IsFlying() && State != EBirdState::TakingOff)
		{
			Speed = FMath::Max(Vel.Size(), S.MinSpeed * 0.6f);
			if (!Horizontal(Vel).IsNearlyZero()) Yaw = Vel.Rotation().Yaw;
		}
	}
	if (State == EBirdState::Walking)
	{
		Spot = Pos - FVector::UpVector * BodyH();
		Timer = Rand(S.PerchTime) * 0.5f;
		bShuffle = false;
		SetState(EBirdState::Perched);
	}
}

void ABird::PushVisuals(float Dt)
{
	if (State == EBirdState::Dead || State == EBirdState::Unplaced) return;
	const bool bAir = IsFlying();
	FlightW = Approach(FlightW, bAir ? 1.f : 0.f, Dt * (bAir ? 6.f : 3.5f));
	if (!bAir)
	{
		HoverW = Approach(HoverW, 0.f, Dt * 2.f);
		FlapW = Approach(FlapW, 0.f, Dt * 2.f);
		FlapPhase += FlapRate() * Dt * FlightW;
	}
	// every wingbeat a slightly different depth
	const float Frac = FMath::Frac(FlapPhase);
	if (Frac < LastFlapFrac) { FlapAmp = FlapAmpNext; FlapAmpNext = 1.f - Rng.FRand() * S.FlapHzVariation * 0.4f; }
	LastFlapFrac = Frac;
	const float Amp = FMath::Lerp(FlapAmp, FlapAmpNext, Frac);
	// far birds standing about: bones updated at a reduced rate (interpolated); never in flight or during a task
	const bool bWantURO = !bAir && bMid && Task == EBirdTask::None && !HeldFish;
	if (bWantURO != bUROOn && Mesh) { Mesh->bEnableUpdateRateOptimizations = bWantURO; bUROOn = bWantURO; }
	// one transform update per frame: the mesh's wingbeat offset is written first (no propagation), then the actor move
	// carries it to the mesh; an unchanged actor (a bird standing still) is not moved at all
	const FQuat ActorQ = FRotator(Pitch, Yaw, Bank).Quaternion();
	const bool bMoved = !Pos.Equals(PushedPos, 0.01) || !ActorQ.Equals(PushedQ, 1e-6f);
	bool bRelSet = false;
	FVector RelLoc = FVector::ZeroVector;
	FQuat RelQ = FQuat::Identity;
	// the body is not carried along a smooth path: it heaves, surges and pitches with every wingbeat (forces integrated in
	// BuildStrokeTables) and rides the turbulence. Applied to the mesh only, so spots / separation / sweeps use the smooth path.
	float StabPitch = 0.f;
	if (FlightW > 0.01f && Mesh)
	{
		auto Tab = [&](const float* Tb)
		{
			const float X = Frac * StrokeN;
			const int32 I0 = FMath::FloorToInt(X) % StrokeN;
			return FMath::Lerp(Tb[I0], Tb[(I0 + 1) % StrokeN], X - FMath::FloorToFloat(X));
		};
		const float Fh = FMath::Max(FlapRate(), 0.5f);
		const float Wb = FlightW * FMath::Clamp(FlapW + HoverW, 0.f, 1.f) * Amp;
		const float G2 = G / (Fh * Fh);
		float Heave = Tab(HeaveTab) * G2 * Wb * (1.f + 0.25f * HoverW);
		const float Surge = Tab(SurgeTab) * G2 * Wb * (1.f - HoverW);
		float PitchOsc = Tab(PitchTab) * S.StrokePitchDeg * Wb * (1.f + HoverW);
		// turbulence: three incommensurate components per bird, felt most in a glide (flapping damps it)
		const float Gw = FlightW * (1.f - 0.6f * FlapW);
		const float Tm = FlapT;
		const float Ga = 0.55f * FMath::Sin(Tm * 2.1f + TurbA) + 0.3f * FMath::Sin(Tm * 5.3f + TurbB) + 0.15f * FMath::Sin(Tm * 11.f + TurbC);
		const float Gb = 0.6f * FMath::Sin(Tm * 1.7f + TurbB) + 0.4f * FMath::Sin(Tm * 4.4f + TurbC);
		const float Gc = 0.6f * FMath::Sin(Tm * 2.6f + TurbC) + 0.4f * FMath::Sin(Tm * 6.1f + TurbA);
		const float GustRoll = S.GustRollDeg * Ga * Gw;
		const float GustPitch = S.GustRollDeg * 0.5f * Gb * Gw;
		Heave += S.GustHeaveCm * Scale * Gc * Gw;
		PitchOsc += GustPitch;
		const FVector Off = ActorQ.UnrotateVector(FVector(0.f, 0.f, Heave)) + FVector(Surge, 0.f, 0.f);
		RelQ = FRotator(PitchOsc, 0.f, GustRoll).Quaternion();
		RelLoc = RelQ.RotateVector(FVector(0.f, 0.f, -BodyH())) + Off;
		bRelSet = true;
		bMeshOffset = true;
		StabPitch = -PitchOsc * 0.8f;		// gaze stabilisation: the neck keeps the head level
	}
	else if (bMeshOffset && Mesh)
	{
		RelLoc = FVector(0.f, 0.f, -BodyH());
		bRelSet = true;
		bMeshOffset = false;
	}
	if (bMoved)
	{
		if (bRelSet)
		{
			Mesh->SetRelativeLocation_Direct(RelLoc);
			Mesh->SetRelativeRotation_Direct(RelQ.Rotator());
		}
		SetActorLocationAndRotation(Pos, ActorQ);
		PushedPos = Pos;
		PushedQ = ActorQ;
	}
	else if (bRelSet) Mesh->SetRelativeLocationAndRotation(RelLoc, RelQ);
	if (Anim)
	{
		FBirdAnimParams P;
		P.Flight = FlightW * (1.f - 0.85f * FoldW);
		P.Flap = FlapW * Amp;
		P.Hover = HoverW;
		P.FlapPhase = Frac;
		P.Walk = WalkW;
		P.WalkPhase = FMath::Frac(WalkPhase);
		P.Beak = Beak;
		P.LookYaw = LookYaw;
		P.LookPitch = LookPitch + StabPitch;
		P.BeakOpenDeg = S.BeakOpenDeg;
		Anim->SetParams(P);
	}
	PlaceHeldFish();
	if (CVarBirdDebug.GetValueOnGameThread() > 0)
	{
		UWorld* W = GetWorld();
		DrawDebugSphere(W, Pos, SeparationRadius(), 12, IsFlying() ? FColor::Cyan : FColor::Green, false, -1.f, 0, 0.5f);
		if (bHasSpot)
		{
			DrawDebugLine(W, Pos, Spot, FColor::Yellow, false, -1.f, 0, 0.5f);
			DrawDebugSphere(W, Spot, 6.f, 8, FColor::Yellow, false, -1.f);
		}
	}
}

void ABird::SetShadowCasting(bool bOn)
{
	bShadowOn = bOn;
	if (Mesh) Mesh->SetCastShadow(bOn);
}

bool ABird::CanThinkSlowly() const
{
	return State == EBirdState::Perched && Task == EBirdTask::None && !HeldFish;
}

void ABird::Startle(FVector From)
{
	if (State == EBirdState::Dead || State == EBirdState::Unplaced) return;
	FleeFrom = From;
	if (State == EBirdState::Perched || State == EBirdState::Walking) StartFlight(true);
	else
	{
		if (State == EBirdState::Landing) { ++AbortedLandings; ReleaseSpot(); SetState(EBirdState::Flying); }
		bFleeing = true;
	}
}

// ---------------------------------------------------------------------------------------------------- damage / death
void ABird::Kill(FVector HitLocation, FVector Impulse, AActor* Killer, FName Bone)
{
	if (State == EBirdState::Dead) return;
	FBirdHitInfo HitInfo = MakeHitInfo(HitLocation, Impulse, Killer, Bone, true);
	if (HeldFish) DropFish(true);
	EndTask();
	const FVector V0 = Vel;
	DeathZ = Pos.Z;
	ReleaseSpot();
	SetState(EBirdState::Dead);
	if (Flock) Flock->NotifyKill();
	if (HitLocation.IsZero()) HitLocation = Pos;
	// ragdoll with the runtime physics asset: the live collision sphere goes, the mesh gets its bodies
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->bEnableUpdateRateOptimizations = false;
	Mesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;	// follow the bodies even off screen
	Mesh->SetCollisionObjectType(ECC_PhysicsBody);
	Mesh->SetCollisionResponseToAllChannels(ECR_Block);
	Mesh->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
	Mesh->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
	Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Mesh->SetNotifyRigidBodyCollision(false);
	if (Ragdoll) Mesh->SetPhysicsAsset(Ragdoll, true);		// (re)creates the bodies now that collision is on
	else Mesh->RecreatePhysicsState();
	Mesh->SetAllBodiesSimulatePhysics(true);
	Mesh->SetSimulatePhysics(true);
	Mesh->WakeAllRigidBodies();
	Mesh->SetAllPhysicsLinearVelocity(V0 + Impulse * 0.3f);
	if (Bone.IsNone()) Bone = Mesh->FindClosestBone(HitLocation, nullptr, 0.f, true);
	if (!Bone.IsNone()) Mesh->AddImpulse(Impulse * 0.7f, Bone, true);
	Mesh->bPauseAnims = true;
	Mesh->bComponentUseFixedSkelBounds = false;		// a ragdoll's bounds must follow its bodies
	Mesh->SetBoundsScale(1.6f);
	if (Flock)
	{
		const float Energy = FMath::Clamp(Impulse.Size() / 900.f, 0.5f, 1.6f);
		const int32 Immediate = FMath::RoundToInt(S.DeathFeathers * 0.6f);
		Flock->SpawnFeathers(this, HitLocation, Impulse.IsNearlyZero() ? FVector::UpVector : Impulse.GetSafeNormal(), Immediate, Energy, &V0);
		ShedTotal = ShedLeft = S.DeathFeathers - Immediate;
		DeadT = 0.f;
		Flock->StartleNear(Pos, 2500.f, this);
		if (Flock->CorpseLifetime > 0.f) SetLifeSpan(Flock->CorpseLifetime);
	}
	ResolveBleed(HitInfo);
	OnBirdDied.Broadcast(this, Killer);
}

void ABird::Wound(FVector HitLocation, FVector Direction, AActor* HitBy)
{
	if (State == EBirdState::Dead) return;
	const float Now = GetWorld()->GetTimeSeconds();
	if (Now - LastHitTime < 0.4f) { bPendingHit = false; return; }
	LastHitTime = Now;
	if (HitLocation.IsZero()) HitLocation = Pos;
	FBirdHitInfo HitInfo = MakeHitInfo(HitLocation, Direction, HitBy, NAME_None, false);
	ResolveBleed(HitInfo);
	if (Flock) Flock->SpawnFeathers(this, HitLocation, Direction.GetSafeNormal(), S.HitFeathers, 0.6f);
	Startle(HitLocation - Direction.GetSafeNormal() * 100.f);
	if (Species == EBirdSpecies::Gull) Cry(0.5f, 1.f);
}

float ABird::TakeDamage(float Damage, FDamageEvent const& DamageEvent, AController* EventInstigator, AActor* DamageCauser)
{
	const float Actual = Super::TakeDamage(Damage, DamageEvent, EventInstigator, DamageCauser);
	if (State == EBirdState::Dead || Damage <= 0.f) return Actual;
	FVector HitLoc = Pos;
	FVector Dir = DamageCauser ? (Pos - DamageCauser->GetActorLocation()).GetSafeNormal() : FVector::UpVector;
	FName Bone = NAME_None;
	if (DamageEvent.IsOfType(FPointDamageEvent::ClassID))
	{
		const FPointDamageEvent& PE = static_cast<const FPointDamageEvent&>(DamageEvent);
		if (!PE.HitInfo.ImpactPoint.IsZero()) HitLoc = PE.HitInfo.ImpactPoint;
		if (!PE.ShotDirection.IsNearlyZero()) Dir = PE.ShotDirection.GetSafeNormal();
		Bone = PE.HitInfo.BoneName;
	}
	const bool bLethal = (Flock && Damage >= Flock->LethalDamage) || (Flock && DamageCauser && Flock->IsLethal(DamageCauser));
	{
		FBirdHitInfo H;
		H.Source = EBirdHitSource::Damage;
		H.Damage = Damage;
		H.Object = DamageCauser;
		H.Location = HitLoc;
		H.Direction = Dir;
		H.Bone = Bone;
		H.bLethalObject = Flock && DamageCauser && Flock->IsLethal(DamageCauser);
		if (DamageCauser)
		{
			H.ObjectForward = DamageCauser->GetActorForwardVector();
			if (UPrimitiveComponent* RC = Cast<UPrimitiveComponent>(DamageCauser->GetRootComponent()))
			{
				H.Component = RC;
				const FVector OV = RC->IsSimulatingPhysics() ? RC->GetPhysicsLinearVelocity() : DamageCauser->GetVelocity();
				H.Speed = (OV - Vel).Size();
				if (RC->IsSimulatingPhysics()) H.Momentum = H.Speed * RC->GetMass();
			}
		}
		H.Time = GetWorld()->GetTimeSeconds();
		SetHitContext(H);
	}
	if (bLethal) Kill(HitLoc, Dir * FMath::Clamp(Damage * 40.f, 300.f, 1500.f), DamageCauser, Bone);
	else Wound(HitLoc, Dir, DamageCauser);
	return Damage;
}

void ABird::OnMeshHit(UPrimitiveComponent* HitComp, AActor* Other, UPrimitiveComponent* OtherComp, FVector NormalImpulse, const FHitResult& Hit)
{
	if (State == EBirdState::Dead || !Flock || !Other || Cast<ABird>(Other)) return;
	// the contact is reported after the solver: use the velocity the object had before it (last probe), or the impulse
	FVector OtherVel = OtherComp ? OtherComp->GetPhysicsLinearVelocity() : FVector::ZeroVector;
	if (const FVector* Prev = OtherComp ? NearbyVel.Find(OtherComp) : nullptr)
	{
		if (Prev->SizeSquared() > OtherVel.SizeSquared()) OtherVel = *Prev;
	}
	const float Imp = NormalImpulse.Size();
	const float OtherMass = OtherComp && OtherComp->IsSimulatingPhysics() ? OtherComp->GetMass() : 0.f;
	float Rel = (OtherVel - Vel).Size();
	if (OtherMass > 0.f) Rel = FMath::Max(Rel, Imp / OtherMass);
	if (OtherVel.IsNearlyZero()) OtherVel = -NormalImpulse.GetSafeNormal() * Rel;
	const bool bLethalObj = Flock->IsLethal(Other) && Rel > Flock->LethalMinSpeed;
	if (ProbeDebugFrames > 0)
	{
		UE_LOG(LogTemp, Display, TEXT("BIRDPROBE hit-event %s rel=%.0f imp=%.0f mass=%.2f lethalobj=%d"), *GetNameSafe(OtherComp), Rel, Imp, OtherMass, bLethalObj ? 1 : 0);
	}
	{
		FBirdHitInfo H;
		H.Source = bLethalObj ? EBirdHitSource::LethalObject : EBirdHitSource::PhysicsImpact;
		H.Object = Other;
		H.Component = OtherComp;
		H.Location = Hit.ImpactPoint;
		H.Direction = (OtherVel - Vel).GetSafeNormal();
		H.Speed = Rel;
		H.Momentum = Rel * OtherMass;
		H.ObjectForward = OtherComp ? OtherComp->GetForwardVector() : Other->GetActorForwardVector();
		H.Bone = Hit.BoneName;
		H.bLethalObject = Flock->IsLethal(Other);
		H.Time = GetWorld()->GetTimeSeconds();
		SetHitContext(H);
	}
	if (bLethalObj || (Imp >= Flock->HeavyHitImpulse && Rel >= Flock->HeavyHitMinSpeed))
	{
		Kill(Hit.ImpactPoint, OtherVel.GetSafeNormal() * FMath::Clamp(Rel * 0.5f, 250.f, 1500.f), Other, Hit.BoneName);
	}
	else if (Imp > Flock->HeavyHitImpulse * 0.15f)
	{
		Wound(Hit.ImpactPoint, OtherVel.GetSafeNormal(), Other);
	}
}

// ---------------------------------------------------------------------------------------------------- blood
FBirdHitInfo ABird::MakeHitInfo(const FVector& Location, const FVector& Dir, AActor* Object, FName Bone, bool bLethal)
{
	const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	FBirdHitInfo H;
	if (bPendingHit && FMath::IsNearlyEqual(PendingHit.Time, Now))
	{
		H = PendingHit;		// detailed description from the detection path that triggered this kill / wound
	}
	else
	{
		H.Source = EBirdHitSource::Manual;
		H.Object = Object;
		if (Object) H.ObjectForward = Object->GetActorForwardVector();
		H.bLethalObject = Object && Flock && Flock->IsLethal(Object);
	}
	bPendingHit = false;
	H.Bird = this;
	if (H.Location.IsZero()) H.Location = Location.IsZero() ? Pos : Location;
	if (H.Direction.IsNearlyZero() || H.Source == EBirdHitSource::Manual) H.Direction = Dir.IsNearlyZero() ? FVector::DownVector : Dir.GetSafeNormal();
	if (H.Bone.IsNone()) H.Bone = Bone;
	if (H.Object == nullptr) H.Object = Object;
	H.bLethal = bLethal;
	H.Time = Now;
	const FVector F = H.ObjectForward.GetSafeNormal();
	H.AlignmentDeg = F.IsNearlyZero() ? 0.f : FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(F, H.Direction), -1.f, 1.f)));
	const FVector N = (H.Location - Pos).GetSafeNormal();
	H.IncidenceDeg = N.IsNearlyZero() ? 90.f : FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(FMath::Abs(FVector::DotProduct(H.Direction, N)), 0.f, 1.f)));
	return H;
}

void ABird::ResolveBleed(FBirdHitInfo& Hit)
{
	bool bBleed = false;
	const int32 Mode = CVarBirdBlood.GetValueOnGameThread();
	if (Mode >= 2) bBleed = true;
	else if (Mode == 1)
	{
		if (Flock && Flock->BleedCondition.IsBound()) bBleed = Flock->BleedCondition.Execute(Hit);
		else bBleed = Flock ? Flock->DefaultShouldBleed(Hit) : Hit.bLethal;
	}
	if (bBleed)
	{
		++Bleeds;
		const float R = S.BloodStainRadius * Scale * (Hit.bLethal ? 1.f : 0.65f);
		const FString BoneStr = Hit.Bone.ToString();
		const bool bWing = BoneStr.Contains(TEXT("arm")) || BoneStr.Contains(TEXT("hand"));
		FVector Entry = Hit.Location, Exit = Hit.Location;
		bool bThrough = false;
		if (!bWing)
		{
			// the stain goes where the line of travel enters the body (and leaves it, for a spear through the bird)
			const FVector D = Hit.Direction;
			const FVector M = Hit.Location - Pos;
			const float Rb = BodyR() * 0.95f;
			const float Bq = FVector::DotProduct(M, D);
			const float Disc = Bq * Bq - (M.SizeSquared() - Rb * Rb);
			if (Disc > 0.f)
			{
				const float Sq = FMath::Sqrt(Disc);
				Entry = Hit.Location + D * (-Bq - Sq);
				Exit = Hit.Location + D * (-Bq + Sq);
				bThrough = true;
			}
			else
			{
				Entry = Pos + (Hit.Location - Pos).GetSafeNormal() * Rb;
			}
		}
		AddBloodStain(Entry, Hit.Direction, R, true, bWing ? Hit.Bone : NAME_None);
		if (bThrough && Hit.bLethal && (Hit.Source == EBirdHitSource::LethalObject || Hit.bLethalObject)) AddBloodStain(Exit, Hit.Direction, R * 0.7f, false);
	}
	OnBirdHit.Broadcast(Hit, bBleed);
}

void ABird::AddBloodStain(FVector WorldLocation, FVector Direction, float RadiusCm, bool bSplat, FName Bone)
{
	if (!Mesh || !Mesh->GetSkinnedAsset()) return;
	if (RadiusCm <= 0.f) RadiusCm = S.BloodStainRadius * Scale;
	int32 BI = Bone.IsNone() ? INDEX_NONE : Mesh->GetBoneIndex(Bone);
	if (BI == INDEX_NONE) BI = Mesh->GetBoneIndex(Mesh->FindClosestBone(WorldLocation));
	if (BI == INDEX_NONE) return;
	// stain centre in the mesh's reference pose (= PreSkinnedPosition in the material): it then follows the body in any pose
	const FReferenceSkeleton& Ref = Mesh->GetSkinnedAsset()->GetRefSkeleton();
	FTransform RefCS = FTransform::Identity;
	for (int32 b = BI; b != INDEX_NONE; b = Ref.GetParentIndex(b)) RefCS = RefCS * Ref.GetRefBonePose()[b];
	const FVector Local = Mesh->GetBoneTransform(BI).InverseTransformPosition(WorldLocation);
	const FVector P = RefCS.TransformPosition(Local);
	const float CompScale = FMath::Max(Mesh->GetComponentScale().X, 0.01f);
	BloodStains[NextStain] = FLinearColor(P.X, P.Y, P.Z, RadiusCm / CompScale);
	NextStain = (NextStain + 1) % 4;
	for (UMaterialInstanceDynamic* M : Mids)
	{
		if (!M) continue;
		for (int32 i = 0; i < 4; ++i) M->SetVectorParameterValue(FName(*FString::Printf(TEXT("BloodStain%d"), i)), BloodStains[i]);
	}
	if (bSplat && Flock) Flock->SpawnBloodSplat(WorldLocation, Direction.IsNearlyZero() ? FVector::DownVector : Direction.GetSafeNormal(), S.BloodVFXScale * Scale);
}

void ABird::ClearBloodStains()
{
	for (FLinearColor& St : BloodStains) St = FLinearColor(0, 0, 0, 0);
	NextStain = 0;
	for (UMaterialInstanceDynamic* M : Mids)
	{
		if (!M) continue;
		for (int32 i = 0; i < 4; ++i) M->SetVectorParameterValue(FName(*FString::Printf(TEXT("BloodStain%d"), i)), BloodStains[i]);
	}
}

// ---------------------------------------------------------------------------------------------------- feeding
void ABird::CacheBill()
{
	// the bill in the head bone's space, from the reference pose: food is held / taken there whatever the head does
	HeadIdx = Mesh ? Mesh->GetBoneIndex(TEXT("head")) : INDEX_NONE;
	if (HeadIdx == INDEX_NONE || !Mesh->GetSkinnedAsset()) return;
	const FReferenceSkeleton& Ref = Mesh->GetSkinnedAsset()->GetRefSkeleton();
	FTransform HeadRef = FTransform::Identity;
	for (int32 b = HeadIdx; b != INDEX_NONE; b = Ref.GetParentIndex(b)) HeadRef = HeadRef * Ref.GetRefBonePose()[b];
	BillInHead = HeadRef.InverseTransformPosition(S.BillBase);
	BillDirInHead = HeadRef.InverseTransformVectorNoScale(FVector::ForwardVector).GetSafeNormal();
	LatInHead = HeadRef.InverseTransformVectorNoScale(FVector::LeftVector).GetSafeNormal();
	UpInHead = HeadRef.InverseTransformVectorNoScale(FVector::UpVector).GetSafeNormal();
}

FVector ABird::BillPoint(float Along) const
{
	if (HeadIdx == INDEX_NONE || !Mesh) return Pos + FRotator(0, Yaw, 0).Vector() * BodyR();
	const FTransform H = Mesh->GetBoneTransform(HeadIdx);
	return H.TransformPosition(BillInHead + BillDirInHead * (S.BillLength * Along));
}

FVector ABird::BillDir() const
{
	if (HeadIdx == INDEX_NONE || !Mesh) return FRotator(Pitch, Yaw, 0).Vector();
	return Mesh->GetBoneTransform(HeadIdx).TransformVectorNoScale(BillDirInHead).GetSafeNormal();
}

FVector ABird::HeadLat() const
{
	if (HeadIdx == INDEX_NONE || !Mesh) return FRotator(0, Yaw, 0).Quaternion().GetRightVector();
	return Mesh->GetBoneTransform(HeadIdx).TransformVectorNoScale(LatInHead).GetSafeNormal();
}

FVector ABird::HeadUp() const
{
	if (HeadIdx == INDEX_NONE || !Mesh) return FVector::UpVector;
	return Mesh->GetBoneTransform(HeadIdx).TransformVectorNoScale(UpInHead).GetSafeNormal();
}

void ABird::EndTask()
{
	if (ABirdFish* F = FoodTarget.Get())
	{
		if (F->Claimant.Get() == this) F->Claimant = nullptr;
		// a meal interrupted half way: what is on the ground is left for the scavengers
		if (F->FishState == EBirdFishState::Dropped) { F->FishState = EBirdFishState::Remains; F->SetLifeSpan(300.f); }
	}
	FoodTarget = nullptr;
	Task = EBirdTask::None;
	TaskT = 0.f;
	bTaskLook = false;
	TaskPitch = 0.f;
	if (BeakHold >= 0.f) BeakHold = -1.f;
}

bool ABird::GoFishing()
{
	if (!Flock || !S.bFishes || HeldFish || IsDead() || Task != EBirdTask::None || State == EBirdState::Unplaced) return false;
	FVector P;
	if (!Flock->PickWaterPoint(Pos, S.FishingRange, 150.f, Rng, P)) return false;
	HuntPoint = P;
	WaterZ = P.Z;
	HuntHeight = Rng.FRandRange(300.f, 650.f);
	Task = EBirdTask::FishHunt;
	TaskT = 0.f;
	Dives = 0;
	FishTrip = 0.f;
	if (State == EBirdState::Landing) { ReleaseSpot(); SetState(EBirdState::Flying); }
	else if (State == EBirdState::Perched || State == EBirdState::Walking) StartFlight(false);
	return true;
}

void ABird::Plunge()
{
	const FVector At(Pos.X, Pos.Y, WaterZ);
	OnBirdPlunge.Broadcast(this, At);
	if (Flock)
	{
		if (UNiagaraSystem* Sys = Flock->SplashSystem.LoadSynchronous())
			UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Sys, At, FRotator::ZeroRotator, FVector(Scale), true, true, ENCPoolMethod::AutoRelease);
	}
	++Dives;
	Task = EBirdTask::FishUnder;
	TaskT = 0.f;
	Vel *= 0.3f;		// water stops a plunging bird within a body length or two
}

bool ABird::UpdateAirTask(float Dt)
{
	if (Task == EBirdTask::None) return false;
	TaskT += Dt;
	FishTrip += Dt;
	auto Integrate = [&]()
	{
		Speed = Vel.Size();
		Pos += Vel * Dt;
	};
	switch (Task)
	{
	case EBirdTask::FishHunt:
	{
		if (State != EBirdState::Flying) return false;
		// fast level approach (10-12 m/s measured) a little below the hover height, then a swoop up into the hover that trades
		// the speed for height (v^2 / 2g) instead of braking dead
		Waypoint = HuntPoint + FVector(0, 0, HuntHeight - 150.f);
		const float BrakeDist = Speed * Speed / (2.f * (G * 0.45f + S.Acceleration)) + 60.f;
		const FVector ToW = Horizontal(Waypoint - Pos);
		// in reach, or passing it (a bank-limited turn would otherwise orbit the point): swoop into the hover from here
		const bool bPassing = ToW.Size() < 1200.f && FVector::DotProduct(ToW, Horizontal(Vel)) < 0.f;
		if (ToW.Size() < FMath::Max(BrakeDist, 450.f) || bPassing || FishTrip > 40.f)
		{
			if (FishTrip > 40.f) { EndTask(); return false; }
			Task = EBirdTask::FishHover;
			TaskT = 0.f;
			TaskDur = Rng.FRandRange(1.5f, 5.f);
			HoverMoves = Rng.RandRange(0, 2);
			// some dives are made straight out of the swoop, at the top of the climb, without settling into a hover
			bDirectDive = Rng.FRand() < 0.35f;
			if (bDirectDive) HoverMoves = 0;
		}
		return false;
	}
	case EBirdTask::FishHover:
	{
		// hover-hunting: body tilted up, tail fanned, head locked on the water below
		// swoop up: climbing bleeds speed (gravity along the path) while the wings brake; then a stationary hover, fast
		// shallow wingbeats, body tilted up, bill pointing ~76 deg down, head held still over the water
		const FVector HoverP = HuntPoint + FVector(0, 0, HuntHeight);
		const FVector ToP = HoverP - Pos;
		FVector TV = ToP * 1.6f;
		TV = FVector(TV.X, TV.Y, 0.f).GetClampedToMaxSize(FMath::Max(Horizontal(Vel).Size(), 250.f)) + FVector(0, 0, FMath::Clamp(TV.Z, -150.f, 400.f));
		const float Climb = FMath::Max(Vel.Z, 0.f);
		HoverFlight(Dt, TV, S.Acceleration * 1.3f + G * 0.45f * FMath::Clamp(Climb / 300.f, 0.f, 1.f));
		HoverW = Approach(HoverW, 1.f, Dt * 2.5f);
		bTaskLook = true;
		TaskLookPitch = -FMath::Lerp(20.f, 95.f, FMath::Clamp(HoverW, 0.f, 1.f));
		TaskLookYaw = 0.f;
		TaskLookRate = 10.f;
		Integrate();
		if (bDirectDive && TaskT > 0.35f && Vel.Z < 60.f && Horizontal(Pos - HoverP).Size() < 250.f)
		{
			Task = EBirdTask::FishDive;
			TaskT = 0.f;
			DiveStartZ = Pos.Z;
			return true;
		}
		if (TaskT > TaskDur && Horizontal(Vel).Size() < 80.f)
		{
			if (HoverMoves > 0)
			{
				// shift the hover a few metres and look again (as hover-hunting kingfishers do)
				--HoverMoves;
				FVector P2;
				if (Flock && Flock->PickWaterPoint(HuntPoint, 350.f, 150.f, Rng, P2)) HuntPoint = P2;
				HuntHeight = FMath::Clamp(HuntHeight + Rng.FRandRange(-120.f, 80.f), 200.f, 800.f);
				TaskT = 0.f;
				TaskDur = Rng.FRandRange(1.5f, 4.f);
				return true;
			}
			Task = EBirdTask::FishDive;
			TaskT = 0.f;
			DiveStartZ = Pos.Z;
		}
		return true;
	}
	case EBirdTask::FishDive:
	{
		// plunge (ballistic once begun): tip over head-down with a last downstroke, sweep the wings back and fall. Gravity does
		// the work - from 4 m the bird hits the water at ~8-9 m/s about 0.9 s later; the only steering is the small horizontal
		// correction that lands the bill on the spot. Air drag: terminal speed ~25 m/s with the wings folded.
		const FVector Target(HuntPoint.X, HuntPoint.Y, WaterZ);
		const float H = FMath::Max(Pos.Z - Target.Z, 1.f);
		const float Vz = -Vel.Z;
		const float TImpact = (-Vz + FMath::Sqrt(Vz * Vz + 2.f * G * H)) / G;
		const FVector HWant = Horizontal(Target - Pos) / FMath::Max(TImpact, 0.15f);
		const FVector HNow = Horizontal(Vel);
		const FVector HNew = HNow + (HWant.GetClampedToMaxSize(350.f) - HNow).GetClampedToMaxSize(600.f * Dt);
		float VzNew = Vel.Z - G * Dt;
		if (TaskT < 0.25f) VzNew -= 700.f * Dt * (1.f - TaskT / 0.25f);	// the last strokes push it down
		Vel = FVector(HNew.X, HNew.Y, VzNew);
		Vel -= Vel * (Vel.Size() * G / FMath::Square(2500.f)) * Dt;
		// the body rotates head-down quickly, then follows the velocity (beak first)
		// one continuous roll-over: the body pitches down with an ease-in / ease-out toward the velocity direction (which
		// itself turns down as the bird falls), the hover strokes fade and the wings sweep back as the speed builds
		const FRotator R = Vel.Rotation();
		const float PitchWant = FMath::Min(R.Pitch, -80.f * SmoothStep01(0.f, 0.45f, TaskT));
		const float PitchRate = FMath::Lerp(60.f, 330.f, SmoothStep01(0.f, 0.25f, TaskT));
		Pitch = Approach(Pitch, PitchWant, PitchRate * Dt);
		if (HNow.Size() > 30.f) Yaw = ApproachAngle(Yaw, R.Yaw, 180.f * Dt);
		Gamma = R.Pitch;
		Bank = Approach(Bank, 0.f, S.RollRateDeg * Dt);
		FlapW = Approach(FlapW, TaskT < 0.2f ? 1.f : 0.f, Dt * 3.f);
		HoverW = Approach(HoverW, 0.f, Dt * 2.5f);
		TaskLookPitch = FMath::Lerp(TaskLookPitch, 0.f, FMath::Min(1.f, Dt * 5.f));	// bill lines up with the body for entry
		TaskLookRate = 12.f;
		Integrate();
		if (Pos.Z - BodyH() * 0.25f <= WaterZ || TaskT > 4.f) Plunge();
		return true;
	}
	case EBirdTask::FishUnder:
	{
		// water is ~800 x denser than air: the dive stops within a body length or two, then buoyancy and wing strokes
		Vel *= FMath::Exp(-14.f * Dt);
		if (TaskT > 0.12f) Vel.Z += 1400.f * Dt;
		// turning back up under water: body swings round to climb out, wings open for the first strokes
		if (TaskT > 0.12f)
		{
			Pitch = Approach(Pitch, 55.f, 380.f * Dt);
			FlapW = Approach(FlapW, 1.f, Dt * 4.f);
			HoverW = Approach(HoverW, 1.f, Dt * 4.f);
		}
		Integrate();
		Pos.Z = FMath::Max(Pos.Z, WaterZ - BodyH() * 3.f);
		if (TaskT > 0.5f)
		{
			if (Rng.FRand() < S.FishingSuccess && Flock)
			{
				ABirdFish* F = GetWorld()->SpawnActor<ABirdFish>(ABirdFish::StaticClass(), FTransform(BillPoint(0.6f)));
				if (F)
				{
					F->Init(Flock->FishMesh.LoadSynchronous(), S.FishLength * Rng.FRandRange(0.8f, 1.2f), S.FishStruggleTime, Rng.RandHelper(1 << 30));
					F->Holder = this;
					F->FishState = EBirdFishState::Held;
					HeldFish = F;
					Flock->RegisterFood(F);
					OnBirdCaughtFish.Broadcast(this, F);
				}
			}
			Task = EBirdTask::FishEmerge;
			TaskT = 0.f;
			Vel = FVector(Vel.X, Vel.Y, FMath::Max(Vel.Z, 300.f));	// breaks out of the water steeply, beating hard
		}
		return true;
	}
	case EBirdTask::FishEmerge:
	{
		const FVector Home = Zone.IsValid() ? Horizontal(Zone->GetCenter() - Pos).GetSafeNormal() : FVector::ZeroVector;
		HoverFlight(Dt, FVector(0, 0, 340.f) + Home * FMath::Lerp(60.f, 450.f, FMath::Clamp(TaskT / 1.2f, 0.f, 1.f)), S.Acceleration * 2.f);
		HoverW = Approach(HoverW, 1.f, Dt * 5.f);
		Integrate();
		bTaskLook = false;
		if (Pos.Z > WaterZ + BodyH() + 110.f || TaskT > 2.f)
		{
			if (HeldFish) Task = EBirdTask::FishCarry;
			else if (Dives < 3 && Rng.FRand() < 0.6f && Flock && Flock->PickWaterPoint(Pos, 600.f, 150.f, Rng, HuntPoint))
			{
				// missed: hover again a little further along and dive again
				Task = EBirdTask::FishHover;
				TaskDur = Rng.FRandRange(1.f, 2.5f);
				HuntHeight = Rng.FRandRange(300.f, 550.f);
				TaskT = 0.f;
				return true;
			}
			else EndTask();
			ApproachDir = Home.IsNearlyZero() ? FRotator(0, Yaw, 0).Vector() : Home;
			SetState(EBirdState::TakingOff);
			StateTime = 0.6f;
		}
		return true;
	}
	default:
		if (Task == EBirdTask::ScavengeFly && (TaskT > 25.f || !FoodTarget.IsValid())) EndTask();
		return false;
	}
}

bool ABird::UpdatePerchedTask(float Dt)
{
	if (Task != EBirdTask::FishHold && Task != EBirdTask::FishPeck && Task != EBirdTask::ScavengeEat) return false;
	TaskT += Dt;
	bTurning = false;
	WalkW = Approach(WalkW, 0.f, Dt * 4.f);
	ThreatCheck -= Dt;
	if (ThreatCheck <= 0.f)
	{
		ThreatCheck = 0.12f;
		if (CheckThreats()) { StartFlight(true); return true; }
	}
	if (SettleT < 1.f) return true;
	bTaskLook = true;
	if (Task == EBirdTask::FishHold)
	{
		// hold the fish clear of the ground until it stops struggling; the head gives with every thrash
		if (!HeldFish) { EndTask(); return true; }
		BeakHold = 0.18f;
		TaskLookPitch = 6.f;
		TaskLookYaw = FishSwing.X * 0.25f;
		TaskLookRate = 18.f;
		TaskPitch = 0.f;
		if (HeldFish->IsStill())
		{
			Task = EBirdTask::FishPeck;
			TaskT = 0.f;
			bFishDropped = false;
			PeckTotal = PeckLeft = FMath::RoundToInt(Rand(S.PeckCount));
		}
		return true;
	}
	if (Task == EBirdTask::FishPeck)
	{
		if (!bFishDropped)
		{
			// bend down and let go of it in front of the feet
			TaskLookPitch = -78.f;
			TaskPitch = -7.f;
			TaskLookYaw = 0.f;
			TaskLookRate = 9.f;
			if (TaskT > 0.55f)
			{
				BeakHold = 0.7f;
				DropFish(false);
				bFishDropped = true;
				TaskT = 0.f;
			}
			return true;
		}
		ABirdFish* F = FoodTarget.Get();
		if (!F) { EndTask(); return true; }
		// pecks: strike (head down, bill opens and bites), then lift and work the bite down
		constexpr float Cycle = 0.75f;
		const float Ph = FMath::Fmod(TaskT, Cycle) / Cycle;
		const int32 Done = FMath::FloorToInt(TaskT / Cycle);
		TaskLookRate = 20.f;
		TaskLookYaw = 0.f;
		if (Ph < 0.33f)
		{
			TaskLookPitch = -88.f;
			TaskPitch = -9.f;
			BeakHold = Ph < 0.22f ? 0.6f : 0.f;
		}
		else
		{
			TaskLookPitch = -35.f;
			TaskPitch = -3.f;
			BeakHold = (Ph > 0.55f && Ph < 0.7f) ? 0.35f : 0.f;
			TaskLookYaw = 6.f * FMath::Sin(Ph * 20.f);
		}
		const int32 Left = PeckTotal - Done;
		if (Left < PeckLeft)
		{
			PeckLeft = Left;
			F->SetMeat(F->Meat - 0.5f / FMath::Max(PeckTotal, 1));
			F->Nudge(14.f);
		}
		if (PeckLeft <= 0)
		{
			F->FishState = EBirdFishState::Remains;
			F->Holder = nullptr;
			F->SetLifeSpan(300.f);
			OnBirdLeftRemains.Broadcast(this, F);
			FoodTarget = nullptr;
			EndTask();
			bLeaveAfterMeal = true;
			Timer = Rng.FRandRange(1.f, 2.5f);
			FishingTimer = Rand(S.FishingInterval);
		}
		return true;
	}
	// ScavengeEat (gull): face it, lower the head, open wide, take it, throw the head back and swallow it whole
	ABirdFish* F = FoodTarget.Get();
	if (!F) { EndTask(); return true; }
	const FVector ToF = Horizontal(F->GetActorLocation() - (Pos - FVector::UpVector * BodyH()));
	const float DY = FMath::FindDeltaAngleDegrees(Yaw, ToF.Rotation().Yaw);
	if (F->FishState == EBirdFishState::Remains)
	{
		if (FMath::Abs(DY) > 6.f && TaskT < 2.f)
		{
			Yaw = ApproachAngle(Yaw, ToF.Rotation().Yaw, 160.f * Dt);
			WalkPhase += 160.f * Dt / FMath::Max(S.TurnDegPerStepCycle, 10.f);
			WalkW = Approach(WalkW, 0.6f, Dt * 8.f);
			TaskT = 0.f;
			return true;
		}
		TaskLookPitch = -90.f;
		TaskPitch = -10.f;
		TaskLookYaw = 0.f;
		TaskLookRate = 10.f;
		if (TaskT > 0.25f) BeakHold = 1.f;
		if (TaskT > 0.5f)
		{
			F->FishState = EBirdFishState::Swallowed;
			F->Holder = this;
			HeldFish = F;
			TaskT = 0.f;
		}
		return true;
	}
	// swallowing: head up and back, the fish slides in head first
	TaskLookPitch = TaskT < 0.25f ? -40.f : 35.f;
	TaskPitch = TaskT < 0.25f ? -5.f : 4.f;
	TaskLookRate = 9.f;
	BeakHold = TaskT < 1.1f ? 1.f : 0.f;
	if (TaskT > 1.3f)
	{
		OnBirdSwallowed.Broadcast(this, F);
		HeldFish = nullptr;
		FoodTarget = nullptr;
		F->Destroy();
		EndTask();
		Timer = FMath::Max(Timer, Rng.FRandRange(2.f, 5.f));
	}
	return true;
}

void ABird::DropFish(bool bAsRemains)
{
	ABirdFish* F = HeldFish;
	if (!F) return;
	HeldFish = nullptr;
	F->Holder = nullptr;
	// lie it on its side on the ground below the bill
	const FVector From = BillPoint(0.6f);
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdFishDrop), false);
	if (Flock) Q.AddIgnoredActors(Flock->TraceIgnore());
	FHitResult H;
	FVector At = From;
	if (GetWorld()->LineTraceSingleByChannel(H, From + FVector(0, 0, 5.f), From - FVector(0, 0, 3000.f), ECC_Visibility, Q)) At = H.ImpactPoint;
	const FVector Along = Horizontal(HeadLat()).IsNearlyZero() ? FRotator(0, Yaw + 90.f, 0).Vector() : Horizontal(HeadLat()).GetSafeNormal();
	F->SetActorLocationAndRotation(At + FVector(0, 0, F->GetHalfThickness()), ABirdFish::Orientation(Along, FVector::UpVector));
	F->FishState = bAsRemains ? EBirdFishState::Remains : EBirdFishState::Dropped;
	if (bAsRemains) F->SetLifeSpan(300.f);
	else FoodTarget = F;
}

void ABird::PlaceHeldFish()
{
	ABirdFish* F = HeldFish;
	if (!F) return;
	if (F->FishState == EBirdFishState::Held)
	{
		// held crosswise in the bill, flat side forward, thrashing about the bill's up axis
		const FVector Lat = HeadLat(), Up = HeadUp(), Fwd = BillDir();
		FQuat Q = ABirdFish::Orientation(Lat, Fwd);
		Q = FQuat(Up, FMath::DegreesToRadians(FishSwing.X)) * FQuat(Lat, FMath::DegreesToRadians(FishSwing.Y)) * Q;
		const FVector Grip = BillPoint(0.62f) - Up * (0.25f * Scale);
		F->SetActorLocationAndRotation(Grip + Q.GetAxisX() * (F->GetLength() * 0.12f), Q);
	}
	else if (F->FishState == EBirdFishState::Swallowed)
	{
		// head first down the throat: from the bill tip back past the gape, shrinking out of sight
		const float T = FMath::Clamp((TaskT - 0.25f) / 0.85f, 0.f, 1.f);
		const FVector Fwd = BillDir();
		const FVector Tip = BillPoint(0.7f), Throat = BillPoint(-0.6f);
		const FQuat Q = ABirdFish::Orientation(Fwd, HeadLat());
		F->SetActorLocationAndRotation(FMath::Lerp(Tip + Fwd * (F->GetLength() * 0.3f), Throat, T), Q);
		F->SetActorScale3D(FVector(FMath::Max(1.f - T * 0.95f, 0.05f)));
	}
}

bool ABird::TryScavenge()
{
	if (!Flock || !S.bScavenges || Task != EBirdTask::None || IsDead()) return false;
	ABirdFish* F = Flock->FindFood(Pos, S.ScavengeRadius);
	if (!F) return false;
	const FVector FoodP = F->GetActorLocation();
	const FVector Foot = Pos - FVector::UpVector * BodyH();
	// stand so the lowered bill reaches it, approaching from our side; try a few angles for a free spot
	const float Reach = (S.BillBase.X + S.BillLength * 0.55f) * Scale;
	FVector From = Horizontal(Foot - FoodP).GetSafeNormal();
	if (From.IsNearlyZero()) From = FRotator(0, Yaw + 180.f, 0).Vector();
	const float Spacing = S.HalfSpan * Scale * 0.75f + BodyR() * 1.1f + 3.f;
	bool bOk = false;
	for (const float A : { 0.f, 45.f, -45.f, 90.f, -90.f, 180.f })
	{
		const FVector Cand = FoodP + From.RotateAngleAxis(A, FVector::UpVector) * Reach;
		if (Flock->IsSpotFree(this, Cand, Spacing)) { FoodApproach = FVector(Cand.X, Cand.Y, FoodP.Z - F->GetHalfThickness()); bOk = true; break; }
	}
	if (!bOk) return false;
	F->Claimant = this;
	FoodTarget = F;
	ScavengeTries = 0;
	if ((State == EBirdState::Perched || State == EBirdState::Walking) && Horizontal(Foot - FoodApproach).Size() < 450.f * Scale)
	{
		Task = EBirdTask::ScavengeWalk;
		if (Horizontal(Foot - FoodApproach).Size() < 12.f * Scale) { Task = EBirdTask::ScavengeEat; TaskT = 0.f; return true; }
		if (StartWalkTo(FoodApproach)) return true;
	}
	Task = EBirdTask::ScavengeFly;
	if (State == EBirdState::Perched || State == EBirdState::Walking) StartFlight(false);
	else if (State == EBirdState::Landing) { ReleaseSpot(); SetState(EBirdState::Flying); }
	return true;
}

bool ABird::StartWalkTo(const FVector& TargetFoot)
{
	if (!Flock) return false;
	UWorld* W = GetWorld();
	FCollisionQueryParams Q(SCENE_QUERY_STAT(BirdWalkTo), false);
	Q.AddIgnoredActors(Flock->TraceIgnore());
	const FVector Foot = Pos - FVector::UpVector * BodyH();
	FHitResult H;
	if (!W->LineTraceSingleByChannel(H, TargetFoot + FVector(0, 0, 40.f * Scale), TargetFoot - FVector(0, 0, 60.f * Scale), ECC_Visibility, Q)) return false;
	if (H.ImpactNormal.Z < 0.75f || FMath::Abs(H.ImpactPoint.Z - Foot.Z) > 30.f * Scale) return false;
	const FVector Target = H.ImpactPoint;
	for (const ABird* O : Flock->AllBirds())
	{
		if (!O || O == this || O->IsDead() || O->IsFlying() || O->GetState() == EBirdState::Unplaced) continue;
		const float Need = O->Settings().HalfSpan * O->GetScale() * 0.75f + O->BodyR() * 1.1f + 3.f;
		if (FMath::PointDistToSegment(O->GetFootSpot(), Foot, Target) < Need) return false;
	}
	if (W->SweepSingleByChannel(H, Pos, Target + FVector::UpVector * BodyH(), FQuat::Identity, ECC_Visibility, FCollisionShape::MakeSphere(BodyR() * 0.8f), Q)) return false;
	WalkTarget = Target;
	Spot = Target;
	bHasSpot = true;
	WalkSpeedCur = 0.f;
	bShuffle = false;
	SetState(EBirdState::Walking);
	return true;
}
