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
    /** Independently select holster physics. Kinematic agents override this until they simulate again.
     * Uses Holster Return Duration to return to the class viewport mount; preserves the authored pelvis joint. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Holster Simulate Physics"))
    static bool SetHolsterSimulatePhysics(AProphecyAgent* Agent,bool Simulate=true);
    /** Import authored body/pole targets, independent D/S speeds, curves, inertia and head/return tuning. Draw Sword uses these action speeds; the real holster transform is unchanged. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword Holster Lab Profile"))
    static bool SetSwordHolsterLabProfile(AProphecyAgent* Agent,const FString& ProfileFile);
    /** Override one action's base FK return duration (0.1..5 authored seconds; 60 ticks per second).
     * Call after Set Sword Holster Lab Profile and before Draw Sword. Sheathe=false selects drawing.
     * Existing angle-dependent extra time and inertia settings are preserved. Active actions are unchanged. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword FK Return Duration"))
    static bool SetSwordFKReturnDuration(AProphecyAgent* Agent,bool Sheathe=false,float Duration=1);
    /** Sheathe=true reaches the mouth and slides in. False reaches the grip and slides out.
     * Uses the independent D/S speeds from Set Sword Holster Lab Profile.
     * One authored second is 60 unpaused game ticks. Both reach limits bound one shared progress. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Draw Sword"))
    static bool DrawSword(AProphecyAgent* Agent,bool Sheathe=false);
    /** Shrink10 means ten percent smaller (90% size). Unshrink starts after drawing clears the holster.
     * Grip stabilization holds world rotation from grip through alignment/sliding (0..100%).
     * Holster return restores the authored local mount over this many 60-tick seconds.
     * Sheathe Kinematic Fraction (0..1) stops holster physics at this reach progress, or attachment if earlier.
     * Compensation still starts at attachment; release/interruption restores the selected mode after return.
     * Attached speeds independently limit hand translation/rotation in the holster frame.
     * Stabilization rotates around the holster mesh/component origin.
     * Without the leeway phase, S waits for tip-at-entrance within tolerance, then slides.
     * Higher Solver Accuracy uses 10 velocity / 32 position iterations during the next D/S action,
     * including return, and restores the configured solver counts on completion or interruption.
     * Independent Draw/Sheathe NN Blend Ranges: X starts blending to the live NN, Y completes it.
     * Fractions of elapsed torso return; .5,.8 blends from 50% through 80%. .5 <= X <= Y <= 1.
     * Does not accelerate the motion or release the gripping arm before slide completion. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword Holster Profile"))
    static bool SetSwordHolsterProfile(AProphecyAgent* Agent,float ShrinkPercent=10,float UnshrinkDuration=.25f,float GripHolsterStabilizationPercent=0,float HolsterReturnDuration=.25f,float ShrinkDuration=.25f,float MaxAttachedSpeed=100,float MaxAttachedRotationSpeed=180,bool LeewayAttachmentPhase=true,float SheatheTipDistanceThreshold=2,bool HigherSolverAccuracy=false,FVector2D DrawNNBlendRange=FVector2D(0.5,0.8),FVector2D SheatheNNBlendRange=FVector2D(0.5,0.8),float SheatheKinematicFraction=.8f);
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
