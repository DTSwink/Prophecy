#pragma once

#include "CoreMinimal.h"
#include "ProphecyDoubleReachTypes.generated.h"

UENUM(BlueprintType)
enum class EProphecyDoubleReachMode : uint8
{
	Off UMETA(DisplayName = "Animation Only"),
	Left UMETA(DisplayName = "Reach Left"),
	Right UMETA(DisplayName = "Reach Right"),
	Both UMETA(DisplayName = "Reach Both")
};
