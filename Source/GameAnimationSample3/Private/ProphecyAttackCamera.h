#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecyAttackCamera.generated.h"

class AProphecyAgent;
class USpringArmComponent;
class USkeletalMeshComponent;

// Created only on the possessed pawn. UObject lifetime keeps a queued tick alive
// when an attack ends or the pawn is destroyed before the PostPhysics group.
UCLASS(Transient)
class UProphecyAttackCameraComponent final : public UActorComponent
{
	GENERATED_BODY()
public:
	UProphecyAttackCameraComponent();
	void Follow(AActor* InManager, AProphecyAgent* InAgent);
	void CompensateRootSnap(const FVector& PreviousSpringOrigin);
	void Stop();
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void OnUnregister() override;

private:
	friend class FProphecyAttackCameraComTest;
	void Restore();
	void ReleasePrerequisites();
	void SetMesh(USkeletalMeshComponent* NewMesh);
	FVector ReadCenterOfMass(bool bRebuild);
	struct FBoneMass { int32 Index; double Mass; FVector LocalCenter; };
	TArray<FBoneMass,TInlineAllocator<32>> BoneMasses;
	FVector InitialComFromRoot=FVector::ZeroVector;
	bool bTrackingCom=false;
	TWeakObjectPtr<AActor> Manager;
	TWeakObjectPtr<AProphecyAgent> Agent;
	TWeakObjectPtr<USpringArmComponent> Spring;
	TWeakObjectPtr<USkeletalMeshComponent> Mesh;
	FVector InitialPelvisFromRoot = FVector::ZeroVector;
	FVector AppliedOffset = FVector::ZeroVector;
	bool bFollowing = false;
	bool bTrackingPelvis = false;
};

namespace ProphecyAttackCamera
{
	// Keep inherited Blueprint references; only possessed players register/tick the rig in game.
	void RefreshPlayerRig(AProphecyAgent* Agent);
	void Stop(const AActor* Manager);
	void End(const AActor* Manager);
	void Update(AActor* Manager, AProphecyAgent* Player, bool bFullAttack);
	void CompensateRootSnap(AProphecyAgent* Player, const FVector& PreviousSpringOrigin);
}
