#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyRootMagic3Library.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyRootMagic3Library : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Independent magic channel 3, world XYZ cm/s, without mover braking.
     * Delay uses 60 unpaused game ticks/second; spread divides the velocity change
     * over Spread Ticks. Braking Deceleration is cm/s squared toward zero during
     * and after spread: 1800 matches idle braking, 0 retains velocity with no brake tick.
     * Add to Current adds to channel 3's value when the delay expires; otherwise
     * ramps from that value to World Linear Velocity. A new call replaces this
     * channel's pending linear request. Zero with defaults clears immediately.
     * Reset/full attack entry cancels pending work and clears the channel.
     * Channels 1/2 are untouched; existing attack/defense application rules apply. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Set Root Magic Velocity 3"))
    static bool SetRootMagicVelocity3(AProphecyAgent* Agent,FVector WorldLinearVelocity,
        bool bAddToCurrent=false,int32 SpreadTicks=1,float Delay=0.f,float BrakingDeceleration=1800.f);

    /** Same delay/spread semantics, world degrees/s, Z yaw only. Independent of linear. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Set Root Magic Ang Velocity 3"))
    static bool SetRootMagicAngVelocity3(AProphecyAgent* Agent,FVector WorldAngularVelocityDegrees,
        bool bAddToCurrent=false,int32 SpreadTicks=1,float Delay=0.f);

    /** Current applied/stored channel 3 value, excluding channels 1/2 and queued targets. */
    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Get Root Magic Velocity 3"))
    static FVector GetRootMagicVelocity3(AProphecyAgent* Agent);

    UFUNCTION(BlueprintPure, Category="Prophecy|Agent|Root", meta=(DefaultToSelf="Agent", DisplayName="Get Root Magic Ang Velocity 3"))
    static FVector GetRootMagicAngVelocity3(AProphecyAgent* Agent);
};
