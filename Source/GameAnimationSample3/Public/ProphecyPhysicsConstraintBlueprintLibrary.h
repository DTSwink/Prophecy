#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "PhysicsEngine/ConstraintTypes.h"
#include "ProphecyPhysicsConstraintBlueprintLibrary.generated.h"

class UPhysicsConstraintComponent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicsConstraintBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Physics|Components|PhysicsConstraint", meta = (DisplayName = "Get Linear ZLimit", Keywords = "constraint physics linear z limit motion free limited locked"))
	static void GetLinearZLimit(
		UPhysicsConstraintComponent* Target,
		TEnumAsByte<ELinearConstraintMotion>& ConstraintType,
		float& LimitSize);
};
