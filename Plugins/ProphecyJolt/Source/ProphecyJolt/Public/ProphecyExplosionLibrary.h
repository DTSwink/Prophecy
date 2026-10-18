#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyExplosionReceiverComponent.h"
#include "ProphecyExplosionLibrary.generated.h"

UCLASS()
class PROPHECYJOLT_API UProphecyExplosionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Call once on BeginPlay and connect a custom event. All limbs share a 0.5-second
     * (30 unpaused game tick) cooldown. Suppressed notifications never suppress physics.
     * Rebinding the same event is idempotent and does not restart or clear the cooldown. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics", meta=(DefaultToSelf="Agent", DisplayName="Bind Explosion Impact"))
    static UProphecyExplosionReceiverComponent* BindExplosionImpact(AActor* Agent, FProphecyExplosionImpactCallback Event);

    /** One-shot outward blast on nearby Jolt-simulated bodies, including PhysicalMesh limbs.
     * Location and Radius are world centimetres. Intensity is peak pressure impulse in N*s/m^2:
     * projected collision area determines momentum; body mass determines velocity change.
     * Bounded inverse-square-like falloff has a 20%-radius soft core and reaches zero at Radius.
     * Falloff Exponent: 2 preserves the original blast; lower values spread the push farther,
     * higher values concentrate it near the centre. Zero keeps only the smooth radius cutoff.
     * Each body is sampled at its centre of mass. A body exactly at Location receives no directional kick.
     * Static/kinematic bodies and Ignore Radial Impulse components are skipped. Existing joints,
     * drives and simulation modes are retained. No damage, production VFX or wall occlusion.
     * Explosion Velocity is cm/s: zero applies instantly; positive values delay by distance/velocity.
     * Distance, direction and impulse are sampled at detonation, not tracked as recipients move.
     * Arrivals use the Jolt simulation clock and deliver at the first completed Step at/after arrival.
     * Returns affected/scheduled body count; deleted, replaced or opted-out bodies are skipped at arrival.
     * Invalid input/unavailable world returns zero. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics", meta=(WorldContext="WorldContextObject", DisplayName="Start Explosion", ReturnDisplayName="Affected Bodies"))
    static int32 StartExplosion(const UObject* WorldContextObject, FVector Location, float Intensity = 1000.f, float Radius = 500.f,
        UPARAM(meta=(ClampMin="0.0", UIMin="0.0")) float FalloffExponent = 2.f,
        UPARAM(meta=(ClampMin="0.0", UIMin="0.0")) float ExplosionVelocity = 0.f);

    /** Draw all active travelling explosion fronts for this frame, at constant radial speed.
     * Call on Tick while debugging. Shares the actual impact simulation clock; pausing physics pauses fronts.
     * Three depth-tested circles per wave. Completed/instant waves are not retained. No-op in Shipping.
     * Returns the number of active fronts submitted. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Physics", meta=(WorldContext="WorldContextObject", DisplayName="Draw Explosion Wavefronts", ReturnDisplayName="Active Wavefronts"))
    static int32 DrawExplosionWavefronts(const UObject* WorldContextObject, FLinearColor Color = FLinearColor(1.f,0.6f,0.05f,1.f), float Thickness = 1.f);
};
