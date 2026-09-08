#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "ProphecySwordComponent.generated.h"

class AProphecyAgent;
class UStaticMeshComponent;
class UPhysicsConstraintComponent;
class USkeletalMeshComponent;

/** Runtime-only controller for the existing sword Blueprint. Never edits the Blueprint asset. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySwordComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UProphecySwordComponent();
	bool Equip(bool bSimulated);
	bool SetSimulated(bool bSimulated);
	AActor* Drop();
	void Disappear();
	void RefreshHandConstraint();
	AActor* GetSword() const { return Sword; }
	bool IsSimulated() const { return Sword && bPhysicsHold; }
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
	AProphecyAgent* Agent() const;
	bool Bind(bool bSnapToGrip);
	FTransform GripWorld() const;
	UPROPERTY(Transient) TObjectPtr<AActor> Sword;
	UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> Blade;
	UPROPERTY(Transient) TObjectPtr<UPhysicsConstraintComponent> Grip;
	UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> BoundMesh;
	bool bPhysicsHold = false;
	FTransform PreviousWorld;
	FVector CarriedLinear = FVector::ZeroVector;
	FVector CarriedAngular = FVector::ZeroVector;
	bool bHasPrevious = false;
};
