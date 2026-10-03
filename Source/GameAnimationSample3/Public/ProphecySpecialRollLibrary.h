#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySpecialRollLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySpecialRollLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Enabled by default. Both forearms use idle-referenced upper-arm roll in attacks,
     * parry and dodge. Disable to inspect the decoded checkpoint rotations.
     * Applies at the next policy pose; positions, hand rotations and NN state are unchanged. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Specials",meta=(DefaultToSelf="Agent"))
    static bool SetSpecialForearmRollCorrection(AProphecyAgent* Agent,bool Enabled=true);

    /** Enabled by default. Both calves use the thigh-guided roll during full
     * attacks. Disable to inspect the decoded checkpoint rotations. Does not
     * change leg reconstruction, foot rotation, endpoints, or locomotion. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Specials",meta=(DefaultToSelf="Agent"))
    static bool SetSpecialCalfRollCorrection(AProphecyAgent* Agent,bool Enabled=true);
};
