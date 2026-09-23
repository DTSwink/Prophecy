#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAgentTimeLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAgentTimeLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Per-agent locomotion speed: 2 advances root and NN twice as fast; 0.5 is
     * half speed. Must be finite and positive. Keeps trained NN steps unchanged.
     * Blends/holds retain their usual 60-game-tick durations. Attack (including
     * half attack), active parry and active dodge reset this permanently to 1.
     * A queued defense awaiting Armed is still locomotion. Non-1 requests during
     * a special return false. At 1 there is no extra inference or active clock
     * after the current interpolation interval finishes. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Time",meta=(DefaultToSelf="Agent",DisplayName="Set Agent Time Dilatation"))
    static bool SetAgentTimeDilation(AProphecyAgent* Agent,float Multiplier=1.f);

    /** Current configured multiplier; 1 during specials and after their end. */
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Time",meta=(DefaultToSelf="Agent",DisplayName="Get Agent Time Dilatation"))
    static float GetAgentTimeDilation(AProphecyAgent* Agent);
};
