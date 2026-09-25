#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyWalkPinningLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyWalkPinningLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Run only: raise the higher effective pin toward 1 using Alpha, after the
     * existing near-floor rule. Lower pin unchanged; exact ties select left.
     * Per agent. Alpha0 removes the setting; Alpha1 fully pins the winner.
     * Applies to the Run contribution in Walk/Run blends. No timer or extra inference. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Foot Pinning",meta=(DefaultToSelf="Agent",ClampMin="0",ClampMax="1"))
    static bool SetRunPinningBoost(AProphecyAgent* Agent,float Alpha=0.f);

    /** Raise the opposite foot's Walk pin to (1 - this foot's backward bound cap) * Multiplier,
     * clamped to 0..1. Uses geometric release, even if the source foot was not selected.
     * Preserves stronger existing pins; receiving foot's own bounds, raw limit and reach guard win.
     * Requires an enabled backward bound; circle alone does not drive transfer. Walk contribution only.
     * Off until configured; disable/zero removes settings, no timer or additional inference. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning",meta=(DefaultToSelf="Agent",ClampMin="0"))
    static bool SetWalkPinningBackwardTransfer(AProphecyAgent* Agent,bool Enabled=true,float Multiplier=1.f);

    /** Cap Walk pinning AFTER temporal smoothing using signed backward distance in cm.
     * Distance <= Min: cap1; distance >= Max: cap0; linear between. Sideways/height ignored.
     * Root Index selects heading only:0=current,1..8=future samples. Distance is always
     * measured from the current root (window0), never the selected future position.
     * Lerp Target blends that heading toward the final locomotion facing goal:
     * 0 preserves the selected root heading; 1 uses the goal beyond the window.
     * Off until configured; disabling removes its settings and all projection/window work. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning")
    static bool SetWalkPinningBackwardBound(AProphecyAgent* Agent,bool Enabled=true,float DistanceMinCm=20.f,float DistanceMaxCm=60.f,int32 RootIndex=0,UPARAM(meta=(ClampMin="0",ClampMax="1")) float LerpTarget=0.f);

    /** One-frame ground arrows for the configured backward bound: green=1, red=0,
     * gradient in between, white=selected root heading. Call from Tick while debugging.
     * Returns false when disabled or the selected continuous window is unavailable. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning|Debug", meta=(DevelopmentOnly))
    static bool DrawWalkPinningBackwardBound(AProphecyAgent* Agent,float WidthCm=100.f,float GroundOffsetCm=2.f);

    /** Circular variant: horizontal distance to the selected continuous root, independent of heading.
     * Cap1 inside Min, cap0 outside Max, linear between; applied after smoothing.
     * Independent enable/settings; if both bounds are enabled, the smaller cap wins. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning")
    static bool SetWalkPinningCircleBound(AProphecyAgent* Agent,bool Enabled=true,float DistanceMinCm=20.f,float DistanceMaxCm=60.f,int32 RootIndex=0);

    /** One-frame ground circles: inner green=1, middle yellow=.5, outer red=0,
     * with radial arrows. Call from Tick only while debugging. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning|Debug", meta=(DevelopmentOnly))
    static bool DrawWalkPinningCircleBound(AProphecyAgent* Agent,float GroundOffsetCm=2.f);

    /** Smooth the visible Walk checkpoint's pin strength independently per foot.
     * Pin In/Out Frames are unpaused game ticks for a full 0->1 / 1->0 ramp (60 = 1 authored second).
     * Reversals continue from the current weight; zero makes that direction immediate.
     * Raw-value limit and reach-guard vetoes remain immediate. Run/specials are unchanged.
     * Off until configured. Disabling (or both durations zero) removes history and ticking. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning", meta=(ClampMin="0"))
    static bool SetWalkPinningSmoothing(AProphecyAgent* Agent,bool Enabled=true,int32 PinInFrames=3,int32 PinOutFrames=3);

    /** Temporary A/B switch. Uses the latest NN pin request and existing Pin In/Out
     * frames to update Walk foot targets every unpaused game tick. NN inference stays
     * at its configured rate. Off by default; disable restores the ordinary path.
     * Requires Set Walk Pinning Smoothing; no state/tick work when disabled. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Foot Pinning",meta=(DefaultToSelf="Agent",DisplayName="Set Walk Pinning Every Tick"))
    static bool SetWalkPinningEveryTick(AProphecyAgent* Agent,bool Enabled=true);

    /** Walk only (including its recovery blend): veto a pin that would fully extend
     * the leg, then suppress that foot for Frames unpaused game ticks (60 = 1 authored second).
     * Frames includes the rejecting tick; zero vetoes only the current prediction.
     * Does not select the other foot. Off until configured; disabling clears both cooldowns. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning", meta=(ClampMin="0"))
    static bool SetWalkPinningReachGuard(AProphecyAgent* Agent,bool Enabled=true,int32 Frames=6);

    /** Walk only: if both raw NN pin outputs are positive and their absolute difference is
     * <= Tolerance, bypass the hard winner. Tolerance is in raw NN output units, not cm.
     * Zero tolerance disables the exception, preserving the original rule (including ties).
     * Tolerance Fallback: 0 = both unpinned; 1 = decoded soft weights; intermediate values scale them.
     * Uses the existing sigmoid decode and PinScale. Does not change Run or attack pinning. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Foot Pinning")
    static bool SetWalkPinningTolerance(AProphecyAgent* Agent,float Tolerance=0.f,float ToleranceFallback=0.f);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Foot Pinning")
    static bool GetWalkPinningTolerance(AProphecyAgent* Agent,float& Tolerance,float& ToleranceFallback);
};
