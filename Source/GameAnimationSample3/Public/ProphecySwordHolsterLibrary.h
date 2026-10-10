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
    /** Import independent timing curves, body/head controls and D/S FK return profiles from a lab JSON file. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword Holster Lab Profile"))
    static bool SetSwordHolsterLabProfile(AProphecyAgent* Agent,const FString& ProfileFile);
    /** Sheathe=true reaches the mouth and slides in. False reaches the grip and slides out.
     * Linear speeds are cm per authored second; rotation is degrees per authored second.
     * One authored second is 60 unpaused game ticks. Both reach limits bound one shared progress. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Draw Sword"))
    static bool DrawSword(AProphecyAgent* Agent,bool Sheathe=false,float MaxReachSpeed=100,float MaxReachRotationSpeed=180,float SlidingSpeed=60);
    /** Shrink10 means ten percent smaller (90% size). Restore duration starts after drawing clears the holster. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Set Sword Holster Profile"))
    static bool SetSwordHolsterProfile(AProphecyAgent* Agent,float ShrinkPercent=10,float UnshrinkDuration=.25f);
    /** Capture the authored SwordRef and base blade marker before BeginPlay deletes them. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Sword",meta=(DefaultToSelf="Agent",DisplayName="Capture Sword Holster Reference"))
    static bool CaptureSwordHolsterReference(AProphecyAgent* Agent);
};
