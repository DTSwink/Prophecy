#include "LeafFall.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Camera/PlayerCameraManager.h"
#include "Materials/MaterialInterface.h"
#include "UObject/UObjectIterator.h"
#include "HAL/IConsoleManager.h"
#include "CollisionQueryParams.h"
#include "GlobalWind.h"

static TAutoConsoleVariable<int32> CVarLeavesEnable(TEXT("leaves.Enable"), 1, TEXT("0 = no falling leaves"));
static TAutoConsoleVariable<int32> CVarLeavesAuto(TEXT("leaves.Auto"), 1, TEXT("1 = create a Leaf Fall automatically in worlds that contain the tree meshes"));
static TAutoConsoleVariable<float> CVarLeavesRate(TEXT("leaves.RateScale"), 1.f, TEXT("Multiplier on LeavesPerTreePerMinute (tests / screenshots)"));

namespace
{
	// Andersen, Pesavento & Wang 2005 (JFM 541) plate coefficients; lift slope and C_D0 for a real blade of aspect ratio ~2
	// (2D lift slope reduced by AR / (AR + 2); veined, serrated blade -> more friction drag than a smooth card)
	constexpr float RHO = 1.2f, GRAV = 9.81f, CT = 0.55f, CR = 0.35f, CD0 = 0.22f, CD90 = 1.6f;
	const TCHAR* LeafDir = TEXT("/Game/Prophecy/Ambient/Leaves");
	const TCHAR* ShapeNames[6] = { TEXT("Flat"), TEXT("Wavy"), TEXT("Cupped"), TEXT("Rolled"), TEXT("Twisted"), TEXT("Wet") };
	const FTransform Hidden(FQuat::Identity, FVector(0, 0, -1e6), FVector(0.001f));
	constexpr int32 NumCustom = 6;
}

ALeafFall::ALeafFall()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	TreeMeshes.Add(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/_mygame/pcg/tree1.tree1"))));
	TreeMeshes.Add(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(TEXT("/Game/_mygame/pcg/tree2.tree2"))));
	LeafMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(FString::Printf(TEXT("%s/MI_Leaf_Hornbeam.MI_Leaf_Hornbeam"), LeafDir)));
	for (const TCHAR* N : ShapeNames)
	{
		LeafMeshes.Add(TSoftObjectPtr<UStaticMesh>(FSoftObjectPath(FString::Printf(TEXT("%s/SM_Leaf_%s.SM_Leaf_%s"), LeafDir, N, N))));
	}
	Stats.ByFlight.Init(0, 6);
}

ALeafFall* ALeafFall::Find(const UObject* WorldContext, bool bCreate)
{
	UWorld* W = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!W) return nullptr;
	for (TActorIterator<ALeafFall> It(W); It; ++It) return *It;
	if (!bCreate) return nullptr;
	FActorSpawnParameters P;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	P.ObjectFlags |= RF_Transient;
	return W->SpawnActor<ALeafFall>(FVector::ZeroVector, FRotator::ZeroRotator, P);
}

void ALeafFall::BeginPlay()
{
	Super::BeginPlay();
	Rng.Initialize(int32(GetUniqueID() * 7919u + 17u));
	TreeSet.Reset();
	for (TSoftObjectPtr<UStaticMesh>& M : TreeMeshes) if (UStaticMesh* SM = M.LoadSynchronous()) TreeSet.Add(SM);
	ScanTrees();
	ScanTimer = 5.f;
	if (Trees.Num()) EnsureAssets();		// load the leaf meshes / material now, not at the first leaf (no hitch)
}

// ---------------------------------------------------------------------------------------------------- assets / pools
void ALeafFall::EnsureAssets()
{
	if (bAssetsReady) return;
	bAssetsReady = true;
	UMaterialInterface* Mat = LeafMaterial.LoadSynchronous();
	for (int32 s = 0; s < 6; ++s)
	{
		UStaticMesh* SM = LeafMeshes.IsValidIndex(s) ? LeafMeshes[s].LoadSynchronous() : nullptr;
		if (!SM && LeafMeshes.Num()) SM = LeafMeshes[0].LoadSynchronous();
		if (!SM) continue;
		UInstancedStaticMeshComponent* ISM = NewObject<UInstancedStaticMeshComponent>(this);
		ISM->SetMobility(EComponentMobility::Movable);
		ISM->SetStaticMesh(SM);
		if (Mat) ISM->SetMaterial(0, Mat);
		ISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		ISM->SetCanEverAffectNavigation(false);
		ISM->SetNumCustomDataFloats(NumCustom);
		ISM->bCastDynamicShadow = bCastShadows;
		ISM->SetCastShadow(bCastShadows);
		ISM->bAffectDistanceFieldLighting = false;
		ISM->SetCullDistances(0, int32(ActiveRadius * 1.5f));
		ISM->SetupAttachment(RootComponent);
		ISM->RegisterComponent();
		AddInstanceComponent(ISM);
		PoolComponents.Add(ISM);
		Pools[s].ISM = ISM;
		const FBox B = SM->GetBoundingBox();
		Pools[s].ZMin = B.Min.Z;
		Pools[s].ZMax = B.Max.Z;
	}
}

// ---------------------------------------------------------------------------------------------------- trees
void ALeafFall::RescanTrees() { ScanTrees(); }

void ALeafFall::AddTree(const FTransform& T, const FBox& LB, UPrimitiveComponent* C)
{
	// canopy = an ellipsoid over the upper ~60 % of the tree; leaves let go from its outer shell
	const FVector E = LB.GetExtent();
	const float H = LB.Max.Z - LB.Min.Z;
	const FVector S = T.GetScale3D().GetAbs();
	FTree Tr;
	Tr.Centre = T.TransformPosition(FVector(LB.GetCenter().X, LB.GetCenter().Y, LB.Min.Z + 0.68f * H));
	Tr.Radii = FVector(0.78f * E.X * S.X, 0.78f * E.Y * S.Y, 0.30f * H * S.Z);
	Tr.Base = T.GetLocation();
	Tr.Comp = C;
	Trees.Add(Tr);
}

void ALeafFall::ScanTrees()
{
	Trees.Reset();
	TreeComponents.Reset();
	if (TreeSet.Num() == 0) { Stats.Trees = 0; return; }
	UWorld* W = GetWorld();
	for (TObjectIterator<UStaticMeshComponent> It; It; ++It)
	{
		UStaticMeshComponent* C = *It;
		if (!IsValid(C) || C->GetWorld() != W || !C->IsRegistered()) continue;
		UStaticMesh* SM = C->GetStaticMesh();
		if (!SM || !TreeSet.Contains(SM)) continue;
		const FBox LB = SM->GetBoundingBox();
		if (UInstancedStaticMeshComponent* I = Cast<UInstancedStaticMeshComponent>(C))
		{
			const int32 N = I->GetInstanceCount();
			for (int32 i = 0; i < N; ++i)
			{
				FTransform T;
				if (I->GetInstanceTransform(i, T, true)) AddTree(T, LB, C);
			}
		}
		else AddTree(C->GetComponentTransform(), LB, C);
		TreeComponents.Add(C);
	}
	Stats.Trees = Trees.Num();
}

// ---------------------------------------------------------------------------------------------------- leaves
int32 ALeafFall::AllocLeaf()
{
	if (FreeLeaves.Num()) return FreeLeaves.Pop(EAllowShrinking::No);
	if (Leaves.Num() >= MaxLeaves) return INDEX_NONE;
	Leaves.AddDefaulted();
	return Leaves.Num() - 1;
}

void ALeafFall::InitLeaf(FLeafSim& L, ELeafCondition Cond, int32 ForceShape, int32 ForceFlight)
{
	FRandomStream& R = L.R;
	L.Condition = Cond;
	L.Len = R.FRandRange(LeafLengthCm.X, LeafLengthCm.Y) / 100.f;
	L.Wid = L.Len * R.FRandRange(0.58f, 0.68f);
	// leaf mass per area (dry matter + water): hornbeam ~50-75 g/m2 green, 35-55 g/m2 dry; a soaked leaf carries 2-3x its weight
	float Lma = 0.055f, Curl = 0.f, Twist = 0.f, Wet = 0.f;
	ELeafShape Shape = ELeafShape::Flat;
	const float S = FMath::Clamp(Season, 0.f, 1.f);
	auto Sgn = [&R]() { return R.FRand() < 0.5f ? -1.f : 1.f; };
	switch (Cond)
	{
	case ELeafCondition::Fresh:
		Lma = R.FRandRange(0.05f, 0.075f); Curl = R.FRandRange(0.f, 0.15f); Twist = R.FRandRange(-0.15f, 0.15f);
		L.Senescence = FMath::Clamp(0.05f + 0.35f * S + R.FRandRange(-0.12f, 0.15f), 0.f, 0.6f);
		break;
	case ELeafCondition::Dry:
	{
		Lma = R.FRandRange(0.035f, 0.055f);
		const float K = R.FRand();
		if (K < 0.35f) { Shape = ELeafShape::Wavy; Curl = R.FRandRange(0.25f, 0.45f); Twist = Sgn() * R.FRandRange(0.f, 0.35f); }
		else if (K < 0.6f) { Shape = ELeafShape::Cupped; Curl = R.FRandRange(0.5f, 0.75f); Twist = Sgn() * R.FRandRange(0.f, 0.4f); }
		else if (K < 0.75f) { Shape = ELeafShape::Rolled; Curl = R.FRandRange(0.8f, 0.95f); Twist = Sgn() * R.FRandRange(0.f, 0.3f); }
		else { Shape = ELeafShape::Twisted; Curl = R.FRandRange(0.28f, 0.45f); Twist = Sgn() * R.FRandRange(0.6f, 1.f); }
		L.Senescence = FMath::Clamp(0.55f + 0.35f * S + R.FRandRange(-0.1f, 0.15f), 0.3f, 1.f);
		break;
	}
	case ELeafCondition::Damp:
		Lma = R.FRandRange(0.05f, 0.07f); Wet = R.FRandRange(0.3f, 0.6f);
		Shape = R.FRand() < 0.6f ? ELeafShape::Flat : ELeafShape::Wavy; Curl = Shape == ELeafShape::Wavy ? R.FRandRange(0.15f, 0.3f) : R.FRandRange(0.f, 0.1f);
		Twist = R.FRandRange(-0.3f, 0.3f);
		L.Senescence = FMath::Clamp(0.4f + 0.45f * S + R.FRandRange(-0.15f, 0.1f), 0.2f, 1.f);
		break;
	default:
		Lma = R.FRandRange(0.05f, 0.07f); Wet = R.FRandRange(0.8f, 1.f); Shape = ELeafShape::Wet; Curl = R.FRandRange(0.f, 0.08f);
		Twist = R.FRandRange(-0.1f, 0.1f);
		L.Senescence = FMath::Clamp(0.5f + 0.45f * S + R.FRandRange(-0.15f, 0.1f), 0.3f, 1.f);
		break;
	}
	if (ForceShape >= 0 && ForceShape < 6) Shape = ELeafShape(ForceShape);
	L.Shape = Shape;
	L.Curl = Curl; L.Twist = Twist; L.Wet = Wet;
	L.Grip = R.FRandRange(0.8f, 2.2f);
	Lma *= 1.f + 2.2f * Wet;
	const float WEff = L.Wid * (1.f - 0.5f * Curl);
	L.Area = 0.72f * L.Len * WEff;
	L.Mass = Lma * 0.72f * L.Len * L.Wid;
	L.AddedMass = 8.f / 3.f * RHO * (L.Len * 0.5f) * FMath::Square(WEff * 0.5f);
	L.AR = L.Len * L.Len / L.Area;
	L.IStar = Lma / (2.f * RHO * WEff);		// APW dimensionless moment of inertia ~ rho_s h / (2 rho_f l), l = chord across the swing
	const float Vt = FMath::Sqrt(2.f * L.Mass * GRAV / (RHO * L.Area * CD90));
	L.WidthEff = FVector2D(WEff, Vt);
	L.Scale = L.Len * 100.f / 9.6f;		// meshes: a 9.6 cm leaf in a 10 cm cell
	// ---- regime (phase diagram of falling plates: flutter below I* ~0.25-0.4, tumbling above, chaotic in between)
	ELeafFlight F;
	if (Wet > 0.6f) F = ELeafFlight::Rock;
	else if (FMath::Abs(Twist) > 0.55f && Curl > 0.25f) F = ELeafFlight::Spiral;
	else if (Curl > 0.75f) F = ELeafFlight::Roll;
	else
	{
		// I* of the blade as it would be dry (a damp blade is heavier but limp: the water adds less to its stiffness-driven
		// overturning than to its weight). Thresholds ~1.3x the rigid-card values of APW / Field et al.: a real leaf is
		// flexible and its petiole damps the overturn, so the flutter range is wider (calibrated for a natural mix: ~27 %
		// flutter, 27 % chaotic, 16 % tumble, 12 % rock, 11 % spiral, 6 % roll with the default condition shares)
		const float Ist = (Lma / (1.f + 2.2f * Wet)) * (1.f + 0.6f * Wet) / (2.f * RHO * WEff) * (1.f + 0.6f * Curl) * R.FRandRange(0.8f, 1.25f);
		F = Ist < 0.55f ? ELeafFlight::Flutter : (Ist < 0.75f ? ELeafFlight::Chaotic : ELeafFlight::Tumble);
	}
	if (ForceFlight >= 0 && ForceFlight < 6) F = ELeafFlight(ForceFlight);
	L.Flight = F;
	// flutter frequency ~ Strouhal * U / l (0.7-1.4 Hz for these leaves), swing 40-65 deg; rocking is small and quicker
	L.Freq = R.FRandRange(0.75f, 1.25f) * 0.33f * Vt / FMath::Sqrt(WEff / 0.045f * 0.06f);
	L.Amp = FMath::DegreesToRadians((F == ELeafFlight::Flutter || F == ELeafFlight::Chaotic) ? R.FRandRange(40.f, 65.f) : R.FRandRange(8.f, 16.f));
	if (F == ELeafFlight::Rock) L.Freq *= 1.8f;
	L.Om = 2.f * PI * (F == ELeafFlight::Roll ? R.FRandRange(2.f, 4.f) : R.FRandRange(1.f, 2.2f)) * Sgn();		// tumbling 1-2 rev/s (APW up to ~40 rad/s)
	L.Psi = R.FRandRange(0.f, 2.f * PI);
	L.PsiRate = 0.f;
	L.Chi = R.FRandRange(-0.6f, 0.6f);
	L.Phase = R.FRandRange(0.f, 2.f * PI);
	L.Theta = L.Amp * FMath::Sin(L.Phase);
	L.bTumbling = F == ELeafFlight::Tumble || F == ELeafFlight::Roll;
	L.Tilt = FMath::DegreesToRadians(R.FRandRange(30.f, 50.f));
	L.PlaneRate = 2.f * PI * R.FRandRange(0.25f, 0.55f) * (Twist < 0.f ? -1.f : 1.f);
	L.Spin = F == ELeafFlight::Spiral ? (Twist < 0.f ? -1.f : 1.f) * 2.f * PI * R.FRandRange(0.6f, 1.6f) : 0.f;
	L.Sigma = R.FRandRange(0.f, 2.f * PI);
	L.Q = Orient(L);
	L.V = FVector(R.FRandRange(-0.1f, 0.1f), R.FRandRange(-0.1f, 0.1f), 0.f);
	L.Age = L.RestT = 0.f;
	L.Fade = 1.f;
	L.bLanded = false;
	L.bActive = true;
}

FVector ALeafFall::WindAt(const FVector& P) const
{
	const AGlobalWind* GW = GlobalWind.Get();
	return GW ? Wind + GW->GetWindAt(P) : Wind;
}

FQuat ALeafFall::Orient(const FLeafSim& L) const
{
	const FVector D(FMath::Cos(L.Psi), FMath::Sin(L.Psi), 0.f);
	const FVector B(-FMath::Sin(L.Psi), FMath::Cos(L.Psi), 0.f);			// up x d: the swing axis
	const FQuat Base(FVector::UpVector, L.Psi + 0.5f * PI + L.Chi);			// lying flat, long axis across the swing
	if (L.Flight == ELeafFlight::Spiral)
	{
		return FQuat(B, L.Tilt) * Base * FQuat(FVector::UpVector, L.Sigma);
	}
	const float Roll = L.bTumbling ? 0.f : 0.22f * L.Amp * FMath::Sin(2.f * L.Phase + 1.f);	// figure-of-eight secondary rock
	return FQuat(B, L.Theta) * FQuat(D, Roll) * Base;
}

void ALeafFall::StepAir(FLeafSim& L, float Dt)
{
	FRandomStream& R = L.R;
	// ---- orientation: the regime oscillator
	switch (L.Flight)
	{
	case ELeafFlight::Spiral:
		L.Psi += L.PlaneRate * Dt;
		L.Sigma += L.Spin * Dt;
		break;
	default:
		// the swing plane wanders slowly (3D flutter is a zig-zag whose plane drifts)
		L.Psi += L.PsiRate * Dt;
		L.PsiRate += (-0.8f * L.PsiRate) * Dt + R.FRandRange(-1.f, 1.f) * 1.04f * FMath::Sqrt(Dt);
		if (L.bTumbling)
		{
			// faster edge-on, slower broadside (the turning points of a tumbling plate)
			L.Theta += L.Om * (1.f + 0.35f * FMath::Cos(2.f * L.Theta)) * Dt;
			L.Phase += 2.f * PI * L.Freq * Dt;
			if (L.Flight == ELeafFlight::Chaotic && R.FRand() < Dt / 1.5f)
			{
				L.bTumbling = false;
				L.Theta = FMath::UnwindRadians(L.Theta + PI);
				L.Phase = FMath::Asin(FMath::Clamp(L.Theta / L.Amp, -1.f, 1.f));
			}
		}
		else
		{
			L.Phase += 2.f * PI * L.Freq * Dt;
			L.Theta = L.Amp * FMath::Sin(L.Phase);
			// chaotic: at the top of a swing it sometimes keeps going over
			if (L.Flight == ELeafFlight::Chaotic && FMath::Abs(FMath::Cos(L.Phase)) < 0.06f && R.FRand() < 0.15f)
			{
				L.bTumbling = true;
				L.Om = FMath::Abs(L.Om) * (FMath::Cos(L.Phase - 0.1f) >= 0.f ? 1.f : -1.f);
			}
		}
		break;
	}
	FQuat Qn = Orient(L);
	if (L.BlendT < 1.f)
	{
		// picked up from the ground: ease from the lying pose into the flight regime
		L.BlendT = FMath::Min(1.f, L.BlendT + Dt / 0.4f);
		Qn = FQuat::Slerp(L.LiftQ, Qn, FMath::SmoothStep(0.f, 1.f, L.BlendT));
	}
	FVector Axis; double Ang = 0.0;
	(Qn * L.Q.Inverse()).ToAxisAndAngle(Axis, Ang);
	if (Ang > PI) Ang -= 2.0 * PI;
	const FVector W = Axis * (Ang / FMath::Max(double(Dt), 1e-5));
	L.Q = Qn;
	// ---- translation: APW quasi-steady forces on the blade, normal added mass, relative to the air (SI)
	// wind slows toward the ground (log profile, forest floor roughness ~10 cm; 1 at ~10 m, ~0.5 at 1 m)
	const float Hm = FMath::Max(float(L.P.Z - L.GroundZ) * 0.01f, 0.f);
	const float Prof = FMath::Clamp(FMath::Loge(1.f + Hm / 0.1f) / FMath::Loge(101.f), 0.2f, 1.1f);
	const FVector Air = WindAt(L.P) * (0.01f * Prof);
	const FVector Vb = L.Q.UnrotateVector(L.V - Air);
	const FVector Wb = L.Q.UnrotateVector(W);
	const float Sp = Vb.Size() + 1e-6f;
	const float Un = Vb.Z;
	const FVector Vt2(Vb.X, Vb.Y, 0.f);
	const float Vtn = Vt2.Size() + 1e-6f;
	const FVector T = Vt2 / Vtn;
	const float Sin2 = FMath::Square(Un / Sp);
	FVector F = L.Mass * L.Q.UnrotateVector(FVector(0.f, 0.f, -GRAV));
	const float Cl = CT * 2.f * FMath::Sqrt(FMath::Max(Sin2 * (1.f - Sin2), 0.f));
	const float Cd = (CD0 + 0.5f * L.Curl) * (1.f - Sin2) + CD90 * Sin2 + Cl * Cl / (PI * L.AR * 0.8f);	// + induced drag
	F += -0.5f * RHO * L.Area * Cd * Sp * Vb;
	const float Lt = FMath::Sqrt(FMath::Square(L.Len * T.X) + FMath::Square(L.WidthEff.X * T.Y));
	const FVector Bb(T.Y, -T.X, 0.f);
	// rotational circulation (lift of a pitching / tumbling blade); a leaf rolled into a tube sheds it and drops faster
	const float CrEff = CR * (1.f - 0.8f * FMath::Clamp((L.Curl - 0.6f) * 3.f, 0.f, 1.f));
	const float Gam = RHO * (-CT * L.Area * Vtn * Un / Sp + 0.5f * CrEff * Lt * L.Area * FMath::Clamp(FVector::DotProduct(Wb, Bb), -8.f, 8.f));
	F += Gam * FVector(-Un * T.X, -Un * T.Y, Vtn);
	const FVector M(L.Mass, L.Mass, L.Mass + L.AddedMass);
	const FVector Pm = M * Vb;
	const FVector DP = FVector::CrossProduct(Pm, Wb) + F;
	const FVector Ci = 0.5f * RHO * L.Area * CD90 * Sp * FVector(0.1f, 0.1f, 1.f);	// drag taken at the new velocity (stable)
	const FVector Vbn = (Pm + Dt * (DP + Ci * Vb)) / (M + Dt * Ci);
	L.V = L.Q.RotateVector(Vbn) + Air;
	L.P += L.V * 100.f * Dt;
}

void ALeafFall::Land(FLeafSim& L, const FHitResult& Hit)
{
	const FVector N = Hit.ImpactNormal.GetSafeNormal();
	const FVector Up = L.Q.GetAxisZ();
	const float Side = FVector::DotProduct(Up, N) >= 0.f ? 1.f : -1.f;
	L.RestQ = FQuat::FindBetweenNormals(Up, N * Side) * L.Q;
	const FLeafPool& Pool = Pools[int32(L.Shape)];
	const float Lift = (Side > 0.f ? -Pool.ZMin : Pool.ZMax) * L.Scale + 0.12f;
	L.P = Hit.ImpactPoint + N * Lift;
	L.SettleFrom = L.Q;
	L.SettleT = 0.f;
	L.bLanded = true;
	L.bSliding = false;
	L.TumbleAng = 0.f;
	L.SlideV = FVector::ZeroVector;
	L.GroundZ = float(Hit.ImpactPoint.Z);
	L.RestT = 0.f;
	L.V = FVector::ZeroVector;
	++Stats.Landed;
}

void ALeafFall::WriteCustom(const FLeafSim& L, bool bAll)
{
	UInstancedStaticMeshComponent* ISM = Pools[int32(L.Shape)].ISM;
	if (!ISM || L.Slot == INDEX_NONE) return;
	if (bAll)
	{
		FRandomStream R(int32(L.Slot * 131 + int32(L.Len * 1e4f)));
		const float D[NumCustom] = { L.Senescence, L.Wet, float(R.RandRange(0, 7)), L.Fade, R.FRandRange(-1.f, 1.f), R.FRand() * L.Senescence };
		ISM->SetCustomData(L.Slot, TArrayView<const float>(D, NumCustom), false);
	}
	else ISM->SetCustomDataValue(L.Slot, 3, L.Fade, true);
}

void ALeafFall::Release(FLeafSim& L, int32 Index)
{
	FLeafPool& Pool = Pools[int32(L.Shape)];
	if (L.Slot != INDEX_NONE && Pool.ISM)
	{
		Pool.Xf[L.Slot] = Hidden;
		Pool.ISM->UpdateInstanceTransform(L.Slot, Hidden, true, true, true);
		Pool.Free.Add(L.Slot);
	}
	L.Slot = INDEX_NONE;
	L.bActive = false;
	FreeLeaves.Add(Index);
	++Stats.Removed;
}

int32 ALeafFall::SpawnLeafAt(FVector Location, ELeafCondition Condition, bool bRandomCondition)
{
	if (bRandomCondition)
	{
		const float Tot = FMath::Max(FreshShare + DryShare + DampShare + WetShare, 1e-3f);
		const float K = Rng.FRand() * Tot;
		Condition = K < FreshShare ? ELeafCondition::Fresh : (K < FreshShare + DryShare ? ELeafCondition::Dry : (K < FreshShare + DryShare + DampShare ? ELeafCondition::Damp : ELeafCondition::Wet));
	}
	return SpawnLeafWith(Location, Condition);
}

int32 ALeafFall::SpawnLeafWith(FVector Location, ELeafCondition Condition, int32 ForceShape, int32 ForceFlight)
{
	EnsureAssets();
	const int32 Idx = AllocLeaf();
	if (Idx == INDEX_NONE) return INDEX_NONE;
	FLeafSim& L = Leaves[Idx];
	L = FLeafSim();
	L.R.Initialize(int32(Rng.GetUnsignedInt() & 0x7fffffff));
	InitLeaf(L, Condition, ForceShape, ForceFlight);
	L.P = Location;
	FLeafPool& Pool = Pools[int32(L.Shape)];
	if (!Pool.ISM) { L.bActive = false; FreeLeaves.Add(Idx); return INDEX_NONE; }
	if (Pool.Free.Num()) L.Slot = Pool.Free.Pop(EAllowShrinking::No);
	else
	{
		L.Slot = Pool.ISM->AddInstance(Hidden, true);
		Pool.Xf.SetNum(FMath::Max(Pool.Xf.Num(), L.Slot + 1));
	}
	{
		FHitResult GH;
		FCollisionQueryParams GQ(SCENE_QUERY_STAT(LeafGround), false);
		GQ.AddIgnoredActor(this);
		L.GroundZ = GetWorld()->LineTraceSingleByChannel(GH, Location, Location - FVector(0, 0, 5000.f), ECC_Visibility, GQ) ? float(GH.ImpactPoint.Z) : float(Location.Z) - 1000.f;
	}
	WriteCustom(L, true);
	++Stats.Spawned;
	++Stats.ByFlight[int32(L.Flight)];
	return Idx;
}

// ---------------------------------------------------------------------------------------------------- wind on the ground
void ALeafFall::StepGround(FLeafSim& L, int32 Index, float Dt, const FCollisionObjectQueryParams& Obj, const FCollisionQueryParams& Q, bool& bMoved)
{
	// A lying leaf in the wind right at the ground (Docs/Leaves.md, "In the wind"):
	// - drag on what sticks up into the flow: a flat leaf offers almost nothing (the wind skims over it), a curled or
	//   cupped one catches it;
	// - static friction (litter interlock, roughness: per leaf, x3 when wet) is higher than sliding friction, so a leaf
	//   needs a real surge to start, then keeps going while the gust holds, and stops when it fades;
	// - it catches on twigs / stems now and then (SnagPerMetre) and holds there until a stronger gust frees it;
	// - curled leaves roll, flat ones skid and now and then flip over;
	// - lift needs an angle of attack: only a leaf caught edge-up into the wind mid-cartwheel, in a strong enough
	//   surge, takes off (L = 1/2 rho U^2 A CL, CL ~ 1.2 sin 2a).
	L.LiftCool -= Dt;
	FVector Wg = WindAt(L.P) * (0.01f * GroundWindFactor);
	Wg.Z = 0.f;
	const float U = Wg.Size();
	const float Wt = L.Mass * GRAV;
	const float Aeff = L.Area * (0.05f + 0.6f * L.Curl + (L.TumbleAng > 0.f ? 0.4f * FMath::Abs(FMath::Sin(L.TumbleAng)) : 0.f));
	const float Fd = 0.5f * RHO * 1.2f * Aeff * U * U;
	const float MuK = (0.45f + 1.4f * L.Wet) * L.Grip;
	const float MuS = MuK * (1.35f + L.Snag);
	if (!L.bSliding)
	{
		L.Snag = FMath::Max(0.f, L.Snag - 0.03f * Dt);
		if (Fd <= MuS * Wt) return;
		L.bSliding = true;
		L.SlideV = FVector::ZeroVector;
		L.TumbleAng = 0.f;
		L.Snag = 0.f;
		L.bFlip = false;
	}
	++Stats.Sliding;
	const FVector Dir = U > 1e-3f ? Wg / U : FVector::ZeroVector;
	const float Push = Fd > MuK * Wt ? (Fd - MuK * Wt) / L.Mass : 0.f;
	FVector Vs = L.SlideV + Dir * (Push * Dt);
	const float Sp = Vs.Size();
	const float Brake = MuK * GRAV * 0.5f * Dt;
	Vs = Sp > Brake ? Vs * ((Sp - Brake) / Sp) : FVector::ZeroVector;
	if (Vs.Size() > 0.6f * U + 0.05f) Vs = Vs.GetSafeNormal() * (0.6f * U + 0.05f);
	L.SlideV = Vs;
	const float Step = Vs.Size() * Dt;		// metres this step
	auto Settle = [&L, &bMoved]()
	{
		L.bSliding = false; L.bFlip = false;
		if (L.TumbleAng > 0.f)
		{
			// fall onto whichever face is nearer
			if (L.TumbleAng > 0.5f * PI) L.RestQ = (FQuat(L.TumbleAxis, PI) * L.RestQ).GetNormalized();
			L.Q = L.RestQ; L.TumbleAng = 0.f;
		}
		bMoved = true;
	};
	if (Vs.SizeSquared() < 0.0004f && Fd < MuK * Wt) { Settle(); return; }		// the gust faded: it stops
	if (L.R.FRand() < Step * SnagPerMetre)									// caught on something
	{
		L.Snag = L.R.FRandRange(0.4f, 1.6f);
		L.SlideV = FVector::ZeroVector;
		Settle();
		return;
	}
	// follow the ground (a short trace down from just above the new spot)
	const FVector NewP = L.P + Vs * (100.f * Dt);
	FHitResult H;
	if (!GetWorld()->LineTraceSingleByObjectType(H, NewP + FVector(0, 0, 15.f), NewP - FVector(0, 0, 40.f), Obj, Q) || H.ImpactNormal.Z < 0.5f)
	{
		// off an edge or against a step: airborne again
		L.bLanded = false; L.bSliding = false; L.TumbleAng = 0.f; L.bFlip = false;
		L.V = Vs + FVector(0, 0, 0.2f);
		L.LiftQ = L.Q; L.BlendT = 0.f;
		return;
	}
	const FLeafPool& Pool = Pools[int32(L.Shape)];
	const FVector Up = L.RestQ.GetAxisZ();
	const float Side = FVector::DotProduct(Up, H.ImpactNormal) >= 0.f ? 1.f : -1.f;
	L.RestQ = (FQuat::FindBetweenNormals(Up, H.ImpactNormal * Side) * L.RestQ).GetNormalized();
	// curled leaves roll over their edge; flat ones skid and, now and then (a bump, an edge catching), flip over
	const bool bRoller = L.Curl > 0.35f;
	if (!bRoller && !L.bFlip && L.R.FRand() < Step * 0.8f) L.bFlip = true;
	const float RollRate = (Vs.Size() / FMath::Max(0.5f * L.Wid, 0.01f)) * ((bRoller || L.bFlip) ? 1.f : 0.f);
	if (L.TumbleAng == 0.f) L.TumbleAxis = FVector::CrossProduct(FVector::UpVector, Dir).GetSafeNormal();
	L.TumbleAng += FMath::Max(RollRate * Dt, L.bFlip ? 6.f * Dt : 0.f);
	if (L.TumbleAng >= PI)
	{
		L.RestQ = (FQuat(L.TumbleAxis, PI) * L.RestQ).GetNormalized();
		L.TumbleAng -= PI;
		if (L.bFlip) { L.bFlip = false; L.TumbleAng = 0.f; }
		L.TumbleAxis = FVector::CrossProduct(FVector::UpVector, Dir).GetSafeNormal();
	}
	L.Q = L.TumbleAng > 0.f ? FQuat(L.TumbleAxis, L.TumbleAng) * L.RestQ : L.RestQ;
	const float Lift = (Side > 0.f ? -Pool.ZMin : Pool.ZMax) * L.Scale + 0.12f + FMath::Sin(L.TumbleAng) * L.Wid * 50.f;
	L.P = H.ImpactPoint + H.ImpactNormal * Lift;
	L.GroundZ = float(H.ImpactPoint.Z);
	bMoved = true;
	// edge up into the wind, mid-cartwheel, in a strong enough surge: it takes off
	const float Aoa = L.TumbleAng < 0.5f * PI ? L.TumbleAng : 0.f;		// rising edge facing the wind
	const float LiftF = 0.5f * RHO * U * U * L.Area * 1.2f * FMath::Sin(2.f * Aoa) * (1.f + L.Curl);
	if (L.LiftCool <= 0.f && LiftF > LiftOffRatio * Wt)
	{
		L.LiftCool = 3.f;
		L.bLanded = false; L.bSliding = false; L.TumbleAng = 0.f; L.bFlip = false;
		L.V = Wg * 0.7f + FVector(0, 0, FMath::Min(LiftF / Wt * 0.12f, 2.2f));
		L.Phase = L.R.FRandRange(0.f, 2.f * PI);
		L.RestT = 0.f;
		L.LiftQ = L.Q; L.BlendT = 0.f;
		++Stats.LiftOffs;
	}
}

// ---------------------------------------------------------------------------------------------------- tick
void ALeafFall::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bEnabled || CVarLeavesEnable.GetValueOnGameThread() == 0) return;
	const double T0 = FPlatformTime::Seconds();
	const float Dt = FMath::Min(DeltaSeconds, 0.05f);
	ScanTimer -= DeltaSeconds;
	if (ScanTimer <= 0.f) { ScanTimer = 5.f; ScanTrees(); if (Trees.Num()) EnsureAssets(); }		// PCG may (re)generate the forest at runtime
	if (Trees.Num() == 0 && Stats.Spawned == Stats.Removed) return;

	// cameras and the trees near them
	Cameras.Reset();
	for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
	{
		const APlayerController* PC = It->Get();
		if (PC && PC->PlayerCameraManager) Cameras.Add(PC->PlayerCameraManager->GetCameraLocation());
	}
	InRange.Reset();
	for (int32 i = 0; i < Trees.Num(); ++i)
	{
		const FTree& Tr = Trees[i];
		const float Reach = ActiveRadius + Tr.Radii.X;
		for (const FVector& C : Cameras) if (FVector::DistSquared(C, Tr.Centre) < Reach * Reach) { InRange.Add(i); break; }
	}
	Stats.TreesInRange = InRange.Num();

	// emission: a Poisson process over the trees in range (exponential gaps); a burst tears leaves off the trees it sweeps
	if (!GlobalWind.IsValid()) GlobalWind = AGlobalWind::Get(this, false);
	const AGlobalWind* GW = GlobalWind.Get();
	TreeWeight.SetNumUninitialized(InRange.Num());
	float WSum = 0.f;
	for (int32 k = 0; k < InRange.Num(); ++k)
	{
		const float Wt = 1.f + (GW ? GustReleaseBoost * GW->GetGustIntensityAt(Trees[InRange[k]].Centre) : 0.f);
		WSum += Wt;
		TreeWeight[k] = WSum;
	}
	const float Rate = WSum * LeavesPerTreePerMinute * CVarLeavesRate.GetValueOnGameThread() / 60.f;
	EmitAccum += Rate * Dt;
	int32 Guard = 16;
	while (InRange.Num() && EmitAccum >= NextGap && Guard-- > 0)
	{
		EmitAccum -= NextGap;
		NextGap = -FMath::Loge(FMath::Max(1.f - Rng.FRand(), 1e-4f));
		const float Pick = Rng.FRand() * WSum;
		int32 Ti = 0;
		while (Ti < InRange.Num() - 1 && TreeWeight[Ti] < Pick) ++Ti;
		const FTree& Tr = Trees[InRange[Ti]];
		// a point of the outer canopy, more often low and on the sides than on top
		const float Z = Rng.FRandRange(-0.85f, 0.45f);
		const float A = Rng.FRandRange(0.f, 2.f * PI);
		const float Rr = FMath::Sqrt(1.f - Z * Z) * Rng.FRandRange(0.8f, 1.f);
		const FVector At = Tr.Centre + FVector(Tr.Radii.X * Rr * FMath::Cos(A), Tr.Radii.Y * Rr * FMath::Sin(A), Tr.Radii.Z * Z);
		SpawnLeafAt(At, ELeafCondition::Dry, true);
	}

	// simulate
	EnsureAssets();
	int32 Lo[6], Hi[6];
	for (int32 s = 0; s < 6; ++s) { Lo[s] = MAX_int32; Hi[s] = -1; }
	FCollisionObjectQueryParams Obj;
	Obj.AddObjectTypesToQuery(ECC_WorldStatic);
	Obj.AddObjectTypesToQuery(ECC_WorldDynamic);
	Obj.AddObjectTypesToQuery(ECC_PhysicsBody);
	Obj.AddObjectTypesToQuery(ECC_Pawn);
	FCollisionQueryParams Q(SCENE_QUERY_STAT(LeafFall), false);
	Q.AddIgnoredActor(this);
	if (!bCollideWithTrees) for (UPrimitiveComponent* C : TreeComponents) if (C) Q.AddIgnoredComponent(C);
	const int32 Sub = FMath::Max(1, FMath::CeilToInt(Dt * 120.f));
	const float H = Dt / Sub;
	const float KillZ = GetWorld()->GetWorldSettings() ? GetWorld()->GetWorldSettings()->KillZ : -1e6f;
	int32 Falling = 0, Resting = 0;
	Stats.Sliding = 0;
	for (int32 i = 0; i < Leaves.Num(); ++i)
	{
		FLeafSim& L = Leaves[i];
		if (!L.bActive) continue;
		L.Age += Dt;
		bool bMoved = false;
		if (!L.bLanded)
		{
			++Falling;
			const FVector P0 = L.P;
			for (int32 k = 0; k < Sub; ++k) StepAir(L, H);
			FHitResult Hit;
			if (FVector::DistSquared(P0, L.P) > 1e-4f && GetWorld()->LineTraceSingleByObjectType(Hit, P0, L.P, Obj, Q))
			{
				const bool bPawn = Hit.GetActor() && Hit.GetActor()->IsA<APawn>();
				if (Hit.ImpactNormal.Z >= 0.55f && !bPawn) Land(L, Hit);
				else
				{
					// walls, trunks, characters: bounce off and keep falling
					const FVector N = Hit.ImpactNormal;
					L.V = (L.V - 1.3f * FVector::DotProduct(L.V, N) * N) * 0.45f;
					L.P = Hit.Location + N * 0.6f;
				}
			}
			// a leaf that never finds the ground (or stays caught) fades out after 40 s anyway
			if (L.Age > 40.f) L.Fade = FMath::Max(0.f, 1.f - (L.Age - 40.f) / FMath::Max(FadeTime, 0.01f));
			bMoved = true;
		}
		else
		{
			++Resting;
			if (L.SettleT < 0.22f)
			{
				// the little flop onto the ground
				L.SettleT += Dt;
				const float A = FMath::Clamp(L.SettleT / 0.22f, 0.f, 1.f);
				L.Q = FQuat::Slerp(L.SettleFrom, L.RestQ, 1.f - FMath::Cube(1.f - A));
				bMoved = true;
			}
			if (bWindMovesFallenLeaves && GW && L.SettleT >= 0.22f) StepGround(L, i, Dt, Obj, Q, bMoved);
			if (!L.bSliding) L.RestT += Dt;		// a leaf being blown along does not start fading
			// never more than 90 s in the world, however often the wind picks it up
			const float RestLeft = FMath::Max(L.RestT - RestTime, L.Age - 90.f);
			if (RestLeft > 0.f) L.Fade = FMath::Max(0.f, 1.f - RestLeft / FMath::Max(FadeTime, 0.01f));
		}
		if (L.Fade < 1.f) WriteCustom(L, false);
		if (L.Fade <= 0.f || L.P.Z < KillZ) { Release(L, i); continue; }
		if (bMoved)
		{
			FLeafPool& Pool = Pools[int32(L.Shape)];
			const int32 S = int32(L.Shape);
			Pool.Xf[L.Slot] = FTransform(L.Q, L.P, FVector(L.Scale));
			Lo[S] = FMath::Min(Lo[S], L.Slot);
			Hi[S] = FMath::Max(Hi[S], L.Slot);
		}
	}
	for (int32 s = 0; s < 6; ++s)
	{
		if (Hi[s] >= Lo[s] && Pools[s].ISM)
		{
			Pools[s].ISM->BatchUpdateInstancesTransforms(Lo[s], TArrayView<const FTransform>(Pools[s].Xf.GetData() + Lo[s], Hi[s] - Lo[s] + 1), true, true, false);
		}
	}
	Stats.Falling = Falling;
	Stats.Resting = Resting;
	const double Ms = (FPlatformTime::Seconds() - T0) * 1000.0;
	TickMsSum += Ms; ++TickN;
	Stats.MaxTickMs = FMath::Max(Stats.MaxTickMs, float(Ms));
	StatsT += DeltaSeconds;
	if (StatsT >= 1.f) { Stats.AvgTickMs = float(TickMsSum / FMath::Max(TickN, 1)); TickMsSum = 0.0; TickN = 0; StatsT = 0.f; }
}

// ---------------------------------------------------------------------------------------------------- auto-create
bool ULeafFallSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* W = Cast<UWorld>(Outer);
	return W && (W->WorldType == EWorldType::Game || W->WorldType == EWorldType::PIE);
}

void ULeafFallSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	if (CVarLeavesAuto.GetValueOnGameThread() == 0 || ALeafFall::Find(&InWorld, false)) return;
	ALeafFall::Find(&InWorld, true);		// idles (a rescan every 5 s) unless the level has the tree meshes
}
