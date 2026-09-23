#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyUpperBodyInertiaLibrary.generated.h"
class AProphecyAgent;
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyUpperBodyInertiaLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Preserve outgoing FK-core angular motion after any special, then fade to
     * normal controls. Response controls spring softness; larger is more inertial.
     * Hold/blend use 60 unpaused game ticks per authored second. Configure before
     * a special ends or inside Special Ended. Zero response/both times zero bypass. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Upper Body Inertia"))
    static bool SetAttackUpperBodyInertia(AProphecyAgent* Agent,bool Enabled=true,
        float ResponseTimeSeconds=.25f,float HoldDurationSeconds=0.f,
        float BlendToNormalDurationSeconds=.5f,float MomentumScale=1.f);
};
