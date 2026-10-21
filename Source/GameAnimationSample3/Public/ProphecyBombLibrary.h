#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyVDBLibrary.h"
#include "ProphecyBombLibrary.generated.h"

class UStaticMeshComponent;
class UStaticMesh;
class UNiagaraSystem;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyBombLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Permanently hide this instance's fuse and stop its sparks. An active burn timer continues. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|VFX", meta=(DisplayName="Hide Bomb Fuse", ReturnDisplayName="Hidden"))
    static bool HideBombFuse(UStaticMeshComponent* Bomb);
    /** Ignite the original CC0 bomb mesh instance. Fuse Burn Speed and Fragment Velocity are cm/s.
     * Burns the curved fuse from its tip in 60-tick authored seconds, then calls Start Explosion
     * and Spawn VDB Effect at the bomb's current shell centre. The bomb actor is consumed.
     * Twenty prepared physical shell fragments inherit its velocity plus the radial launch speed.
     * Repeated calls on an already burning bomb are ignored. Returns false for invalid inputs/assets.
     * Fragments expire after Fragment Lifetime authored seconds; no runtime mesh fracture/cooking.
     * Fragment Fade Duration fades opacity during the last part of that lifetime; zero disables fading.
     * Fuse Cap is the remaining fuse fraction at detonation: 0 burns fully, 1 explodes immediately.
     * Fuse Sparks follows the burn tip with world Z up, independent of bomb rotation. Null means no emitter.
     * Physical blast affects existing Jolt bodies, using the same contract as Start Explosion. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|VFX", meta=(DisplayName="Light Bomb Fuse", ReturnDisplayName="Started", AdvancedDisplay="Rotation,FragmentLifetime"))
    static bool LightBombFuse(UStaticMeshComponent* Bomb, float FuseBurnSpeed=2.f,
        float FragmentVelocity=700.f, float Intensity=1000.f, float Radius=500.f,
        float FalloffExponent=2.f, float ExplosionVelocity=0.f,
        EProphecyVDBEffect Effect=EProphecyVDBEffect::ShockwaveExplosion, float Scale=1.f,
        float Framerate=30.f, float DensityFadeStart=3.f, float TargetDensity=0.f,
        float DensityFadeDuration=1.f, FRotator Rotation=FRotator::ZeroRotator, float FragmentLifetime=8.f,
        UNiagaraSystem* FuseSparks=nullptr,
        bool bInstantExplosion=false, bool bSpawnFragments=true, float FragmentFadeDuration=1.f,
        UPARAM(meta=(ClampMin="0.0",ClampMax="1.0",UIMin="0.0",UIMax="1.0")) float FuseCap=0.f,
        UPARAM(DisplayName="Optimised", meta=(ToolTip="Cache the finished VDB smoke volume when stable. Freezes its lighting and disables projected smoke shadows. Unchecked keeps current rendering.")) bool bOptimised=false,
        FLinearColor TemperatureColor=FLinearColor(0.99f,0.13f,0.011f,1.f), FLinearColor ScatteringColor=FLinearColor::White);

    /** Editor-only deterministic asset preparation, used by Tools/BombFuse. */
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true", DevelopmentOnly))
    static TArray<UStaticMesh*> PrepareBombMeshes(const FString& GeometryFile);
};
