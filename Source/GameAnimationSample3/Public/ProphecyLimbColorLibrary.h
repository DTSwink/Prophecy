#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Components/ActorComponent.h"
#include "ProphecyLimbColorLibrary.generated.h"
class AProphecyAgent;
class USkinnedMeshComponent;
class UTexture2D;
class UMaterialInterface;
class UMaterialInstanceDynamic;

USTRUCT()
struct FProphecyLimbColorBinding
{
    GENERATED_BODY()
    UPROPERTY() TWeakObjectPtr<USkinnedMeshComponent> Mesh;
    UPROPERTY() TObjectPtr<UMaterialInterface> Original;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> Dynamic;
};

/** Created only by Set Limb Color; never ticks or modifies physics. */
UCLASS(Transient,NotBlueprintable)
class GAMEANIMATIONSAMPLE3_API UProphecyLimbColorState : public UActorComponent
{
    GENERATED_BODY()
public:
    UProphecyLimbColorState();
    bool Bind(AProphecyAgent* Agent);
    void Set(int32 Region,const FLinearColor& Color);
    void Restore();
    virtual void OnComponentDestroyed(bool bDestroyingHierarchy) override;
    UPROPERTY(Transient) TObjectPtr<UTexture2D> Palette;
    UPROPERTY(Transient) TArray<FProphecyLimbColorBinding> Bindings;
    FLinearColor Colors[32];
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyLimbColorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Tint one UEFN Manny limb. Alpha controls tint strength; 0 restores its original
     * material color. Fingers use hand_l/r, toes use foot_l/r. Applies to both normal
     * and PhysicalMesh presentation. No per-tick work or additional render sections. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Appearance",meta=(DefaultToSelf="Agent",DisplayName="Set Limb Color"))
    static bool SetLimbColor(AProphecyAgent* Agent,FName BoneName=TEXT("head"),FLinearColor Color=FLinearColor(1.f,0.f,0.f,1.f));
    /** Restore one limb; BoneName=None restores all limbs and original materials. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Appearance",meta=(DefaultToSelf="Agent",DisplayName="Reset Limb Color"))
    static bool ResetLimbColor(AProphecyAgent* Agent,FName BoneName=NAME_None);
    UFUNCTION(BlueprintPure,Category="Prophecy|Agent|Appearance")
    static TArray<FName> GetLimbColorBones();
};
