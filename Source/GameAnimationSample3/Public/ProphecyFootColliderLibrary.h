#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyFootColliderLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyFootColliderLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Shorten both Jolt foot boxes at the toe end, keeping the heel fixed.
     * Absolute cm removed from the original collider, not cumulative. Zero restores it.
     * Call with Jolt simulation active. All animation modes; retained across simulation switches. Mass, joints and target poses
     * are unchanged. Does not edit the shared Physics Asset or the Chaos collider.
     * No per-tick work. Requires box foot colliders; invalid/excessive trims fail without changes. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Agent|Jolt|Collision", meta=(DefaultToSelf="Agent", AdvancedDisplay="OutError"))
    static bool SetFootColliderFrontTrim(AProphecyAgent* Agent, FString& OutError, float TrimCm=0.0f);
};
