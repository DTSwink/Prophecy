#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecySwordHolsterLibrary.generated.h"
class AProphecyAgent;
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecySwordHolsterLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Import authored body/pole targets, independent D/S speeds, curves, inertia and head/return tuning. Saved action speeds override Draw Sword speed pins while this profile is configured; the real holster transform is unchanged. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword Holster Lab Profile"))
    static bool SetSwordHolsterLabProfile(AProphecyAgent* Agent,const FString& ProfileFile);
    /** Sheathe=true reaches the mouth and slides in. False reaches the grip and slides out.
     * Linear speeds are cm per authored second; rotation is degrees per authored second.
     * One authored second is 60 unpaused game ticks. Both reach limits bound one shared progress. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Draw Sword"))
    static bool DrawSword(AProphecyAgent* Agent,bool Sheathe=false,float MaxReachSpeed=100,float MaxReachRotationSpeed=180,float SlidingSpeed=60);
    /** Shrink10 means ten percent smaller (90% size). Unshrink starts after drawing clears the holster.
     * Grip stabilization holds world rotation from grip through alignment/sliding (0..100%).
     * Holster return restores the authored local mount over this many 60-tick seconds.
     * Attached speeds independently limit hand translation/rotation in the holster frame.
     * Stabilization rotates around the holster mesh/component origin.
     * Without the leeway phase, S waits for tip-at-entrance within tolerance, then slides. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword Holster Profile"))
    static bool SetSwordHolsterProfile(AProphecyAgent* Agent,float ShrinkPercent=10,float UnshrinkDuration=.25f,float GripHolsterStabilizationPercent=0,float HolsterReturnDuration=.25f,float ShrinkDuration=.25f,float MaxAttachedSpeed=100,float MaxAttachedRotationSpeed=180,bool LeewayAttachmentPhase=true,float SheatheTipDistanceThreshold=2);
    /** Capture the authored SwordRef and base blade marker before BeginPlay deletes them. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Capture Sword Holster Reference"))
    static bool CaptureSwordHolsterReference(AProphecyAgent* Agent);
    /** Call on Tick to visualize S's entry gate. Cone = allowed blade tilt (cyan outside, green within full tolerance); roll dial shows
     * the remaining roll allowance at the current tilt. Green/red ray uses the full rotation
     * test, including roll. Tip marker measures distance to the entrance; rotation admits attachment. Draws during S reach and tip alignment.
     * Display Length only changes drawing size. Duration zero draws for one frame. Returns true when drawn. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Visualize Sheathing Leeway",AdvancedDisplay="Duration"))
    static bool VisualizeSheathingLeeway(AProphecyAgent* Agent,float DisplayLength=40,float Duration=0);
};
