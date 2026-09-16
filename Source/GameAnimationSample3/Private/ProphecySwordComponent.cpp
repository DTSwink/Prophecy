#include "ProphecySwordComponent.h"
#include "ProphecyAgent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "UObject/UnrealType.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "PBDRigidsSolver.h"
#include "Chaos/PBDRigidsEvolution.h"
#include "Chaos/Collision/CollisionConstraintFlags.h"

struct FProphecyJoltSwordBinding
{
	TWeakObjectPtr<UProphecyJoltWorldSubsystem> World;
	TWeakObjectPtr<UProphecyJoltCharacterComponent> Character;
	FProphecyJoltJointHandle Joint;
	FProphecyJoltBodyHandle Hand;
};

void FProphecyJoltSwordBindingDeleter::operator()(FProphecyJoltSwordBinding* Binding) const { delete Binding; }

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
	void IgnoreOwnerCollisions(const UProphecySwordComponent* Controller, UStaticMeshComponent* Blade, AProphecyAgent* Owner,
		bool bAllOwner = true, bool bIncludeHand = false)
	{
		FOwnerCollisionPairs Pairs;
		const auto Handle = Blade->BodyInstance.ActorHandle;
		if (!Handle) return;
		Pairs.Solver = Handle->GetSolver<Chaos::FPhysicsSolver>();
		if (!Pairs.Solver) return;
		Pairs.Blade = Handle->GetGameThreadAPI().UniqueIdx();
		// The fixed grip owns this pair independently, including after an attack ends.
		const auto* OwnerMesh = Owner->GetPoseReferenceMesh();
		const FBodyInstance* GrippingHand = OwnerMesh ? OwnerMesh->GetBodyInstance(OwnerMesh->GetSocketBoneName(Owner->SwordHandSocket)) : nullptr;
		TArray<UPrimitiveComponent*> Components;
		Owner->GetComponents(Components);
		for (UPrimitiveComponent* Component : Components)
		{
			auto Add = [&Pairs, GrippingHand, bAllOwner, bIncludeHand](FBodyInstance* Body)
			{
				if (Body && (Body == GrippingHand ? bIncludeHand : bAllOwner)
					&& Body->ActorHandle && Body->ActorHandle->GetSolver<Chaos::FPhysicsSolver>() == Pairs.Solver)
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

UProphecySwordComponent::~UProphecySwordComponent() = default;

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
	// This controller owns the native Jolt weld or explicit Chaos grip. UE auto-welding
	// the attached receiver into the hand adds foreign shapes to its PHAT body on a
	// backend switch and prevents later Jolt rig capture.
	Blade->BodyInstance.bAutoWeld = false;
	Blade->SetSimulatePhysics(false);
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	Sword->SetRootComponent(Blade);
	if (OldRoot && OldRoot != Blade) OldRoot->AttachToComponent(Blade, FAttachmentTransformRules::KeepWorldTransform);
	Blade->SetCollisionProfileName(TEXT("PhysicsActor"));
	Blade->SetEnableGravity(true);
	BaseMassKg = A->SwordMassKg;
	if (!ApplyMass(BaseMassKg * A->GetSwordInertiaScale())) { Disappear(); return false; }
	Blade->BodyInstance.bUseCCD = true;
	Blade->BodyInstance.PositionSolverIterationCount = 16;
	Blade->BodyInstance.VelocitySolverIterationCount = 8;
	Grip = NewObject<UPhysicsConstraintComponent>(A);
	Grip->ComponentTags.Add(TEXT("Prophecy.ManagedConstraint")); // Its controller owns the Jolt grip separately.
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

UProphecyJoltBodyComponent* UProphecySwordComponent::EnsureJoltBody()
{
	if (!IsValid(Sword) || !IsValid(Blade)) return nullptr;
	if (!JoltBody)
	{
		JoltBody = NewObject<UProphecyJoltBodyComponent>(Sword);
		Sword->AddInstanceComponent(JoltBody);
		JoltBody->RegisterComponent();
	}
	return IsValid(JoltBody) && JoltBody->IsRegistered() && JoltBody->GetOwner() == Sword ? JoltBody.Get() : nullptr;
}

void UProphecySwordComponent::CancelJoltAdmission()
{
	PendingJoltBindId.Invalidate();
	bDropPending = false;
	if (JoltBody)
	{
		JoltBody->OnDeferredEnableCompleted.Remove(JoltEnableDelegate);
		if (JoltBody->IsEnablePending()) JoltBody->DisableBody();
	}
	JoltEnableDelegate.Reset();
}

bool UProphecySwordComponent::ReleaseJoltGrip()
{
	if (JoltBinding && JoltBinding->World.IsValid() && JoltBinding->World->OwnsJoint(JoltBinding->Joint))
	{
		const auto Result = JoltBinding->World->DestroyJoint(JoltBinding->Joint);
		if (!Result.IsSuccess())
		{
			UE_LOG(LogTemp, Error, TEXT("Jolt sword grip cleanup failed: %s"), *Result.Message);
			return false;
		}
	}
	JoltBinding.Reset();
	return true;
}

bool UProphecySwordComponent::ReleaseJoltBody()
{
	CancelJoltAdmission();
	if (!ReleaseJoltGrip()) return false;
	if (JoltBody)
	{
		JoltBody->DisableBody();
		if (JoltBody->IsJoltBody() || JoltBody->IsReceiverRestorePending()) return false;
	}
	return true;
}

bool UProphecySwordComponent::FinishJoltGrip(UProphecyJoltCharacterComponent& Character, USkeletalMeshComponent& Mesh)
{
	AProphecyAgent* A = Agent();
	if (!A || !IsValid(Sword) || !IsValid(Blade) || !JoltBody
		|| Character.IsSteppingStopped()
		|| !A->IsJoltPhysicalAnimationEnabled() || A->GetJoltCharacterComponent() != &Character
		|| A->GetPoseReferenceMesh() != &Mesh || !Mesh.GetPhysicsAsset()) return false;
	UProphecyJoltWorldSubsystem* World = JoltBody->GetWorldOwner();
	if (!World || World != GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()) return false;
	const FName Bone = Mesh.GetSocketBoneName(A->SwordHandSocket);
	FProphecyJoltBodyHandle Hand, SwordBody;
	FProphecyJoltBodyState HandState;
	FTransform BodyOriginToComponent;
	if (!Character.GetBodyHandle(Bone, Hand) || !JoltBody->GetBodyHandle(SwordBody)
		|| Hand.WorldLifetime != SwordBody.WorldLifetime || !World->ReadBody(Hand, HandState).IsSuccess()
		|| !JoltBody->GetBodyOriginToComponent(BodyOriginToComponent)) return false;
	if (!bPhysicsHold)
	{
		if (!ReleaseJoltGrip()) return false;
		FString Error;
		if (!JoltBody->FollowWelded(Hand, Mesh, A->SwordHandSocket, A->SwordGripTransform, Error))
		{ UE_LOG(LogTemp, Error, TEXT("Attached sword collider failed: %s"), *Error); return false; }
		if (!SetAttachedInertiaScale(A->GetSwordAttachedInertiaScale())) return false;
		JoltBinding.Reset(new FProphecyJoltSwordBinding);
		JoltBinding->World = World;
		JoltBinding->Character = &Character;
		JoltBinding->Hand = Hand;
		RefreshOwnerCollision();
		Blade->AttachToComponent(&Mesh, FAttachmentTransformRules::KeepWorldTransform, A->SwordHandSocket);
		Blade->SetRelativeTransform(A->SwordGripTransform);
		Blade->UpdateComponentToWorld();
		return true;
	}
	FTransform Anchor = Mesh.GetSocketTransform(A->SwordHandSocket);
	Anchor.SetScale3D(FVector::OneVector);
	FTransform DesiredComponent = GripWorld();
	DesiredComponent.SetScale3D(FVector::OneVector);
	const FTransform DesiredBodyOrigin = BodyOriginToComponent * DesiredComponent;
	FProphecyJoltJointSettings Settings;
	Settings.Type = EProphecyJoltJointType::Fixed;
	Settings.BodyA = Hand;
	Settings.BodyB = SwordBody;
	Settings.FrameA = Anchor.GetRelativeTransform(FTransform(HandState.Rotation, HandState.PositionCm));
	Settings.FrameB = Anchor.GetRelativeTransform(DesiredBodyOrigin);
	Settings.FrameA.SetScale3D(FVector::OneVector);
	Settings.FrameB.SetScale3D(FVector::OneVector);
	Settings.FrameA.NormalizeRotation();
	Settings.FrameB.NormalizeRotation();
	TArray<FProphecyJoltBodyPair> Exclusions;
	for (const USkeletalBodySetup* Setup : Mesh.GetPhysicsAsset()->SkeletalBodySetups)
	{
		FProphecyJoltBodyHandle OwnerBody;
		if (!Setup || !Character.GetBodyHandle(Setup->BoneName, OwnerBody)
			|| OwnerBody.WorldLifetime != SwordBody.WorldLifetime) return false;
		if (A->IsSwordAttackActive() || Setup->BoneName == Bone) Exclusions.Add({ SwordBody, OwnerBody });
	}
	if (!ReleaseJoltGrip()) return false;
	FProphecyJoltJointHandle Joint;
	const auto Result = World->CreateJoint(Settings, Exclusions, Joint);
	if (!Result.IsSuccess())
	{
		UE_LOG(LogTemp, Error, TEXT("Jolt sword fixed grip failed: %s"), *Result.Message);
		return false;
	}
	JoltBinding.Reset(new FProphecyJoltSwordBinding);
	JoltBinding->World = World;
	JoltBinding->Character = &Character;
	JoltBinding->Joint = Joint;
	JoltBinding->Hand = Hand;
	return true;
}

bool UProphecySwordComponent::BindJolt(bool bSnapToGrip)
{
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* Mesh = A ? A->GetPoseReferenceMesh() : nullptr;
	UProphecyJoltCharacterComponent* Character = A ? A->GetJoltCharacterComponent() : nullptr;
	FProphecyJoltBodyHandle ExpectedHand;
	if (!Mesh || !Character || Character->IsSteppingStopped()
		|| !Character->GetBodyHandle(Mesh->GetSocketBoneName(A->SwordHandSocket), ExpectedHand)) return false;
	if (PendingJoltBindId.IsValid()) return true;
	if (!EnsureJoltBody()) return false;
	if (JoltBody->IsAttachedCollider() && bPhysicsHold && !ReleaseJoltBody()) return false;
	if (JoltBody->IsJoltBody()) return FinishJoltGrip(*Character, *Mesh);
	const TWeakObjectPtr<AActor> ExpectedSword = Sword;
	const TWeakObjectPtr<UStaticMeshComponent> ExpectedBlade = Blade;
	const TWeakObjectPtr<USkeletalMeshComponent> ExpectedMesh = Mesh;
	const TWeakObjectPtr<UProphecyJoltCharacterComponent> ExpectedCharacter = Character;
	const TWeakObjectPtr<UProphecyJoltBodyComponent> ExpectedBody = JoltBody;
	const auto Intact = [&]()
	{
		return IsValid(this) && ExpectedSword.IsValid() && !ExpectedSword->IsActorBeingDestroyed()
			&& ExpectedBlade.IsValid() && Sword == ExpectedSword.Get() && Blade == ExpectedBlade.Get()
			&& JoltBody == ExpectedBody.Get() && Agent() == A && A->IsJoltPhysicalAnimationEnabled()
			&& A->GetPoseReferenceMesh() == ExpectedMesh.Get() && A->GetJoltCharacterComponent() == ExpectedCharacter.Get();
	};
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	if (!Intact()) return false;
	if (bSnapToGrip) Blade->SetWorldTransform(GripWorld(), false, nullptr, ETeleportType::TeleportPhysics);
	if (!Intact()) return false;
	Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	if (!Intact()) return false;
	Blade->SetSimulatePhysics(true); // Required live source; coordinator admission owns the handoff.
	if (!Intact() || !Blade->IsSimulatingPhysics()) return false;
	// User-approved Jolt policy: omit Chaos MACD and retain the existing CCD setting.
	Blade->BodyInstance.SetUseMACD(false);
	if (bSnapToGrip)
	{
		// Internal capture setup belongs to this controller. Do not dispatch through
		// the generic receiver, which would auto-admit a second owner before ours.
		Blade->UPrimitiveComponent::SetPhysicsLinearVelocity(CarriedLinear);
		Blade->UPrimitiveComponent::SetPhysicsAngularVelocityInRadians(CarriedAngular);
	}
	const FGuid RequestId = FGuid::NewGuid();
	PendingJoltBindId = RequestId;
	JoltEnableDelegate = JoltBody->OnDeferredEnableCompleted.AddWeakLambda(this,
		[this, RequestId, ExpectedSword, ExpectedBlade, ExpectedMesh, ExpectedCharacter, ExpectedBody,
		 ExpectedHand](bool bSucceeded, const FString& Error)
		{
			if (PendingJoltBindId != RequestId || Sword != ExpectedSword.Get() || Blade != ExpectedBlade.Get()
				|| JoltBody != ExpectedBody.Get()) return;
			PendingJoltBindId.Invalidate();
			JoltEnableDelegate.Reset();
			FProphecyJoltBodyHandle CurrentHand;
			const bool bSameHand = ExpectedMesh.IsValid() && ExpectedCharacter.IsValid() && Agent()
				&& ExpectedCharacter->GetBodyHandle(ExpectedMesh->GetSocketBoneName(Agent()->SwordHandSocket), CurrentHand)
				&& CurrentHand.WorldLifetime == ExpectedHand.WorldLifetime && CurrentHand.Slot == ExpectedHand.Slot
				&& CurrentHand.Generation == ExpectedHand.Generation;
			if (bSucceeded && bSameHand && FinishJoltGrip(*ExpectedCharacter, *ExpectedMesh)) return;
			UE_LOG(LogTemp, Error, TEXT("Deferred Jolt sword binding failed: %s"),
				Error.IsEmpty() ? TEXT("The captured hand binding changed or the fixed joint could not be created.") : *Error);
			// Keep the existing receiver, materials and blood even when native activation fails.
			if (ReleaseJoltBody())
			{
				bPhysicsHold = false;
				if (Bind(false)) return;
			}
			bRefreshPending = true;
		});
	FString Error;
	if (!JoltBody->EnableBody(*Blade, Error))
	{
		CancelJoltAdmission();
		UE_LOG(LogTemp, Error, TEXT("Jolt sword body activation failed: %s"), *Error);
		return false;
	}
	if (!Intact()) return false;
	if (JoltBody->IsEnablePending()) return true;
	CancelJoltAdmission(); // Remove only our completion listener; active ownership remains.
	if (FinishJoltGrip(*Character, *Mesh)) return true;
	ReleaseJoltBody();
	return false;
}

bool UProphecySwordComponent::Bind(bool bSnapToGrip)
{
	if (bBinding || bDropPending || (JoltBody && JoltBody->IsReceiverRestorePending())) return false;
	TGuardValue<bool> BindingGuard(bBinding, true);
	AProphecyAgent* A = Agent();
	USkeletalMeshComponent* M = A ? A->GetPoseReferenceMesh() : nullptr;
	if (!M || !Sword || !Blade || !Grip || !M->DoesSocketExist(A->SwordHandSocket)) return false;
	if (A->GetJoltCharacterComponent() && A->GetJoltCharacterComponent()->IsKinematicRestorePending()) return false;
	ClearOwnerCollisions(this);
	Grip->BreakConstraint();
	if (BoundMesh != M)
	{
		if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
		BoundMesh = M;
		AddTickPrerequisiteComponent(M);
	}
	if (A->IsJoltPhysicalAnimationEnabled()) return BindJolt(bSnapToGrip);
	if (bPhysicsHold)
	{
		if (!ReleaseJoltBody()) return false;
		const FName Bone = M->GetSocketBoneName(A->SwordHandSocket);
		FBodyInstance* Hand = M->GetBodyInstance(Bone);
		if (!Hand || !Hand->IsValidBodyInstance()) return false;
		Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
		if (bSnapToGrip) Blade->SetWorldTransform(GripWorld(), false, nullptr, ETeleportType::TeleportPhysics);
		Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Blade->SetSimulatePhysics(true);
		if (!Blade->IsSimulatingPhysics()) return false;
		if (A->IsSwordAttackActive()) IgnoreOwnerCollisions(this, Blade, A);
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
		if (!ReleaseJoltBody()) return false;
		Blade->SetSimulatePhysics(false);
		// Chaos owns a moving, non-simulated collider while the socket owns presentation.
		Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		Blade->AttachToComponent(M, FAttachmentTransformRules::KeepWorldTransform, A->SwordHandSocket);
		Blade->SetRelativeTransform(A->SwordGripTransform);
		// An unchanged relative transform can early-out after a mode switch has
		// temporarily propagated a different socket pose to attached children.
		Blade->UpdateComponentToWorld();
		IgnoreOwnerCollisions(this, Blade, A, A->IsSwordAttackActive(), true);
	}
	bHasPrevious = false;
	return true;
}

bool UProphecySwordComponent::ApplyMass(float MassKg)
{
	if (!Blade || !FMath::IsFinite(MassKg) || MassKg <= 0 || !FMath::IsFinite(1.0f / MassKg)) return false;
	if (JoltBody && (JoltBody->IsEnablePending() || JoltBody->IsReceiverRestorePending())) return false;
	if (JoltBody && JoltBody->IsJoltBody() && !JoltBody->IsAttachedCollider())
	{
		FProphecyJoltBodyHandle Handle;
		if (!JoltBody->GetWorldOwner() || !JoltBody->GetBodyHandle(Handle)) return false;
		const auto Result = JoltBody->GetWorldOwner()->SetBodyMassKg(Handle, MassKg);
		if (!Result.IsSuccess()) { UE_LOG(LogTemp, Error, TEXT("Sword mass update failed: %s"), *Result.Message); return false; }
	}
	// Keep the existing UE receiver's mass override in sync for backend changes/re-admission.
	// Neither operation replaces the body, changes its COM, or rewrites its velocity.
	Blade->SetMassOverrideInKg(NAME_None, MassKg, true);
	return true;
}

bool UProphecySwordComponent::SetInertiaScale(float Scale)
{
	return !Sword || (!bDropPending && ApplyMass(BaseMassKg * Scale));
}

bool UProphecySwordComponent::SetAttachedInertiaScale(float Scale)
{
	// Store preferences before equip, during deferred admission, and on other backends.
	// Only an existing welded Jolt collider needs a native update here.
	if (!JoltBody || !JoltBody->IsAttachedCollider()) return true;
	FProphecyJoltBodyHandle Handle;
	if (!JoltBody->GetWorldOwner() || !JoltBody->GetBodyHandle(Handle)) return false;
	const auto Result = JoltBody->GetWorldOwner()->SetWeldedBodyInertiaScale(Handle, Scale);
	if (!Result.IsSuccess()) UE_LOG(LogTemp, Error, TEXT("Attached sword inertia update failed: %s"), *Result.Message);
	return Result.IsSuccess();
}

void UProphecySwordComponent::RefreshOwnerCollision()
{
	AProphecyAgent* A = Agent();
	if (!A || !Sword || !Blade || bDropPending) return;
	// Deferred admission reads the current attack state when it creates the grip.
	if (PendingJoltBindId.IsValid()) return;
	if (JoltBinding)
	{
		FProphecyJoltBodyHandle SwordBody;
		auto* Character = JoltBinding->Character.Get();
		auto* World = JoltBinding->World.Get();
		if (!World || !Character || !BoundMesh || !BoundMesh->GetPhysicsAsset()
			|| !JoltBody || !JoltBody->GetBodyHandle(SwordBody)) return;
		TArray<FProphecyJoltBodyPair> Pairs;
		Pairs.Add({ SwordBody, JoltBinding->Hand });
		if (A->IsSwordAttackActive())
		{
			for (const USkeletalBodySetup* Setup : BoundMesh->GetPhysicsAsset()->SkeletalBodySetups)
			{
				FProphecyJoltBodyHandle Body;
				if (Setup && Character->GetBodyHandle(Setup->BoneName, Body)) Pairs.Add({ SwordBody, Body });
			}
		}
		const auto Result = JoltBody->IsAttachedCollider()
			? World->UpdateBodySuppressedPairs(SwordBody, Pairs)
			: World->UpdateJointSuppressedPairs(JoltBinding->Joint, Pairs);
		if (!Result.IsSuccess()) UE_LOG(LogTemp, Error, TEXT("Sword owner collision update failed: %s"), *Result.Message);
	}
	else
	{
		ClearOwnerCollisions(this);
		if (A->IsSwordAttackActive() || !bPhysicsHold)
			IgnoreOwnerCollisions(this, Blade, A, A->IsSwordAttackActive(), !bPhysicsHold);
	}
}

bool UProphecySwordComponent::SetSimulated(bool bSimulated)
{
	if (!Sword || !Blade || bBinding || bDropPending || PendingJoltBindId.IsValid()
		|| (JoltBody && JoltBody->IsReceiverRestorePending())) return false;
	if (bPhysicsHold == bSimulated) return true;
	const bool OldMode = bPhysicsHold;
	bPhysicsHold = bSimulated;
	if (!Bind(bSimulated)) { bPhysicsHold = OldMode; if (!Bind(false)) bRefreshPending = true; return false; }
	if (bSimulated)
	{
		if (JoltBody && JoltBody->IsJoltBody())
		{
			FString Error;
			if (!JoltBody->SetBodyVelocity(CarriedLinear, CarriedAngular, true, Error))
			{
				UE_LOG(LogTemp, Error, TEXT("Jolt sword velocity handoff failed: %s"), *Error);
				bPhysicsHold = OldMode;
				if (!Bind(false)) bRefreshPending = true;
				return false;
			}
		}
		else if (!PendingJoltBindId.IsValid())
		{
			Blade->UPrimitiveComponent::SetPhysicsLinearVelocity(CarriedLinear);
			Blade->UPrimitiveComponent::SetPhysicsAngularVelocityInRadians(CarriedAngular);
		}
	}
	return true;
}

void UProphecySwordComponent::RefreshHandConstraint()
{
	if (!Sword || bDropPending) return;
	AProphecyAgent* A = Agent();
	if (bBinding || (JoltBody && JoltBody->IsReceiverRestorePending())
		|| (A && A->GetJoltCharacterComponent() && A->GetJoltCharacterComponent()->IsKinematicRestorePending()))
	{ bRefreshPending = true; return; }
	bRefreshPending = false;
	if (!Bind(false))
	{
		UE_LOG(LogTemp, Error, TEXT("Sword backend refresh failed; retaining the item in attached mode."));
		bPhysicsHold = false;
		if (!Bind(false)) bRefreshPending = true;
	}
}

AActor* UProphecySwordComponent::FinishDrop()
{
	ClearOwnerCollisions(this);
	if (Grip) { Grip->BreakConstraint(); Grip->DestroyComponent(); Grip = nullptr; }
	AActor* Result = Sword;
	Result->SetOwner(nullptr);
	if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
	BoundMesh = nullptr;
	// The component belongs to the sword actor and remains registered after these held references clear.
	JoltBody = nullptr;
	Sword = nullptr;
	Blade = nullptr;
	bPhysicsHold = false;
	bDropPending = false;
	bRefreshPending = false;
	PendingJoltBindId.Invalidate();
	JoltEnableDelegate.Reset();
	bHasPrevious = false;
	return Result;
}

AActor* UProphecySwordComponent::Drop()
{
	if (!IsValid(Sword) || !IsValid(Blade) || bBinding
		|| (JoltBody && JoltBody->IsReceiverRestorePending())) return nullptr;
	if (bDropPending) return Sword;
	AProphecyAgent* A = Agent();
	if (A && A->GetJoltCharacterComponent() && A->GetJoltCharacterComponent()->IsKinematicRestorePending()) return nullptr;
	TGuardValue<bool> BindingGuard(bBinding, true);
	// Restore the hand shape and re-admit the sword as an independent dynamic on drop.
	if (JoltBody && JoltBody->IsAttachedCollider() && !ReleaseJoltBody()) return nullptr;
	// Held assistance ends on release, without changing the carried linear/angular velocities.
	if (!ApplyMass(BaseMassKg)) return nullptr;
	if (JoltBody && JoltBody->IsJoltBody())
	{
		FProphecyJoltBodyState Current;
		if (JoltBody->IsSteppingStopped() || !JoltBody->GetBodyState(Current) || !ReleaseJoltGrip()) return nullptr;
		CancelJoltAdmission();
		return FinishDrop(); // Native V/W, gravity and registration are unchanged.
	}
	const FVector Linear = bPhysicsHold ? Blade->GetPhysicsLinearVelocity() : CarriedLinear;
	const FVector Angular = bPhysicsHold ? Blade->GetPhysicsAngularVelocityInRadians() : CarriedAngular;
	CancelJoltAdmission();
	if (!ReleaseJoltGrip()) return nullptr;
	ClearOwnerCollisions(this);
	if (Grip) Grip->BreakConstraint();
	const TWeakObjectPtr<AActor> ExpectedSword = Sword;
	const TWeakObjectPtr<UStaticMeshComponent> ExpectedBlade = Blade;
	const auto Intact = [&]()
	{
		return IsValid(this) && ExpectedSword.IsValid() && !ExpectedSword->IsActorBeingDestroyed()
			&& ExpectedBlade.IsValid() && Sword == ExpectedSword.Get() && Blade == ExpectedBlade.Get();
	};
	Blade->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
	if (!Intact()) return nullptr;
	Blade->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
	if (!Intact()) return nullptr;
	Blade->SetEnableGravity(true);
	Blade->SetSimulatePhysics(true);
	if (!Intact()) return nullptr;
	// Stage the live source for the managed handoff below. Calling the derived
	// Blueprint receiver here auto-admits/freezes it before EnsureJoltBody runs.
	Blade->UPrimitiveComponent::SetPhysicsLinearVelocity(Linear);
	Blade->UPrimitiveComponent::SetPhysicsAngularVelocityInRadians(Angular);
	Blade->WakeAllRigidBodies();
	if (!Intact()) return nullptr;
	if (!A || !A->IsJoltPhysicalAnimationEnabled()) return FinishDrop();
	const auto RestoreAttached = [&]()
	{
		if (!Intact()) return;
		CancelJoltAdmission();
		bPhysicsHold = false;
		TGuardValue<bool> AllowBind(bBinding, false);
		if (!Bind(false)) bRefreshPending = true;
	};
	if (!EnsureJoltBody()) { RestoreAttached(); return nullptr; }
	// An attached sword can be dropped directly without ever going through BindJolt.
	Blade->BodyInstance.SetUseMACD(false);
	const TWeakObjectPtr<UProphecyJoltBodyComponent> ExpectedBody = JoltBody;
	const FGuid RequestId = FGuid::NewGuid();
	PendingJoltBindId = RequestId;
	bDropPending = true;
	JoltEnableDelegate = JoltBody->OnDeferredEnableCompleted.AddWeakLambda(this,
		[this, ExpectedSword, ExpectedBlade, ExpectedBody, RequestId](bool bSucceeded, const FString& Error)
		{
			if (PendingJoltBindId != RequestId || !bDropPending || Sword != ExpectedSword.Get()
				|| Blade != ExpectedBlade.Get() || JoltBody != ExpectedBody.Get()) return;
			PendingJoltBindId.Invalidate();
			JoltEnableDelegate.Reset();
			bDropPending = false;
			if (bSucceeded && ExpectedBody.IsValid() && ExpectedBody->IsJoltBody()) { FinishDrop(); return; }
			UE_LOG(LogTemp, Error, TEXT("Deferred Jolt sword drop failed; the existing sword stays held: %s"), *Error);
			bPhysicsHold = false;
			if (!Bind(false)) bRefreshPending = true;
		});
	FString Error;
	if (!JoltBody->EnableBody(*Blade, Error))
	{
		UE_LOG(LogTemp, Error, TEXT("Jolt sword drop failed; restored held attachment: %s"), *Error);
		RestoreAttached();
		return nullptr;
	}
	if (!Intact()) return nullptr;
	if (JoltBody->IsEnablePending()) return Sword; // Accepted request; held references survive until success.
	CancelJoltAdmission();
	return FinishDrop();
}

void UProphecySwordComponent::Disappear()
{
	CancelJoltAdmission();
	ReleaseJoltBody(); // Generic grip is always removed before its native body.
	ClearOwnerCollisions(this);
	if (Grip) { Grip->BreakConstraint(); Grip->DestroyComponent(); Grip = nullptr; }
	if (Sword) Sword->Destroy();
	Sword = nullptr;
	Blade = nullptr;
	JoltBody = nullptr;
	if (BoundMesh) RemoveTickPrerequisiteComponent(BoundMesh);
	BoundMesh = nullptr;
	bPhysicsHold = false;
	bRefreshPending = false;
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
	if (!IsValid(Sword) || !IsValid(Blade)) { Disappear(); return; }
	AProphecyAgent* A = Agent();
	if (!A) return;
	if (!bDropPending && (bRefreshPending || BoundMesh != A->GetPoseReferenceMesh()
		|| (!PendingJoltBindId.IsValid()
			&& A->IsJoltPhysicalAnimationEnabled() != bool(JoltBinding)))) RefreshHandConstraint();
	if (!IsValid(Sword) || !IsValid(Blade)) return;
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
bool AProphecyAgent::SetSwordAttachedInertiaScale(float Scale)
{
	if (!FMath::IsFinite(Scale) || Scale < 0.0f) return false;
	if (Scale == SwordAttachedInertiaScale) return true;
	if (auto* C = SwordController(this, false); C && !C->SetAttachedInertiaScale(Scale)) return false;
	SwordAttachedInertiaScale = Scale;
	return true;
}

bool AProphecyAgent::SetSwordInertiaScale(float Scale)
{
	if (!FMath::IsFinite(Scale) || Scale <= 0 || !FMath::IsFinite(1.0f / Scale)) return false;
	if (Scale == SwordInertiaScale) return true;
	if (auto* C = SwordController(this, false); C && !C->SetInertiaScale(Scale)) return false;
	SwordInertiaScale = Scale;
	return true;
}
#include "ProphecyPhysicalContext.h"
void AProphecyAgent::NotifySwordAttackState(bool bAttacking)
{
	if (bSwordAttackActive == bAttacking) return;
	bSwordAttackActive = bAttacking;
	ProphecyPhysicalContext::AttackChanged(this);
	if (auto* C = SwordController(this, false)) C->RefreshOwnerCollision();
}
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
