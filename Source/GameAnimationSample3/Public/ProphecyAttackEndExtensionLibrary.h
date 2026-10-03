#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackEndExtensionLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackEndExtensionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** At the normal attack ending, predict one more 30 Hz frame. Keep it only if the
     * pointing direction turns MORE than the threshold. At most one extra frame per attack.
     * Slashes use the ghost sword; hooks/overs use the striking forearm. Other attacks are unchanged.
     * Enabled by default. 180 degrees disables a family; Enabled=false disables all extra inference.
     * Angles are degrees. The default is 0.75 times the measured missing slash frame (67.584 degrees). */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DisplayName="Set Attack End Extension",DefaultToSelf="Agent",ClampMin="0",ClampMax="180"))
    static bool SetAttackEndExtension(AProphecyAgent* Agent,bool Enabled=true,
        float SlashThresholdDegrees=50.688107f,float HookThresholdDegrees=50.688107f,float OverThresholdDegrees=50.688107f);
};
