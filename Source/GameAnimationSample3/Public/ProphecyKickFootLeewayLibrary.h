#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyKickFootLeewayLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyKickFootLeewayLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Jolt ankle joints: during kickL/kickR allow both feet to extend along their calf's length.
     * Immediate on kick start; on any attack exit shrink to zero without a hold.
     * Duration 1 = 60 unpaused game ticks. Zero leeway disables; zero duration restores immediately.
     * Also permits the matching axial foot drive target. Angular limits/rotations are unchanged. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Physics",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetKickFootJointLeeway(AProphecyAgent* Agent,float LeewayCm=0.f,float ReturnDurationSeconds=1.f);
};
