#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyHandInertiaLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyHandInertiaCheckpoint : uint8 { Walk, Run, Attack };

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyHandInertiaLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Hand Bone is hand_l or hand_r. Disabled by default. Applies to the IK target in every simulation mode. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Hand Inertia")
    static bool SetHandInertiaEnabled(AProphecyAgent* Agent, FName HandBone, bool bEnabled);

    /** Split vector pins for separate X/Y/Z controls. All values 0..1, default 1.
     * 1 follows the NN; 0 preserves world momentum. Linear/angular control axes rotate with the current root.
     * Walk/Run values blend with actual checkpoint weights. Attack covers the shared attack checkpoint. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Hand Inertia")
    static bool SetHandInertiaCheckpoint(AProphecyAgent* Agent, FName HandBone,
        EProphecyHandInertiaCheckpoint Checkpoint, FVector LinearFollow = FVector(1,1,1), FVector AngularFollow = FVector(1,1,1));

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Hand Inertia")
    static bool GetHandInertiaCheckpoint(AProphecyAgent* Agent, FName HandBone,
        EProphecyHandInertiaCheckpoint Checkpoint, bool& bEnabled, FVector& LinearFollow, FVector& AngularFollow);
};
