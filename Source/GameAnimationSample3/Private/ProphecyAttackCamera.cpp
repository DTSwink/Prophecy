#include "ProphecyAttackCamera.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"

UProphecyAttackCameraComponent::UProphecyAttackCameraComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
	PrimaryComponentTick.EndTickGroup = TG_PostPhysics;
}

void UProphecyAttackCameraComponent::SetMesh(USkeletalMeshComponent* NewMesh)
{
	if (Mesh.Get() == NewMesh) return;
	if (Mesh.IsValid()) RemoveTickPrerequisiteComponent(Mesh.Get());
	Mesh = NewMesh;
	if (NewMesh) AddTickPrerequisiteComponent(NewMesh);
}

void UProphecyAttackCameraComponent::Follow(AActor* InManager, AProphecyAgent* InAgent)
{
	if (bFollowing)
	{
		SetMesh(InAgent->GetPoseReferenceMesh());
		return;
	}
	Manager = InManager; Agent = InAgent; Spring = InAgent->GetAgentSpringArm();
	SetMesh(InAgent->GetPoseReferenceMesh());
	InitialPelvisFromRoot = Mesh->GetSocketLocation(TEXT("pelvis")) - InAgent->GetActorLocation();
	AddTickPrerequisiteActor(InManager);
	AddTickPrerequisiteActor(InAgent);
	Spring->AddTickPrerequisiteComponent(this);
	bFollowing = true;
	SetComponentTickEnabled(true);
}

void UProphecyAttackCameraComponent::Restore()
{
	if (Spring.IsValid()) Spring->TargetOffset -= AppliedOffset;
	AppliedOffset = FVector::ZeroVector;
}

void UProphecyAttackCameraComponent::ReleasePrerequisites()
{
	if (Spring.IsValid()) Spring->RemoveTickPrerequisiteComponent(this);
	if (Manager.IsValid()) RemoveTickPrerequisiteActor(Manager.Get());
	if (Agent.IsValid()) RemoveTickPrerequisiteActor(Agent.Get());
	SetMesh(nullptr);
}

void UProphecyAttackCameraComponent::Stop()
{
	Restore();
	bFollowing = false;
	SetComponentTickEnabled(false);
	ReleasePrerequisites();
}

void UProphecyAttackCameraComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	AProphecyAgent* Pawn = Agent.Get();
	const auto* OwnerManager = Cast<AProphecyNNLocomotionManager>(Manager.Get());
	FName Attack; bool bHalf = false, bArmed = false, bHit = false; int32 Frame = 0;
	const bool bFullAttack = Pawn && OwnerManager && OwnerManager->GetAgentNNAttackState(
		Pawn->GetAgentHandle(), Attack, bHalf, bArmed, bHit, Frame) && !bHalf;
	if (!bFollowing || !bFullAttack || !Cast<APlayerController>(Pawn->GetController()) || !Spring.IsValid() || !Mesh.IsValid())
	{
		Stop();
		return;
	}
	// Jolt publishes before physics completes; the mesh prerequisite also waits
	// for skeletal evaluation. Read the actual displayed body in either backend.
	FVector Offset = Mesh->GetSocketLocation(TEXT("pelvis")) - Pawn->GetActorLocation() - InitialPelvisFromRoot;
	Offset.Z = 0; // Follow attack travel without adding pelvis bob to the camera.
	Spring->TargetOffset += Offset - AppliedOffset;
	AppliedOffset = Offset;
}

void UProphecyAttackCameraComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	Stop();
	Super::EndPlay(Reason);
}

void UProphecyAttackCameraComponent::OnUnregister()
{
	Stop();
	Super::OnUnregister();
}

namespace ProphecyAttackCamera
{
	static TMap<const AActor*, TWeakObjectPtr<UProphecyAttackCameraComponent>> Followers;

	void Stop(const AActor* Manager)
	{
		if (auto* Entry = Followers.Find(Manager))
			if (auto* Follow = Entry->Get()) Follow->Stop();
	}

	void End(const AActor* Manager)
	{
		TWeakObjectPtr<UProphecyAttackCameraComponent> Entry;
		if (Followers.RemoveAndCopyValue(Manager, Entry))
			if (auto* Follow = Entry.Get()) Follow->DestroyComponent();
	}

	void Update(AActor* Manager, AProphecyAgent* Player, bool bFullAttack)
	{
		if (!bFullAttack || !Player || !Cast<APlayerController>(Player->GetController()) ||
			!Player->GetAgentSpringArm() || !Player->GetPoseReferenceMesh())
		{
			// Blueprint may start the next attack later in PrePhysics. The follower
			// resolves the final state in PostPhysics, avoiding an intermediate reset.
			return;
		}
		auto& Entry = Followers.FindOrAdd(Manager);
		if (Entry.IsValid() && Entry->GetOwner() != Player)
		{
			Entry->DestroyComponent();
			Entry.Reset();
		}
		if (!Entry.IsValid())
		{
			auto* Follow = NewObject<UProphecyAttackCameraComponent>(Player, NAME_None, RF_Transient);
			Player->AddInstanceComponent(Follow);
			Follow->RegisterComponent();
			Entry = Follow;
		}
		Entry->Follow(Manager, Player);
	}
}
