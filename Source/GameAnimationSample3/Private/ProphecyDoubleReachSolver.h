#pragma once
#include "CoreMinimal.h"
#include "ProphecyDoubleReachTypes.h"

// Same numerical solver as the DoubleReach animation proxy, without pose/rig transport.
namespace ProphecyNativeReach
{
struct FState
{
    double Body[6] = {};
    FVector Targets[2] = {}, Elbows[2] = {};
    bool Active[2] = {};
};
TConstArrayView<FName> BoneNames();
bool Step(TConstArrayView<FTransform> Base, EProphecyDoubleReachMode Mode,
    const FVector (&Targets)[2], const float (&Speed)[2], FState& State,
    TArray<FTransform>& Output, double Dt);
}
