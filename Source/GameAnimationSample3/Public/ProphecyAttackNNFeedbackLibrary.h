#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackNNFeedbackLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackNNFeedbackLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Controls direct write-back of upper modifiers into the active attack checkpoint.
     * All checked restores the pre-audit behavior. Unchecked keeps the modifier's
     * visible/physical effect but skips its write-back. Turn all off for isolated
     * upper recurrence; another enabled modifier can still encode a combined pose.
     * Old full/half ownership is preserved: the four inertia/cone paths only feed
     * full attacks; the wrist constraint can feed both. Does not enable modifiers.
     * Applies to subsequent predictions, without rewinding existing NN history.
     * Configure before Trigger Attack for a reproducible comparison. The earlier
     * Set Attack Motion Inertia filter remains presentation-only. Saved by agent reset. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Attack",meta=(DefaultToSelf="Agent",DisplayName="Set Attack NN Feedback"))
    static bool SetAttackNNFeedback(AProphecyAgent* Agent,bool StartCoreInertia=true,
        bool StartHandInertia=true,bool HandInertia=true,bool ArmCone=true,bool LeftWristConstraint=true);
};
