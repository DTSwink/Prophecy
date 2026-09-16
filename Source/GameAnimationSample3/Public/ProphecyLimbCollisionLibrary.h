#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyLimbCollisionLibrary.generated.h"
class AProphecyAgent;

/** Per-body Jolt collision overrides, automatically suspended during attacks/parry/dodge. */
UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyLimbCollisionLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Changes the selected PHAT body's object channel during locomotion. Include Children
     * selects descendant PHAT bodies too (thigh_r includes calf_r and foot_r).
     * Requires a live Jolt rig. Automatically tracked; original settings return for combat.
     * Does not change PHAT assets, collision shapes, or the self-collision pair table. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Collision", meta=(DefaultToSelf="Agent", AdvancedDisplay="OutError"))
    static bool SetJoltLimbCollisionChannel(AProphecyAgent* Agent,FName BoneName,
        TEnumAsByte<ECollisionChannel> ObjectChannel,FString& OutError,bool bIncludeChildren=false);

    /** Overrides this body's response to the selected channel during locomotion.
     * Standard bilateral collision rules apply. For leg-leg filtering, assign a dedicated
     * object channel to the legs on both agents, then set their response to that channel to Ignore.
     * Overlap means no physical blocking; this node does not add Jolt overlap-event support. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Collision", meta=(DefaultToSelf="Agent", AdvancedDisplay="OutError"))
    static bool SetJoltLimbCollisionResponse(AProphecyAgent* Agent,FName BoneName,
        TEnumAsByte<ECollisionChannel> Channel,TEnumAsByte<ECollisionResponse> Response,
        FString& OutError,bool bIncludeChildren=false);

    /** Restore captured PHAT collision and remove these bodies from the modified list. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Collision", meta=(DefaultToSelf="Agent", AdvancedDisplay="OutError"))
    static bool ResetJoltLimbCollision(AProphecyAgent* Agent,FName BoneName,FString& OutError,bool bIncludeChildren=false);

    /** Bodies with configured overrides, including overrides currently suspended for combat. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Jolt|Collision", meta=(DefaultToSelf="Agent"))
    static TArray<FName> GetModifiedLimbCollisionBones(AProphecyAgent* Agent);

    /** Read actual native Jolt settings on demand; no capture or per-frame readback. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Jolt|Collision", meta=(DefaultToSelf="Agent"))
    static bool GetJoltLimbCollisionResponse(AProphecyAgent* Agent,FName BoneName,
        TEnumAsByte<ECollisionChannel> Channel,TEnumAsByte<ECollisionChannel>& ObjectChannel,
        TEnumAsByte<ECollisionResponse>& Response,bool& bModified,bool& bLocomotionOverrideActive);
};
