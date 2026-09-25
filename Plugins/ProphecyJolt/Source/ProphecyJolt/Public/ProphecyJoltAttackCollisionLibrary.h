#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltAttackCollisionLibrary.generated.h"

/** Internal event-only bridge. Attack suppression never overwrites configured self-collision. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltAttackCollisionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION()
    static bool SetSuppressed(UObject* WorldContext, FGuid Lifetime, int32 RigSlot,
        int64 RigGeneration, bool bSuppressed, FString& OutError);
};
