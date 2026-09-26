#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyGhostAttackLibrary.generated.h"
class AProphecyAgent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyGhostAttackLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Draw the raw full attack ghost, its PHAT shapes (cyan), sword (yellow), and
     * ghost-space target (red). Works during half and full attacks. Call each Tick;
     * Duration 0 draws one frame. World Offset moves all drawing together for comparison.
     * Shows latest NN policy pose, before graft/clamps/roll corrections, not interpolated.
     * No spawned objects or tick registration. Disabled/inactive/Shipping does no drawing.
     * Uses authored PHAT geometry; physical-only collider trims are not ghost geometry. */
    UFUNCTION(BlueprintCallable,Category="Prophecy|Agent|Debug",meta=(DefaultToSelf="Agent",AdvancedDisplay="Duration,Thickness"))
    static bool VisualizeGhostAttack(AProphecyAgent* Agent,bool Enabled=true,
        FVector WorldOffset=FVector(150,0,0),float Duration=0.0f,float Thickness=1.0f);
};
