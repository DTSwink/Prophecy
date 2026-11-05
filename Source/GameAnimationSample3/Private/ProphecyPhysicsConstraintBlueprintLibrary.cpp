#include "ProphecyPhysicsConstraintBlueprintLibrary.h"
#include "ProphecyJoltConstraintRuntime.h"

#include "ProphecyRetractableSkeletalMeshComponent.h"
#include "ProphecyNoose.h"
#include "ProphecyPotenceRope.h"
#include "ProphecyJoltFightSetup.h"
#include "ProphecyJoltSkeletalPropComponent.h"
#include "ProphecyJoltStaticMeshLibrary.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"

#include "Components/SkeletalMeshComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Chaos/ChaosEngineInterface.h"
#include "Chaos/CollisionFilterData.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Physics/Experimental/ChaosScopedSceneLock.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "ReferenceSkeleton.h"
#include "TimerManager.h"

bool UProphecyPhysicsConstraintBlueprintLibrary::StartOptimisedSwordCut(AActor* SwordActor, UPhysicsConstraintComponent* Constraint)
{
	return ProphecyJolt::Constraints::StartOptimisedSwordCut(SwordActor, Constraint);
}

bool UProphecyPhysicsConstraintBlueprintLibrary::SetPikeWoundCorrection(UPhysicsConstraintComponent* Constraint, bool Enabled)
{
	return ProphecyJolt::Constraints::SetPikeWoundCorrection(Constraint, Enabled);
}

namespace
{
// The gallows rope is one passive Jolt articulation whenever the world runs Jolt gameplay
// physics; 0 restores the legacy Chaos rope/noose path (comparison and fallback only).
TAutoConsoleVariable<int32> CVarPotenceRopeJolt(TEXT("Prophecy.Rope.Jolt"), 1,
	TEXT("1: the gallows rope, its pulley and its noose run in Jolt when the world uses Jolt gameplay physics. 0: legacy Chaos rope."));

bool IsJoltRopeWorld(UWorld* World)
{
	if (!World || !World->IsGameWorld() || CVarPotenceRopeJolt.GetValueOnGameThread() == 0) return false;
	// Same decision as ProphecyJolt::DefaultPhysics: an explicit setup actor wins, else the project default.
	bool bAnySetup = false;
	for (TActorIterator<AProphecyJoltFightSetup> It(World); It; ++It)
	{
		bAnySetup = true;
		if (It->bEnableJolt) return true;
	}
	if (bAnySetup) return false;
	static IConsoleVariable* Default = IConsoleManager::Get().FindConsoleVariable(TEXT("Prophecy.Jolt.DefaultPhysics"));
	return !Default || Default->GetInt() != 0;
}

TAutoConsoleVariable<int32> CVarPotenceRopeJoltVelocitySteps(TEXT("Prophecy.Rope.JoltVelocitySteps"), 48,
	TEXT("Jolt velocity solver steps for the gallows rope articulation (world default is lower; a 27-link chain needs more)."));
TAutoConsoleVariable<int32> CVarPotenceRopeJoltPositionSteps(TEXT("Prophecy.Rope.JoltPositionSteps"), 32,
	TEXT("Jolt position solver steps for the gallows rope articulation."));

// Runs on the game thread until the rope's Jolt admission completes, then applies the rope
// solver steps and the welded noose mass once, and stops. No recurring work afterwards.
TMap<TWeakObjectPtr<USkeletalMeshComponent>, FTimerHandle> PotenceRopeTuning;
void SchedulePotenceRopeJoltTuning(USkeletalMeshComponent* Rope, const FName TipBone, const float ExtraTipMassKg)
{
	UWorld* World = Rope ? Rope->GetWorld() : nullptr;
	if (!World || PotenceRopeTuning.Contains(Rope)) return;
	const TWeakObjectPtr<USkeletalMeshComponent> WeakRope(Rope);
	TSharedRef<int32> Polls = MakeShared<int32>(0);
	FTimerHandle& Handle = PotenceRopeTuning.Add(Rope);
	World->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateLambda([WeakRope, TipBone, ExtraTipMassKg, Polls]()
	{
		USkeletalMeshComponent* Mesh = WeakRope.Get();
		auto Stop = [&WeakRope, Mesh]()
		{
			FTimerHandle Done;
			if (PotenceRopeTuning.RemoveAndCopyValue(WeakRope, Done) && Mesh && Mesh->GetWorld()) Mesh->GetWorld()->GetTimerManager().ClearTimer(Done);
		};
		UProphecyJoltSkeletalPropComponent* Prop = Mesh ? UProphecyJoltSkeletalPropComponent::Find(Mesh) : nullptr;
		if (!Mesh || ++*Polls > 600) { Stop(); return; }
		if (!Prop || !Prop->IsJoltStepClientActive()) return;
		FString Error;
		const int32 V = CVarPotenceRopeJoltVelocitySteps.GetValueOnGameThread(), P = CVarPotenceRopeJoltPositionSteps.GetValueOnGameThread();
		if (V > 0 && P > 0 && !Prop->SetSolverIterations(V, P, Error))
			UE_LOG(LogPhysics, Warning, TEXT("Potence rope (Jolt) solver steps: %s"), *Error);
		const double TipMass = Prop->GetCapturedBodyMassKg(TipBone);
		if (ExtraTipMassKg > 0.f && TipMass > 0.0 && !Prop->SetBodyMassKg(TipBone, float(TipMass) + ExtraTipMassKg, Error))
			UE_LOG(LogPhysics, Warning, TEXT("Potence rope (Jolt) noose mass: %s"), *Error);
		UE_LOG(LogTemp, Display, TEXT("Potence rope in Jolt: %s, velocity/position steps %d/%d, %s %.3f kg + noose %.3f kg"),
			*Mesh->GetName(), V, P, *TipBone.ToString(), TipMass, ExtraTipMassKg);
		ProphecyNoose::OnRopeAdmitted(Mesh);
		Stop();
	}), 0.1f, true);
}

constexpr int32 PotenceRopeSegmentCount = 27;
constexpr float PotenceRopeScaleTolerance = 1.0e-5f;
constexpr int32 PotenceRopePositionSolverIterations = 12;
constexpr int32 PotenceRopeVelocitySolverIterations = 2;
constexpr int32 PotenceRopeProjectionSolverIterations = 24;
const FName PotenceRopeRootBone(TEXT("joint"));

struct FPotenceRopeBodyState
{
	FName BoneName;
	FBodyInstance* Body = nullptr;
	bool bRetired = false;
	bool bSimulationConfigured = false;
};

struct FPotenceRopeConstraintState
{
	FConstraintInstance* Constraint = nullptr;
};

struct FPotenceRopeState
{
	TWeakObjectPtr<USkeletalMeshComponent> Target;
	TWeakObjectPtr<UPhysicsAsset> PhysicsAsset;
	FBodyInstance* RootBody = nullptr;
	TArray<FPotenceRopeBodyState> Bodies;
	TArray<FPotenceRopeConstraintState> Constraints;
	float AppliedAmount = 0.0f;
};

TMap<TWeakObjectPtr<USkeletalMeshComponent>, FPotenceRopeState> PotenceRopeStates;
TMap<TWeakObjectPtr<USkeletalMeshComponent>, float> PotenceRopeAmounts;
uint32 PotenceRopeUpdateCallCount = 0;

uint32 HashBoatWaveSeed(uint32 Value)
{
	Value ^= Value >> 16;
	Value *= 0x7feb352du;
	Value ^= Value >> 15;
	Value *= 0x846ca68bu;
	Value ^= Value >> 16;
	return Value;
}

float BoatWavePhase(const int32 Seed, const uint32 Salt)
{
	constexpr float Inverse24BitRange = 1.0f / 16777216.0f;
	const uint32 Hash = HashBoatWaveSeed(static_cast<uint32>(Seed) ^ Salt);
	return static_cast<float>(Hash & 0x00ffffffu) * Inverse24BitRange * (2.0f * PI);
}

FVector2D RotateBoatWaveDirection(const FVector2D& Direction, const float AngleRadians)
{
	float Sine = 0.0f;
	float Cosine = 1.0f;
	FMath::SinCos(&Sine, &Cosine, AngleRadians);
	return FVector2D(
		Direction.X * Cosine - Direction.Y * Sine,
		Direction.X * Sine + Direction.Y * Cosine);
}

FName MakePotenceRopeBoneName(const int32 SegmentIndex)
{
	return FName(*FString::Printf(TEXT("joint%d"), SegmentIndex + 1));
}

bool GetReferenceBoneComponentTransform(
	const USkeletalMeshComponent* Target,
	const FName BoneName,
	FTransform& OutTransform)
{
	const USkeletalMesh* SkeletalMesh = Target ? Target->GetSkeletalMeshAsset() : nullptr;
	if (!SkeletalMesh)
	{
		return false;
	}

	const FReferenceSkeleton& ReferenceSkeleton = SkeletalMesh->GetRefSkeleton();
	const int32 BoneIndex = ReferenceSkeleton.FindBoneIndex(BoneName);
	if (BoneIndex == INDEX_NONE)
	{
		return false;
	}

	const TArray<FTransform>& ReferencePose = ReferenceSkeleton.GetRefBonePose();
	OutTransform = ReferencePose[BoneIndex];
	for (int32 ParentIndex = ReferenceSkeleton.GetParentIndex(BoneIndex);
		ParentIndex != INDEX_NONE;
		ParentIndex = ReferenceSkeleton.GetParentIndex(ParentIndex))
	{
		OutTransform *= ReferencePose[ParentIndex];
	}
	return true;
}

bool GetPotenceRopeReelGeometry(
	const USkeletalMeshComponent* Target,
	FTransform& OutAnchorWorld,
	FVector& OutRetractionDirectionWorld,
	float& OutRopeLengthWorld)
{
	FTransform RootReferenceTransform;
	if (!GetReferenceBoneComponentTransform(Target, PotenceRopeRootBone, RootReferenceTransform))
	{
		return false;
	}

	const FTransform ComponentTransform = Target->GetComponentTransform();
	OutAnchorWorld = RootReferenceTransform * ComponentTransform;
	FVector PreviousPosition = OutAnchorWorld.GetLocation();
	OutRetractionDirectionWorld = FVector::ZeroVector;
	OutRopeLengthWorld = 0.0f;

	for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
	{
		FTransform SegmentReferenceTransform;
		if (!GetReferenceBoneComponentTransform(Target, MakePotenceRopeBoneName(SegmentIndex), SegmentReferenceTransform))
		{
			return false;
		}

		const FVector SegmentPosition = ComponentTransform.TransformPosition(SegmentReferenceTransform.GetLocation());
		if (SegmentIndex == 0)
		{
			OutRetractionDirectionWorld = (PreviousPosition - SegmentPosition).GetSafeNormal();
		}
		OutRopeLengthWorld += FVector::Distance(PreviousPosition, SegmentPosition);
		PreviousPosition = SegmentPosition;
	}

	return !OutRetractionDirectionWorld.IsNearlyZero() && OutRopeLengthWorld > KINDA_SMALL_NUMBER;
}

void RemoveStalePotenceRopeStates()
{
	for (auto It = PotenceRopeStates.CreateIterator(); It; ++It)
	{
		if (!It.Key().IsValid())
		{
			It.RemoveCurrent();
		}
	}
}

void ConfigurePotenceRopeBodySolver(FBodyInstance* Body)
{
	if (!Body || !Body->IsValidBodyInstance())
	{
		return;
	}

	// A long hard-joint chain needs more than the default single projection pass:
	// otherwise a character contact can leave a small error at every joint and the
	// accumulated error looks like the rope lengthening. These are per-particle
	// overrides for this 28-body island, not global Chaos settings.
	FPhysicsCommand::ExecuteWrite(Body->GetPhysicsActor(), [](const FPhysicsActorHandle& Actor)
	{
		FChaosEngineInterface::SetPositionSolverIterationCount_AssumesLocked(
			Actor, PotenceRopePositionSolverIterations);
		FChaosEngineInterface::SetVelocitySolverIterationCount_AssumesLocked(
			Actor, PotenceRopeVelocitySolverIterations);
		FChaosEngineInterface::SetProjectionSolverIterationCount_AssumesLocked(
			Actor, PotenceRopeProjectionSolverIterations);
	});
}

bool IsPotenceRopeStateCurrent(const FPotenceRopeState& State, USkeletalMeshComponent* Target)
{
	if (State.Target.Get() != Target || State.PhysicsAsset.Get() != Target->GetPhysicsAsset()
		|| State.Bodies.Num() != PotenceRopeSegmentCount || State.Constraints.Num() != PotenceRopeSegmentCount)
	{
		return false;
	}

	if (State.RootBody != Target->GetBodyInstance(PotenceRopeRootBone))
	{
		return false;
	}

	for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
	{
		if (State.Bodies[SegmentIndex].Body != Target->GetBodyInstance(State.Bodies[SegmentIndex].BoneName)
			|| State.Constraints[SegmentIndex].Constraint != Target->FindConstraintInstance(State.Bodies[SegmentIndex].BoneName))
		{
			return false;
		}
	}

	return true;
}

bool BuildPotenceRopeState(USkeletalMeshComponent* Target, FPotenceRopeState& OutState)
{
	if (!Target || !Target->IsPhysicsStateCreated() || !Target->GetPhysicsAsset())
	{
		return false;
	}

	OutState = FPotenceRopeState();
	OutState.Target = Target;
	OutState.PhysicsAsset = Target->GetPhysicsAsset();
	OutState.RootBody = Target->GetBodyInstance(PotenceRopeRootBone);
	if (!OutState.RootBody || !OutState.RootBody->IsValidBodyInstance())
	{
		UE_LOG(LogPhysics, Warning, TEXT("Potence rope: missing valid kinematic root body '%s' on %s"),
			*PotenceRopeRootBone.ToString(), *Target->GetPathName());
		return false;
	}
	ConfigurePotenceRopeBodySolver(OutState.RootBody);

	// This helper owns the one kinematic rope root while active. Prevent the
	// skeletal pre-physics update from restoring that body to the reference pose
	// on alternating frames; simulated children still feed their poses back normally.
	Target->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;

	OutState.Bodies.Reserve(PotenceRopeSegmentCount);
	OutState.Constraints.Reserve(PotenceRopeSegmentCount);
	for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
	{
		const FName BoneName = MakePotenceRopeBoneName(SegmentIndex);
		FBodyInstance* Body = Target->GetBodyInstance(BoneName);
		FConstraintInstance* Constraint = Target->FindConstraintInstance(BoneName);
		if (!Body || !Body->IsValidBodyInstance() || !Constraint || !Constraint->IsValidConstraintInstance())
		{
			UE_LOG(LogPhysics, Warning, TEXT("Potence rope: missing valid body or parent constraint for '%s' on %s"),
				*BoneName.ToString(), *Target->GetPathName());
			return false;
		}

		FPotenceRopeBodyState& BodyState = OutState.Bodies.AddDefaulted_GetRef();
		BodyState.BoneName = BoneName;
		BodyState.Body = Body;
		ConfigurePotenceRopeBodySolver(Body);
		FPotenceRopeConstraintState& ConstraintState = OutState.Constraints.AddDefaulted_GetRef();
		ConstraintState.Constraint = Constraint;
	}

	// The wood attachment is authoritative and must never enter simulation.
	if (OutState.RootBody->IsInstanceSimulatingPhysics())
	{
		Target->SetBodySimulatePhysics(PotenceRopeRootBone, false);
	}

	return true;
}

void SetPotenceRopeBodyShapesEnabled(FBodyInstance* Body, const bool bEnabled)
{
	if (!Body || !Body->IsValidBodyInstance())
	{
		return;
	}

	if (bEnabled)
	{
		// Rebuild the normal filter without recreating the actor or changing whether
		// the capsule is a simulation shape. Since retirement leaves that flag alone,
		// this does not trigger a mass-properties change.
		Body->UpdatePhysicsFilterData();
		return;
	}

	// Keep the tiny consumed capsule registered as a simulation shape and only make
	// it match no collision channels. Flipping IsSimulationShape at every segment
	// boundary changes the solver body's mass/contact topology and produces a visible
	// one-frame correction at the free tip. Empty filter data retires collision while
	// leaving the 27-body constraint island structurally unchanged.
	FPhysicsCommand::ExecuteWrite(Body->GetPhysicsActor(), [Body](const FPhysicsActorHandle& Actor)
	{
		TArray<FPhysicsShapeHandle> Shapes;
		FPhysicsInterface::GetAllShapes_AssumedLocked(Actor, Shapes);
		for (const FPhysicsShapeHandle& Shape : Shapes)
		{
			if (Body->GetOriginalBodyInstance(Shape) == Body)
			{
				FPhysicsInterface::SetShapeFilterData(Shape, Chaos::Filter::FShapeFilterData());
			}
		}
	});
}

bool PerformPotenceNooseWeld(
	UStaticMeshComponent* Noose,
	USkeletalMeshComponent* Rope,
	const FName TerminalBone)
{
	if (!Noose || !Rope || TerminalBone.IsNone()
		|| Rope->GetBoneIndex(TerminalBone) == INDEX_NONE
		|| !Noose->IsPhysicsStateCreated() || !Rope->IsPhysicsStateCreated())
	{
		return false;
	}

	if (IsJoltRopeWorld(Rope->GetWorld()))
	{
		// Jolt: the authored (Fab) noose is replaced by the procedural one carried by the rope end bone;
		// its mass goes on the terminal rope body once the rope is admitted.
		ProphecyNoose::Install(Rope, TerminalBone, Noose);
		SchedulePotenceRopeJoltTuning(Rope, TerminalBone, ProphecyNoose::GetMassKg(Rope));
		return true;
	}

	Noose->SetWorldLocation(
		Rope->GetSocketLocation(TerminalBone),
		false,
		nullptr,
		ETeleportType::TeleportPhysics);

	const FAttachmentTransformRules WeldRules(EAttachmentRule::KeepWorld, true);
	if (!Noose->AttachToComponent(Rope, WeldRules, TerminalBone))
	{
		return false;
	}

	Noose->WakeAllRigidBodies();
	Rope->WakeAllRigidBodies();
	return true;
}

}

bool ProphecyPotenceRope::GetReelGeometry(const USkeletalMeshComponent* Rope, FTransform& AnchorWorld, FVector& RetractionDirectionWorld, float& LengthWorld)
{
	return Rope && GetPotenceRopeReelGeometry(Rope, AnchorWorld, RetractionDirectionWorld, LengthWorld);
}

float ProphecyPotenceRope::GetAmount(const USkeletalMeshComponent* Rope)
{
	const float* Amount = PotenceRopeAmounts.Find(const_cast<USkeletalMeshComponent*>(Rope));
	return Amount ? *Amount : 0.f;
}

void UProphecyPhysicsConstraintBlueprintLibrary::GetLinearZLimit(
	UPhysicsConstraintComponent* Target,
	TEnumAsByte<ELinearConstraintMotion>& ConstraintType,
	float& LimitSize)
{
	if (!Target)
	{
		ConstraintType = LCM_Free;
		LimitSize = 0.0f;
		return;
	}

	ConstraintType = Target->ConstraintInstance.GetLinearZMotion();
	LimitSize = Target->ConstraintInstance.GetLinearLimit();
}

bool UProphecyPhysicsConstraintBlueprintLibrary::WeldNooseToRopeEnd(
	UPhysicsConstraintComponent* Constraint,
	UStaticMeshComponent* Noose,
	USkeletalMeshComponent* Rope,
	const FName TerminalBone)
{
	if (!Constraint || !Noose || !Rope || TerminalBone.IsNone()
		|| Rope->GetBoneIndex(TerminalBone) == INDEX_NONE)
	{
		UE_LOG(LogPhysics, Warning,
			TEXT("Potence noose weld: invalid constraint, noose, rope, or terminal bone"));
		return false;
	}

	// The old fixed constraint is solver-compliant under contact and visibly
	// stretches. Remove it before welding so there is only one rigid relationship.
	Constraint->BreakConstraint();
	Constraint->SetActive(false);
	Constraint->SetAutoActivate(false);
	Constraint->SetComponentTickEnabled(false);

	UWorld* World = Rope->GetWorld();
	if (!World)
	{
		return false;
	}

	// Construction Scripts execute before PIE has created both Chaos actors. An
	// immediate AttachToComponent appears successful at that stage but is discarded
	// when the bodies register. In game worlds, defer exactly once to the next world
	// tick; this is the same registered-body timing as a BeginPlay weld, with no
	// ongoing tick or transform correction.
	if (World->IsGameWorld())
	{
		if (Noose->IsPhysicsStateCreated() && Rope->IsPhysicsStateCreated())
		{
			return PerformPotenceNooseWeld(Noose, Rope, TerminalBone);
		}

		const TWeakObjectPtr<UStaticMeshComponent> WeakNoose(Noose);
		const TWeakObjectPtr<USkeletalMeshComponent> WeakRope(Rope);
		World->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateLambda(
			[WeakNoose, WeakRope, TerminalBone]()
			{
				UStaticMeshComponent* DeferredNoose = WeakNoose.Get();
				USkeletalMeshComponent* DeferredRope = WeakRope.Get();
				if (!PerformPotenceNooseWeld(DeferredNoose, DeferredRope, TerminalBone))
				{
					UE_LOG(LogPhysics, Warning,
						TEXT("Potence noose weld: deferred joint27 weld failed"));
				}
			}));
		return true;
	}

	// Editor preview instances do not own live Chaos actors. Leave their authored
	// component hierarchy untouched; every PIE/runtime instance performs the weld.
	return true;
}

bool UProphecyPhysicsConstraintBlueprintLibrary::UpdatePotenceRopePhysics(
	USkeletalMeshComponent* Target,
	float Amount)
{
	if (!Target)
	{
		return false;
	}
	UProphecyRetractableSkeletalMeshComponent* RetractableTarget =
		Cast<UProphecyRetractableSkeletalMeshComponent>(Target);
	if (!RetractableTarget)
	{
		UE_LOG(LogPhysics, Warning,
			TEXT("Potence rope: %s must use ProphecyRetractableSkeletalMeshComponent"),
			*Target->GetPathName());
		return false;
	}

	check(IsInGameThread());
	if (IsJoltRopeWorld(Target->GetWorld()))
	{
		if (UProphecyJoltSkeletalPropComponent* Prop = UProphecyJoltSkeletalPropComponent::Find(Target))
		{
			const float JoltAmount = FMath::Clamp(Amount, 0.0f, 1.0f);
			RetractableTarget->SetRetractionVisualAmount(JoltAmount);
			RetractableTarget->SetVisibility(true, false);
			// Admission pending: Chaos is already off for this mesh. Never re-enable it here;
			// the next call after admission applies the reel to the native bodies.
			if (!Prop->IsJoltStepClientActive())
			{
				return true;
			}
			FTransform JoltAnchorWorld;
			FVector JoltDirectionWorld;
			float JoltLengthWorld = 0.0f;
			if (!GetPotenceRopeReelGeometry(Target, JoltAnchorWorld, JoltDirectionWorld, JoltLengthWorld))
			{
				return false;
			}
			// Same reel as the Chaos path: the kinematic root slides back through the fixed
			// wood anchor, the full-length chain follows, consumed links stop colliding.
			FTransform JoltRootTarget = JoltAnchorWorld;
			JoltRootTarget.AddToTranslation(JoltDirectionWorld * JoltLengthWorld * JoltAmount);
			FString Error;
			if (!Prop->SetKinematicBodyTarget(PotenceRopeRootBone, JoltRootTarget, Error))
			{
				UE_LOG(LogPhysics, Warning, TEXT("Potence rope (Jolt): %s"), *Error);
				return false;
			}
			const float JoltProgress = JoltAmount * static_cast<float>(PotenceRopeSegmentCount);
			TArray<FName, TInlineAllocator<PotenceRopeSegmentCount>> Bones;
			TArray<bool, TInlineAllocator<PotenceRopeSegmentCount>> Retired;
			for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
			{
				Bones.Add(MakePotenceRopeBoneName(SegmentIndex));
				Retired.Add(JoltProgress - static_cast<float>(SegmentIndex) >= 1.0f);
			}
			if (!Prop->SetBodiesCollisionRetired(Bones, Retired, Error))
			{
				UE_LOG(LogPhysics, Warning, TEXT("Potence rope (Jolt): %s"), *Error);
				return false;
			}
			PotenceRopeAmounts.Add(Target, JoltAmount);
			ProphecyNoose::OnRopeReeled(Target);
			return true;
		}
	}
	if ((++PotenceRopeUpdateCallCount & 0xffu) == 0u)
	{
		RemoveStalePotenceRopeStates();
	}

	FPotenceRopeState& State = PotenceRopeStates.FindOrAdd(Target);
	if (!IsPotenceRopeStateCurrent(State, Target) && !BuildPotenceRopeState(Target, State))
	{
		PotenceRopeStates.Remove(Target);
		return false;
	}

	const float ClampedAmount = FMath::Clamp(Amount, 0.0f, 1.0f);
	const bool bAmountChanged = !FMath::IsNearlyEqual(ClampedAmount, State.AppliedAmount, PotenceRopeScaleTolerance);
	const float SegmentProgress = ClampedAmount * static_cast<float>(PotenceRopeSegmentCount);
	FTransform AnchorWorld;
	FVector RetractionDirectionWorld;
	float RopeLengthWorld = 0.0f;
	if (!GetPotenceRopeReelGeometry(Target, AnchorWorld, RetractionDirectionWorld, RopeLengthWorld))
	{
		return false;
	}

	// Reel the unchanged, full-length physics chain through the fixed wood anchor.
	// Moving one kinematic target continuously avoids the degenerate zero-length
	// constraint frames that made Chaos release a full segment of error at once.
	FTransform RootTarget = AnchorWorld;
	RootTarget.AddToTranslation(RetractionDirectionWorld * RopeLengthWorld * ClampedAmount);
	State.RootBody->SetBodyTransform(RootTarget, ETeleportType::None, true);

	// Bodies reeled above the wood keep participating in the constraint chain but
	// leave the collision scene. Their solver topology and mass never change.
	for (int32 SegmentIndex = 0; SegmentIndex < PotenceRopeSegmentCount; ++SegmentIndex)
	{
		FPotenceRopeBodyState& BodyState = State.Bodies[SegmentIndex];
		const bool bShouldRetire = SegmentProgress - static_cast<float>(SegmentIndex) >= 1.0f;
		if (!BodyState.bSimulationConfigured || BodyState.bRetired != bShouldRetire)
		{
			if (!BodyState.bSimulationConfigured && !BodyState.Body->IsInstanceSimulatingPhysics())
			{
				Target->SetBodySimulatePhysics(BodyState.BoneName, true);
			}
			SetPotenceRopeBodyShapesEnabled(BodyState.Body, !bShouldRetire);
			BodyState.bRetired = bShouldRetire;
			BodyState.bSimulationConfigured = true;
		}
	}

	if (State.RootBody->IsInstanceSimulatingPhysics())
	{
		Target->SetBodySimulatePhysics(PotenceRopeRootBone, false);
	}
	if (bAmountChanged)
	{
		// Updating a constraint reference frame does not wake a sleeping Chaos island.
		// Wake once per changed input so continuous expansion cannot freeze after the
		// collapsed chain settles. This is 27 tiny bodies and avoids any reconstruction.
		Target->WakeAllRigidBodies();
	}
	State.AppliedAmount = ClampedAmount;
	PotenceRopeAmounts.Add(Target, ClampedAmount);
	RetractableTarget->SetRetractionVisualAmount(ClampedAmount);
	RetractableTarget->SetVisibility(true, false);

	return true;
}

bool UProphecyPhysicsConstraintBlueprintLibrary::ApplyBoatWaveForces(
	UPrimitiveComponent* Target,
	const float Strength,
	const float HeaveAcceleration,
	const float WaveFrequencyHz,
	const float FrequencySpread,
	FVector2D WaveDirection,
	const float DirectionSpreadDegrees,
	const float WavelengthCm,
	const float HullHalfLengthYcm,
	const float HullHalfWidthXcm,
	const float RockingStrength,
	FVector2D DriftDirection,
	const float DriftAcceleration,
	const float DriftFrequencyHz,
	const float HorizontalDamping,
	const float VerticalDamping,
	const float AngularDamping,
	const float YawAccelerationDegrees,
	const int32 Seed,
	const float TimeScale,
	const float PhaseOffsetSeconds,
	const FName BoneName)
{
	if (!Target || !Target->IsRegistered() || !Target->IsSimulatingPhysics(BoneName))
	{
		return false;
	}

	const float AppliedStrength = FMath::Max(Strength, 0.0f);
	const float MassKg = Target->GetMass();
	const UWorld* World = Target->GetWorld();
	if (AppliedStrength <= KINDA_SMALL_NUMBER || MassKg <= KINDA_SMALL_NUMBER || !World)
	{
		return false;
	}

	WaveDirection = WaveDirection.GetSafeNormal();
	if (WaveDirection.IsNearlyZero())
	{
		WaveDirection = FVector2D(1.0f, 0.0f);
	}
	DriftDirection = DriftDirection.GetSafeNormal();
	if (DriftDirection.IsNearlyZero())
	{
		DriftDirection = WaveDirection;
	}

	const float SafeFrequency = FMath::Max(WaveFrequencyHz, 0.001f);
	const float SafeWavelength = FMath::Max(WavelengthCm, 1.0f);
	const float SafeFrequencySpread = FMath::Clamp(FrequencySpread, 0.0f, 0.95f);
	const float SafeDirectionSpread = FMath::DegreesToRadians(
		FMath::Clamp(DirectionSpreadDegrees, 0.0f, 180.0f));
	const float SafeTimeScale = FMath::Max(TimeScale, 0.0f);
	const float WaveTime = World->GetTimeSeconds() * SafeTimeScale + PhaseOffsetSeconds;
	const FVector CenterOfMass = Target->GetCenterOfMass(BoneName);
	const FVector2D HorizontalPosition(CenterOfMass.X, CenterOfMass.Y);

	// A compact irregular-wave spectrum. Frequency and wave number are coupled
	// with the deep-water relation k ~ frequency^2, while the seed changes only
	// phase, never frame-to-frame continuity.
	const float FrequencyRatios[3] =
	{
		1.0f,
		1.0f - SafeFrequencySpread,
		1.0f + SafeFrequencySpread
	};
	const float DirectionOffsets[3] =
	{
		0.0f,
		-SafeDirectionSpread,
		SafeDirectionSpread
	};
	const float WaveWeights[3] = {0.5f, 0.3f, 0.2f};
	const uint32 PhaseSalts[3] = {0x68bc21ebu, 0x02e5be93u, 0x967a889bu};
	const float BaseWaveNumber = (2.0f * PI) / SafeWavelength;

	float HeaveSignal = 0.0f;
	FVector2D WaveGradient = FVector2D::ZeroVector;
	for (int32 WaveIndex = 0; WaveIndex < 3; ++WaveIndex)
	{
		const float Ratio = FMath::Max(FrequencyRatios[WaveIndex], 0.05f);
		const FVector2D Direction = RotateBoatWaveDirection(
			WaveDirection, DirectionOffsets[WaveIndex]);
		const float Frequency = SafeFrequency * Ratio;
		const float WaveNumber = BaseWaveNumber * Ratio * Ratio;
		const float Phase =
			WaveNumber * FVector2D::DotProduct(HorizontalPosition, Direction)
			- (2.0f * PI) * Frequency * WaveTime
			+ BoatWavePhase(Seed, PhaseSalts[WaveIndex]);

		float Sine = 0.0f;
		float Cosine = 1.0f;
		FMath::SinCos(&Sine, &Cosine, Phase);
		HeaveSignal += WaveWeights[WaveIndex] * Sine;
		WaveGradient += Direction * (WaveWeights[WaveIndex] * WaveNumber * Cosine);
	}

	// Integrate vertical pressure at four virtual hull corners, but accumulate it
	// analytically into one force and one torque call. This produces convincing
	// heave, roll, and pitch without four separate Chaos body-interface updates.
	const float HalfLengthY = FMath::Max(HullHalfLengthYcm, 0.0f);
	const float HalfWidthX = FMath::Max(HullHalfWidthXcm, 0.0f);
	const float AppliedRocking = FMath::Max(RockingStrength, 0.0f);
	const FQuat HullRotation = Target->GetComponentQuat();
	const FVector LocalHullOffsets[4] =
	{
		FVector(HalfWidthX, HalfLengthY, 0.0f),
		FVector(HalfWidthX, -HalfLengthY, 0.0f),
		FVector(-HalfWidthX, HalfLengthY, 0.0f),
		FVector(-HalfWidthX, -HalfLengthY, 0.0f)
	};

	FVector TotalForce = FVector::ZeroVector;
	FVector TotalWaveTorque = FVector::ZeroVector;
	for (const FVector& LocalOffset : LocalHullOffsets)
	{
		const FVector WorldOffset = HullRotation.RotateVector(LocalOffset);
		const float SlopeVariation =
			WaveGradient.X * WorldOffset.X + WaveGradient.Y * WorldOffset.Y;
		const float PointAcceleration =
			HeaveAcceleration * AppliedStrength
			* (HeaveSignal + AppliedRocking * SlopeVariation);
		const FVector PointForce =
			FVector::UpVector * (MassKg * 0.25f * PointAcceleration);
		TotalForce += PointForce;
		TotalWaveTorque += FVector::CrossProduct(WorldOffset, PointForce);
	}

	// Drift uses two much slower, incommensurate components. It is smooth and
	// zero-mean, so damping bounds the motion instead of letting random impulses
	// integrate into an ever-growing velocity.
	const float SafeDriftFrequency = FMath::Max(DriftFrequencyHz, 0.001f);
	const float DriftPhaseA =
		(2.0f * PI) * SafeDriftFrequency * WaveTime
		+ BoatWavePhase(Seed, 0x3c6ef372u);
	const float DriftPhaseB =
		(2.0f * PI) * SafeDriftFrequency * 0.6180339887f * WaveTime
		+ BoatWavePhase(Seed, 0xa54ff53au);
	const float DriftA = FMath::Sin(DriftPhaseA);
	const float DriftB = FMath::Sin(DriftPhaseB);
	const FVector2D DriftSide(-DriftDirection.Y, DriftDirection.X);
	constexpr float DriftNormalization = 0.9119215f;
	const FVector2D DriftSignal =
		(DriftDirection * DriftA + DriftSide * (0.45f * DriftB)) * DriftNormalization;

	const FVector LinearVelocity = Target->GetPhysicsLinearVelocity(BoneName);
	const FVector DriftAndDampingAcceleration(
		DriftSignal.X * DriftAcceleration
			- LinearVelocity.X * FMath::Max(HorizontalDamping, 0.0f),
		DriftSignal.Y * DriftAcceleration
			- LinearVelocity.Y * FMath::Max(HorizontalDamping, 0.0f),
		-LinearVelocity.Z * FMath::Max(VerticalDamping, 0.0f));
	TotalForce += DriftAndDampingAcceleration * (MassKg * AppliedStrength);

	if (!TotalForce.IsNearlyZero())
	{
		Target->AddForce(TotalForce, BoneName, false);
	}
	if (!TotalWaveTorque.IsNearlyZero())
	{
		Target->AddTorqueInRadians(TotalWaveTorque, BoneName, false);
	}

	const FVector AngularVelocity = Target->GetPhysicsAngularVelocityInRadians(BoneName);
	const float YawSignal = FMath::Sin(
		(2.0f * PI) * SafeDriftFrequency * 0.79f * WaveTime
		+ BoatWavePhase(Seed, 0x510e527fu));
	const FVector AngularAcceleration =
		-AngularVelocity * (FMath::Max(AngularDamping, 0.0f) * AppliedStrength)
		+ FVector::UpVector
			* (FMath::DegreesToRadians(YawAccelerationDegrees) * YawSignal * AppliedStrength);
	if (!AngularAcceleration.IsNearlyZero())
	{
		Target->AddTorqueInRadians(AngularAcceleration, BoneName, true);
	}

	return true;
}
