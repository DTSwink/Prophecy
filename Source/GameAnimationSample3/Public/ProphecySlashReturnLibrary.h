#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySlashReturnLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySlashReturnLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** After slashL/R/LD/RD/LU/RU or pike, guide the right arm toward authored idle around
     * the front of the torso. Also guides the attacking arm after jabL/R, hookL/R and overL/R:
     * left for jabL/hookL/overL, right for jabR/hookR/overR, including half attacks.
     * Kicks, headbutts and defense are excluded.
     * Hold keeps full procedural ownership; Blend transfers it back to the NN.
     * Return Speed is cm per authored second at an initial hand-to-idle distance
     * of100cm. Each return captures Speed * InitialDistanceCm /100 once from the
     * outgoing pose; approaching or moving the target does not rescale it.
     * One authored second is60 unpaused game ticks, independent of FPS.
     * Configure before attacking or inside Special Ended. Disabled/both times zero
     * removes the feature; a new special cancels the active return. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Locomotion",meta=(DefaultToSelf="Agent",DisplayName="Set Attack Arm Return To Neutral",Keywords="Slash Pike Jab Hook Over Idle"))
    static bool SetSlashRightArmReturnToNeutral(AProphecyAgent* Agent,bool Enabled=true,
        float HoldDurationSeconds=.3f,float BlendToNNDurationSeconds=.5f,float ReturnSpeed=100.f);
};
