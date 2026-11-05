#include "ProphecyNoose.h"
#include "ProphecyPotenceRope.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltSkeletalPropComponent.h"
#include "ProphecyJoltStaticMeshLibrary.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "UObject/ConstructorHelpers.h"
#include "AnimationRuntime.h"
#include "Algo/Reverse.h"
#include "UObject/UObjectIterator.h"
#include "Components/PoseableMeshComponent.h"
#include "TimerManager.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#if WITH_EDITORONLY_DATA
#include "Rendering/SkeletalMeshModel.h"
#include "Rendering/SkeletalMeshLODModel.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogProphecyNoose, Log, All);

namespace
{
// Tied, the coil leans out from the limb by this much (a hangman's knot stands along the rope, beside the loop).
constexpr double KnotLeanDegrees = 30.0;
// Tied: relative angular damping on the hanging body's joints (the plugin's implicit joint damping, 1/s, mass
// normalised). It removes the small solver jiggle of a body hanging from a rope; the whole body still swings freely.
constexpr float TiedJointDamping = 300.f;
// Reeling a tied body. Shortening the load tether's limit a little every frame made Jolt close each step's gap with a
// position correction on the light neck body alone, which dragged the 60+ kg torso through the neck joints: the neck
// stretched ~6 cm while the rope rose. Now the tether keeps a fixed length and hangs from an invisible kinematic anchor
// on the pulley->load line, beyond the pulley by the rope reeled in since the tie. The reel moves that anchor (a
// kinematic velocity, solved at velocity level across the whole body), and since the anchor stays on the line through
// the load, the load is always exactly the hanging rope's length from the pulley - the pivot stays at the pulley.
// The tether is a stiff spring, like a real rope (~2.5 mm of stretch under a 73 kg body), not a hard limit: the
// plugin's radial limit switches itself off for the whole step whenever the solver leaves the load a hair inside the
// radius, so a body hanging still at the limit dropped one step of free fall every few seconds (a visible hitch).
// A loaded spring always sits a little past its rest length, so it never switches off while it carries the body.
constexpr float TetherStiffness = 3.0e5f;	// N/m
constexpr float TetherDamping = 9.0e3f;		// N s/m, about critical for a 73 kg body
// While the reel pulls the body up, this share of each frame's pull is applied the old way - the anchor jumps instead
// of moving with a velocity, against a hard limit - so the neck gives a little under the pull (a fraction of the
// ~6 cm stretch of the old shortening tether); the rest goes through the anchor's velocity. 0 = no give.
// The tether is hard only while the reel pulls up, and a spring again once it has been still for ReelHardHoldSeconds.
constexpr double ReelNeckGive = .35;
constexpr double ReelHardHoldSeconds = .3;
}

namespace ProphecyNooseMesh
{
// Where the drawn rope enters each noose (its standing strand, inside the top of the coil), in the noose's frame.
TMap<TWeakObjectPtr<const UProphecyNooseComponent>, FVector> GEntrance;

struct FMeshOut
{
	TArray<FVector> V; TArray<int32> I; TArray<FVector> N; TArray<FVector2D> UV; TArray<FProcMeshTangent> T;
};

// UE front faces: (v2 - v0) x (v1 - v0) points out of the visible side (as UE's own mesh tools compute face normals).
void AddTri(FMeshOut& M, int32 A, int32 B, int32 C, const FVector& Out)
{
	if (FVector::DotProduct(FVector::CrossProduct(M.V[C] - M.V[A], M.V[B] - M.V[A]), Out) >= 0) { M.I.Add(A); M.I.Add(B); M.I.Add(C); }
	else { M.I.Add(A); M.I.Add(C); M.I.Add(B); }
}

TArray<FVector> Smooth(const TArray<FVector>& K, float Step)
{
	TArray<FVector> Out;
	for (int32 i = 0; i + 1 < K.Num(); ++i)
	{
		const FVector P0 = K[FMath::Max(i - 1, 0)], P1 = K[i], P2 = K[i + 1], P3 = K[FMath::Min(i + 2, K.Num() - 1)];
		const int32 Steps = FMath::Max(1, FMath::CeilToInt(FVector::Dist(P1, P2) / Step));
		for (int32 s = 0; s < Steps; ++s)
		{
			const float t = float(s) / Steps, t2 = t * t, t3 = t2 * t;
			Out.Add(0.5f * ((2.f * P1) + (P2 - P0) * t + (2.f * P0 - 5.f * P1 + 4.f * P2 - P3) * t2 + (3.f * P1 - P0 - 3.f * P2 + P3) * t3));
		}
	}
	Out.Add(K.Last());
	return Out;
}

// Rope tube along a polyline (parallel-transported frame), rope UV convention: U across the section, V along.
float Tube(FMeshOut& M, const TArray<FVector>& P, float R, int32 Sides, float UVAround, float UVAlong, float V0, bool Cap0, bool Cap1, float Flare1 = 1.f, float Taper0 = 1.f)
{
	const int32 N = P.Num();
	if (N < 2) return V0;
	// Optional taper: the first ring is Taper0 x R, blending to R along the tube (smoothstep over its length).
	TArray<float> Along; Along.SetNum(N); Along[0] = 0;
	for (int32 i = 1; i < N; ++i) Along[i] = Along[i - 1] + float(FVector::Dist(P[i], P[i - 1]));
	const float Total = FMath::Max(Along.Last(), 1e-3f);
	TArray<FVector> Tan; Tan.SetNum(N);
	for (int32 i = 0; i < N; ++i) Tan[i] = (P[FMath::Min(i + 1, N - 1)] - P[FMath::Max(i - 1, 0)]).GetSafeNormal();
	const FVector Ref = FMath::Abs(Tan[0].Z) < .9f ? FVector::UpVector : FVector::ForwardVector;
	FVector Nrm = FVector::CrossProduct(Tan[0], Ref).GetSafeNormal();
	const int32 Base = M.V.Num();
	float V = V0;
	for (int32 i = 0; i < N; ++i)
	{
		if (i > 0)
		{
			Nrm = FQuat::FindBetweenNormals(Tan[i - 1], Tan[i]).RotateVector(Nrm);
			Nrm = (Nrm - Tan[i] * FVector::DotProduct(Nrm, Tan[i])).GetSafeNormal();
			V += float(FVector::Dist(P[i], P[i - 1])) * UVAlong;
		}
		const FVector Bi = FVector::CrossProduct(Tan[i], Nrm);
		const float Ta = FMath::SmoothStep(0.f, 1.f, Along[i] / Total);
		const float Rad = R * (i == N - 1 ? Flare1 : 1.f) * FMath::Lerp(Taper0, 1.f, Ta);
		for (int32 s = 0; s <= Sides; ++s)
		{
			const float A = 2.f * PI * s / Sides;
			const FVector Dir = Nrm * FMath::Cos(A) + Bi * FMath::Sin(A);
			M.V.Add(P[i] + Dir * Rad); M.N.Add(Dir); M.UV.Add(FVector2D(UVAround * s / Sides, V)); M.T.Add(FProcMeshTangent(Tan[i], false));
		}
	}
	for (int32 i = 0; i + 1 < N; ++i)
		for (int32 s = 0; s < Sides; ++s)
		{
			const int32 a = Base + i * (Sides + 1) + s, b = a + Sides + 1;
			AddTri(M, a, b, a + 1, M.N[a]);
			AddTri(M, a + 1, b, b + 1, M.N[a + 1]);
		}
	auto Cap = [&](int32 Ring, const FVector& Center, const FVector& Out)
	{
		const int32 C = M.V.Num();
		M.V.Add(Center); M.N.Add(Out); M.UV.Add(FVector2D(UVAround * .5f, V)); M.T.Add(FProcMeshTangent(M.N[Ring], false));
		for (int32 s = 0; s < Sides; ++s) AddTri(M, C, Ring + s, Ring + s + 1, Out);
	};
	if (Cap0) Cap(Base, P[0] - Tan[0] * R * .1f, -Tan[0]);
	if (Cap1) Cap(Base + (N - 1) * (Sides + 1), P[N - 1] + Tan[N - 1] * R * .15f, Tan[N - 1]);
	return V;
}
}

UProphecyNooseComponent::UProphecyNooseComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryComponentTick.bCanEverTick = false;
	SetCollisionEnabled(ECollisionEnabled::NoCollision);
	bUseComplexAsSimpleCollision = false;
	SetGenerateOverlapEvents(false);
	CastShadow = true;
	static ConstructorHelpers::FObjectFinderOptional<UMaterialInterface> RopeMaterial(TEXT("/Game/_mygame/assets/hanging/MI_RopeHang.MI_RopeHang"));
	if (RopeMaterial.Get()) SetMaterial(0, RopeMaterial.Get());
}

void UProphecyNooseComponent::BuildLoose()
{
	// Hanging free: the loop falls below the knot in a plane containing the rope.
	Build(FVector::ForwardVector, FVector::UpVector, LooseLoopRadius, TArray<float>());
}

void UProphecyNooseComponent::BuildAround(const FVector& Axis, const FVector& KnotSide, float InnerRadius, const TArray<float>& InnerProfile)
{
	Build(Axis, KnotSide, InnerRadius, InnerProfile);
}

void UProphecyNooseComponent::Build(const FVector& AxisIn, const FVector& SideIn, float InnerRadius, const TArray<float>& Profile)
{
	using namespace ProphecyNooseMesh;
	const float r = RopeRadius;
	const FVector Up = FVector::UpVector;
	FVector A = AxisIn.GetSafeNormal();
	FVector D = (SideIn - A * FVector::DotProduct(SideIn, A)).GetSafeNormal();
	if (A.IsNearlyZero() || D.IsNearlyZero()) { A = FVector::ForwardVector; D = Up; }
	const float Rc = FMath::Max(InnerRadius, r) + r;	// loop centreline radius at the knot
	// Loop centreline radius all around: the skin profile when given (angle 0 = knot side), else a circle.
	const int32 NP = Profile.Num();
	auto RcAt = [&](float Phi)
	{
		if (NP < 3) return Rc;
		const float U = FMath::Fmod(Phi / (2.f * PI) + 4.f, 1.f) * NP;
		const int32 K0 = FMath::FloorToInt(U) % NP, K1 = (K0 + 1) % NP;
		return FMath::Max(FMath::Lerp(Profile[K0], Profile[K1], U - FMath::FloorToFloat(U)), r) + r;
	};
	{
		float Sum = 0;
		for (float P : Profile) Sum += FMath::Max(P, r);
		CurrentInnerRadius = NP >= 3 ? Sum / NP : Rc - r;
	}
	const float H = GetCoilLength(), T0 = GetKnotTop();
	const FVector K0 = GetKnotBottom();
	const FVector C = K0 - D * (Rc + GetKnotStandoff());
	const FVector E2 = FVector::CrossProduct(A, D);	// loop tangent on the knot side
	FVector E = E2 - Up * FVector::DotProduct(E2, Up);	// strand separation inside the coil
	if (E.SizeSquared() < 1e-4) E = FVector::CrossProduct(Up, D);
	if (E.SizeSquared() < 1e-4) E = FVector::ForwardVector;
	E.Normalize();
	const FVector F = FVector::CrossProduct(Up, E);
	const float Step = r * .9f;
	FMeshOut M;

	// One rope runs down the centre of the coil: the drawn rope enters on the axis, a little inside the top, and goes
	// on down through the wraps into the loop. The wraps sit tight on it (their hole is the rope's own size), so the
	// knot is never hollow and the joint never shows. The loop's other leg ends hidden inside the bottom wraps.
	const FVector Entrance = -Up * (T0 + 1.5f * r);
	ProphecyNooseMesh::GEntrance.FindOrAdd(this) = Entrance;

	// The wraps: a slightly flattened helix around the two strands, top to bottom.
	{
		TArray<FVector> Coil;
		const int32 PerTurn = 18, Count = CoilTurns * PerTurn;
		for (int32 i = 0; i <= Count; ++i)
		{
			const float t = float(i) / PerTurn * 2.f * PI;
			const float z = -T0 - r - (H - 2.f * r) * float(i) / Count;
			Coil.Add(E * (2.f * r * FMath::Cos(t)) + F * (2.f * r * FMath::Sin(t)) + Up * z);
		}
		Tube(M, Coil, r, Sides, UVAroundPerTurn, UVAlongPerCm, .11f, true, true);
	}

	// The loop: both strands leave the bottom of the coil and close around centre C in the plane normal to A.
	{
		const float Phi0 = FMath::Clamp(FMath::Asin(FMath::Min(1.5f * r / Rc, .95f)), .15f, 1.f);
		TArray<FVector> Key;
		Key.Add(Entrance);
		Key.Add(K0 - Up * (r * .6f));
		const int32 Seg = 28;
		for (int32 i = 0; i <= Seg; ++i)
		{
			const float Phi = -Phi0 - (2.f * PI - 2.f * Phi0) * float(i) / Seg;
			Key.Add(C + RcAt(Phi) * (D * FMath::Cos(Phi) + E2 * FMath::Sin(Phi)));
		}
		Key.Add(K0 + E * (r * .5f) - Up * (r * .6f));
		Key.Add(K0 + E * (r * .4f) + Up * (1.5f * r));
		Tube(M, Smooth(Key, Step), r, Sides, UVAroundPerTurn, UVAlongPerCm, .23f, false, true);
	}
	ClearAllMeshSections();
	CreateMeshSection(0, M.V, M.I, M.N, M.UV, TArray<FColor>(), M.T, false);
	UE_LOG(LogProphecyNoose, Verbose, TEXT("Noose %s: %d verts, %d tris, inner radius %.1f cm"), *GetName(), M.V.Num(), M.I.Num() / 3, CurrentInnerRadius);
}

// ---------------------------------------------------------------------------------------------------------------
namespace
{
struct FNooseState
{
	TWeakObjectPtr<UProphecyNooseComponent> Noose;
	FName TipBone, RootBone = TEXT("Root");
	FProphecyJoltJointHandle TipTether, Tie;
	FProphecyJoltJointSettings TipTetherSettings, TieSettings;
	TWeakObjectPtr<UPrimitiveComponent> Target;
	FProphecyJoltBodyHandle TargetBody;
	double TipMassUntied = 0;
	bool bTied = false;
	FTransform NooseOnBone;					// the noose's place on the rope end bone
	FTransform NooseOnLimb;					// tied: where the noose sits on the limb body
	FTransform TieFrameStart, TieFrameEnd;	// the tie joint's rope-side frame, drawn from start to end
	double CloseElapsed = 0;
	FTimerHandle CloseTimer;
	// The drawn rope (see UpdateRopeTube).
	TWeakObjectPtr<UProceduralMeshComponent> RopeTube;
	TArray<FName> RopeChain;			// the rope's bodies from the first link to the end
	TArray<FVector> SmoothedLinks;
	FVector SmoothP1 = FVector::ZeroVector;
	double SmoothLambda = 0;
	bool bSmoothValid = false, bLoggedBadPath = false;
	double DiagClock = 0;
	TArray<TWeakObjectPtr<UPrimitiveComponent>> HiddenSkins;
	bool bRopeDrawnBySkin = true;
	double NextSkinScan = 0;
	bool bDumpedNearby = false, bLoggedReshow = false;
	double LogClock = 0;
	bool bClosing = false;
	// Tied, the tether carries the load from the rope root straight to the loop's centre on the limb (no lever on
	// the limb, the rope only follows); TetherOffset keeps its length matched to the paid-out rope.
	bool bTetherOnLimb = false;
	double TetherOffset = 0;
	// The tether can only join the fixed rope root to a moving body: a held (kinematic) limb takes it once released.
	// Until then the guard tether stays on the rope end.
	bool bTetherPending = false;
	FProphecyJoltBodyHandle TetherLimb;
	FTransform TetherFrameOnLimb;
	FString TetherError;
	// Tied limb and the light bodies between it and the trunk: at least MinLimbMassKg while tied (two 0.6 kg neck
	// bodies cannot carry a hanging body in the solver). Original masses are restored when untied.
	TArray<TPair<FName, double>> RaisedBodies;
	bool bLimbMassPending = false, bLimbMassApplied = false;
	FProphecyJoltBodyHandle CoilBody;			// the coil's collider: a light box locked to its carrier
	FProphecyJoltJointHandle CoilJoint;		// carrier = the rope end while loose, the tied limb once tied
	TArray<FProphecyJoltBodyPair> CoilPairs;	// it never touches the rope it is part of
	FProphecyJoltBodyHandle DampedBody;		// tied: a body of the hanging rig whose joints carry TiedJointDamping
	FProphecyJoltBodyHandle TetherAnchor;	// tied: the kinematic body the load tether hangs from (see above)
	FVector TetherPulley = FVector::ZeroVector;
	double TetherAmount0 = 0, TetherReelLength = 0;
	double TetherLastAmount = -1, TetherLastPull = -1;	// reel amount last frame; when the reel last pulled up
	bool bTetherHard = false;							// tether temporarily a hard limit (pulling up)
};
TMap<TWeakObjectPtr<USkeletalMeshComponent>, FNooseState> NooseStates;

struct FTieGeometry
{
	FVector Center, Axis, Side, NooseOrigin, Tip;
	FVector LoopNormal, CoilAxis;		// rigid noose: loop plane normal and coil axis (in the loop plane)
	FQuat NooseRotation, TipRotation;
	float Inner = 0, LimbRadius = 0, TiltDeg = 0;
	float LoopTiltDeg = 0, DropCm = 0;		// the loop's placement found on the skin (tilt, lowered along the limb)
	int32 Blocked = 0;					// skin of the next body still within the rope's reach (0 = clear)
	TArray<float> Profile;			// loop inner radius all around (skin + clearance), empty = circle
	const TCHAR* SkinSource = TEXT("capsule");
	FProphecyJoltBodyHandle TipBody, LimbBody;
	FTransform LimbPose;
};

UProphecyJoltWorldSubsystem* NativeOf(const UObject* O) { return O && O->GetWorld() ? O->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr; }

bool ReadPose(UProphecyJoltWorldSubsystem* Native, const FProphecyJoltBodyHandle& H, FTransform& Pose)
{
	FProphecyJoltBodyState S;
	if (!Native || !Native->ReadBody(H, S).IsSuccess()) return false;
	Pose = FTransform(S.Rotation, S.PositionCm);
	return true;
}

bool BodyOf(UPrimitiveComponent* C, FName Bone, FProphecyJoltBodyHandle& H)
{
	if (!IsValid(C) || !C->GetWorld()) return false;
	if (auto* Agent = Cast<AProphecyAgent>(C->GetOwner()); Agent && Agent->GetPoseReferenceMesh() == C)
		if (auto* Character = Agent->GetJoltCharacterComponent(); Character && Character->IsJoltPhysical())
			return Character->GetBodyHandle(Bone, H);
	if (auto* Skeletal = Cast<USkeletalMeshComponent>(C))
	{
		auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Skeletal);
		return Prop && Prop->IsJoltStepClientActive() && Prop->GetBodyHandle(Bone, H);
	}
	auto* Scene = UProphecyJoltSceneCollisionComponent::FindForWorld(C->GetWorld());
	return Scene && Scene->GetBodyHandle(*C, INDEX_NONE, H);
}

// The limb's collision: capsule (or sphere/box) of that body, its axis, radius and the tie spot.
bool LimbGeometry(UPrimitiveComponent* C, FName Bone, FName AtBone, FVector& Center, FVector& Axis, float& Radius, FString& Error)
{
	UBodySetup* Setup = nullptr;
	FTransform Frame;
	auto* Skeletal = Cast<USkeletalMeshComponent>(C);
	if (Skeletal)
	{
		UPhysicsAsset* PA = Skeletal->GetPhysicsAsset();
		const int32 I = PA ? PA->FindBodyIndex(Bone) : INDEX_NONE;
		if (I == INDEX_NONE) { Error = FString::Printf(TEXT("%s has no physics body %s."), *GetNameSafe(C), *Bone.ToString()); return false; }
		Setup = PA->SkeletalBodySetups[I].Get();
		Frame = Skeletal->GetSocketTransform(Bone, RTS_World);
	}
	else
	{
		Setup = C->GetBodySetup();
		Frame = C->GetComponentTransform();
	}
	if (!Setup) { Error = TEXT("Target has no collision setup."); return false; }
	const float Scale = float(Frame.GetScale3D().GetAbsMin());
	const FKAggregateGeom& G = Setup->AggGeom;
	float HalfLength = 0;
	if (G.SphylElems.Num())
	{
		const FKSphylElem* Best = &G.SphylElems[0];
		for (const FKSphylElem& E : G.SphylElems) if (E.Radius * (E.Length + 2 * E.Radius) > Best->Radius * (Best->Length + 2 * Best->Radius)) Best = &E;
		const FTransform T = Best->GetTransform();
		Center = Frame.TransformPosition(T.GetLocation());
		Axis = Frame.TransformVectorNoScale(T.GetRotation().GetAxisZ()).GetSafeNormal();
		Radius = Best->Radius * Scale;
		HalfLength = Best->Length * .5f * Scale;
	}
	else if (G.SphereElems.Num())
	{
		Center = Frame.TransformPosition(G.SphereElems[0].Center);
		Axis = Frame.GetRotation().GetAxisX();
		Radius = G.SphereElems[0].Radius * Scale;
	}
	else if (G.BoxElems.Num())
	{
		const FKBoxElem& B = G.BoxElems[0];
		const FVector Ext(B.X, B.Y, B.Z);
		const int32 Long = Ext.X >= Ext.Y && Ext.X >= Ext.Z ? 0 : (Ext.Y >= Ext.Z ? 1 : 2);
		const FQuat Q = B.Rotation.Quaternion();
		const FVector Local = Long == 0 ? Q.GetAxisX() : (Long == 1 ? Q.GetAxisY() : Q.GetAxisZ());
		Center = Frame.TransformPosition(B.Center);
		Axis = Frame.TransformVectorNoScale(Local).GetSafeNormal();
		const float A = float(Long == 0 ? Ext.Y : Ext.X), Bb = float(Long == 2 ? Ext.Y : Ext.Z);
		Radius = .5f * FMath::Sqrt(A * A + Bb * Bb) * Scale;		// circumscribed: the loop must clear the corners
		HalfLength = float(Ext[Long]) * .5f * Scale;
	}
	else { Error = TEXT("Target body has no capsule, sphere or box to tie around."); return false; }
	if (Skeletal && !AtBone.IsNone())
	{
		if (Skeletal->GetBoneIndex(AtBone) == INDEX_NONE) { Error = FString::Printf(TEXT("No bone %s."), *AtBone.ToString()); return false; }
		// A little inside the joint: the skin there follows this limb, not the next one (the foot at an ankle).
		const float Inset = FMath::Min(3.f, HalfLength);
		const float T = FMath::Clamp(float(FVector::DotProduct(Skeletal->GetSocketLocation(AtBone) - Center, Axis)), -HalfLength + Inset, HalfLength - Inset);
		Center += Axis * T;
	}
	return Radius > 0;
}


// Skin cross-section of a skeletal mesh at the tie: the mesh's triangles, skinned to the current pose, cut by the loop's
// plane. Profile[k] = distance from the loop centre to the skin at angle 2*pi*k/N from the knot side towards
// Normal x Side (world cm), made convex (a rope under tension spans the hollows).
// The loop must sit on the limb, never through the next body (the head over a neck, the heel at an ankle): from the
// given spot it searches a little lower along the limb and a tilt of the loop (front down, knot side up, as a real
// noose hangs) until no skin of that next body comes within the rope's reach; the smallest such change wins.
// Runs once per tie. Needs the mesh's editor data (editor and -game runs); otherwise false = use the capsule.
bool MeasureSkin(USkeletalMeshComponent* Skel, FName Bone, const FVector& CenterW, const FVector& AxisW, const FVector& SideW,
	float SearchRadiusW, float RopeRadiusW, float ClearanceW, TArray<float>& Profile, const TCHAR*& Source, FString& Why,
	FVector& OutCenterW, FVector& OutNormalW, float& OutTiltDeg, float& OutDropCm, int32& OutBlocked)
{
	constexpr int32 N = 32;
	OutCenterW = CenterW; OutNormalW = AxisW; OutTiltDeg = 0; OutDropCm = 0; OutBlocked = 0;
	USkeletalMesh* Mesh = Skel ? Skel->GetSkeletalMeshAsset() : nullptr;
	if (!Mesh || Skel->GetBoneIndex(Bone) == INDEX_NONE) { Why = TEXT("not a skeletal mesh bone"); return false; }
	const FTransform CompW = Skel->GetComponentTransform();
	const double Scale = CompW.GetScale3D().GetAbsMin();
	if (Scale < KINDA_SMALL_NUMBER) { Why = TEXT("zero scale"); return false; }
	TArray<FVector3f> Positions;
	TArray<bool> OnLimb;	// skin that belongs to the tied limb (not the foot, the head or the shoulders)
	TArray<bool> OnNear;	// fallback: the limb and its neighbours, without the next body (a short neck has little skin of its own)
	TArray<bool> Blocker;	// skin of the next body towards the extremity (the head, the foot): the loop must stay clear of it
	TArray<uint32> Indices;
#if WITH_EDITORONLY_DATA
	if (const FSkeletalMeshModel* Model = Mesh->GetImportedModel(); Model && Model->LODModels.Num())
	{
		// Linear blend skinning with the current component-space pose (the limb as it is now, not its bind pose).
		const TArray<FTransform>& Pose = Skel->GetComponentSpaceTransforms();
		const TArray<FMatrix44f>& RefInv = Mesh->GetRefBasesInvMatrix();
		TArray<FMatrix44f> SkinMat; SkinMat.SetNum(FMath::Min(Pose.Num(), RefInv.Num()));
		for (int32 B = 0; B < SkinMat.Num(); ++B) SkinMat[B] = RefInv[B] * FMatrix44f(Pose[B].ToMatrixWithScale());
		// The limb: the tied bone and its descendants that have no physics body of their own (twist bones).
		// Beyond it: descendants that have a body (the head, the foot) and everything under them.
		const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
		const UPhysicsAsset* PA = Skel->GetPhysicsAsset();
		auto HasBody = [&](int32 B) { return PA && PA->FindBodyIndex(Ref.GetBoneName(B)) != INDEX_NONE; };
		TArray<bool> LimbBone, BeyondBone;
		LimbBone.Init(false, Ref.GetNum()); BeyondBone.Init(false, Ref.GetNum());
		const int32 Root = Ref.FindBoneIndex(Bone);
		if (LimbBone.IsValidIndex(Root)) LimbBone[Root] = true;
		for (int32 B = 0; B < Ref.GetNum(); ++B)
		{
			const int32 Parent = Ref.GetParentIndex(B);
			if (B == Root || Parent == INDEX_NONE) continue;
			if (BeyondBone[Parent] || (LimbBone[Parent] && HasBody(B))) BeyondBone[B] = true;
			else if (LimbBone[Parent]) LimbBone[B] = true;
		}
		TArray<bool> NearBone = LimbBone;
		if (LimbBone.IsValidIndex(Root) && Ref.GetParentIndex(Root) != INDEX_NONE) NearBone[Ref.GetParentIndex(Root)] = true;
		const FSkeletalMeshLODModel& LOD = Model->LODModels[0];
		for (const FSkelMeshSection& Section : LOD.Sections)
			for (const FSoftSkinVertex& V : Section.SoftVertices)
			{
				FVector3f Sum = FVector3f::ZeroVector; float WSum = 0, WLimb = 0, WNear = 0, WBeyond = 0;
				for (int32 K = 0; K < MAX_TOTAL_INFLUENCES; ++K)
				{
					const float W = float(V.InfluenceWeights[K]);
					if (W <= 0) continue;
					const int32 B = Section.BoneMap.IsValidIndex(V.InfluenceBones[K]) ? int32(Section.BoneMap[V.InfluenceBones[K]]) : INDEX_NONE;
					if (!SkinMat.IsValidIndex(B)) continue;
					Sum += FVector3f(SkinMat[B].TransformPosition(V.Position)) * W; WSum += W;
					if (LimbBone.IsValidIndex(B) && LimbBone[B]) WLimb += W;
					if (NearBone.IsValidIndex(B) && NearBone[B]) WNear += W;
					if (BeyondBone.IsValidIndex(B) && BeyondBone[B]) WBeyond += W;
				}
				Positions.Add(WSum > 0 ? Sum / WSum : V.Position);
				OnLimb.Add(WSum > 0 && WLimb >= .35f * WSum);
				OnNear.Add(WSum > 0 && WNear >= .5f * WSum && WBeyond < .5f * WSum);
				Blocker.Add(WSum > 0 && WBeyond >= .5f * WSum);
			}
		Indices = LOD.IndexBuffer;
	}
#endif
	if (Positions.IsEmpty() || Indices.Num() < 3) { Why = TEXT("mesh triangles are not readable here (no editor data)"); return false; }
	const FVector P0 = CompW.InverseTransformPosition(CenterW);
	const FVector A0 = CompW.InverseTransformVectorNoScale(AxisW).GetSafeNormal();
	FVector S0 = CompW.InverseTransformVectorNoScale(SideW);
	S0 = (S0 - A0 * FVector::DotProduct(S0, A0)).GetSafeNormal();
	if (A0.IsNearlyZero() || S0.IsNearlyZero()) { Why = TEXT("degenerate limb frame"); return false; }
	const double Search = SearchRadiusW / Scale;

	// One cut: plane through P, normal A; knot side D (in the plane). Fills Out (world cm), false if the plane missed.
	bool bNeighbours = false;
	auto Cut = [&](const FVector& P, const FVector& A, TArray<float>& Out, FString& CutWhy) -> bool
	{
		const FVector D = (S0 - A * FVector::DotProduct(S0, A)).GetSafeNormal();
		const FVector E = FVector::CrossProduct(A, D);
		double Near[N]; FVector2D NearPt[N];
		int32 Crossings = 0;
		bNeighbours = false;
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			const TArray<bool>& Mask = Pass == 0 ? OnLimb : OnNear;
			if (Pass == 1)
			{
				int32 Seen0 = 0;
				for (double X : Near) Seen0 += X < TNumericLimits<double>::Max();
				if (Seen0 >= N / 2 || Mask.Num() != Positions.Num()) break;
				bNeighbours = true;
			}
			for (double& X : Near) X = TNumericLimits<double>::Max();
			Crossings = 0;
			// Nearest skin crossing per angle: the limb's own surface is the closest one on every ray.
			for (int32 T = 0; T + 2 < Indices.Num(); T += 3)
				for (int32 Ed = 0; Ed < 3; ++Ed)
				{
					const uint32 I0 = Indices[T + Ed], I1 = Indices[T + (Ed + 1) % 3];
					if (!Positions.IsValidIndex(int32(I0)) || !Positions.IsValidIndex(int32(I1)) || !Mask[I0] || !Mask[I1]) continue;
					const double H0 = FVector::DotProduct(FVector(Positions[I0]) - P, A), H1 = FVector::DotProduct(FVector(Positions[I1]) - P, A);
					if ((H0 > 0) == (H1 > 0)) continue;
					const FVector Q = FVector(Positions[I0]) + (FVector(Positions[I1]) - FVector(Positions[I0])) * (H0 / (H0 - H1)) - P;
					const FVector2D Q2(FVector::DotProduct(Q, D), FVector::DotProduct(Q, E));
					const double Rho = Q2.Size();
					if (Rho > Search || Rho < 1e-3) continue;
					const int32 K = FMath::FloorToInt32((FMath::Atan2(Q2.Y, Q2.X) / (2. * PI) + 1.) * N) % N;
					if (Rho < Near[K]) { Near[K] = Rho; NearPt[K] = Q2; }
					++Crossings;
				}
		}
		int32 Seen = 0;
		for (double X : Near) Seen += X < TNumericLimits<double>::Max();
		if (Seen < N / 2) { CutWhy = FString::Printf(TEXT("the cut found skin on %d of %d sides (%d crossings)"), Seen, N, Crossings); return false; }
		// Fill unseen angles from their neighbours, convex hull (monotone chain), then its radius along each direction.
		TArray<FVector2D> Pts, Hull;
		for (int32 K = 0; K < N; ++K)
		{
			if (Near[K] < TNumericLimits<double>::Max()) { Pts.Add(NearPt[K]); continue; }
			int32 B = 1, F = 1;
			while (Near[(K - B + N) % N] == TNumericLimits<double>::Max()) ++B;
			while (Near[(K + F) % N] == TNumericLimits<double>::Max()) ++F;
			const double R = FMath::Lerp(Near[(K - B + N) % N], Near[(K + F) % N], double(B) / (B + F)), Ang = 2. * PI * (K + .5) / N;
			Pts.Add(FVector2D(FMath::Cos(Ang), FMath::Sin(Ang)) * R);
		}
		Pts.Sort([](const FVector2D& L, const FVector2D& R) { return L.X < R.X || (L.X == R.X && L.Y < R.Y); });
		auto Turn = [](const FVector2D& O, const FVector2D& Aa, const FVector2D& Bb) { return (Aa.X - O.X) * (Bb.Y - O.Y) - (Aa.Y - O.Y) * (Bb.X - O.X); };
		for (int32 Pass = 0; Pass < 2; ++Pass)
		{
			const int32 Start = Hull.Num();
			for (int32 I = 0; I < Pts.Num(); ++I)
			{
				const FVector2D& Pt = Pts[Pass ? Pts.Num() - 1 - I : I];
				while (Hull.Num() >= Start + 2 && Turn(Hull[Hull.Num() - 2], Hull.Last(), Pt) <= 0) Hull.Pop();
				Hull.Add(Pt);
			}
			Hull.Pop();
		}
		if (Hull.Num() < 3) { CutWhy = TEXT("degenerate section"); return false; }
		Out.SetNum(N);
		for (int32 K = 0; K < N; ++K)
		{
			const double Ang = 2. * PI * K / N;
			const FVector2D U(FMath::Cos(Ang), FMath::Sin(Ang));
			double Best = 0;
			for (int32 I = 0; I < Hull.Num(); ++I)
			{
				const FVector2D Aa = Hull[I], Ab = Hull[(I + 1) % Hull.Num()] - Aa;
				const double Den = U.X * Ab.Y - U.Y * Ab.X;
				if (FMath::Abs(Den) < 1e-9) continue;
				const double S = (U.Y * Aa.X - U.X * Aa.Y) / Den, Tt = (Aa.X * Ab.Y - Aa.Y * Ab.X) / Den;
				if (S >= -1e-6 && S <= 1. + 1e-6 && Tt > Best) Best = Tt;
			}
			if (Best <= 0) { CutWhy = TEXT("the limb axis is outside the skin here"); return false; }
			Out[K] = float(Best * Scale);
		}
		return true;
	};
	// Skin of the next body within the rope's reach of this loop (the rope's tube, or inside the loop at the plane).
	auto Blocked = [&](const FVector& P, const FVector& A, const TArray<float>& Prof) -> int32
	{
		const FVector D = (S0 - A * FVector::DotProduct(S0, A)).GetSafeNormal();
		const FVector E = FVector::CrossProduct(A, D);
		const double Reach = (RopeRadiusW + .6) / Scale;
		int32 Count = 0;
		for (int32 I = 0; I < Positions.Num(); ++I)
		{
			if (!Blocker[I]) continue;
			const FVector Q = FVector(Positions[I]) - P;
			const double Hh = FVector::DotProduct(Q, A);
			if (FMath::Abs(Hh) > Reach) continue;
			const FVector2D Q2(FVector::DotProduct(Q, D), FVector::DotProduct(Q, E));
			const int32 K = FMath::FloorToInt32((FMath::Atan2(Q2.Y, Q2.X) / (2. * PI) + 1.) * N + .5) % N;
			const double Loop = (Prof[K] + ClearanceW + RopeRadiusW) / Scale;	// rope centreline
			if (Q2.Size() < Loop + Reach) ++Count;
		}
		return Count;
	};
	// Candidates, smallest change first: drop along the limb (cm) and tilt (deg).
	struct FCand { double Drop, Tilt; };
	TArray<FCand> Cands;
	for (double Drop : { 0., 1., 2., 3., 4., 5. }) for (double Tilt : { 0., 8., 16., 24., 32., 40. }) Cands.Add({ Drop, Tilt });
	Cands.Sort([](const FCand& L, const FCand& R) { return L.Drop / 1.5 + L.Tilt / 10. < R.Drop / 1.5 + R.Tilt / 10.; });
	int32 BestBlocked = MAX_int32; FCand Best{ 0, 0 }; TArray<float> BestProf; bool bBestNeighbours = false;
	FString CutWhy;
	for (const FCand& C : Cands)
	{
		const double T = FMath::DegreesToRadians(C.Tilt);
		const FVector A = (A0 * FMath::Cos(T) - S0 * FMath::Sin(T)).GetSafeNormal();	// knot side up, the far side down
		const FVector P = P0 - A0 * (C.Drop / Scale);
		TArray<float> Prof;
		if (!Cut(P, A, Prof, CutWhy)) continue;
		const int32 Bl = Blocker.Contains(true) ? Blocked(P, A, Prof) : 0;
		if (Bl < BestBlocked) { BestBlocked = Bl; Best = C; BestProf = Prof; bBestNeighbours = bNeighbours; }
		if (Bl == 0) break;
	}
	if (BestBlocked == MAX_int32) { Why = CutWhy; return false; }
	Profile = BestProf;
	const double Tb = FMath::DegreesToRadians(Best.Tilt);
	OutNormalW = CompW.TransformVectorNoScale((A0 * FMath::Cos(Tb) - S0 * FMath::Sin(Tb)).GetSafeNormal()).GetSafeNormal();
	OutCenterW = CompW.TransformPosition(P0 - A0 * (Best.Drop / Scale));
	OutTiltDeg = float(Best.Tilt); OutDropCm = float(Best.Drop); OutBlocked = BestBlocked;
	Source = bBestNeighbours ? TEXT("posed mesh (limb and neighbours)") : TEXT("posed mesh");
	return true;
}

bool ComputeTie(USkeletalMeshComponent* Rope, UPrimitiveComponent* Target, FName BodyBone, FName AtBone, float Clearance, FTieGeometry& G, FString& Error)
{
	auto* State = NooseStates.Find(Rope);
	UProphecyNooseComponent* Noose = State ? State->Noose.Get() : nullptr;
	auto* Prop = Rope ? UProphecyJoltSkeletalPropComponent::Find(Rope) : nullptr;
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	if (!Noose || !Prop || !Prop->IsJoltStepClientActive() || !Native) { Error = TEXT("The rope and its noose are not in Jolt (yet)."); return false; }
	if (!Prop->GetBodyHandle(State->TipBone, G.TipBody)) { Error = TEXT("Rope end body missing."); return false; }
	if (!BodyOf(Target, BodyBone, G.LimbBody)) { Error = FString::Printf(TEXT("%s.%s has no Jolt body."), *GetNameSafe(Target), *BodyBone.ToString()); return false; }
	if (!LimbGeometry(Target, BodyBone, AtBone, G.Center, G.Axis, G.LimbRadius, Error)) return false;
	FTransform Tip;
	if (!ReadPose(Native, G.TipBody, Tip) || !ReadPose(Native, G.LimbBody, G.LimbPose)) { Error = TEXT("Cannot read the bodies."); return false; }
	const FTransform NooseWorld(Noose->GetComponentQuat(), Noose->GetComponentLocation());
	const FVector Up = NooseWorld.GetUnitAxis(EAxis::Z);	// the rope's pull, seen from its end
	// A hangman's knot: the coil is wrapped around the standing part, so it runs along the rope, beside the loop, and
	// the rope leaves from its top. A hanged body hangs from its extremity (the head side of a neck, the foot side of an
	// ankle): the coil runs along the limb towards it, leaning out by KnotLeanDegrees, the loop square to the limb.
	FVector Ext = G.Axis;
	{
		const double Away = FVector::DotProduct(G.Center - Target->Bounds.Origin, G.Axis);
		if (FMath::Abs(Away) > 1.0) { if (Away < 0) Ext = -Ext; }
		else if (FVector::DotProduct(Up, G.Axis) < 0) Ext = -Ext;	// limb across the body's middle: towards the rope
	}
	const double Lean = FMath::DegreesToRadians(KnotLeanDegrees);
	auto CoilDir = [&](const FVector& S) { return (Ext * FMath::Cos(Lean) + S * FMath::Sin(Lean)).GetSafeNormal(); };
	// Knot side: where the rope pulls, seen across the limb; if the rope runs along the limb, the target's side.
	FVector Side = Up - G.Axis * FVector::DotProduct(Up, G.Axis);
	const double Across = Side.Size();
	// Only a rope pulling clearly across the limb (> ~45 deg off its axis) picks the side; near the axis that projection
	// is unstable (a swaying rope would flip the knot from one side to the other between two calls).
	if (Across < .7)
	{
		// The rope runs along the limb: the knot goes behind it (the back of the neck, the heel side of an ankle) unless
		// something is in the way there, then on a side, the front last. Judged from every other bone against where the
		// coil will stand. Facing: from the heels to the balls of the feet when the skeleton has them, else the mesh's +Y
		// (the skeletal mesh convention: characters face +Y in their component).
		FVector Facing = Target->GetComponentQuat().GetRightVector();
		if (auto* Skel = Cast<USkeletalMeshComponent>(Target))
		{
			FVector Sum = FVector::ZeroVector;
			for (const TCHAR* Side2 : { TEXT("l"), TEXT("r") })
			{
				const FName Ball(*FString::Printf(TEXT("ball_%s"), Side2)), Foot(*FString::Printf(TEXT("foot_%s"), Side2));
				if (Skel->GetBoneIndex(Ball) != INDEX_NONE && Skel->GetBoneIndex(Foot) != INDEX_NONE)
					Sum += (Skel->GetBoneLocation(Ball) - Skel->GetBoneLocation(Foot)).GetSafeNormal();
			}
			if (Sum.SizeSquared() > .25) Facing = Sum.GetSafeNormal();
		}
		Facing = (Facing - G.Axis * FVector::DotProduct(Facing, G.Axis)).GetSafeNormal();
		if (Facing.IsNearlyZero()) Facing = FVector::CrossProduct(G.Axis, FVector::UpVector).GetSafeNormal();
		const FVector Across2 = FVector::CrossProduct(G.Axis, Facing).GetSafeNormal();
		const FVector Candidates[] = { -Facing, Across2, -Across2, Facing };
		const float Out0 = G.LimbRadius + Noose->RopeRadius * 4.f, Len = Noose->GetCoilLength() + Noose->GetKnotTop();
		// Every bone outside the tied limb, the next body's own bones too (a foot's ball and toes reach forward of the
		// ankle: a coil there would run through the foot).
		TArray<FVector> Others;
		if (auto* Skel = Cast<USkeletalMeshComponent>(Target); Skel && Skel->GetSkeletalMeshAsset())
		{
			const UPhysicsAsset* PA = Skel->GetPhysicsAsset();
			const FReferenceSkeleton& Ref = Skel->GetSkeletalMeshAsset()->GetRefSkeleton();
			const int32 LimbIndex = Ref.FindBoneIndex(BodyBone);
			TArray<bool> InLimb; InLimb.Init(false, Ref.GetNum());
			for (int32 B = 0; B < Ref.GetNum(); ++B)
			{
				const int32 Parent = Ref.GetParentIndex(B);
				InLimb[B] = B == LimbIndex || (Parent != INDEX_NONE && InLimb[Parent] && (!PA || PA->FindBodyIndex(Ref.GetBoneName(B)) == INDEX_NONE));
				if (!InLimb[B]) Others.Add(Skel->GetBoneLocation(Ref.GetBoneName(B)));
			}
		}
		double Clears[4], Best = 0;
		for (int32 K = 0; K < 4; ++K)
		{
			const FVector C = Candidates[K];
			Clears[K] = TNumericLimits<double>::Max();
			for (const FVector& O : Others)
				Clears[K] = FMath::Min(Clears[K], FMath::PointDistToSegment(O, G.Center + C * Out0, G.Center + C * Out0 + CoilDir(C) * Len));
			Best = FMath::Max(Best, Clears[K]);
		}
		// The first side in order of preference that is clear enough: 8 cm from every other bone, or nearly the best.
		Side = FVector::ZeroVector;
		for (int32 K = 0; K < 4 && Side.IsNearlyZero(); ++K)
			if (Clears[K] >= FMath::Min(8.0, .7 * Best)) Side = Candidates[K];
		if (Side.IsNearlyZero()) Side = FVector::CrossProduct(G.Axis, FVector::UpVector);
	}
	G.Side = Side.GetSafeNormal();
	// The noose is one rigid piece: the loop square to the limb, the coil standing beside it along the rope.
	G.LoopNormal = Ext;
	G.CoilAxis = CoilDir(G.Side);
	G.TiltDeg = float(KnotLeanDegrees);
	const float Clear = FMath::Max(Clearance, 0.f);
	G.Inner = G.LimbRadius + Clear;
	// The loop hugs the visible skin; the knot stays outside both the skin and the collision capsule.
	FString Why;
	auto* Skin = Cast<USkeletalMeshComponent>(Target);
	FVector FitCenter = G.Center, FitNormal = G.LoopNormal;
	float FitTilt = 0, FitDrop = 0; int32 FitBlocked = 0;
	if (Skin && !MeasureSkin(Skin, BodyBone, G.Center, G.LoopNormal, G.Side, 2.5f * G.LimbRadius + 4.f, Noose->RopeRadius, Clear, G.Profile, G.SkinSource, Why,
		FitCenter, FitNormal, FitTilt, FitDrop, FitBlocked))
	{
		UE_LOG(LogProphecyNoose, Display, TEXT("Noose: no skin fit on %s.%s (%s) - loop sized to the capsule."), *GetNameSafe(Target), *BodyBone.ToString(), *Why);
	}
	else if (Skin)
	{
		const float Mean = [&] { float S = 0; for (float P : G.Profile) S += P; return S / G.Profile.Num(); }();
		if (Mean < .35f * G.LimbRadius || Mean > 3.f * G.LimbRadius)
		{
			UE_LOG(LogProphecyNoose, Warning, TEXT("Noose: skin of %s.%s measured %.1f cm against a %.1f cm capsule - using the capsule."),
				*GetNameSafe(Target), *BodyBone.ToString(), Mean, G.LimbRadius);
			G.Profile.Reset(); G.SkinSource = TEXT("capsule");
		}
		else
		{
			for (float& P : G.Profile) P += Clear;
			G.Inner = FMath::Max(G.Inner, G.Profile[0]);
			// On the neck, under the head: lowered and tilted (far side down) until clear of the next body's skin.
			G.Center = FitCenter; G.LoopNormal = FitNormal;
			G.LoopTiltDeg = FitTilt; G.DropCm = FitDrop; G.Blocked = FitBlocked;
		}
	}
	const float Rc = G.Inner + Noose->RopeRadius;
	// The coil's foot sits on the loop's knot side, in the loop plane; its top (the rope end) is up the coil.
	const FVector SideInLoop = (G.Side - G.LoopNormal * FVector::DotProduct(G.Side, G.LoopNormal)).GetSafeNormal();
	G.NooseOrigin = G.Center + SideInLoop * (Rc + Noose->GetKnotStandoff()) + G.CoilAxis * (Noose->GetKnotTop() + Noose->GetCoilLength());
	// Noose frame: Z up the coil, X across it towards the knot side; the loop lies on the -X side.
	G.NooseRotation = FRotationMatrix::MakeFromZX(G.CoilAxis, G.Side).ToQuat();
	// The noose is fixed on the rope end: the end goes wherever puts the noose there.
	const FTransform NooseOnTip = NooseWorld.GetRelativeTransform(FTransform(Tip.GetRotation(), Tip.GetLocation()));
	const FTransform TipDesired = NooseOnTip.Inverse() * FTransform(G.NooseRotation, G.NooseOrigin);
	G.Tip = TipDesired.GetLocation();
	G.TipRotation = TipDesired.GetRotation();
	return true;
}

// Locks the coil's collider to its carrier body, at BoxWorld.
bool LockCoil(UProphecyJoltWorldSubsystem& Native, FNooseState& State, const FProphecyJoltBodyHandle& Carrier, const FTransform& CarrierPose, const FTransform& BoxWorld)
{
	if (!Native.OwnsBody(State.CoilBody)) return false;
	if (Native.OwnsJoint(State.CoilJoint)) Native.DestroyJoint(State.CoilJoint);
	State.CoilJoint = {};
	FProphecyJoltJointSettings S;
	S.Type = EProphecyJoltJointType::HardSixDOF;	// all axes locked
	S.BodyA = Carrier; S.BodyB = State.CoilBody;
	S.FrameA = BoxWorld.GetRelativeTransform(CarrierPose);
	S.FrameB = FTransform::Identity;
	return Native.CreateJoint(S, {}, State.CoilJoint).IsSuccess();
}

// The coil collides like the rest of the rope: a light box the size of the wraps, locked to whatever carries the noose
// (the rope end, or the tied limb). It never touches the rope's own bodies; when tied, not the tied limb either.
void AddCoilCollider(USkeletalMeshComponent* Rope, FNooseState& State, UProphecyJoltSkeletalPropComponent& Prop,
	UProphecyJoltWorldSubsystem& Native, const FProphecyJoltBodyHandle& TipH)
{
	UProphecyNooseComponent* Noose = State.Noose.Get();
	FTransform Tip;
	if (!Noose || Native.OwnsBody(State.CoilBody) || !ReadPose(&Native, TipH, Tip)) return;
	FVector BoxC, BoxH;
	Noose->GetCoilBox(BoxC, BoxH);
	const FTransform NooseWorld(Noose->GetComponentQuat(), Noose->GetComponentLocation());
	const FTransform BoxOnTip = FTransform(BoxC) * NooseWorld.GetRelativeTransform(FTransform(Tip.GetRotation(), Tip.GetLocation()));
	const FTransform BoxWorld = BoxOnTip * FTransform(Tip.GetRotation(), Tip.GetLocation());
	FProphecyJoltFixtureBodySettings Settings;
	Settings.PositionCm = BoxWorld.GetLocation();
	Settings.Rotation = BoxWorld.GetRotation();
	Settings.bDynamic = true;
	Settings.MassKg = .3;
	Settings.Friction = .9f;
	Settings.AssociatedObject = Rope;
	Settings.ObjectChannel = Rope->GetCollisionObjectType();
	Settings.CollisionResponses = Rope->GetCollisionResponseToChannels();
	const double Convex = FMath::Min(.5, .4 * BoxH.GetMin());
	auto Result = Native.CreateBox(BoxH, Convex, Settings, State.CoilBody);
	const bool bLocked = Result.IsSuccess() && LockCoil(Native, State, TipH, FTransform(Tip.GetRotation(), Tip.GetLocation()), BoxWorld);
	if (Result.IsSuccess())
	{
		State.CoilPairs.Reset();
		if (const UPhysicsAsset* PA = Rope->GetPhysicsAsset())
			for (const auto& Setup : PA->SkeletalBodySetups)
			{
				FProphecyJoltBodyHandle H;
				if (Setup && Prop.GetBodyHandle(Setup->BoneName, H)) State.CoilPairs.Add({ State.CoilBody, H });
			}
		Result = Native.UpdateBodySuppressedPairs(State.CoilBody, State.CoilPairs);
	}
	if (!Result.IsSuccess() || !bLocked)
	{
		if (Native.OwnsJoint(State.CoilJoint)) Native.DestroyJoint(State.CoilJoint);
		if (Native.OwnsBody(State.CoilBody)) Native.DestroyBody(State.CoilBody);
		State.CoilBody = {}; State.CoilJoint = {};
	}
	UE_LOG(LogProphecyNoose, Display, TEXT("Noose coil collider %.0f x %.0f x %.0f cm on %s.%s: %s"), 2 * BoxH.X, 2 * BoxH.Y, 2 * BoxH.Z,
		*Rope->GetName(), *State.TipBone.ToString(), !Result.IsSuccess() ? *Result.Message : (bLocked ? TEXT("locked to the rope end") : TEXT("lock failed")));
}

// Puts the noose back on the rope end bone (after a tie has closed, or when it is undone).
// The whole hanging rope is drawn by this module, as one tube with the noose's own rope (same thickness, same
// pattern), from where it leaves the gallows down into the top of the knot. The skinned rope stays as the physics
// rig (its bodies, joints and bones are untouched) but is no longer rendered: rope and knot are then one rope by
// construction, a reeled rope simply gets shorter (no shrunk or collapsed links), and the solver's fine shake of the
// links is smoothed out of the drawing (the ends stay exact: the gallows and the knot).
FTransform RefComponentTransform(const FReferenceSkeleton& Ref, int32 B)
{
	return B == INDEX_NONE ? FTransform::Identity : FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, B);
}

void SetRopeDrawnBySkin(USkeletalMeshComponent* Rope, FNooseState& State, bool bSkin)
{
	// The skinned rope and any copy of it the gallows renders (a posed copy can be made later, so this rescans).
	const double Now = Rope->GetWorld() ? Rope->GetWorld()->GetTimeSeconds() : 0.0;
	if (State.bRopeDrawnBySkin == bSkin && (bSkin || Now < State.NextSkinScan)) return;
	State.NextSkinScan = Now + 0.5;
	if (bSkin)
	{
		for (const TWeakObjectPtr<UPrimitiveComponent>& C : State.HiddenSkins) if (C.IsValid()) C->SetHiddenInGame(false, false);
		State.HiddenSkins.Reset();
	}
	else
	{
		const USkinnedAsset* Asset = Rope->GetSkinnedAsset();
		for (TObjectIterator<USkinnedMeshComponent> It; It; ++It)
		{
			USkinnedMeshComponent* C = *It;
			if (!C || C->GetWorld() != Rope->GetWorld() || C->GetSkinnedAsset() != Asset || C->HasAnyFlags(RF_ClassDefaultObject)) continue;
			// Same rope asset near this rope (the gallows may render it from a child actor).
			if (C != Rope && FVector::Dist(C->GetComponentLocation(), Rope->GetComponentLocation()) > 800.0) continue;
			if (!C->GetVisibleFlag() || C->bHiddenInGame || State.HiddenSkins.Contains(C)) continue;
			State.HiddenSkins.Add(C);
			UE_LOG(LogProphecyNoose, Display, TEXT("Noose rope: %s (%s) hidden, the rope is drawn by the noose"), *C->GetName(), *C->GetClass()->GetName());
		}
	}
	State.bRopeDrawnBySkin = bSkin;
	if (UProceduralMeshComponent* TubeComp = State.RopeTube.Get()) TubeComp->SetVisibility(!bSkin, false);
}

// A stand-in of the hanging rope the gallows may show while its skinned rope is hidden: a long thin static mesh of the
// same actor reaching down to the knot. Checked every frame (the gallows may show it again each tick).
void HideRopeStandIns(USkeletalMeshComponent* Rope, FNooseState& State)
{
	AActor* Owner = Rope->GetOwner();
	if (!Owner || !State.Noose.IsValid()) return;
	TArray<UStaticMeshComponent*> Statics;
	Owner->GetComponents(Statics);
	const FVector Knot = State.Noose->GetComponentLocation();
	for (UStaticMeshComponent* C : Statics)
	{
		if (!C || !C->GetVisibleFlag() || C->bHiddenInGame) continue;
		const FBox Box = C->Bounds.GetBox();
		const FVector Ext = Box.GetExtent();
		// The gallows' own stand-in (a stretched cylinder named "rope"), or any long thin mesh reaching the knot.
		const bool bNamed = C->GetName().Equals(TEXT("rope"), ESearchCase::IgnoreCase) || GetNameSafe(C->GetStaticMesh()) == TEXT("Cylinder");
		const bool bNear = Box.ComputeSquaredDistanceToPoint(Knot) < 60.0 * 60.0 && Ext.GetMax() > 4.0 * FMath::Max(Ext.GetMin(), 1.0);
		if (!bNamed && !bNear) continue;
		if (!State.HiddenSkins.Contains(C))
		{
			State.HiddenSkins.Add(C);
			UE_LOG(LogProphecyNoose, Display, TEXT("Noose rope: %s (%s) hidden, a stand-in of the hanging rope"), *C->GetName(), *GetNameSafe(C->GetStaticMesh()));
		}
		C->SetHiddenInGame(true, false);
	}
}

void MoveTetherAnchor(USkeletalMeshComponent* Rope, FNooseState& State);
void UpdateRopeTube(TWeakObjectPtr<USkeletalMeshComponent> WeakRope)
{
	USkeletalMeshComponent* Rope = WeakRope.Get();
	FNooseState* State = Rope ? NooseStates.Find(Rope) : nullptr;
	UWorld* World = Rope ? Rope->GetWorld() : nullptr;
	if (!State || !World) return;
	// Once per frame, after physics and bone updates (timers run after the post-physics tick group).
	World->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateLambda([WeakRope] { UpdateRopeTube(WeakRope); }));
	MoveTetherAnchor(Rope, *State);
	UProphecyNooseComponent* Noose = State->Noose.Get();
	UProceduralMeshComponent* TubeComp = State->RopeTube.Get();
	auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Rope);
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	const USkeletalMesh* Mesh = Rope->GetSkeletalMeshAsset();
	if (!Noose || !TubeComp || !Mesh)
	{
		SetRopeDrawnBySkin(Rope, *State, true);
		return;
	}
	// The links: the simulated bodies once the rope is in Jolt, its bones before (so it is drawn from the first frame).
	const bool bJolt = Prop && Native && Prop->IsJoltStepClientActive();
	// Where the rope leaves the gallows: the reel's anchor (the first link's bind position), and the way down.
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	const FTransform CompW = Rope->GetComponentTransform();
	const int32 First = Ref.FindBoneIndex(TEXT("joint")), Second = Ref.FindBoneIndex(TEXT("joint1"));
	const FVector Anchor = CompW.TransformPosition(RefComponentTransform(Ref, First).GetLocation());
	const FVector Down = CompW.TransformVectorNoScale(RefComponentTransform(Ref, Second).GetLocation() - RefComponentTransform(Ref, First).GetLocation()).GetSafeNormal();
	TArray<FVector> Links;	// paid-out links, top to bottom, below the anchor
	for (int32 I = 0; I < State->RopeChain.Num() - 1; ++I)	// all but the rope end: the knot takes its place
	{
		FVector P; bool bHave = false;
		FProphecyJoltBodyHandle H; FTransform Pose;
		if (bJolt && Prop->GetBodyHandle(State->RopeChain[I], H) && ReadPose(Native, H, Pose)) { P = Pose.GetLocation(); bHave = true; }
		else if (Rope->GetBoneIndex(State->RopeChain[I]) != INDEX_NONE) { P = Rope->GetBoneLocation(State->RopeChain[I]); bHave = true; }
		if (bHave && !P.ContainsNaN() && FVector::DotProduct(P - Anchor, Down) > 2.0) Links.Add(P);
	}
	// Into the knot: down the coil's standing strand (it enters inside the coil), straight along the coil's axis.
	const FTransform NooseW = Noose->GetComponentTransform();
	const FVector* EntryLocal = ProphecyNooseMesh::GEntrance.Find(Noose);
	const FVector EL = EntryLocal ? *EntryLocal : FVector(0, 0, -(Noose->GetKnotTop() + 1.5f * Noose->RopeRadius));
	const FVector Axis = Noose->GetUpVector();
	const FVector Entry = NooseW.TransformPosition(EL), TopW = NooseW.TransformPosition(FVector(EL.X, EL.Y, 0.0));
	const FVector Q3 = TopW + Axis * 6.0;
	// The rope between the gallows and the knot as one smooth cubic, fitted to the links (least squares): it keeps the
	// rope's sway and bend but none of the links' small shake. End points exact; it leaves the knot along the coil.
	const FVector P0 = Anchor;
	auto Bern = [](double T, double& B0, double& B1, double& B2, double& B3)
	{
		const double U = 1 - T; B0 = U * U * U; B1 = 3 * U * U * T; B2 = 3 * U * T * T; B3 = T * T * T;
	};
	TArray<double> Ts;
	{
		double Len = 0; FVector Prev = P0;
		TArray<double> Acc;
		for (const FVector& L : Links) { Len += FVector::Dist(Prev, L); Acc.Add(Len); Prev = L; }
		Len += FVector::Dist(Prev, Q3);
		for (double A : Acc) Ts.Add(Len > 1e-3 ? A / Len : 0.5);
	}
	FVector P1 = FMath::Lerp(P0, Q3, 1.0 / 3.0);
	double Lambda = FVector::Dist(P0, Q3) / 3.0;
	bool bFit = false;
	if (Links.Num() >= 2)
	{
		double N[4][5] = {};
		for (int32 I = 0; I < Links.Num(); ++I)
		{
			double B0, B1, B2, B3; Bern(Ts[I], B0, B1, B2, B3);
			const FVector R = Links[I] - P0 * B0 - Q3 * (B2 + B3);
			const double J[3][4] = { { B1, 0, 0, B2 * Axis.X }, { 0, B1, 0, B2 * Axis.Y }, { 0, 0, B1, B2 * Axis.Z } };
			const double Rv[3] = { R.X, R.Y, R.Z };
			for (int32 K = 0; K < 3; ++K)
				for (int32 A = 0; A < 4; ++A)
				{
					for (int32 B = 0; B < 4; ++B) N[A][B] += J[K][A] * J[K][B];
					N[A][4] += J[K][A] * Rv[K];
				}
		}
		bFit = true;
		for (int32 C = 0; C < 4 && bFit; ++C)	// Gauss-Jordan with partial pivoting
		{
			int32 Pv = C;
			for (int32 Rr = C + 1; Rr < 4; ++Rr) if (FMath::Abs(N[Rr][C]) > FMath::Abs(N[Pv][C])) Pv = Rr;
			if (FMath::Abs(N[Pv][C]) < 1e-9) { bFit = false; break; }
			for (int32 K = 0; K < 5; ++K) Swap(N[C][K], N[Pv][K]);
			for (int32 Rr = 0; Rr < 4; ++Rr)
				if (Rr != C)
				{
					const double F = N[Rr][C] / N[C][C];
					for (int32 K = 0; K < 5; ++K) N[Rr][K] -= F * N[C][K];
				}
		}
		if (bFit)
		{
			P1 = FVector(N[0][4] / N[0][0], N[1][4] / N[1][1], N[2][4] / N[2][2]);
			Lambda = N[3][4] / N[3][3];
		}
	}
	if (P1.ContainsNaN() || !FMath::IsFinite(Lambda) || FVector::Dist(P1, P0) > 2000.0) { P1 = FMath::Lerp(P0, Q3, 1.0 / 3.0); Lambda = FVector::Dist(P0, Q3) / 3.0; bFit = false; }
	Lambda = FMath::Clamp(Lambda, 2.0, .6 * FVector::Dist(P0, Q3) + 2.0);
	// How well one cubic holds the rope; a rope in loops (slack on the ground) is drawn through its links instead.
	double Worst = 0;
	for (int32 I = 0; I < Links.Num(); ++I)
	{
		double B0, B1, B2, B3; Bern(Ts[I], B0, B1, B2, B3);
		Worst = FMath::Max(Worst, FVector::Dist(Links[I], P0 * B0 + P1 * B1 + (Q3 + Axis * Lambda) * B2 + Q3 * B3));
	}
	const bool bCubic = Links.Num() < 2 || (bFit && Worst < 15.0);
	// Steady in time: the free controls follow over a few frames (the ends never lag).
	if (!State->bSmoothValid || State->SmoothP1.ContainsNaN() || !FMath::IsFinite(State->SmoothLambda) || FVector::Dist(State->SmoothP1, P1) > 40.0) { State->SmoothP1 = P1; State->SmoothLambda = Lambda; }
	State->SmoothP1 = FMath::Lerp(State->SmoothP1, P1, .25);
	State->SmoothLambda = FMath::Lerp(State->SmoothLambda, Lambda, .25);
	State->bSmoothValid = true;
	TArray<FVector> Path;	// from the knot upward (the rope's pattern stays put on the rope as it reels)
	Path.Add(Entry);
	Path.Add(TopW);
	if (bCubic)
	{
		const FVector C1 = State->SmoothP1, C2 = Q3 + Axis * State->SmoothLambda;
		const int32 Samples = FMath::Clamp(FMath::CeilToInt32(FVector::Dist(P0, Q3) / 5.0), 8, 90);
		for (int32 I = Samples; I >= 0; --I)
		{
			double B0, B1, B2, B3; Bern(double(I) / Samples, B0, B1, B2, B3);
			Path.Add(P0 * B0 + C1 * B1 + C2 * B2 + Q3 * B3);
		}
	}
	else
	{
		TArray<FVector> Pts = { Q3 };
		for (int32 I = Links.Num() - 1; I >= 0; --I) Pts.Add(Links[I]);
		Pts.Add(P0);
		for (int32 I = 0; I + 1 < Pts.Num(); ++I)
		{
			const FVector A0 = Pts[FMath::Max(I - 1, 0)], A1 = Pts[I], A2 = Pts[I + 1], A3 = Pts[FMath::Min(I + 2, Pts.Num() - 1)];
			const int32 Sub = FMath::Clamp(FMath::CeilToInt32(FVector::Dist(A1, A2) / 4.0), 1, 4);
			for (int32 K = 0; K < Sub; ++K)
			{
				const float T = float(K) / Sub, T2 = T * T, T3 = T2 * T;
				Path.Add(0.5f * ((2.f * A1) + (-A0 + A2) * T + (2.f * A0 - 5.f * A1 + 4.f * A2 - A3) * T2 + (-A0 + 3.f * A1 - 3.f * A2 + A3) * T3));
			}
		}
		Path.Add(P0);
	}
	// Never hand the renderer a broken shape (a NaN or a point kilometres away would poison its bounds).
	for (const FVector& P : Path)
		if (P.ContainsNaN() || FVector::DistSquared(P, Anchor) > 2000.0 * 2000.0)
		{
			if (!State->bLoggedBadPath) UE_LOG(LogProphecyNoose, Warning, TEXT("Noose rope: bad drawn path (%s) - frame skipped (logged once)"), *P.ToString());
			State->bLoggedBadPath = true; State->bSmoothValid = false;
			return;
		}
	// Twice a second for the first 30 s: what the drawing does (diagnostics).
	State->DiagClock += World->GetDeltaSeconds();
	if (State->DiagClock >= .5 && World->GetTimeSeconds() < 30.0)
	{
		State->DiagClock = 0;
		float NeckLen = 0;	// tied: how far neck_01, neck_02 and head sit from where their parents put them (joint gaps, cm)
		if (auto* Body = Cast<USkeletalMeshComponent>(State->Target.Get()); Body && State->bTied && Body->GetSkeletalMeshAsset())
		{
			const FReferenceSkeleton& RS = Body->GetSkeletalMeshAsset()->GetRefSkeleton();
			for (const TCHAR* Name : { TEXT("neck_01"), TEXT("neck_02"), TEXT("head") })
			{
				const int32 B = RS.FindBoneIndex(Name), P = B != INDEX_NONE ? RS.GetParentIndex(B) : INDEX_NONE;
				if (P == INDEX_NONE) continue;
				const FTransform ParentW = Body->GetBoneTransform(P);
				NeckLen += float(FVector::Dist(Body->GetBoneTransform(B).GetLocation(), (RS.GetRefBonePose()[B] * ParentW).GetLocation()));
			}
		}
		double TetherGap = 0;	// load tether: its length minus the actual root-to-load distance (< 0: stretched past it)
		{
			FTransform RootP, LimbP;
			if (State->bTetherOnLimb && Native && ReadPose(Native, State->TipTetherSettings.BodyA, RootP) && ReadPose(Native, State->TipTetherSettings.BodyB, LimbP))
				TetherGap = State->TipTetherSettings.Translation[0].Maximum - FVector::Dist(RootP.GetLocation(), (State->TipTetherSettings.FrameB * LimbP).GetLocation());
		}
		UE_LOG(LogProphecyNoose, Display, TEXT("Noose rope tick: %d links, %s, worst %.1f cm, %d path points, lambda %.1f, neck %.2f cm, tether %.1f cm (reeled in %.1f since the tie), slack %.2f cm"), Links.Num(), bCubic ? TEXT("cubic") : TEXT("through links"), Worst, Path.Num(), State->SmoothLambda, NeckLen,
			State->TipTetherSettings.Translation[0].Maximum, State->TetherReelLength * (ProphecyPotenceRope::GetAmount(Rope) - State->TetherAmount0), TetherGap);
	}
	using namespace ProphecyNooseMesh;
	FMeshOut M;
	Tube(M, Path, Noose->RopeRadius, Noose->Sides, Noose->UVAroundPerTurn, Noose->UVAlongPerCm, 0.f, true, true);
	if (TubeComp->GetNumSections() > 0 && TubeComp->GetProcMeshSection(0) && TubeComp->GetProcMeshSection(0)->ProcVertexBuffer.Num() == M.V.Num())
		TubeComp->UpdateMeshSection(0, M.V, M.N, M.UV, TArray<FColor>(), M.T);
	else
	{
		TubeComp->CreateMeshSection(0, M.V, M.I, M.N, M.UV, TArray<FColor>(), M.T, false);
		TubeComp->SetMaterial(0, Noose->GetMaterial(0));
	}
	SetRopeDrawnBySkin(Rope, *State, false);
	HideRopeStandIns(Rope, *State);
	// Hidden "in game" (the reel shows the skinned rope again with SetVisibility every update; that flag alone no
	// longer brings it back).
	for (const TWeakObjectPtr<UPrimitiveComponent>& C : State->HiddenSkins)
		if (C.IsValid() && !C->bHiddenInGame) C->SetHiddenInGame(true, false);
	// Every 4 s while tied: the tie's hold.
	State->LogClock += World->GetDeltaSeconds();
	if (State->bTied && State->LogClock >= 4.0)
	{
		State->LogClock = 0;
		float Lin = 0, Ang = 0;
		UProphecyNooseLibrary::GetNooseTieError(Rope, Lin, Ang);
		UE_LOG(LogProphecyNoose, Display, TEXT("Noose rope drawn: %d links paid out, %.0f cm; tie %.2f cm / %.1f deg"), Links.Num(),
			[&] { double L = 0; for (int32 I = 1; I < Path.Num(); ++I) L += FVector::Dist(Path[I - 1], Path[I]); return L; }(), Lin, Ang);
	}
}

void SeatNooseOnRope(USkeletalMeshComponent* Rope, FNooseState& State)
{
	if (UWorld* World = Rope ? Rope->GetWorld() : nullptr) World->GetTimerManager().ClearTimer(State.CloseTimer);
	State.bClosing = false;
	if (UProphecyNooseComponent* Noose = State.Noose.Get(); Noose && IsValid(Rope))
	{
		Noose->AttachToComponent(Rope, FAttachmentTransformRules::KeepRelativeTransform, State.TipBone);
		Noose->SetRelativeTransform(State.NooseOnBone);
		UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
		auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Rope);
		FProphecyJoltBodyHandle TipH; FTransform Tip;
		if (Native && Prop && Prop->GetBodyHandle(State.TipBone, TipH) && ReadPose(Native, TipH, Tip))
		{
			FVector BoxC, BoxH; Noose->GetCoilBox(BoxC, BoxH);
			LockCoil(*Native, State, TipH, Tip, FTransform(BoxC) * FTransform(Noose->GetComponentQuat(), Noose->GetComponentLocation()));
		}
	}
}

constexpr double MinLimbMassKg = 3.0;

// The tied body and every light body between it and the trunk (up the physics-asset parents), lighter than MinLimbMassKg.
void CollectLightChain(USkeletalMeshComponent* Skel, UProphecyJoltSkeletalPropComponent* Prop, FName Bone, TArray<TPair<FName, double>>& Out)
{
	const UPhysicsAsset* PA = Skel ? Skel->GetPhysicsAsset() : nullptr;
	for (int32 Guard = 0; PA && !Bone.IsNone() && Guard < 8; ++Guard)
	{
		if (PA->FindBodyIndex(Bone) != INDEX_NONE)
		{
			const double Mass = Prop->GetCapturedBodyMassKg(Bone);
			if (Mass <= 0 || Mass >= MinLimbMassKg) break;
			Out.Add({ Bone, Mass });
		}
		Bone = Skel->GetParentBone(Bone);
	}
}

// Raises the light chain to MinLimbMassKg (props only; held, kinematic bodies take it once released).
void TryApplyLimbMass(FNooseState& State)
{
	if (!State.bLimbMassPending) return;
	auto* Skel = Cast<USkeletalMeshComponent>(State.Target.Get());
	auto* Prop = Skel ? UProphecyJoltSkeletalPropComponent::Find(Skel) : nullptr;
	if (!Prop) { State.bLimbMassPending = false; return; }
	for (const auto& B : State.RaisedBodies) if (!Prop->IsBodyDynamic(B.Key)) return;
	FString Error, Names;
	for (const auto& B : State.RaisedBodies)
	{
		Prop->SetBodyMassKg(B.Key, float(MinLimbMassKg), Error);
		Names += FString::Printf(TEXT("%s%s %.2f"), Names.IsEmpty() ? TEXT("") : TEXT(", "), *B.Key.ToString(), B.Value);
	}
	State.bLimbMassPending = false; State.bLimbMassApplied = true;
	UE_LOG(LogProphecyNoose, Display, TEXT("Noose: %s carries %.1f kg per body while tied (%s kg before)"), *GetNameSafe(Skel), MinLimbMassKg, *Names);
}

bool TryTetherOnLimb(USkeletalMeshComponent* Rope, FNooseState& State);

// One step of a tie closing: the tie joint's rope-side frame moves from where the rope end was to where it belongs,
// so the end is drawn in instead of snapping; meanwhile the noose already sits on the limb.
void StepClosing(TWeakObjectPtr<USkeletalMeshComponent> WeakRope)
{
	USkeletalMeshComponent* Rope = WeakRope.Get();
	FNooseState* State = Rope ? NooseStates.Find(Rope) : nullptr;
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	if (!State || !State->bClosing) return;
	if (!Native || !Native->OwnsJoint(State->Tie))
	{
		if (UWorld* World = Rope->GetWorld()) World->GetTimerManager().ClearTimer(State->CloseTimer);
		State->bClosing = false;
		return;
	}
	UProphecyNooseComponent* Noose = State->Noose.Get();
	const double Seconds = Noose ? FMath::Max(double(Noose->TieCloseSeconds), 1e-3) : 1e-3;
	State->CloseElapsed += 1.0 / 60.0;
	const float A = FMath::SmoothStep(0.f, 1.f, float(FMath::Clamp(State->CloseElapsed / Seconds, 0.0, 1.0)));
	FProphecyJoltJointSettings S = State->TieSettings;
	S.FrameA.Blend(State->TieFrameStart, State->TieFrameEnd, A);
	if (Native->UpdateJoint(State->Tie, S).IsSuccess()) State->TieSettings = S;
	TryApplyLimbMass(*State);
	if (State->bTetherPending) TryTetherOnLimb(Rope, *State);
	if (State->CloseElapsed >= Seconds && ((!State->bLimbMassPending && !State->bTetherPending) || State->CloseElapsed > 30.0))
	{
		if (State->bTetherPending)
			UE_LOG(LogProphecyNoose, Warning, TEXT("Noose: load tether to the limb never took (%s) - the rope carries the load."), *State->TetherError);
		State->bTetherPending = false;
		if (UWorld* World = Rope->GetWorld()) World->GetTimerManager().ClearTimer(State->CloseTimer);
		State->bClosing = false;
		State->bLimbMassPending = false;
	}
}

FProphecyJoltJointSettings MakeTether(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B, double Radius,
	const FTransform& FrameB = FTransform::Identity)
{
	FProphecyJoltJointSettings S;
	S.Type = EProphecyJoltJointType::HardSixDOF;
	S.BodyA = A; S.BodyB = B;
	S.FrameB = FrameB;
	for (int32 I = 0; I < 3; ++I)
	{
		S.Translation[I] = { EProphecyJoltAxisMotion::Limited, -Radius, Radius };
		S.Rotation[I] = { EProphecyJoltAxisMotion::Free, 0.0, 0.0 };
	}
	S.bRadialTranslation = true;
	return S;
}

// Longest straight distance the rope end may be from the root body: the paid-out rope plus a little slack.
bool TetherRadius(USkeletalMeshComponent* Rope, FNooseState& State, double& Radius)
{
	auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Rope);
	FProphecyJoltBodyHandle RootH;
	FTransform Root, Anchor;
	FVector Dir; float Length = 0;
	if (!Prop || !Prop->GetBodyHandle(State.RootBone, RootH) || !ReadPose(NativeOf(Rope), RootH, Root)
		|| !ProphecyPotenceRope::GetReelGeometry(Rope, Anchor, Dir, Length)) return false;
	const double Free = FVector::Dist(Root.GetLocation(), Anchor.GetLocation()) + Length * (1.0 - ProphecyPotenceRope::GetAmount(Rope));
	// Loose: a guard just past the rope's length. Tied: the load-bearing length itself.
	Radius = State.bTetherOnLimb ? Free + State.TetherOffset : Free * 1.015 + 1.0;
	return true;
}

// Each frame: the anchor goes on the pulley->load line, beyond the pulley by the rope reeled in since the tie.
void MoveTetherAnchor(USkeletalMeshComponent* Rope, FNooseState& State)
{
	UWorld* World = Rope ? Rope->GetWorld() : nullptr;
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	if (!World || !Native || !State.bTetherOnLimb || !Native->OwnsBody(State.TetherAnchor)) return;
	FTransform Limb;
	if (!ReadPose(Native, State.TetherLimb, Limb)) return;
	const FVector Load = (State.TetherFrameOnLimb * Limb).GetLocation();
	const FVector Dir = (State.TetherPulley - Load).GetSafeNormal();
	const double Amount = ProphecyPotenceRope::GetAmount(Rope);
	const double In = State.TetherReelLength * (Amount - State.TetherAmount0);
	if (Dir.IsNearlyZero() || World->GetDeltaSeconds() <= 0) return;
	// Pulling up: the given share of this frame's pull as a jump of the anchor, against a hard limit (see ReelNeckGive).
	const double Pulled = State.TetherLastAmount >= 0 ? State.TetherReelLength * (Amount - State.TetherLastAmount) : 0.0;
	State.TetherLastAmount = Amount;
	auto SetHard = [&](bool bHard)
	{
		FProphecyJoltJointSettings T = State.TipTetherSettings;
		T.bSoftTranslation = !bHard;
		if (Native->UpdateJoint(State.TipTether, T).IsSuccess()) { State.TipTetherSettings = T; State.bTetherHard = bHard; }
	};
	if (ReelNeckGive > 0 && Pulled > 1e-4)
	{
		State.TetherLastPull = World->GetTimeSeconds();
		if (!State.bTetherHard) SetHard(true);
		FTransform AnchorNow;
		if (State.bTetherHard && ReadPose(Native, State.TetherAnchor, AnchorNow))
			Native->SetBodyPose(State.TetherAnchor, FTransform(AnchorNow.GetLocation() + Dir * (Pulled * ReelNeckGive)));
	}
	else if (State.bTetherHard && World->GetTimeSeconds() - State.TetherLastPull > ReelHardHoldSeconds) SetHard(false);
	Native->MoveKinematicBody(State.TetherAnchor, FTransform(State.TetherPulley + Dir * In), World->GetDeltaSeconds());
	// Test trace (-NooseTrace): every frame, the hanging body and the tether, to find hitches.
	static const bool bTrace = FParse::Param(FCommandLine::Get(), TEXT("NooseTrace"));
	if (bTrace)
	{
		auto* Body = Cast<USkeletalMeshComponent>(State.Target.Get());
		FTransform AnchorP; ReadPose(Native, State.TetherAnchor, AnchorP);
		FProphecyJoltBodyState LimbS; Native->ReadBody(State.TetherLimb, LimbS);
		FProphecyJoltBodyHandle PelvisH; FProphecyJoltBodyState PelvisS;
		const bool bPelvis = Body && BodyOf(Body, TEXT("pelvis"), PelvisH) && Native->ReadBody(PelvisH, PelvisS).IsSuccess();
		const FVector HandR = Body && Body->GetBoneIndex(TEXT("hand_r")) != INDEX_NONE ? Body->GetBoneLocation(TEXT("hand_r")) : FVector::ZeroVector;
		UE_LOG(LogProphecyNoose, Display, TEXT("NOOSETRACE t=%.4f dt=%.4f load=%s v=%s active=%d pelvis=%s pv=%s pactive=%d hand_r=%s anchor=%s slack=%.3f"),
			World->GetTimeSeconds(), World->GetDeltaSeconds(), *Load.ToCompactString(), *LimbS.CenterOfMassVelocityCmPerSecond.ToCompactString(), LimbS.bActive ? 1 : 0,
			bPelvis ? *PelvisS.CenterOfMassPositionCm.ToCompactString() : TEXT("-"), bPelvis ? *PelvisS.CenterOfMassVelocityCmPerSecond.ToCompactString() : TEXT("-"), bPelvis && PelvisS.bActive ? 1 : 0,
			*HandR.ToCompactString(), *AnchorP.GetLocation().ToCompactString(),
			State.TipTetherSettings.Translation[0].Maximum - FVector::Dist(AnchorP.GetLocation(), Load));
	}
}

// Moves the load tether from the rope end to the loop's centre on the limb. The new one is made first, so the rope is
// never without a tether; a held limb refuses it (no moving body), it is retried each closing step until released.
bool TryTetherOnLimb(USkeletalMeshComponent* Rope, FNooseState& State)
{
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	if (!Native || !State.bTetherPending) return false;
	FTransform Pulley, Limb; FVector ReelDir; float ReelLength = 0;
	if (!ProphecyPotenceRope::GetReelGeometry(Rope, Pulley, ReelDir, ReelLength)) { State.TetherError = TEXT("no reel geometry"); return false; }
	if (!ReadPose(Native, State.TetherLimb, Limb)) { State.TetherError = TEXT("cannot read the limb"); return false; }
	FProphecyJoltBodyState LimbState;
	if (!Native->ReadBody(State.TetherLimb, LimbState).IsSuccess() || !LimbState.bDynamic) { State.TetherError = TEXT("the limb is held (not dynamic)"); return false; }
	const FVector Load = (State.TetherFrameOnLimb * Limb).GetLocation();
	const double Length = FVector::Dist(Pulley.GetLocation(), Load);	// taut from the pulley, as the rope hangs now
	// The anchor: an invisible kinematic point that touches nothing.
	FProphecyJoltBodyHandle Anchor;
	if (!Native->OwnsBody(State.TetherAnchor))
	{
		FProphecyJoltFixtureBodySettings Settings;
		Settings.PositionCm = Pulley.GetLocation();
		Settings.bDynamic = true;
		Settings.MassKg = 1.0;
		Settings.AssociatedObject = Rope;
		Settings.CollisionResponses = FCollisionResponseContainer(ECR_Ignore);
		auto Made = Native->CreateSphere(1.0, Settings, Anchor);
		if (Made.IsSuccess()) Made = Native->SetBodyKinematic(Anchor);
		if (!Made.IsSuccess())
		{
			if (Native->OwnsBody(Anchor)) Native->DestroyBody(Anchor);
			State.TetherError = Made.Message; return false;
		}
	}
	else
	{
		Anchor = State.TetherAnchor;
		Native->SetBodyPose(Anchor, FTransform(Pulley.GetLocation()));
	}
	FProphecyJoltJointSettings S = MakeTether(Anchor, State.TetherLimb, Length, State.TetherFrameOnLimb);
	S.bSoftTranslation = true;
	S.TranslationStiffness = TetherStiffness;
	S.TranslationDamping = TetherDamping;
	FProphecyJoltJointHandle New;
	const auto Made = Native->CreateJoint(S, {}, New);
	if (!Made.IsSuccess()) { Native->DestroyBody(Anchor); State.TetherAnchor = {}; State.TetherError = Made.Message; return false; }
	if (Native->OwnsJoint(State.TipTether)) Native->DestroyJoint(State.TipTether);
	State.TipTether = New;
	State.TipTetherSettings = S;
	State.TetherAnchor = Anchor;
	State.TetherPulley = Pulley.GetLocation();
	State.TetherAmount0 = ProphecyPotenceRope::GetAmount(Rope);
	State.TetherReelLength = ReelLength;
	State.TetherLastAmount = -1; State.bTetherHard = false;
	State.bTetherOnLimb = true;
	State.bTetherPending = false;
	UE_LOG(LogProphecyNoose, Display, TEXT("Noose: load carried from the pulley to the loop centre (%.1f cm), reeled by a moving anchor"), Length);
	return true;
}
}

namespace ProphecyNoose
{
void Install(USkeletalMeshComponent* Rope, FName TipBone, UStaticMeshComponent* AuthoredNoose)
{
	if (!IsValid(Rope) || !Rope->GetOwner() || Rope->GetBoneIndex(TipBone) == INDEX_NONE) return;
	FNooseState& State = NooseStates.FindOrAdd(Rope);
	if (State.Noose.IsValid()) return;
	if (IsValid(AuthoredNoose))
	{
		// The procedural noose replaces the authored one (kept in the Blueprint, hidden at runtime).
		UProphecyJoltStaticMeshLibrary::DisableJoltStaticMeshPhysics(AuthoredNoose);
		AuthoredNoose->SetSimulatePhysics(false);
		AuthoredNoose->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		AuthoredNoose->SetHiddenInGame(true);
		AuthoredNoose->SetVisibility(false);
	}
	State.TipBone = TipBone;
	auto* Noose = NewObject<UProphecyNooseComponent>(Rope->GetOwner(), TEXT("ProphecyNoose"), RF_Transient);
	// Match the rope: its section radius and texel density (mesh UVs are isotropic per mesh cm).
	const FVector Scale = Rope->GetComponentScale().GetAbs();
	if (const USkeletalMesh* Mesh = Rope->GetSkeletalMeshAsset())
	{
		// The rope mesh is a long thin tube: its long bound axis runs along the rope, the other two span the section.
		const FVector Ext = Mesh->GetImportedBounds().BoxExtent;
		const int32 Long = Ext.X >= Ext.Y && Ext.X >= Ext.Z ? 0 : (Ext.Y >= Ext.Z ? 1 : 2);
		const int32 A = (Long + 1) % 3, B = (Long + 2) % 3;
		Noose->HangingRopeRadius = float(FMath::Min(Ext[A] * Scale[A], Ext[B] * Scale[B]));
		// Same rope pattern at the noose's smaller scale: one texture turn per section turn, strands scaled along.
		Noose->UVAlongPerCm = float(0.00222 / FMath::Max(Scale[Long], 0.01)) * Noose->HangingRopeRadius / FMath::Max(Noose->RopeRadius, .3f);
	}
	if (Rope->GetMaterial(0)) Noose->SetMaterial(0, Rope->GetMaterial(0));
	Rope->GetOwner()->AddInstanceComponent(Noose);
	Noose->RegisterComponent();
	const FVector At = Rope->GetSocketLocation(TipBone);
	const FName Parent = Rope->GetParentBone(TipBone);
	FVector Up = Parent.IsNone() ? FVector::UpVector : (Rope->GetSocketLocation(Parent) - At).GetSafeNormal();
	if (Up.IsNearlyZero()) Up = FVector::UpVector;
	// The rope mesh runs on past its last bone: the noose starts where the mesh ends, so it continues the rope.
	float EndOffset = 0;
	if (const USkeletalMesh* Mesh = Rope->GetSkeletalMeshAsset())
	{
		const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
		const int32 TipI = Ref.FindBoneIndex(TipBone), ParI = TipI != INDEX_NONE ? Ref.GetParentIndex(TipI) : INDEX_NONE;
		if (ParI != INDEX_NONE)
		{
			const FVector TipRef = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, TipI).GetLocation();
			const FVector Dir = (TipRef - FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, ParI).GetLocation()).GetSafeNormal();
			const FBox Box = Mesh->GetImportedBounds().GetBox();
			double Far = 0;
			for (int32 C = 0; C < 8; ++C)
				Far = FMath::Max(Far, FVector::DotProduct(FVector(C & 1 ? Box.Max.X : Box.Min.X, C & 2 ? Box.Max.Y : Box.Min.Y, C & 4 ? Box.Max.Z : Box.Min.Z) - TipRef, Dir));
			EndOffset = float(FMath::Clamp(Far, 0.0, 40.0) * Rope->GetComponentScale().GetAbs().GetMax());
		}
	}
	Noose->SetWorldLocationAndRotation(At - Up * EndOffset, FRotationMatrix::MakeFromZX(Up, Rope->GetForwardVector()).ToQuat());
	Noose->AttachToComponent(Rope, FAttachmentTransformRules::KeepWorldTransform, TipBone);
	State.NooseOnBone = Noose->GetRelativeTransform();
	Noose->BuildLoose();
	State.Noose = Noose;
	// The drawn rope: a world-space tube on the same actor, redrawn once per frame.
	{
		for (FName B = TipBone; !B.IsNone() && B != State.RootBone; B = Rope->GetParentBone(B)) State.RopeChain.Insert(B, 0);
		auto* TubeComp = NewObject<UProceduralMeshComponent>(Rope->GetOwner(), TEXT("ProphecyRopeTube"), RF_Transient);
		TubeComp->SetUsingAbsoluteLocation(true); TubeComp->SetUsingAbsoluteRotation(true); TubeComp->SetUsingAbsoluteScale(true);
		TubeComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		TubeComp->SetGenerateOverlapEvents(false);
		TubeComp->CastShadow = true;
		TubeComp->SetVisibility(false, false);
		Rope->GetOwner()->AddInstanceComponent(TubeComp);
		TubeComp->RegisterComponent();
		TubeComp->SetWorldTransform(FTransform::Identity);
		State.RopeTube = TubeComp;
		const TWeakObjectPtr<USkeletalMeshComponent> WeakRope(Rope);
		Rope->GetWorld()->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateLambda([WeakRope] { UpdateRopeTube(WeakRope); }));
	}
	FVector BoxC, BoxH; Noose->GetCoilBox(BoxC, BoxH);
	UE_LOG(LogProphecyNoose, Display, TEXT("Procedural noose on %s.%s: noose rope radius %.2f cm (gallows rope %.2f), %d wraps, knot %.0f x %.0f cm, starts %.1f cm past the last bone, uv/cm %.5f"),
		*Rope->GetName(), *TipBone.ToString(), Noose->RopeRadius, Noose->HangingRopeRadius, Noose->CoilTurns, 2 * BoxH.Z, 2 * BoxH.Y, EndOffset, Noose->UVAlongPerCm);
}

float GetMassKg(const USkeletalMeshComponent* Rope)
{
	const FNooseState* State = NooseStates.Find(Rope);
	return State && State->Noose.IsValid() ? State->Noose->MassKg : 0.f;
}

void OnRopeAdmitted(USkeletalMeshComponent* Rope)
{
	FNooseState* State = NooseStates.Find(Rope);
	auto* Prop = Rope ? UProphecyJoltSkeletalPropComponent::Find(Rope) : nullptr;
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	if (!State || !Prop || !Native || Native->OwnsJoint(State->TipTether)) return;
	FProphecyJoltBodyHandle RootH, TipH;
	double Radius = 0;
	if (!Prop->GetBodyHandle(State->RootBone, RootH) || !Prop->GetBodyHandle(State->TipBone, TipH) || !TetherRadius(Rope, *State, Radius)) return;
	// A hidden radial tether from the fixed root body to the rope end: the 27 light links can no longer
	// be stretched by a heavy or fast load. It only acts when the rope is taut.
	State->TipTetherSettings = MakeTether(RootH, TipH, Radius);
	const auto Made = Native->CreateJoint(State->TipTetherSettings, {}, State->TipTether);
	UE_LOG(LogProphecyNoose, Display, TEXT("Rope tether %s: radius %.1f cm %s"), *Rope->GetName(), Radius, Made.IsSuccess() ? TEXT("") : *Made.Message);
	AddCoilCollider(Rope, *State, *Prop, *Native, TipH);
}

void OnRopeReeled(USkeletalMeshComponent* Rope)
{
	FNooseState* State = NooseStates.Find(Rope);
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	double Radius = 0;
	if (!State || !Native || !Native->OwnsJoint(State->TipTether) || !TetherRadius(Rope, *State, Radius)) return;
	// Tied: the reel moves the tether's anchor (MoveTetherAnchor), the tether itself is never re-made.
	if (State->bTied && State->bTetherOnLimb) return;
	if (FMath::Abs(Radius - State->TipTetherSettings.Translation[0].Maximum) < .2) return;
	auto Settings = MakeTether(State->TipTetherSettings.BodyA, State->TipTetherSettings.BodyB, Radius, State->TipTetherSettings.FrameB);
	if (Native->UpdateJoint(State->TipTether, Settings).IsSuccess()) State->TipTetherSettings = Settings;
}
}

bool UProphecyNooseLibrary::GetNooseTieTarget(USkeletalMeshComponent* Rope, UPrimitiveComponent* Target, FName BodyBone, FName AtBone, FVector& RopeEndLocation, FString& Error, float Clearance)
{
	FTieGeometry G;
	if (!ComputeTie(Rope, Target, BodyBone, AtBone, Clearance, G, Error)) return false;
	RopeEndLocation = G.NooseOrigin;	// the knot point: where the rope end is pinned
	return true;
}

bool UProphecyNooseLibrary::TieNoose(USkeletalMeshComponent* Rope, UPrimitiveComponent* Target, FName BodyBone, FName AtBone, FString& Error, float Clearance)
{
	if (IsNooseTied(Rope)) UntieNoose(Rope);
	FTieGeometry G;
	if (!ComputeTie(Rope, Target, BodyBone, AtBone, Clearance, G, Error)) return false;
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	FNooseState& State = NooseStates.FindChecked(Rope);
	FTransform Tip;
	ReadPose(Native, G.TipBody, Tip);
	const float Gap = float(FVector::Dist(Tip.GetLocation(), G.NooseOrigin));
	if (Gap > 35.f) { Error = FString::Printf(TEXT("Bring the noose closer: the rope end is %.0f cm from the tie position."), Gap); return false; }
	// The noose is rigid on the limb (it rides on the limb's bone). The rope end is pinned at the knot point, where the
	// rope enters the knot: no sliding, but free to bend there, so the rope's own limits never fight the tie.
	// The pin starts where the rope end is (no jolt) and draws it onto the knot over TieCloseSeconds.
	// The rope leaves the knot along the coil, as from a real hangman's knot: the joint frame's X runs up the coil, the
	// rope end may turn about it (twist free) but not bend away from it (swing locked), so rope and knot read as one.
	const FTransform World(FRotationMatrix::MakeFromXZ(G.CoilAxis, G.Side).ToQuat(), G.NooseOrigin);
	FProphecyJoltJointSettings S;
	S.Type = EProphecyJoltJointType::HardSixDOF;
	S.Rotation[0].Motion = EProphecyJoltAxisMotion::Free;
	S.Rotation[1].Motion = EProphecyJoltAxisMotion::Locked;
	S.Rotation[2].Motion = EProphecyJoltAxisMotion::Locked;
	S.BodyA = G.TipBody; S.BodyB = G.LimbBody;
	S.FrameA = World.GetRelativeTransform(Tip);
	S.FrameB = World.GetRelativeTransform(G.LimbPose);
	// While tied the rope and the hanging body never collide: the rope's last links lie against the head or the
	// foot by construction and their contacts only make both jiggle. The pairs belong to the tie joint (gone with it).
	TArray<FProphecyJoltBodyPair> RopeVsBody;
	if (auto* RopeProp = UProphecyJoltSkeletalPropComponent::Find(Rope))
		if (const UPhysicsAsset* RopePA = Rope->GetPhysicsAsset())
		{
			TArray<FProphecyJoltBodyHandle> Mine, Theirs;
			for (const auto& Setup : RopePA->SkeletalBodySetups)
			{
				FProphecyJoltBodyHandle H;
				if (Setup && RopeProp->GetBodyHandle(Setup->BoneName, H)) Mine.Add(H);
			}
			if (auto* Skel = Cast<USkeletalMeshComponent>(Target); Skel && Skel->GetPhysicsAsset())
			{
				for (const auto& Setup : Skel->GetPhysicsAsset()->SkeletalBodySetups)
				{
					FProphecyJoltBodyHandle H;
					if (Setup && BodyOf(Target, Setup->BoneName, H)) Theirs.Add(H);
				}
			}
			else Theirs.Add(G.LimbBody);
			for (const auto& A : Mine) for (const auto& B : Theirs) RopeVsBody.Add({ A, B });
		}
	auto Made = Native->CreateJoint(S, RopeVsBody, State.Tie);
	if (!Made.IsSuccess() && RopeVsBody.Num())
	{
		UE_LOG(LogProphecyNoose, Warning, TEXT("Noose: rope/body collision pairs refused (%s) - tying with collision on."), *Made.Message);
		RopeVsBody.Reset();
		Made = Native->CreateJoint(S, {}, State.Tie);
	}
	if (!Made.IsSuccess()) { Error = Made.Message; return false; }
	State.TieSettings = S; State.Target = Target; State.TargetBody = G.LimbBody; State.bTied = true;
	// The load path: rope root -> the loop's centre on the limb, at the paid-out rope length (now, or once released).
	if (Native->OwnsJoint(State.TipTether))
	{
		FTransform Root;
		if (ReadPose(Native, State.TipTetherSettings.BodyA, Root))
		{
			State.TetherOffset = FVector::Dist(Root.GetLocation(), G.Center) - FVector::Dist(Root.GetLocation(), G.NooseOrigin);
			State.TetherLimb = G.LimbBody;
			State.TetherFrameOnLimb = FTransform(G.Center).GetRelativeTransform(G.LimbPose);
			State.bTetherPending = true;
			if (!TryTetherOnLimb(Rope, State))
				UE_LOG(LogProphecyNoose, Display, TEXT("Noose: load tether waits for the limb to move (%s)"), *State.TetherError);
		}
	}
	State.RaisedBodies.Reset();
	State.bLimbMassApplied = false;
	State.bLimbMassPending = false;
	if (auto* LimbSkel = Cast<USkeletalMeshComponent>(Target))
		if (auto* LimbProp = UProphecyJoltSkeletalPropComponent::Find(LimbSkel))
		{
			CollectLightChain(LimbSkel, LimbProp, BodyBone, State.RaisedBodies);
			State.bLimbMassPending = State.RaisedBodies.Num() > 0;
			TryApplyLimbMass(State);
			// A hanging body settles without the solver's jiggle: damp its joints (relative motion only).
			FString DampError;
			const FProphecyJoltBodyHandle& L = G.LimbBody;
			if (Native->SetRigJointDamping(L.WorldLifetime, L.Slot, int64(L.Generation), INDEX_NONE, TiedJointDamping, DampError))
				State.DampedBody = L;
			UE_LOG(LogProphecyNoose, Display, TEXT("Noose: %s joints damped %.0f/s while tied%s%s; rope/body collision off (%d pairs)"),
				*LimbSkel->GetName(), TiedJointDamping, DampError.IsEmpty() ? TEXT("") : TEXT(" - "), *DampError, RopeVsBody.Num());
		}
	State.TieFrameStart = S.FrameA;
	State.TieFrameEnd = World.GetRelativeTransform(FTransform(G.TipRotation, G.Tip));	// the rope end along the coil
	State.NooseOnLimb = FTransform(G.NooseRotation, G.NooseOrigin).GetRelativeTransform(G.LimbPose);
	// A heavy load on a light rope end: give the end enough mass for the solver (rope + noose + wet knot).
	if (auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Rope))
	{
		State.TipMassUntied = Prop->GetCapturedBodyMassKg(State.TipBone) + (State.Noose.IsValid() ? State.Noose->MassKg : 0.f);
		const float Load = FMath::Clamp(Target->CalculateMass(), 1.f, 400.f);
		FString MassError;
		Prop->SetBodyMassKg(State.TipBone, FMath::Max(float(State.TipMassUntied), FMath::Min(.12f * Load, 20.f)), MassError);
	}
	// Rigid noose: in its own frame the coil runs up Z; the loop is square to the limb, beside the coil's foot.
	if (UProphecyNooseComponent* Noose = State.Noose.Get())
	{
		const FQuat ToNoose = G.NooseRotation.Inverse();
		Noose->BuildAround(ToNoose.RotateVector(G.LoopNormal), ToNoose.RotateVector(G.Side), G.Inner, G.Profile);
		// The noose is on the limb at once (snug, centred) and rides on its bone; the rope end follows it in.
		Noose->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
		Noose->SetWorldTransform(State.NooseOnLimb * G.LimbPose);
		auto* LimbMesh = Cast<USkeletalMeshComponent>(Target);
		Noose->AttachToComponent(Target, FAttachmentTransformRules::KeepWorldTransform, LimbMesh ? BodyBone : NAME_None);
		FVector BoxC, BoxH; Noose->GetCoilBox(BoxC, BoxH);
		LockCoil(*Native, State, G.LimbBody, G.LimbPose, FTransform(BoxC) * State.NooseOnLimb * G.LimbPose);
		State.bClosing = true;
		State.LogClock = 0;
		State.CloseElapsed = 0;
		const TWeakObjectPtr<USkeletalMeshComponent> WeakRope(Rope);
		Rope->GetWorld()->GetTimerManager().SetTimer(State.CloseTimer, FTimerDelegate::CreateLambda([WeakRope] { StepClosing(WeakRope); }), 1.f / 60.f, true);
	}
	if (Native->OwnsBody(State.CoilBody))
	{
		// Tied, the noose rides rigidly on the limb: its knot ignores the whole tied body (no head or foot jiggling
		// against it) and still collides with everything else.
		TArray<FProphecyJoltBodyPair> Pairs = State.CoilPairs;
		Pairs.Add({ State.CoilBody, G.LimbBody });
		if (auto* Skel = Cast<USkeletalMeshComponent>(Target))
			if (const UPhysicsAsset* PA = Skel->GetPhysicsAsset())
				for (const auto& Setup : PA->SkeletalBodySetups)
				{
					FProphecyJoltBodyHandle H;
					if (Setup && BodyOf(Target, Setup->BoneName, H)) Pairs.Add({ State.CoilBody, H });
				}
		Native->UpdateBodySuppressedPairs(State.CoilBody, Pairs);
	}
	float SkinMin = 0, SkinMax = 0;
	if (G.Profile.Num()) { SkinMin = FMath::Min(G.Profile); SkinMax = FMath::Max(G.Profile); }
	UE_LOG(LogProphecyNoose, Display, TEXT("Noose tied around %s.%s: capsule radius %.1f cm, loop inner %.1f-%.1f cm from the %s, knot at %.1f cm, coil along the rope leaning %.0f deg, rope end moved %.1f cm; loop tilted %.0f deg and %.0f cm lower to clear the next body (%d skin points left in reach)"),
		*GetNameSafe(Target), *BodyBone.ToString(), G.LimbRadius, G.Profile.Num() ? SkinMin : G.Inner, G.Profile.Num() ? SkinMax : G.Inner, G.SkinSource, G.Inner, G.TiltDeg, Gap, G.LoopTiltDeg, G.DropCm, G.Blocked);
	return true;
}

bool UProphecyNooseLibrary::UntieNoose(USkeletalMeshComponent* Rope)
{
	FNooseState* State = NooseStates.Find(Rope);
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	if (!State || !State->bTied) return false;
	if (Native && Native->OwnsJoint(State->Tie)) Native->DestroyJoint(State->Tie);
	if (State->bLimbMassApplied)
		if (auto* LimbSkel = Cast<USkeletalMeshComponent>(State->Target.Get()))
			if (auto* LimbProp = UProphecyJoltSkeletalPropComponent::Find(LimbSkel))
			{
				FString MassError;
				for (const auto& B : State->RaisedBodies) LimbProp->SetBodyMassKg(B.Key, float(B.Value), MassError);
			}
	State->bLimbMassApplied = State->bLimbMassPending = false;
	if (Native && State->DampedBody.IsSet())
	{
		FString DampError;	// back to the rig's default (motors off)
		Native->SetRigJointDamping(State->DampedBody.WorldLifetime, State->DampedBody.Slot, int64(State->DampedBody.Generation), INDEX_NONE, 0.f, DampError);
	}
	State->DampedBody = {};
	State->bTetherPending = false;
	if (State->bTetherOnLimb)
	{
		if (Native && Native->OwnsJoint(State->TipTether)) Native->DestroyJoint(State->TipTether);
		State->TipTether = {};
		State->bTetherOnLimb = false;
		State->TetherOffset = 0;
		ProphecyNoose::OnRopeAdmitted(Rope);	// the guard tether back on the rope end
	}
	if (Native && Native->OwnsBody(State->TetherAnchor)) Native->DestroyBody(State->TetherAnchor);
	State->TetherAnchor = {};
	State->Tie = {}; State->bTied = false; State->Target.Reset();
	if (Native && Native->OwnsBody(State->CoilBody)) Native->UpdateBodySuppressedPairs(State->CoilBody, State->CoilPairs);
	if (auto* Prop = UProphecyJoltSkeletalPropComponent::Find(Rope); Prop && State->TipMassUntied > 0)
	{
		FString MassError;
		Prop->SetBodyMassKg(State->TipBone, float(State->TipMassUntied), MassError);
	}
	if (State->Noose.IsValid()) State->Noose->BuildLoose();
	SeatNooseOnRope(Rope, *State);	// back on the rope end, its collider too
	return true;
}

bool UProphecyNooseLibrary::IsNooseTied(USkeletalMeshComponent* Rope)
{
	const FNooseState* State = NooseStates.Find(Rope);
	const UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	return State && State->bTied && Native && Native->OwnsJoint(State->Tie);
}

bool UProphecyNooseLibrary::GetNooseTieError(USkeletalMeshComponent* Rope, float& LinearCm, float& AngularDegrees)
{
	LinearCm = AngularDegrees = 0;
	const FNooseState* State = NooseStates.Find(Rope);
	UProphecyJoltWorldSubsystem* Native = NativeOf(Rope);
	FTransform A, B;
	if (!IsNooseTied(Rope) || !ReadPose(Native, State->TieSettings.BodyA, A) || !ReadPose(Native, State->TieSettings.BodyB, B)) return false;
	const FTransform FA = State->TieSettings.FrameA * A, FB = State->TieSettings.FrameB * B;
	LinearCm = float(FVector::Dist(FA.GetLocation(), FB.GetLocation()));
	// Twist is free: the error is how far the rope end bends away from the coil's axis (the frames' X).
	if (State->TieSettings.Rotation[1].Motion == EProphecyJoltAxisMotion::Locked)
		AngularDegrees = float(FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(FVector::DotProduct(FA.GetUnitAxis(EAxis::X), FB.GetUnitAxis(EAxis::X)), -1.0, 1.0))));
	return true;
}
