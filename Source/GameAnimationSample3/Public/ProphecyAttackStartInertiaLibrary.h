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
    /** Parent-local angular inertia for spine, neck, head and clavicles on new full/half attacks.
     * Arms follow their parents without any local arm/hand inertia. Configure before triggering.
     * HoldOutTime retains full influence; BlendTime fades it to the attack. ResponseTime controls
     * spring softness; MomentumScale scales outgoing angular velocity; Alpha controls influence.
     * Times mean 60 unpaused game ticks per second. Disabled by default; disabled/Alpha 0/Response 0
     * does no sampling or spring work. Settings latch at entry; disabling cancels immediately. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Upper Body", meta=(DefaultToSelf="Agent",DisplayName="Set Attack Start FK Core Inertia"))
    static bool SetAttackStartFKCoreInertia(AProphecyAgent* Agent, bool Enabled=false,
        float HoldOutTime=.1f, float BlendTime=.3f, float ResponseTime=.25f, float MomentumScale=1.f,
        UPARAM(meta=(ClampMin="0",ClampMax="1")) float Alpha=1.f);

    /** NN hand position/rotation inertia on a new full or half attack. Configure
     * before triggering; repeated attack requests and half/full switches do not
     * restart it. ReferenceAlpha: 0 locomotion root local, 1 spine_05 local;
     * intermediate values blend root position/heading toward spine position/rotation.
     * Hold keeps full influence, then BlendTime fades to the attack checkpoint.
     * ResponseTime controls softness; MomentumScale scales entry velocity only.
     * Times use 60 unpaused ticks/second. Disabled/Alpha 0: no sampling or clock.
     * Settings latch at entry; disabling cancels immediately. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Hands", meta=(DefaultToSelf="Agent",DisplayName="Set Attack Start Hand Inertia"))
    static bool SetAttackStartHandInertia(AProphecyAgent* Agent, bool Enabled,
        float HoldOutTime=.1f, float BlendTime=.3f,
        UPARAM(meta=(ClampMin="0",ClampMax="1")) float ReferenceAlpha=1.f,
        float ResponseTime=.25f, float MomentumScale=1.f,
        UPARAM(meta=(ClampMin="0",ClampMax="1")) float Alpha=1.f,
        bool LeftHand=true, bool RightHand=true);

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

    /** Both feet retain their world motion at full-attack entry, fading to authored
     * motion over the selected game-tick windows. Continues across lower release.
     * Pure half entry does not start it. Disabled/finished: no sampling or pose work. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Feet", meta=(DefaultToSelf="Agent"))
    static bool SetAttackStartFootInertia(AProphecyAgent* Agent, bool Enabled,
        int32 TranslationWindowFrames=5, float TranslationInertia=1.f,
        int32 RotationWindowFrames=5, float RotationInertia=1.f);
};
