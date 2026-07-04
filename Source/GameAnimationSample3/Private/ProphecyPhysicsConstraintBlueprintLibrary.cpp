#include "ProphecyPhysicsConstraintBlueprintLibrary.h"

#include "PhysicsEngine/PhysicsConstraintComponent.h"

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
