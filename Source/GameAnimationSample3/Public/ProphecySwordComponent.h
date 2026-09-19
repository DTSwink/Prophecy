#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecySwordComponent.generated.h"

class AProphecyAgent;
class UStaticMeshComponent;
class UPhysicsConstraintComponent;
class USkeletalMeshComponent;
class UProphecyJoltBodyComponent;
class UProphecyJoltCharacterComponent;
struct FProphecyJoltSwordBinding;
struct FProphecyJoltSwordBindingDeleter
{
	void operator()(FProphecyJoltSwordBinding* Binding) const;
};

/** Runtime-only controller for the existing sword Blueprint. Never edits the Blueprint asset. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySwordComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UProphecySwordComponent();
	virtual ~UProphecySwordComponent() override;
	bool Equip(bool bSimulated);
	bool SetSimulated(bool bSimulated);
	AActor* Drop();
	void Disappear();
	void RefreshHandConstraint();
	bool BreakGripConstraint();
	bool SetInertiaScale(float Scale);
	bool SetAttachedInertiaScale(float Scale);
	void RefreshOwnerCollision();
	AActor* GetSword() const { return Sword; }
	bool IsSimulated() const { return Sword && bPhysicsHold; }
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
	AProphecyAgent* Agent() const;
	bool Bind(bool bSnapToGrip);
	bool BindJolt(bool bSnapToGrip);
	bool FinishJoltGrip(UProphecyJoltCharacterComponent& Character, USkeletalMeshComponent& Mesh);
	bool ReleaseJoltGrip();
	bool ReleaseJoltBody();
	UProphecyJoltBodyComponent* EnsureJoltBody();
	void CancelJoltAdmission();
	AActor* FinishDrop();
	FTransform GripWorld() const;
	bool ApplyMass(float MassKg);
	float BaseMassKg = 1.0f;
	UPROPERTY(Transient) TObjectPtr<AActor> Sword;
	UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Blade;
	UPROPERTY(Transient) TObjectPtr<UPhysicsConstraintComponent> Grip;
	UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> BoundMesh;
	UPROPERTY(Transient) TObjectPtr<UProphecyJoltBodyComponent> JoltBody;
	TUniquePtr<FProphecyJoltSwordBinding, FProphecyJoltSwordBindingDeleter> JoltBinding;
	FGuid PendingJoltBindId;
	FDelegateHandle JoltEnableDelegate;
	bool bBinding = false;
	bool bDropPending = false;
	bool bRefreshPending = false;
	bool bPhysicsHold = false;
	FTransform PreviousWorld;
	FVector CarriedLinear = FVector::ZeroVector;
	FVector CarriedAngular = FVector::ZeroVector;
	bool bHasPrevious = false;
};
