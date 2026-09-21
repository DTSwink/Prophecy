#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltFootJointLibrary.generated.h"

/** Internal bridge; keeps the existing WorldSubsystem reflected layout unchanged. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltFootJointLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION()
    static bool SetFootExtension(UObject* WorldContext, FGuid Lifetime, int32 BodySlot, int64 BodyGeneration,
        float LeewayCm, FVector LeftCalfAxis, FVector RightCalfAxis, FString& OutError);
};
