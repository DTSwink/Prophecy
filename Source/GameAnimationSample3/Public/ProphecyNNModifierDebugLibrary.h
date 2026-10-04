#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyNNModifierDebugLibrary.generated.h"

class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyNNModifierDebugLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Read the current accepted modifier state without advancing it. Draw each entry in a different
     * color for one game tick. Call on Tick to keep it visible, or once to inspect that instant.
     * Report also contains every row, including rows that cannot fit a small viewport.
     * Active constraints are potential corrections, not proof of a nonzero bone displacement.
     * Input/history, output, presentation and physical influences are labelled separately. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|NN Debug", meta=(DefaultToSelf="Agent", DisplayName="Print NN Modifiers"))
    static int32 PrintNNModifiers(AProphecyAgent* Agent, FString& Report);
};
