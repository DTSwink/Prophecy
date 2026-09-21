#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyClampProfileLibrary.generated.h"
class AProphecyAgent;

UENUM(BlueprintType)
enum class EProphecyClampProfileMode : uint8 { All, Locomotion, Attack, Parry, Dodge };

UENUM(BlueprintType)
enum class EProphecyClampType : uint8 { Calf, Forearm, Hand, Foot };

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyClampProfileLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Restore only the selected existing clamp setting, shared left/right.
     * Duration 1 = 60 unpaused ticks; <=0 is immediate. Off blends through 1000
     * allowance, then the saved enabled/override flags are restored exactly. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Physical Profiles",meta=(DefaultToSelf="Agent"))
    static bool BlendClampToSnapshot(AProphecyAgent* Agent,EProphecyClampType Clamp,float DurationSeconds=1.f,
        FName SnapshotName=NAME_None,EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All);
    /** Restore all existing clamp types in the selected mode(s). */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Physical Profiles",meta=(DefaultToSelf="Agent"))
    static int32 BlendAllClampsToSnapshot(AProphecyAgent* Agent,float DurationSeconds=1.f,
        FName SnapshotName=NAME_None,EProphecyClampProfileMode Mode=EProphecyClampProfileMode::All);
};
