#pragma once
#include "CoreMinimal.h"
#include "ProphecyPhysicalContextTypes.generated.h"

// Both is deliberately zero: existing serialized Blueprint nodes retain their scope.
UENUM(BlueprintType)
enum class EProphecyLocomotionSelection : uint8 { Both, Walk, Run };

UENUM(BlueprintType)
enum class EProphecyEquipmentSelection : uint8 { Both, Drawn, Sheathed };
