#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Kismet/BlueprintAsyncActionBase.h"
#include "ProphecyThrowLibrary.generated.h"

class AProphecyAgent;
UENUM(BlueprintType)
enum class EProphecyThrow : uint8 { BigThrow, SmallThrow };
UENUM(BlueprintType)
enum class EProphecyThrowPhase : uint8 { Charging, Throwing, Released, Finished, Cancelled, Failed };

/** Physical launch adjustments. Animation, grip, timing and motion shaping come from the lab. */
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyThrowPhysics
{
    GENERATED_BODY()
    /** Multiplies the approved lab's velocity (which already includes its amplitude). */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Throw") float VelocityMultiplier=1;
    /** World-space rotation applied after the lab's launch direction/aim. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Throw") FRotator VelocityRotation=FRotator::ZeroRotator;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Throw") bool bOverrideTwist=false;
    /** Rotation about the weapon's long axis, in degrees per authored frame. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Throw",meta=(EditCondition="bOverrideTwist")) float TwistDegreesPerFrame=0;
};
USTRUCT(BlueprintType)
struct GAMEANIMATIONSAMPLE3_API FProphecyThrowState
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly,Category="Throw") EProphecyThrowPhase Phase=EProphecyThrowPhase::Failed;
    UPROPERTY(BlueprintReadOnly,Category="Throw") float Frame=0;
    UPROPERTY(BlueprintReadOnly,Category="Throw") float ThrowPercent=100;
    UPROPERTY(BlueprintReadOnly,Category="Throw") float ReleaseFrame=0;
    /** Remaining fraction of the game tick after the exact release. */
    UPROPERTY(BlueprintReadOnly,Category="Throw") float ReleaseRemainderFrames=0;
    UPROPERTY(BlueprintReadOnly,Category="Throw") FTransform HandWorld=FTransform::Identity;
    /** Lab weapon frame; its geometry bind must match the exported lab asset. */
    UPROPERTY(BlueprintReadOnly,Category="Throw") FTransform WeaponWorld=FTransform::Identity;
    UPROPERTY(BlueprintReadOnly,Category="Throw") FVector LinearVelocityCmPerSecond=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Category="Throw") FVector AngularVelocityRadiansPerSecond=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Category="Throw") FName ObjectKind;
    UPROPERTY(BlueprintReadOnly,Category="Throw") FVector WeaponScale=FVector::OneVector;
    UPROPERTY(BlueprintReadOnly,Category="Throw") FString Error;
};
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FProphecyThrowEvent,const FProphecyThrowState&,State);

/** Finite throw action: no Blueprint Tick is required to receive release or completion. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyThrowAction : public UBlueprintAsyncActionBase
{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintAssignable) FProphecyThrowEvent Released;
    UPROPERTY(BlueprintAssignable) FProphecyThrowEvent Completed;
    UPROPERTY(BlueprintAssignable) FProphecyThrowEvent Cancelled;
    UPROPERTY(BlueprintAssignable) FProphecyThrowEvent Failed;
    /** Trigger down. Small Throw charge is determined when Release Lab Throw is called. */
    UFUNCTION(BlueprintCallable,meta=(BlueprintInternalUseOnly="true",DisplayName="Begin Lab Throw",AutoCreateRefTerm="Physics"),Category="Prophecy|Throw")
    static UProphecyThrowAction* BeginLabThrow(AProphecyAgent* Agent,EProphecyThrow Throw,FVector TargetWorld,const FProphecyThrowPhysics& Physics);
    /** Play immediately. -1 uses the approved lab's percentage; 0..100 overrides physical charge. */
    UFUNCTION(BlueprintCallable,meta=(BlueprintInternalUseOnly="true",DisplayName="Play Lab Throw",AutoCreateRefTerm="Physics",AdvancedDisplay="ThrowPercent"),Category="Prophecy|Throw")
    static UProphecyThrowAction* PlayLabThrow(AProphecyAgent* Agent,EProphecyThrow Throw,FVector TargetWorld,const FProphecyThrowPhysics& Physics,float ThrowPercent=-1);
    virtual void Activate() override;
    void Notify(const FProphecyThrowState& State);
private:
    TWeakObjectPtr<AProphecyAgent> Agent;
    EProphecyThrow Kind=EProphecyThrow::BigThrow;
    FVector Target=FVector::ZeroVector;
    FProphecyThrowPhysics Physics;
    bool Automatic=false;
    float Percent=-1;
};
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyThrowLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Trigger up; charge is measured from unpaused game ticks, never future input. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Throw") static bool ReleaseLabThrow(AProphecyAgent* Agent);
    UFUNCTION(BlueprintCallable,Category="Prophecy|Throw") static bool CancelLabThrow(AProphecyAgent* Agent);
    UFUNCTION(BlueprintPure,Category="Prophecy|Throw") static bool GetLabThrowState(AProphecyAgent* Agent,FProphecyThrowState& State);
};
