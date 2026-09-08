#pragma once

#include "CoreMinimal.h"
#include "Components/SkinnedMeshComponent.h"
#include "ProceduralMeshComponent.h"
#include "ProphecyPotenceRopeVisualComponent.generated.h"

class USkeletalMeshComponent;

/**
 * Post-physics updater for a transient poseable copy of SKM_RopeHang.
 *
 * The hidden skeletal mesh remains the PHAT rig. Its original skinned geometry is
 * rendered unchanged while reeled bones are collapsed at the fixed wood anchor.
 */
UCLASS(Transient, NotBlueprintable)
class GAMEANIMATIONSAMPLE3_API UProphecyPotenceRopeVisualComponent final : public UProceduralMeshComponent
{
	GENERATED_BODY()

public:
	explicit UProphecyPotenceRopeVisualComponent(const FObjectInitializer& ObjectInitializer);

	void Initialize(USkeletalMeshComponent* InTarget);
	void SetRetractionAmount(float InAmount);
	USkeletalMeshComponent* GetTarget() const { return Target.Get(); }

	virtual void TickComponent(
		float DeltaTime,
		ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void OnComponentDestroyed(bool bDestroyingHierarchy) override;

private:
	void UpdateRopeMesh();

	TWeakObjectPtr<USkeletalMeshComponent> Target;
	float RetractionAmount = 0.0f;
	float RopeRadius = 5.0f;
	bool bSectionCreated = false;
	bool bOriginalTargetVisible = true;
	EVisibilityBasedAnimTickOption OriginalVisibilityTickOption = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;

	TArray<FVector> Vertices;
	TArray<int32> Triangles;
	TArray<FVector> Normals;
	TArray<FVector2D> UV0;
	TArray<FLinearColor> VertexColors;
	TArray<FProcMeshTangent> Tangents;
};
