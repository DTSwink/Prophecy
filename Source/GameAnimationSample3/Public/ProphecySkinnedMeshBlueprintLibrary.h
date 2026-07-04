#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySkinnedMeshBlueprintLibrary.generated.h"

class USkinnedMeshComponent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySkinnedMeshBlueprintLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Prophecy|Skinned Mesh", meta = (DisplayName = "Get Bone Parent And Children", Keywords = "bone parent child children recursive skeleton skinned mesh"))
	static void GetBoneParentAndChildren(
		USkinnedMeshComponent* SkinnedComp,
		FName BoneName,
		FName& OutParent,
		TArray<FName>& OutChildren,
		bool bRecursive = true);
};
