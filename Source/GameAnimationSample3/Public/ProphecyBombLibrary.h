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
    /** Enable the cosmetic flexible fuse, or change its angular spring. Zero is floppy; higher is stiffer.
     * Can be called before ignition or while burning. The original bomb collider is retained. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|VFX", meta=(DisplayName="Set Bomb Fuse Stiffness", ReturnDisplayName="Applied"))
    static bool SetBombFuseStiffness(UStaticMeshComponent* Bomb, float Stiffness=20.f);
    /** Permanently hide this instance's fuse and stop its sparks/dynamics. An active burn timer continues. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|VFX", meta=(DisplayName="Hide Bomb Fuse", ReturnDisplayName="Hidden"))
    static bool HideBombFuse(UStaticMeshComponent* Bomb);
    /** Ignite the original CC0 bomb mesh instance. Fuse Burn Speed and Fragment Velocity are cm/s.
     * Burns the curved fuse from its tip in 60-tick authored seconds, then calls Start Explosion
     * and Spawn VDB Effect at the bomb's current shell centre. The bomb actor is consumed.
     * Twenty prepared physical shell fragments inherit its velocity plus the radial launch speed.
     * Repeated calls on an already burning bomb are ignored. Returns false for invalid inputs/assets.
     * Fragments expire after Fragment Lifetime authored seconds; no runtime mesh fracture/cooking.
     * Fragment Fade Duration fades opacity during the last part of that lifetime; zero disables fading.
     * Physical blast affects existing Jolt bodies, using the same contract as Start Explosion. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|VFX", meta=(DisplayName="Light Bomb Fuse", ReturnDisplayName="Started", AdvancedDisplay="Rotation,FragmentLifetime,SparkRotationOffset"))
    static bool LightBombFuse(UStaticMeshComponent* Bomb, float FuseBurnSpeed=2.f,
        float FragmentVelocity=700.f, float Intensity=1000.f, float Radius=500.f,
        float FalloffExponent=2.f, float ExplosionVelocity=0.f,
        EProphecyVDBEffect Effect=EProphecyVDBEffect::ShockwaveExplosion, float Scale=1.f,
        float Framerate=30.f, float DensityFadeStart=3.f, float TargetDensity=0.f,
        float DensityFadeDuration=1.f, FRotator Rotation=FRotator::ZeroRotator, float FragmentLifetime=8.f,
        UNiagaraSystem* FuseSparks=nullptr, FRotator SparkRotationOffset=FRotator::ZeroRotator,
        bool bInstantExplosion=false, bool bSpawnFragments=true, float FragmentFadeDuration=1.f);

    /** Editor-only deterministic asset preparation, used by Tools/BombFuse. */
    UFUNCTION(BlueprintCallable, meta=(BlueprintInternalUseOnly="true", DevelopmentOnly))
    static TArray<UStaticMesh*> PrepareBombMeshes(const FString& GeometryFile);
};
