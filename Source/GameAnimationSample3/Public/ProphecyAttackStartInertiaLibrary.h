#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyAttackStartInertiaLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyAttackStartInertiaLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Full attack entry only; retriggering an ongoing attack does not restart it.
     * Windows count unpaused game ticks (60 Hz convention), independently of FPS.
     * Strength 1 keeps the previous WORLD pelvis delta on the first frame, then
     * linearly fades to the authored target on the last frame. Rotation uses the
     * previous world angular delta. Windows <=1 or strength 0 bypass that channel.
     * Disabled by default. No history, timer or pose correction when disabled.
     * Half attacks keep locomotion ownership of the pelvis. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Pelvis", meta=(DefaultToSelf="Agent"))
    static bool SetAttackStartPelvisInertia(AProphecyAgent* Agent, bool Enabled,
        int32 TranslationWindowFrames=5, float TranslationInertia=1.f,
        int32 RotationWindowFrames=5, float RotationInertia=1.f);
};
