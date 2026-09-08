#include "ProphecySwordComponent.h"
#include "ProphecyAgent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "UObject/UnrealType.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "PBDRigidsSolver.h"
#include "Chaos/PBDRigidsEvolution.h"
#include "Chaos/Collision/CollisionConstraintFlags.h"

namespace
{
	struct FOwnerCollisionPairs
	{
		Chaos::FPhysicsSolver* Solver = nullptr;
		Chaos::FUniqueIdx Blade;
		TArray<Chaos::FUniqueIdx> Bodies;
	};
	// Stable across Live Coding; entries are released on drop, destruction and EndPlay.
	TMap<const UProphecySwordComponent*, FOwnerCollisionPairs>& OwnerCollisionPairs()
	{
		static auto* Pairs = new TMap<const UProphecySwordComponent*, FOwnerCollisionPairs>;
		return *Pairs;
	}
	void QueueOwnerCollisions(const FOwnerCollisionPairs& Pairs, bool bIgnore)
	{
		Pairs.Solver->EnqueueCommandImmediate([Pairs, bIgnore]()
		{
			auto* BladeProxy = Pairs.Solver->GetParticleProxy_PT(Pairs.Blade);
			if (!BladeProxy) return;
			auto& Manager = Pairs.Solver->GetEvolution()->GetBroadPhase().GetIgnoreCollisionManager();
			for (const auto Id : Pairs.Bodies)
			{
				if (auto* BodyProxy = Pairs.Solver->GetParticleProxy_PT(Id))
				{
					if (bIgnore) Manager.AddIgnoreCollisions(BladeProxy->GetHandle_LowLevel(), BodyProxy->GetHandle_LowLevel());
					else Manager.RemoveIgnoreCollisions(BladeProxy->GetHandle_LowLevel(), BodyProxy->GetHandle_LowLevel());
				}
			}
		});
	}
	void ClearOwnerCollisions(const UProphecySwordComponent* Controller)
	{
		FOwnerCollisionPairs Pairs;
		if (OwnerCollisionPairs().RemoveAndCopyValue(Controller, Pairs)) QueueOwnerCollisions(Pairs, false);
	}
	void IgnoreOwnerCollisions(const UProphecySwordComponent* Controller, UStaticMeshComponent* Blade, AProphecyAgent* Owner)
	{
		FOwnerCollisionPairs Pairs;
		const auto Handle = Blade->BodyInstance.ActorHandle;
		if (!Handle) return;
		Pairs.Solver = Handle->GetSolver<Chaos::FPhysicsSolver>();
		if (!Pairs.Solver) return;
		Pairs.Blade = Handle->GetGameThreadAPI().UniqueIdx();
		TArray<UPrimitiveComponent*> Components;
		Owner->GetComponents(Components);
		for (UPrimitiveComponent* Component : Components)
		{
			auto Add = [&Pairs](FBodyInstance* Body)
			{
				if (Body && Body->ActorHandle && Body->ActorHandle->GetSolver<Chaos::FPhysicsSolver>() == Pairs.Solver)
					Pairs.Bodies.AddUnique(Body->ActorHandle->GetGameThreadAPI().UniqueIdx());
			};
			if (auto* Mesh = Cast<USkeletalMeshComponent>(Component)) for (auto* Body : Mesh->Bodies) Add(Body);
			else Add(Component->GetBodyInstance());
		}
		OwnerCollisionPairs().Add(Controller, Pairs);
		QueueOwnerCollisions(Pairs, true);
	}
}

UProphecySwordComponent::UProphecySwordComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

AProphecyAgent* UProphecySwordComponent::Agent() const { return Cast<AProphecyAgent>(GetOwner()); }

FTransform UProphecySwordComponent::GripWorld() const
{
	return Agent()->SwordGripTransform * Agent()->GetPoseReferenceMesh()->GetSocketTransform(Agent()->SwordHandSocket);
}

bool UProphecySwordComponent::Equip(bool bSimulated)
{
	if (Sword) return SetSimulated(bSimulated);
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* M = A ? A->GetPoseReferenceMesh() : nullptr;
	UClass* Class = A ? A->SwordBlueprint.LoadSynchronous() : nullptr;
	if (!M || !M->DoesSocketExist(A->SwordHandSocket) || !Class) return false;
	if (!FMath::IsFinite(A->SwordMassKg) || A->SwordMassKg <= 0 || A->SwordGripTransform.ContainsNaN()) return false;
	// A_Sword's existing cutting/NS code expects its decal manager in the world.
	// Reuse it or create the dependency once; do not remove the cutting graph.
	const bool bKnownSword = Class->GetPathName() == TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C");
	if (bKnownSword)
	{
		if (const FObjectPropertyBase* P = FindFProperty<FObjectPropertyBase>(Class, TEXT("decal manager"));
			P && P->PropertyClass && P->PropertyClass->IsChildOf(AActor::StaticClass()))
		{
			bool bFound = false;
			for (TActorIterator<AActor> It(GetWorld(), P->PropertyClass); It; ++It) { bFound = true; break; }
			if (!bFound)
			{
				FActorSpawnParameters ManagerParameters;
				ManagerParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				if (!GetWorld()->SpawnActor<AActor>(P->PropertyClass, FTransform::Identity, ManagerParameters)) return false;
			}
		}
	}
	FActorSpawnParameters P;
	P.Owner = A;
	P.Instigator = A;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	P.bDeferConstruction = true;
	Sword = GetWorld()->SpawnActor<AActor>(Class, GripWorld(), P);
	if (!Sword) return false;
	if (bKnownSword)
	{
		// Per-instance gameplay initialization BEFORE Blueprint BeginPlay. Its
		// authored debug defaults otherwise change global FPS and pause on tick 0.
		if (FBoolProperty* Flag = FindFProperty<FBoolProperty>(Class, TEXT("debug mode"))) Flag->SetPropertyValue_InContainer(Sword, false);
		if (FIntProperty* Freeze = FindFProperty<FIntProperty>(Class, TEXT("freeze tick"))) Freeze->SetPropertyValue_InContainer(Sword, -1);
		if (FIntProperty* Unfreeze = FindFProperty<FIntProperty>(Class, TEXT("unfreeze tick"))) Unfreeze->SetPropertyValue_InContainer(Sword, 0);
		if (FBoolProperty* Gravity = FindFProperty<FBoolProperty>(Class, TEXT("enable gravity"))) Gravity->SetPropertyValue_InContainer(Sword, true);
	}
	Sword->FinishSpawning(GripWorld());
	TArray<UStaticMeshComponent*> Meshes;
	Sword->GetComponents(Meshes);
	for (UStaticMeshComponent* C : Meshes) if (C->GetFName() == TEXT("sword")) Blade = C;
	if (!Blade && Meshes.Num() == 1) Blade = Meshes[0];
	if (!Blade || !Blade->GetStaticMesh()) { Disappear(); return false; }
	if (Blade->GetStaticMesh()->GetPathName() == TEXT("/Game/_mygame/sword/geometry/Sword_GL01.Sword_GL01"))
	{
		if (UStaticMesh* Exact = A->SwordTrainingMesh.LoadSynchronous()) Blade->SetStaticMesh(Exact);
	}
	// Make the existing Blueprint mesh the runtime root so a dropped simulated
	// sword's actor transform follows its body, not an abandoned scene root.
	USceneComponent* OldRoot = Sword->GetRootComponent();
	Blade->SetSimulatePhysics(false);
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	Sword->SetRootComponent(Blade);
	if (OldRoot && OldRoot != Blade) OldRoot->AttachToComponent(Blade, FAttachmentTransformRules::KeepWorldTransform);
	Blade->SetCollisionProfileName(TEXT("PhysicsActor"));
	Blade->SetEnableGravity(true);
	Blade->SetMassOverrideInKg(NAME_None, A->SwordMassKg, true);
	Blade->BodyInstance.bUseCCD = true;
	Blade->BodyInstance.PositionSolverIterationCount = 16;
	Blade->BodyInstance.VelocitySolverIterationCount = 8;
	Grip = NewObject<UPhysicsConstraintComponent>(A);
	A->AddInstanceComponent(Grip);
	Grip->RegisterComponent();
	Grip->SetDisableCollision(true);
	Grip->SetLinearXLimit(LCM_Locked, 0);
	Grip->SetLinearYLimit(LCM_Locked, 0);
	Grip->SetLinearZLimit(LCM_Locked, 0);
	Grip->SetAngularSwing1Limit(ACM_Locked, 0);
	Grip->SetAngularSwing2Limit(ACM_Locked, 0);
	Grip->SetAngularTwistLimit(ACM_Locked, 0);
	bPhysicsHold = bSimulated;
	if (!Bind(true)) { Disappear(); return false; }
	SetComponentTickEnabled(true);
	return true;
}

bool UProphecySwordComponent::Bind(bool bSnapToGrip)
{
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* M = A ? A->GetPoseReferenceMesh() : nullptr;
	if (!M || !Sword || !Blade || !Grip || !M->DoesSocketExist(A->SwordHandSocket)) return false;
	ClearOwnerCollisions(this);
	Grip->BreakConstraint();
	if (BoundMesh != M)
	{
		if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
		BoundMesh = M;
		AddTickPrerequisiteComponent(M);
	}
	if (bPhysicsHold)
	{
		const FName Bone = M->GetSocketBoneName(A->SwordHandSocket);
		FBodyInstance* Hand = M->GetBodyInstance(Bone);
		if (!Hand || !Hand->IsValidBodyInstance()) return false;
		Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
		if (bSnapToGrip) Blade->SetWorldTransform(GripWorld(), false, nullptr, ETeleportType::TeleportPhysics);
		Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Blade->SetSimulatePhysics(true);
		if (!Blade->IsSimulatingPhysics()) return false;
		// The held blade must not cut its own holder. Pair-specific suppression
		// leaves world/victim contacts and A_Sword's cutting logic intact.
		IgnoreOwnerCollisions(this, Blade, A);
		FTransform Anchor = M->GetSocketTransform(A->SwordHandSocket);
		Anchor.SetScale3D(FVector::OneVector);
		Grip->SetWorldTransform(Anchor);
		Grip->SetConstrainedComponents(M, Bone, Blade, NAME_None);
		// Fixed authored frames, not frames inferred from a deflected current sword.
		Grip->SetConstraintReferenceFrame(EConstraintFrame::Frame1,
			Anchor.GetRelativeTransform(Hand->GetUnrealWorldTransform()));
		FTransform BladeFrame = Anchor.GetRelativeTransform(GripWorld());
		// Chaos reference positions are in scaled body-local coordinates.
		BladeFrame.SetLocation(BladeFrame.GetLocation() * GripWorld().GetScale3D());
		BladeFrame.SetScale3D(FVector::OneVector);
		Grip->SetConstraintReferenceFrame(EConstraintFrame::Frame2, BladeFrame);
		Blade->WakeAllRigidBodies();
	}
	else
	{
		Blade->SetSimulatePhysics(false);
		// Attached presentation is intentionally non-physical; no kinematic sword
		// collider can push the owning hand or pin it against the world.
		Blade->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Blade->AttachToComponent(M, FAttachmentTransformRules::KeepWorldTransform, A->SwordHandSocket);
		Blade->SetRelativeTransform(A->SwordGripTransform);
		// An unchanged relative transform can early-out after a mode switch has
		// temporarily propagated a different socket pose to attached children.
		Blade->UpdateComponentToWorld();
	}
	bHasPrevious = false;
	return true;
}

bool UProphecySwordComponent::SetSimulated(bool bSimulated)
{
	if (!Sword || !Blade) return false;
	if (bPhysicsHold == bSimulated) return true;
	const bool OldMode = bPhysicsHold;
	bPhysicsHold = bSimulated;
	if (!Bind(bSimulated)) { bPhysicsHold = OldMode; Bind(false); return false; }
	if (bSimulated)
	{
		Blade->SetPhysicsLinearVelocity(CarriedLinear);
		Blade->SetPhysicsAngularVelocityInRadians(CarriedAngular);
	}
	return true;
}

void UProphecySwordComponent::RefreshHandConstraint()
{
	if (Sword) Bind(false);
}

AActor* UProphecySwordComponent::Drop()
{
	if (!Sword || !Blade) return nullptr;
	ClearOwnerCollisions(this);
	const FVector Linear = bPhysicsHold ? Blade->GetPhysicsLinearVelocity() : CarriedLinear;
	const FVector Angular = bPhysicsHold ? Blade->GetPhysicsAngularVelocityInRadians() : CarriedAngular;
	if (Grip) { Grip->BreakConstraint(); Grip->DestroyComponent(); Grip = nullptr; }
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	Blade->SetEnableGravity(true);
	Blade->SetSimulatePhysics(true);
	Blade->SetPhysicsLinearVelocity(Linear);
	Blade->SetPhysicsAngularVelocityInRadians(Angular);
	Blade->WakeAllRigidBodies();
	AActor* Result = Sword;
	Result->SetOwner(nullptr);
	Sword = nullptr;
	Blade = nullptr;
	bHasPrevious = false;
	return Result;
}

void UProphecySwordComponent::Disappear()
{
	ClearOwnerCollisions(this);
	if (Grip) { Grip->BreakConstraint(); Grip->DestroyComponent(); Grip = nullptr; }
	if (Sword) Sword->Destroy();
	Sword = nullptr;
	Blade = nullptr;
	bHasPrevious = false;
}

void UProphecySwordComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	Disappear();
	Super::EndPlay(Reason);
}

void UProphecySwordComponent::TickComponent(float Dt, ELevelTick Type, FActorComponentTickFunction* Function)
{
	Super::TickComponent(Dt, Type, Function);
	if (!IsValid(Sword) || !IsValid(Blade)) { ClearOwnerCollisions(this); Sword = nullptr; Blade = nullptr; return; }
	if (BoundMesh != Agent()->GetPoseReferenceMesh()) Bind(false);
	const FTransform Current = Blade->GetComponentTransform();
	if (bHasPrevious && Dt > SMALL_NUMBER)
	{
		CarriedLinear = (Current.GetLocation() - PreviousWorld.GetLocation()) / Dt;
		FQuat Delta = Current.GetRotation() * PreviousWorld.GetRotation().Inverse();
		if (Delta.W < 0) Delta = Delta * -1.;
		FVector Axis; double Angle;
		Delta.ToAxisAndAngle(Axis, Angle);
		CarriedAngular = Axis * Angle / Dt;
	}
	PreviousWorld = Current;
	bHasPrevious = true;
}

namespace
{
	UProphecySwordComponent* SwordController(AProphecyAgent* A, bool bCreate)
	{
		auto* C = A->FindComponentByClass<UProphecySwordComponent>();
		if (!C && bCreate)
		{
			C = NewObject<UProphecySwordComponent>(A);
			A->AddInstanceComponent(C);
			C->RegisterComponent();
		}
		return C;
	}
}

bool AProphecyAgent::EquipSword(bool bSimulated) { return SwordController(this, true)->Equip(bSimulated); }
bool AProphecyAgent::SetSwordSimulated(bool bSimulated)
{
	UProphecySwordComponent* C = SwordController(this, false);
	return C && C->SetSimulated(bSimulated);
}
AActor* AProphecyAgent::DropSword()
{
	UProphecySwordComponent* C = SwordController(this, false);
	return C ? C->Drop() : nullptr;
}
void AProphecyAgent::HideSword()
{
	if (UProphecySwordComponent* C = SwordController(this, false)) C->Disappear();
}
AActor* AProphecyAgent::GetHeldSword() const
{
	const UProphecySwordComponent* C = FindComponentByClass<UProphecySwordComponent>();
	return C ? C->GetSword() : nullptr;
}
bool AProphecyAgent::IsSwordSimulated() const
{
	const UProphecySwordComponent* C = FindComponentByClass<UProphecySwordComponent>();
	return C && C->IsSimulated();
}
