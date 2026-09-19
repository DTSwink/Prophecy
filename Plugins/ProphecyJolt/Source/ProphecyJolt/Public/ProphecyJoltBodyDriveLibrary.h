#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltBodyDriveLibrary.generated.h"

/** Internal event bridge: avoids changing the live WorldSubsystem reflected class. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltBodyDriveLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION()
    static bool SetDriveFollower(UObject* WorldContext, FGuid Lifetime, int32 BodySlot, int64 BodyGeneration,
        int32 ParentSlot, int64 ParentGeneration, FTransform BodyToParent, bool Enabled);
};
