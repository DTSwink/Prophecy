#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltHitImpactLibrary.generated.h"

class UPrimitiveComponent;

UCLASS()
class PROPHECYJOLT_API UProphecyJoltHitImpactLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Opt a standalone dynamic component into clean Hit continuation. Call once
     * before its first physics step (BeginPlay is supported before Jolt admission).
     * Keeps one start-of-step pose per enabled component; false removes it.
     * Does not change collisions, masses, velocities or joints. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics|Hit", meta=(DisplayName="Enable Clean Hit Continuation"))
    static void EnableCleanHitContinuation(UPrimitiveComponent* Component, bool Enabled=true);

    /** Call synchronously inside Event Hit AFTER your Blueprint accepts a pike,
     * BEFORE creating its cut joint. Continues the opted-in standalone body along
     * its incoming trajectory for this frame, replacing native pose and velocities
     * together. Other body response and joint settings are left alone.
     * Requires one collision substep, no pre-existing joint on the receiver, and
     * no other solved contact pair involving it this step. Refuses ambiguous cases,
     * welded/kinematic bodies and calls outside the matching Hit; Reason explains.
     * Incoming velocity includes this step's gravity/damping. Not a physics replay.
     * No persistent no-reaction mode; normal collisions resume immediately. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics|Hit", meta=(DefaultToSelf="HitReceiver", DisplayName="Cancel Hit Reaction", ReturnDisplayName="Accepted", AdvancedDisplay="Reason"))
    static bool AcceptPikeHit(const UObject* HitReceiver, FString& Reason);

    /** Call directly inside a Jolt Hit event, before any Delay. Hit Receiver is the
     * receiving actor (Self) or receiving component. The current hit is read automatically.
     * Impact Speed is incoming relative closing speed along the contact normal,
     * in cm/s, measured before solving, including both bodies' angular motion.
     * Relative Velocity is receiver minus other at the sampled contact points.
     * Multiple points/substeps report the fastest closing sample, not their sum.
     * Both recipients get the same nonnegative speed. Returns false/zero outside
     * the matching event or without a native pre-solve sample (including Chaos).
     * This is speed, not impulse/energy; sustained contacts can produce more events. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Physics|Hit", meta=(DefaultToSelf="HitReceiver", DisplayName="Get Hit Impact Speed", ReturnDisplayName="Valid", AdvancedDisplay="RelativeVelocity"))
    static bool GetHitImpactSpeed(const UObject* HitReceiver,
        double& ImpactSpeed, FVector& RelativeVelocity);

    /** Estimate all five sword values one physics tick before the incoming contact sample.
     * Call synchronously inside the receiving sword's Hit event, before any Delay.
     * Hit Receiver is Self or the hit component. Tip Distance is in world centimetres
     * along the sword component's local +Z axis, without applying component scale again.
     * Use the component-origin-to-tip distance from your sword's get limits location.
     * Rewinds using constant incoming COM velocity and world angular velocity.
     * Velocity and Tip Velocity are world cm/s at the estimated origin and tip;
     * Angular Velocity is world radians/s. Location and rotation are the estimated
     * component world pose, not the COM or hand pose. No per-body tick history.
     * Lookback is the full current physics tick, even with collision substeps.
     * This is an estimate, not the exact previous tick boundary: speculative/CCD
     * contacts sample at different phases; earlier forces/impacts are not undone.
     * Get Hit Impact Speed remains the measured incoming contact-time motion.
     * Handles independently simulated, kinematic and welded sword components.
     * Skeletal-body/ISM contacts and calls outside the matching Jolt event return
     * false and zero outputs. Computed only on contacts requesting Hit events. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Physics|Hit", meta=(DefaultToSelf="HitReceiver", DisplayName="Get Hit Pre Impact State", ReturnDisplayName="Valid", Keywords="sword prehit rewind extrapolate velocity angular tip location rotation"))
    static bool GetHitPreImpactState(const UObject* HitReceiver, double TipDistance,
        FVector& Velocity, FVector& TipVelocity, FVector& AngularVelocityRad,
        FVector& Location, FRotator& Rotation);
};
